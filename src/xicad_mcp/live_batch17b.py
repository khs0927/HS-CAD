from __future__ import annotations

import hashlib
import json
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .headless_core_batch14 import GeometrySnapshot
from .headless_core_batch17 import (
    ParkingRequest,
    PartialZoomRequest,
    QRCodeRequest,
    ScaleBarRequest,
    StairRequest,
    SteelBeamRequest,
    plan_parking,
    plan_partial_zoom,
    plan_qr_code,
    plan_scale_bar,
    plan_stair,
    plan_steel_beam,
)

EVIDENCE = {
    "PK": "xiShortkey xipk=주차장 그리기; xiConfig /xiParking includes handicap/arrow/angle/layer options",
    "PZ": "xiShortkey xiPartialZoom=부분 확대도; xiConfig /xiPartialZoom includes circle/mode/layer/color/linetype",
    "QRC": "xiShortkey xiQRcode=QR 코드 그리기; binary implementation only",
    "SCB": "xiShortkey xiScaleBar=축척 막대 그리기; binary implementation only",
    "STB": "xiShortkey xiSTB=철골 보 그리기; binary implementation only",
    "STC": "xiShortkey xiSTC=계단 입면; xiConfig /xiSTC includes handrail/slab/finish/layers",
}

BLOCKED = {
    "PK": "planner omits rotated stalls, aisle, handicap marks, and direction arrows",
    "PZ": "planner omits boundary rendering, source-type preservation, and block ownership/naming",
    "QRC": "planner omits module-row axis direction and cell merge/output geometry policy",
    "SCB": "planner omits baseline, tick height, and label insertion points",
    "STB": "planner centerline/mark omit beam edges, offsets, web, and connection symbols",
    "STC": "planner diagonal points omit tread/riser turns, slab, finish, numbering, and handrail geometry",
}


def _fingerprint(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


def _blocked_preview(alias: str, request: Any, plan: Any, **evidence: Any) -> dict[str, Any]:
    if not request.dry_run:
        raise ValueError("live preview requires the structured request in dry-run mode")
    payload = {
        "command_alias": alias,
        "request": request.model_dump(mode="json"),
        "plan": plan.model_dump(mode="json"),
        **evidence,
    }
    return {
        **payload,
        "approval_fingerprint": _fingerprint(payload),
        "mutation": False,
        "live_executable": False,
        "source_evidence": EVIDENCE[alias],
        "blocked_reason": BLOCKED[alias],
    }


def preview_live_pk(request: ParkingRequest) -> dict[str, Any]:
    return _blocked_preview("PK", request, plan_parking(request))


def preview_live_pz(request: PartialZoomRequest, snapshots: tuple[GeometrySnapshot, ...]) -> dict[str, Any]:
    return _blocked_preview(
        "PZ",
        request,
        plan_partial_zoom(request, snapshots),
        expected_sources=[item.model_dump(mode="json") for item in snapshots],
    )


def preview_live_qrc(request: QRCodeRequest) -> dict[str, Any]:
    payload_digest = "sha256:" + hashlib.sha256(request.payload.encode()).hexdigest()
    return _blocked_preview(
        "QRC",
        request,
        plan_qr_code(request),
        payload_digest_matches=payload_digest.casefold() == request.payload_digest.casefold(),
    )


def preview_live_scb(request: ScaleBarRequest) -> dict[str, Any]:
    return _blocked_preview("SCB", request, plan_scale_bar(request))


def preview_live_stb(request: SteelBeamRequest) -> dict[str, Any]:
    return _blocked_preview("STB", request, plan_steel_beam(request))


def preview_live_stc(request: StairRequest) -> dict[str, Any]:
    return _blocked_preview("STC", request, plan_stair(request))


def register_live_batch17b_tools(mcp: FastMCP) -> None:
    preview = ToolAnnotations(
        title="Preview blocked xiCAD Batch 17B operation",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    registrations = (
        ("xicad_preview_live_pk", preview_live_pk),
        ("xicad_preview_live_pz", preview_live_pz),
        ("xicad_preview_live_qrc", preview_live_qrc),
        ("xicad_preview_live_scb", preview_live_scb),
        ("xicad_preview_live_stb", preview_live_stb),
        ("xicad_preview_live_stc", preview_live_stc),
    )
    for name, function in registrations:
        mcp.tool(name=name, annotations=preview)(function)
