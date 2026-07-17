[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Root,
    [string]$Workspace = "outputs\orchestrator\windows-fixture-matrix",
    [string]$PythonExe = ".venv-windows-runner\Scripts\python.exe",
    [string[]]$Query = @(),
    [switch]$SkipSetup,
    [switch]$WithOCR,
    [switch]$KeepExisting,
    [switch]$AllowStaticOnly
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

if ($env:OS -ne "Windows_NT") { Write-Error "Windows 11 is required for the fixture matrix."; exit 2 }
if (-not (Test-Path $Root -PathType Container)) { Write-Error "Fixture root does not exist."; exit 2 }

$fixtureRoot = (Resolve-Path $Root).Path
$workspacePath = if ([IO.Path]::IsPathRooted($Workspace)) { [IO.Path]::GetFullPath($Workspace) } else { Join-Path $RepoRoot $Workspace }
if ((Test-Path $workspacePath) -and -not $KeepExisting) { Remove-Item -Recurse -Force $workspacePath }
New-Item -ItemType Directory -Force -Path $workspacePath | Out-Null

$pythonPath = if ([IO.Path]::IsPathRooted($PythonExe)) { [IO.Path]::GetFullPath($PythonExe) } else { Join-Path $RepoRoot $PythonExe }
if (-not (Test-Path $pythonPath) -and -not $SkipSetup) {
    & powershell -ExecutionPolicy Bypass -File "scripts\windows-runner-preflight.ps1" -Install -RunVirtualWindows
    if ($LASTEXITCODE -ne 0) { throw "Windows runner preflight failed." }
}
if (-not (Test-Path $pythonPath)) { Write-Error "Python executable not found: $PythonExe"; exit 2 }
$python = (Resolve-Path $pythonPath).Path
if ($WithOCR) {
    & $python -m pip install --disable-pip-version-check -e ".[dev,ocr]"
    if ($LASTEXITCODE -ne 0) { throw "OCR dependency installation failed." }
}

$fixtures = @(Get-ChildItem -Path $fixtureRoot -Recurse -File | Where-Object { $_.Extension.ToLowerInvariant() -in @(".dwg", ".dxf", ".pdf") })
if ($fixtures.Count -eq 0) { Write-Error "No DWG, DXF, or PDF fixtures were found."; exit 4 }
$dwgFixtures = @($fixtures | Where-Object { $_.Extension.ToLowerInvariant() -eq ".dwg" })
if ($dwgFixtures.Count -eq 0 -and -not $AllowStaticOnly) { Write-Error "At least one DWG fixture is required for the strict ZWCAD acceptance gate."; exit 4 }
$zwcad = Get-Process -Name "ZWCAD" -ErrorAction SilentlyContinue
if (-not $zwcad -and -not $AllowStaticOnly) { Write-Error "ZWCAD must be installed and running before the strict acceptance gate can execute."; exit 3 }

function Get-StringSha256([string]$Value) {
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($Value)))).Replace("-", "").ToLowerInvariant() } finally { $sha.Dispose() }
}
$trimChars = [char[]]@([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
$fixturePrefix = $fixtureRoot.TrimEnd($trimChars) + [IO.Path]::DirectorySeparatorChar
$manifest = @{
    schema_version = "1.1"; generated_at = [DateTime]::UtcNow.ToString("o"); fixture_count = $fixtures.Count; strict_cad_required = (-not $AllowStaticOnly)
    extensions = @($fixtures | Group-Object Extension | ForEach-Object { @{ extension = $_.Name.ToLowerInvariant(); count = $_.Count } })
    files = @($fixtures | ForEach-Object {
        $fullPath = [IO.Path]::GetFullPath($_.FullName)
        if (-not $fullPath.StartsWith($fixturePrefix, [StringComparison]::OrdinalIgnoreCase)) { throw "Fixture path escaped the approved fixture root." }
        $relative = $fullPath.Substring($fixturePrefix.Length).Replace("\", "/").ToLowerInvariant()
        @{ path_sha256 = Get-StringSha256 $relative; extension = $_.Extension.ToLowerInvariant(); size_bytes = $_.Length }
    })
}
$manifestPath = Join-Path $workspacePath "fixture-manifest.json"
$manifest | ConvertTo-Json -Depth 6 | Set-Content -Path $manifestPath -Encoding UTF8
$env:HSCAD_FIXTURE_ROOT = $fixtureRoot
$env:HSCAD_FIXTURE_WORKSPACE = $workspacePath
$env:HSCAD_WINDOWS_CAD_ACCEPTANCE = "1"
$env:HSCAD_WINDOWS_STATIC_ONLY = $(if ($AllowStaticOnly) { "1" } else { "0" })
& $python -m pytest -q --disable-warnings --maxfail=1 "tests\test_windows_cad_acceptance.py"
$acceptanceExit = $LASTEXITCODE
if ($acceptanceExit -ne 0) { Write-Error "Windows/ZWCAD acceptance tests failed with exit code $acceptanceExit."; exit $acceptanceExit }
if ($AllowStaticOnly) { Write-Host "Static-only fixture validation passed."; exit 0 }

$nativeWorkspace = Join-Path $workspacePath "native-zwcad"
$fallbackWorkspace = Join-Path $workspacePath "fallback-only"
$comparisonMd = Join-Path $workspacePath "DRAWING_INDEX_FIXTURE_COMPARISON.md"
$comparisonJson = Join-Path $workspacePath "DRAWING_INDEX_FIXTURE_COMPARISON.json"
$resultMd = Join-Path $workspacePath "WINDOWS_VALIDATION_RESULT.md"
function Invoke-ValidationPass {
    param([string]$Name, [string]$TargetWorkspace, [switch]$NoNative)
    New-Item -ItemType Directory -Force -Path $TargetWorkspace | Out-Null
    $args = @("scripts\validate_drawing_index_v2.py", $fixtureRoot, "--workspace", $TargetWorkspace, "--sample", "0", "--strict")
    foreach ($item in $Query) { $args += @("--query", $item) }
    if ($NoNative) { $args += "--no-native-zwcad" }
    & $python @args 2>&1 | Tee-Object -FilePath (Join-Path $TargetWorkspace "console.log") | ForEach-Object { Write-Host $_ }
    return $LASTEXITCODE
}
$nativeExit = Invoke-ValidationPass -Name "native ZWCAD + fallback" -TargetWorkspace $nativeWorkspace
$fallbackExit = Invoke-ValidationPass -Name "fallback-only" -TargetWorkspace $fallbackWorkspace -NoNative
& $python "scripts\compare_drawing_index_fixture_runs.py" $nativeWorkspace $fallbackWorkspace --out $comparisonMd --json-out $comparisonJson
$comparisonExit = $LASTEXITCODE
$lines = @("# Windows/ZWCAD Drawing Index Validation", "", "- Date: $(Get-Date -Format o)", "- Fixture count: $($fixtures.Count)", "- Acceptance exit code: $acceptanceExit", "- Native pass exit code: $nativeExit", "- Fallback pass exit code: $fallbackExit", "- Comparison exit code: $comparisonExit", "", "## Required manual review", "", "Open every drawing marked REVIEW or BLOCK and compare layouts, XREFs, proxy objects, dimensions, tables, leaders, raster/OLE content, and searchable text against the generated local evidence.")
Set-Content -Path $resultMd -Value ($lines -join "`n") -Encoding UTF8
if ($nativeExit -ne 0 -or $fallbackExit -ne 0 -or $comparisonExit -ne 0) { exit 1 }
Write-Host "Windows/ZWCAD Drawing Index full validation passed."
exit 0
