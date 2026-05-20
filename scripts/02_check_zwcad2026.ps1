param(
  [switch]$StartZWCAD,
  [string]$OutDir = "outputs/zwcad2026_env_check"
)
$ErrorActionPreference = "Stop"
$argsList = @("-m", "src.main", "env-check", "--version", "2026", "--out-dir", $OutDir)
if ($StartZWCAD) { $argsList += "--start-zwcad" }
python @argsList
Write-Host "Results: $OutDir\environment_check.json and $OutDir\environment_check.md"
Write-Host "If COM fails, run ZWCAD once as administrator, confirm 64-bit Python/ZWCAD, or retry with -StartZWCAD."
