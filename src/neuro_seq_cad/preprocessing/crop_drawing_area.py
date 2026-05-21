from __future__ import annotations


def crop_drawing_area(image_info: dict) -> dict:
    return {**image_info, "crop_bbox": [0, 0, image_info.get("width", 0), image_info.get("height", 0)]}

