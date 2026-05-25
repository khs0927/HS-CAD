from __future__ import annotations

from pathlib import Path

from hscad.cad.layer_schema import LAYER_SCHEMA
from hscad.core.evidence import ConfidenceScore, Evidence, EvidenceKind, EvidenceSource
from hscad.domain_rules.base import DomainRuleResult, RuleStatus
from hscad.fileizers.dxf_fileizer import DxfFileizer
from hscad.fusion.evidence_fusion import EvidenceFusionEngine


def test_layer_schema_contains_required_qa_layers() -> None:
    assert "AI_LOWCONF" in LAYER_SCHEMA
    assert "QA_MARKUP" in LAYER_SCHEMA
    assert "RAW_LINES" in LAYER_SCHEMA
    assert LAYER_SCHEMA["QA_MARKUP"].required is True


def test_confidence_rejects_invalid_value() -> None:
    try:
        ConfidenceScore(1.5)
    except ValueError:
        return
    raise AssertionError("ConfidenceScore should reject values above 1.0")


def test_dxf_fileizer_parses_fixture() -> None:
    drawing = DxfFileizer().fileize(Path("tests/fixtures/minimal_floorplan.dxf"))
    assert drawing.input_type == "dxf"
    assert len(drawing.entities) >= 1
    assert drawing.evidence


def test_fusion_groups_evidence() -> None:
    ev1 = Evidence(EvidenceSource.DXF, EvidenceKind.LAYER, {"layer": "WAL1"}, entity_id="layer:WAL1")
    ev2 = Evidence(EvidenceSource.SYSTEM, EvidenceKind.LAYER, {"layer": "WAL1"}, entity_id="layer:WAL1")
    result = EvidenceFusionEngine().fuse([ev1, ev2])
    assert len(result.groups) == 1
    assert result.groups[0].key == "layer:WAL1"


def test_domain_rule_result_is_plan_only() -> None:
    result = DomainRuleResult(
        rule_id="TEST_RULE",
        status=RuleStatus.REVIEW,
        confidence=ConfidenceScore.medium("test"),
    )
    record = result.to_record()
    assert record["plan_only"] is True
    assert result.as_evidence().payload["rule_id"] == "TEST_RULE"
