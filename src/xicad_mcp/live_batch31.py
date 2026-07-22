"""Truthful ZWCAD live previews and SNAPANG execution for xiCAD Batch 31."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from .headless_core_batch31a import (
    AxisChangeRequest,
    AxisResetRequest,
    CopyValueRequest,
    ElevationMarkRequest,
    HatchThicknessRequest,
    KitchenInlineRequest,
    PurgeAllRequest,
    SaveSeparateRequest,
    plan_axis_change,
    plan_axis_reset,
    plan_copy_value,
    plan_elevation_mark,
    plan_hatch_thickness,
    plan_kitchen_inline,
    plan_purge_all,
    plan_save_separate,
)
from .headless_core_batch31b import (
    KitchenCornerRequest,
    PlaneLevelRequest,
    ReferenceMarkRequest,
    RoofDrainRequest,
    RubbleRequest,
    SaveAsBlockRequest,
    SectionSymbolRequest,
    UtilityLineRequest,
    plan_kitchen_corner,
    plan_plane_level,
    plan_reference_mark,
    plan_roof_drain,
    plan_rubble,
    plan_save_as_block,
    plan_section_symbol,
    plan_utility_line,
)

HELP_URLS = {
    "PUA": "https://izzarder.com/379", "SVS": "https://izzarder.com/111",
    "A0": "https://izzarder.com/242", "A1": "https://izzarder.com/242",
    "CV": "https://izzarder.com/307", "ELM": "https://izzarder.com/234",
    "HT": "https://izzarder.com/266", "KCI": "https://izzarder.com/236",
    "KCL": "https://izzarder.com/237", "PLM": "https://izzarder.com/235",
    "PPB": "https://izzarder.com/233", "RD": "https://izzarder.com/231",
    "RUB": "https://izzarder.com/230", "SAB": "https://izzarder.com/514",
    "SSL": "https://izzarder.com/433", "WU": "https://izzarder.com/374",
}

BLOCKED = {
    "PUA": "purge eligibility/order, SB integration, dependency cleanup, and failure rollback are unrecovered",
    "SVS": "frame discovery, filename policy, WBLOCK serialization, xref binding, and file rollback are unrecovered",
    "CV": "resource lookup, typed system-variable conversion, annotative behavior, and atomic rollback are unrecovered",
    "ELM": "level-mark geometry, scale, formatting/increment, and entity composition are unrecovered",
    "HT": "boundary side, hatch origin/angle, associativity, and exact entity properties are unrecovered",
    "KCI": "three-point semantics, cabinet modules, blocks, dimensions, and refrigerator geometry are unrecovered",
    "KCL": "corner handedness, cabinet composition, widths, blocks, and dimensions are unrecovered",
    "PLM": "symbol insertion transform, attributes, numeric increment, and resource semantics are unrecovered",
    "PPB": "corner order, rectangle construction, text placement, and scale transforms are unrecovered",
    "RD": "diameter-to-symbol transform, resource decomposition, attributes, and repeat behavior are unrecovered",
    "RUB": "authoritative resource, orientation transform, repetition, spacing, and clipping are unrecovered",
    "SAB": "whole-file normalization, dependency cleanup, three-pass purge, save version, and file rollback are unrecovered",
    "SSL": "section-marker geometry, direction, labels, sizes, colors, and text properties are unrecovered",
    "WU": "exact linetype resource/name, vertices, widths, scale, and property assignment are unrecovered",
}


class LiveAxisEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    document_name: str
    snap_angle_radians: float
    state_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveA0ExecuteRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    request: AxisResetRequest
    expected_source: LiveAxisEvidence
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveA1ExecuteRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    request: AxisChangeRequest
    expected_source: LiveAxisEvidence
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LiveBatch31Result(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    document_name: str
    command_alias: str
    before_snap_angle_radians: float
    after_snap_angle_radians: float
    undo_mark_opened: bool
    undo_mark_closed: bool
    postcondition_verified: bool


def _fingerprint(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


def _drawing(name: str) -> Any:
    import win32com.client

    app = win32com.client.GetActiveObject("ZWCAD.Application.2026")
    matches = [doc for doc in app.Documents if str(doc.Name).casefold() == name.casefold()]
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one open document named {name!r}, found {len(matches)}")
    matches[0].Activate()
    return matches[0]


def _plan(request: Any) -> Any:
    planners = {
        PurgeAllRequest: plan_purge_all, SaveSeparateRequest: plan_save_separate,
        AxisResetRequest: plan_axis_reset, AxisChangeRequest: plan_axis_change,
        CopyValueRequest: plan_copy_value, ElevationMarkRequest: plan_elevation_mark,
        HatchThicknessRequest: plan_hatch_thickness, KitchenInlineRequest: plan_kitchen_inline,
        KitchenCornerRequest: plan_kitchen_corner, PlaneLevelRequest: plan_plane_level,
        ReferenceMarkRequest: plan_reference_mark, RoofDrainRequest: plan_roof_drain,
        RubbleRequest: plan_rubble, SaveAsBlockRequest: plan_save_as_block,
        SectionSymbolRequest: plan_section_symbol, UtilityLineRequest: plan_utility_line,
    }
    for request_type, planner in planners.items():
        if isinstance(request, request_type):
            return planner(request)
    raise TypeError(f"unsupported Batch 31 request: {type(request).__name__}")


def _axis_evidence(doc: Any) -> LiveAxisEvidence:
    angle = float(doc.GetVariable("SNAPANG"))
    state = {"document_name": str(doc.Name), "snap_angle_radians": angle}
    return LiveAxisEvidence(**state, state_fingerprint=_fingerprint(state))


def _axis_payload(request: Any, plan: Any, source: LiveAxisEvidence) -> dict[str, Any]:
    return {
        "command_alias": plan.command_alias,
        "document_name": request.document_id,
        "request": request.model_dump(mode="json"),
        "plan": plan.model_dump(mode="json"),
        "expected_source": source.model_dump(mode="json"),
    }


def _preview_axis(request: AxisResetRequest | AxisChangeRequest) -> dict[str, Any]:
    if not request.dry_run:
        raise ValueError("live preview requires dry_run=true")
    plan = _plan(request)
    doc = _drawing(request.document_id)
    source = _axis_evidence(doc)
    if not math.isclose(source.snap_angle_radians, request.source.snap_angle_radians, rel_tol=0, abs_tol=1e-12):
        raise ValueError("Batch 31 live SNAPANG does not match the request source snapshot")
    payload = _axis_payload(request, plan, source)
    return {
        **payload,
        "approval_fingerprint": _fingerprint(payload),
        "mutation": True,
        "live_executable": True,
        "official_help_url": HELP_URLS[plan.command_alias],
        "scope_note": "only SNAPANG is changed; no entity, layer, xref, file, or other system variable is touched",
    }


def _preview_blocked(request: Any) -> dict[str, Any]:
    if not request.dry_run:
        raise ValueError("live preview requires dry_run=true")
    plan = _plan(request)
    payload = {
        "command_alias": plan.command_alias,
        "document_name": request.document_id,
        "request": request.model_dump(mode="json"),
        "plan": plan.model_dump(mode="json"),
    }
    return {
        **payload,
        "approval_fingerprint": _fingerprint(payload),
        "mutation": False,
        "live_executable": False,
        "blocked_reason": BLOCKED[plan.command_alias],
        "official_help_url": HELP_URLS[plan.command_alias],
    }


def preview_live_a0(request: AxisResetRequest) -> dict[str, Any]: return _preview_axis(request)
def preview_live_a1(request: AxisChangeRequest) -> dict[str, Any]: return _preview_axis(request)


def _execute_axis(request: Any, expected: LiveAxisEvidence, approval: str) -> LiveBatch31Result:
    plan = _plan(request)
    payload = _axis_payload(request, plan, expected)
    if approval != _fingerprint(payload):
        raise ValueError("approval fingerprint does not match the exact Batch 31 SNAPANG preview")
    doc = _drawing(request.document_id)
    current = _axis_evidence(doc)
    if current != expected:
        raise ValueError("Batch 31 SNAPANG state no longer matches the approved preview")
    target = float(plan.result.snap_angle_radians)
    doc.StartUndoMark()
    closed = False
    try:
        doc.SetVariable("SNAPANG", target)
    finally:
        doc.EndUndoMark()
        closed = True
    actual = float(doc.GetVariable("SNAPANG"))
    if not math.isclose(actual, target, rel_tol=0, abs_tol=1e-12):
        raise RuntimeError(f"{plan.command_alias} SNAPANG postcondition failed")
    return LiveBatch31Result(
        document_name=str(doc.Name), command_alias=plan.command_alias,
        before_snap_angle_radians=current.snap_angle_radians,
        after_snap_angle_radians=actual, undo_mark_opened=True,
        undo_mark_closed=closed, postcondition_verified=True,
    )


def execute_live_a0(request: LiveA0ExecuteRequest) -> LiveBatch31Result:
    return _execute_axis(request.request, request.expected_source, request.approval_fingerprint)


def execute_live_a1(request: LiveA1ExecuteRequest) -> LiveBatch31Result:
    return _execute_axis(request.request, request.expected_source, request.approval_fingerprint)


def preview_live_pua(request: PurgeAllRequest) -> dict[str, Any]: return _preview_blocked(request)
def preview_live_svs(request: SaveSeparateRequest) -> dict[str, Any]: return _preview_blocked(request)
def preview_live_cv(request: CopyValueRequest) -> dict[str, Any]: return _preview_blocked(request)
def preview_live_elm(request: ElevationMarkRequest) -> dict[str, Any]: return _preview_blocked(request)
def preview_live_ht(request: HatchThicknessRequest) -> dict[str, Any]: return _preview_blocked(request)
def preview_live_kci(request: KitchenInlineRequest) -> dict[str, Any]: return _preview_blocked(request)
def preview_live_kcl(request: KitchenCornerRequest) -> dict[str, Any]: return _preview_blocked(request)
def preview_live_plm(request: PlaneLevelRequest) -> dict[str, Any]: return _preview_blocked(request)
def preview_live_ppb(request: ReferenceMarkRequest) -> dict[str, Any]: return _preview_blocked(request)
def preview_live_rd(request: RoofDrainRequest) -> dict[str, Any]: return _preview_blocked(request)
def preview_live_rub(request: RubbleRequest) -> dict[str, Any]: return _preview_blocked(request)
def preview_live_sab(request: SaveAsBlockRequest) -> dict[str, Any]: return _preview_blocked(request)
def preview_live_ssl(request: SectionSymbolRequest) -> dict[str, Any]: return _preview_blocked(request)
def preview_live_wu(request: UtilityLineRequest) -> dict[str, Any]: return _preview_blocked(request)


def register_live_batch31_tools(mcp: FastMCP) -> None:
    preview = ToolAnnotations(title="Preview live xiCAD Batch 31 operation", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
    execute = ToolAnnotations(title="Execute live xiCAD Batch 31 SNAPANG operation", readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=False)
    functions = {
        "pua": preview_live_pua, "svs": preview_live_svs, "a0": preview_live_a0,
        "a1": preview_live_a1, "cv": preview_live_cv, "elm": preview_live_elm,
        "ht": preview_live_ht, "kci": preview_live_kci, "kcl": preview_live_kcl,
        "plm": preview_live_plm, "ppb": preview_live_ppb, "rd": preview_live_rd,
        "rub": preview_live_rub, "sab": preview_live_sab, "ssl": preview_live_ssl,
        "wu": preview_live_wu,
    }
    for alias, function in functions.items():
        mcp.tool(name=f"xicad_preview_live_{alias}", annotations=preview)(function)
    mcp.tool(name="xicad_execute_live_a0", annotations=execute)(execute_live_a0)
    mcp.tool(name="xicad_execute_live_a1", annotations=execute)(execute_live_a1)
