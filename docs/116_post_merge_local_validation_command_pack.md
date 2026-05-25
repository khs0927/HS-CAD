# HS-CAD Post-merge Local Validation Command Pack

Run these only after human main merge approval and only in Windows/ZWCAD/C:/xicad environment.

## 1. Copied DWG scan validation

```powershell
python -X utf8 -m src.main zwcad-copy-scan-validate --original-dwg "C:/cad/test/original.dwg" --working-copy-dwg "C:/cad/test_work/copy.dwg" --out-dir outputs/zwcad_copy_validation_live
```

## 2. Copied DWG SaveAs validation

```powershell
python -X utf8 -m src.main zwcad-copy-saveas-validate --original-dwg "C:/cad/test/original.dwg" --working-copy-dwg "C:/cad/test_work/copy.dwg" --save-as-target "C:/cad/test_work/result.dwg" --out-dir outputs/zwcad_copy_saveas_validation_live --overwrite-copy
```

## 3. C:/xicad allowlist validation

```powershell
python -X utf8 -m src.main xicad-policy-candidates --xicad-root C:/xicad --out-dir outputs/xicad_policy_candidates_verify
```

## 4. Phase 12 candidate guard

```powershell
python -X utf8 -m src.main hscad-analysis-phase12-manual-live-candidate --workspace outputs/phase10_11_domain_copy_verify --alias WAL --manual-live-flag --operator-approved --out-dir outputs/phase12_manual_live_candidate_verify
```

## Must remain true

- original DWG is not mutated
- copied DWG is used
- execution_allowed false
- sendcommand_allowed false
- final runner not implemented
