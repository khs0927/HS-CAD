from __future__ import annotations


def binarize_image(image_info: dict) -> dict:
    return {**image_info, "binarized": True}

