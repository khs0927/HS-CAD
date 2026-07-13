from __future__ import annotations

from pathlib import Path
from typing import Any

REQUIRED_TOP_LEVEL_FIELDS = {
    "file_id",
    "source_path",
    "relative_path",
    "extension",
    "status",
    "engine",
    "layers",
    "blocks",
    "entities",
    "texts",
    "dimensions",
    "metadata",
    "warnings",
    "errors",
}
VALID_STATUSES = {"ok", "failed", "unavailable"}


class FileizedRecordValidator:
    def validate_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        errors: list[dict[str, str]] = []
        warnings: list[dict[str, str]] = []
        missing = sorted(REQUIRED_TOP_LEVEL_FIELDS - set(payload))
        for field in missing:
            errors.append({"type": "missing_field", "field": field})
        status = payload.get("status")
        if status not in VALID_STATUSES:
            errors.append(
                {"type": "invalid_status", "field": "status", "value": str(status)}
            )
        for field in (
            "layers",
            "blocks",
            "entities",
            "texts",
            "dimensions",
            "layouts",
            "xrefs",
            "warnings",
            "errors",
        ):
            if field in payload and not isinstance(payload[field], list):
                errors.append({"type": "invalid_list_field", "field": field})
        for field in ("metadata", "extraction_report"):
            if field in payload and not isinstance(payload[field], dict):
                errors.append({"type": "invalid_dict_field", "field": field})
        try:
            schema_version = int(payload.get("schema_version", 1))
        except (TypeError, ValueError):
            errors.append({"type": "invalid_schema_version", "field": "schema_version"})
            schema_version = 0
        if status == "ok" and not payload.get("entities"):
            warnings.append({"type": "ok_record_without_entities", "field": "entities"})
        if status == "failed" and not payload.get("errors"):
            warnings.append({"type": "failed_record_without_errors", "field": "errors"})
        if status == "unavailable" and not payload.get("warnings"):
            warnings.append(
                {"type": "unavailable_record_without_warnings", "field": "warnings"}
            )
        if schema_version >= 2 and status == "ok":
            report = payload.get("extraction_report") or {}
            if not report:
                warnings.append(
                    {"type": "missing_extraction_report", "field": "extraction_report"}
                )
            elif not report.get("complete", False):
                warnings.append(
                    {"type": "extraction_incomplete", "field": "extraction_report"}
                )
            for row in payload.get("texts") or []:
                if not isinstance(row, dict):
                    errors.append({"type": "invalid_text_row", "field": "texts"})
                    continue
                if not row.get("text") and not row.get("plain_text"):
                    errors.append({"type": "text_row_without_text", "field": "texts"})
                if not row.get("occurrence_id"):
                    warnings.append(
                        {"type": "text_row_without_occurrence_id", "field": "texts"}
                    )
        return {
            "valid": not errors,
            "error_count": len(errors),
            "warning_count": len(warnings),
            "errors": errors,
            "warnings": warnings,
        }

    def validate_json_file(self, path: str | Path) -> dict[str, Any]:
        import json

        source = Path(path)
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
        except Exception as exc:
            return {
                "path": str(source),
                "valid": False,
                "error_count": 1,
                "warning_count": 0,
                "errors": [{"type": "json_read_failed", "reason": str(exc)}],
                "warnings": [],
            }
        result = self.validate_payload(payload)
        result["path"] = str(source)
        result["file_id"] = payload.get("file_id")
        result["relative_path"] = payload.get("relative_path")
        return result

    def validate_json_dir(self, json_dir: str | Path) -> dict[str, Any]:
        base = Path(json_dir)
        results = [
            self.validate_json_file(path) for path in sorted(base.glob("*.json"))
        ]
        return {
            "json_dir": str(base),
            "record_count": len(results),
            "valid_count": sum(1 for item in results if item.get("valid")),
            "invalid_count": sum(1 for item in results if not item.get("valid")),
            "error_count": sum(int(item.get("error_count") or 0) for item in results),
            "warning_count": sum(
                int(item.get("warning_count") or 0) for item in results
            ),
            "records": results,
        }
