from __future__ import annotations


def mask_regions(image_info: dict, regions: list[dict] | None = None) -> dict:
    return {**image_info, "masked_regions": regions or []}

