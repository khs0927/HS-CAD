import json
from pathlib import Path

from .schema import DxfRewriteReport, to_dict


def write_rewrite_report_json(report: DxfRewriteReport, path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(to_dict(report), ensure_ascii=False, indent=2), encoding="utf-8")


def write_rewrite_report_md(report: DxfRewriteReport, path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# DXF Rewrite Report",
        "",
        f"- Source DXF: {report.source_dxf}",
        f"- Output DXF: {report.output_dxf}",
        f"- Source exists: {report.source_exists}",
        f"- ezdxf available: {report.ezdxf_available}",
        f"- Copied without rewrite: {report.copied_without_rewrite}",
        f"- Inspected count: {report.inspected_count}",
        "",
        "## Warnings",
    ]
    for warning in report.warnings or ["none"]:
        lines.append(f"- {warning}")
    lines += ["", "## Errors"]
    for error in report.errors or ["none"]:
        lines.append(f"- {error}")
    lines += ["", "## Actions"]
    for action in report.actions[:200]:
        lines.append(
            f"- handle={action.handle}, type={action.dxftype}, {action.old_layer} -> {action.new_layer}, applied={action.applied}, reason={action.reason}"
        )
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
