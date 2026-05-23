# 28. Open Source Fusion and Cross-Validation Process

This document defines how HS-CAD should integrate mature open-source tools without breaking the core drawing analysis system.

## Core direction

HS-CAD must stay analysis-first.

Drawing automation with XiCAD, ArchiOffice, HSS, LISP, AutoCAD, ZWCAD, and GstarCAD workflows should come after the drawing analysis engine is stable.

The analysis engine must use mature open-source projects through optional adapters, not as hard dependencies.

## Integration principle

```text
HS-CAD Core
  - fileized JSON schema
  - corpus index
  - layer/text/area/graph outputs
  - evidence/confidence/audit schema

Open-source tools
  - optional backend
  - adapter contract
  - capability detection
  - fallback path
  - cross-validation signal
```

## Open-source families and roles

### 1. DWG/DXF vector parsing

Tools:

```text
ezdxf
ODA File Converter
LibreDWG candidate
AutoCAD/ZWCAD/GstarCAD/BricsCAD SaveAs fallback
```

Role:

```text
DWG -> DXF conversion
DXF entity extraction
layer/entity/text/block/dimension/hatch parsing
```

HS-CAD policy:

```text
Prefer ODA -> DXF -> ezdxf for corpus analysis.
Use CAD COM/SendCommand only as fallback.
Do not use ModelSpace COM full scan as the default.
```

### 2. Vector geometry and topology

Tools:

```text
Shapely / GEOS
```

Role:

```text
area
contains/touches/intersects
STRtree spatial index
polygonize / polygonize_full
snap / line_merge
make_valid / buffer(0)
```

HS-CAD policy:

```text
Use Shapely as optional backend.
Keep pure-Python fallback.
Record spatial_backend in all results.
```

### 3. Graph analysis

Tools:

```text
NetworkX
```

Role:

```text
connected components
isolated text
unlabeled areas
orphan layers
relationship quality audit
Graph RAG preparation
```

HS-CAD policy:

```text
Keep SPATIAL_GRAPH.json as stable contract.
NetworkX is optional analysis backend only.
```

### 4. Analytical storage

Tools:

```text
DuckDB
DuckDB Spatial
Parquet / Arrow future option
```

Role:

```text
large corpus layer statistics
area schedules
object distribution
project comparison
fast SQL aggregation
```

HS-CAD policy:

```text
SQLite remains basic corpus index.
DuckDB is optional analytical export.
```

### 5. Raster/PDF/image analysis

Tools:

```text
OpenCV
scikit-image candidate
PyMuPDF rasterization
```

Role:

```text
image/PDF contour extraction
connected components
table line detection
raster area candidates
vector-vs-raster cross-check
```

HS-CAD policy:

```text
Do not replace vector CAD results.
Use as evidence when vector data is missing or suspicious.
```

### 6. OCR and document layout

Tools:

```text
PaddleOCR / PP-Structure / PaddleOCR-VL
PP-DocLayout
LayoutParser
Table Transformer-style adapters
```

Role:

```text
scanned text extraction
title block recognition
table detection and cell structure
general note extraction
OCR cross-check against CAD TEXT/MTEXT
```

HS-CAD policy:

```text
OCR/layout backends enrich evidence.
They do not override CAD vector text without agreement scoring.
```

### 7. BIM / IFC / collaboration

Tools:

```text
IfcOpenShell
Speckle candidate
FreeCAD/Bonsai ecosystem references
```

Role:

```text
IFC object extraction
BIM property comparison
2D CAD vs BIM consistency review
```

HS-CAD policy:

```text
Keep separate BIM branch until 2D drawing analysis stabilizes.
```

## Cross-validation matrix

### Area element validation

Signals:

```text
closed_polyline_area
line_loop_area
arc_segment_loop_area
hatch_boundary_area
shapely_polygonize_area
opencv_contour_area
room_label_inside
layer_semantic_support
```

Expected output:

```json
{
  "target_type": "area",
  "target_id": "area:file:P1",
  "agreement_score": 0.92,
  "confidence": 0.88,
  "signals": []
}
```

### Text role validation

Signals:

```text
CAD TEXT/MTEXT position
boundary containment
not inside table region
titleblock exclusion
OCR match
leader proximity
layer semantic support
```

### Layer semantic validation

Signals:

```text
layer name pattern
entity type distribution
color distribution
linetype distribution
block names
text samples
spatial graph connections
manual review corrections, later only
```

### Graph relationship validation

Signals:

```text
area has label
text assigned to layer
area assigned to layer
orphan text count
unlabeled area count
isolated component count
```

## Customization strategy

Open-source tools should be customized by adapters, not by modifying upstream code.

Recommended customizations:

```text
ezdxf adapter: normalize entity schema for HS-CAD
Shapely adapter: convert fileized JSON boundaries to GEOS geometries
NetworkX adapter: load SPATIAL_GRAPH.json into graph object
DuckDB exporter: materialize HS-CAD JSON artifacts into SQL tables
OpenCV adapter: convert PDF/image pages to contour candidates
OCR/layout adapter: normalize output to text/table/titleblock evidence
```

Avoid:

```text
forking upstream projects unless necessary
hardcoding one company layer standard
making optional libraries mandatory
letting OCR override CAD vector evidence alone
mutating original DWG during analysis
```

## Development process

Every new open-source integration must follow this order:

```text
1. Identify target analysis problem.
2. Select open-source candidate.
3. Define HS-CAD adapter contract.
4. Add capability detection.
5. Keep fallback behavior.
6. Normalize output schema.
7. Add cross-validation signals.
8. Add confidence and evidence.
9. Add audit outputs.
10. Add CLI.
11. Add tests.
12. Add validation TODO.
13. Validate on Webhard corpus.
14. Record false positives and false negatives.
15. Only then add project/company calibration.
```

## Recommended next PRs

```text
PR #6: Shapely topology backend expansion
PR #7: NetworkX graph audit backend
PR #8: DuckDB analytical export
PR #9: OpenCV raster/PDF backend
PR #10: OCR/layout backend
PR #11: IFC/BIM backend
```

## Current PR #5 scope

PR #5 should include only:

```text
CAD platform compatibility discovery
vendor-neutral layer semantics
layer audit
layer-aware graph
open-source fusion matrix
cross-validation foundation
```

Company-specific profile learning remains deferred until real Webhard drawings are reviewed.
