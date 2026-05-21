from __future__ import annotations

from pathlib import Path

from neuro_seq_cad.io.image_loader import load_image


def normalize_scan(image_path: str | Path, out_dir: str | Path | None = None) -> dict:
    loaded = load_image(image_path)
    warnings: list[str] = []
    debug_paths: dict[str, str] = {}
    if loaded.backend == "png-header":
        warnings.append("optional_dependency_missing: pillow/opencv not available, using metadata-only normalize fallback")
    return {
        "image_path": str(loaded.path),
        "width": loaded.width,
        "height": loaded.height,
        "debug_paths": debug_paths,
        "warnings": warnings,
    }

