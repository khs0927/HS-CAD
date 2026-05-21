from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable, Sequence


@dataclass(slots=True)
class DetailPattern:
    pattern_name: str
    situation_tag: str
    elements: list[str]
    materials: list[str]
    typical_dimensions: list[str]
    notes: list[str]
    evidence_file_ids: list[str]
    confidence: float = 0.65

    def to_dict(self) -> dict:
        return asdict(self)


def build_detail_patterns(
    *,
    file_id: str,
    situations: Sequence[object],
    elements: Sequence[object],
    materials: Sequence[object],
    dimensions: Sequence[object],
) -> list[DetailPattern]:
    """단일 파일의 추출 결과에서 상세 패턴 후보를 만든다.

    여러 파일을 묶는 강화 학습은 corpus_learner에서 수행한다.
    """
    situation_tags = [_get(s, "tag", "unknown") for s in situations] or ["unknown"]
    element_names = sorted({_get(e, "canonical_element", "UNKNOWN") for e in elements if _get(e, "canonical_element", "UNKNOWN") != "UNKNOWN"})
    material_names = sorted({_get(m, "normalized_name", _get(m, "material_name", "")) for m in materials if _get(m, "normalized_name", _get(m, "material_name", ""))})
    dim_values = sorted({_get(d, "value", _get(d, "raw_text", "")) for d in dimensions if _get(d, "value", _get(d, "raw_text", ""))})

    results: list[DetailPattern] = []
    for tag in situation_tags:
        if tag == "unknown" and not (material_names or element_names or dim_values):
            continue

        pattern_name = _pattern_name(tag, element_names, material_names)
        notes = []
        if material_names:
            notes.append(f"반복 재료 후보: {', '.join(material_names[:6])}")
        if dim_values:
            notes.append(f"대표 치수/규격 후보: {', '.join(dim_values[:6])}")
        if element_names:
            notes.append(f"관련 건축 요소: {', '.join(element_names[:6])}")

        results.append(
            DetailPattern(
                pattern_name=pattern_name,
                situation_tag=tag,
                elements=element_names[:12],
                materials=material_names[:12],
                typical_dimensions=dim_values[:12],
                notes=notes,
                evidence_file_ids=[file_id],
                confidence=0.55 + min(0.35, 0.04 * (len(material_names) + len(element_names) + len(dim_values))),
            )
        )
    return results


def _get(obj: object, attr: str, default=None):
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return getattr(obj, attr, default)


def _pattern_name(tag: str, elements: list[str], materials: list[str]) -> str:
    if tag and tag != "unknown":
        return f"{tag} 상세 구성 후보"
    if "PANEL_SYSTEM" in elements or "panel" in materials:
        return "판넬/외장 상세 구성 후보"
    if "STRUCTURAL_STEEL" in elements:
        return "철골 접합 상세 구성 후보"
    if "WINDOW" in elements:
        return "창호 상세 구성 후보"
    return "일반 건축 상세 구성 후보"


def infer_detail_patterns(*, file_id: str, situations: list[object], elements: list[object] = [], materials: list[object] = [], dimensions: list[object] = []) -> list[DetailPattern]:
    """Compatibility wrapper expected by tests.

    ``elements`` is optional because many callers only provide situations,
    materials and dimensions.  An empty list is used when omitted.
    """
    return build_detail_patterns(
        file_id=file_id,
        situations=situations,
        elements=elements,
        materials=materials,
        dimensions=dimensions,
    )
