import json
from pathlib import Path

from .schema import PreviewOperationResult, PreviewSession
from .store import save_preview_session
from .zwcad_ops import connect_active_zwcad, create_undo_mark, erase_object_by_handle, insert_block_from_dxf


def _load_json(path: str | Path | None) -> dict:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def create_session_from_plan_and_insert_result(plan_path: str | Path | None, insert_result_path: str | Path | None) -> PreviewSession:
    plan = _load_json(plan_path)
    result = _load_json(insert_result_path)

    return PreviewSession(
        active_dwg=result.get("active_dwg"),
        source_dxf=plan.get("source_dxf"),
        inserted_handle=result.get("inserted_handle"),
        insert_layer=plan.get("insert_layer") or "QA-REVIEW",
        base_point=plan.get("base_point") or [0.0, 0.0, 0.0],
        scale=float(plan.get("scale") or 1.0),
        rotation=float(plan.get("rotation") or 0.0),
        undo_mark_created=bool(result.get("undo_mark_created")),
        saved=False,
        status="inserted" if result.get("inserted_handle") else "planned",
        warnings=list(plan.get("warnings") or []) + list(result.get("warnings") or []),
        errors=list(result.get("errors") or []),
        metadata={"plan_path": str(plan_path or ""), "insert_result_path": str(insert_result_path or "")},
    )


def remove_preview(session: PreviewSession, allow_execute: bool = False) -> PreviewOperationResult:
    result = PreviewOperationResult(operation="remove_preview", session_id=session.session_id, allow_execute=allow_execute)
    if not session.inserted_handle:
        result.errors.append("session has no inserted_handle")
        return result
    if not allow_execute:
        result.warnings.append("allow_execute is false; dry-run remove only")
        return result

    try:
        _, doc = connect_active_zwcad()
        create_undo_mark(doc)
        ok, error = erase_object_by_handle(doc, session.inserted_handle)
        result.executed = ok
        if error:
            result.errors.append(error)
    except Exception as exc:
        result.errors.append(str(exc))
    return result


def replace_preview(session: PreviewSession, source_dxf: str, out_path: str | Path, allow_execute: bool = False) -> PreviewOperationResult:
    result = PreviewOperationResult(operation="replace_preview", session_id=session.session_id, allow_execute=allow_execute)
    if not allow_execute:
        result.warnings.append("allow_execute is false; dry-run replace only")
        result.metadata["new_source_dxf"] = source_dxf
        return result

    try:
        _, doc = connect_active_zwcad()
        create_undo_mark(doc)
        if session.inserted_handle:
            ok, error = erase_object_by_handle(doc, session.inserted_handle)
            if not ok and error:
                result.errors.append(error)
                return result
        ref = insert_block_from_dxf(doc, source_dxf, session.base_point, session.scale, session.rotation, session.insert_layer)
        new_handle = getattr(ref, "Handle", None)
        session.inserted_handle = new_handle
        session.source_dxf = source_dxf
        session.status = "replaced"
        session.saved = False
        save_preview_session(session, out_path)
        result.executed = True
        result.metadata["new_handle"] = new_handle
    except Exception as exc:
        result.errors.append(str(exc))
    return result
