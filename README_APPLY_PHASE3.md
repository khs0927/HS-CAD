# HS-CAD Phase 3 Real Data Binding Patch

Save this ZIP as:

```text
C:\Users\user\Downloads\HS-CAD-phase3-real-data-binding-patch.zip
```

Apply from repository root:

```powershell
cd C:\CODE\HS-CAD
git fetch origin feat/analysis-phase2-data-extraction
git switch feat/analysis-phase2-data-extraction
git switch -c feat/analysis-phase3-real-data-binding
Expand-Archive -Path "C:\Users\user\Downloads\HS-CAD-phase3-real-data-binding-patch.zip" -DestinationPath ".\_phase3_patch" -Force
Copy-Item -Path ".\_phase3_patch\*" -Destination "." -Recurse -Force
```

Test:

```powershell
python -X utf8 -m pytest -q tests/test_analysis_phase3_real_data_binding.py
python -X utf8 -m src.main --help
```
