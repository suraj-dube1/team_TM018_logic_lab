$ErrorActionPreference = "Stop"
Write-Host "Logic Labs — Windows setup" -ForegroundColor Cyan
Write-Host "Current folder: $PWD"

if (-not (Test-Path ".\backend")) { throw "Run this script from the Logic Labs project root (the folder containing backend)." }
Set-Location ".\backend"

if (-not (Test-Path ".\venv")) {
  python -m venv venv
}
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt

if (-not (Test-Path ".\.env")) {
  Copy-Item "..\.env.local.example" ".\.env"
  Write-Host "Created backend\.env from .env.local.example" -ForegroundColor Yellow
  Write-Host "Paste your Neon connection string into ADMIN_DB_URL, then rerun this script." -ForegroundColor Yellow
  exit 0
}

if ((Get-Content .env -Raw) -notmatch '(?m)^SECRET_KEY=.{20,}$') {
  python generate_secret.py
}

Write-Host "Next step: python setup_db.py" -ForegroundColor Green
Write-Host "Then seed: python -m app.seed" -ForegroundColor Green
Write-Host "Then run: uvicorn app.main:app --host 127.0.0.1 --port 8000" -ForegroundColor Green
