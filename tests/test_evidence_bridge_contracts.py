from __future__ import annotations

from pathlib import Path

from hscad.connectors.legacy_artifact_adapter import KNOWN_ARTIFACT_KINDS, LegacyArtifactAdapter
from hscad.safety.policy import SAFETY_FLAGS, assert_safe_defaults
from tests.fixtures.legacy_artifact_factory import write_legacy_artifact_set


def test_known_artifact_contract_contains_existing_outputs() -> None:
    required = {"FILEIZED_DRAWING.json", "ANALYSIS_GRAPH.json", "LAYER_SEMANTICS.json", "CROSS_VALIDATION.json", "DOMAIN_RULE_RESULTS.json"}
    assert required.issubset(KNOWN_ARTIFACT_KINDS)


def test_legacy_artifact_adapter_emits_evidence(tmp_path: Path) -> None:
    legacy_dir = write_legacy_artifact_set(tmp_path / "legacy")
    bridge = LegacyArtifactAdapter().load(legacy_dir)
    assert bridge.artifacts
    assert len(bridge.evidence) >= 8
    assert "legacy_conflict" in bridge.by_kind
    drawing = LegacyArtifactAdapter().drawing_from_fileized_artifact(bridge)
    assert len(drawing.entities) == 3


def test_safety_flags_stay_review_only() -> None:
    assert_safe_defaults()
    forbidden = ["final_live_runner_implemented", "sendcommand_allowed_by_default", "cad_execution_allowed_by_default", "zwcad_com_allowed_by_default", "xicad_alias_execution_allowed", "domain_rule_command_execution_allowed", "original_dwg_mutation_allowed"]
    for key in forbidden:
        assert SAFETY_FLAGS.get(key) is False
