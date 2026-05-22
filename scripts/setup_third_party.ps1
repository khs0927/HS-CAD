<# ──────────────────────────────────────────────────────────────
   setup_third_party.ps1
   Clone third-party repositories into ./third_party/
   Usage: pwsh scripts/setup_third_party.ps1
   ────────────────────────────────────────────────────────────── #>

$ErrorActionPreference = "Stop"

$ROOT = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$THIRD = Join-Path $ROOT "third_party"

if (-not (Test-Path $THIRD)) {
    New-Item -ItemType Directory -Path $THIRD | Out-Null
}

# ── Repository list ──────────────────────────────────────────
$repos = @(
    @{ Name = "Raster2Seq";          Url = "https://github.com/Cornell-VAILab/Raster2Seq.git" },
    @{ Name = "planparser";          Url = "https://github.com/anngrrr/planparser.git" },
    @{ Name = "mlsd";                Url = "https://github.com/navervision/mlsd.git" },
    @{ Name = "floorplan-detection"; Url = "https://github.com/Daigo-Kanda/floorplan-detection.git" },
    @{ Name = "Img2CADSeq";         Url = "https://github.com/Rilpraa0110/Img2CADSeq.git" }
)

Write-Host ""
Write-Host "═══════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Third-Party Repository Setup" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

foreach ($repo in $repos) {
    $dest = Join-Path $THIRD $repo.Name
    if (Test-Path $dest) {
        Write-Host "[SKIP] $($repo.Name) — already exists at $dest" -ForegroundColor Yellow
    }
    else {
        Write-Host "[CLONE] $($repo.Name) ← $($repo.Url)" -ForegroundColor Green
        git clone --depth 1 $repo.Url $dest
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[ERROR] Failed to clone $($repo.Name)" -ForegroundColor Red
        }
        else {
            Write-Host "[OK] $($repo.Name) cloned successfully" -ForegroundColor Green
        }
    }
}

Write-Host ""
Write-Host "═══════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Summary" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════" -ForegroundColor Cyan

foreach ($repo in $repos) {
    $dest = Join-Path $THIRD $repo.Name
    if (Test-Path $dest) {
        $fileCount = (Get-ChildItem -Recurse -File $dest | Measure-Object).Count
        Write-Host "  ✓ $($repo.Name) ($fileCount files)" -ForegroundColor Green
    }
    else {
        Write-Host "  ✗ $($repo.Name) — MISSING" -ForegroundColor Red
    }
}

Write-Host ""
