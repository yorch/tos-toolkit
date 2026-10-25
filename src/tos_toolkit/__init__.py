"""tos-toolkit: static analysis and scaffolding for ThinkScript.

Layered by design:

* language-generic rules are always on
* house conventions (header block, directory layout, @status) come from a profile
* grammar validation is an optional extra that requires a local thinkorswim install

Nothing in this package bundles or redistributes thinkorswim code.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
