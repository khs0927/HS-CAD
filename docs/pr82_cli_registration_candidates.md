# PR82 CLI Registration Candidates

Date: 2026-05-26

## Status

This is a docs-only candidate record derived from PR #94. PR #94 added or modified `src/app/**` modules directly, so it is not merged as part of the PR82 source-only extraction sequence.

CLI registration remains pending. This document preserves the candidate commands and contracts for a later dedicated implementation PR.

## Safety Boundary

- `src/main.py` is not modified.
- `config/worker_manifest.json` is not modified.
- Live runner commands are not registered.
- CAD execution is not enabled.
- SendCommand remains disabled.
- SaveAs remains disabled.
- DXFOUT remains disabled.
- XiCAD alias execution remains disabled.
- Original DWG mutation remains forbidden.

## Candidate Modules From PR #94

| Candidate file | Candidate area | Status |
| --- | --- | --- |
| `src/app/open_backends_cli.py` | Open backend discovery | Candidate only |
| `src/app/cad_platforms_cli.py` | CAD platform discovery | Candidate only |
| `src/app/layer_analysis_cli.py` | Layer semantics analysis | Candidate only |
| `src/app/layer_audit_cli.py` | Layer audit | Candidate only |
| `src/app/text_roles_cli.py` | Text role inference and area inference | Candidate only |
| `src/app/spatial_cli.py` | Spatial containment | Candidate only |
| `src/app/spatial_graph_cli.py` | Spatial graph export | Candidate only |
| `src/app/shapely_topology_cli.py` | Shapely topology | Candidate only |
| `src/app/shapely_topology_audit_cli.py` | Shapely topology audit | Candidate only |
| `src/app/shapely_area_match_cli.py` | Shapely area matching | Candidate only |
| `src/app/fusion_matrix_cli.py` | Fusion matrix | Candidate only |
| `src/app/cross_validate_cli.py` | Cross validation | Candidate only |
| `src/app/worker_cli.py` | Worker runner shell | Candidate only |
| `src/app/analysis_shortcut_cli.py` | Shortcut routing updates | Candidate only |
| `src/app/__init__.py` | App package exports | Candidate only |

## Candidate Command Groups

### PDF Raster

Potential command group: `pdf-raster`

Input contract:

```json
{
  "workspace": "outputs/sample_workspace",
  "dpi": 180,
  "max_pages": 3
}
```

Output contract:

```json
{
  "artifacts": [
    "PDF_COORDINATE_CONTRACT.json",
    "PDF_VECTOR_OBJECTS.json",
    "RASTER_CONTOURS.json",
    "PDF_VECTOR_RASTER_IOU.json",
    "RASTER_CONTOUR_CLASSES.json",
    "PDF_RASTER_ANALYSIS.json"
  ]
}
```

Implementation status: source and direct worker tests landed through PR #89. CLI registration pending.

### OCR and Text Review

Potential command groups:

- `ocr-text-region`
- `ocr-vector-text-match`
- `ocr-cad-text-match`
- `text-evidence-fusion`
- `text-review-queue`
- `text-corrections-export`
- `text-corrections-apply`
- `text-calibration-report`
- `text-weight-suggestions`

Input contract:

```json
{
  "workspace": "outputs/sample_workspace",
  "max_images": 20,
  "include_all": false
}
```

Output contract:

```json
{
  "artifacts": [
    "OCR_TEXT_REGIONS.json",
    "OCR_VECTOR_TEXT_MATCHES.json",
    "OCR_CAD_TEXT_MATCHES.json",
    "TEXT_EVIDENCE_FUSION.json",
    "TEXT_REVIEW_QUEUE.json",
    "TEXT_CORRECTIONS_TEMPLATE.json",
    "TEXT_CORRECTIONS_APPLIED.json",
    "TEXT_CALIBRATION_REPORT.json",
    "TEXT_FUSION_WEIGHT_SUGGESTIONS.json"
  ]
}
```

Implementation status: source and direct worker tests landed through PR #93. CLI registration pending.

### NetworkX Graph Audit

Potential command group: `networkx-graph-audit`

Input contract:

```json
{
  "workspace": "outputs/sample_workspace",
  "input": "SPATIAL_GRAPH.json"
}
```

Output contract:

```json
{
  "artifacts": [
    "GRAPH_AUDIT.json",
    "GRAPH_AUDIT.md"
  ]
}
```

Implementation status: source and direct worker tests landed through PR #96. CLI registration pending.

### DuckDB Analytics

Potential command group: `duckdb-export`

Input contract:

```json
{
  "workspace": "outputs/sample_workspace"
}
```

Output contract:

```json
{
  "artifacts": [
    "DUCKDB_EXPORT.json",
    "DUCKDB_EXPORT_REPORT.md",
    "hscad_analysis.duckdb",
    "analytics/*.parquet"
  ]
}
```

Implementation status: source and direct worker tests landed through PR #97. CLI registration pending.

## Future Implementation Rules

A later CLI registration PR may modify app registration files only after these checks pass:

1. The command is registered without enabling live CAD execution.
2. `src/main.py --help` succeeds.
3. Focused CLI smoke tests are added.
4. `config/worker_manifest.json` changes, if needed, are handled in a separate manifest PR.
5. Runtime artifacts remain ignored and uncommitted.

## Validation Basis

Current source modules have been validated by direct worker or focused tests, not by CLI registration:

- PDF Raster: PR #89
- OCR Tools: PR #93
- NetworkX Graph Audit: PR #96
- DuckDB Analytics: PR #97

## Decision

PR #94 direct merge: NO.

Use this document as the handoff for a future, narrow CLI registration implementation PR.
