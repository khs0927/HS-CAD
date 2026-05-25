# HS-CAD Main-Code Overlay v3 Progress Report

## Purpose

v1/v2 proved that the new review-only main-code pipeline can run independently.
v3 connects existing HS-CAD analyzer/exporter JSON artifacts to the new evidence/fusion layer.

## Added capabilities

- `LegacyArtifactAdapter` discovers known legacy output files.
- Existing outputs such as `FILEIZED_DRAWING.json`, `LAYER_SEMANTICS.json`, `TEXT_ROLE_INFERENCE.json`, `AREA_ELEMENTS.json`, `SHAPELY_TOPOLOGY.json`, `CROSS_VALIDATION.json`, and `DOMAIN_RULE_RESULTS.json` are converted into normalized `Evidence` records.
- `run_evidence_bridge_pipeline()` writes:
  - `LEGACY_ARTIFACT_BRIDGE_RESULT.json`
  - `EVIDENCE_GRAPH.json`
  - `FUSION_MATRIX.json`
  - `CROSS_VALIDATION.json`
  - `EVIDENCE_BRIDGE_PIPELINE_RESULT.json`
  - `EVIDENCE_BRIDGE_REPORT.md`
  - `hscad_evidence_bridge.sqlite3`
- Optional CLI wrapper: `python -m hscad.app.cli_evidence_bridge`.
- Optional `src.main` Typer registration script is dry-run first.
- Commit hygiene helper excludes runtime artifacts.

## Safety

- No CAD execution.
- No ZWCAD COM.
- No SendCommand.
- No XiCAD alias execution.
- No original DWG mutation.
- Safety flags remain false.

## Remaining work after v3

1. Connect the bridge to the real existing analyzer output directory used by HS-CAD CI.
2. Decide whether `hscad-evidence-bridge` should be registered in `src.main` in this PR or a follow-up PR.
3. Add golden artifact tests once representative real outputs are available.
4. Use evidence graph IDs in the final markdown report and QA overlay.
