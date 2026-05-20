param(
  [Parameter(Mandatory=$true)][string]$DWG,
  [ValidateSet("2025","2026")][string]$Version = "2026",
  [string]$XiCADRoot = "",
  [switch]$StartZWCAD,
  [switch]$ExecuteSmoke,
  [string]$MoveLayer = "MARK",
  [double]$DX = 0,
  [double]$DY = 0
)
$ErrorActionPreference = "Stop"
Write-Host "Original DWG will not be modified. Execute smoke tests run on a copied DWG only." -ForegroundColor Yellow
$outDir = "outputs/zwcad${Version}_test_plan"
$argsList = @("tools/run_zwcad_test_plan.py", "--version", $Version, "--dwg", $DWG, "--out-dir", $outDir)
if ($XiCADRoot -ne "") { $argsList += @("--xicad-root", $XiCADRoot) }
if ($StartZWCAD) { $argsList += "--start-zwcad" }
if ($ExecuteSmoke) { $argsList += @("--execute-smoke", "--move-layer", $MoveLayer, "--dx", $DX, "--dy", $DY) }
python @argsList
