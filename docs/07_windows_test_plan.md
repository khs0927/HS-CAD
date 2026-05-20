# Windows + ZWCAD Test Plan

## 1. Basic environment

```powershell
python -m src.main --help
python -m pytest
```

## 2. ZWCAD COM connection

```powershell
python -m src.main connect
```

## 3. Drawing scan

```powershell
python -m src.main scan --dwg "C:/cad/sample.dwg" --out "outputs/objects.json"
python -m src.main layers --dwg "C:/cad/sample.dwg"
python -m src.main blocks --dwg "C:/cad/sample.dwg"
python -m src.main texts --dwg "C:/cad/sample.dwg"
```

## 4. Safe mutation on a copy

```powershell
python -m src.main run-command --dwg "C:/cad/sample_copy.dwg" --command "examples/commands/move_layer.json" --execute --save-as "C:/cad/sample_modified.dwg"
```

## 5. Architecture audit

```powershell
python -m src.main analyze-architecture --dwg "C:/cad/sample.dwg" --out-dir "outputs/architecture_report"
```

## 6. XiCAD

```powershell
python -m src.main detect-xicad --xicad-root "C:/xicad"
python -m src.main xicad-catalog --xicad-root "C:/xicad"
python -m src.main load-xicad --dwg "C:/cad/sample.dwg" --xicad-root "C:/xicad"
python -m src.main run-xicad --dwg "C:/cad/sample.dwg" --xicad-root "C:/xicad" --load-first --alias WAL
```

XiCAD commands can be interactive. Confirm the ZWCAD command line prompts and document each alias flow.
