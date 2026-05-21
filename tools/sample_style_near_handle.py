#!/usr/bin/env python
"""
Sample the drawing style near a given handle or active selection.
Generates a JSON report and a simple Markdown summary.
"""

import argparse
import json
import os
import sys

def main() -> None:
    parser = argparse.ArgumentParser(description="Sample drawing style near a handle or active selection.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--handle", help="Handle of the source object")
    group.add_argument("--active-selection", action="store_true", help="Use the active selection as source")
    parser.add_argument("--radius", type=int, default=3000, help="Search radius (in drawing units)")
    parser.add_argument("--out-dir", required=True, help="Directory to write output files")
    args = parser.parse_args()

    source_handle = args.handle if args.handle else "active_selection_dummy"

    # Stub data – in a real implementation this would query ZWCAD via COM.
    data = {
        "source_handle": source_handle,
        "radius": args.radius,
        "nearby_entity_count": 42,
        "dominant_layers": {"0": 42},
        "dominant_entity_types": {"LINE": 20, "ARC": 10, "TEXT": 12},
        "dominant_colors": {"256": 42},
        "dominant_linetypes": {"BYLAYER": 42},
        "dominant_lineweights": {"0.25mm": 42},
        "text_height_families": [2.5],
        "text_styles": ["Standard"],
        "dimension_styles": ["DimStyle1"],
        "leader_patterns": ["Straight"],
        "block_effective_names": ["ZIUM_sheet_architect"],
        "recommended_generation_style": {
            "line_layer": "0",
            "line_color": "256",
            "line_linetype": "BYLAYER",
            "lineweight": "0.25mm",
            "text_height": 2.5,
            "dimension_style": "DimStyle1",
            "leader_style": "Straight",
        },
    }

    os.makedirs(args.out_dir, exist_ok=True)

    json_path = os.path.join(args.out_dir, "local_style_sample.json")
    md_path = os.path.join(args.out_dir, "local_style_sample.md")

    with open(json_path, "w", encoding="utf-8") as f_json:
        json.dump(data, f_json, ensure_ascii=False, indent=2)

    with open(md_path, "w", encoding="utf-8") as f_md:
        f_md.write("# Local Style Sample\n\n")
        f_md.write(f"- Source handle: `{source_handle}`\n")
        f_md.write(f"- Search radius: {args.radius}\n")
        f_md.write(f"- Nearby entity count: {data['nearby_entity_count']}\n\n")
        f_md.write("## Dominant Layers\n")
        for layer, cnt in data["dominant_layers"].items():
            f_md.write(f"- {layer}: {cnt}\n")
        f_md.write("\n## Recommended Generation Style\n")
        for k, v in data["recommended_generation_style"].items():
            f_md.write(f"- {k}: {v}\n")

if __name__ == "__main__":
    main()
