"""Optional grammar validation via a locally installed thinkorswim parser.

This module does **not** ship, copy, or decode any Schwab code. It locates the
user's own thinkorswim installation, compiles a tiny reflection shim against it,
and asks that parser whether a file is grammatically valid.

If thinkorswim is absent, `tos syntax-check` reports the check as unavailable and
exits 2. Every other command keeps working.

See ``docs/adr/0004-no-jar-redistribution.md``.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

JAVA_SOURCE = Path(__file__).resolve().parent / "java" / "Checker.java"

# Globs for the jars the shim needs. Matched against the newest versioned dir.
_REQUIRED = [
    "thinkscript-[0-9]*.jar",
    "thinkscript-scripts-*.jar",
    "thinkscript-parser-*.jar",
    "thinkscript-api-*.jar",
    "thinkscript-facade-*.jar",
    "thinkscript-qd-*.jar",
    "toscommon-core-*.jar",
    "dxlib-*.jar",
]


class ParserUnavailable(Exception):
    """Raised when the ToS parser cannot be reached."""


@dataclass(frozen=True)
class Runtimes:
    java: str
    classpath: str


def _runs(binary: str | Path) -> bool:
    """A binary is only usable if it actually executes on this machine.

    macOS ships multi-arch stubs that resolve to the wrong architecture, so a
    path existing is not enough — probe it.
    """
    try:
        result = subprocess.run(
            [str(binary), "-version"], capture_output=True, timeout=30
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def _first_working(candidates: list[str | None]) -> str | None:
    seen: set[str] = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        if Path(candidate).is_file() and _runs(candidate):
            return candidate
    return None


_JAVA_CANDIDATES = (
    "/opt/homebrew/opt/openjdk/bin/java",
    "/opt/homebrew/opt/openjdk@21/bin/java",
    "/usr/local/opt/openjdk/bin/java",
    "java",
)


def _find_java() -> str:
    candidates: list[str | None] = []
    for name in _JAVA_CANDIDATES:
        candidates.append(shutil.which(name) if "/" not in name else name)
    found = _first_working(candidates)
    if found:
        return found
    raise ParserUnavailable(
        "no working JDK found (install one, e.g. `brew install openjdk`)"
    )


def _find_javac(java: str) -> Path:
    candidates: list[str | None] = [str(Path(java).parent / "javac")]
    for name in (
        "/opt/homebrew/opt/openjdk/bin/javac",
        "/opt/homebrew/opt/openjdk@21/bin/javac",
        "/usr/local/opt/openjdk/bin/javac",
        "javac",
    ):
        candidates.append(shutil.which(name) if "/" not in name else name)
    found = _first_working(candidates)
    if found is None:
        raise ParserUnavailable("no working javac found (a JDK is required, not a JRE)")
    return Path(found)


def _version_key(path: Path) -> tuple:
    """Sort '1993.2.4' numerically, so 1994.0.56 beats 1993.3.1."""
    parts = re.split(r"[.\-_]", path.name)
    return tuple(int(p) if p.isdigit() else 0 for p in parts)


def _build_classpath(tos_path: str) -> tuple[list[str], str]:
    root = Path(tos_path)
    usergui = root / "usergui"
    if not usergui.is_dir():
        raise ParserUnavailable(f"no usergui directory under {root}")

    version_dir = None
    candidates = [c for c in usergui.iterdir() if c.is_dir()]
    for candidate in sorted(candidates, key=_version_key, reverse=True):
        if list(candidate.glob("thinkscript-parser-*.jar")):
            version_dir = candidate
            break
    if version_dir is None:
        raise ParserUnavailable(f"no thinkscript-parser jar under {usergui}")

    jars: list[str] = []
    for pattern in _REQUIRED:
        matches = list(version_dir.glob(pattern))
        if matches:
            jars.append(str(max(matches, key=_version_key)))
    if not jars:
        raise ParserUnavailable("no thinkscript jars found")

    suit = root / "suit"
    if suit.is_dir():
        suit_versions = [c for c in suit.iterdir() if c.is_dir()]
        for candidate in sorted(suit_versions, key=_version_key, reverse=True):
            if list(candidate.glob("dxlib-*.jar")):
                jars.extend(str(jar) for jar in sorted(candidate.glob("*.jar")))
                break
    return jars, version_dir.name


def prepare(tos_path: str) -> Runtimes:
    """Locate Java and the ToS jars, compiling the reflection shim if needed."""
    java = _find_java()
    jars, tos_version = _build_classpath(tos_path)

    build_root = Path(__file__).resolve().parent / "java"
    build_dir = build_root / ".classes"
    try:
        build_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        # Read-only package install (e.g. a system site-packages): fall back to
        # the user's cache directory.
        build_dir = Path(tempfile.gettempdir()) / "tos-toolkit-shim"
        build_dir.mkdir(parents=True, exist_ok=True)

    shim = build_dir / "Checker.class"
    stamp = build_dir / "stamp"
    signature = f"{tos_version}|{JAVA_SOURCE.stat().st_mtime_ns}"
    current = stamp.read_text(encoding="utf-8") if stamp.is_file() else ""

    if (
        not shim.is_file()
        or shim.stat().st_mtime < JAVA_SOURCE.stat().st_mtime
        or current != signature
    ):
        javac = _find_javac(java)
        result = subprocess.run(
            [str(javac), "-cp", os.pathsep.join(jars), "-d", str(build_dir), str(JAVA_SOURCE)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise ParserUnavailable(
                f"failed to build parser shim:\n{result.stderr.strip()}"
            )
        stamp.write_text(signature, encoding="utf-8")

    classpath = os.pathsep.join([str(build_dir), *jars])
    return Runtimes(java=java, classpath=classpath)


def check_file(path: Path, runtimes: Runtimes) -> tuple[bool, list[str]]:
    """Ask the real parser about one file. Returns (ok, messages)."""
    # The shim reads a path; keep the original name so error messages are useful.
    with tempfile.TemporaryDirectory(prefix="tos-syntax-") as tmp:
        staged = Path(tmp) / path.name
        shutil.copy2(path, staged)
        result = subprocess.run(
            [runtimes.java, "-cp", runtimes.classpath, "Checker", str(staged)],
            capture_output=True,
            text=True,
            timeout=120,
        )

    output = f"{result.stdout}\n{result.stderr}"

    # Require a clean exit and an exact first-line match. A substring search
    # would let a source string literal such as "RESULT: OK" produce a false pass.
    first_line = next((line.strip() for line in output.splitlines() if line.strip()), "")
    if result.returncode == 0 and first_line == "RESULT: OK":
        return True, []

    messages: list[str] = []
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("RESULT:"):
            continue
        if "Exception" in stripped or "Invalid statement" in stripped:
            messages.append(stripped)
    if not messages:
        messages.append(f"unexpected parser output (exit {result.returncode}): {output[:300]}")
    return False, messages
