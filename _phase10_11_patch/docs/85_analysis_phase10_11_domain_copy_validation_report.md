# HS-CAD Phase 10~11 Domain Decision + Copied DWG Validation Patch Report

## Purpose

This bundled patch prepares the bridge from review-only Domain Rule decisions to copied-DWG validation planning.

## Included stages

- Phase 10: Domain Decision Connector
- Phase 11: Copied DWG Validation Bridge

## Added files

- `src/analysis/phase10_domain_decision_connector.py`
- `src/analysis/phase11_copied_dwg_validation_bridge.py`
- `src/workers/analysis_phase10_11_domain_copy_validation_worker.py`
- `src/app/analysis_phase10_11_cli.py`
- `tests/test_analysis_phase10_11_domain_copy_validation_bundle.py`
- `docs/84_analysis_phase10_11_domain_copy_validation_prompt.md`
- `docs/85_analysis_phase10_11_domain_copy_validation_report.md`
- `config/worker_manifest.phase10_11.patch.json`
- `MAIN_IMPORT_PHASE10_11_PATCH.txt`
- `README_APPLY_PHASE10_11.md`

## Safety

- No source drawing mutation
- No CAD execution
- No ZWCAD COM
- No SendCommand
- No XiCAD alias execution
- No Domain Rule Command Plan execution
- No live execution readiness
- Copied-DWG validation is plan-only in this phase
