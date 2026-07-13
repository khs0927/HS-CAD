#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare native-ZWCAD and fallback-only HS-CAD fixture runs."
    )
    parser.add_argument("native_workspace", type=Path)
    parser.add_argument("fallback_workspace", type=Path)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("CODEX_WINDOWS_FIXTURE_COMPARISON.md"),
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=Path("CODEX_WINDOWS_FIXTURE_COMPARISON.json"),
    )
    return parser.parse_args()


def read_records(workspace: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    root = workspace / "fileized" / "json"
    for path in sorted(root.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        key = str(
            payload.get("relative_path")
            or payload.get("source_path")
            or payload.get("file_id")
            or path.stem
        ).replace("\\", "/")
        records[key] = payload
    return records


def facts(record: dict[str, Any] | None) -> dict[str, Any]:
    if record is None:
        return {
            "present": False,
            "status": "missing",
            "engine": "",
            "complete": False,
            "entities": 0,
            "texts": 0,
            "layouts": 0,
            "blockers": ["record_missing"],
        }
    report = record.get("extraction_report") or {}
    return {
        "present": True,
        "status": str(record.get("status") or "unknown"),
        "engine": str(record.get("engine") or ""),
        "complete": bool(report.get("complete")),
        "entities": int(report.get("entity_count", len(record.get("entities") or [])) or 0),
        "texts": int(
            report.get("text_occurrence_count", len(record.get("texts") or [])) or 0
        ),
        "layouts": int(report.get("layout_count", len(record.get("layouts") or [])) or 0),
        "blockers": [str(item) for item in (report.get("blockers") or [])],
    }


def classify(native: dict[str, Any], fallback: dict[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    severity = "PASS"

    if not native["present"]:
        return "BLOCK", ["native record missing"]

    if fallback["complete"] and not native["complete"]:
        severity = "BLOCK"
        reasons.append("fallback completed but native path did not")
    elif not native["complete"]:
        severity = "REVIEW"
        reasons.append("native path remains incomplete")

    if fallback["present"] and native["layouts"] < fallback["layouts"]:
        severity = "BLOCK" if severity == "PASS" else severity
        reasons.append(
            f"native layouts {native['layouts']} < fallback layouts {fallback['layouts']}"
        )

    if fallback["present"] and native["texts"] < fallback["texts"]:
        if severity == "PASS":
            severity = "REVIEW"
        reasons.append(f"native texts {native['texts']} < fallback texts {fallback['texts']}")

    if fallback["present"] and native["entities"] < fallback["entities"]:
        if severity == "PASS":
            severity = "REVIEW"
        reasons.append(
            f"native entities {native['entities']} < fallback entities {fallback['entities']}"
        )

    if native["blockers"]:
        if severity == "PASS":
            severity = "REVIEW"
        reasons.append("native blockers: " + ", ".join(native["blockers"]))

    if not fallback["present"]:
        reasons.append("fallback comparison record missing")
        if severity == "PASS":
            severity = "REVIEW"

    return severity, reasons


def main() -> int:
    args = parse_args()
    native_workspace = args.native_workspace.resolve()
    fallback_workspace = args.fallback_workspace.resolve()
    native_records = read_records(native_workspace)
    fallback_records = read_records(fallback_workspace)

    rows: list[dict[str, Any]] = []
    counts = {"PASS": 0, "REVIEW": 0, "BLOCK": 0}
    for relative_path in sorted(set(native_records) | set(fallback_records)):
        native = facts(native_records.get(relative_path))
        fallback = facts(fallback_records.get(relative_path))
        severity, reasons = classify(native, fallback)
        counts[severity] += 1
        rows.append(
            {
                "relative_path": relative_path,
                "severity": severity,
                "reasons": reasons,
                "native": native,
                "fallback": fallback,
            }
        )

    payload = {
        "native_workspace": str(native_workspace),
        "fallback_workspace": str(fallback_workspace),
        "counts": counts,
        "rows": rows,
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = [
        "# HS-CAD Windows/ZWCAD Fixture Comparison",
        "",
        f"- Native workspace: `{native_workspace}`",
        f"- Fallback workspace: `{fallback_workspace}`",
        f"- PASS: `{counts['PASS']}`",
        f"- REVIEW: `{counts['REVIEW']}`",
        f"- BLOCK: `{counts['BLOCK']}`",
        "",
        "| Result | Drawing | Native engine | Native complete | Fallback engine | Fallback complete | Findings |",
        "|---|---|---|---:|---|---:|---|",
    ]
    for row in rows:
        native = row["native"]
        fallback = row["fallback"]
        findings = "<br>".join(row["reasons"]) or "No known regression"
        lines.append(
            "| {severity} | `{path}` | `{native_engine}` | `{native_complete}` | "
            "`{fallback_engine}` | `{fallback_complete}` | {findings} |".format(
                severity=row["severity"],
                path=row["relative_path"],
                native_engine=native["engine"] or "-",
                native_complete=native["complete"],
                fallback_engine=fallback["engine"] or "-",
                fallback_complete=fallback["complete"],
                findings=findings,
            )
        )

    lines.extend(
        [
            "",
            "## Release gate",
            "",
            "- `BLOCK` must be resolved before the PR leaves Draft.",
            "- `REVIEW` requires manual inspection of the source drawing and generated JSON/Markdown evidence.",
            "- A zero-BLOCK report does not prove that proprietary proxy objects expose hidden content.",
            "",
        ]
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"report": str(args.out), "counts": counts}, ensure_ascii=False))
    return 1 if counts["BLOCK"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
