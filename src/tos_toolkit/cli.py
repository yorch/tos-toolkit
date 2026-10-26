"""``tos`` command line interface.

Subcommands
-----------
``lint``          static analysis over .thinkscript files
``status``        validation debt: which scripts are still drafts
``syntax-check``  real-grammar check via a local thinkorswim install
``new``           scaffold a file from a template
``init``          scaffold a project (tos.toml, dirs, templates, docs)
``docs``          the bundled ThinkScript knowledge base
``explain``       look up one function or constant in the registry
``review``        adversarial review of a diff, files, or the whole repo
``mcp``           serve the toolkit to coding assistants over the Model Context Protocol
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .checks import Context, run_all
from .config import CONFIG_NAME, ConfigError, load
from .diagnostics import ERROR, WARNING, Finding, Level, Report
from .registry import load as load_registry

THINKSSCRIPT_SUFFIX = ".thinkscript"
STRAY_SUFFIX = ".ts"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tos",
        description="Static analysis and scaffolding for ThinkScript.",
    )
    parser.add_argument("--version", action="version", version=f"tos {__version__}")
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help=f"path to {CONFIG_NAME} (default: search upwards from cwd)",
    )
    parser.add_argument(
        "--profile",
        default=None,
        help="override the profile (strict | loose)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    lint = subparsers.add_parser("lint", help="analyse .thinkscript files")
    lint.add_argument("paths", nargs="*", help="files or directories (default: configured)")
    lint.add_argument("--strict", action="store_true", help="treat warnings as errors")
    lint.add_argument("--json", action="store_true", help="machine-readable output")
    lint.add_argument("--quiet", action="store_true", help="print findings only")
    lint.add_argument(
        "--allow-empty",
        action="store_true",
        help=(
            "succeed when no files were checked. Off by default: a gate that "
            "silently checks nothing is indistinguishable from a passing one."
        ),
    )

    status = subparsers.add_parser("status", help="report validation debt (@status)")
    status.add_argument("paths", nargs="*")

    syntax = subparsers.add_parser(
        "syntax-check", help="grammar check using a local thinkorswim install"
    )
    syntax.add_argument("paths", nargs="*")
    syntax.add_argument("--keep-going", action="store_true", help="report all files, don't stop")
    syntax.add_argument(
        "--allow-empty",
        action="store_true",
        help="succeed when no files were checked (default: exit 2)",
    )

    new = subparsers.add_parser("new", help="scaffold a file from a template")
    new.add_argument("kind_or_path", help="kind (study/scan/strategy/column) or path")
    new.add_argument("path", nargs="?", help="path within the kind directory")
    new.add_argument("--name", default=None, help="display name for @name")

    init = subparsers.add_parser("init", help="scaffold a project")
    init.add_argument("--force", action="store_true", help="overwrite existing files")
    init.add_argument(
        "--profile",
        dest="init_profile",
        default=None,
        help="profile to put in tos.toml (default: strict)",
    )

    docs = subparsers.add_parser("docs", help="ThinkScript knowledge base")
    docs.add_argument("topic", nargs="?", help="topic file stem, e.g. gotchas")
    docs.add_argument("--list", action="store_true", help="list topics")
    docs.add_argument("--grep", default=None, help="search the knowledge base")

    explain = subparsers.add_parser("explain", help="look up a function or constant")
    explain.add_argument("name")

    # No transport flag: stdio is the only transport, and a flag that changes
    # nothing implies a choice that does not exist.
    subparsers.add_parser(
        "mcp", help="serve tools to coding assistants over MCP (stdio)"
    )

    review = subparsers.add_parser("review", help="adversarial review")
    review.add_argument("--mode", choices=["diff", "audit", "files"], default="diff")
    review.add_argument("--harness", default=None, help="override review.harness")
    review.add_argument("--model", default=None, help="override review.model")
    review.add_argument("paths", nargs="*")

    return parser


# --------------------------------------------------------------------------
# file discovery


def _walk(
    targets: list[str], root: Path, *, strict_paths: bool = False
) -> tuple[list[Path], list[Path]]:
    """Return (thinkscript files, stray .ts files).

    With *strict_paths*, an explicit path that does not exist raises, so a typo
    in a pre-commit hook cannot silently check zero files.
    """
    files: list[Path] = []
    stray: list[Path] = []
    for target in targets:
        path = Path(target)
        if not path.is_absolute():
            candidate = (root / target).resolve()
            if candidate.exists():
                path = candidate
        if path.is_file():
            if path.name.endswith(STRAY_SUFFIX):
                stray.append(path)
            else:
                files.append(path)
            continue
        if not path.is_dir():
            if strict_paths:
                raise SystemExit(2)
            continue
        for item in sorted(path.rglob("*")):
            if not item.is_file():
                continue
            if item.name.endswith(STRAY_SUFFIX):
                stray.append(item)
            elif item.name.endswith(THINKSSCRIPT_SUFFIX):
                files.append(item)
    return files, stray


# --------------------------------------------------------------------------
# commands


def _cmd_lint(args, config) -> int:
    registry = load_registry()
    targets = args.paths or [
        str(config.root / target)
        for target in config.targets
        if (config.root / target).exists()
    ]
    if not targets:
        message = (
            "No target directories found. Run `tos init` or pass paths explicitly."
        )
        print(message, file=sys.stderr)
        ok = bool(args.allow_empty)
        if args.json:
            # Consumers parse this; empty stdout is invalid JSON, and a gate that
            # receives no JSON cannot tell "clean" from "nothing ran".
            print(
                json.dumps(
                    {
                        "ok": ok,
                        "targets_found": False,
                        "error_count": 0,
                        "warning_count": 0,
                        "files_checked": 0,
                        "findings": [],
                        "summary": message,
                    },
                    indent=2,
                )
            )
        return 0 if ok else 2

    try:
        files, stray = _walk(targets, config.root, strict_paths=bool(args.paths))
    except SystemExit:
        message = f"path not found: {' '.join(args.paths)}"
        print(f"error: {message}", file=sys.stderr)
        if args.json:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "targets_found": False,
                        "error_count": 0,
                        "warning_count": 0,
                        "files_checked": 0,
                        "findings": [],
                        "summary": message,
                    },
                    indent=2,
                )
            )
        return 2
    report = Report()

    for path in stray:
        try:
            rel = path.resolve().relative_to(config.root.resolve())
        except ValueError:
            rel = path
        level = config.level("E005")
        if level is Level.OFF:
            continue
        report.add(
            Finding(
                str(rel),
                0,
                "E005",
                f"'{path.name}' collides with TypeScript; rename to .thinkscript",
                ERROR if level is Level.ERROR else WARNING,
            )
        )

    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            level = config.level("E006")
            if level is not Level.OFF:
                report.add(
                    Finding(
                        str(path.relative_to(config.root) if path.is_relative_to(config.root) else path),
                        0,
                        "E006",
                        "not valid UTF-8",
                        ERROR if level is Level.ERROR else WARNING,
                    )
                )
            continue
        ctx = Context(path=path, root=config.root, text=text, config=config, registry=registry)
        report.files_checked += 1
        report.extend(run_all(ctx))

    # Empty means nothing was checked *and* nothing was reported: with E005
    # disabled, a tree of ignored .ts files would otherwise look like a clean run.
    empty = report.files_checked == 0 and not report.findings
    if empty and not args.allow_empty:
        message = (
            "no .thinkscript files were checked; refusing to report success "
            "(pass --allow-empty if that is expected)"
        )
        print(message, file=sys.stderr)

    if args.json:
        payload = [
            {
                "path": f.path,
                "line": f.line,
                "code": f.code,
                "severity": f.severity,
                "message": f.message,
                "hint": f.hint,
            }
            for f in report.sorted_findings()
        ]
        print(
            json.dumps(
                {
                    "ok": (not empty or bool(args.allow_empty))
                    and not report.errors
                    and not (args.strict and report.warnings),
                    "targets_found": True,
                    "error_count": len(report.errors),
                    "warning_count": len(report.warnings),
                    "files_checked": report.files_checked,
                    "findings": payload,
                    "summary": report.summary(),
                },
                indent=2,
            )
        )
    else:
        for finding in report.sorted_findings():
            print(finding.render())
        if not args.quiet or report.findings:
            print()
            print(report.summary())

    if report.errors:
        return 1
    if args.strict and report.warnings:
        return 1
    if empty and not args.allow_empty:
        return 2
    return 0


def _cmd_status(args, config) -> int:
    registry = load_registry()
    targets = args.paths or [
        str(config.root / target)
        for target in config.targets
        if (config.root / target).exists() and target != config.templates_dir
    ]
    files, _ = _walk(targets, config.root)

    rows = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        ctx = Context(path=path, root=config.root, text=text, config=config, registry=registry)
        rows.append(
            (
                ctx.rel_posix,
                ctx.header.get("kind", "?"),
                ctx.header.get("status", "?"),
                ctx.header.get("version", "?"),
            )
        )

    if not rows:
        print("No .thinkscript files yet. Scaffold one with `tos new <kind> <path>`.")
        return 0

    rows.sort(key=lambda r: (r[2], r[0]))
    print(f"{'STATUS':<12} {'KIND':<9} {'VER':<8} PATH")
    for rel, kind, status, version in rows:
        print(f"{status:<12} {kind:<9} {version:<8} {rel}")

    known = config.statuses
    counts: dict[str, int] = {}
    for _, _, status, _ in rows:
        key = status if status in known else "unknown"
        counts[key] = counts.get(key, 0) + 1
    print("\nSummary")
    for status in ["draft", "validated", "in-use", "deprecated", "unknown"]:
        if counts.get(status):
            print(f"  {status:<12} {counts[status]}")
    debt = counts.get("draft", 0) + counts.get("unknown", 0)
    if debt:
        print(
            f"\nValidation debt: {debt} script(s) not validated "
            "(draft or missing/unknown @status)."
        )
    return 0


def _cmd_syntax(args, config) -> int:
    from .parser import bridge

    targets = args.paths or [
        str(config.root / target)
        for target in config.targets
        if (config.root / target).exists()
    ]
    try:
        files, _ = _walk(targets, config.root, strict_paths=bool(args.paths))
    except SystemExit:
        print(f"error: path not found: {' '.join(args.paths)}", file=sys.stderr)
        return 2
    if not files:
        print("No .thinkscript files found.", file=sys.stderr)
        # Same rule as lint: a checker that verified nothing must not report
        # success, because "0 grammar errors" then means nothing at all.
        return 0 if args.allow_empty else 2

    if not config.parser_enabled:
        print(
            "Grammar check disabled in config ([parser] enabled = false).",
            file=sys.stderr,
        )
        return 2

    try:
        runtimes = bridge.prepare(config.tos_path)
    except bridge.ParserUnavailable as exc:
        print(f"Grammar check unavailable: {exc}", file=sys.stderr)
        print(
            "This check requires a local thinkorswim install and a JDK.\n"
            "Everything else (tos lint, tos review) works without it.",
            file=sys.stderr,
        )
        return 2

    failures = 0
    errors = 0
    processed = 0
    for path in files:
        processed += 1
        status, messages = bridge.check_file(path, runtimes)
        if status == bridge.OK:
            print(f"  OK (grammar only): {path}")
        elif status == bridge.ERROR:
            errors += 1
            print(f"  ERROR (parser did not run): {path}")
            for message in messages:
                print(f"    {message}")
            break
        else:
            failures += 1
            print(f"  FAIL: {path}")
            for message in messages:
                print(f"    {message}")
            if not args.keep_going:
                break

    skipped = len(files) - processed
    note = f" ({skipped} not checked; use --keep-going)" if skipped else ""
    print(f"\n{processed} file(s) checked, {failures} with grammar errors{note}.")
    print("NOTE: grammar only — function names, types, and semantics are not verified.")
    if errors:
        print(
            "The parser could not run, so nothing was verified. Fix the bridge "
            "before trusting any result.",
            file=sys.stderr,
        )
        return 2
    return 1 if failures else 0


def _cmd_docs(args, config) -> int:
    from . import knowledge

    if args.list or (not args.topic and not args.grep):
        for slug, title in knowledge.topics():
            print(f"  {slug:<24} {title}")
        print("\nUse `tos docs <topic>` to print one, or --grep to search.")
        return 0

    if args.grep:
        hits = knowledge.search(args.grep)
        if not hits:
            print(f"No matches for '{args.grep}'.")
            return 1
        for slug, line_no, line in hits:
            print(f"{slug}:{line_no}: {line}")
        return 0

    text = knowledge.read(args.topic)
    if text is None:
        print(f"Unknown topic '{args.topic}'. Use --list.", file=sys.stderr)
        return 2
    print(text)
    return 0


def _cmd_explain(args, config) -> int:
    registry = load_registry()
    info = registry.function(args.name)
    if info is None:
        # try as a constant namespace member
        if "." in args.name:
            namespace, member = args.name.split(".", 1)
            if registry.has_namespace(namespace):
                if member.lower() in registry.namespace_members(namespace):
                    print(f"{args.name}: valid {namespace} member")
                    return 0
                print(f"{args.name}: NOT a known {namespace} member")
                print(f"  known: {', '.join(sorted(registry.namespace_members(namespace)))}")
                return 1
        print(f"'{args.name}' is not in the registry.")
        print("That does not mean it is invalid — the registry is curated, not exhaustive.")
        print("Verify in the platform before shipping.")
        return 1

    print(f"{info.name}  [{info.category}]  confidence={info.confidence}")
    if info.notes:
        print(f"  {info.notes}")
    if info.is_unverified:
        print("  WARNING: unverified. Paste-test before relying on it.")
    return 0


def _cmd_new(args, config) -> int:
    from . import scaffold

    return scaffold.new_file(config, args.kind_or_path, args.path, args.name)


def _cmd_init(args, config) -> int:
    from . import scaffold

    profile = args.init_profile or args.profile or "strict"
    return scaffold.init_project(Path.cwd(), profile=profile, force=args.force)


def _cmd_mcp(args, config) -> int:
    from . import mcp

    # Nothing but JSON-RPC may reach stdout, or the transport is corrupted.
    print(
        f"tos mcp: serving {len(mcp.TOOLS)} tool(s) over stdio "
        f"(server {mcp.SERVER_NAME} {__version__})",
        file=sys.stderr,
    )
    return mcp.serve(config)


def _cmd_review(args, config) -> int:
    from . import review

    if args.harness:
        config.review_harness = args.harness
    if args.model:
        config.review_model = args.model
    return review.run(config, mode=args.mode, paths=args.paths)


COMMANDS = {
    "lint": _cmd_lint,
    "status": _cmd_status,
    "syntax-check": _cmd_syntax,
    "docs": _cmd_docs,
    "explain": _cmd_explain,
    "new": _cmd_new,
    "init": _cmd_init,
    "review": _cmd_review,
    "mcp": _cmd_mcp,
}


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        config = load(config_path=args.config, profile=args.profile)
    except ConfigError as exc:
        print(f"tos: {exc}", file=sys.stderr)
        return 2

    handler = COMMANDS.get(args.command)
    if handler is None:  # pragma: no cover - argparse guards this
        parser.error(f"unknown command {args.command}")
        return 2
    return handler(args, config)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
