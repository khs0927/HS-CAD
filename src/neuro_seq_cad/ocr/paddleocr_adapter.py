from __future__ import annotations


def run_paddleocr(image_path: str) -> tuple[list[dict], list[str]]:
    try:
        import paddleocr  # type: ignore  # noqa: F401
    except Exception:
        return [], ["optional_dependency_missing: paddleocr is not installed"]
    return [], ["model_adapter_missing: PaddleOCR runtime not configured"]

