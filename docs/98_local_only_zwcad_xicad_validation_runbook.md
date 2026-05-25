# HS-CAD Local-only ZWCAD/XiCAD Validation Runbook

## When to use

Use this only after review-only PR stack is green and main readiness review is complete.

## Local-only validations

### 1. Copied DWG scan validation

```powershell
python -X utf8 -m src.main zwcad-copy-scan-validate --original-dwg "C:/cad/test/original.dwg" --working-copy-dwg "C:/cad/test_work/copy.dwg" --out-dir outputs/zwcad_copy_validation_live
```

Confirm:

- original hash unchanged
- working copy path differs from original
- audit log exists
- no SendCommand for scan

### 2. Copied DWG SaveAs validation

```powershell
python -X utf8 -m src.main zwcad-copy-saveas-validate --original-dwg "C:/cad/test/original.dwg" --working-copy-dwg "C:/cad/test_work/copy.dwg" --save-as-target "C:/cad/test_work/result.dwg" --out-dir outputs/zwcad_copy_saveas_validation_live --overwrite-copy
```

Confirm:

- SaveAs target differs from original
- original hash unchanged
- before/after scan exists
- delta report exists
- audit log exists

### 3. C:/xicad policy candidate generation

```powershell
python -X utf8 -m src.main xicad-policy-candidates --xicad-root C:/xicad --out-dir outputs/xicad_policy_candidates_verify
```

Confirm:

- allowed_for_execution remains false
- execution_allowed_aliases remains empty
- unknown aliases blocked
- destructive aliases blocked

### 4. Phase 12 candidate guard only

```powershell
python -X utf8 -m src.main hscad-analysis-phase12-manual-live-candidate --workspace outputs/phase10_11_domain_copy_verify --alias WAL --manual-live-flag --operator-approved --out-dir outputs/phase12_manual_live_candidate_verify
```

Confirm:

- execution_allowed false
- sendcommand_allowed false
- final runner not implemented
- original DWG not mutated

## Not allowed

- original DWG live execution
- unknown alias
- destructive alias
- automatic operator approval
- final live runner without separate safety PR
