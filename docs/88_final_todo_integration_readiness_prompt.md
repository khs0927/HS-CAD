# HS-CAD Final TODO Integration Readiness Prompt

## Goal

Process all remaining TODOs after Phase 3~12:

1. Verify PR stack order.
2. Generate final TODO readiness report.
3. Prepare CLI registration PR.
4. Prepare worker manifest registration PR.
5. Prepare final integration readiness PR.
6. Keep live runner disabled.

## Branch

```powershell
git fetch origin feat/analysis-phase12-manual-live-execution-candidate
git switch feat/analysis-phase12-manual-live-execution-candidate
git switch -c integration/final-todo-readiness
```

## Apply patch ZIP

Save the ZIP at:

```text
C:\Users\user\Downloads\HS-CAD-final-todo-integration-readiness-bundle.zip
```

Apply from repo root:

```powershell
cd C:\CODE\HS-CAD
Expand-Archive -Path "C:\Users\user\Downloads\HS-CAD-final-todo-integration-readiness-bundle.zip" -DestinationPath ".\_final_todo_patch" -Force
Copy-Item -Path ".\_final_todo_patch\*" -Destination "." -Recurse -Force
```

## Optional CLI registration

Add to `src/main.py` only if CLI registration is included in this PR:

```python
import src.app.final_todo_cli  # noqa: F401,E402
```

Otherwise keep CLI registration separate.

## Targeted tests

```powershell
python -X utf8 -m pytest -q tests/test_final_todo_integration_readiness.py
python -X utf8 -m src.main --help
```

## Optional CLI smoke

If CLI registration was added:

```powershell
python -X utf8 -m src.main hscad-final-todo-readiness --repo-root . --workspace outputs\phase12_manual_live_candidate_verify --out-dir outputs\final_todo_integration_readiness
```

Expected outputs:

```text
FINAL_TODO_INTEGRATION_READINESS.json
FINAL_TODO_INTEGRATION_READINESS.md
FINAL_PR_SEQUENCE_PLAN.json
```

## Safety checks

Confirm:

- live_execution_ready is false
- final_runner_implemented is false
- cad_execution_allowed_by_default is false
- sendcommand_allowed_by_default is false
- outputs are not committed
- no DWG/DXF files are committed

## Full validation

```powershell
python -X utf8 -m pytest -q
```

## Commit

```powershell
git add src/analysis/final_todo_integration_readiness.py
git add src/workers/final_todo_integration_readiness_worker.py
git add src/app/final_todo_cli.py
git add tests/test_final_todo_integration_readiness.py
git add docs/88_final_todo_integration_readiness_prompt.md
git add docs/89_final_todo_integration_readiness_report.md
git add docs/90_final_live_runner_deferred_safety_policy.md
git add config/worker_manifest.final_todo.patch.json
git add MAIN_IMPORT_FINAL_TODO_PATCH.txt
git add README_APPLY_FINAL_TODO.md

git commit -m "feat: add final todo integration readiness reporting"
git push -u origin integration/final-todo-readiness
```

## PR

Base:

```text
feat/analysis-phase12-manual-live-execution-candidate
```

Head:

```text
integration/final-todo-readiness
```

Title:

```text
Add final TODO integration readiness reporting
```
