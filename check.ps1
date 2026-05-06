# Script de verificación: linter + type checker + tests con cobertura.
# Uso: .\check.ps1
$ErrorActionPreference = "Stop"

Write-Host "==> Activando venv..." -ForegroundColor Cyan
. .\.venv\Scripts\Activate.ps1

Write-Host "`n==> Ruff (lint)..." -ForegroundColor Cyan
ruff check .

Write-Host "`n==> Mypy (type check)..." -ForegroundColor Cyan
mypy backend

Write-Host "`n==> Pytest (unit tests + coverage)..." -ForegroundColor Cyan
pytest tests/unit -v --cov=backend --cov-report=term-missing --cov-fail-under=80

Write-Host "`nOK: todas las verificaciones pasaron." -ForegroundColor Green
