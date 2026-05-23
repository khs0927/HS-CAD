# HS-CAD isolated code roadmap

This document records why several currently unreferenced modules are kept in the
repository and what should happen to them next.

The files listed here were detected during PR verification as modules that exist
but are not yet imported by production code or tests. They are not all dead code.
Most of them are staging points for HS-CAD's longer-term goal: avoiding expensive
Python COM full scans where possible, supporting multiple CAD backends, and
building evidence-rich drawing analysis from DWG, DXF, PDF, and raster inputs.

## Decision summary

| File | Current status | Decision | Intended integration |
|---|---|---|---|
| `src/adapters/pyrx_adapter.py` | Skeleton adapter | Keep as experimental backend | Future high-performance ZWCAD/PyRx path for large-object drawings |
| `src/adapters/pyzwcad_adapter.py` | Thin optional wrapper over COM adapter | Keep as compatibility shim for now | Optional pyzwcad-assisted COM workflow; remove only if no pyzwcad-specific value appears |
| `src/adapters/ezdxf_adapter.py` | Minimal DXF reader | Keep and later consolidate | Offline DXF fallback / evidence extraction for fileized drawings |
| `src/scanners/boundary_scanner.py` | Small pure helper | Keep and wire into audits | Closed polyline room/area/boundary candidate detection |
| `src/scanners/dimension_scanner.py` | Small pure helper | Keep and wire into audits | Dimension evidence extraction for scale and QA checks |
| `src/scanners/object_scanner.py` | Thin wrapper over `CADAdapter.scan_modelspace()` | Keep for orchestration boundary | Backend-neutral scan entry point for future registry/worker routing |

## Why these files should not be deleted yet

### 1. Large drawing workflows need non-COM escape hatches

HS-CAD has a recurring requirement to process drawings with many objects. A full
Python COM scan is useful as a baseline, but it can be slow, brittle, and tied to
an active Windows CAD session. The project therefore keeps alternative adapter
slots:

- `pyrx_adapter.py` for a future PyRx/cad-pyrx or ZRX-level backend.
- `pyzwcad_adapter.py` for optional pyzwcad helpers while preserving the robust
  COM fallback.
- `ezdxf_adapter.py` for offline DXF reads when a drawing can be exported or
  fileized without an active CAD session.

These are backend options, not active default paths.

### 2. The scanner helpers match planned evidence pipelines

The scanner modules are small and pure. They match future report/evidence needs:

- boundary candidates support room, area, wall-loop, and closed-polyline QA.
- dimension extraction supports scale inference, missing-dimension checks, and
  OCR/CAD cross-validation.
- object scanning gives orchestration code a neutral function that can accept any
  `CADAdapter` implementation.

These should eventually feed `analyze-architecture`, worker outputs, or a drawing
evidence package rather than being imported only ad hoc.

### 3. The project is currently branch-stacked

Several PRs are layered on top of each other. Some modules are intentionally ahead
of their integration points. Deleting them now would create churn and may remove
planned hooks for PRs that add OCR/vector/text fusion, worker manifests, or PDF
raster analysis.

## Next actions

### Safe immediate actions

1. Add import-safety tests for currently isolated modules.
2. Keep the modules side-effect free and dependency-lazy.
3. Document their status here so future reviewers do not delete them as accidental
   leftovers.

### Future integration PRs

1. **Scanner integration PR**
   - Add boundary and dimension scanner outputs to `analyze-architecture` or a
     dedicated evidence worker.
   - Add tests using small synthetic object dictionaries.

2. **Backend registry PR**
   - Add adapter capability metadata for COM, PyRx, pyzwcad, and ezdxf.
   - Keep COM as default.
   - Mark PyRx and pyzwcad as experimental/optional.
   - Use ezdxf as an offline DXF inspection fallback.

3. **Cleanup PR after integration decision**
   - Remove `pyzwcad_adapter.py` only if no pyzwcad-specific helpers are added.
   - Keep `pyrx_adapter.py` only if the project still targets ZWCAD 2025/2026
     high-performance local automation.
   - Merge `ezdxf_adapter.py` into the fileizer layer if it duplicates a mature
     DXF fileizer.

## Current policy

Do not delete these files in broad cleanup PRs. Either:

- wire them into a tested workflow,
- explicitly archive them with a replacement path, or
- remove them in a dedicated cleanup PR with rationale.
