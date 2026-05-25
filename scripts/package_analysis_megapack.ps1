param(
  [string]$Out = "outputs\HS-CAD-analysis-megapack-code.zip"
)

$ErrorActionPreference = "Stop"
chcp 65001 | Out-Null
$env:PYTHONIOENCODING = "utf-8"

if (Test-Path $Out) { Remove-Item -LiteralPath $Out -Force }

$paths = @(
  "src\analysis",
  "src\workers",
  "src\app\analysis_shortcut_cli.py",
  "config\worker_manifest.json",
  "docs\43_analysis_core_megapack_plan.md",
  "docs\44_analysis_graph_megapack_plan.md",
  "docs\45_analysis_advanced_megapack_plan.md",
  "docs\46_analysis_ops_megapack_plan.md",
  "docs\47_analysis_automation_megapack_plan.md",
  "docs\48_analysis_evidence_megapack_plan.md",
  "docs\49_analysis_cli_shortcuts_todo.md",
  "docs\VALIDATION_TODO_ALL_MEGAPACKS.md"
) | Where-Object { Test-Path $_ }

Compress-Archive -Path $paths -DestinationPath $Out -Force
Write-Host "Created $Out"
