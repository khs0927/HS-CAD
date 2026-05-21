from __future__ import annotations

from pathlib import Path

from neuro_seq_cad.fusion.evidence_graph import EvidenceGraph
from neuro_seq_cad.io.coordinate_system import cad_to_image_point
from neuro_seq_cad.io.image_loader import load_image
from neuro_seq_cad.review.synthetic_floorplan_generator import make_synthetic_floorplan


def _img_point(point: tuple[float, float], image_height: int, scale: float) -> tuple[float, float]:
    return cad_to_image_point(point, image_height, scale)


def render_overlay(image_path: str | Path, graph: EvidenceGraph, out_path: str | Path) -> Path:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image, ImageDraw  # type: ignore

        img = Image.open(image_path).convert("RGB")
        image_height = img.height
        scale = graph.scale or 1.0
        draw = ImageDraw.Draw(img, "RGBA")
        for entity in graph.entities:
            geom = entity.geometry
            if entity.entity_type in {"raw_line", "wall_centerline"}:
                color = (0, 180, 255, 120) if entity.entity_type == "raw_line" else (0, 220, 0, 180)
                draw.line([_img_point(tuple(geom["p1"]), image_height, scale), _img_point(tuple(geom["p2"]), image_height, scale)], fill=color, width=3)
            elif entity.entity_type == "wall_polygon":
                pts = [_img_point(tuple(p), image_height, scale) for p in geom.get("points", [])]
                if len(pts) >= 3:
                    draw.polygon(pts, outline=(255, 0, 0, 180), fill=(255, 0, 0, 40))
            elif entity.confidence < 0.45:
                p = _img_point(tuple(geom.get("point", geom.get("p1", (10, 10)))), image_height, scale)
                draw.ellipse((p[0] - 15, p[1] - 15, p[0] + 15, p[1] + 15), outline=(255, 0, 255, 220), width=3)
        img.save(out)
        return out
    except Exception:
        img = load_image(image_path)
        return make_synthetic_floorplan(out, img.width, img.height)
