# Real ZWCAD Validation Guide

## 1. Prepare

```powershell
cd zwcad-ai-modifier
python -m src.main --help
python -m pytest -q
```

Prepare a copied DWG file. Do not test on original project files.

## 2. COM connection

```powershell
python -m src.main connect
```

## 3. Scan

```powershell
python -m src.main scan --dwg "C:/cad/sample_copy.dwg" --out "outputs/objects.json"
python -m src.main layers --dwg "C:/cad/sample_copy.dwg"
python -m src.main blocks --dwg "C:/cad/sample_copy.dwg"
python -m src.main texts --dwg "C:/cad/sample_copy.dwg"
```

## 4. Architecture report

```powershell
python -m src.main analyze-architecture --dwg "C:/cad/sample_copy.dwg" --out-dir "outputs/architecture_report"
```

## 5. Safe mutation test

```powershell
python -m src.main run-command --dwg "C:/cad/sample_copy.dwg" --command "examples/commands/move_layer.json" --dry-run
python -m src.main run-command --dwg "C:/cad/sample_copy.dwg" --command "examples/commands/move_layer.json" --execute --save-as "C:/cad/sample_modified.dwg"
```

## 6. XiCAD

```powershell
python -m src.main detect-xicad --xicad-root "C:/xicad"
python -m src.main xicad-catalog --xicad-root "C:/xicad"
python -m src.main load-xicad --dwg "C:/cad/sample_copy.dwg" --xicad-root "C:/xicad"
python -m src.main run-xicad --dwg "C:/cad/sample_copy.dwg" --xicad-root "C:/xicad" --load-first --alias WAL
```

Most XiCAD commands are interactive. Complete the prompts in ZWCAD, then run a scan/report again.

## 7. Debug bundle

```powershell
python -m src.main collect-debug --dwg "C:/cad/sample_copy.dwg" --xicad-root "C:/xicad" --out-dir "outputs/debug_bundle"
```

Share the debug bundle when reporting issues.

## 8. Operational finish process

For the standard working flow, including GitHub synchronization, final text-in-cell verification, and XiCAD `TOA` left/center/right text alignment, follow:

- `docs/22_operational_sync_and_cad_finish_process.md`
