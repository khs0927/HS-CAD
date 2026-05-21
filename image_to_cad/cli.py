from __future__ import annotations

import argparse
from pathlib import Path

from image_to_cad.auto.active_analyzer import analyze_active_drawing
from image_to_cad.auto.auto_report import write_auto_analysis
from image_to_cad.auto.image_result_auto_fit import prepare_image_result_fit
from image_to_cad.auto.live_preview import apply_live_preview
from image_to_cad.auto.undo_guard import undo_back_to_mark


def _auto_analyze_active(args: argparse.Namespace) -> int:
    analysis = analyze_active_drawing()
    paths = write_auto_analysis(analysis, args.out)
    print(f"auto_inventory: {paths['inventory']}")
    print(f"mapping_candidates: {paths['candidates']}")
    print(f"report: {paths['report']}")
    return 0


def _auto_preview_remap(args: argparse.Namespace) -> int:
    analysis = analyze_active_drawing()
    paths = write_auto_analysis(analysis, args.out)
    result = apply_live_preview(
        analysis,
        min_confidence=args.min_confidence,
        allow_layer_zero=args.allow_layer_zero,
    )
    preview_path = Path(args.out) / "auto_preview_result.json"
    write_auto_analysis(analysis, args.out, preview_result=result)
    print(f"auto_inventory: {paths['inventory']}")
    print(f"preview_result: {preview_path}")
    print({"changed": result.changed, "skipped": result.skipped, "errors": len(result.errors), "undo_mark_created": result.undo_mark_created})
    return 0


def _auto_undo_preview(args: argparse.Namespace) -> int:
    ok = undo_back_to_mark()
    print({"undo_back_sent": ok})
    return 0 if ok else 1


def _auto_fit_image_result(args: argparse.Namespace) -> int:
    result = prepare_image_result_fit(
        Path(args.recognition_output),
        Path(args.out),
        target_active=args.target_active,
        base_point=args.base_point,
        scale=args.scale,
        rotation=args.rotation,
    )
    print(result)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Image-to-CAD active drawing automation.")
    sub = parser.add_subparsers(dest="command", required=True)

    analyze = sub.add_parser("auto-analyze-active", help="Analyze the active ZWCAD drawing without modifying it.")
    analyze.add_argument("--out", "--out-dir", default="outputs/auto_analysis")
    analyze.set_defaults(func=_auto_analyze_active)

    preview = sub.add_parser("auto-preview-remap", help="Apply high-confidence layer remap preview without saving.")
    preview.add_argument("--out", "--out-dir", default="outputs/auto_analysis")
    preview.add_argument("--min-confidence", type=float, default=0.82)
    preview.add_argument("--allow-layer-zero", action="store_true")
    preview.set_defaults(func=_auto_preview_remap)

    undo = sub.add_parser("auto-undo-preview", help="Send UNDO BACK to return to the previous preview mark.")
    undo.set_defaults(func=_auto_undo_preview)

    fit = sub.add_parser("auto-fit-image-result", help="Prepare recognition output for CAD insertion/preview.")
    fit.add_argument("recognition_output")
    fit.add_argument("--out", default="outputs/image_fit")
    fit.add_argument("--target-active", action="store_true")
    fit.add_argument("--base-point", default=None)
    fit.add_argument("--scale", type=float, default=1.0)
    fit.add_argument("--rotation", type=float, default=0.0)
    fit.set_defaults(func=_auto_fit_image_result)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

