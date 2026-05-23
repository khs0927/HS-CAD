# 26. HS-CAD Open Source Integration Framework

HS-CAD should not reimplement mature open-source geometry, OCR, layout, graph, and BIM systems from scratch. The project should absorb them through stable adapters while keeping deterministic fallbacks.

## Principle

```text
HS-CAD core schema and pipeline stay stable.
External projects are optional backends.
Every backend must have:
- capability detection
- deterministic fallback
- version/license notes
- isolated adapter
- JSON output contract
- validation TODO
```

## Integration layers

### Layer 1. CAD vector geometry

Primary tools:

- ezdxf
- Shapely / GEOS
- cad-to-shapely pattern references

Use for:

- DXF entity extraction
- polygonize linework
- line merge
- snapping broken endpoints
- STRtree spatial indexing
- accurate area/intersection/touch/within operations

HS-CAD status:

- ezdxf already in PR #3/PR #4
- pure-Python fallback exists
- Shapely backend should be PR #5

### Layer 2. Spatial graph / knowledge graph

Primary tools:

- NetworkX
- rustworkx, optional future high-performance graph backend

Use for:

- room/area nodes
- text label nodes
- block/equipment nodes
- leader/dimension nodes
- adjacency edges
- contains/inside/touches/near/connects_to relationships

HS-CAD status:

- not yet added
- graph JSON contract should come before NetworkX hard dependency

### Layer 3. Analytical storage

Primary tools:

- DuckDB
- DuckDB Spatial
- GeoParquet / Arrow in future

Use for:

- fast querying over many drawings
- large corpus statistics
- spatial SQL exports
- area schedules and object tables

HS-CAD status:

- SQLite corpus index exists
- DuckDB should be optional analytical export, not a replacement yet

### Layer 4. Image/PDF floorplan vision

Primary tools:

- OpenCV
- scikit-image optional
- SAM/FloorSAM-style future adapters

Use for:

- PDF/image contour extraction
- raster floorplan segmentation
- wall/room boundary recovery when vector data is missing

HS-CAD status:

- image metadata fileizer exists
- vision backend should be optional and isolated from CAD-vector inference

### Layer 5. OCR and document layout

Primary tools:

- PaddleOCR / PP-Structure
- LayoutParser
- Table Transformer / PubTables-style model patterns
- img2table style table extraction patterns

Use for:

- title block extraction
- table cell text
- general note tables
- scanned PDF/image text recognition

HS-CAD status:

- text role inference foundation exists
- OCR/layout backends should enrich evidence, not override CAD text blindly

### Layer 6. BIM / IFC / collaboration

Primary tools:

- IfcOpenShell
- Speckle
- FreeCAD/Bonsai ecosystem references

Use for:

- IFC property extraction
- BIM object relationships
- CAD-to-BIM bridge
- object streaming/versioning in later phases

HS-CAD status:

- out of PR #4 scope
- should be a separate BIM branch after spatial graph stabilizes

## Backend contract

Every adapter should expose:

```python
class BackendAdapter:
    backend_id: str
    capability: str

    def is_available(self) -> tuple[bool, str]: ...
    def describe(self) -> dict: ...
```

Backend outputs must be JSON-serializable and evidence-backed.

## Conflict prevention rules

1. Do not make Shapely, NetworkX, DuckDB, OpenCV, OCR, or IFC mandatory in core pipeline.
2. Keep pure-Python fallback for fileized JSON analysis.
3. Add new backends behind a registry and CLI discovery command.
4. Do not mutate drawings from analysis backends.
5. Record source backend in every derived artifact.
6. Any AI/LLM interpretation must cite deterministic evidence fields.

## Recommended PR sequence

### PR #4 current

- pure-Python spatial containment
- boundary candidates
- text role inference
- area element inference
- integration framework registry

### PR #5

- Shapely optional backend
- STRtree index
- polygonize / polygonize_full
- snap / line_merge

### PR #6

- graph JSON exporter
- optional NetworkX backend
- adjacency and contains graph

### PR #7

- DuckDB analytical export
- optional DuckDB Spatial

### PR #8

- OCR/layout adapters
- PaddleOCR/PP-Structure/LayoutParser style adapters
- table/title block extraction enrichment

### PR #9

- IFC/BIM adapters
- IfcOpenShell bridge
- Speckle export experiment
