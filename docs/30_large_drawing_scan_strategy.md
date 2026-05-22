# Large Drawing Scan Strategy

HS-CAD should not use Python COM full ModelSpace scans as the default path for
large production DWGs. COM remains useful for connection, save, small targeted
edits, and fallback debugging, but repeated full scans create one cross-process
call per object property.

## Default Workflow

1. `fast-scan --active`
   Read drawing name, path, object count, layers, block definitions, title-block
   candidates, and a scan strategy recommendation.
2. `audit-native --active`
   Run AutoLISP inside ZWCAD to count entities, layers, blocks, texts, and
   dimensions without walking every object through Python COM.
3. `index-dxf`
   When repeated whole-drawing queries are needed, convert a DWG copy to DXF
   with ODA File Converter and build a SQLite analysis cache through `ezdxf`.
4. `query-index`
   Query the offline cache for AI planning and review.
5. Targeted execution
   Modify the source DWG through ZWCAD COM, PyRx, or XiCAD Safe Bridge by
   handle, layer, selection, or bounded window.

## COM Scan Modes

- `minimal`: handle, object name, entity type, and layer.
- `index`: minimal data plus bounding box, text preview, and block name where
  cheap enough to read.
- `full`: legacy detailed extraction. This is heavy and requires explicit
  `--confirm-heavy` on drawings above 20,000 objects.

## Object Count Guidance

| Object count | Recommended strategy |
| ---: | --- |
| 0-5,000 | COM minimal/index is acceptable. |
| 5,000-20,000 | Fast scan plus targeted COM access. |
| 20,000-100,000 | Native LISP audit and DXF index first. |
| 100,000+ | Avoid COM full scan; use native audit, offline index, and targeted execution. |

## Commands

```powershell
python -m src.main fast-scan --active --out generated/fast_scan_report.json
python -m src.main audit-native --active --out generated/native_audit.json
python -m src.main index-dxf --dwg "C:/cad/sample.dwg" --out generated/index.sqlite
python -m src.main query-index --where "layer='WAL1' and type='LWPOLYLINE'"
python -m src.main scan --dwg "C:/cad/sample.dwg" --mode minimal
python -m src.main scan --dwg "C:/cad/sample.dwg" --mode index
python -m src.main scan --dwg "C:/cad/sample.dwg" --mode full --confirm-heavy
python -m src.main scan-layer --active --layer WAL1 --types LINE,LWPOLYLINE
python -m src.main scan-window --active --bbox "0,0,10000,8000" --types LINE,LWPOLYLINE,TEXT
python -m src.main scan-selection --active --out generated/selection.json
```

DXF indexes are analysis caches only. Final mutations must still be applied to
the source DWG through the ZWCAD/PyRx/XiCAD execution path.
