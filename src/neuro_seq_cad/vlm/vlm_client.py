from __future__ import annotations


class DummyVLMClient:
    def refine(self, payload: dict) -> str:
        return '{"corrections": [], "warnings": []}'

