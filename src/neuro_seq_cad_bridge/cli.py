from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.hs_style_context.builder import build_style_context_from_paths
from src.hs_style_context.report import write_style_context_json, write_style_context_md
from src.hs_style_context.schema import StyleContext, to_dict
from src.neuro_seq_cad_bridge.cadpatch_builder import build_preview_insert_plan
from src.neuro_seq_cad_bridge.preview_insert import connect_active_zwcad, insert_dxf_preview, undo_back, write_insert_result
from src.neuro_seq_cad_bridge.qa_merger import merge_qa_reports
from src.neuro_seq_cad_bridge.result_loader import load_neuro_result
from src.neuro_seq_cad_bridge.style_adapter import apply_style_context_to_neuro_result


def _load_style_context(path: str | Path) -> StyleContext:
    from src.hs_style_context.schema import (
        BlockPreference,
        DimensionStylePreference,
        LayerPreference,
        LineStylePreference,
        SheetContext,
        StyleSource,
        TextStylePreference,
    )

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return StyleContext(
        version=data.get("version", "stage23-style-context-v1"),
        generated_at=data.get("generated_at", ""),
        sources=[StyleSource(**x) for x in data.get("sources", [])],
        layer_preferences=[LayerPreference(**x) for x in data.get("layer_preferences", [])],
        line_style_preferences=[LineStylePreference(**x) for x in data.get("line_style_preferences", [])],
        text_style_preferences=[TextStylePreference(**x) for x in data.get("text_style_preferences", [])],
        dimension_style_preferences=[DimensionStylePreference(**x) for x in data.get("dimension_style_preferences", [])],
        block_preferences=[BlockPreference(**x) for x in data.get("block_preferences", [])],
        sheet_context=SheetContext(**data["sheet_context"]) if data.get("sheet_context") else None,
        warnings=list(data.get("warnings", [])),
        metadata=dict(data.get("metadata", {})),
    )


def _write_json(path: str | Path, data: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _write_styled_md(path: str | Path, styled: dict[str, Any]) -> None:
    lines = [
        "# Styled Neuro Result",
        "",
        f"- Mode: {styled.get('mode')}",
        f"- Entity count: {len(styled.get('entities', []))}",
        "",
        "## Entities",
    ]
    for item in styled.get("entities", [])[:100]:
        original = item.get("original_entity", {})
        lines.append(
            f"- {original.get('id')} type={original.get('entity_type')} "
            f"layer={item.get('target_layer')} review={item.get('needs_review')} "
            f"reason={item.get('style_reason')}"
        )
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_plan_md(path: str | Path, plan: dict[str, Any]) -> None:
    lines = [
        "# Preview Insert Plan",
        "",
        f"- Operation: {plan.get('operation')}",
        f"- Source DXF: {plan.get('source_dxf')}",
        f"- Can execute: {plan.get('can_execute')}",
        f"- Dry run: {plan.get('dry_run')}",
        f"- Save: {plan.get('save')}",
        f"- Undo mark required: {plan.get('undo_mark_required')}",
        f"- Insert layer: {plan.get('insert_layer')}",
        f"- Base point: {plan.get('base_point')}",
        f"- Scale: {plan.get('scale')}",
        f"- Rotation: {plan.get('rotation')}",
        f"- Low confidence count: {plan.get('low_confidence_count')}",
        "",
        "## Warnings",
    ]
    for warning in plan.get("warnings", []):
        lines.append(f"- {warning}")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def cmd_build_style_context(args: argparse.Namespace) -> int:
    context = build_style_context_from_paths(
        local_style_sample=args.local_style,
        zium_sheet_area=args.zium_sheet,
        active_form_sample=args.active_form,
        active_scan=args.active_scan,
        reference_style_profile=args.reference_style,
    )
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    write_style_context_json(context, out / "style_context.json")
    write_style_context_md(context, out / "style_context.md")
    print(out / "style_context.json")
    return 0


def cmd_adapt_neuro_result(args: argparse.Namespace) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    result = load_neuro_result(args.result)
    context = _load_style_context(args.style_context)
    styled = apply_style_context_to_neuro_result(result, context, mode=args.mode)
    _write_json(out / "styled_result.json", styled)
    _write_styled_md(out / "styled_result.md", styled)
    print(out / "styled_result.json")
    return 0


def _load_styled_result(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {"entities": [], "warnings": [f"missing styled result: {p}"]}
    return json.loads(p.read_text(encoding="utf-8"))


def cmd_build_preview_plan(args: argparse.Namespace) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    styled = _load_styled_result(args.styled_result)
    context = _load_style_context(args.style_context)
    plan = build_preview_insert_plan(
        styled,
        centerline_dxf=args.centerline_dxf,
        wallsolid_dxf=args.wallsolid_dxf,
        style_context=context,
        base_point=None,
        scale=args.scale,
        rotation=args.rotation,
        use_wallsolid=not args.use_centerline,
    )
    _write_json(out / "preview_insert_plan.json", plan)
    _write_plan_md(out / "preview_insert_plan.md", plan)
    merge_qa_reports(args.neuro_qa, context, plan, out / "merged_qa_report.md")
    print(out / "preview_insert_plan.json")
    return 0


def cmd_insert_preview(args: argparse.Namespace) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    if args.allow_execute:
        _, doc = connect_active_zwcad()
        result = insert_dxf_preview(doc, plan, allow_execute=True)
    else:
        result = insert_dxf_preview(None, plan, allow_execute=False)
    write_insert_result(result, out / "insert_preview_result.json")
    print(out / "insert_preview_result.json")
    return 0


def cmd_undo_preview(args: argparse.Namespace) -> int:
    ok = undo_back()
    print(json.dumps({"undo_back_sent": ok}, ensure_ascii=False))
    return 0


def cmd_run_all_preview_plan(args: argparse.Namespace) -> int:
    style_out = Path(args.out) / "style_context"
    bridge_out = Path(args.out)
    style_out.mkdir(parents=True, exist_ok=True)
    bridge_out.mkdir(parents=True, exist_ok=True)

    context = build_style_context_from_paths(
        local_style_sample=args.local_style,
        zium_sheet_area=args.zium_sheet,
        active_form_sample=args.active_form,
        active_scan=args.active_scan,
        reference_style_profile=args.reference_style,
    )
    write_style_context_json(context, style_out / "style_context.json")
    write_style_context_md(context, style_out / "style_context.md")

    result = load_neuro_result(args.result)
    styled = apply_style_context_to_neuro_result(result, context, mode="existing_dwg_preview")
    _write_json(bridge_out / "styled_result.json", styled)
    _write_styled_md(bridge_out / "styled_result.md", styled)

    plan = build_preview_insert_plan(
        styled,
        centerline_dxf=args.centerline_dxf,
        wallsolid_dxf=args.wallsolid_dxf,
        style_context=context,
        scale=args.scale,
        rotation=args.rotation,
        use_wallsolid=not args.use_centerline,
    )
    _write_json(bridge_out / "preview_insert_plan.json", plan)
    _write_plan_md(bridge_out / "preview_insert_plan.md", plan)
    merge_qa_reports(args.neuro_qa, context, plan, bridge_out / "merged_qa_report.md")
    print(bridge_out / "preview_insert_plan.json")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="HS-CAD style context bridge for neuro_seq_cad outputs.")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_style_inputs(p):
        p.add_argument("--local-style")
        p.add_argument("--zium-sheet")
        p.add_argument("--active-form")
        p.add_argument("--active-scan")
        p.add_argument("--reference-style")

    p = sub.add_parser("build-style-context")
    add_style_inputs(p)
    p.add_argument("--out", default="generated/style_context")
    p.set_defaults(func=cmd_build_style_context)

    p = sub.add_parser("adapt-neuro-result")
    p.add_argument("--result", required=True)
    p.add_argument("--style-context", required=True)
    p.add_argument("--mode", default="existing_dwg_preview", choices=["existing_dwg_preview", "standalone_dxf"])
    p.add_argument("--out", default="generated/neuro_bridge")
    p.set_defaults(func=cmd_adapt_neuro_result)

    p = sub.add_parser("build-preview-plan")
    p.add_argument("--styled-result", required=True)
    p.add_argument("--centerline-dxf")
    p.add_argument("--wallsolid-dxf")
    p.add_argument("--style-context", required=True)
    p.add_argument("--neuro-qa")
    p.add_argument("--scale", type=float, default=1.0)
    p.add_argument("--rotation", type=float, default=0.0)
    p.add_argument("--use-centerline", action="store_true")
    p.add_argument("--out", default="generated/neuro_bridge")
    p.set_defaults(func=cmd_build_preview_plan)

    p = sub.add_parser("insert-preview")
    p.add_argument("--plan", required=True)
    p.add_argument("--allow-execute", action="store_true")
    p.add_argument("--out", default="generated/neuro_bridge")
    p.set_defaults(func=cmd_insert_preview)

    p = sub.add_parser("undo-preview")
    p.set_defaults(func=cmd_undo_preview)

    p = sub.add_parser("run-all-preview-plan")
    p.add_argument("--result")
    p.add_argument("--centerline-dxf")
    p.add_argument("--wallsolid-dxf")
    p.add_argument("--neuro-qa")
    add_style_inputs(p)
    p.add_argument("--scale", type=float, default=1.0)
    p.add_argument("--rotation", type=float, default=0.0)
    p.add_argument("--use-centerline", action="store_true")
    p.add_argument("--out", default="generated/neuro_bridge")
    p.set_defaults(func=cmd_run_all_preview_plan)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
