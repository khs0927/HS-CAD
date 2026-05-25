"""Review-only DXF builders.

They write new files only. They do not mutate the original DWG/DXF.
"""
from __future__ import annotations

from pathlib import Path

from hscad.adapters.ezdxf_adapter import write_review_dxf
from hscad.cad.layer_schema import LAYER_SCHEMA
from hscad.core.models import DrawingEntity


def _clone_with_layer(entity: DrawingEntity, layer: str, entity_type: str | None = None) -> DrawingEntity:
    return DrawingEntity(entity.entity_id, entity_type or entity.entity_type, layer, entity.geometry, entity.text, {**entity.raw, "review_output_layer": layer}, entity.confidence, entity.source)


class ResultDxfBuilder:
    def build_all(self, out_dir: str | Path, entities: list[DrawingEntity], qa_messages: list[str] | None = None) -> dict[str, str]:
        out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
        centerline = self.build_centerline(out / "result_centerline.dxf", entities)
        wallsolid = self.build_wallsolid(out / "result_wallsolid.dxf", entities)
        qa = self.build_qa_overlay(out / "qa_overlay.dxf", entities, qa_messages or [])
        return {"result_centerline": str(centerline), "result_wallsolid": str(wallsolid), "qa_overlay": str(qa)}

    def build_centerline(self, path: str | Path, entities: list[DrawingEntity]) -> Path:
        selected = [e for e in entities if e.layer.upper() in {"CEN", "CEN1", "WAL1", "WAL2", "WAL3"} and e.entity_type.upper() in {"LINE", "LWPOLYLINE", "POLYLINE"}]
        normalized = [_clone_with_layer(e, "CEN" if e.layer.upper() not in {"CEN", "CEN1"} else e.layer.upper()) for e in selected]
        return write_review_dxf(path, normalized, layer_descriptions=LAYER_SCHEMA)

    def build_wallsolid(self, path: str | Path, entities: list[DrawingEntity]) -> Path:
        selected = [e for e in entities if e.layer.upper() in {"WAL1", "WAL2", "WAL3", "WAL_HATCH"}]
        normalized = [_clone_with_layer(e, "WAL_HATCH" if e.entity_type.upper() in {"LWPOLYLINE", "POLYLINE", "HATCH"} else e.layer.upper()) for e in selected]
        return write_review_dxf(path, normalized, layer_descriptions=LAYER_SCHEMA)

    def build_qa_overlay(self, path: str | Path, entities: list[DrawingEntity], messages: list[str]) -> Path:
        qa_entities: list[DrawingEntity] = []
        for idx, msg in enumerate(messages):
            qa_entities.append(DrawingEntity(f"QA-{idx:06d}", "TEXT", "QA_MARKUP", {"insert": (0.0, idx * 300.0), "height": 180.0}, msg, {"generated": True, "review_output": True}, 1.0, "hscad.cad.dxf_builders"))
        low_conf = [_clone_with_layer(e, "AI_LOWCONF") for e in entities if e.confidence < 0.5]
        return write_review_dxf(path, [*qa_entities, *low_conf], layer_descriptions=LAYER_SCHEMA)
