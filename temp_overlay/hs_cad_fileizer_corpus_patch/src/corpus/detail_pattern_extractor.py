from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class DetailPattern:
    pattern_name: str
    situation_tag: str
    elements: list[str] = field(default_factory=list)
    materials: list[str] = field(default_factory=list)
    typical_dimensions: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    evidence_file_ids: list[str] = field(default_factory=list)
    confidence: float = 0.5


def infer_detail_patterns(
    *,
    file_id: str = "",
    situations: list[Any] | None = None,
    materials: list[Any] | None = None,
    dimensions: list[Any] | None = None,
    elements: list[Any] | None = None,
) -> list[DetailPattern]:
    situations = situations or []
    materials = materials or []
    dimensions = dimensions or []
    elements = elements or []

    material_names = [getattr(m, "material_name", str(m)) for m in materials]
    dim_values = [getattr(d, "raw_text", getattr(d, "value", str(d))) for d in dimensions]
    elem_names = [getattr(e, "canonical_element", str(e)) for e in elements]
    out: list[DetailPattern] = []

    tags = [getattr(s, "tag", str(s)) for s in situations]
    if "방음시창" in tags:
        out.append(
            DetailPattern(
                "방음시창 기본 상세 구성",
                "방음시창",
                elements=sorted(set(elem_names + ["WINDOW", "ACOUSTIC", "MATERIAL_NOTE", "DIMENSION"])),
                materials=material_names,
                typical_dimensions=dim_values,
                notes=["창호 크기, 프레임, 유리 사양, 실란트/코킹, 차음성능 표기를 함께 검토한다."],
                evidence_file_ids=[file_id] if file_id else [],
                confidence=0.75,
            )
        )
    if "판넬마감" in tags or "H빔접합" in tags:
        out.append(
            DetailPattern(
                "판넬-H빔 접합 상세 구성",
                "H빔접합" if "H빔접합" in tags else "판넬마감",
                elements=sorted(set(elem_names + ["STRUCTURAL_STEEL", "PANEL_SYSTEM", "THERMAL_INSULATION", "MATERIAL_NOTE"])),
                materials=material_names,
                typical_dimensions=dim_values,
                notes=["판넬 두께, 하지철물, 후레싱, 실란트, 고정 피스, H빔 돌출 간격을 함께 검토한다."],
                evidence_file_ids=[file_id] if file_id else [],
                confidence=0.72,
            )
        )
    if "천장마감" in tags:
        out.append(
            DetailPattern(
                "천장 마감 검토 구성",
                "천장마감",
                elements=sorted(set(elem_names + ["CEILING_SYSTEM", "DIMENSION", "MATERIAL_NOTE"])),
                materials=material_names,
                typical_dimensions=dim_values,
                notes=["경량철골 천장틀, 석고텍스, 보 하부 높이, 마감 여유 공간, 최종 천장고를 함께 검토한다."],
                evidence_file_ids=[file_id] if file_id else [],
                confidence=0.7,
            )
        )
    return out
