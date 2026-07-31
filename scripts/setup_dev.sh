#!/usr/bin/env bash
# Set up the local development environment for TianshangCAD.
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON=${PYTHON:-python3}

echo "==> Creating virtual environment (.venv)"
"$PYTHON" -m venv .venv

# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> Installing package with dev extras"
pip install --upgrade pip
pip install -e ".[dev]"

echo "==> Installing typing stubs for linting"
pip install types-PyYAML

echo "==> Done. Activate with: source .venv/bin/activate"
