# Apply Final Live Runner Preflight Guard

## Purpose
This patch provides the final live runner preflight guard which validates that all required safety prerequisites have been met before any actual implementation of live CAD automation can occur.

## How to Apply

1. The CLI is automatically registered in `src/main.py`.
2. The worker manifests can be applied using the patch tools if necessary.
3. Tests are provided in `tests/test_final_live_runner_preflight_guard.py`.

## Testing

```powershell
python -X utf8 -m pytest -q tests/test_final_live_runner_preflight_guard.py
```

## CLI Usage Example

```powershell
python -X utf8 -m src.main hscad-final-live-runner-preflight-guard ^
  --candidate-json outputs\phase12_manual_live_candidate_verify\PHASE12_MANUAL_LIVE_EXECUTION_CANDIDATE.json ^
  --allowlist-json outputs\phase10_11_domain_copy_verify\XICAD_ALIAS_ALLOWLIST_PLAN.json ^
  --zwcad-com-evidence-json outputs\zwcad_com_evidence_probe\ZWCAD_COM_EVIDENCE_PROBE.json ^
  --local-validation-summary-json outputs\local_validation_recorder\LOCAL_VALIDATION_RESULT_SUMMARY.json ^
  --safety-spec-approval-md docs\149_final_live_runner_safety_spec_approval_after_com_probe.md ^
  --original-dwg "C:/cad/test/original.dwg" ^
  --working-copy-dwg "C:/cad/test_work/copy.dwg" ^
  --save-as-target "C:/cad/test_work/result.dwg" ^
  --alias WAL ^
  --manual-live-flag ^
  --operator-approved ^
  --out-dir outputs\final_live_runner_preflight_guard
```

## Important Safety Notes
- This guard **does not** execute CAD commands.
- It **does not** run SendCommand or SaveAs.
- Output artifacts should **never** be committed to version control.
- `execution_allowed` will always default to `false`.
