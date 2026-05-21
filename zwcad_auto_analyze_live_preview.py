from __future__ import annotations

import argparse

from image_to_cad.auto.active_analyzer import analyze_active_drawing
from image_to_cad.auto.auto_report import write_auto_analysis
from image_to_cad.auto.live_preview import apply_live_preview
from image_to_cad.auto.undo_guard import undo_back_to_mark


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze active ZWCAD drawing and optionally apply live layer preview.")
    parser.add_argument("--out-dir", default="outputs/auto_analysis")
    parser.add_argument("--apply-preview", action="store_true")
    parser.add_argument("--min-confidence", type=float, default=0.82)
    parser.add_argument("--allow-layer-zero", action="store_true")
    parser.add_argument("--undo-preview", action="store_true")
    args = parser.parse_args()

    if args.undo_preview:
        ok = undo_back_to_mark()
        print({"undo_back_sent": ok})
        return 0 if ok else 1

    analysis = analyze_active_drawing(allow_layer_zero=args.allow_layer_zero)
    result = None
    if args.apply_preview:
        result = apply_live_preview(
            analysis,
            min_confidence=args.min_confidence,
            allow_layer_zero=args.allow_layer_zero,
        )
    paths = write_auto_analysis(analysis, args.out_dir, preview_result=result)
    print(paths)
    if result:
        print(result.to_dict())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
