#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "==> Creating virtualenv (.venv)"
"$PYTHON_BIN" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> Upgrading pip"
python -m pip install --upgrade pip

echo "==> Installing package with dev extras"
pip install -e ".[dev]"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "==> Created .env from .env.example — fill in Salesforce credentials"
else
  echo "==> .env already exists"
fi

echo "==> Offline health check"
python scripts/health_check.py --offline

echo "==> Done. Activate with: source .venv/bin/activate"
echo "    Run MCP (stdio): salesforce-account-engagement-mcp"
echo "    Run tests: pytest"
