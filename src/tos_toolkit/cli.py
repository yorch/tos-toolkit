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
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .checks import Context, run_all
from .config import CONFIG_NAME, ConfigError, load
from .diagnostics import ERROR, Finding, Report
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

    status = subparsers.add_parser("status", help="report validation debt (@status)")
    status.add_argument("paths", nargs="*")

    syntax = subparsers.add_parser(
        "syntax-check", help="grammar check using a local thinkorswim install"
    )
    syntax.add_argument("paths", nargs="*")
    syntax.add_argument("--keep-going", action="store_true", help="report all files, don't stop")

    new = subparsers.add_parser("new", help="scaffold a file from a template")
    new.add_argument("kind_or_path", help="kind (study/scan/strategy/column) or path")
    new.add_argument("path", nargs="?", help="path within the kind directory")
    new.add_argument("--name", default=None, help="display name for @name")

    init = subparsers.add_parser("init", help="scaffold a project")
    init.add_argument("--force", action="store_true", help="overwrite existing files")
    init.add_argument("--profile", default="strict", help="profile to put in tos.toml")

    docs = subparsers.add_parser("docs", help="ThinkScript knowledge base")
    docs.add_argument("topic", nargs="?", help="topic file stem, e.g. gotchas")
    docs.add_argument("--list", action="store_true", help="list topics")
    docs.add_argument("--grep", default=None, help="search the knowledge base")

    explain = subparsers.add_parser("explain", help="look up a function or constant")
    explain.add_argument("name")
    explain.add_argument("--category", default=None, help="filter by category")

    review = subparsers.add_parser("review", help="adversarial review")
    review.add_argument("--mode", choices=["diff", "audit", "files"], default="diff")
    review.add_argument("paths", nargs="*")

    return parser


# --------------------------------------------------------------------------
# file discovery


def _walk(targets: list[str], root: Path) -> tuple[list[Path], list[Path]]:
    """Return (thinkscript files, stray .ts files)."""
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
        print(
            "No target directories found. Run `tos init` or pass paths explicitly.",
            file=sys.stderr,
        )
        return 0

    files, stray = _walk(targets, config.root)
    report = Report()

    for path in stray:
        try:
            rel = path.resolve().relative_to(config.root.resolve())
        except ValueError:
            rel = path
        report.add(
            Finding(
                str(rel),
                0,
                "E005",
                f"'{path.name}' collides with TypeScript; rename to .thinkscript",
                ERROR,
            )
        )

    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            report.add(
                Finding(
                    str(path.relative_to(config.root) if path.is_relative_to(config.root) else path),
                    0,
                    "E006",
                    "not valid UTF-8",
                    ERROR,
                )
            )
            continue
        ctx = Context(path=path, root=config.root, text=text, config=config, registry=registry)
        report.files_checked += 1
        report.extend(run_all(ctx))

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
        print(json.dumps({"findings": payload, "summary": report.summary()}, indent=2))
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

    counts: dict[str, int] = {}
    for _, _, status, _ in rows:
        counts[status] = counts.get(status, 0) + 1
    print("\nSummary")
    for status in ["draft", "validated", "in-use", "deprecated"]:
        if counts.get(status):
            print(f"  {status:<12} {counts[status]}")
    debt = counts.get("draft", 0)
    if debt:
        print(
            f"\nValidation debt: {debt} draft script(s) awaiting a human paste-test."
        )
    return 0


def _cmd_syntax(args, config) -> int:
    from .parser import bridge

    targets = args.paths or [
        str(config.root / target)
        for target in config.targets
        if (config.root / target).exists()
    ]
    files, _ = _walk(targets, config.root)
    if not files:
        print("No .thinkscript files found.")
        return 0

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
    for path in files:
        ok, messages = bridge.check_file(path, runtimes)
        if ok:
            print(f"  OK (grammar only): {path}")
        else:
            failures += 1
            print(f"  FAIL: {path}")
            for message in messages:
                print(f"    {message}")
            if not args.keep_going:
                break

    print(f"\n{len(files)} file(s) checked, {failures} with grammar errors.")
    print("NOTE: grammar only — function names, types, and semantics are not verified.")
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

    return scaffold.init_project(Path.cwd(), profile=args.profile, force=args.force)


def _cmd_review(args, config) -> int:
    from . import review

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
