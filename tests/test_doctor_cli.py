from __future__ import annotations

from pathlib import Path

from src.app.doctor_cli import _find_zwcad, collect_doctor_checks, doctor_payload


def test_doctor_payload_has_stable_json_shape() -> None:
    payload = doctor_payload(probe_com=False)

    assert isinstance(payload["ok"], bool)
    assert isinstance(payload["failure_count"], int)
    assert payload["checks"]
    assert {"name", "status", "detail", "required"} <= set(payload["checks"][0])


def test_collect_doctor_checks_never_probes_com_by_default() -> None:
    checks = collect_doctor_checks()
    names = {item.name for item in checks}

    assert "Python" in names
    assert "Operating system" in names
    assert "ZWCAD COM probe" not in names


def test_find_zwcad_honors_explicit_executable(monkeypatch, tmp_path: Path) -> None:
    executable = tmp_path / "ZWCAD.exe"
    executable.write_bytes(b"test")
    monkeypatch.setenv("ZWCAD_EXE", str(executable))

    assert _find_zwcad() == executable.resolve()
