"""Optional grammar validation via a locally installed thinkorswim parser.

This module does **not** ship, copy, or decode any Schwab code. It locates the
user's own thinkorswim installation, compiles a tiny reflection shim against it,
and asks that parser whether a file is grammatically valid.

If thinkorswim is absent, `tos syntax-check` reports the check as unavailable and
exits 2. Every other command keeps working.

See ``docs/adr/0004-no-jar-redistribution.md``.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

JAVA_SOURCE = Path(__file__).resolve().parent / "java" / "Checker.java"

# Globs for the jars the shim needs. Matched against the newest versioned dir.
_REQUIRED = [
    "thinkscript-*.jar",
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


def _build_classpath(tos_path: str) -> list[str]:
    root = Path(tos_path)
    usergui = root / "usergui"
    if not usergui.is_dir():
        raise ParserUnavailable(f"no usergui directory under {root}")

    version_dir = None
    for candidate in sorted(usergui.iterdir(), reverse=True):
        if candidate.is_dir() and list(candidate.glob("thinkscript-parser-*.jar")):
            version_dir = candidate
            break
    if version_dir is None:
        raise ParserUnavailable(f"no thinkscript-parser jar under {usergui}")

    jars: list[str] = []
    for pattern in _REQUIRED:
        matches = sorted(version_dir.glob(pattern))
        if matches:
            jars.append(str(matches[-1]))
    if not jars:
        raise ParserUnavailable("no thinkscript jars found")

    suit = root / "suit"
    if suit.is_dir():
        for candidate in sorted(suit.iterdir(), reverse=True):
            if (candidate / "dxlib-3.351.jar").is_file():
                jars.extend(str(jar) for jar in sorted(candidate.glob("*.jar")))
                break
    return jars


def prepare(tos_path: str) -> Runtimes:
    """Locate Java and the ToS jars, compiling the reflection shim if needed."""
    java = _find_java()
    jars = _build_classpath(tos_path)

    build_dir = Path(__file__).resolve().parent / "java" / ".classes"
    build_dir.mkdir(parents=True, exist_ok=True)
    shim = build_dir / "Checker.class"

    if not shim.is_file() or shim.stat().st_mtime < JAVA_SOURCE.stat().st_mtime:
        javac = _find_javac(java)
        result = subprocess.run(
            [str(javac), "-cp", ":".join(jars), "-d", str(build_dir), str(JAVA_SOURCE)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise ParserUnavailable(f"failed to build parser shim:\n{result.stderr.strip()}")

    classpath = ":".join([str(build_dir), *jars])
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
    if "RESULT: OK" in output:
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
