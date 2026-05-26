# PR82 CLI Candidate Validation Matrix

This document tracks the import validation and registration readiness of the CLI candidates from PR82 before integration into `src/main.py`.

| Command family | Module path | Import pass | Requires src.main edit | Live CAD risk | Status | Notes |
|---|---|---:|---:|---:|---|---|
| open_backends_cli | src.app.open_backends_cli | No | Yes | Low | missing_module | No module named 'src.integrations.open_source_backends' |
| cad_platforms_cli | src.app.cad_platforms_cli | No | Yes | Low | missing_module | No module named 'src.integrations.cad_platforms' |
| layer_analysis_cli | src.app.layer_analysis_cli | Yes | Yes | Low | ready_for_small_manifest_pr | Fully importable |
| layer_audit_cli | src.app.layer_audit_cli | No | Yes | Low | missing_module | No module named 'src.analysis.layer_audit' |
| text_roles_cli | src.app.text_roles_cli | Yes | Yes | Low | ready_for_small_manifest_pr | Fully importable |
| spatial_cli | src.app.spatial_cli | Yes | Yes | Low | ready_for_small_manifest_pr | Fully importable |
| spatial_graph_cli | src.app.spatial_graph_cli | Yes | Yes | Low | ready_for_small_manifest_pr | Fully importable |
| shapely_topology_cli | src.app.shapely_topology_cli | Yes | Yes | Low | ready_for_small_manifest_pr | Fully importable |
| shapely_topology_audit_cli | src.app.shapely_topology_audit_cli | Yes | Yes | Low | ready_for_small_manifest_pr | Fully importable |
| shapely_area_match_cli | src.app.shapely_area_match_cli | Yes | Yes | Low | ready_for_small_manifest_pr | Fully importable |
| fusion_matrix_cli | src.app.fusion_matrix_cli | No | Yes | Low | missing_module | No module named 'src.integrations.fusion_matrix' |
| cross_validate_cli | src.app.cross_validate_cli | No | Yes | Low | missing_module | No module named 'src.analysis.cross_validation' |
| worker_cli | src.app.worker_cli | Yes | Yes | Low | ready_for_small_manifest_pr | Fully importable |
| analysis_shortcut_cli | src.app.analysis_shortcut_cli | Yes | Yes | Low | ready_for_small_manifest_pr | Fully importable |
| app_package | src.app | Yes | Yes | Low | ready_for_small_manifest_pr | Fully importable |

## Summary

- **10 CLI modules** are fully validated for import and are marked as `ready_for_small_manifest_pr`.
- **5 CLI modules** failed import validation due to missing underlying source dependencies and are marked as `missing_module`.
