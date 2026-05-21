from __future__ import annotations

from pathlib import Path
from typing import Any

from src.hs_style_context.schema import StyleContext


def _read_optional(path: str | None) -> str:
    if not path:
        return ""
    p = Path(path)
    if not p.exists():
        return ""
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return ""


def merge_qa_reports(
    neuro_qa_path: str | None,
    style_context: StyleContext,
    preview_plan: dict[str, Any],
    out_path: str | Path,
) -> None:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Merged QA Report",
        "",
        "## Image-to-CAD QA",
    ]
    neuro_text = _read_optional(neuro_qa_path)
    lines.append(neuro_text if neuro_text else "- no neuro qa report loaded")

    lines += ["", "## Style Context Warnings"]
    if style_context.warnings:
        for warning in style_context.warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("- none")

    lines += ["", "## Preview Plan Warnings"]
    warnings = preview_plan.get("warnings") or []
    if warnings:
        for warning in warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("- none")

    lines += [
        "",
        "## Manual Review Checklist",
        "- Check DXF insertion scale and base point.",
        "- Check QA-REVIEW and AI_LOWCONF entities before merging into office DWG.",
        "- Do not save the original DWG until preview is verified.",
        "- Use UNDO BACK if the inserted preview is not correct.",
    ]
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
