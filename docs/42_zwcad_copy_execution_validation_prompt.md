# Validation prompt for ZWCAD copy execution validation

Repository:
khs0927/HS-CAD

Branch:
exp/zwcad-copy-execution-validation

Base:
exp/domain-rule-safe-execution-harness

Goal:
Validate that HS-CAD can safely use ZWCAD COM against copied DWG files only.

Rules:
- Do not modify original DWG.
- Do not use production DWG directly unless copied.
- Do not commit outputs.
- Tests must pass without ZWCAD using FakeAdapter.
- Live ZWCAD validation is optional.

Commands:

git fetch origin exp/zwcad-copy-execution-validation
git switch exp/zwcad-copy-execution-validation

python -X utf8 -m pytest -q tests/test_zwcad_copy_execution_validation.py

python -X utf8 -m pytest -q

python -X utf8 -m src.main --help

Confirm CLI:
- zwcad-copy-scan-validate
- zwcad-copy-saveas-validate

Optional live ZWCAD copy scan test:
Only run if ZWCAD is installed and a safe copied test DWG is available.

python -X utf8 -m src.main zwcad-copy-scan-validate --original-dwg "C:/cad/test/original.dwg" --working-copy-dwg "C:/cad/test_work/copy.dwg" --out-dir outputs/zwcad_copy_validation_live

Optional live SaveAs test:
Only run on safe copied test DWG.

python -X utf8 -m src.main zwcad-copy-saveas-validate --original-dwg "C:/cad/test/original.dwg" --working-copy-dwg "C:/cad/test_work/copy.dwg" --save-as-target "C:/cad/test_work/result.dwg" --out-dir outputs/zwcad_copy_saveas_validation_live --overwrite-copy

Confirm artifacts:
- COPY_MANIFEST.json
- BEFORE_SCAN.json
- AFTER_SCAN.json if SaveAs test
- DELTA_REPORT.json if SaveAs test
- EXECUTION_AUDIT_LOG.json

Confirm:
- original_dwg_mutation_allowed=false
- copy_hash_matches_original=true before SaveAs
- original path and working copy path are different
- original path and save_as_target are different
- no outputs or DWG files are committed

Report:
- Branch/commit tested
- Unit test result
- Full pytest result
- CLI registration result
- Optional live ZWCAD result
- Artifact verification result
- Failures
- Patch required
- PR readiness
