"""DXF fileizer."""
from __future__ import annotations

from pathlib import Path

from hscad.adapters.ezdxf_adapter import read_dxf_entities
from hscad.core.evidence import ConfidenceScore, Evidence, EvidenceKind, EvidenceSource
from hscad.core.models import FileizedDrawing
from hscad.fileizers.base import Fileizer


class DxfFileizer(Fileizer):
    input_types = ("dxf",)

    def fileize(self, path: str | Path, *, out_dir: str | Path | None = None) -> FileizedDrawing:
        dxf_path = Path(path)
        entities, metadata = read_dxf_entities(dxf_path)
        drawing = FileizedDrawing(
            input_path=str(dxf_path),
            input_type="dxf",
            normalized_path=str(dxf_path),
            entities=entities,
            metadata={"fileizer": "DxfFileizer", **metadata},
        )
        drawing.add_evidence(
            Evidence(
                source=EvidenceSource.DXF,
                kind=EvidenceKind.ENTITY,
                payload={"entity_count": len(entities), "backend": metadata.get("backend")},
                confidence=ConfidenceScore.high("DXF parsed successfully"),
                tags=["fileized", "dxf"],
            )
        )
        return drawing
