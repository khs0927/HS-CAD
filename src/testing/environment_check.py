from __future__ import annotations

import importlib
import importlib.util
import json
import platform
import struct
import sys
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version as distribution_version
from pathlib import Path
from typing import Any


COMMON_PROGIDS = ["ZWCAD.Application", "ZwCAD.Application"]
PROGIDS_2025 = ["ZWCAD.Application.2025", "ZwCAD.Application.2025"]
PROGIDS_2026 = ["ZWCAD.Application.2026", "ZwCAD.Application.2026"]

OPTIONAL_IMPORTS = {
    "comtypes": "comtypes",
    "pywin32": "win32com.client",
    "ezdxf": "ezdxf",
    "pandas": "pandas",
    "openpyxl": "openpyxl",
    "cad_pyrx": "pyrx",
    "pyzwcad": "pyzwcad",
    "pil": "PIL",
    "mss": "mss",
    "yaml": "yaml",
    "typer": "typer",
    "pydantic": "pydantic",
}


def zwcad_progid_candidates(version: str | None = None) -> list[str]:
    requested = str(version or "").strip()
    if requested == "2025":
        ordered = PROGIDS_2025 + COMMON_PROGIDS + PROGIDS_2026
    elif requested == "2026":
        ordered = PROGIDS_2026 + COMMON_PROGIDS + PROGIDS_2025
    else:
        ordered = COMMON_PROGIDS + PROGIDS_2025 + PROGIDS_2026
    return list(dict.fromkeys(ordered))


def _module_available(module_name: str) -> tuple[bool, str | None]:
    try:
        if importlib.util.find_spec(module_name) is None:
            return False, "module spec not found"
        return True, None
    except Exception as exc:
        return False, str(exc)


def check_optional_imports() -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for key, module_name in OPTIONAL_IMPORTS.items():
        ok, error = _module_available(module_name)
        rows[key] = {"module": module_name, "available": ok, "error": error}
    return rows


def check_imports() -> list[dict[str, Any]]:
    return [{"name": key, **value} for key, value in check_optional_imports().items()]


def _safe_attr(obj: Any, name: str) -> Any:
    try:
        return getattr(obj, name)
    except Exception:
        return None


def _safe_str_attr(obj: Any, name: str) -> str | None:
    value = _safe_attr(obj, name)
    return str(value) if value is not None else None


def _error_payload(exc: BaseException) -> dict[str, Any]:
    payload: dict[str, Any] = {"message": str(exc), "type": type(exc).__name__}
    hresult = getattr(exc, "hresult", None)
    if hresult is None and getattr(exc, "args", None):
        first = exc.args[0]
        if isinstance(first, int):
            hresult = first
    if hresult is not None:
        payload["hresult"] = hresult
    return payload


def _initialize_com() -> tuple[str, Any] | None:
    try:
        pythoncom = importlib.import_module("pythoncom")
        pythoncom.CoInitialize()
        return "pythoncom", pythoncom
    except Exception:
        pass
    try:
        comtypes = importlib.import_module("comtypes")
        comtypes.CoInitialize()
        return "comtypes", comtypes
    except Exception:
        return None


def _uninitialize_com(token: tuple[str, Any] | None) -> None:
    if token is None:
        return
    _backend, module = token
    try:
        module.CoUninitialize()
    except Exception:
        pass


def _try_get_active(progid: str) -> tuple[Any | None, dict[str, Any]]:
    try:
        win32_client = importlib.import_module("win32com.client")
        app = win32_client.GetActiveObject(progid)
        return app, {"ok": True, "method": "GetActiveObject", "backend": "pywin32"}
    except Exception as win32_exc:
        win32_error = _error_payload(win32_exc)
    try:
        comtypes_client = importlib.import_module("comtypes.client")
        app = comtypes_client.GetActiveObject(progid)
        return app, {"ok": True, "method": "GetActiveObject", "backend": "comtypes"}
    except Exception as comtypes_exc:
        return None, {
            "ok": False,
            "method": "GetActiveObject",
            "errors": {"pywin32": win32_error, "comtypes": _error_payload(comtypes_exc)},
        }


def _try_create(progid: str) -> tuple[Any | None, dict[str, Any]]:
    try:
        win32_client = importlib.import_module("win32com.client")
        app = win32_client.Dispatch(progid)
        return app, {"ok": True, "method": "CreateObject", "backend": "pywin32"}
    except Exception as win32_exc:
        win32_error = _error_payload(win32_exc)
    try:
        comtypes_client = importlib.import_module("comtypes.client")
        app = comtypes_client.CreateObject(progid)
        return app, {"ok": True, "method": "CreateObject", "backend": "comtypes"}
    except Exception as comtypes_exc:
        return None, {
            "ok": False,
            "method": "CreateObject",
            "errors": {"pywin32": win32_error, "comtypes": _error_payload(comtypes_exc)},
        }


def probe_zwcad_com(version: str | None = None, start_zwcad: bool = False) -> dict[str, Any]:
    candidates = zwcad_progid_candidates(version)
    payload: dict[str, Any] = {
        "attempted": False,
        "connected": False,
        "candidates": candidates,
        "results": [],
        "active_progid": None,
        "connection_mode": "skipped",
        "application_name": None,
        "version": None,
        "active_document": None,
        "error": None,
    }
    if platform.system().lower() != "windows":
        payload["error"] = "COM probe skipped because this is not Windows."
        return payload

    payload["attempted"] = True
    com_token = _initialize_com()
    try:
        for progid in candidates:
            row: dict[str, Any] = {"progid": progid, "active_object": None, "created_object": None}
            app, active_result = _try_get_active(progid)
            row["active_object"] = active_result
            mode = "active_object"
            if app is None and start_zwcad:
                app, create_result = _try_create(progid)
                row["created_object"] = create_result
                mode = "created_object"
            elif app is None:
                row["created_object"] = {"ok": False, "skipped": True, "reason": "--start-zwcad not set"}
            if app is not None:
                active_document = _safe_attr(app, "ActiveDocument")
                payload.update(
                    {
                        "connected": True,
                        "active_progid": progid,
                        "connection_mode": mode,
                        "application_name": _safe_str_attr(app, "Name"),
                        "version": _safe_str_attr(app, "Version"),
                        "active_document": _safe_str_attr(active_document, "Name"),
                        "error": None,
                    }
                )
                payload["results"].append(row)
                return payload
            payload["results"].append(row)
    finally:
        _uninitialize_com(com_token)

    payload["connection_mode"] = "failed"
    payload["error"] = "No ZWCAD COM ProgID connected. If ZWCAD is installed, run it once as administrator or retry with --start-zwcad."
    return payload


def build_recommendations(payload: dict[str, Any]) -> list[str]:
    recs = [
        "Python 64-bit and ZWCAD 64-bit are recommended.",
        "If ZWCAD is installed but COM fails, run ZWCAD once as administrator and retry.",
        "Use --start-zwcad when ZWCAD is not already running.",
        "When multiple versions are installed, pass --version 2025 or --version 2026.",
    ]
    if not payload.get("is_windows"):
        recs.insert(0, "ZWCAD COM integration requires Windows.")
    if payload.get("zwcad_com_connect_attempted") and not payload.get("zwcad_com_connected"):
        recs.append("COM ProgID registration may be missing; repair or reinstall ZWCAD if all ProgIDs fail.")
    return recs


def _package_version() -> str:
    try:
        return distribution_version("hs-cad")
    except PackageNotFoundError:
        return "unknown"


def run_environment_check(
    dwg: str | None = None,
    xicad_root: str | None = None,
    out: str | Path | None = None,
    out_dir: str | Path | None = None,
    version: str | None = None,
    start_zwcad: bool = False,
    project_root: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(project_root) if project_root else Path.cwd()
    optional_imports = check_optional_imports()
    com = probe_zwcad_com(version=version, start_zwcad=start_zwcad)
    xicad = _detect_xicad_root(xicad_root)
    payload: dict[str, Any] = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "python_version": sys.version,
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "working_directory": str(Path.cwd()),
        "project_root": str(root),
        "package_version": _package_version(),
        "is_windows": platform.system().lower() == "windows",
        "is_64bit_python": struct.calcsize("P") * 8 == 64,
        "optional_imports": optional_imports,
        "comtypes_available": optional_imports["comtypes"]["available"],
        "pywin32_available": optional_imports["pywin32"]["available"],
        "ezdxf_available": optional_imports["ezdxf"]["available"],
        "pandas_available": optional_imports["pandas"]["available"],
        "openpyxl_available": optional_imports["openpyxl"]["available"],
        "cad_pyrx_available": optional_imports["cad_pyrx"]["available"],
        "pyzwcad_available": optional_imports["pyzwcad"]["available"],
        "pil_available": optional_imports["pil"]["available"],
        "mss_available": optional_imports["mss"]["available"],
        "dwg": str(dwg) if dwg else None,
        "dwg_exists": Path(dwg).exists() if dwg else None,
        "xicad_root": str(xicad_root) if xicad_root else None,
        "xicad_detection": xicad,
        "zwcad_requested_version": version,
        "zwcad_start_requested": start_zwcad,
        "zwcad_com_connect_attempted": com["attempted"],
        "zwcad_com_connected": com["connected"],
        "zwcad_progid_candidates": com["candidates"],
        "zwcad_progid_results": com["results"],
        "zwcad_active_progid": com["active_progid"],
        "zwcad_connection_mode": com["connection_mode"],
        "zwcad_application_name": com["application_name"],
        "zwcad_version": com["version"],
        "zwcad_active_document": com["active_document"],
        "zwcad_error": com["error"],
    }
    payload["recommendations"] = build_recommendations(payload)
    if out:
        write_json(Path(out), payload)
    if out_dir:
        write_environment_check(payload, out_dir)
    return payload


def _detect_xicad_root(xicad_root: str | None) -> dict[str, Any]:
    if not xicad_root:
        return {"provided": False}
    root = Path(xicad_root)
    expected = {
        "root": root,
        "_ZWCad": root / "_ZWCad",
        "Lisp": root / "Lisp",
        "Lib": root / "Lib",
        "xiLib": root / "xiLib",
        "xiShortkey_origin.key": root / "Lisp" / "xiShortkey_origin.key",
    }
    return {key: {"path": str(path), "exists": path.exists()} for key, path in expected.items()}


def write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_environment_check(payload: dict[str, Any], out_dir: str | Path) -> dict[str, str]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = {
        "environment_check": str(write_json(out / "environment_check.json", payload)),
        "optional_imports": str(write_json(out / "optional_imports.json", payload.get("optional_imports", {}))),
    }
    md_path = out / "environment_check.md"
    md_path.write_text(summarize_environment_check(payload), encoding="utf-8")
    paths["markdown"] = str(md_path)
    return paths


def summarize_environment_check(payload: dict[str, Any]) -> str:
    missing = [k for k, v in payload.get("optional_imports", {}).items() if not v.get("available")]
    lines = [
        "# ZWCAD 2025/2026 Environment Check",
        "",
        f"- Timestamp: {payload.get('timestamp')}",
        f"- Python: {payload.get('python_executable') or payload.get('python_version')}",
        f"- Platform: {payload.get('platform')}",
        f"- Working directory: {payload.get('working_directory')}",
        f"- Requested ZWCAD version: {payload.get('zwcad_requested_version') or 'auto'}",
        f"- Start requested: {payload.get('zwcad_start_requested')}",
        f"- COM connected: {payload.get('zwcad_com_connected')}",
        f"- Active ProgID: {payload.get('zwcad_active_progid') or '-'}",
        f"- Connection mode: {payload.get('zwcad_connection_mode')}",
        f"- Application: {payload.get('zwcad_application_name') or '-'} {payload.get('zwcad_version') or ''}",
        f"- Active document: {payload.get('zwcad_active_document') or '-'}",
        f"- Missing optional imports: {', '.join(missing) if missing else 'none'}",
        "",
        "## ProgID Probe Results",
    ]
    for row in payload.get("zwcad_progid_results", []):
        active = row.get("active_object") or {}
        created = row.get("created_object") or {}
        lines.append(f"- {row.get('progid')}: active={active.get('ok')} created={created.get('ok')}")
    lines.extend(["", "## Recommendations"])
    lines.extend(f"- {item}" for item in payload.get("recommendations", []))
    return "\n".join(lines) + "\n"
