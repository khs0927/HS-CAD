# tests/test_pr82_worker_candidate_imports.py
from __future__ import annotations

import importlib

CANDIDATE_MODULES = [
    "src.workers.pdf_raster_worker",
    "src.workers.ocr_text_region_worker",
    "src.workers.networkx_graph_audit_worker",
    "src.workers.duckdb_export_worker",
]


def test_pr82_worker_candidate_modules_importable():
    failures = []
    for module_name in CANDIDATE_MODULES:
        try:
            importlib.import_module(module_name)
        except Exception as exc:
            failures.append(f"{module_name}: {type(exc).__name__}: {exc}")

    assert failures == []
