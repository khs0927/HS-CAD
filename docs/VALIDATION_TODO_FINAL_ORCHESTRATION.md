# Validation TODO — Final Orchestration

All verification is deferred.

## Later checks

```powershell
python -X utf8 scripts\collect_final_todos.py
python -X utf8 scripts\generate_final_apply_plan.py
python -X utf8 scripts\write_codex_final_apply_prompt.py
python -X utf8 scripts\build_final_codegen_inventory.py
```

## Expected outputs

```text
outputs\FINAL_TODO_INDEX.md
outputs\FINAL_APPLY_PLAN.md
outputs\CODEX_FINAL_APPLY_PROMPT.md
outputs\FINAL_CODEGEN_INVENTORY.md
```
