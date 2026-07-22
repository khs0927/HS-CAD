from __future__ import annotations

from scripts.inspect_clean_mcp_demo_drawing1 import validate_demo_snapshot


def objects() -> list[dict[str, object]]:
    return [
        {
            "handle": "T1",
            "object_name": "AcDbMText",
            "text": "1000,1000,1000",
            "text_height": 250.0,
            "insertion_point": [0.0, 0.0, 0.0],
            "bbox": {"min": [0.0, 0.0, 0.0], "max": [1000.0, 300.0, 0.0]},
        },
        {
            "handle": "T2",
            "object_name": "AcDbMText",
            "text": "3000",
            "text_height": 300.0,
            "insertion_point": [3000.0, 0.0, 0.0],
            "bbox": {"min": [3000.0, 0.0, 0.0], "max": [3500.0, 300.0, 0.0]},
        },
        {
            "handle": "L1",
            "object_name": "AcDb2dLeader",
            "annotation_handle": "T1",
            "bbox": {"min": [-500.0, -500.0, 0.0], "max": [0.0, 0.0, 0.0]},
        },
        {
            "handle": "L2",
            "object_name": "AcDbLeader",
            "annotation_handle": "T2",
            "bbox": {"min": [2500.0, -500.0, 0.0], "max": [3000.0, 0.0, 0.0]},
        },
    ]


def report(items: list[dict[str, object]], *, cmdactive: int = 0) -> dict[str, object]:
    return validate_demo_snapshot(
        document="Drawing1.dwg",
        layer="MCP_HSCAD_DEMO_LIVE",
        cmdactive=cmdactive,
        objects=items,
    )


def test_valid_snapshot_reports_counts_links_distance_and_bbox() -> None:
    result = report(objects())
    assert result["ok"]
    assert result["object_count"] == 4
    assert result["mtext_insertion_distance"] == 3000
    assert result["overall_bbox"] == {
        "min": [-500.0, -500.0, 0.0],
        "max": [3500.0, 300.0, 0.0],
        "size": [4000.0, 800.0, 0.0],
    }


def test_rejects_wrong_text_height_distance_and_active_command() -> None:
    items = objects()
    items[0]["text_height"] = 249
    items[1]["insertion_point"] = [1000.0, 0.0, 0.0]
    result = report(items, cmdactive=1)
    assert not result["ok"]
    assert any("CMDACTIVE" in error for error in result["errors"])
    assert any("height" in error for error in result["errors"])
    assert any("distance" in error for error in result["errors"])


def test_rejects_missing_or_crossed_annotation_connections() -> None:
    items = objects()
    items[2]["annotation_handle"] = None
    items[3]["annotation_handle"] = "T1"
    result = report(items)
    assert not result["ok"]
    assert any("no annotation" in error for error in result["errors"])
    assert any("one-to-one" in error for error in result["errors"])


def test_rejects_extra_type_and_missing_bbox() -> None:
    items = objects()
    items.append({"handle": "X", "object_name": "AcDbLine", "bbox": None})
    for item in items:
        item["bbox"] = None
    result = report(items)
    assert not result["ok"]
    assert any("other than" in error for error in result["errors"])
    assert any("bounding box" in error for error in result["errors"])
