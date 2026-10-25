set shell := ["bash", "-euo", "pipefail", "-c"]

# tos-toolkit development. Consumers use the `tos` CLI, not this justfile.

default:
    @just --list

# Install the package in editable mode with dev deps
install:
    @python3 -m pip install -e ".[dev]"

# Run the test suite
test:
    @python3 -m pytest -q

# Lint the toolkit's own Python
lint-py:
    @python3 -m compileall -q src/tos_toolkit && echo "python compiles"

# Self-check: the tool must accept its own templates and reject a known collision
selfcheck: install
    @tos --profile loose lint src/tos_toolkit/scaffold/templates
    @printf 'declare upper;\nrec pdHigh = 1;\nplot PdHigh = pdHigh;\n' > /tmp/tos-selfcheck.thinkscript
    @! tos --profile loose lint /tmp/tos-selfcheck.thinkscript
    @echo "selfcheck passed: templates clean, collision rejected"
    @rm -f /tmp/tos-selfcheck.thinkscript

# Stage the knowledge base, then serve the docs site locally
docs-serve:
    @python3 scripts/sync_kb_docs.py
    @mkdocs serve

# Stage the knowledge base, then build the site strictly (CI parity)
docs-build:
    @python3 scripts/sync_kb_docs.py
    @mkdocs build --strict

# Build the distribution and check metadata
package:
    @python3 -m build
    @python3 -m twine check dist/*

# Remove build artefacts
clean:
    @rm -rf build dist *.egg-info .pytest_cache .ruff_cache
    @find . -name __pycache__ -type d -prune -exec rm -rf {} +
