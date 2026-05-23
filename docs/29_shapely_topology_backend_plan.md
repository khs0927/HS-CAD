# 29. Shapely Topology Backend Plan

This document defines PR #6: optional Shapely/GEOS topology analysis for HS-CAD.

## Goal

Use Shapely as an optional evidence-producing backend for CAD vector topology.

Shapely must not become a hard dependency. If Shapely is missing, the pipeline must keep running and produce a structured `unavailable` result.

## Why Shapely first

Shapely is the most useful first open-source backend because it provides mature GEOS-backed operations for:

```text
polygonize
linemerge
unary_union
area
bounds
contains/touches/intersects
future STRtree spatial index
future snap/line_merge cleanup
```

## Scope of this PR

This PR adds:

```text
src/spatial/shapely_topology.py
src/app/shapely_topology_cli.py
tests/test_shapely_topology.py
```

Output:

```text
SHAPELY_TOPOLOGY.json
```

Command:

```powershell
python -X utf8 -m src.main hscad-shapely-topology --workspace outputs\webhard_batch_100
```

## Behavior

If Shapely is installed:

```text
fileized LINE/POLYLINE/HATCH boundary linework
-> Shapely LineString
-> unary_union
-> linemerge
-> polygonize
-> polygon candidates
```

If Shapely is not installed:

```json
{
  "backend": "shapely_topology",
  "status": "unavailable",
  "reason": "shapely not installed"
}
```

## Cross-validation integration

`hscad-cross-validate` reads `SHAPELY_TOPOLOGY.json` and adds this signal when polygon candidates exist:

```text
shapely_polygonize_area
```

This does not override HS-CAD area elements. It only adds additional evidence to the fusion/cross-validation score.

## Validation

Run:

```powershell
python -m pytest tests/test_shapely_topology.py tests/test_cross_validation.py -q
python -X utf8 -m src.main hscad-shapely-topology --workspace outputs\webhard_batch_100
python -X utf8 -m src.main hscad-cross-validate --workspace outputs\webhard_batch_100
```

Expected files:

```text
outputs\webhard_batch_100\SHAPELY_TOPOLOGY.json
outputs\webhard_batch_100\CROSS_VALIDATION.json
```

## Future PRs

Later Shapely expansion should add:

```text
STRtree
snap
polygonize_full
make_valid
area similarity matching between HS-CAD area elements and Shapely polygons
layer-aware polygon filtering
```
