param(
  [Parameter(Mandatory = $true)][string]$Root,
  [string]$Workspace = "outputs/orchestrator/windows-fixture-matrix"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

if ($env:OS -ne "Windows_NT") {
  Write-Error "Windows 11 is required for the ZWCAD fixture matrix."
  exit 2
}
if (-not (Test-Path $Root -PathType Container)) {
  Write-Error "Fixture root does not exist."
  exit 2
}

$zwcad = Get-Process -Name "ZWCAD" -ErrorAction SilentlyContinue
if (-not $zwcad) {
  Write-Error "ZWCAD must be installed and running before this acceptance gate can execute."
  exit 3
}

$venvPython = Join-Path $RepoRoot ".venv-windows-runner\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
  Write-Error "Windows runner environment is missing. Run scripts/windows-runner-preflight.ps1 -Install first."
  exit 2
}

$fixtureRoot = (Resolve-Path $Root).Path
$workspacePath = Join-Path $RepoRoot $Workspace
New-Item -ItemType Directory -Force -Path $workspacePath | Out-Null

$fixtures = Get-ChildItem -Path $fixtureRoot -Recurse -File | Where-Object {
  $_.Extension.ToLowerInvariant() -in @(".dwg", ".dxf", ".pdf")
}
if (-not $fixtures -or $fixtures.Count -eq 0) {
  Write-Error "No DWG, DXF, or PDF fixtures were found."
  exit 4
}

$manifest = @{
  schema_version = "1.0"
  generated_at = [DateTime]::UtcNow.ToString("o")
  fixture_count = $fixtures.Count
  extensions = @($fixtures | Group-Object Extension | ForEach-Object {
    @{ extension = $_.Name.ToLowerInvariant(); count = $_.Count }
  })
  files = @($fixtures | ForEach-Object {
    $relative = [IO.Path]::GetRelativePath($fixtureRoot, $_.FullName)
    @{ relative_path = $relative; size_bytes = $_.Length }
  })
}
$manifestPath = Join-Path $workspacePath "fixture-manifest.json"
$manifest | ConvertTo-Json -Depth 6 | Set-Content -Path $manifestPath -Encoding UTF8

$env:HSCAD_FIXTURE_ROOT = $fixtureRoot
$env:HSCAD_FIXTURE_WORKSPACE = $workspacePath
$env:HSCAD_WINDOWS_CAD_ACCEPTANCE = "1"

& $venvPython -m pytest -q --disable-warnings --maxfail=1 -m "windows or zwcad"
$testExit = $LASTEXITCODE
if ($testExit -ne 0) {
  Write-Error "Windows/ZWCAD acceptance tests failed with exit code $testExit."
  exit $testExit
}

Write-Host "Windows/ZWCAD fixture matrix passed."
Write-Host "Manifest: $manifestPath"
