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

# Self-check: run tos against its own fixture corpus
selfcheck: install
    @tos lint tests/fixtures/good --profile loose
    @tos lint tests/fixtures/bad --profile loose || true

# Remove build artefacts
clean:
    @rm -rf build dist *.egg-info .pytest_cache .ruff_cache
    @find . -name __pycache__ -type d -prune -exec rm -rf {} +
