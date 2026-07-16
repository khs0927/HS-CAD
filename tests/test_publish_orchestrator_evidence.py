from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def _load_module():
    root = Path(__file__).resolve().parents[1]
    path = root / "scripts" / "publish_orchestrator_evidence.py"
    spec = importlib.util.spec_from_file_location("publish_orchestrator_evidence", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _evidence() -> dict:
    return {
        "schema_version": "hscad.plugin-orchestrator.v1.1",
        "completed_at": "2026-07-17T00:00:00+00:00",
        "status": "passed",
        "profiles": ["core"],
        "summary": {"total": 1, "passed": 1, "failed": 0, "blocked": 0},
        "results": [
            {
                "name": "compile",
                "status": "passed",
                "command": ["python", "-m", "compileall", "private/project"],
                "working_directory": "private/project",
                "return_code": 0,
                "duration_seconds": 1.23456,
                "stdout_sha256": EMPTY_SHA256,
                "stderr_sha256": EMPTY_SHA256,
                "stdout": "PRIVATE-DRAWING-NAME",
                "stderr": "",
                "reason": "private/project",
            }
        ],
    }


def test_build_record_keeps_only_hash_safe_result_fields() -> None:
    module = _load_module()
    repository_ref = "private-owner/private-repository"
    branch_ref = "feature/private-customer-name"
    namespace = "not-committed-secret-namespace"

    record = module.build_record(
        _evidence(),
        repository_ref=repository_ref,
        branch_ref=branch_ref,
        commit_sha="0123456789abcdef0123456789abcdef01234567",
        runner="local-container",
        namespace=namespace,
    )

    serialized = repr(record)
    assert repository_ref not in serialized
    assert branch_ref not in serialized
    assert namespace not in serialized
    assert "PRIVATE-DRAWING-NAME" not in serialized
    assert "working_directory" not in record["results"][0]
    assert "command" not in record["results"][0]
    assert "stdout" not in record["results"][0]
    assert "stderr" not in record["results"][0]
    assert "reason" not in record["results"][0]
    assert set(record["results"][0]) == set(module.RESULT_FIELDS)


def test_namespace_changes_repository_and_branch_tokens() -> None:
    module = _load_module()
    kwargs = {
        "evidence": _evidence(),
        "repository_ref": "owner/repository",
        "branch_ref": "feature/example",
        "commit_sha": "0123456789abcdef0123456789abcdef01234567",
        "runner": "local-container",
    }

    first = module.build_record(namespace="namespace-one", **kwargs)
    second = module.build_record(namespace="namespace-two", **kwargs)

    assert first["repository_token"] != second["repository_token"]
    assert first["branch_token"] != second["branch_token"]
    assert len(first["repository_token"]) == 64
    assert len(first["branch_token"]) == 64


def test_build_record_is_deterministic() -> None:
    module = _load_module()
    kwargs = {
        "evidence": _evidence(),
        "repository_ref": "owner/repository",
        "branch_ref": "feature/example",
        "commit_sha": "0123456789abcdef0123456789abcdef01234567",
        "runner": "local-container",
        "namespace": "namespace",
    }

    assert module.build_record(**kwargs) == module.build_record(**kwargs)


def test_rejects_invalid_commit_sha() -> None:
    module = _load_module()

    with pytest.raises(ValueError, match="commit SHA"):
        module.build_record(
            _evidence(),
            repository_ref="owner/repository",
            branch_ref="feature/example",
            commit_sha="short",
            runner="local-container",
            namespace="namespace",
        )


def test_rejects_invalid_log_digest() -> None:
    module = _load_module()
    evidence = _evidence()
    evidence["results"][0]["stdout_sha256"] = "not-a-digest"

    with pytest.raises(ValueError, match="SHA-256"):
        module.build_record(
            evidence,
            repository_ref="owner/repository",
            branch_ref="feature/example",
            commit_sha="0123456789abcdef0123456789abcdef01234567",
            runner="local-container",
            namespace="namespace",
        )


def test_rejects_summary_that_does_not_match_results() -> None:
    module = _load_module()
    evidence = _evidence()
    evidence["summary"] = {"total": 2, "passed": 2, "failed": 0, "blocked": 0}

    with pytest.raises(ValueError, match="number of sanitized results"):
        module.build_record(
            evidence,
            repository_ref="owner/repository",
            branch_ref="feature/example",
            commit_sha="0123456789abcdef0123456789abcdef01234567",
            runner="local-container",
            namespace="namespace",
        )


def test_publish_requires_https() -> None:
    module = _load_module()

    with pytest.raises(ValueError, match="HTTPS"):
        module.publish_record(
            {"status": "passed"},
            supabase_url="http://example.invalid",
            service_role_key="secret",
        )
