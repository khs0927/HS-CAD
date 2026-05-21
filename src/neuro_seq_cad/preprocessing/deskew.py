from __future__ import annotations


def deskew_image(image_info: dict) -> dict:
    return {**image_info, "deskew_angle": 0.0}

