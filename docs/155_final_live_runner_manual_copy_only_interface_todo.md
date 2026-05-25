# HS-CAD Final Live Runner Manual Copy-only Interface TODO

## Purpose

This TODO closes the gap between the remote PR #77 branch and the full local megapack ZIP.

The ZIP artifact is:

```text
C:\Users\user\Downloads\HS-CAD-final-live-runner-manual-copy-only-interface.zip
```

This work continues after PR #75 / `feat/final-live-runner-preflight-guard`.

## Current remote status

The PR #77 branch already contains the core review-only interface modules:

- `src/analysis/final_live_runner_manual_copy_only_interface.py`
- `src/workers/final_live_runner_manual_copy_only_interface_worker.py`
- `src/app/final_live_runner_manual_copy_interface_cli.py`
- `docs/152_final_live_runner_manual_copy_only_interface_prompt.md`
- `config/worker_manifest.final_live_runner_manual_copy_only_interface.patch.json`
- `MAIN_IMPORT_FINAL_LIVE_RUNNER_MANUAL_COPY_ONLY_INTERFACE_PATCH.txt`
- `README_APPLY_FINAL_LIVE_RUNNER_MANUAL_COPY_ONLY_INTERFACE.md`

Some ZIP files were intentionally left for local completion because direct remote write checks blocked a few large validation/report files.

## Strict safety scope

This interface remains review-only.

It must not perform:

- CAD execution
- DWG mutation
- automatic operator approval
- production runner behavior
- any automatic live command path

All safety outputs must remain false by default:

- `execution_allowed=false`
- `sendcommand_allowed=false`
- `saveas_allowed=false`
- `xicad_alias_execution_allowed=false`
- `original_dwg_mutation_allowed=false`
- `production_execution_allowed=false`

## TODO 1 — Sync PR #77 with its base

1. Check PR #75 and PR #77 status.
2. Update `feat/manual-copy-interface` with the latest `feat/final-live-runner-preflight-guard`.
3. Resolve only additive/import conflicts if any.
4. Keep `src/main.py` clean and avoid duplicate imports.

Expected result:

- PR #77 is no longer behind its base.
- PR #77 becomes mergeable after validation.

## TODO 2 — Apply the full megapack ZIP

Apply the ZIP content into the working tree.

Expected files after applying the ZIP:

- `tests/test_final_live_runner_manual_copy_only_interface.py`
- `docs/153_final_live_runner_manual_copy_only_interface_report.md`
- `docs/154_final_live_runner_manual_copy_only_interface_result.md`
- `PROMPT_FINAL_LIVE_RUNNER_MANUAL_COPY_ONLY_INTERFACE.txt`

The prompt file may be kept as an archived reference only if project convention allows it. If not, do not commit it.

## TODO 3 — Register CLI import

Add the CLI registration line to `src/main.py` only if it is not already present:

```python
import src.app.final_live_runner_manual_copy_interface_cli  # noqa: F401,E402
```

Do not add duplicates.

## TODO 4 — Validate without local CAD execution

Run validation that does not require ZWCAD live operation.

Required checks:

```powershell
python -X utf8 -m pytest -q tests/test_final_live_runner_manual_copy_only_interface.py
python -X utf8 -m compileall -q src tests
python -X utf8 -m pytest -q
python -X utf8 -m src.main --help
```

Optional if available:

```powershell
python -X utf8 -m ruff check src tests --select E9,F63,F7,F82,F821
```

## TODO 5 — Run dry CLI smoke only

Run the CLI smoke in review-only mode.

Expected behavior:

- If preflight outputs are missing, status may be `blocked`.
- A blocked result is acceptable if refusal reasons are written.
- No live CAD operation may occur.
- All execution-related flags must remain false.

Expected artifacts:

- `FINAL_LIVE_RUNNER_MANUAL_COPY_ONLY_INTERFACE.json`
- `FINAL_LIVE_RUNNER_MANUAL_COPY_ONLY_INTERFACE.md`
- `FINAL_LIVE_RUNNER_OPERATOR_CONFIRMATION_PROMPT.md`
- `FINAL_LIVE_RUNNER_MANUAL_COPY_ONLY_AUDIT_INTENT.json`
- `FINAL_LIVE_RUNNER_MANUAL_COPY_ONLY_REFUSAL.json`
- `NEXT_MANUAL_COPY_ONLY_EXECUTION_CANDIDATE_PR.json`

Do not commit anything under `outputs/**`.

## TODO 6 — Fill result report

Update:

```text
docs/154_final_live_runner_manual_copy_only_interface_result.md
```

Required fields:

- target test result
- compileall result
- full pytest result
- `src.main --help` result
- ruff result or skip reason
- CLI smoke status
- interface status
- all safety flags
- git pollution check
- PR #77 mergeability

## TODO 7 — Commit allowed files only

Allowed files:

- `src/analysis/final_live_runner_manual_copy_only_interface.py`
- `src/workers/final_live_runner_manual_copy_only_interface_worker.py`
- `src/app/final_live_runner_manual_copy_interface_cli.py`
- `tests/test_final_live_runner_manual_copy_only_interface.py`
- `docs/152_final_live_runner_manual_copy_only_interface_prompt.md`
- `docs/153_final_live_runner_manual_copy_only_interface_report.md`
- `docs/154_final_live_runner_manual_copy_only_interface_result.md`
- `docs/155_final_live_runner_manual_copy_only_interface_todo.md`
- `config/worker_manifest.final_live_runner_manual_copy_only_interface.patch.json`
- `MAIN_IMPORT_FINAL_LIVE_RUNNER_MANUAL_COPY_ONLY_INTERFACE_PATCH.txt`
- `README_APPLY_FINAL_LIVE_RUNNER_MANUAL_COPY_ONLY_INTERFACE.md`
- `src/main.py`

Forbidden files:

- `outputs/**`
- `*.dwg`
- `*.dxf`
- `__pycache__/**`
- `.pytest_cache/**`
- temporary ZIP extraction folders

## TODO 8 — Final PR state

Before requesting review:

- PR #77 should target `feat/final-live-runner-preflight-guard`.
- PR #77 should be mergeable.
- The branch should be clean.
- The full Python test suite should pass.
- The interface must remain dry-run/review-only.

## Next stage after PR #77

The next stage is not production execution.

Recommended next PR name:

```text
feat/final-live-runner-manual-copy-only-execution-candidate
```

That future PR must still remain human-gated and copy-only. It must not be started until PR #77 is fully validated and reviewed.
