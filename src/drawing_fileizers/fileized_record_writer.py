from __future__ import annotations

import json
from pathlib import Path

from .models import FileizedDrawingRecord


class FileizedRecordWriter:
    def __init__(self, out_dir: Path) -> None:
        self.out_dir = Path(out_dir)
        self.json_dir = self.out_dir / "json"
        self.markdown_dir = self.out_dir / "markdown"
        self.jsonl_path = self.out_dir / "all_records.jsonl"
        self.json_dir.mkdir(parents=True, exist_ok=True)
        self.markdown_dir.mkdir(parents=True, exist_ok=True)

    def write(self, record: FileizedDrawingRecord) -> Path:
        json_path = self.json_dir / f"{record.file_id}.json"
        # Ensure parent directories exist for nested file_id paths
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(record.model_dump_json(indent=2), encoding="utf-8")

        with self.jsonl_path.open("a", encoding="utf-8") as f:
            f.write(record.model_dump_json() + "\n")

        md_path = self.markdown_dir / f"{record.file_id}.md"
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(self.to_markdown(record), encoding="utf-8")
        return json_path

    @staticmethod
    def to_markdown(record: FileizedDrawingRecord) -> str:
        lines = [
            f"# Fileized Drawing: {record.relative_path or record.source_path}",
            "",
            f"- file_id: `{record.file_id}`",
            f"- status: `{record.status}`",
            f"- fileizer: `{record.fileizer}`",
            f"- extension: `{record.extension}`",
            f"- entities: {len(record.entities)}",
            f"- texts: {len(record.texts)}",
            f"- dimensions: {len(record.dimensions)}",
            "",
            "## Warnings",
        ]
        lines.extend([f"- {w}" for w in record.warnings] or ["- none"])
        lines.append("")
        lines.append("## Errors")
        lines.extend([f"- {e}" for e in record.errors] or ["- none"])
        return "\n".join(lines)
