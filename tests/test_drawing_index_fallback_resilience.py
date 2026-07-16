from __future__ import annotations

from pathlib import Path

from src.corpus.schema import FileizedDrawingRecord
from src.drawing_index.application.fileizer_registry import FileizerRegistry
from src.fileizers.base import DrawingFileizer


class _ExplodingFileizer(DrawingFileizer):
    supported_extensions = (".dwg",)

    def __init__(self, engine_name: str, message: str = "native automation failed") -> None:
        self.engine_name = engine_name
        self.message = message
        self.calls = 0

    def fileize(self, path, *, file_id, relative_path):
        self.calls += 1
        raise RuntimeError(self.message)


class _CompleteFileizer(DrawingFileizer):
    supported_extensions = (".dwg",)

    def __init__(self, engine_name: str) -> None:
        self.engine_name = engine_name
        self.calls = 0

    def fileize(self, path, *, file_id, relative_path):
        self.calls += 1
        return FileizedDrawingRecord(
            file_id=file_id,
            source_path=str(path),
            relative_path=str(relative_path),
            extension=".dwg",
            status="ok",
            engine=self.engine_name,
            layouts=[{"name": "Model"}],
            extraction_report={
                "complete": True,
                "layout_count": 1,
                "text_occurrence_count": 0,
                "coverage": {"model_space": True},
                "opened_read_only": True,
            },
        )


def test_registry_continues_after_fileizer_exception() -> None:
    native = _ExplodingFileizer("zwcad-native")
    fallback = _CompleteFileizer("ezdxf")

    record = FileizerRegistry([native, fallback]).fileize(
        Path("source.dwg"),
        file_id="drawing-1",
        relative_path="plans/source.dwg",
    )

    assert native.calls == 1
    assert fallback.calls == 1
    assert record.status == "ok"
    assert record.engine == "ezdxf"
    assert record.extraction_report["complete"] is True
    assert record.extraction_report["fallback_used"] is True
    assert record.extraction_report["attempt_count"] == 2

    attempts = record.extraction_report["fileizer_attempts"]
    assert attempts[0]["engine"] == "zwcad-native"
    assert attempts[0]["status"] == "failed"
    assert attempts[0]["complete"] is False
    assert "RuntimeError: native automation failed" in attempts[0]["reason"]
    assert attempts[1]["engine"] == "ezdxf"
    assert attempts[1]["complete"] is True


def test_registry_returns_auditable_failed_record_when_all_fileizers_raise() -> None:
    first = _ExplodingFileizer("zwcad-native", "COM unavailable")
    second = _ExplodingFileizer("ezdxf", "malformed input")

    record = FileizerRegistry([first, second]).fileize(
        "source.dwg",
        file_id="drawing-2",
        relative_path="source.dwg",
    )

    assert record.status == "failed"
    assert record.extraction_report["complete"] is False
    assert record.extraction_report["attempt_count"] == 2
    assert record.extraction_report["selected_engine"] == "zwcad-native"
    assert record.extraction_report["fallback_used"] is False
    assert [item["status"] for item in record.extraction_report["fileizer_attempts"]] == [
        "failed",
        "failed",
    ]
    assert record.errors[0]["type"] == "fileizer_exception"
