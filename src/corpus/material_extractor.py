from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Iterable, List


@dataclass(slots=True)
class MaterialMention:
    material_name: str
    normalized_name: str
    category: str
    context_text: str
    confidence: float = 0.75
    source_text_id: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


MATERIAL_KEYWORDS: dict[str, tuple[str, str]] = {
    "콘크리트": ("concrete", "structure"),
    "철근콘크리트": ("reinforced_concrete", "structure"),
    "RC": ("reinforced_concrete", "structure"),
    "철골": ("steel_structure", "structure"),
    "H빔": ("h_beam", "structural_steel"),
    "H-BEAM": ("h_beam", "structural_steel"),
    "형강": ("section_steel", "structural_steel"),
    "각파이프": ("square_pipe", "structural_steel"),
    "스틸": ("steel", "metal"),
    "알루미늄": ("aluminum", "metal"),
    "AL": ("aluminum", "metal"),
    "스테인리스": ("stainless_steel", "metal"),
    "STS": ("stainless_steel", "metal"),
    "유리": ("glass", "glazing"),
    "복층유리": ("insulated_glass", "glazing"),
    "로이유리": ("low_e_glass", "glazing"),
    "강화유리": ("tempered_glass", "glazing"),
    "접합유리": ("laminated_glass", "glazing"),
    "방화유리": ("fire_rated_glass", "glazing"),
    "창호": ("window_system", "opening"),
    "PVC": ("pvc", "opening"),
    "시스템창호": ("system_window", "opening"),
    "프로젝트창": ("project_window", "opening"),
    "방음문": ("soundproof_door", "acoustic"),
    "방음시창": ("soundproof_window", "acoustic"),
    "목문": ("wood_door", "door"),
    "철재문": ("steel_door", "door"),
    "방화문": ("fire_door", "fire_safety"),
    "글라스울": ("glasswool", "insulation"),
    "그라스울": ("glasswool", "insulation"),
    "미네랄울": ("mineral_wool", "insulation"),
    "EPS": ("eps", "insulation"),
    "우레탄": ("urethane", "insulation"),
    "단열재": ("insulation", "insulation"),
    "샌드위치패널": ("sandwich_panel", "panel"),
    "판넬": ("panel", "panel"),
    "패널": ("panel", "panel"),
    "징크": ("zinc", "finish"),
    "석고보드": ("gypsum_board", "ceiling_wall_finish"),
    "방화석고보드": ("fire_rated_gypsum_board", "fire_safety"),
    "석고텍스": ("gypsum_tex", "ceiling"),
    "텍스": ("tex_ceiling_tile", "ceiling"),
    "경량철골": ("lightweight_steel_frame", "ceiling"),
    "몰탈": ("mortar", "finish"),
    "타일": ("tile", "finish"),
    "방수": ("waterproofing", "waterproofing"),
    "우레탄방수": ("urethane_waterproofing", "waterproofing"),
    "시트방수": ("sheet_waterproofing", "waterproofing"),
    "실란트": ("sealant", "joint"),
    "코킹": ("caulking", "joint"),
    "후레싱": ("flashing", "panel_joint"),
    "플래싱": ("flashing", "panel_joint"),
    "마감캡": ("finish_cap", "panel_joint"),
    "흡음재": ("sound_absorber", "acoustic"),
    "차음재": ("sound_insulation", "acoustic"),
    "내화도장": ("fireproof_paint", "fire_safety"),
    "방청도장": ("anti_corrosion_paint", "coating"),
    "페인트": ("paint", "coating"),
}


def _context(text: str, start: int, end: int, radius: int = 45) -> str:
    return text[max(0, start - radius): min(len(text), end + radius)].strip()


def extract_materials_from_text(text: str, source_text_id: str | None = None) -> list[MaterialMention]:
    """건축 도면 텍스트에서 재료명을 추출한다.

    회사별 레이어명은 표준으로 삼지 않고, 텍스트 근거만 기반으로 일반 재료 지식으로 정규화한다.
    """
    if not text:
        return []

    mentions: list[MaterialMention] = []
    seen: set[tuple[str, int]] = set()

    for keyword, (normalized, category) in MATERIAL_KEYWORDS.items():
        flags = re.IGNORECASE if keyword.isascii() else 0
        pattern = re.escape(keyword)
        for match in re.finditer(pattern, text, flags):
            key = (normalized, match.start())
            if key in seen:
                continue
            seen.add(key)
            confidence = 0.82
            if category in {"acoustic", "fire_safety", "panel_joint", "insulation"}:
                confidence = 0.88
            mentions.append(
                MaterialMention(
                    material_name=match.group(0),
                    normalized_name=normalized,
                    category=category,
                    context_text=_context(text, match.start(), match.end()),
                    confidence=confidence,
                    source_text_id=source_text_id,
                )
            )

    return mentions


def extract_materials_from_texts(texts: Iterable[str]) -> list[MaterialMention]:
    """Extract material mentions from multiple texts."""
    results: list[MaterialMention] = []
    for idx, text in enumerate(texts):
        results.extend(extract_materials_from_text(str(text), source_text_id=f"text_{idx}"))
    return results


def extract_materials(text: str) -> list[MaterialMention]:
    """Compatibility wrapper expected by tests."""
    return extract_materials_from_text(text)
