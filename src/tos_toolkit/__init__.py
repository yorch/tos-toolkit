"""tos-toolkit: static analysis and scaffolding for ThinkScript.

Layered by design:

* language-generic rules are always on
* house conventions (header block, directory layout, @status) come from a profile
* grammar validation is an optional extra that requires a local thinkorswim install

Nothing in this package bundles or redistributes thinkorswim code.
"""

def _resolve_version() -> str:
    """Read the version from installed metadata.

    A hand-maintained string drifts: 0.2.0 shipped with `__version__` still saying
    0.1.0 because the bump happened in pyproject.toml only. The package metadata is
    the one place a version is authoritative for an installed distribution.
    """
    try:
        from importlib.metadata import PackageNotFoundError, version
    except ImportError:  # pragma: no cover - Python < 3.8
        return "0.0.0+unknown"
    try:
        return version("tos-toolkit")
    except PackageNotFoundError:
        # A source checkout that was never installed.
        return "0.0.0+source"


__version__ = _resolve_version()

__all__ = ["__version__"]
