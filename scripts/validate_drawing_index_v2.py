#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.corpus_run.pipeline_runner import CorpusPipelineRunner  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the HS-CAD V2 drawing index locally without GitHub Actions."
    )
    parser.add_argument("root", type=Path, help="Folder containing DWG/DXF/PDF/image drawings")
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path("outputs/drawing-index-v2-validation"),
    )
    parser.add_argument("--sample", type=int, default=5, help="0 means every file")
    parser.add_argument("--query", action="append", default=[])
    parser.add_argument("--no-native-zwcad", action="store_true")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return exit code 1 when any record is failed, unavailable or incomplete",
    )
    return parser.parse_args()


def read_records(workspace: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for path in sorted((workspace / "fileized" / "json").glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            out.append(
                {
                    "file_id": path.stem,
                    "relative_path": path.name,
                    "status": "failed",
                    "errors": [{"type": "json_read_failed", "reason": str(exc)}],
                    "extraction_report": {"complete": False},
                }
            )
            continue
        out.append(payload)
    return out


def reason_rows(record: dict[str, Any]) -> list[str]:
    report = record.get("extraction_report") or {}
    reasons: list[str] = []
    for key in (
        "warning_count",
        "adapter_warning_count",
        "requires_ocr_count",
        "unsupported_proxy_count",
        "unresolved_xref_count",
    ):
        value = int(report.get(key) or 0)
        if value:
            reasons.append(f"{key}={value}")
    coverage = report.get("coverage") or {}
    missing = sorted(str(key) for key, value in coverage.items() if not value)
    if missing:
        reasons.append("coverage=" + ",".join(missing))
    for item in record.get("errors") or []:
        reasons.append("error=" + str(item.get("reason") or item))
    if not reasons and not report.get("complete", False):
        reasons.append("complete=false (no detailed reason recorded)")
    return reasons


def build_report(
    workspace: Path,
    records: list[dict[str, Any]],
    queries: list[dict[str, Any]],
) -> str:
    status_counts = Counter(str(item.get("status") or "unknown") for item in records)
    complete = [
        item
        for item in records
        if item.get("status") == "ok"
        and bool((item.get("extraction_report") or {}).get("complete"))
    ]
    incomplete = [item for item in records if item not in complete]
    lines = [
        "# HS-CAD Drawing Index V2 Local Validation",
        "",
        f"- Workspace: `{workspace.resolve()}`",
        f"- Record count: `{len(records)}`",
        f"- Complete: `{len(complete)}`",
        f"- Incomplete/failed: `{len(incomplete)}`",
        f"- Status counts: `{dict(status_counts)}`",
        "",
        "## Per drawing",
        "",
    ]
    for record in records:
        report = record.get("extraction_report") or {}
        name = record.get("relative_path") or record.get("source_path") or record.get("file_id")
        mark = "PASS" if record in complete else "REVIEW"
        lines.extend(
            [
                f"### {mark} — {name}",
                "",
                f"- Status: `{record.get('status')}`",
                f"- Engine: `{record.get('engine')}`",
                f"- Entities: `{report.get('entity_count', len(record.get('entities') or []))}`",
                f"- Text occurrences: `{report.get('text_occurrence_count', len(record.get('texts') or []))}`",
                f"- Layouts: `{report.get('layout_count', len(record.get('layouts') or []))}`",
                f"- Complete: `{bool(report.get('complete'))}`",
            ]
        )
        reasons = reason_rows(record)
        if reasons:
            lines.append("- Reasons:")
            lines.extend(f"  - `{reason}`" for reason in reasons)
        lines.append("")
    if queries:
        lines.extend(["## Search checks", ""])
        for result in queries:
            lines.append(
                f"- `{result.get('query')}`: `{len(result.get('matches') or [])}` matches"
            )
        lines.append("")
    lines.extend(
        [
            "## Interpretation",
            "",
            "A PASS means that the enabled extractors found no known omission signal. ",
            "It does not prove that a proprietary proxy object exposes every hidden string. ",
            "Every REVIEW item must be checked before the index is described as complete.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    workspace = args.workspace.resolve()
    if not root.is_dir():
        print(f"ERROR: drawing folder does not exist: {root}", file=sys.stderr)
        return 2
    runner = CorpusPipelineRunner(
        workspace, include_com_fallback=not args.no_native_zwcad
    )
    print(json.dumps(runner.prepare(root, sample=max(0, args.sample)), ensure_ascii=False))
    print(json.dumps(runner.fileize(), ensure_ascii=False))
    print(json.dumps(runner.index(), ensure_ascii=False))
    query_results = [runner.query(value, limit=50) for value in args.query]
    records = read_records(workspace)
    report_text = build_report(workspace, records, query_results)
    report_path = workspace / "DRAWING_INDEX_V2_VALIDATION.md"
    report_path.write_text(report_text, encoding="utf-8")
    summary = {
        "workspace": str(workspace),
        "report": str(report_path),
        "record_count": len(records),
        "complete_count": sum(
            1
            for record in records
            if record.get("status") == "ok"
            and bool((record.get("extraction_report") or {}).get("complete"))
        ),
        "queries": query_results,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    incomplete = summary["complete_count"] != summary["record_count"]
    return 1 if args.strict and incomplete else 0


if __name__ == "__main__":
    raise SystemExit(main())
