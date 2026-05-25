"""DWG fileizer.

DWG is converted to DXF first. COM full-scan is intentionally not used here.
"""
from __future__ import annotations

from pathlib import Path

from hscad.adapters.odafc_adapter import OdaFileConverterAdapter
from hscad.core.evidence import make_evidence
from hscad.core.models import FileizedDrawing
from hscad.fileizers.dxf_fileizer import DxfFileizer


class DwgFileizer:
    def __init__(self, odafc: OdaFileConverterAdapter | None = None) -> None:
        self.odafc = odafc or OdaFileConverterAdapter()

    def fileize(self, input_path: str | Path, out_dir: str | Path | None = None) -> FileizedDrawing:
        path = Path(input_path)
        target_dir = Path(out_dir or path.parent / "_converted")
        result = self.odafc.convert_dwg_to_dxf(path, target_dir)
        if result.ok and result.output_path:
            drawing = DxfFileizer().fileize(result.output_path, out_dir=target_dir)
            return FileizedDrawing(
                str(path),
                "dwg",
                drawing.entities,
                {**drawing.metadata, "conversion": result.__dict__, "strategy": "odafc_to_dxf"},
                [*drawing.evidence, make_evidence("fileizer.dwg.converted", "conversion", "DWG converted to DXF before analysis", module="hscad.fileizers.dwg_fileizer", source_id=str(path), confidence=0.9, data=result.__dict__)],
                converted_path=result.output_path,
            )
        evidence = make_evidence(
            "fileizer.dwg.not_converted",
            "conversion_required",
            "DWG was not analyzed because no configured DXF conversion succeeded",
            module="hscad.fileizers.dwg_fileizer",
            source_id=str(path),
            confidence=0.2,
            reason="DWG parser not available without conversion",
            data=result.__dict__,
        )
        return FileizedDrawing(str(path), "dwg", [], {"conversion": result.__dict__, "strategy": "no_com_full_scan"}, [evidence], [result.message], result.output_path)
