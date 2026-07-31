#!/usr/bin/env bash
# Run lint, type check and the full test suite with the coverage gate.
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON=${PYTHON:-python3}

echo "==> ruff"
ruff check .

echo "==> mypy"
mypy src

echo "==> pytest (coverage gate >= 80%)"
pytest --cov=cad_mcp_server --cov-report=term-missing --cov-fail-under=80
