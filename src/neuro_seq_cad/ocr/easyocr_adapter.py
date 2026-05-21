from __future__ import annotations


def run_easyocr(image_path: str) -> tuple[list[dict], list[str]]:
    try:
        import easyocr  # type: ignore  # noqa: F401
    except Exception:
        return [], ["optional_dependency_missing: easyocr is not installed"]
    return [], ["model_adapter_missing: EasyOCR runtime not configured"]

