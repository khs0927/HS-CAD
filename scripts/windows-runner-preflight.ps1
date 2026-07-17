param(
  [string]$Python = "py",
  [string]$FixtureRoot = "",
  [switch]$Install,
  [switch]$RunPortable
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

function Write-Check([string]$Name, [bool]$Ok, [string]$Detail) {
  $state = if ($Ok) { "PASS" } else { "FAIL" }
  Write-Host "[$state] $Name - $Detail"
  if (-not $Ok) { $script:Failed = $true }
}

$script:Failed = $false
Write-Host "HS-CAD Windows Runner preflight"
Write-Host "Repository: $RepoRoot"

if ($env:OS -ne "Windows_NT") {
  Write-Check "Windows platform" $false "This runner must execute on Windows."
  exit 2
}
Write-Check "Windows platform" $true ([System.Environment]::OSVersion.VersionString)

$pythonCmd = Get-Command $Python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
  Write-Check "Python launcher" $false "Install Python 3.10, 3.11, or 3.12 and ensure '$Python' is available."
  exit 2
}

$versionText = & $Python -3.12 -c "import sys; print('.'.join(map(str, sys.version_info[:3])))" 2>$null
$pythonArgs = @("-3.12")
if (-not $versionText) {
  $versionText = & $Python -3.11 -c "import sys; print('.'.join(map(str, sys.version_info[:3])))" 2>$null
  $pythonArgs = @("-3.11")
}
if (-not $versionText) {
  $versionText = & $Python -3.10 -c "import sys; print('.'.join(map(str, sys.version_info[:3])))" 2>$null
  $pythonArgs = @("-3.10")
}
Write-Check "Supported Python" ([bool]$versionText) ($(if ($versionText) { $versionText } else { "Required: >=3.10,<3.13" }))
if (-not $versionText) { exit 2 }

$venv = Join-Path $RepoRoot ".venv-windows-runner"
$venvPython = Join-Path $venv "Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
  if (-not $Install) {
    Write-Check "Virtual environment" $false "Missing. Re-run with -Install."
    exit 2
  }
  & $Python @pythonArgs -m venv $venv
}
Write-Check "Virtual environment" (Test-Path $venvPython) $venv

if ($Install) {
  & $venvPython -m pip install --disable-pip-version-check --upgrade pip
  & $venvPython -m pip install --disable-pip-version-check -e ".[dev]"
}

& $venvPython -c "import comtypes, win32api, pydantic, ezdxf; print('imports-ok')" | Out-Null
Write-Check "Windows dependencies" ($LASTEXITCODE -eq 0) "comtypes, pywin32, pydantic, ezdxf"

$required = @(
  "scripts\run_plugin_orchestrator.py",
  "scripts\publish_orchestrator_evidence.py",
  "pyproject.toml"
)
foreach ($relative in $required) {
  Write-Check "Required file" (Test-Path (Join-Path $RepoRoot $relative)) $relative
}

$zwcad = Get-Process -Name "ZWCAD" -ErrorAction SilentlyContinue
if ($zwcad) {
  Write-Check "ZWCAD process" $true "PID $($zwcad.Id -join ',')"
} else {
  Write-Host "[BLOCKED] ZWCAD process - not running; portable checks remain available."
}

if ($FixtureRoot) {
  Write-Check "Fixture root" (Test-Path $FixtureRoot) $FixtureRoot
}

if ($RunPortable) {
  $output = Join-Path $RepoRoot "outputs\orchestrator\windows-preflight.json"
  & $venvPython "scripts\run_plugin_orchestrator.py" --profile core --continue-on-error --output $output
  Write-Check "Portable orchestrator" ($LASTEXITCODE -eq 0) $output
}

if ($script:Failed) { exit 1 }
Write-Host "Windows runner preflight completed."
