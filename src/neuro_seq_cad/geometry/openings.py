from __future__ import annotations


def find_openings(symbols: list[dict]) -> list[dict]:
    return [s for s in symbols if s.get("type") in {"door", "window"}]

