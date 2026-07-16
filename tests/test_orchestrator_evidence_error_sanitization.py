from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    root = Path(__file__).resolve().parents[1]
    path = root / "scripts" / "publish_orchestrator_evidence.py"
    spec = importlib.util.spec_from_file_location("publish_orchestrator_evidence_errors", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_file_errors_do_not_expose_local_paths() -> None:
    module = _load_module()
    private_path = "/private/customer/project/evidence.json"

    not_found = FileNotFoundError(2, "missing", private_path)
    permission = PermissionError(13, "denied", private_path)
    generic = OSError(5, "failed", private_path)

    for exc in (not_found, permission, generic):
        message = module._safe_failure_message(exc)
        assert private_path not in message
        assert "customer" not in message


def test_unsafe_status_value_is_not_reflected_in_validation_error() -> None:
    module = _load_module()
    private_value = "failed-/private/customer"
    evidence = {
        "schema_version": "hscad.plugin-orchestrator.v1.1",
        "completed_at": "2026-07-17T00:00:00+00:00",
        "status": private_value,
        "profiles": ["core"],
        "summary": {"total": 0, "passed": 0, "failed": 0, "blocked": 0},
        "results": [],
    }

    try:
        module.build_record(
            evidence,
            repository_ref="owner/repository",
            branch_ref="feature/example",
            commit_sha="0123456789abcdef0123456789abcdef01234567",
            runner="local-container",
            namespace="private-namespace",
        )
    except ValueError as exc:
        assert private_value not in str(exc)
    else:
        raise AssertionError("unsafe status must be rejected")
