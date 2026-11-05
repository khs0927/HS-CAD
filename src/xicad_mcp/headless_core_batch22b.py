"""Evidence-bounded dialog-free planners for xiCAD batch 22B."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .headless_core_batch1 import Approval, Point3D

Matrix4 = tuple[
    tuple[float, float, float, float],
    tuple[float, float, float, float],
    tuple[float, float, float, float],
    tuple[float, float, float, float],
]


class EvidenceLevel(StrEnum):
    DCL_AND_CONFIG_RECOVERED = "dcl_and_config_recovered"
    CONFIG_AND_SHORTCUT_ONLY = "config_and_shortcut_only_explicit_result"
    SHORTCUT_ONLY_EXPLICIT_POLICY = "shortcut_only_explicit_policy_not_legacy_equivalent"


class ContractRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    document_id: str = Field(min_length=1)
    dry_run: bool = True
    approval: Approval = Approval()

    def fingerprint(self) -> str:
        payload = self.model_dump(mode="json", exclude={"dry_run", "approval"})
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()

    @model_validator(mode="after")
    def validate_approval(self) -> ContractRequest:
        if not self.dry_run and (not self.approval.approved or self.approval.fingerprint != self.fingerprint()):
            raise ValueError("execution requires an exact approval fingerprint")
        return self


class Batch22bPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command_alias: str
    legacy_symbol: str
    document_id: str
    dry_run: bool
    request_fingerprint: str
    semantic_evidence: str
    semantic_gaps: tuple[str, ...]
    evidence_level: EvidenceLevel
    dialog_required: bool = False
    cad_mutation_tool_exposed: bool = False
    legacy_equivalence_verified_in_cad: bool = False
    production_usable: bool = False


class BoundingBox(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    minimum: Point3D
    maximum: Point3D

    @model_validator(mode="after")
    def validate_extents(self) -> BoundingBox:
        if (
            self.minimum.x > self.maximum.x
            or self.minimum.y > self.maximum.y
            or self.minimum.z > self.maximum.z
        ):
            raise ValueError("bounding-box minimum must not exceed maximum")
        return self


class ScaleAnchor(StrEnum):
    LEFT_TOP = "LTop"
    CENTER_TOP = "Top"
    RIGHT_TOP = "RTop"
    LEFT_MIDDLE = "Left"
    CENTER = "Center"
    RIGHT_MIDDLE = "Right"
    LEFT_BOTTOM = "LBtm"
    CENTER_BOTTOM = "Btm"
    RIGHT_BOTTOM = "RBtm"
    INSERTION_OR_START = "Insert"


class ScaleItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    bounds: BoundingBox
    insertion_or_start: Point3D


class ScaleTransform(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str
    base_point: Point3D
    matrix: Matrix4


class ScaleMultiRequest(ContractRequest):
    items: tuple[ScaleItem, ...] = Field(min_length=1)
    factor: float = Field(gt=0)
    anchor: ScaleAnchor

    @model_validator(mode="after")
    def validate_items(self) -> ScaleMultiRequest:
        _unique(tuple(item.handle for item in self.items), "SM")
        if self.factor == 1:
            raise ValueError("SM factor must change entity size")
        return self


class ScalePlan(Batch22bPlan):
    factor: float
    transforms: tuple[ScaleTransform, ...]


def plan_scale_multi(request: ScaleMultiRequest) -> ScalePlan:
    transforms = tuple(
        _scale_transform(item.handle, _anchor_point(item, request.anchor), request.factor) for item in request.items
    )
    return ScalePlan(
        command_alias="SM",
        legacy_symbol="xiScaleMulti",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcut plus ACAD_xi0419_d.02.dcl ten anchor keys and /xiScaleMulti config",
        semantic_gaps=("compiled entity extents rules unavailable", "second persisted config value meaning unavailable"),
        evidence_level=EvidenceLevel.DCL_AND_CONFIG_RECOVERED,
        factor=request.factor,
        transforms=transforms,
    )


class SequentialScaleItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    handle: str = Field(min_length=1)
    base_point: Point3D


class SequentialScaleRequest(ContractRequest):
    items: tuple[SequentialScaleItem, ...] = Field(min_length=1)
    remembered_factor: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_items(self) -> SequentialScaleRequest:
        _unique(tuple(item.handle for item in self.items), "SS")
        if self.remembered_factor == 1:
            raise ValueError("SS remembered_factor must change entity size")
        return self


def plan_sequential_scale(request: SequentialScaleRequest) -> ScalePlan:
    return ScalePlan(
        command_alias="SS",
        legacy_symbol="xiSCALE",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcut: remember scale factor for continuous scaling; bases explicit",
        semantic_gaps=("no command-specific DCL/config/readable source", "legacy base-point prompt/default unavailable"),
        evidence_level=EvidenceLevel.SHORTCUT_ONLY_EXPLICIT_POLICY,
        factor=request.remembered_factor,
        transforms=tuple(
            _scale_transform(item.handle, item.base_point, request.remembered_factor) for item in request.items
        ),
    )


class ProposedLine(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_boundary_handles: tuple[str, ...] = Field(min_length=2)
    start: Point3D
    end: Point3D
    layer: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_line(self) -> ProposedLine:
        if self.start == self.end:
            raise ValueError("proposed line endpoints must differ")
        _unique(self.source_boundary_handles, "WR proposal")
        return self


class WallRecoverRequest(ContractRequest):
    boundary_line_handles: tuple[str, ...] = Field(min_length=2)
    intermediate_delete_handles: tuple[str, ...] = Field(min_length=1)
    proposed_lines: tuple[ProposedLine, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_topology(self) -> WallRecoverRequest:
        _unique(self.boundary_line_handles, "WR boundary")
        _unique(self.intermediate_delete_handles, "WR delete")
        boundary = {value.casefold() for value in self.boundary_line_handles}
        deleted = {value.casefold() for value in self.intermediate_delete_handles}
        if boundary & deleted:
            raise ValueError("WR boundary lines cannot be intermediate delete targets")
        if any({value.casefold() for value in line.source_boundary_handles} != boundary for line in self.proposed_lines):
            raise ValueError("WR proposed lines must bind to the complete boundary set")
        return self


class WallRecoverPlan(Batch22bPlan):
    preserve_handles: tuple[str, ...]
    delete_handles: tuple[str, ...]
    creates: tuple[ProposedLine, ...]


def plan_wall_recover(request: WallRecoverRequest) -> WallRecoverPlan:
    return WallRecoverPlan(
        command_alias="WR",
        legacy_symbol="xiWallRecover",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcut: recover lines and delete every intermediate object",
        semantic_gaps=("wall/intersection recognition algorithm compiled", "tolerance and extension policy unavailable"),
        evidence_level=EvidenceLevel.SHORTCUT_ONLY_EXPLICIT_POLICY,
        preserve_handles=request.boundary_line_handles,
        delete_handles=request.intermediate_delete_handles,
        creates=request.proposed_lines,
    )


class SourceDisposition(StrEnum):
    MOVE = "move"
    COPY = "copy"


class BoxMoveRequest(ContractRequest):
    source_handles: tuple[str, ...] = Field(min_length=1)
    source_reference: Point3D
    target_reference: Point3D
    disposition: SourceDisposition

    @model_validator(mode="after")
    def validate_move(self) -> BoxMoveRequest:
        _unique(self.source_handles, "BMT")
        if self.source_reference == self.target_reference:
            raise ValueError("BMT source and target references must differ")
        return self


class TranslationSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str
    displacement: Point3D
    copy_entity: bool


class TranslationPlan(Batch22bPlan):
    transforms: tuple[TranslationSpec, ...]


def plan_box_move(request: BoxMoveRequest) -> TranslationPlan:
    displacement = Point3D(
        x=request.target_reference.x - request.source_reference.x,
        y=request.target_reference.y - request.source_reference.y,
        z=request.target_reference.z - request.source_reference.z,
    )
    return TranslationPlan(
        command_alias="BMT",
        legacy_symbol="xiBoxMoveTool",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcut and CAD menu: copy/move between floor plans",
        semantic_gaps=("no command-specific DCL/config/readable source", "floor-plan recognition and selection defaults unavailable"),
        evidence_level=EvidenceLevel.SHORTCUT_ONLY_EXPLICIT_POLICY,
        transforms=tuple(
            TranslationSpec(
                source_handle=handle,
                displacement=displacement,
                copy_entity=request.disposition is SourceDisposition.COPY,
            )
            for handle in request.source_handles
        ),
    )


class AnnotationEntityType(StrEnum):
    TEXT = "TEXT"
    MTEXT = "MTEXT"
    BLOCK_REFERENCE = "BLOCK_REFERENCE"


class AttributeValue(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    tag: str = Field(min_length=1)
    value: str


class ProposedScaleAnnotation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    entity_type: AnnotationEntityType
    insertion_point: Point3D
    layer: str = Field(min_length=1)
    text: str | None = None
    text_height: float | None = Field(default=None, gt=0)
    block_name: str | None = None
    attributes: tuple[AttributeValue, ...] = ()

    @model_validator(mode="after")
    def validate_payload(self) -> ProposedScaleAnnotation:
        if self.entity_type is AnnotationEntityType.BLOCK_REFERENCE:
            if not self.block_name:
                raise ValueError("block scale annotation requires block_name")
        elif self.text is None or self.text_height is None:
            raise ValueError("text scale annotation requires text and text_height")
        return self


class DynamicScaleRequest(ContractRequest):
    scale_denominator: float = Field(gt=0)
    exact_annotations: tuple[ProposedScaleAnnotation, ...] = Field(min_length=1)


class DynamicScalePlan(Batch22bPlan):
    scale_denominator: float
    creates: tuple[ProposedScaleAnnotation, ...]


def plan_dynamic_scale(request: DynamicScaleRequest) -> DynamicScalePlan:
    return DynamicScalePlan(
        command_alias="DAS",
        legacy_symbol="xiDyScale",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcut: insert live drawing scale; /xiDyScale persisted config exists",
        semantic_gaps=("config field meanings are undocumented", "dynamic linkage/entity construction is compiled"),
        evidence_level=EvidenceLevel.CONFIG_AND_SHORTCUT_ONLY,
        scale_denominator=request.scale_denominator,
        creates=request.exact_annotations,
    )


class FrameEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    frame_handle: str = Field(min_length=1)
    frame_bounds: BoundingBox
    source_reference: Point3D


class DboxAutoCopyRequest(ContractRequest):
    frame: FrameEvidence
    source_entity_handles: tuple[str, ...] = Field(min_length=1)
    target_reference_points: tuple[Point3D, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_copy(self) -> DboxAutoCopyRequest:
        _unique(self.source_entity_handles, "DBC")
        if self.frame.frame_handle.casefold() not in {value.casefold() for value in self.source_entity_handles}:
            raise ValueError("DBC source entities must include the recognized frame handle")
        if any(point == self.frame.source_reference for point in self.target_reference_points):
            raise ValueError("DBC targets must differ from source reference")
        return self


def plan_dbox_auto_copy(request: DboxAutoCopyRequest) -> TranslationPlan:
    transforms = tuple(
        TranslationSpec(
            source_handle=handle,
            displacement=Point3D(
                x=target.x - request.frame.source_reference.x,
                y=target.y - request.frame.source_reference.y,
                z=target.z - request.frame.source_reference.z,
            ),
            copy_entity=True,
        )
        for target in request.target_reference_points
        for handle in request.source_entity_handles
    )
    return TranslationPlan(
        command_alias="DBC",
        legacy_symbol="xiDboxAutoCopy",
        document_id=request.document_id,
        dry_run=request.dry_run,
        request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcut and CAD menu: automatically recognize and copy drawing border",
        semantic_gaps=("border recognition algorithm compiled", "copy-set and placement prompt defaults unavailable"),
        evidence_level=EvidenceLevel.SHORTCUT_ONLY_EXPLICIT_POLICY,
        transforms=transforms,
    )


def _anchor_point(item: ScaleItem, anchor: ScaleAnchor) -> Point3D:
    if anchor is ScaleAnchor.INSERTION_OR_START:
        return item.insertion_or_start
    x_values = {
        ScaleAnchor.LEFT_TOP: item.bounds.minimum.x,
        ScaleAnchor.LEFT_MIDDLE: item.bounds.minimum.x,
        ScaleAnchor.LEFT_BOTTOM: item.bounds.minimum.x,
        ScaleAnchor.CENTER_TOP: (item.bounds.minimum.x + item.bounds.maximum.x) / 2,
        ScaleAnchor.CENTER: (item.bounds.minimum.x + item.bounds.maximum.x) / 2,
        ScaleAnchor.CENTER_BOTTOM: (item.bounds.minimum.x + item.bounds.maximum.x) / 2,
        ScaleAnchor.RIGHT_TOP: item.bounds.maximum.x,
        ScaleAnchor.RIGHT_MIDDLE: item.bounds.maximum.x,
        ScaleAnchor.RIGHT_BOTTOM: item.bounds.maximum.x,
    }
    y_values = {
        ScaleAnchor.LEFT_BOTTOM: item.bounds.minimum.y,
        ScaleAnchor.CENTER_BOTTOM: item.bounds.minimum.y,
        ScaleAnchor.RIGHT_BOTTOM: item.bounds.minimum.y,
        ScaleAnchor.LEFT_MIDDLE: (item.bounds.minimum.y + item.bounds.maximum.y) / 2,
        ScaleAnchor.CENTER: (item.bounds.minimum.y + item.bounds.maximum.y) / 2,
        ScaleAnchor.RIGHT_MIDDLE: (item.bounds.minimum.y + item.bounds.maximum.y) / 2,
        ScaleAnchor.LEFT_TOP: item.bounds.maximum.y,
        ScaleAnchor.CENTER_TOP: item.bounds.maximum.y,
        ScaleAnchor.RIGHT_TOP: item.bounds.maximum.y,
    }
    return Point3D(x=x_values[anchor], y=y_values[anchor], z=(item.bounds.minimum.z + item.bounds.maximum.z) / 2)


def _scale_transform(handle: str, base: Point3D, factor: float) -> ScaleTransform:
    return ScaleTransform(
        source_handle=handle,
        base_point=base,
        matrix=(
            (factor, 0, 0, (1 - factor) * base.x),
            (0, factor, 0, (1 - factor) * base.y),
            (0, 0, factor, (1 - factor) * base.z),
            (0, 0, 0, 1),
        ),
    )


def _unique(handles: tuple[str, ...], alias: str) -> None:
    folded = [handle.casefold() for handle in handles]
    if len(folded) != len(set(folded)):
        raise ValueError(f"{alias} handles must be unique")


def register_headless_core_batch22b_tools(mcp: Any) -> None:
    from mcp.types import ToolAnnotations

    annotations = ToolAnnotations(
        title="xiCAD Headless Core Batch 22B Planner",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    tools = (
        ("xicad_plan_sm", plan_scale_multi),
        ("xicad_plan_ss", plan_sequential_scale),
        ("xicad_plan_wr", plan_wall_recover),
        ("xicad_plan_bmt", plan_box_move),
        ("xicad_plan_das", plan_dynamic_scale),
        ("xicad_plan_dbc", plan_dbox_auto_copy),
    )
    for name, function in tools:
        mcp.tool(name=name, annotations=annotations)(function)
