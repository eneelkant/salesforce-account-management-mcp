$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Python = if ($env:PYTHON_BIN) { $env:PYTHON_BIN } else { "python" }

Write-Host "==> Creating virtualenv (.venv)"
& $Python -m venv .venv
& .\.venv\Scripts\Activate.ps1

Write-Host "==> Upgrading pip"
python -m pip install --upgrade pip

Write-Host "==> Installing package with dev extras"
pip install -e ".[dev]"

if (-not (Test-Path .env)) {
  Copy-Item .env.example .env
  Write-Host "==> Created .env from .env.example — fill in Salesforce credentials"
} else {
  Write-Host "==> .env already exists"
}

Write-Host "==> Offline health check"
python scripts/health_check.py --offline

Write-Host "==> Done. Activate with: .\.venv\Scripts\Activate.ps1"
Write-Host "    Run MCP (stdio): salesforce-account-engagement-mcp"
Write-Host "    Run tests: pytest"
