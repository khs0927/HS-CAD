[CmdletBinding()]
param(
    [string]$Python = "py -3.11",
    [string]$Venv = ".venv",
    [switch]$WithOCR,
    [switch]$SkipInstall,
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

$env:HSCAD_RUNTIME_PROFILE = "free-local"
$env:HSCAD_SUMMARY_BACKEND = "local"
$env:HSCAD_ALLOW_PAID_SERVICES = "0"
$env:HSCAD_ALLOW_EXTERNAL_SUMMARY = "0"
$env:HSCAD_ALLOW_NETWORK_MODELS = "0"
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"

if (-not (Test-Path "$Venv\Scripts\python.exe")) {
    Write-Host "[HS-CAD] Creating Python 3.11 virtual environment: $Venv"
    $parts = $Python -split " ", 2
    if ($parts.Count -eq 1) {
        & $parts[0] -m venv $Venv
    } else {
        & $parts[0] $parts[1] -m venv $Venv
    }
    if ($LASTEXITCODE -ne 0) { throw "Failed to create virtual environment" }
}

$pythonExe = Resolve-Path "$Venv\Scripts\python.exe"

if (-not $SkipInstall) {
    Write-Host "[HS-CAD] Installing open-source local runtime"
    & $pythonExe -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed" }
    & $pythonExe -m pip install -e ".[dev]"
    if ($LASTEXITCODE -ne 0) { throw "project installation failed" }
    if ($WithOCR) {
        Write-Host "[HS-CAD] Installing optional local OCR packages"
        & $pythonExe -m pip install -e ".[ocr]"
        if ($LASTEXITCODE -ne 0) { throw "OCR package installation failed" }
    }
}

Write-Host "[HS-CAD] Validating free-only policy"
& $pythonExe scripts\validate_free_only.py
if ($LASTEXITCODE -ne 0) { throw "Free-only validation failed" }

if (-not $SkipTests) {
    Write-Host "[HS-CAD] Running local drawing-index tests"
    & $pythonExe -m pytest -q `
        tests\test_corpus_foundation.py `
        tests\test_drawing_index_v2.py `
        tests\test_drawing_index_architecture.py `
        tests\test_free_only_runtime.py `
        tests\test_compare_drawing_index_fixture_runs.py
    if ($LASTEXITCODE -ne 0) { throw "Local tests failed" }
}

Write-Host ""
Write-Host "Free local environment is ready."
Write-Host "Run:"
Write-Host "  $pythonExe -m src.main corpus-run complete --root D:\CAD --workspace outputs\drawing-index-v2"
Write-Host "Default summary database: outputs\drawing-index-v2\drawing_index_history.sqlite"
