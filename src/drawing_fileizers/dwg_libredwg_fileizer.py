from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from .base import BaseDrawingFileizer
from .dxf_fileizer import DXFFileizer
from .models import FileizedDrawingRecord
from .utils import stable_file_id


class LibreDWGFileizer(BaseDrawingFileizer):
    """Optional LibreDWG CLI fileizer.

    LibreDWG is GPLv3. This adapter calls external CLI tools by subprocess and
    does not link against GPL libraries.
    """

    def supports(self, path: Path) -> bool:
        return path.suffix.lower() == ".dwg"

    def is_available(self) -> bool:
        return shutil.which("dwgread") is not None or shutil.which("dwg2dxf") is not None

    def get_name(self) -> str:
        return "libredwg-cli"

    def get_version(self) -> str:
        for cmd in ("dwgread", "dwg2dxf"):
            if shutil.which(cmd):
                try:
                    res = subprocess.run([cmd, "--version"], capture_output=True, text=True, timeout=10)
                    return (res.stdout or res.stderr).splitlines()[0].strip()
                except Exception:
                    return "unknown"
        return "unavailable"

    def fileize(self, path: Path, out_dir: Path) -> FileizedDrawingRecord:
        path = Path(path)
        out_dir = Path(out_dir)
        tmp_dir = out_dir / "tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)

        if not self.is_available():
            return FileizedDrawingRecord.failed(path, self.get_name(), "LibreDWG CLI is not installed", status="unavailable")

        file_id = stable_file_id(path)

        if shutil.which("dwgread"):
            json_path = tmp_dir / f"{file_id}.libredwg.json"
            try:
                res = subprocess.run(
                    ["dwgread", "-O", "JSON", "-o", str(json_path), str(path)],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if res.returncode == 0 and json_path.exists():
                    data = json.loads(json_path.read_text(encoding="utf-8", errors="ignore"))
                    return FileizedDrawingRecord(
                        file_id=file_id,
                        source_path=str(path),
                        relative_path=path.name,
                        extension=".dwg",
                        fileizer=self.get_name(),
                        fileizer_version=self.get_version(),
                        status="partial",
                        raw_outputs={"libredwg_json_path": str(json_path), "top_level_keys": list(data)[:50]},
                        metadata={"note": "Raw LibreDWG JSON captured; normalize later if needed."},
                        warnings=["LibreDWG JSON is stored as raw output; entity normalization may be partial."],
                    )
            except Exception:
                pass

        if shutil.which("dwg2dxf"):
            dxf_path = tmp_dir / f"{file_id}.dxf"
            try:
                res = subprocess.run(["dwg2dxf", "-o", str(dxf_path), str(path)], capture_output=True, text=True, timeout=120)
                if res.returncode == 0 and dxf_path.exists():
                    record = DXFFileizer().fileize(dxf_path, out_dir)
                    record.source_path = str(path)
                    record.relative_path = path.name
                    record.extension = ".dwg"
                    record.fileizer = "libredwg-dwg2dxf+ezdxf"
                    record.raw_outputs["converted_dxf_path"] = str(dxf_path)
                    return record
            except Exception as exc:
                return FileizedDrawingRecord.failed(path, self.get_name(), f"dwg2dxf failed: {exc}")

        return FileizedDrawingRecord.failed(path, self.get_name(), "LibreDWG could not convert this DWG")
