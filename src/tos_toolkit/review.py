"""Adversarial review harness.

Same idea as a code reviewer, but the prompt is written to assume the author is
wrong. The harness pins a model so the reviewer's behaviour is reproducible, and
parses a machine-readable verdict so the result can gate a commit.

Exit codes
----------
0  PASS or WARN (human decides)
1  BLOCK — do not commit
2  review could not run, or produced no parseable verdict
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

PROMPT_FILE = Path(__file__).resolve().parent / "prompts" / "adversarial-review.md"
VERDICT_RE = re.compile(r"VERDICT:\s*(BLOCK|WARN|PASS)", re.IGNORECASE | re.ASCII)
MAX_INLINE_CHARS = 400_000
_SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "site-packages",
    "__pycache__",
    "build",
    "dist",
    ".review",
}


class ReviewUnavailable(Exception):
    """Raised when the review scope cannot be established."""


def _git(root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args], capture_output=True, text=True, timeout=60
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ReviewUnavailable(f"git failed: {exc}") from exc
    if result.returncode != 0:
        raise ReviewUnavailable(result.stderr.strip() or f"git {args[0]} failed")
    return result.stdout


def _has_head(root: Path) -> bool:
    """True when the repo has at least one commit. Never raises."""
    try:
        _git(root, "rev-parse", "--verify", "HEAD")
    except ReviewUnavailable:
        return False
    return True


def _is_repo(root: Path) -> bool:
    try:
        _git(root, "rev-parse", "--git-dir")
    except ReviewUnavailable:
        return False
    return True


def _inlined_files(root: Path, files: list[Path]) -> tuple[str, list[str]]:
    """Inline the files under review, and report any that were left out.

    A file dropped for size means the reviewer never saw it, so a PASS cannot be
    trusted — the caller turns this into exit 2 rather than a green gate.
    """
    chunks: list[str] = []
    skipped: list[str] = []
    total = 0
    for path in files:
        try:
            body = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            chunks.append(f"--- {path.name} (unreadable) ---\n")
            continue
        if total + len(body) > MAX_INLINE_CHARS:
            chunks.append(f"--- {path.name} (skipped, size budget) ---\n")
            skipped.append(str(path))
            continue
        total += len(body)
        chunks.append(f"--- {path} ---\n{body}\n")
    return "\n".join(chunks), skipped


def _scope(root: Path, mode: str, paths: list[str]) -> str:
    thinkscript = sorted(root.rglob("*.thinkscript"))
    if mode == "audit":
        listed = "\n".join(f"- {p.relative_to(root) if p.is_relative_to(root) else p}" for p in thinkscript)
        return (
            "### repository sweep\n\n"
            "Review every ThinkScript file for correctness, consistency, header\n"
            "honesty, and copy-paste drift between duplicates.\n\n"
            f"### files\n\n{listed}\n"
        )

    if mode == "files":
        if not paths:
            raise ReviewUnavailable("--mode files needs at least one path")
        selected: list[Path] = []
        for raw in paths:
            candidate = Path(raw)
            if not candidate.is_absolute():
                candidate = root / raw
            if candidate.is_dir():
                for pattern in ("*.thinkscript", "*.py"):
                    for found in sorted(candidate.rglob(pattern)):
                        if _SKIP_DIRS & set(found.parts):
                            continue
                        selected.append(found)
            elif candidate.is_file():
                selected.append(candidate)
            else:
                raise ReviewUnavailable(f"path not found: {raw}")
        if not selected:
            raise ReviewUnavailable("no reviewable files matched")
        text, skipped = _inlined_files(root, selected)
        if skipped:
            raise ReviewUnavailable(
                "too large to review in one call (size budget): "
                + ", ".join(skipped)
                + "\nReview fewer files at a time — a PASS that never saw these is worthless."
            )
        return "### files under review\n\n" + text

    if not _is_repo(root):
        raise ReviewUnavailable(f"{root} is not a git repository")

    status = _git(root, "status", "--porcelain")
    if not status.strip():
        return ""

    parts = ["### git status\n", status]
    if _has_head(root):
        parts += ["\n### git diff (unstaged)\n", _git(root, "diff")]
    parts += ["\n### git diff (staged)\n", _git(root, "diff", "--cached")]

    untracked_out = _git(root, "ls-files", "--others", "--exclude-standard")
    untracked = [
        root / name for name in untracked_out.splitlines() if name.strip()
    ]
    untracked_text, skipped = _inlined_files(root, untracked)
    parts += ["\n### untracked file contents\n", untracked_text]
    if skipped:
        parts.append(
            "\n### WARNING: not reviewed (size budget)\n"
            + "".join(f"- {path}\n" for path in skipped)
            + "\nA verdict that did not see these files is incomplete.\n"
        )
    return "".join(parts)


def _compose(root: Path, mode: str, scope: str) -> str:
    prompt = PROMPT_FILE.read_text(encoding="utf-8")
    return (
        f"{prompt}\n\n---\n\n## Scope\n\n"
        f"Mode: `{mode}`  ·  repository root: `{root}`\n\n{scope}\n"
    )


def _invoke(config, prompt: str) -> tuple[int, str, str]:
    """Return (exit code, stdout, stderr) from the configured harness.

    Never raises: a hung or missing harness must map to exit 2, not a traceback
    (which the shell would read as exit 1 = BLOCK).
    """
    try:
        return _invoke_inner(config, prompt)
    except subprocess.TimeoutExpired:
        return 2, "", "review harness timed out"
    except OSError as exc:
        return 2, "", f"could not run review harness: {exc}"


def _invoke_inner(config, prompt: str) -> tuple[int, str, str]:
    harness = config.review_harness
    if harness == "codex":
        binary = shutil.which("codex")
        if binary is None:
            return 2, "", "codex CLI not on PATH"
        result = subprocess.run(
            [
                binary,
                "exec",
                "--sandbox",
                "read-only",
                "--cd",
                str(config.root),
                "--model",
                config.review_model,
                "--config",
                f'model_reasoning_effort="{config.review_effort}"',
                "-",
            ],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=1800,
        )
        return result.returncode, result.stdout, result.stderr

    binary = shutil.which("claude")
    if binary is None:
        return 2, "", "claude CLI not on PATH"
    result = subprocess.run(
        [
            binary,
            "-p",
            "--model",
            config.review_model,
            "--permission-mode",
            "dontAsk",
            "--allowedTools",
            "Read",
            "Grep",
            "Glob",
        ],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=1800,
    )
    return result.returncode, result.stdout, result.stderr


PINNED_HARNESS = "codex"
PINNED_MODEL = "gpt-6.1-sol"


def _lint_preflight(config) -> bool:
    """Refuse to review code that already fails static analysis.

    Reviewing a file that lint rejects wastes the model call and can produce a
    PASS on a diff that does not even parse.
    """
    from .checks import Context, run_all
    from .registry import load as load_registry

    registry = load_registry()
    targets = [
        config.root / target
        for target in config.targets
        if (config.root / target).exists()
    ]
    if not targets:
        return True

    errors = 0
    for target in targets:
        for path in sorted(target.rglob("*.thinkscript")):
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            ctx = Context(
                path=path, root=config.root, text=text, config=config, registry=registry
            )
            for finding in run_all(ctx):
                if finding.is_error:
                    errors += 1
                    print(finding.render(), file=sys.stderr)
    if errors:
        print(
            f"review: {errors} static error(s); fix them first (tos lint).",
            file=sys.stderr,
        )
        return False
    return True


def run(config, mode: str = "diff", paths: list[str] | None = None) -> int:
    root = config.root
    if not _lint_preflight(config):
        return 1
    try:
        scope = _scope(root, mode, paths or [])
    except ReviewUnavailable as exc:
        print(f"review: {exc}", file=sys.stderr)
        return 2
    if not scope.strip():
        print("review: nothing in scope — nothing to review.", file=sys.stderr)
        return 0

    prompt = _compose(root, mode, scope)
    print(
        f"── adversarial review · harness={config.review_harness} · "
        f"model={config.review_model} · prompt={len(prompt)} bytes ──",
        file=sys.stderr,
    )
    substitute = (
        config.review_harness != PINNED_HARNESS or config.review_model != PINNED_MODEL
    )
    if substitute:
        print(
            "SUBSTITUTE REVIEW — this is not the pinned gate "
            "(codex + gpt-6.1-sol). Record it as a waiver, not a pass.",
            file=sys.stderr,
        )

    code, stdout, stderr = _invoke(config, prompt)
    if code != 0 or not stdout.strip():
        print(f"review: harness exited {code}", file=sys.stderr)
        tail = (stderr or stdout).strip().splitlines()[-20:]
        for line in tail:
            print(f"  {line}", file=sys.stderr)
        return 2

    report = stdout
    out_dir = root / ".review"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "last.md").write_text(report, encoding="utf-8")
    print(report)

    # Verdict must be on the first non-empty line, allowing a leading code fence.
    # Stray text must not decide a gate.
    first = ""
    for line in report.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("```"):
            continue
        first = stripped
        break
    match = VERDICT_RE.fullmatch(first)
    if match is None:
        print(
            "review: no parseable VERDICT on the first line — treat as untrustworthy.",
            file=sys.stderr,
        )
        return 2

    verdict = match.group(1).upper()
    if verdict == "BLOCK":
        print("GATE: BLOCK — do not commit.", file=sys.stderr)
        return 1

    if substitute:
        # A distinct non-zero code: automation must never read a substitute
        # PASS/WARN as the pinned gate having passed.
        print(
            f"SUBSTITUTE: {verdict} — the gate is NOT satisfied. Record this run as "
            "a waiver and re-run the pinned reviewer when it is available.",
            file=sys.stderr,
        )
        return 3

    if verdict == "WARN":
        print(
            "GATE: WARN — commit allowed; record waivers in the commit message.",
            file=sys.stderr,
        )
        return 0
    print("GATE: PASS.", file=sys.stderr)
    return 0
