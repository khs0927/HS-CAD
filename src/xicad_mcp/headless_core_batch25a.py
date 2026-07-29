"""Evidence-bounded dialog-free planners for xiCAD batch 25A."""

from __future__ import annotations

import hashlib
import json
import math
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .headless_core_batch1 import Approval, Point3D


class EvidenceLevel(StrEnum):
    DCL_EXPLICIT_POLICY = "shortcut_plus_dcl_explicit_policy_not_legacy_equivalent"
    DCL_CONFIG_EXPLICIT_GEOMETRY = "shortcut_plus_dcl_config_explicit_geometry_not_legacy_equivalent"
    DATA_CONFIG_EXPLICIT_SELECTION = "shortcut_plus_data_config_explicit_selection_not_legacy_equivalent"
    EXTERNAL_PROGRAM_EXPLICIT_TEXT = "shortcut_plus_external_program_explicit_text_not_legacy_equivalent"
    SHORTCUT_EXPLICIT_SNAPSHOT = "shortcut_only_explicit_snapshot_not_legacy_equivalent"


class ContractRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    document_id: str = Field(min_length=1)
    dry_run: bool = True
    approval: Approval = Approval()

    def fingerprint(self) -> str:
        payload = self.model_dump(mode="json", exclude={"dry_run", "approval"})
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()

    @model_validator(mode="after")
    def validate_approval(self) -> ContractRequest:
        if not self.dry_run and (not self.approval.approved or self.approval.fingerprint != self.fingerprint()):
            raise ValueError("execution requires an exact approval fingerprint")
        return self


class Batch25APlan(BaseModel):
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


class TextCreate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    text: str = Field(min_length=1)
    insertion_point: Point3D
    layer: str = Field(min_length=1)
    text_height: float = Field(gt=0)
    rotation_degrees: float = Field(default=0, ge=0, lt=360)


class SlopeFormat(StrEnum):
    PERCENT = "percent"
    VERTICAL_RATIO = "vertical_ratio"
    TEN_BASE_RATIO = "ten_base_ratio"
    RECIPROCAL = "reciprocal"


class SlopeRequest(ContractRequest):
    start: Point3D
    end: Point3D
    format: SlopeFormat
    decimal_places: int = Field(default=2, ge=0, le=8)
    prefix: str = ""
    text_insertion_point: Point3D
    layer: str = Field(min_length=1)
    text_height: float = Field(gt=0)
    align_to_slope: bool = True
    triangle_vertices: tuple[Point3D, ...] = ()

    @model_validator(mode="after")
    def validate_geometry(self) -> SlopeRequest:
        run = self.end.x - self.start.x
        rise = self.end.y - self.start.y
        if run == 0:
            raise ValueError("SL requires non-zero horizontal run")
        if self.format is SlopeFormat.RECIPROCAL and rise == 0:
            raise ValueError("SL reciprocal format requires non-zero rise")
        if self.triangle_vertices and len(self.triangle_vertices) != 3:
            raise ValueError("SL triangle_vertices must contain exactly three points")
        return self


class SlopePlan(Batch25APlan):
    run: float
    rise: float
    text: TextCreate
    triangle_vertices: tuple[Point3D, ...]


def plan_slope(request: SlopeRequest) -> SlopePlan:
    run = request.end.x - request.start.x
    rise = request.end.y - request.start.y
    ratio = Decimal(str(rise)) / Decimal(str(run))
    values = {
        SlopeFormat.PERCENT: (ratio * 100, "%"),
        SlopeFormat.VERTICAL_RATIO: (ratio, "1:"),
        SlopeFormat.TEN_BASE_RATIO: (ratio * 10, "10:"),
        SlopeFormat.RECIPROCAL: (Decimal(1) / ratio, "1:"),
    }
    value, marker = values[request.format]
    rendered = format(value.quantize(Decimal(1).scaleb(-request.decimal_places), rounding=ROUND_HALF_UP), "f")
    text = request.prefix + (rendered + marker if request.format is SlopeFormat.PERCENT else marker + rendered)
    rotation = math.degrees(math.atan2(rise, run)) % 360 if request.align_to_slope else 0
    return SlopePlan(
        command_alias="SL", legacy_symbol="xiSLOPE", document_id=request.document_id,
        dry_run=request.dry_run, request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcut plus xi0320 DCL slope controls",
        semantic_gaps=("legacy point acquisition and triangle construction unavailable", "2x4 text behavior unavailable", "numeric precision is explicit replacement policy"),
        evidence_level=EvidenceLevel.DCL_EXPLICIT_POLICY, run=run, rise=rise,
        text=TextCreate(text=text, insertion_point=request.text_insertion_point, layer=request.layer, text_height=request.text_height, rotation_degrees=rotation),
        triangle_vertices=request.triangle_vertices,
    )


class ExactGraphicKind(StrEnum):
    LINE = "LINE"
    POLYLINE = "POLYLINE"
    TEXT = "TEXT"
    HATCH = "HATCH"


class ExactGraphic(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    kind: ExactGraphicKind
    layer: str = Field(min_length=1)
    points: tuple[Point3D, ...] = ()
    text: str | None = None
    text_height: float | None = Field(default=None, gt=0)
    boundary_handles: tuple[str, ...] = ()
    hatch_pattern: str | None = None
    hatch_scale: float | None = Field(default=None, gt=0)
    hatch_angle_degrees: float | None = None

    @model_validator(mode="after")
    def validate_kind(self) -> ExactGraphic:
        if self.kind is ExactGraphicKind.LINE and len(self.points) != 2:
            raise ValueError("LINE requires two points")
        if self.kind is ExactGraphicKind.POLYLINE and len(self.points) < 2:
            raise ValueError("POLYLINE requires at least two points")
        if self.kind is ExactGraphicKind.TEXT and (len(self.points) != 1 or not self.text or self.text_height is None):
            raise ValueError("TEXT requires one point, text, and text_height")
        if self.kind is ExactGraphicKind.HATCH and (not self.boundary_handles or not self.hatch_pattern or self.hatch_scale is None):
            raise ValueError("HATCH requires boundary handles, pattern, and scale")
        return self


class EnergyAreaTableRequest(ContractRequest):
    source_handles: tuple[str, ...] = Field(min_length=1)
    result_with_legend: bool
    unit_placement: str = Field(min_length=1)
    elevation_table_scale: float = Field(gt=0)
    plan_table_scale: float = Field(gt=0)
    excluded_layers: tuple[str, ...] = ()
    exact_graphics: tuple[ExactGraphic, ...] = Field(min_length=1)


class EnergyAreaTablePlan(Batch25APlan):
    source_handles: tuple[str, ...]
    result_with_legend: bool
    unit_placement: str
    elevation_table_scale: float
    plan_table_scale: float
    excluded_layers: tuple[str, ...]
    creates: tuple[ExactGraphic, ...]


def plan_energy_area_table(request: EnergyAreaTableRequest) -> EnergyAreaTablePlan:
    return EnergyAreaTablePlan(
        command_alias="ZAE", legacy_symbol="xiZareaElev", document_id=request.document_id,
        dry_run=request.dry_run, request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcut plus xi0388 DCL and /xiZareaElev config",
        semantic_gaps=("compiled area classification and summation unavailable", "layer-category hatch mapping unavailable", "table and hatch geometry must be reviewed upstream"),
        evidence_level=EvidenceLevel.DCL_CONFIG_EXPLICIT_GEOMETRY,
        source_handles=request.source_handles, result_with_legend=request.result_with_legend,
        unit_placement=request.unit_placement, elevation_table_scale=request.elevation_table_scale,
        plan_table_scale=request.plan_table_scale, excluded_layers=request.excluded_layers,
        creates=request.exact_graphics,
    )


class CommonTextRequest(ContractRequest):
    catalog_group: int = Field(ge=1, le=12)
    catalog_index: int = Field(ge=0)
    catalog_text: str = Field(min_length=1)
    insertion_point: Point3D
    layer: str = Field(min_length=1)
    text_height: float = Field(gt=0)
    rotation_degrees: float = Field(default=0, ge=0, lt=360)


class CommonTextPlan(Batch25APlan):
    catalog_group: int
    catalog_index: int
    create: TextCreate


def plan_common_text(request: CommonTextRequest) -> CommonTextPlan:
    return CommonTextPlan(
        command_alias="QT", legacy_symbol="xiCommonTxt", document_id=request.document_id,
        dry_run=request.dry_run, request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcut plus xiCommonText.txt groups and /xiCommonTxt config",
        semantic_gaps=("legacy generated dialog and editing workflow unavailable", "catalog file mutation is intentionally excluded", "text style/width defaults are not decoded from opaque config"),
        evidence_level=EvidenceLevel.DATA_CONFIG_EXPLICIT_SELECTION,
        catalog_group=request.catalog_group, catalog_index=request.catalog_index,
        create=TextCreate(text=request.catalog_text, insertion_point=request.insertion_point, layer=request.layer, text_height=request.text_height, rotation_degrees=request.rotation_degrees),
    )


class SpecialCharacterRequest(ContractRequest):
    characters: str = Field(min_length=1)
    insertion_point: Point3D
    layer: str = Field(min_length=1)
    text_height: float = Field(gt=0)


def plan_special_character(request: SpecialCharacterRequest) -> CommonTextPlan:
    return CommonTextPlan(
        command_alias="QW", legacy_symbol="xiQickSpecialChar", document_id=request.document_id,
        dry_run=request.dry_run, request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcut plus SpecialChar.exe and position-only SpecialChar.ini",
        semantic_gaps=("external-program IPC and character palette unavailable", "legacy font/encoding conversion unavailable", "character choice is explicit Unicode input"),
        evidence_level=EvidenceLevel.EXTERNAL_PROGRAM_EXPLICIT_TEXT,
        catalog_group=0, catalog_index=0,
        create=TextCreate(text=request.characters, insertion_point=request.insertion_point, layer=request.layer, text_height=request.text_height),
    )


class NumericTextSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_handle: str = Field(min_length=1)
    prefix: str = ""
    value: int
    suffix: str = ""
    minimum_digits: int = Field(default=1, ge=1, le=32)


class NumberedPlacement(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    insertion_point: Point3D
    layer: str = Field(min_length=1)
    text_height: float = Field(gt=0)
    rotation_degrees: float = Field(default=0, ge=0, lt=360)


class TextPointIncrementRequest(ContractRequest):
    source: NumericTextSnapshot
    increment: int
    placements: tuple[NumberedPlacement, ...] = Field(min_length=1)


class TextPointIncrementPlan(Batch25APlan):
    source_handle: str
    creates: tuple[TextCreate, ...]


def plan_text_point_increment(request: TextPointIncrementRequest) -> TextPointIncrementPlan:
    creates = []
    for index, placement in enumerate(request.placements, 1):
        value = request.source.value + request.increment * index
        sign = "-" if value < 0 else ""
        number = sign + str(abs(value)).zfill(request.source.minimum_digits)
        creates.append(TextCreate(text=request.source.prefix + number + request.source.suffix, **placement.model_dump()))
    return TextPointIncrementPlan(
        command_alias="TIP", legacy_symbol="xiTextPointInc", document_id=request.document_id,
        dry_run=request.dry_run, request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcut: incrementing numeric text copy with specified positions",
        semantic_gaps=("legacy numeric-token discovery unavailable", "entity type/style inheritance unavailable", "increment start and zero-padding are explicit policy"),
        evidence_level=EvidenceLevel.SHORTCUT_EXPLICIT_SNAPSHOT,
        source_handle=request.source.source_handle, creates=tuple(creates),
    )


class ObjectTextTarget(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    object_handle: str = Field(min_length=1)
    anchor: Point3D
    tangent_degrees: float = Field(ge=0, lt=360)


class TextOnObjectRequest(ContractRequest):
    text: str = Field(min_length=1)
    targets: tuple[ObjectTextTarget, ...] = Field(min_length=1)
    normal_offset: float = 0
    layer: str = Field(min_length=1)
    text_height: float = Field(gt=0)
    align_to_object: bool = True


class ObjectTextCreate(TextCreate):
    object_handle: str


class TextOnObjectPlan(Batch25APlan):
    creates: tuple[ObjectTextCreate, ...]


def plan_text_on_object(request: TextOnObjectRequest) -> TextOnObjectPlan:
    creates = []
    for target in request.targets:
        normal = math.radians(target.tangent_degrees + 90)
        point = Point3D(x=target.anchor.x + request.normal_offset * math.cos(normal), y=target.anchor.y + request.normal_offset * math.sin(normal), z=target.anchor.z)
        creates.append(ObjectTextCreate(object_handle=target.object_handle, text=request.text, insertion_point=point, layer=request.layer, text_height=request.text_height, rotation_degrees=target.tangent_degrees if request.align_to_object else 0))
    return TextOnObjectPlan(
        command_alias="TOO", legacy_symbol="xiTextOnObj", document_id=request.document_id,
        dry_run=request.dry_run, request_fingerprint=request.fingerprint(),
        semantic_evidence="current/frozen shortcut: place text attached to objects",
        semantic_gaps=("supported object types and closest-point selection unavailable", "legacy attachment/reactor behavior unavailable", "anchor/tangent snapshots and offset policy are explicit"),
        evidence_level=EvidenceLevel.SHORTCUT_EXPLICIT_SNAPSHOT, creates=tuple(creates),
    )


def register_headless_core_batch25a_tools(mcp: Any) -> None:
    from mcp.types import ToolAnnotations

    annotations = ToolAnnotations(title="xiCAD Headless Core Batch 25A Planner", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
    for name, function in (
        ("xicad_plan_sl", plan_slope), ("xicad_plan_zae", plan_energy_area_table),
        ("xicad_plan_qt", plan_common_text), ("xicad_plan_qw", plan_special_character),
        ("xicad_plan_tip", plan_text_point_increment), ("xicad_plan_too", plan_text_on_object),
    ):
        mcp.tool(name=name, annotations=annotations)(function)
