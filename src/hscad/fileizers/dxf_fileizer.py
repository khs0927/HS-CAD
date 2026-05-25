"""DXF fileizer."""
from __future__ import annotations

from pathlib import Path

from hscad.adapters.ezdxf_adapter import read_dxf_entities
from hscad.core.evidence import make_evidence
from hscad.core.models import FileizedDrawing


class DxfFileizer:
    def fileize(self, input_path: str | Path, out_dir: str | Path | None = None) -> FileizedDrawing:
        path = Path(input_path)
        entities = read_dxf_entities(path)
        evidence = [
            make_evidence(
                "fileizer.dxf.read",
                "fileized_input",
                f"DXF parsed with {len(entities)} entities",
                module="hscad.fileizers.dxf_fileizer",
                source_id=str(path),
                confidence=0.95 if entities else 0.45,
                reason="entities extracted" if entities else "no supported entities found",
                data={"entity_count": len(entities)},
            )
        ]
        return FileizedDrawing(str(path), "dxf", entities, {"entity_count": len(entities)}, evidence)
