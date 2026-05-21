from __future__ import annotations

from collections import Counter
from pathlib import Path


KNOWN_WARNING_TYPES = [
    "scale_unresolved",
    "open_wall_polygon",
    "wall_gap",
    "door_not_on_wall",
    "window_not_on_wall",
    "ocr_failed",
    "vlm_validation_failed",
    "low_confidence_entities",
    "hatch_skipped",
    "non_manhattan_detected",
    "model_adapter_missing",
    "optional_dependency_missing",
]


def write_qa_report(path: str | Path, warnings: list[str], summary: dict) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    counter = Counter(w.split(":", 1)[0] for w in warnings)
    lines = [
        "# QA Report",
        "",
        "이 보고서는 이미지/PDF 기반 CAD 초안 생성 과정에서 확정하지 못한 판단을 숨기지 않고 기록합니다.",
        "",
        "## Summary",
    ]
    for key, value in summary.items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Warning Types"])
    for key in KNOWN_WARNING_TYPES:
        lines.append(f"- {key}: {counter.get(key, 0)}")
    lines.extend(["", "## Warnings"])
    if warnings:
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.append("- none")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out

