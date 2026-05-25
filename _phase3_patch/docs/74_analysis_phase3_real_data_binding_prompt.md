# HS-CAD Phase 3 Real Data Binding Validation Prompt

## Goal
Validate Phase 3 real-data binding between Phase 1/2 analysis artifacts and the Phase 2 export/reporting layer.

## Apply patch ZIP
Save the ZIP under:

```text
C:\Users\user\Downloads\HS-CAD-phase3-real-data-binding-patch.zip
```

Apply from the repository root:

```powershell
cd C:\CODE\HS-CAD
git fetch origin feat/analysis-phase2-data-extraction
git switch feat/analysis-phase2-data-extraction
git switch -c feat/analysis-phase3-real-data-binding
Expand-Archive -Path "C:\Users\user\Downloads\HS-CAD-phase3-real-data-binding-patch.zip" -DestinationPath ".\_phase3_patch" -Force
Copy-Item -Path ".\_phase3_patch\*" -Destination "." -Recurse -Force
```

Optional CLI registration in `src/main.py`:

```python
import src.app.analysis_phase3_cli  # noqa: F401,E402
```

If CLI registration is separated, do not modify `src/main.py`.

## Tests

```powershell
python -X utf8 -m pytest -q tests/test_analysis_phase3_real_data_binding.py
python -X utf8 -m src.main --help
```

Optional CLI smoke, only if CLI registration was added:

```powershell
python -X utf8 -m src.main hscad-analysis-phase3-bind --workspace outputs\webhard_batch_100 --out-dir outputs\phase3_real_data_binding_verify
```

Expected artifacts:

```text
PHASE3_REAL_DATA_BINDING_REPORT.json
PHASE3_REAL_DATA_BINDING_REPORT.md
PHASE3_ARTIFACT_COVERAGE.json
```

## Safety checks
Confirm:
- `source_mutation_allowed` is false
- `cad_execution_allowed` is false
- `zwcad_com_allowed` is false
- `xicad_alias_execution_allowed` is false
- outputs are not committed
- no DWG/DXF files are committed
