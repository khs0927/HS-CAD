from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path

from src.corpus.schema import FileizedDrawingRecord


class DrawingFileizer(ABC):
    """Base interface for all HS-CAD fileizers."""

    engine_name = "base"
    supported_extensions: tuple[str, ...] = ()

    def supports(self, path: str | Path) -> bool:
        return Path(path).suffix.lower() in self.supported_extensions

    def is_available(self) -> tuple[bool, str]:
        return True, "available"

    @abstractmethod
    def fileize(
        self,
        path: str | Path,
        *,
        file_id: str,
        relative_path: str | Path,
    ) -> FileizedDrawingRecord:
        raise NotImplementedError


class FileizedRecordWriter:
    """Write stable JSON, review evidence, and searchable Markdown."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.json_dir = self.root / "fileized" / "json"
        self.md_dir = self.root / "fileized" / "markdown"
        self.failure_dir = self.root / "failures"
        self.review_dir = self.root / "reviews"

    def write(self, record: FileizedDrawingRecord) -> dict[str, str]:
        self.json_dir.mkdir(parents=True, exist_ok=True)
        self.md_dir.mkdir(parents=True, exist_ok=True)
        self.failure_dir.mkdir(parents=True, exist_ok=True)
        self.review_dir.mkdir(parents=True, exist_ok=True)

        json_path = self.json_dir / f"{record.file_id}.json"
        json_path.write_text(
            json.dumps(record.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        md_path = self.md_dir / f"{record.file_id}.md"
        md_path.write_text(self.to_markdown(record), encoding="utf-8")

        paths = {"json": str(json_path), "markdown": str(md_path)}
        if record.status != "ok":
            failure_path = self.failure_dir / f"{record.file_id}.json"
            failure_path.write_text(
                json.dumps(record.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            paths["failure"] = str(failure_path)

        complete = bool((record.extraction_report or {}).get("complete"))
        if record.status != "ok" or not complete:
            review_path = self.review_dir / f"{record.file_id}.json"
            review_path.write_text(
                json.dumps(record.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            paths["review"] = str(review_path)
        else:
            stale_review = self.review_dir / f"{record.file_id}.json"
            if stale_review.exists():
                stale_review.unlink()
        return paths

    @staticmethod
    def _display_value(value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, (dict, list, tuple)):
            return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        return str(value)

    @classmethod
    def to_markdown(cls, record: FileizedDrawingRecord) -> str:
        report = record.extraction_report or {}
        lines = [
            f"# Fileized Drawing: {record.relative_path}",
            "",
            f"- File ID: `{record.file_id}`",
            f"- Source path: `{record.source_path}`",
            f"- Status: `{record.status}`",
            f"- Engine: `{record.engine}`",
            f"- Schema: `{record.schema_version}`",
            f"- Extension: `{record.extension}`",
            f"- Entities: {len(record.entities)}",
            f"- Layers: {len(record.layers)}",
            f"- Layouts: {len(record.layouts)}",
            f"- XREFs: {len(record.xrefs)}",
            f"- Blocks: {len(record.blocks)}",
            f"- Text occurrences: {len(record.texts)}",
            f"- Dimensions: {len(record.dimensions)}",
            f"- Extraction complete: `{bool(report.get('complete'))}`",
            "",
        ]
        blockers = report.get("blockers") or []
        if blockers:
            lines.extend(["## Review blockers", ""])
            lines.extend(f"- `{cls._display_value(item)}`" for item in blockers)
            lines.append("")
        if report:
            lines.extend(
                [
                    "## Extraction report",
                    "",
                    "```json",
                    json.dumps(report, ensure_ascii=False, indent=2),
                    "```",
                    "",
                ]
            )
        if record.warnings:
            lines.append("## Warnings")
            lines.append("")
            for item in record.warnings:
                lines.append(f"- {cls._display_value(item)}")
            lines.append("")
        if record.errors:
            lines.append("## Errors")
            lines.append("")
            for item in record.errors:
                lines.append(f"- {cls._display_value(item)}")
            lines.append("")
        if record.layouts:
            lines.extend(["## Layouts", ""])
            for row in record.layouts:
                lines.append(
                    f"- `{row.get('name')}` space=`{row.get('space')}` "
                    f"available=`{row.get('available', True)}`"
                )
            lines.append("")
        if record.xrefs:
            lines.extend(["## External references", ""])
            for row in record.xrefs:
                lines.append(
                    f"- `{row.get('name')}` path=`{row.get('path')}` "
                    f"loaded=`{row.get('loaded')}`"
                )
            lines.append("")
        if record.texts:
            lines.extend(["## Complete searchable text occurrences", ""])
            for index, row in enumerate(record.texts, start=1):
                block_path = row.get("block_path") or []
                if isinstance(block_path, str):
                    block_path = [block_path]
                evidence = " | ".join(
                    part
                    for part in [
                        f"layout={row.get('layout') or 'Model'}",
                        f"layer={row.get('layer') or ''}",
                        f"type={row.get('entity_type') or ''}",
                        f"source={row.get('source_kind') or ''}",
                        f"handle={row.get('handle') or ''}",
                        f"sub_handle={row.get('sub_handle') or ''}",
                        f"block={' > '.join(str(item) for item in block_path)}",
                        f"tag={row.get('tag') or ''}",
                        f"position={cls._display_value(row.get('insert'))}",
                        f"confidence={row.get('confidence', 1.0)}",
                    ]
                    if not part.endswith("=")
                )
                lines.extend(
                    [
                        f"### Text {index}",
                        "",
                        str(row.get("plain_text") or row.get("text") or ""),
                        "",
                        f"`{evidence}`",
                        "",
                    ]
                )
        return "\n".join(lines)
