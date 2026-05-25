from __future__ import annotations

from pathlib import Path

from hscad.cad.dxf_builders import ResultDxfBuilder
from hscad.cad.layer_schema import LAYER_SCHEMA
from hscad.core.evidence import AuditTrail, ConfidenceScore, Evidence, EvidenceKind, EvidenceSource
from hscad.core.models import DrawingEntity, FileizedDrawing
from hscad.domain_rules.architectural_rules import ArchitecturalRuleEngine
from hscad.fileizers.dwg_fileizer import DwgFileizer
from hscad.fileizers.image_fileizer import ImageFileizer
from hscad.fileizers.pdf_fileizer import PdfFileizer
from hscad.fusion.evidence_fusion import EvidenceFusionEngine


def test_fileizers_return_common_model_without_cad_execution(tmp_path: Path):
    pdf = tmp_path / "a.pdf"
    image = tmp_path / "a.png"
    dwg = tmp_path / "a.dwg"
    pdf.write_bytes(b"%PDF")
    image.write_bytes(b"PNG")
    dwg.write_bytes(b"DWG")

    for result in [PdfFileizer().fileize(pdf), ImageFileizer().fileize(image), DwgFileizer().fileize(dwg)]:
        payload = result.to_record()
        assert payload["input_type"] in {"pdf", "png", "dwg"}
        assert "entities" in payload
        assert "evidence" in payload


def test_evidence_and_fusion_contracts(tmp_path: Path):
    evidence = Evidence(
        kind=EvidenceKind.LAYER,
        payload={"layer": "WAL1"},
        source=EvidenceSource.DXF,
        confidence=ConfidenceScore(0.8, reason="fixture"),
        audit=[AuditTrail(created_by="test", action="created")],
    )
    result = EvidenceFusionEngine().fuse([evidence])
    paths = result.write_outputs(tmp_path)

    assert result.groups[0].confidence == 0.8
    assert Path(paths["FUSION_MATRIX"]).name == "FUSION_MATRIX.json"
    assert Path(paths["CROSS_VALIDATION"]).name == "CROSS_VALIDATION.json"


def test_layer_schema_and_dxf_builder_are_plan_only(tmp_path: Path):
    assert "WAL1" in LAYER_SCHEMA
    assert "QA_MARKUP" in LAYER_SCHEMA

    plan = ResultDxfBuilder(tmp_path).build_qa_overlay(["review this wall"])

    assert Path(plan.output_path).name == "qa_overlay.dxf"
    assert plan.name == "qa_overlay"


def test_domain_rule_engine_returns_plan_only_results():
    engine = ArchitecturalRuleEngine()
    drawing = FileizedDrawing(
        input_path="fixture.dxf",
        input_type="dxf",
        entities=[
            DrawingEntity(entity_id="1", entity_type="LINE", layer="WAL1"),
            DrawingEntity(entity_id="2", entity_type="INSERT", layer="DOOR"),
        ],
    )
    results = engine.evaluate(drawing)

    assert results[0].rule_id == "ARCH_BASIC_LAYER_PRESENCE"
    assert "recommended_action" in results[0].to_record()
    assert results[0].plan_only is True
