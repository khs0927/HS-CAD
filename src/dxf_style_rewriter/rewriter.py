from __future__ import annotations

import json
import shutil
from pathlib import Path

from .entity_styler import build_rewrite_actions_from_styled_result
from .inspector import inspect_dxf
from .report import write_rewrite_report_json, write_rewrite_report_md
from .schema import DxfRewriteAction, DxfRewriteReport


def _load_json_optional(path: str | Path | None) -> dict:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _target_name(source: Path) -> str:
    if source.stem.startswith("styled_"):
        return source.name
    return f"styled_{source.name}"


def rewrite_dxf(
    source_dxf: str | Path,
    styled_result_path: str | Path | None,
    style_context_path: str | Path | None,
    out_dir: str | Path,
) -> DxfRewriteReport:
    source = Path(source_dxf)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    output = out / _target_name(source)

    report = DxfRewriteReport(source_dxf=str(source), output_dxf=str(output))
    report.source_exists = source.exists()

    styled_result = _load_json_optional(styled_result_path)
    style_context = _load_json_optional(style_context_path)
    if not styled_result:
        report.warnings.append("styled_result missing or invalid; rewrite uses DXF inspection/copy fallback")
    if not style_context:
        report.warnings.append("style_context missing or invalid; rewrite policy uses fallback layers")

    entities, inspect_warnings = inspect_dxf(source)
    report.warnings.extend(inspect_warnings)
    report.inspected_count = len(entities)
    report.ezdxf_available = not any("ezdxf is not installed" in w for w in inspect_warnings)

    if not source.exists():
        report.output_dxf = None
        report.errors.append(f"source DXF missing: {source}")
        write_rewrite_report_json(report, out / "dxf_rewrite_report.json")
        write_rewrite_report_md(report, out / "dxf_rewrite_report.md")
        return report

    try:
        shutil.copyfile(source, output)
        report.copied_without_rewrite = True
    except Exception as exc:
        report.errors.append(f"failed to copy DXF: {exc}")

    action_specs = build_rewrite_actions_from_styled_result(styled_result)
    for spec in action_specs:
        report.actions.append(
            DxfRewriteAction(
                handle=None,
                dxftype=str(spec.get("entity_type") or "unknown"),
                old_layer=None,
                new_layer=str(spec.get("target_layer") or "QA_MARKUP"),
                reason=str(spec.get("reason") or "styled_result action"),
                applied=False,
            )
        )

    if report.copied_without_rewrite:
        report.warnings.append("DXF was copied conservatively; entity-level rewrite requires stable entity handles or explicit mapping.")

    write_rewrite_report_json(report, out / "dxf_rewrite_report.json")
    write_rewrite_report_md(report, out / "dxf_rewrite_report.md")
    return report
