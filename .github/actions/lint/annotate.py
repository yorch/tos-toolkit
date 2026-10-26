#!/usr/bin/env python3
"""Turn `tos lint --json` output into GitHub annotations, plain text, or outputs.

Three modes, because a composite action needs all three and shell heredocs inside
YAML are a good way to introduce bugs:

``annotate.py findings.json``            inline ``::error``/``::warning`` markers
``annotate.py --plain findings.json``    human-readable log lines
``annotate.py --outputs findings.json``  ``errors=…``/``warnings=…`` for $GITHUB_OUTPUT

Annotation *properties* need GitHub's own escaping, which differs from the
message escaping. Get it wrong and the marker is silently swallowed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def escape_data(value: str) -> str:
    """Escaping for the message body."""
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def escape_property(value: str) -> str:
    """Escaping for `key=value` properties: also comma and colon."""
    return escape_data(value).replace(":", "%3A").replace(",", "%2C")


def load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"annotate: {path} is not valid JSON: {exc}")


def emit_annotations(payload: dict) -> None:
    for finding in payload.get("findings", []):
        level = "error" if finding.get("severity") == "error" else "warning"
        code = finding.get("code") or ""
        body = f"{code}: {finding.get('message', '')}" if code else finding.get("message", "")
        hint = finding.get("hint")
        if hint:
            body += f" — {hint}"

        properties = [f"file={escape_property(str(finding.get('path', '')))}"]
        if finding.get("line"):
            properties.append(f"line={int(finding['line'])}")
        if code:
            properties.append(f"title={escape_property(code)}")
        print(f"::{level} {','.join(properties)}::{escape_data(body)}")

    summary = payload.get("summary")
    if summary:
        print(f"::notice title=tos-toolkit::{escape_data(summary)}")


def emit_plain(payload: dict) -> None:
    for finding in payload.get("findings", []):
        print(
            f"{finding.get('path')}:{finding.get('line')}: "
            f"[{finding.get('code')}] {finding.get('message')}"
        )
        if finding.get("hint"):
            print(f"    hint: {finding['hint']}")
    print(payload.get("summary", ""))


def counts(payload: dict) -> tuple[int, int]:
    """Prefer the reported counts, but derive them if the payload omits them.

    Reporting 0 because a field is missing is worse than recomputing: the step
    output would quietly disagree with the annotations next to it.
    """
    findings = payload.get("findings", [])
    derived_errors = sum(1 for f in findings if f.get("severity") == "error")
    derived_warnings = sum(1 for f in findings if f.get("severity") == "warning")
    errors = payload.get("error_count")
    warnings = payload.get("warning_count")
    return (
        derived_errors if errors is None else int(errors),
        derived_warnings if warnings is None else int(warnings),
    )


def emit_outputs(payload: dict) -> None:
    """Counts only: the caller knows where its own report file lives."""
    errors, warnings = counts(payload)
    print(f"errors={errors}")
    print(f"warnings={warnings}")


def main(argv: list[str]) -> int:
    mode = "annotations"
    positional = [a for a in argv[1:]]
    if positional and positional[0].startswith("--"):
        mode = positional.pop(0).lstrip("-")
    if len(positional) != 1:
        print(__doc__ or "", file=sys.stderr)
        return 2

    payload = load(Path(positional[0]))
    if mode == "plain":
        emit_plain(payload)
    elif mode == "outputs":
        emit_outputs(payload)
    elif mode == "annotations":
        emit_annotations(payload)
    else:
        print(f"annotate: unknown mode {mode!r}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
