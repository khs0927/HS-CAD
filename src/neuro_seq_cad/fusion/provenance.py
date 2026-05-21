from __future__ import annotations


def make_provenance(source: str, detail: dict | None = None) -> dict:
    return {"source": source, "detail": detail or {}}

