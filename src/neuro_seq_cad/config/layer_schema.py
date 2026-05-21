from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LayerSpec:
    name: str
    description: str
    color: int = 7
    linetype: str = "CONTINUOUS"
    is_hatch_layer: bool = False
    is_review_layer: bool = False


DEFAULT_LAYERS: dict[str, LayerSpec] = {
    "COL": LayerSpec("COL", "기둥 / 구조체", 2),
    "WAL1": LayerSpec("WAL1", "경량벽 / 일반 칸막이", 8),
    "WAL2": LayerSpec("WAL2", "조적벽 / 두꺼운 벽", 9),
    "WAL3": LayerSpec("WAL3", "기타 벽체 후보", 30),
    "WAL_HATCH": LayerSpec("WAL_HATCH", "벽체 solid hatch", 253, is_hatch_layer=True),
    "DOOR": LayerSpec("DOOR", "문", 4),
    "DOOR_SWING": LayerSpec("DOOR_SWING", "문 여닫이 arc", 4),
    "WIN": LayerSpec("WIN", "창", 5),
    "WINBAR": LayerSpec("WINBAR", "창 프레임", 5),
    "STAIR": LayerSpec("STAIR", "계단", 6),
    "DIM": LayerSpec("DIM", "치수선", 3),
    "DIMLE": LayerSpec("DIMLE", "치수 지시선 / 주석", 3),
    "CEN": LayerSpec("CEN", "중심선", 1, "CENTER"),
    "CEN1": LayerSpec("CEN1", "보조 중심선", 1, "CENTER"),
    "ELE": LayerSpec("ELE", "입면/레벨선", 6),
    "TEXT": LayerSpec("TEXT", "OCR 문자", 7),
    "FURN": LayerSpec("FURN", "가구/비구조 참고", 8),
    "RAW_LINES": LayerSpec("RAW_LINES", "원본 선분 추출 결과", 252, is_review_layer=True),
    "AI_LOWCONF": LayerSpec("AI_LOWCONF", "저신뢰 객체", 1, is_review_layer=True),
    "QA_MARKUP": LayerSpec("QA_MARKUP", "경고/검수 표시", 1, is_review_layer=True),
}


def ensure_dxf_layers(doc: Any) -> None:
    """Create all generated-DXF layers on an ezdxf document.

    기존 사무소 DWG 레이어를 바꾸는 함수가 아니다. 이미지/PDF에서 독립 DXF
    초안을 만들 때만 생성용 레이어를 보장한다.
    """

    for spec in DEFAULT_LAYERS.values():
        if spec.name in doc.layers:
            layer = doc.layers.get(spec.name)
        else:
            layer = doc.layers.add(spec.name)
        layer.dxf.color = spec.color
        try:
            layer.dxf.linetype = spec.linetype
        except Exception:
            pass
