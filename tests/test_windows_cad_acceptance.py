from __future__ import annotations

import json
import os
import platform
from pathlib import Path
from typing import Any

import pytest

from src.testing.environment_check import zwcad_progid_candidates

pytestmark = [pytest.mark.windows, pytest.mark.zwcad]


def _acceptance_context() -> tuple[Path, Path, bool]:
    if platform.system() != "Windows":
        pytest.skip("real Windows acceptance requires Windows")
    if os.environ.get("HSCAD_WINDOWS_CAD_ACCEPTANCE") != "1":
        pytest.skip("HSCAD_WINDOWS_CAD_ACCEPTANCE=1 is required")
    fixture_root = Path(os.environ["HSCAD_FIXTURE_ROOT"]).resolve()
    workspace = Path(os.environ["HSCAD_FIXTURE_WORKSPACE"]).resolve()
    static_only = os.environ.get("HSCAD_WINDOWS_STATIC_ONLY") == "1"
    assert fixture_root.is_dir()
    workspace.mkdir(parents=True, exist_ok=True)
    return fixture_root, workspace, static_only


def _fixture_files(root: Path, suffix: str) -> list[Path]:
    expected = suffix.lower()
    return sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() == expected)


def test_windows_dependencies_are_importable():
    _acceptance_context()
    import comtypes  # noqa: F401
    import ezdxf  # noqa: F401
    import fitz  # noqa: F401
    import pythoncom  # noqa: F401
    import win32api  # noqa: F401
    import win32com.client  # noqa: F401


def test_fixture_manifest_is_hash_only():
    _fixture_root, workspace, _static_only = _acceptance_context()
    payload = json.loads((workspace / "fixture-manifest.json").read_text(encoding="utf-8-sig"))
    assert payload["fixture_count"] > 0
    for item in payload["files"]:
        assert set(item) == {"path_sha256", "extension", "size_bytes"}
        assert len(item["path_sha256"]) == 64
        assert "relative_path" not in item


def test_dxf_fixtures_parse_when_present():
    fixture_root, _workspace, _static_only = _acceptance_context()
    paths = _fixture_files(fixture_root, ".dxf")
    if not paths:
        pytest.skip("no DXF fixtures")
    import ezdxf
    for path in paths:
        assert ezdxf.readfile(path).modelspace() is not None


def test_pdf_fixtures_parse_when_present():
    fixture_root, _workspace, _static_only = _acceptance_context()
    paths = _fixture_files(fixture_root, ".pdf")
    if not paths:
        pytest.skip("no PDF fixtures")
    import fitz
    for path in paths:
        with fitz.open(path) as document:
            assert document.page_count > 0


def _get_active_app(client: Any) -> tuple[Any, str]:
    errors: list[str] = []
    for progid in zwcad_progid_candidates("2026"):
        try:
            return client.GetActiveObject(progid), progid
        except Exception as exc:
            errors.append(type(exc).__name__)
    raise AssertionError(f"no active ZWCAD COM object; attempts={len(errors)}")


def test_all_dwg_fixtures_open_read_only_in_running_zwcad():
    fixture_root, _workspace, static_only = _acceptance_context()
    if static_only:
        pytest.skip("static-only fixture validation")
    paths = _fixture_files(fixture_root, ".dwg")
    assert paths, "strict acceptance requires at least one DWG fixture"
    import pythoncom
    import win32com.client
    pythoncom.CoInitialize()
    try:
        app, progid = _get_active_app(win32com.client)
        assert progid
        for path in paths:
            document = None
            try:
                document = app.Documents.Open(str(path), True)
                assert document is not None
                assert str(document.Name)
                assert int(document.ModelSpace.Count) >= 0
            finally:
                if document is not None:
                    document.Close(False)
    finally:
        pythoncom.CoUninitialize()
