# 24. Codex Route Plan Validation Guide

Use this guide on a Windows machine with the PR branch checked out.

## 1. Checkout PR branch

```powershell
git fetch origin pull/3/head:pr-3-corpus-foundation
git switch pr-3-corpus-foundation
python -m pip install -r requirements.txt
python -m pip install pytest requests
```

## 2. Run fast unit tests first

```powershell
python -m pytest tests/test_route_defaults.py tests/test_task_router.py tests/test_route_plan_writer.py tests/test_large_dwg_strategy.py tests/test_open_tools_catalog.py -q
```

Expected result: all tests pass.

## 3. Generate a route plan for the Webhard DWG corpus

```powershell
python -m src.main hscad-route-plan "웹하드 도면을 샘플 분석해줘" --source "Z:\내 드라이브\#웹하드\sample.dwg" --sample 20 --limit 20 --out-dir "outputs\codex_route_plan"
```

If the sample DWG path does not exist, replace it with any real DWG under:

```text
Z:\내 드라이브\#웹하드
```

Review these files:

```text
outputs\codex_route_plan\task_route.json
outputs\codex_route_plan\task_route.md
outputs\codex_route_plan\task_route_review.ps1
```

Confirm that the route uses:

```text
zwcad_saveas_dxf_ezdxf
```

and does not use Python COM ModelSpace bulk iteration as the default.

## 4. Run the generated review script only after inspection

The PowerShell file is a review artifact. Inspect it first.

```powershell
Get-Content outputs\codex_route_plan\task_route_review.ps1
```

If the source root and workspace look correct, run the commands manually step by step instead of blindly executing the file.

## 5. Real ZWCAD test for DWG conversion

After route plan validation, run a real 1 to 5 file sample:

```powershell
python -m src.main corpus-run prepare --root "Z:\내 드라이브\#웹하드" --workspace "outputs\webhard_real_sample" --sample 5
python -m src.main corpus-run fileize --workspace "outputs\webhard_real_sample" --limit 5
python -m src.main corpus-run validate --workspace "outputs\webhard_real_sample"
python -m src.main corpus-run index --workspace "outputs\webhard_real_sample"
python -m src.main corpus-run learn --workspace "outputs\webhard_real_sample"
python -m src.main corpus-run quality --workspace "outputs\webhard_real_sample"
python -m src.main corpus-run report --workspace "outputs\webhard_real_sample"
```

Check:

```text
outputs\webhard_real_sample\QUALITY_AUDIT.md
outputs\webhard_real_sample\FINAL_REPORT.md
outputs\webhard_real_sample\failures
outputs\webhard_real_sample\tmp\dxf
```

## Pass criteria

- DWG records use `zwcad_saveas_dxf_ezdxf`.
- Temporary DXF files are created under the workspace.
- `validate` succeeds.
- `quality` and `report` files are created.
- Any failures are captured as JSON instead of crashing the run.
