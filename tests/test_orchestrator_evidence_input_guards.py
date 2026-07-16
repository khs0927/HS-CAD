from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

import pytest

EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
COMMIT_SHA = "0123456789abcdef0123456789abcdef01234567"


def _load_module():
    root = Path(__file__).resolve().parents[1]
    path = root / "scripts" / "publish_orchestrator_evidence.py"
    spec = importlib.util.spec_from_file_location("publish_orchestrator_evidence_guards", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _result(name: str = "compile") -> dict:
    return {
        "name": name,
        "status": "passed",
        "return_code": 0,
        "duration_seconds": 0.1,
        "stdout_sha256": EMPTY_SHA256,
        "stderr_sha256": EMPTY_SHA256,
    }


def _evidence() -> dict:
    return {
        "schema_version": "hscad.plugin-orchestrator.v1.1",
        "completed_at": "2026-07-17T00:00:00+00:00",
        "status": "passed",
        "profiles": ["core"],
        "summary": {"total": 1, "passed": 1, "failed": 0, "blocked": 0},
        "results": [_result()],
    }


def _build(module, evidence: dict, *, runner: str = "local-container"):
    return module.build_record(
        evidence,
        repository_ref="owner/repository",
        branch_ref="feature/example",
        commit_sha=COMMIT_SHA,
        runner=runner,
        namespace="private-namespace",
    )


@pytest.mark.parametrize("duration", [math.nan, math.inf, -math.inf, -0.1])
def test_rejects_non_finite_or_negative_duration(duration: float) -> None:
    module = _load_module()
    evidence = _evidence()
    evidence["results"][0]["duration_seconds"] = duration

    with pytest.raises(ValueError, match="finite"):
        _build(module, evidence)


def test_rejects_timestamp_without_timezone() -> None:
    module = _load_module()
    evidence = _evidence()
    evidence["completed_at"] = "2026-07-17T00:00:00"

    with pytest.raises(ValueError, match="timezone"):
        _build(module, evidence)


@pytest.mark.parametrize("profile", ["unknown", "CORE /tmp/private", ""])
def test_rejects_unknown_or_unsafe_profile(profile: str) -> None:
    module = _load_module()
    evidence = _evidence()
    evidence["profiles"] = [profile]

    with pytest.raises(ValueError, match="profile"):
        _build(module, evidence)


def test_rejects_duplicate_profiles() -> None:
    module = _load_module()
    evidence = _evidence()
    evidence["profiles"] = ["core", "core"]

    with pytest.raises(ValueError, match="duplicate"):
        _build(module, evidence)


@pytest.mark.parametrize("runner", ["Runner With Spaces", "../../private", "A" * 65])
def test_rejects_unsafe_runner_label(runner: str) -> None:
    module = _load_module()

    with pytest.raises(ValueError, match="runner"):
        _build(module, _evidence(), runner=runner)


def test_rejects_unsafe_result_name() -> None:
    module = _load_module()
    evidence = _evidence()
    evidence["results"][0]["name"] = "compile /private/customer"

    with pytest.raises(ValueError, match="result name"):
        _build(module, evidence)


def test_rejects_more_than_128_results() -> None:
    module = _load_module()
    evidence = _evidence()
    evidence["results"] = [_result(f"check-{index}") for index in range(129)]
    evidence["summary"] = {"total": 129, "passed": 129, "failed": 0, "blocked": 0}

    with pytest.raises(ValueError, match="at most 128"):
        _build(module, evidence)
