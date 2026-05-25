param(
  [string]$RepoRoot = "."
)

$ErrorActionPreference = "Stop"

python -X utf8 scripts\collect_final_todos.py
python -X utf8 scripts\generate_final_apply_plan.py
python -X utf8 scripts\write_codex_final_apply_prompt.py
python -X utf8 scripts\build_final_codegen_inventory.py

Write-Host "Generated:"
Write-Host "  outputs\FINAL_TODO_INDEX.md"
Write-Host "  outputs\FINAL_APPLY_PLAN.md"
Write-Host "  outputs\CODEX_FINAL_APPLY_PROMPT.md"
Write-Host "  outputs\FINAL_CODEGEN_INVENTORY.md"
Write-Host "Validation remains TODO."
