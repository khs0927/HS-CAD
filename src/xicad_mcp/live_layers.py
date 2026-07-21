from __future__ import annotations

import hashlib
import json
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .headless_core_batch1 import (
    LayerAffixMode,
    LayerAffixRequest,
    LayerNameRef,
    LayerRenamePair,
    plan_layer_affix,
)


class LiveLayerAffixPreviewRequest(BaseModel):
    """Resolve an LPP/LPS request against one exact open drawing."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    document_name: str = Field(min_length=1)
    mode: LayerAffixMode
    affix: str = Field(min_length=1, max_length=128)
    target_names: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def reject_protected_targets(self) -> LiveLayerAffixPreviewRequest:
        protected = {"0", "defpoints"}
        for name in self.target_names:
            if name.casefold() in protected:
                raise ValueError(f"protected CAD layer cannot be renamed: {name}")
            if "|" in name:
                raise ValueError(f"xref-dependent layer cannot be renamed: {name}")
        return self


class LiveLayerAffixExecuteRequest(LiveLayerAffixPreviewRequest):
    expected_rename_pairs: tuple[LayerRenamePair, ...] = Field(min_length=1)
    approval_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def expected_fingerprint(self) -> str:
        return _fingerprint(self.model_dump(mode="json", exclude={"approval_fingerprint"}))


class LayerRenameEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source: str
    target: str
    source_absent: bool
    target_present: bool


class LiveLayerAffixResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    document_name: str
    command_alias: str
    renamed_pairs: tuple[LayerRenamePair, ...]
    evidence: tuple[LayerRenameEvidence, ...]
    undo_mark_opened: bool
    undo_mark_closed: bool
    postcondition_verified: bool


def _fingerprint(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


def _drawing(document_name: str) -> Any:
    # Keep pywin32 optional for CAD-free contract imports and unit tests.
    import win32com.client

    app = win32com.client.GetActiveObject("ZWCAD.Application.2026")
    matches = [doc for doc in app.Documents if str(doc.Name).casefold() == document_name.casefold()]
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one open document named {document_name!r}, found {len(matches)}")
    doc = matches[0]
    doc.Activate()
    return doc


def _layers(doc: Any) -> tuple[LayerNameRef, ...]:
    result: list[LayerNameRef] = []
    for layer in doc.Layers:
        name = str(layer.Name)
        result.append(
            LayerNameRef(
                name=name,
                system=name.casefold() in {"0", "defpoints"},
                xref_dependent="|" in name,
            )
        )
    return tuple(result)


def _plan(request: LiveLayerAffixPreviewRequest, doc: Any):
    return plan_layer_affix(
        LayerAffixRequest(
            document_id=str(doc.Name),
            mode=request.mode,
            affix=request.affix,
            target_names=request.target_names,
            preserve_names=("0", "Defpoints"),
            dry_run=True,
        ),
        _layers(doc),
    )


def preview_live_layer_affix(request: LiveLayerAffixPreviewRequest) -> dict[str, Any]:
    doc = _drawing(request.document_name)
    plan = _plan(request, doc)
    if plan.skipped_names:
        raise ValueError(f"protected layers cannot be renamed: {list(plan.skipped_names)}")
    if not plan.rename_pairs:
        raise ValueError("layer affix request resolved to no renames")
    payload = {
        **request.model_dump(mode="json"),
        "expected_rename_pairs": [pair.model_dump(mode="json") for pair in plan.rename_pairs],
    }
    return {
        **payload,
        "command_alias": plan.command_alias,
        "approval_fingerprint": _fingerprint(payload),
        "mutation": True,
    }


def execute_live_layer_affix(
    request: LiveLayerAffixExecuteRequest,
    *,
    allowed_mode: LayerAffixMode | None = None,
) -> LiveLayerAffixResult:
    if allowed_mode is not None and request.mode is not allowed_mode:
        alias = "LPP" if allowed_mode is LayerAffixMode.PREFIX else "LPS"
        raise ValueError(f"this tool only executes {alias}")
    if request.approval_fingerprint != request.expected_fingerprint():
        raise ValueError("approval fingerprint does not match the exact layer affix request")

    doc = _drawing(request.document_name)
    plan = _plan(request, doc)
    if plan.rename_pairs != request.expected_rename_pairs:
        raise ValueError("layer inventory no longer matches the approved rename plan")

    by_name = {str(layer.Name).casefold(): layer for layer in doc.Layers}
    opened = False
    closed = False
    try:
        doc.StartUndoMark()
        opened = True
        for pair in plan.rename_pairs:
            by_name[pair.source.casefold()].Name = pair.target
    finally:
        if opened:
            doc.EndUndoMark()
            closed = True

    after = {str(layer.Name).casefold() for layer in doc.Layers}
    evidence = tuple(
        LayerRenameEvidence(
            source=pair.source,
            target=pair.target,
            source_absent=pair.source.casefold() not in after,
            target_present=pair.target.casefold() in after,
        )
        for pair in plan.rename_pairs
    )
    if not evidence or not all(item.source_absent and item.target_present for item in evidence):
        raise RuntimeError("layer affix postcondition failed")
    return LiveLayerAffixResult(
        document_name=str(doc.Name),
        command_alias=plan.command_alias,
        renamed_pairs=plan.rename_pairs,
        evidence=evidence,
        undo_mark_opened=opened,
        undo_mark_closed=closed,
        postcondition_verified=True,
    )


def execute_live_lpp(request: LiveLayerAffixExecuteRequest) -> LiveLayerAffixResult:
    return execute_live_layer_affix(request, allowed_mode=LayerAffixMode.PREFIX)


def execute_live_lps(request: LiveLayerAffixExecuteRequest) -> LiveLayerAffixResult:
    return execute_live_layer_affix(request, allowed_mode=LayerAffixMode.SUFFIX)


def register_live_layer_tools(mcp: FastMCP) -> None:
    mcp.tool(
        name="xicad_preview_live_layer_affix",
        description="Validate an exact LPP/LPS layer rename plan in one named open ZWCAD drawing.",
        annotations=ToolAnnotations(
            title="Preview live xiCAD layer affix",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )(preview_live_layer_affix)
    live_write = ToolAnnotations(
        title="Execute live xiCAD layer affix",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=False,
    )
    mcp.tool(
        name="xicad_execute_live_lpp",
        description="Apply an approved prefix to exact non-system ZWCAD layer names.",
        annotations=live_write,
    )(execute_live_lpp)
    mcp.tool(
        name="xicad_execute_live_lps",
        description="Apply an approved suffix to exact non-system ZWCAD layer names.",
        annotations=live_write,
    )(execute_live_lps)
