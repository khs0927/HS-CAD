param(
  [string]$ZipDir = ".",
  [string]$RepoRoot = ".",
  [string]$Out = "outputs\HS-CAD-final-codegen-bundle.zip"
)

$ErrorActionPreference = "Stop"

python -X utf8 scripts\apply_megapack_zips.py --zip-dir $ZipDir --repo-root $RepoRoot
python -X utf8 scripts\update_worker_manifest_from_fragments.py --repo-root $RepoRoot
python -X utf8 scripts\update_main_imports.py --repo-root $RepoRoot
python -X utf8 scripts\build_final_codegen_zip.py --repo-root $RepoRoot --out $Out

Write-Host "Final codegen bundle created: $Out"
Write-Host "Validation remains TODO. Do not run tests unless ready."
