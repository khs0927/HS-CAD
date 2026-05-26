# tests/test_pr82_cli_candidate_imports.py
from __future__ import annotations

import importlib

CLI_CANDIDATE_MODULES = [
    "src.app.layer_analysis_cli",
    "src.app.text_roles_cli",
    "src.app.spatial_cli",
    "src.app.spatial_graph_cli",
    "src.app.shapely_topology_cli",
    "src.app.shapely_topology_audit_cli",
    "src.app.shapely_area_match_cli",
    "src.app.worker_cli",
    "src.app.analysis_shortcut_cli",
    "src.app",
]


def test_pr82_cli_candidate_modules_importable_without_registration():
    failures = []
    for module_name in CLI_CANDIDATE_MODULES:
        try:
            importlib.import_module(module_name)
        except Exception as exc:
            failures.append(f"{module_name}: {type(exc).__name__}: {exc}")

    assert failures == []
