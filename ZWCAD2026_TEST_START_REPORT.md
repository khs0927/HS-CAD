# ZWCAD 2026 Test Start Package Report

## Added

- `src/testing/environment_check.py`: Python/package/path/ZWCAD COM/XiCAD environment diagnostics.
- `tools/verify_zwcad2026_environment.py`: standalone environment check tool.
- `tools/run_zwcad2026_test_plan.py`: safe real-DWG smoke test runner.
- `scripts/01_setup_venv.ps1`: Windows venv and requirements setup.
- `scripts/02_check_zwcad2026.ps1`: environment check wrapper.
- `scripts/03_run_safe_test_plan.ps1`: full safe test plan wrapper.
- `scripts/04_run_cli_smoke.ps1`: CLI smoke workflow wrapper.
- `docs/14_zwcad_2026_test_start_guide.md`: full ZWCAD 2026 start guide.
- `docs/15_zwcad_2026_troubleshooting.md`: troubleshooting guide.
- `tests/test_environment_check.py`: environment checker unit tests.
- `tests/test_tools_help.py`: tool CLI help tests.

## Verified without ZWCAD

```text
python -m src.main --help                         OK
python -m src.main env-check --help               OK
python tools/verify_zwcad2026_environment.py --help OK
python tools/run_zwcad2026_test_plan.py --help    OK
python -m pytest -q                               37 passed, 1 skipped
```

## First Windows Commands

```powershell
cd zwcad-ai-modifier
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\01_setup_venv.ps1
.\.venv\Scripts\Activate.ps1
python -m src.main env-check --start-zwcad --out-dir outputs/zwcad2026_env_check
```

## First DWG Test

```powershell
python -m src.main scan --dwg "C:/cad-test/sample.dwg" --out outputs/objects.json
python -m src.main classify-objects --dwg "C:/cad-test/sample.dwg" --out outputs/object_semantics.json
python -m src.main analyze-architecture --dwg "C:/cad-test/sample.dwg" --out-dir outputs/architecture_report
```

## Safe Full Plan

```powershell
python tools/run_zwcad2026_test_plan.py --dwg "C:/cad-test/sample.dwg" --xicad-root "C:/xicad" --start-zwcad --out-dir outputs/zwcad2026_test_plan
```

## Minimal Modify Smoke Test

This copies the DWG first and only edits the copy.

```powershell
python tools/run_zwcad2026_test_plan.py --dwg "C:/cad-test/sample.dwg" --start-zwcad --execute-smoke --move-layer MARK --dx 0 --dy 0
```
