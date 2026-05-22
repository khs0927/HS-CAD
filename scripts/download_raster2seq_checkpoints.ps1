<# ──────────────────────────────────────────────────────────────
   download_raster2seq_checkpoints.ps1
   Download Raster2Seq pre-trained checkpoints using gdown.
   Usage: pwsh scripts/download_raster2seq_checkpoints.ps1
   ────────────────────────────────────────────────────────────── #>

$ErrorActionPreference = "Stop"

$ROOT = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$CKPT_DIR = Join-Path $ROOT "third_party" "Raster2Seq" "checkpoints"

if (-not (Test-Path $CKPT_DIR)) {
    New-Item -ItemType Directory -Path $CKPT_DIR | Out-Null
    Write-Host "[INFO] Created checkpoint directory: $CKPT_DIR" -ForegroundColor Cyan
}

# ── Checkpoint Google Drive file IDs ─────────────────────────
$checkpoints = @(
    @{ Name = "cubicasa.ckpt"; FileId = "1Fq6WKkI0k5_jHxodhyQzJcFVf_0vqcfm" },
    @{ Name = "s3d.ckpt";     FileId = "1gqKLjhINqPsM8UfMPfhGz2aAixlJJoIx" },
    @{ Name = "r2g.ckpt";     FileId = "1M7k0jZwsIwmfGTjFLqC_W_EgSr3F8-t4" }
)

# ── Check gdown is available ─────────────────────────────────
try {
    $null = Get-Command gdown -ErrorAction Stop
}
catch {
    Write-Host "[ERROR] gdown not found. Install it: pip install gdown" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "═══════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Raster2Seq Checkpoint Download" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

foreach ($ckpt in $checkpoints) {
    $dest = Join-Path $CKPT_DIR $ckpt.Name
    if (Test-Path $dest) {
        $size = [math]::Round((Get-Item $dest).Length / 1MB, 1)
        Write-Host "[SKIP] $($ckpt.Name) — already exists (${size} MB)" -ForegroundColor Yellow
    }
    else {
        Write-Host "[DOWNLOAD] $($ckpt.Name) (Google Drive ID: $($ckpt.FileId))" -ForegroundColor Green
        $url = "https://drive.google.com/uc?id=$($ckpt.FileId)"
        gdown $url -O $dest
        if ($LASTEXITCODE -eq 0) {
            $size = [math]::Round((Get-Item $dest).Length / 1MB, 1)
            Write-Host "[OK] $($ckpt.Name) downloaded (${size} MB)" -ForegroundColor Green
        }
        else {
            Write-Host "[ERROR] Failed to download $($ckpt.Name)" -ForegroundColor Red
        }
    }
}

Write-Host ""
Write-Host "Done. Checkpoints are in: $CKPT_DIR" -ForegroundColor Cyan
Write-Host ""
