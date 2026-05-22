from __future__ import annotations

import csv
import time
from pathlib import Path
from typing import Any


AUDIT_LISP_NAME = "hs_audit_entities.lsp"


def _wait_for_stable_file(path: Path, timeout_seconds: int = 90) -> None:
    last_size = -1
    stable_count = 0
    for _ in range(timeout_seconds):
        if path.exists():
            size = path.stat().st_size
            if size == last_size and size > 0:
                stable_count += 1
                if stable_count >= 2:
                    return
            else:
                stable_count = 0
                last_size = size
        time.sleep(1)
    raise TimeoutError(f"Timed out waiting for native audit output: {path}")


def parse_native_audit_tsv(path: Path) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "entity_counts": {},
        "layer_counts": {},
        "block_counts": {},
        "text_count": 0,
        "dimension_count": 0,
    }
    with path.open("r", encoding="utf-8", errors="replace", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            section = row.get("section")
            key = row.get("key") or ""
            value = int(float(row.get("value") or 0))
            if section == "entity":
                payload["entity_counts"][key] = value
                if key in {"TEXT", "MTEXT"}:
                    payload["text_count"] += value
                if "DIMENSION" in key or key.startswith("DIM"):
                    payload["dimension_count"] += value
            elif section == "layer":
                payload["layer_counts"][key] = value
            elif section == "block":
                payload["block_counts"][key] = value
    payload["total_objects"] = sum(payload["entity_counts"].values())
    return payload


def run_native_audit(adapter: Any, out: str | Path, project_root: Path | None = None) -> dict[str, Any]:
    """Run CAD-internal LISP audit and parse the TSV output."""

    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tsv_path = out_path.with_suffix(".tsv")
    if tsv_path.exists():
        tsv_path.unlink()

    root = project_root or Path.cwd()
    lisp_path = root / "lisp" / AUDIT_LISP_NAME
    if not lisp_path.exists():
        raise FileNotFoundError(lisp_path)

    adapter.load_lisp(str(lisp_path))
    adapter.run_command(f'(HS_AUDIT_ENTITIES "{tsv_path.as_posix()}")')
    _wait_for_stable_file(tsv_path)
    payload = parse_native_audit_tsv(tsv_path)
    payload["source_tsv"] = str(tsv_path)
    payload["drawing"] = adapter._safe_get(adapter.get_active_document(), "FullName")
    return payload
