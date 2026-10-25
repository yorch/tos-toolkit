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
VERDICT_RE = re.compile(r"VERDICT:\s*(BLOCK|WARN|PASS)", re.IGNORECASE)
MAX_INLINE_BYTES = 400_000


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, timeout=60
    )
    return result.stdout if result.returncode == 0 else ""


def _inlined_files(root: Path, files: list[Path]) -> str:
    chunks: list[str] = []
    total = 0
    for path in files:
        try:
            body = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            chunks.append(f"--- {path.name} (unreadable) ---\n")
            continue
        if total + len(body) > MAX_INLINE_BYTES:
            chunks.append(f"--- {path.name} (skipped, size budget) ---\n")
            continue
        total += len(body)
        chunks.append(f"--- {path} ---\n{body}\n")
    return "\n".join(chunks)


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
            return ""
        selected = []
        for raw in paths:
            candidate = Path(raw)
            if not candidate.is_absolute():
                candidate = root / raw
            selected.append(candidate)
        return "### files under review\n\n" + _inlined_files(root, selected)

    status = _git(root, "status", "--porcelain")
    if not status.strip():
        return ""

    parts = ["### git status\n", status]
    if _git(root, "rev-parse", "--verify", "HEAD").strip():
        parts += ["\n### git diff (unstaged)\n", _git(root, "diff")]
    parts += ["\n### git diff (staged)\n", _git(root, "diff", "--cached")]

    untracked_out = _git(root, "ls-files", "--others", "--exclude-standard")
    untracked = [
        root / name for name in untracked_out.splitlines() if name.strip()
    ]
    parts += ["\n### untracked file contents\n", _inlined_files(root, untracked)]
    return "".join(parts)


def _compose(root: Path, mode: str, scope: str) -> str:
    prompt = PROMPT_FILE.read_text(encoding="utf-8")
    return (
        f"{prompt}\n\n---\n\n## Scope\n\n"
        f"Mode: `{mode}`  ·  repository root: `{root}`\n\n{scope}\n"
    )


def _invoke(config, prompt: str) -> tuple[int, str, str]:
    """Return (exit code, stdout, stderr) from the configured harness."""
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


def run(config, mode: str = "diff", paths: list[str] | None = None) -> int:
    root = config.root
    scope = _scope(root, mode, paths or [])
    if not scope.strip():
        print("review: nothing in scope — nothing to review.", file=sys.stderr)
        return 0

    prompt = _compose(root, mode, scope)
    print(
        f"── adversarial review · harness={config.review_harness} · "
        f"model={config.review_model} · prompt={len(prompt)} bytes ──",
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

    # Verdict must be on the first non-empty line: stray text must not decide a gate.
    first = next((line for line in report.splitlines() if line.strip()), "")
    match = VERDICT_RE.search(first)
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
    if verdict == "WARN":
        print("GATE: WARN — commit allowed; record waivers in the commit message.", file=sys.stderr)
        return 0
    print("GATE: PASS.", file=sys.stderr)
    return 0
