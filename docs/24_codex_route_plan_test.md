# 24. Codex Route Plan Validation Guide

Use this guide on a Windows machine with the PR branch checked out.

## 1. Checkout PR branch

```powershell
git fetch origin pull/3/head:pr-3-corpus-foundation
git switch pr-3-corpus-foundation
git reset --hard FETCH_HEAD
python -m pip install -r requirements.txt
python -m pip install pytest requests
```

## 2. Run fast unit tests first

```powershell
python -m pytest tests/test_route_defaults.py tests/test_task_router.py tests/test_route_plan_writer.py tests/test_large_dwg_strategy.py tests/test_open_tools_catalog.py tests/test_encoding_and_webhard_cli.py tests/test_dwg_dxf_fileizer_errors.py tests/test_oda_converter_adapter.py tests/test_run_result_summarizer.py tests/test_batch_runner.py -q
```

Expected result: all tests pass.

## 3. Check external converter discovery

```powershell
python -X utf8 -m src.main hscad-converters --probe
```

If ODA File Converter is installed in a non-standard location, set:

```powershell
$env:ODA_FILE_CONVERTER="C:\Path\To\ODAFileConverter.exe"
python -X utf8 -m src.main hscad-converters --probe
```

The DWG fileizer now tries ODA File Converter before ZWCAD COM when the executable is available.

## 4. Generate a route plan for the Webhard DWG corpus

Set UTF-8 first:

```powershell
chcp 65001
$env:PYTHONIOENCODING="utf-8"
```

Then generate the plan:

```powershell
python -X utf8 -m src.main hscad-route-plan "웹하드 도면을 샘플 분석해줘" --source "Z:\내 드라이브\#웹하드\sample.dwg" --sample 20 --limit 20 --out-dir "outputs\codex_route_plan"
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

## 5. Safer Webhard sample command

If PowerShell still has Korean path quoting or output encoding issues, use the dedicated command below. It assembles this path inside Python instead of receiving it from the shell:

```text
Z:/내 드라이브/#웹하드
```

Run:

```powershell
python -X utf8 -m src.main hscad-webhard-sample --drive "Z:/" --workspace "outputs\webhard_real_sample" --sample 5 --limit 5
```

This runs:

```text
prepare -> fileize -> validate -> index -> learn -> quality -> report
```

and writes:

```text
outputs\webhard_real_sample\webhard_sample_run.json
```

## 6. Resumable Webhard batch command

After the 5-file sample is stable, use batches. This avoids one huge run and lets the process resume safely.

First 100-file manifest, one 50-file batch:

```powershell
python -X utf8 -m src.main hscad-webhard-batch --drive "Z:/" --workspace "outputs\webhard_batch_100" --sample 100 --batch-size 50 --max-batches 1 --start-offset 0
```

Second 50-file batch using the same manifest:

```powershell
python -X utf8 -m src.main hscad-webhard-batch --drive "Z:/" --workspace "outputs\webhard_batch_100" --sample 100 --batch-size 50 --max-batches 1 --start-offset 50 --no-prepare
```

Resume safely from the beginning without reprocessing successful JSON:

```powershell
python -X utf8 -m src.main hscad-webhard-batch --drive "Z:/" --workspace "outputs\webhard_batch_100" --sample 100 --batch-size 50 --max-batches 2 --start-offset 0 --skip-existing
```

Review:

```powershell
Get-Content -Encoding UTF8 outputs\webhard_batch_100\BATCH_RUN.json
Get-Content -Encoding UTF8 outputs\webhard_batch_100\RUN_SUMMARY.md
```

## 7. Run the generated review script only after inspection

The PowerShell file is a review artifact. Inspect it first.

```powershell
Get-Content -Encoding UTF8 outputs\codex_route_plan\task_route_review.ps1
```

If the source root and workspace look correct, run the commands manually step by step instead of blindly executing the file.

## 8. DWG conversion order and failure classification

The DWG fileizer now tries this order:

```text
1. ODA File Converter, if available
2. ZWCAD Documents.Open(staged_dwg)
3. If Open fails: SendCommand _.OPEN
4. SaveAs DXF using COM SaveAs format candidates
5. If SaveAs fails: SendCommand _.SAVEAS / _.DXFOUT candidates
```

If DWG conversion fails, inspect the failure JSON files:

```powershell
Get-ChildItem outputs\webhard_real_sample\failures -Filter *.json | Select-Object -First 5 | ForEach-Object { Get-Content -Encoding UTF8 $_.FullName }
```

Expected error types:

```text
open_document_failed
save_as_dxf_failed
fileize_failed
```

If ODA conversion succeeds, the fileized JSON should contain:

```text
"external_converter_used": true
```

and warnings should include:

```text
external_converter_used
```

If conversion succeeds after the ZWCAD command fallback, the fileized JSON should contain:

```text
"command_fallback_used": true
```

and warnings should include:

```text
zwcad_sendcommand_fallback_used
```

If `open_document_failed` still appears and ODA is unavailable, install/configure ODA File Converter or add a vendor batch conversion path.

## Pass criteria

- DWG records use `zwcad_saveas_dxf_ezdxf`.
- Temporary staged DWG files are created under the workspace.
- Temporary DXF files are created when any converter path succeeds.
- `validate` succeeds.
- `quality` and `report` files are created.
- Korean path/prompt output does not crash stdout/stderr.
- Any failures are captured as JSON instead of crashing the run.
- DWG failures are classified as `open_document_failed` or `save_as_dxf_failed` when possible.
- If external converter succeeds, `external_converter_used` is recorded.
- If ZWCAD fallback succeeds, `command_fallback_used` is recorded.
- Batch runs write `BATCH_RUN.json` and can resume with `--skip-existing`.
