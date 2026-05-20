param(
  [string]$Venv = ".venv"
)
$ErrorActionPreference = "Stop"
try {
  Write-Host "[1/5] Python version"
  python --version
  Write-Host "[2/5] Creating virtual environment: $Venv"
  python -m venv $Venv
  Write-Host "[3/5] Activate with: .\$Venv\Scripts\Activate.ps1"
  & "$Venv\Scripts\Activate.ps1"
  Write-Host "[4/5] Upgrading pip"
  python -m pip install --upgrade pip
  Write-Host "[5/5] Installing requirements.txt"
  python -m pip install -r requirements.txt
  Write-Host "Done. Activate later with: .\$Venv\Scripts\Activate.ps1"
} catch {
  Write-Host "Setup failed: $($_.Exception.Message)" -ForegroundColor Red
  Write-Host "Check the failing package line above, disk space, file permissions, and Python installation." -ForegroundColor Yellow
  throw
}
