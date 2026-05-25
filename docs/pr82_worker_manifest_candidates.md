# PR82 Worker Manifest Candidates

Date: 2026-05-25

## Purpose

This document preserves `config/worker_manifest.json` candidates from PR82 without directly modifying the active worker manifest.

The PR82 manifest and current main manifest use different shapes. Direct replacement would be unsafe.

## Current main status

Latest checked main SHA:

```text
ff7bffc01c691e24909f72d0ea8cd600db620acd
```

Current main already has an active `config/worker_manifest.json` with implemented analysis/readiness workers. PR82 proposed a larger optional-backend manifest with a different schema.

## Candidate worker keys from PR82

```text
shapely_topology
networkx_graph_audit
duckdb_export
pdf_raster
ocr_text_region
ocr_vector_text_match
ocr_cad_text_match
text_evidence_fusion
text_review_queue
text_corrections_export
text_corrections_apply
text_calibration_report
text_weight_suggestions
analysis_core_megapack
analysis_graph_megapack
analysis_advanced_megapack
analysis_ops_megapack
analysis_automation_megapack
analysis_evidence_megapack
vision_layout
bim_projection
```

## Candidate registration policy

Each worker should be registered only after its source module, tests, and artifact contract are validated.

Do not merge PR82's manifest wholesale.

## Candidate mapping guidance

For current main's manifest style, prefer entries like:

```json
{
  "worker_name": {
    "module": "src.workers.<worker_module>",
    "callable": "run_worker",
    "status": "implemented",
    "description": "...",
    "outputs": [],
    "safety": {
      "source_mutation_allowed": false,
      "cad_execution_allowed": false,
      "sendcommand_allowed": false,
      "saveas_allowed": false,
      "original_dwg_mutation_allowed": false
    }
  }
}
```

## Priority candidates

These appear safer because they are review/report workers and should not mutate CAD files:

```text
shapely_topology
networkx_graph_audit
duckdb_export
pdf_raster
ocr_text_region
ocr_vector_text_match
ocr_cad_text_match
text_evidence_fusion
text_review_queue
text_corrections_export
text_calibration_report
text_weight_suggestions
```

These need stricter review because they imply broader orchestration or future execution paths:

```text
text_corrections_apply
analysis_automation_megapack
analysis_evidence_megapack
vision_layout
bim_projection
```

## Validation commands before manifest registration

```powershell
python -X utf8 -m compileall -q src/workers tests
python -X utf8 -m pytest -q tests/test_worker_contracts.py tests/test_worker_run_log.py tests/test_worker_runner.py
```

Then run focused tests for each worker group.

## Safety

This candidate document does not modify `config/worker_manifest.json`.

Still blocked by default:

```text
ZWCAD COM SendCommand
CHPROP execution
SAVEAS execution
DXFOUT execution
XiCAD alias execution
original DWG mutation
```
