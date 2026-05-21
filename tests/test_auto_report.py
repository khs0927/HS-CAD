from image_to_cad.auto.active_analyzer import ActiveDrawingAnalysis
from image_to_cad.auto.auto_layer_mapper import guess_layer_mapping
from image_to_cad.auto.auto_report import write_auto_analysis


def test_auto_report_writes_expected_files(tmp_path):
    analysis = ActiveDrawingAnalysis(
        generated_at="now",
        active_doc="fake.dwg",
        object_count=1,
        layer_counts={"DOOR1": 1},
        entity_counts={"LINE": 1},
        layer_entity_counts={"DOOR1": {"LINE": 1}},
        block_counts={},
        text_samples=[],
        dimension_count=0,
        candidates=[guess_layer_mapping("DOOR1", 1)],
        warnings=[],
    )

    paths = write_auto_analysis(analysis, tmp_path)

    assert "DOOR1" in (tmp_path / "auto_analysis_report.md").read_text(encoding="utf-8")
    assert (tmp_path / "auto_inventory.json").exists()
    assert (tmp_path / "layer_mapping_candidates.csv").exists()
    assert (tmp_path / "auto_preview_plan.json").exists()
    assert (tmp_path / "auto_preview_result.json").exists()
    assert set(paths) == {"inventory", "candidates", "plan", "preview_result", "report"}
