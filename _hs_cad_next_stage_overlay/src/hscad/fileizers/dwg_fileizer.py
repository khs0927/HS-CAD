"""DWG fileizer using DWG→DXF conversion path.

COM full scan is intentionally not part of the default flow.
"""
from __future__ import annotations

from pathlib import Path

from hscad.adapters.odafc_adapter import OdaFileConverterAdapter
from hscad.core.evidence import Evidence, EvidenceSource
from hscad.core.models import FileizedDrawing
from hscad.fileizers.base import Fileizer
from hscad.fileizers.dxf_fileizer import DxfFileizer


class DwgFileizer(Fileizer):
    input_types = ("dwg",)

    def __init__(self, odafc: OdaFileConverterAdapter | None = None) -> None:
        self.odafc = odafc or OdaFileConverterAdapter()
        self.dxf_fileizer = DxfFileizer()

    def fileize(self, path: str | Path, *, out_dir: str | Path | None = None) -> FileizedDrawing:
        src = Path(path)
        conversion_dir = Path(out_dir or src.parent / "_converted_dxf")
        result = self.odafc.convert_dwg_to_dxf(src, conversion_dir)
        if result.ok and result.output_path:
            drawing = self.dxf_fileizer.fileize(result.output_path, out_dir=out_dir)
            drawing.input_path = str(src)
            drawing.input_type = "dwg"
            drawing.metadata["dwg_conversion"] = result.__dict__
            return drawing
        drawing = FileizedDrawing(
            input_path=str(src),
            input_type="dwg",
            normalized_path=result.output_path,
            metadata={"fileizer": "DwgFileizer", "dwg_conversion": result.__dict__, "com_scan_used": False},
        )
        drawing.add_evidence(
            Evidence.error(
                "DWG conversion failed; COM full scan was not attempted by default",
                source=EvidenceSource.DWG,
                conversion=result.__dict__,
                com_scan_used=False,
            )
        )
        return drawing
