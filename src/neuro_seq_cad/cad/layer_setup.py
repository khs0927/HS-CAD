"""
cad.layer_setup – 표준 CAD 레이어 및 라인타입 설정
===================================================
open-image-to-zwcad 프로젝트의 레이어 표준을 그대로 따르되,
neuro_seq_cad 파이프라인에서 필요한 최소 레이어 세트만 설정한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:
    import ezdxf
except ImportError:
    ezdxf = None  # type: ignore[assignment]


@dataclass
class LayerDef:
    """표준 레이어 하나의 정의."""
    name: str
    color: int
    linetype: str = "Continuous"
    lineweight: int = 25  # 0.01mm 단위
    description: str = ""


# ── 표준 레이어 사전 ──
LAYER_DEFS: dict[str, LayerDef] = {
    "COL":       LayerDef("COL",       1,  "Continuous", 50, "골조"),
    "WAL1":      LayerDef("WAL1",      7,  "Continuous", 35, "경량벽/일반벽"),
    "WAL2":      LayerDef("WAL2",      3,  "Continuous", 35, "조적"),
    "WAL3":      LayerDef("WAL3",      8,  "Continuous", 25, "기타 벽"),
    "DOOR":      LayerDef("DOOR",      2,  "Continuous", 25, "문"),
    "WIN":       LayerDef("WIN",       4,  "Continuous", 25, "창호"),
    "WINBAR":    LayerDef("WINBAR",    4,  "Continuous", 18, "창호 바"),
    "STAIR":     LayerDef("STAIR",     3,  "Continuous", 25, "계단"),
    "DIM":       LayerDef("DIM",       5,  "Continuous", 15, "치수"),
    "DIMLE":     LayerDef("DIMLE",     5,  "Continuous", 15, "지시선"),
    "CEN":       LayerDef("CEN",       6,  "CENTER",    15, "중심선"),
    "CEN1":      LayerDef("CEN1",      6,  "CENTER",    15, "골조 중심선"),
    "ELE":       LayerDef("ELE",       4,  "Continuous", 15, "입면선"),
    "TXT":       LayerDef("TXT",       7,  "Continuous", 25, "문자"),
    "FUR":       LayerDef("FUR",       8,  "Continuous", 15, "가구"),
    "ZONE":      LayerDef("ZONE",      4,  "Continuous", 25, "구역계"),
    "QA-REVIEW": LayerDef("QA-REVIEW", 1,  "DASHED",    15, "검수용 QA 레이어"),
    "UNDERLAY":  LayerDef("UNDERLAY",  9,  "Continuous",  9, "원본 이미지 언더레이"),
}


def _ensure_linetypes(doc: Any) -> None:
    """라인타입이 아직 없으면 생성."""
    lt_defs = {
        "CENTER":  {"desc": "Center _ . _ . _", "pattern": [2.0, -0.5, 0.5, -0.5]},
        "DASHED":  {"desc": "Dashed _ _ _ _",   "pattern": [1.0, -0.5]},
        "HIDDEN":  {"desc": "Hidden _ _ _ _",   "pattern": [0.5, -0.25]},
    }
    for name, props in lt_defs.items():
        if name not in doc.linetypes:
            try:
                doc.linetypes.new(
                    name=name,
                    dxfattribs={"description": props["desc"], "pattern": props["pattern"]},
                )
            except Exception:
                pass


def ensure_layers(doc: Any) -> None:
    """ezdxf 문서에 표준 레이어를 모두 등록한다."""
    if ezdxf is None:
        return

    _ensure_linetypes(doc)

    for name, spec in LAYER_DEFS.items():
        if name not in doc.layers:
            try:
                doc.layers.new(
                    name=name,
                    dxfattribs={
                        "color": spec.color,
                        "linetype": spec.linetype,
                        "lineweight": spec.lineweight,
                    },
                )
            except Exception:
                pass
