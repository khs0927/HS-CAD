from __future__ import annotations

from scripts.compare_drawing_index_fixture_runs import classify, facts


def _record(*, complete: bool, engine: str = "native", entities: int = 10, texts: int = 5, layouts: int = 2):
    return {
        "status": "ok",
        "engine": engine,
        "entities": [{}] * entities,
        "texts": [{}] * texts,
        "layouts": [{}] * layouts,
        "extraction_report": {
            "complete": complete,
            "entity_count": entities,
            "text_occurrence_count": texts,
            "layout_count": layouts,
            "blockers": [] if complete else ["extractor_reported_incomplete"],
        },
    }


def test_fallback_complete_but_native_incomplete_is_blocking() -> None:
    severity, reasons = classify(
        facts(_record(complete=False)),
        facts(_record(complete=True, engine="ezdxf")),
    )
    assert severity == "BLOCK"
    assert "fallback completed but native path did not" in reasons


def test_native_missing_layout_is_blocking() -> None:
    severity, reasons = classify(
        facts(_record(complete=True, layouts=1)),
        facts(_record(complete=True, engine="ezdxf", layouts=2)),
    )
    assert severity == "BLOCK"
    assert "native layouts 1 < fallback layouts 2" in reasons


def test_native_lower_text_count_requires_review() -> None:
    severity, reasons = classify(
        facts(_record(complete=True, texts=4)),
        facts(_record(complete=True, engine="ezdxf", texts=5)),
    )
    assert severity == "REVIEW"
    assert "native texts 4 < fallback texts 5" in reasons


def test_equal_complete_records_pass() -> None:
    severity, reasons = classify(
        facts(_record(complete=True)),
        facts(_record(complete=True, engine="ezdxf")),
    )
    assert severity == "PASS"
    assert reasons == []
