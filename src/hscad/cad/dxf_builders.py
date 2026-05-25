"""Review-only DXF builders.

They write new files only. They do not mutate the original DWG/DXF.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from hscad.adapters.ezdxf_adapter import write_review_dxf
from hscad.cad.layer_schema import LAYER_SCHEMA
from hscad.cad.review_output import (
    ReviewDxfProfile,
    build_review_dxf_manifest,
    clone_entity_to_layer,
    make_low_confidence_review_entities,
    make_qa_text_entities,
    normalize_review_issues,
    write_review_dxf_manifest,
)
from hscad.core.models import DrawingEntity


def _clone_with_layer(entity: DrawingEntity, layer: str, entity_type: str | None = None) -> DrawingEntity:
    return clone_entity_to_layer(entity, layer, entity_type=entity_type)


class ResultDxfBuilder:
    def __init__(self, profile: ReviewDxfProfile | None = None) -> None:
        self.profile = profile or ReviewDxfProfile()

    def build_all(self, out_dir: str | Path, entities: list[DrawingEntity], qa_messages: list[str | dict[str, Any]] | None = None) -> dict[str, str]:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        issues = normalize_review_issues(qa_messages or [])

        centerline = self.build_centerline(out / "result_centerline.dxf", entities)
        wallsolid = self.build_wallsolid(out / "result_wallsolid.dxf", entities)
        qa = self.build_qa_overlay(out / "qa_overlay.dxf", entities, list(qa_messages or []))
        low_conf_count = sum(1 for entity in entities if entity.confidence < self.profile.low_conf_threshold)

        paths = {"result_centerline": str(centerline), "result_wallsolid": str(wallsolid), "qa_overlay": str(qa)}
        manifest = build_review_dxf_manifest(
            output_paths=paths,
            input_entity_count=len(entities),
            qa_issue_count=len(issues),
            low_confidence_count=low_conf_count,
            profile=self.profile,
        )
        manifest_path = write_review_dxf_manifest(out / "REVIEW_DXF_MANIFEST.json", manifest)
        return {**paths, "review_dxf_manifest": str(manifest_path)}

    def build_centerline(self, path: str | Path, entities: list[DrawingEntity]) -> Path:
        selected = [e for e in entities if e.layer.upper() in {"CEN", "CEN1", "WAL1", "WAL2", "WAL3"} and e.entity_type.upper() in {"LINE", "LWPOLYLINE", "POLYLINE"}]
        normalized = [_clone_with_layer(e, "CEN" if e.layer.upper() not in {"CEN", "CEN1"} else e.layer.upper()) for e in selected]
        return write_review_dxf(path, normalized, layer_descriptions=LAYER_SCHEMA)

    def build_wallsolid(self, path: str | Path, entities: list[DrawingEntity]) -> Path:
        selected = [e for e in entities if e.layer.upper() in {"WAL1", "WAL2", "WAL3", "WAL_HATCH"}]
        normalized = [_clone_with_layer(e, "WAL_HATCH" if e.entity_type.upper() in {"LWPOLYLINE", "POLYLINE", "HATCH"} else e.layer.upper()) for e in selected]
        return write_review_dxf(path, normalized, layer_descriptions=LAYER_SCHEMA)

    def build_qa_overlay(self, path: str | Path, entities: list[DrawingEntity], messages: list[str | dict[str, Any]]) -> Path:
        issues = normalize_review_issues(messages)
        entities_by_id = {entity.entity_id: entity for entity in entities}
        qa_entities = make_qa_text_entities(issues, entities_by_id=entities_by_id, profile=self.profile)
        low_conf = make_low_confidence_review_entities(entities, profile=self.profile, include_labels=True)
        return write_review_dxf(path, [*qa_entities, *low_conf], layer_descriptions=LAYER_SCHEMA)
