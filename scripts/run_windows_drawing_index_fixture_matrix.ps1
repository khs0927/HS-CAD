[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Root,

    [string]$Workspace = "outputs\codex-windows-fixture-matrix",
    [string]$PythonExe = ".venv\Scripts\python.exe",
    [string[]]$Query = @(),
    [switch]$SkipSetup,
    [switch]$WithOCR,
    [switch]$KeepExisting
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

if ($env:OS -ne "Windows_NT") {
    throw "This fixture matrix must run on Windows with the user's local CAD installation."
}

$rootPath = (Resolve-Path $Root).Path
$workspacePath = [System.IO.Path]::GetFullPath((Join-Path $repo $Workspace))
$nativeWorkspace = Join-Path $workspacePath "native-zwcad"
$fallbackWorkspace = Join-Path $workspacePath "fallback-only"
$comparisonMd = Join-Path $workspacePath "CODEX_WINDOWS_FIXTURE_COMPARISON.md"
$comparisonJson = Join-Path $workspacePath "CODEX_WINDOWS_FIXTURE_COMPARISON.json"
$resultMd = Join-Path $workspacePath "CODEX_WINDOWS_VALIDATION_RESULT.md"

if ((Test-Path $workspacePath) -and -not $KeepExisting) {
    Remove-Item -Recurse -Force $workspacePath
}
New-Item -ItemType Directory -Force -Path $workspacePath | Out-Null

if (-not $SkipSetup) {
    $setupArgs = @("-ExecutionPolicy", "Bypass", "-File", "scripts\setup_free_local.ps1")
    if ($WithOCR) { $setupArgs += "-WithOCR" }
    & powershell @setupArgs
    if ($LASTEXITCODE -ne 0) { throw "Free local environment setup failed." }
}

if (-not (Test-Path $PythonExe)) {
    throw "Python executable not found: $PythonExe"
}
$python = (Resolve-Path $PythonExe).Path

function Invoke-ValidationPass {
    param(
        [string]$Name,
        [string]$TargetWorkspace,
        [switch]$NoNative
    )

    Write-Host ""
    Write-Host "[HS-CAD] Running $Name fixture pass"
    New-Item -ItemType Directory -Force -Path $TargetWorkspace | Out-Null
    $logPath = Join-Path $TargetWorkspace "console.log"
    $args = @(
        "scripts\validate_drawing_index_v2.py",
        $rootPath,
        "--workspace", $TargetWorkspace,
        "--sample", "0",
        "--strict"
    )
    foreach ($item in $Query) {
        $args += @("--query", $item)
    }
    if ($NoNative) { $args += "--no-native-zwcad" }

    & $python @args 2>&1 |
        Tee-Object -FilePath $logPath |
        ForEach-Object { Write-Host $_ }
    $exitCode = $LASTEXITCODE
    return $exitCode
}

$nativeExit = Invoke-ValidationPass -Name "native ZWCAD + fallback" -TargetWorkspace $nativeWorkspace
$fallbackExit = Invoke-ValidationPass -Name "fallback-only" -TargetWorkspace $fallbackWorkspace -NoNative

Write-Host ""
Write-Host "[HS-CAD] Comparing fixture passes"
& $python scripts\compare_drawing_index_fixture_runs.py `
    $nativeWorkspace `
    $fallbackWorkspace `
    --out $comparisonMd `
    --json-out $comparisonJson
$comparisonExit = $LASTEXITCODE

$zwcadProcesses = @(Get-Process -ErrorAction SilentlyContinue | Where-Object {
    $_.ProcessName -match "^ZWCAD$"
})
$zwcadStatus = if ($zwcadProcesses.Count -gt 0) {
    "Detected running ZWCAD process"
} else {
    "No running ZWCAD process detected after validation"
}

$lines = @(
    "# Codex Windows/ZWCAD Validation Result",
    "",
    "- Date: $(Get-Date -Format o)",
    "- Repository: $repo",
    "- Drawing root: $rootPath",
    "- Native pass exit code: $nativeExit",
    "- Fallback pass exit code: $fallbackExit",
    "- Comparison exit code: $comparisonExit",
    "- ZWCAD observation: $zwcadStatus",
    "",
    "## Artifacts",
    "",
    "- [Native validation report](native-zwcad/DRAWING_INDEX_V2_VALIDATION.md)",
    "- [Fallback validation report](fallback-only/DRAWING_INDEX_V2_VALIDATION.md)",
    "- [Comparison report](CODEX_WINDOWS_FIXTURE_COMPARISON.md)",
    "- [Comparison JSON](CODEX_WINDOWS_FIXTURE_COMPARISON.json)",
    "",
    "## Required manual review",
    "",
    "Open every drawing marked REVIEW or BLOCK and compare its layouts, XREFs, proxy objects, dimensions, tables, leaders, raster/OLE content, and searchable text against the generated evidence.",
    ""
)
Set-Content -Path $resultMd -Value ($lines -join "`n") -Encoding utf8

Write-Host ""
Write-Host "Result: $resultMd"
Write-Host "Comparison: $comparisonMd"

if ($nativeExit -ne 0 -or $comparisonExit -ne 0) {
    exit 1
}
exit 0
