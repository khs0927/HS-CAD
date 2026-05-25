# HS-CAD Main-Code Overlay v6 Schema Mapping Report

## Purpose

v6 continues after PR #66 by strengthening the legacy artifact bridge. PR #66 created a review-only evidence bridge and proved that known JSON artifacts can be converted into `Evidence` records. v6 adds schema-aware extraction so that real-world analyzer/exporter outputs with nested wrappers can still be mapped without changing the safety posture.

## Added capabilities

- `src/hscad/connectors/artifact_schema.py`
  - Detects artifact payload shape.
  - Extracts records from lists, mappings, and nested wrappers such as `data`, `result`, and `payload`.
  - Generates compact schema summaries with record paths, record counts, and observed ID/text/geometry keys.
- `legacy_artifact_adapter.py`
  - Includes schema summaries in artifact records and loaded-artifact evidence.
  - Uses the schema-aware extractor for layer, text, area, topology, cross-validation, and domain-rule artifacts.
- `scripts/inspect_legacy_artifact_schema.py`
  - Produces a review-only JSON report for existing HS-CAD output directories.
- `tests/fixtures/legacy_schema_artifact_factory.py`
  - Generates JSON-only schema-variant fixtures at runtime.
- `tests/test_legacy_artifact_schema_v6.py`
  - Verifies nested schema extraction, evidence bridge counts, and schema report generation.

## Safety posture

v6 is still review-only.

- CAD execution: false
- ZWCAD COM: false
- SendCommand: false
- XiCAD alias execution: false
- Original DWG mutation: false
- Runtime artifacts remain excluded from commit

## Validation

Recommended local validation after applying this stacked branch:

```bash
python -X utf8 -m pytest -q tests/test_legacy_artifact_schema_v6.py
python -X utf8 scripts/inspect_legacy_artifact_schema.py --legacy-dir outputs/main_code_v2_smoke --out outputs/schema_report_v6.json
python -m ruff check . --select F821,E9,F63,F7,F82
python -X utf8 -m src.main --help
python -X utf8 -m pytest -q
```

## Next production direction

1. Run the schema inspector against several real HS-CAD output directories.
2. Convert observed schema summaries into golden JSON fixtures.
3. Add schema-specific assertions for `LAYER_SEMANTICS`, `TEXT_ROLE_INFERENCE`, `AREA_ELEMENTS`, `SHAPELY_TOPOLOGY`, `CROSS_VALIDATION`, and `DOMAIN_RULE_RESULTS`.
4. Feed stable evidence IDs into final markdown reports and QA overlay DXF files.
