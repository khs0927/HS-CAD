[CmdletBinding()]
param(
    [string]$Version = "0.2.0",
    [switch]$SkipTests,
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not $IsWindows) {
    throw "HS-CAD Windows releases must be built on Windows."
}

$Python = Get-Command py -ErrorAction SilentlyContinue
if ($Python) {
    $PythonArgs = @("-3.11")
    $PythonExe = "py"
} else {
    $Python = Get-Command python -ErrorAction Stop
    $PythonArgs = @()
    $PythonExe = $Python.Source
}

$Venv = Join-Path $Root ".venv-build"
if (-not (Test-Path $Venv)) {
    & $PythonExe @PythonArgs -m venv $Venv
}

$VenvPython = Join-Path $Venv "Scripts\python.exe"
& $VenvPython -m pip install --upgrade pip wheel setuptools
& $VenvPython -m pip install -e ".[dev,build]"

if (-not $SkipTests) {
    & $VenvPython -m pytest -q --disable-warnings --maxfail=1
}

& $VenvPython scripts\build_windows_exe.py

$PortableExe = Join-Path $Root "dist\HS-CAD.exe"
if (-not (Test-Path $PortableExe)) {
    throw "Portable executable was not produced: $PortableExe"
}

if (-not $SkipInstaller) {
    $Candidates = @(
        "$env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    )
    $Iscc = $Candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $Iscc) {
        throw "Inno Setup 6 was not found. Install it or run with -SkipInstaller."
    }

    & $Iscc "/DMyAppVersion=$Version" "installer\HS-CAD.iss"
    $SetupExe = Join-Path $Root "dist\HS-CAD-Setup-$Version.exe"
    if (-not (Test-Path $SetupExe)) {
        throw "Installer was not produced: $SetupExe"
    }
}

Write-Host "HS-CAD release build completed." -ForegroundColor Green
Get-ChildItem (Join-Path $Root "dist") | Format-Table Name, Length, LastWriteTime
