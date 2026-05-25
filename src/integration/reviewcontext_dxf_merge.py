from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

try:
    from shapely.geometry import LineString, Point, Polygon, shape
    from shapely.strtree import STRtree
except Exception:  # pragma: no cover - optional on minimal environments
    LineString = Point = Polygon = shape = STRtree = None  # type: ignore


@dataclass
class DrawingObject:
    id: str
    layer: str
    object_type: str
    semantic_type: str | None = None
    geometry: Any = None
    bbox: tuple[float, float, float, float] | None = None
    properties: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.5

    def __post_init__(self) -> None:
        if self.bbox is None and self.geometry is not None:
            try:
                self.bbox = tuple(float(v) for v in self.geometry.bounds)  # type: ignore[assignment]
            except Exception:
                self.bbox = None


@dataclass
class ReviewContext:
    drawing_id: str
    units: str = "unknown"
    scale: float | None = None
    space: str = "model"
    objects: list[DrawingObject] = field(default_factory=list)
    graph_reports: dict[str, Any] = field(default_factory=dict)
    spatial: "SpatialQueryService | None" = None

    def attach_spatial(self) -> None:
        self.spatial = SpatialQueryService(self.objects)

    @property
    def rooms(self) -> list[DrawingObject]:
        return [o for o in self.objects if o.semantic_type == "room"]

    @property
    def texts(self) -> list[DrawingObject]:
        return [o for o in self.objects if o.object_type == "text"]

    @property
    def beams(self) -> list[DrawingObject]:
        return [o for o in self.objects if o.semantic_type in {"beam", "steel_beam"}]


@dataclass
class RuleViolation:
    id: str
    code: str
    severity: str
    message: str
    target_object_id: str | None = None
    evidence_ids: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionCandidate:
    id: str
    action_type: str
    target_object_id: str | None = None
    target_object_ids: list[str] = field(default_factory=list)
    params: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.7
    reason: str = ""
    rule_code: str = ""
    requires_user_approval: bool = True
    dry_run: bool = True


class SpatialQueryService:
    def __init__(self, objects: list[DrawingObject]):
        self.objects = [o for o in objects if o.geometry is not None]
        self._tree = None
        self._geom_to_object: dict[int, DrawingObject] = {}
        if STRtree is not None and self.objects:
            try:
                geometries = [o.geometry for o in self.objects]
                self._tree = STRtree(geometries)
                self._geom_to_object = {id(g): o for g, o in zip(geometries, self.objects)}
            except Exception:
                self._tree = None

    def _matches(self, obj: DrawingObject, object_type: str | None = None, layer_like: str | None = None) -> bool:
        if object_type and obj.object_type != object_type and obj.semantic_type != object_type:
            return False
        if layer_like and layer_like.lower() not in (obj.layer or "").lower():
            return False
        return True

    def find_inside(self, container_geometry: Any, object_type: str | None = None, layer_like: str | None = None) -> list[DrawingObject]:
        if container_geometry is None:
            return []
        out: list[DrawingObject] = []
        for obj in self.objects:
            if not self._matches(obj, object_type, layer_like):
                continue
            try:
                if container_geometry.contains(obj.geometry) or container_geometry.covers(obj.geometry):
                    out.append(obj)
            except Exception:
                pass
        return out

    def find_nearby(self, target_geometry: Any, object_type: str | None = None, radius: float = 500) -> list[DrawingObject]:
        if target_geometry is None:
            return []
        out: list[DrawingObject] = []
        for obj in self.objects:
            if not self._matches(obj, object_type):
                continue
            try:
                if obj.geometry is not target_geometry and target_geometry.distance(obj.geometry) <= radius:
                    out.append(obj)
            except Exception:
                pass
        return out


class FileizedReviewAdapter:
    @classmethod
    def from_json(cls, path: str | Path) -> ReviewContext:
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReviewContext:
        ctx = ReviewContext(
            drawing_id=str(data.get("file_id") or data.get("drawing_id") or "fileized_drawing"),
            units=str(data.get("units") or data.get("metadata", {}).get("units") or "unknown"),
            scale=data.get("scale") or data.get("metadata", {}).get("scale"),
            graph_reports={
                "source": "fileized_dxf_record",
                "engine": data.get("engine"),
                "source_path": data.get("source_path"),
                "metadata": data.get("metadata") or {},
                "warnings": data.get("warnings") or [],
            },
        )
        for idx, raw in enumerate(data.get("entities") or []):
            ctx.objects.append(cls._entity_to_object(raw, idx))
        ctx.attach_spatial()
        return ctx

    @classmethod
    def _entity_to_object(cls, raw: dict[str, Any], idx: int) -> DrawingObject:
        etype = str(raw.get("entity_type") or raw.get("type") or "object").upper()
        layer = str(raw.get("layer") or "0")
        text = str(raw.get("text") or raw.get("text_override") or "")
        semantic = cls._semantic(raw, layer, etype, text)
        object_type = "text" if etype in {"TEXT", "MTEXT"} else semantic or etype.lower()
        return DrawingObject(
            id=str(raw.get("handle") or raw.get("id") or f"ent_{idx:06d}"),
            layer=layer,
            object_type=object_type,
            semantic_type=semantic,
            geometry=cls._geometry(raw, etype),
            properties=dict(raw),
            confidence=0.9 if object_type == "text" else 0.7,
        )

    @classmethod
    def _geometry(cls, raw: dict[str, Any], etype: str) -> Any:
        if Point is None:
            return None
        if "geometry" in raw and shape is not None:
            try:
                return shape(raw["geometry"])
            except Exception:
                pass
        if etype in {"TEXT", "MTEXT", "INSERT"}:
            xy = cls._xy(raw.get("insert"))
            return Point(xy) if xy else None
        if etype == "LINE":
            a, b = cls._xy(raw.get("start")), cls._xy(raw.get("end"))
            return LineString([a, b]) if a and b and LineString is not None else None
        if etype in {"POLYLINE", "LWPOLYLINE"}:
            pts = [p for p in (cls._xy(p) for p in raw.get("points") or []) if p]
            if len(pts) >= 3 and raw.get("closed") and Polygon is not None:
                try:
                    return Polygon(pts)
                except Exception:
                    return None
            if len(pts) >= 2 and LineString is not None:
                return LineString(pts)
        return None

    @staticmethod
    def _xy(value: Any) -> tuple[float, float] | None:
        try:
            return float(value[0]), float(value[1])
        except Exception:
            return None

    @staticmethod
    def _semantic(raw: dict[str, Any], layer: str, etype: str, text: str) -> str | None:
        hay = f"{layer} {etype} {text} {raw.get('name') or ''} {raw.get('effective_name') or ''}".lower()
        if etype in {"TEXT", "MTEXT"}:
            return "text"
        if any(t in hay for t in ["dimle", "leader", "??", "??", "???"]):
            return "leader"
        if any(t in hay for t in ["col", "column", "??"]):
            return "column"
        if any(t in hay for t in ["beam", "h-", "h??", "h?", "steel", "?"]):
            return "beam"
        if any(t in hay for t in ["win", "window", "??", "??"]):
            return "window"
        if any(t in hay for t in ["door", "?"]):
            return "door"
        if any(t in hay for t in ["wall", "wal", "??", "?"]):
            return "wall"
        if etype in {"POLYLINE", "LWPOLYLINE"} and raw.get("closed") and any(t in hay for t in ["room", "rm", "area", "?", "?"]):
            return "room"
        return None


FINISH_KEYWORDS = ["??", "?", "??", "??", "????", "?????", "??", "??", "??", "??", "??", "??", "??", "????", "???", "????", "??", "??", "??", "????"]
BEAM_MARK_PATTERN = re.compile(r"(h-|sb|rh|hn|bh|h??|h?|\d{2,4}\s*[x?]\s*\d{2,4})", re.I)


class DomainReviewEngine:
    def run(self, ctx: ReviewContext) -> dict[str, Any]:
        violations: list[RuleViolation] = []
        actions: list[ActionCandidate] = []
        spatial = ctx.spatial or SpatialQueryService(ctx.objects)

        for room in ctx.rooms:
            texts = spatial.find_inside(room.geometry, object_type="text")
            if not any(any(k in str(t.properties.get("text") or "") for k in FINISH_KEYWORDS) for t in texts):
                v = RuleViolation(str(uuid.uuid4()), "ROOM_FINISH_TEXT_MISSING", "warning", "Room ??? ??/?/?? ?? ???? ????.", room.id)
                violations.append(v)
                actions.append(ActionCandidate(str(uuid.uuid4()), "ADD_FINISH_TEXT_OR_LEADER", room.id, reason=v.message, rule_code=v.code))

        for beam in ctx.beams:
            near = spatial.find_nearby(beam.geometry, radius=500)
            ok = any(o.semantic_type == "leader" or BEAM_MARK_PATTERN.search(str(o.properties.get("text") or "")) for o in near)
            if not ok:
                v = RuleViolation(str(uuid.uuid4()), "STEEL_BEAM_LEADER_MISSING", "error", "H? ?? ??? ??? ?? ?? ???? ????.", beam.id)
                violations.append(v)
                actions.append(ActionCandidate(str(uuid.uuid4()), "ADD_BEAM_MARK_LEADER", beam.id, reason=v.message, rule_code=v.code))

        layer_rules = {
            "column": (["COL"], "COL"),
            "wall": (["WAL1", "WAL2", "WAL3"], "WAL1"),
            "window": (["WIN", "WINBAR", "WINELE"], "WIN"),
            "door": (["DOOR", "DOOR_ELE"], "DOOR"),
            "leader": (["DIMLE"], "DIMLE"),
            "dimension": (["DIM", "DIMLE"], "DIM"),
            "beam": (["COL", "BEAM"], "COL"),
        }
        for obj in ctx.objects:
            if not obj.semantic_type or obj.semantic_type not in layer_rules:
                continue
            allowed, target = layer_rules[obj.semantic_type]
            if not any(a.lower() in obj.layer.lower() for a in allowed):
                v = RuleViolation(str(uuid.uuid4()), "LAYER_SEMANTIC_MISMATCH", "warning", f"semantic_type={obj.semantic_type} ??? ?? ???? ?? ????.", obj.id, payload={"from_layer": obj.layer, "to_layer": target})
                violations.append(v)
                actions.append(ActionCandidate(str(uuid.uuid4()), "CHANGE_LAYER", obj.id, params={"from_layer": obj.layer, "to_layer": target, "semantic_type": obj.semantic_type}, reason=v.message, rule_code=v.code))

        return _report(ctx.drawing_id, violations, actions)


def _report(drawing_id: str, violations: list[RuleViolation], actions: list[ActionCandidate]) -> dict[str, Any]:
    by_severity: dict[str, int] = {}
    by_rule_code: dict[str, int] = {}
    for v in violations:
        by_severity[v.severity] = by_severity.get(v.severity, 0) + 1
        by_rule_code[v.code] = by_rule_code.get(v.code, 0) + 1
    return {
        "drawing_id": drawing_id,
        "summary": {"violation_count": len(violations), "action_candidate_count": len(actions), "by_severity": by_severity, "by_rule_code": by_rule_code},
        "violations": [asdict(v) for v in violations],
        "action_candidates": [asdict(a) for a in actions],
    }


def review_fileized_record(input_path: str | Path, out_path: str | Path) -> dict[str, Any]:
    ctx = FileizedReviewAdapter.from_json(input_path)
    payload = DomainReviewEngine().run(ctx)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def review_dxf_file(dxf_path: str | Path, out_path: str | Path, *, file_id: str | None = None) -> dict[str, Any]:
    from src.fileizers.dxf_ezdxf_fileizer import DXFEzdxfFileizer

    src = Path(dxf_path)
    record = DXFEzdxfFileizer().fileize(src, file_id=file_id or src.stem, relative_path=src.name)
    payload = record.to_dict() if hasattr(record, "to_dict") else dict(record)  # type: ignore[arg-type]
    ctx = FileizedReviewAdapter.from_dict(payload)
    report = DomainReviewEngine().run(ctx)
    report["source"] = {"mode": "dxf_ezdxf_no_com", "dxf_path": str(src), "fileizer_status": payload.get("status"), "fileizer_engine": payload.get("engine")}
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def command_plan_from_review(review_path: str | Path, out_path: str | Path, *, engine: str = "zwcad") -> dict[str, Any]:
    review = json.loads(Path(review_path).read_text(encoding="utf-8"))
    plans = []
    for action in review.get("action_candidates", []):
        action_type = action.get("action_type")
        params = action.get("params") or {}
        commands: list[str]
        if action_type == "CHANGE_LAYER":
            commands = [f"SELECT_BY_HANDLE {action.get('target_object_id')}", "CHPROP", "LAYER", str(params.get("to_layer"))]
        elif action_type == "ADD_BEAM_MARK_LEADER":
            commands = ["; TODO: add beam mark leader after user approval"]
        elif action_type == "ADD_FINISH_TEXT_OR_LEADER":
            commands = ["; TODO: add finish text or leader after user approval"]
        else:
            commands = [f"; unsupported action {action_type}"]
        plans.append({"id": str(uuid.uuid4()), "engine": engine, "dry_run": True, "requires_user_approval": True, "action": action, "commands": commands})
    payload = {"drawing_id": review.get("drawing_id"), "summary": {"plan_count": len(plans)}, "command_plans": plans}
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload
