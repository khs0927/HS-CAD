param(
  [Parameter(Mandatory=$true)][string]$DWG,
  [string]$XiCADRoot = "",
  [switch]$StartZWCAD,
  [switch]$ExecuteSmoke,
  [string]$MoveLayer = "MARK",
  [double]$DX = 0,
  [double]$DY = 0
)
$ErrorActionPreference = "Stop"
Write-Host "Original DWG will not be modified. Execute smoke tests run on a copied DWG only." -ForegroundColor Yellow
$argsList = @("tools/run_zwcad2025_test_plan.py", "--dwg", $DWG, "--out-dir", "outputs/zwcad2025_test_plan")
if ($XiCADRoot -ne "") { $argsList += @("--xicad-root", $XiCADRoot) }
if ($StartZWCAD) { $argsList += "--start-zwcad" }
if ($ExecuteSmoke) { $argsList += @("--execute-smoke", "--move-layer", $MoveLayer, "--dx", $DX, "--dy", $DY) }
python @argsList
