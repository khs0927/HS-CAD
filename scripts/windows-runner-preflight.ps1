param(
  [string]$Python = "py",
  [string]$FixtureRoot = "",
  [switch]$Install,
  [switch]$RunPortable,
  [switch]$RunVirtualWindows
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

function Test-SupportedVersion([string]$VersionText) {
  if (-not $VersionText) { return $false }
  try {
    $parts = $VersionText.Trim().Split(".")
    $major = [int]$parts[0]
    $minor = [int]$parts[1]
    return ($major -eq 3 -and $minor -ge 10 -and $minor -lt 13)
  } catch {
    return $false
  }
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

$pythonArgs = @()
$versionText = ""
try {
  $directVersion = & $Python -c "import sys; print('.'.join(map(str, sys.version_info[:3])))" 2>$null
  if (Test-SupportedVersion $directVersion) {
    $versionText = $directVersion
  }
} catch {}

if (-not $versionText -and $pythonCmd.Name -match '^py(\.exe)?$') {
  foreach ($candidate in @("3.12", "3.11", "3.10")) {
    try {
      $candidateVersion = & $Python "-$candidate" -c "import sys; print('.'.join(map(str, sys.version_info[:3])))" 2>$null
      if (Test-SupportedVersion $candidateVersion) {
        $versionText = $candidateVersion
        $pythonArgs = @("-$candidate")
        break
      }
    } catch {}
  }
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

try {
  & $venvPython -c "import comtypes, win32api, win32com.client, pydantic, ezdxf; print('imports-ok')" | Out-Null
  Write-Check "Windows dependencies" ($LASTEXITCODE -eq 0) "comtypes, pywin32, pydantic, ezdxf"
} catch {
  Write-Check "Windows dependencies" $false "Import verification failed."
}

$required = @(
  "scripts\run_plugin_orchestrator.py",
  "scripts\publish_orchestrator_evidence.py",
  "scripts\validate_windows_runner_contract.py",
  "tests\test_windows_runner_virtualization.py",
  "tests\test_windows_runner_contract.py",
  "tests\test_windows_cad_acceptance.py",
  "pyproject.toml"
)
foreach ($relative in $required) {
  Write-Check "Required file" (Test-Path (Join-Path $RepoRoot $relative)) $relative
}

$zwcad = Get-Process -Name "ZWCAD" -ErrorAction SilentlyContinue
if ($zwcad) {
  Write-Check "ZWCAD process" $true "PID $($zwcad.Id -join ',')"
} else {
  Write-Host "[BLOCKED] ZWCAD process - not running; portable and virtual checks remain available."
}

if ($FixtureRoot) {
  Write-Check "Fixture root" (Test-Path $FixtureRoot -PathType Container) $FixtureRoot
}

$contractOutput = Join-Path $RepoRoot "outputs\orchestrator\windows-runner-contract.json"
& $venvPython "scripts\validate_windows_runner_contract.py" --json-output $contractOutput
Write-Check "Windows runner contract" ($LASTEXITCODE -eq 0) $contractOutput

if ($RunVirtualWindows) {
  & $venvPython -m pytest -q --disable-warnings --maxfail=1 `
    "tests\test_windows_runner_virtualization.py" `
    "tests\test_windows_runner_contract.py"
  Write-Check "Virtual Windows simulation" ($LASTEXITCODE -eq 0) "mocked platform, COM, and fail-closed contracts"
}

if ($RunPortable) {
  $output = Join-Path $RepoRoot "outputs\orchestrator\windows-preflight.json"
  & $venvPython "scripts\run_plugin_orchestrator.py" --profile core --continue-on-error --output $output
  Write-Check "Portable orchestrator" ($LASTEXITCODE -eq 0) $output
}

if ($script:Failed) { exit 1 }
Write-Host "Windows runner preflight completed."
