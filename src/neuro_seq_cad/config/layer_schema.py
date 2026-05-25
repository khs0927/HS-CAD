"""
layer_schema.py — CAD 레이어 스키마 정의 및 ezdxf 문서 레이어 생성

표준 CAD 레이어 구조:
  - 구조체: COL (기둥), WAL1/WAL2/WAL3 (벽체 종류별)
  - 개구부: DOOR (문), WIN (창문), WINBAR (창살)
  - 기타 건축요소: STAIR (계단), ELE (엘리베이터)
  - 치수/중심선: DIM, DIMLE, CEN, CEN1
  - 텍스트/가구: TEXT, FURN
  - QA/언더레이: QA-REVIEW, UNDERLAY

색상 번호는 AutoCAD ACI (AutoCAD Color Index) 기준:
  1=빨강, 2=노랑, 3=녹색, 4=시안, 5=파랑,
  6=마젠타, 7=흰색/검정, 8=회색, 9=밝은회색, 253=어두운회색
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Dict

from pydantic import BaseModel, Field

if TYPE_CHECKING:  # pragma: no cover - typing only
    import ezdxf  # type: ignore[import-not-found]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 레이어 정의 모델 (Layer definition Pydantic model)
# ---------------------------------------------------------------------------
class LayerDefinition(BaseModel):
    """단일 CAD 레이어의 속성 정의.

    Attributes:
        name: 레이어 이름 (예: "WAL1")
        color: ACI 색상 번호 (1~255)
        linetype: 선종류 (Continuous / CENTER / DASHED 등)
        lineweight: 선 두께 (1/100 mm 단위, 예: 25 = 0.25mm)
        description: 레이어 용도 설명 (한국어)
    """

    name: str = Field(..., min_length=1, max_length=255, description="레이어 이름")
    color: int = Field(..., ge=1, le=255, description="ACI 색상 번호")
    linetype: str = Field(default="Continuous", description="선종류")
    lineweight: int = Field(default=25, ge=0, le=211, description="선 두께 (1/100mm)")
    description: str = Field(default="", description="레이어 용도 설명")


# ---------------------------------------------------------------------------
# 표준 레이어 딕셔너리 (Standard CAD layers dictionary)
# ---------------------------------------------------------------------------
# fmt: off
CAD_LAYERS: Dict[str, LayerDefinition] = {
    # ── 구조체 (Structural) ──────────────────────────────────────────────
    "COL": LayerDefinition(
        name="COL", color=1, linetype="Continuous", lineweight=50,
        description="기둥 (Column) — 구조 기둥 외곽선",
    ),
    "WAL1": LayerDefinition(
        name="WAL1", color=7, linetype="Continuous", lineweight=50,
        description="벽체 1 (주요 외벽, 내력벽)",
    ),
    "WAL2": LayerDefinition(
        name="WAL2", color=3, linetype="Continuous", lineweight=35,
        description="벽체 2 (내부 칸막이벽)",
    ),
    "WAL3": LayerDefinition(
        name="WAL3", color=8, linetype="Continuous", lineweight=25,
        description="벽체 3 (경량 파티션, 마감벽)",
    ),

    # ── 개구부 (Openings) ────────────────────────────────────────────────
    "DOOR": LayerDefinition(
        name="DOOR", color=2, linetype="Continuous", lineweight=25,
        description="문 (Door) — 회전문, 미닫이문 등",
    ),
    "WIN": LayerDefinition(
        name="WIN", color=4, linetype="Continuous", lineweight=25,
        description="창문 (Window) — 이중선 프레임",
    ),
    "WINBAR": LayerDefinition(
        name="WINBAR", color=4, linetype="Continuous", lineweight=13,
        description="창살 (Window bar) — 창문 내부 분할선",
    ),

    # ── 수직 동선 (Vertical circulation) ─────────────────────────────────
    "STAIR": LayerDefinition(
        name="STAIR", color=3, linetype="Continuous", lineweight=25,
        description="계단 (Staircase)",
    ),
    "ELE": LayerDefinition(
        name="ELE", color=9, linetype="Continuous", lineweight=25,
        description="엘리베이터 (Elevator)",
    ),

    # ── 치수 및 중심선 (Dimensions & center lines) ───────────────────────
    "DIM": LayerDefinition(
        name="DIM", color=5, linetype="Continuous", lineweight=13,
        description="치수선 (Dimension line)",
    ),
    "DIMLE": LayerDefinition(
        name="DIMLE", color=5, linetype="Continuous", lineweight=13,
        description="치수 보조선 (Dimension leader / extension line)",
    ),
    "CEN": LayerDefinition(
        name="CEN", color=6, linetype="CENTER", lineweight=13,
        description="중심선 (Center line) — 기둥·벽 중심",
    ),
    "CEN1": LayerDefinition(
        name="CEN1", color=8, linetype="CENTER", lineweight=13,
        description="보조 중심선 (Secondary center line)",
    ),

    # ── 텍스트·가구 (Text & furniture) ───────────────────────────────────
    "TEXT": LayerDefinition(
        name="TEXT", color=7, linetype="Continuous", lineweight=13,
        description="텍스트 주석 (Room names, labels)",
    ),
    "FURN": LayerDefinition(
        name="FURN", color=253, linetype="Continuous", lineweight=13,
        description="가구 (Furniture) — 싱크, 욕조, 변기 등",
    ),

    # ── QA / 참조 (QA / Reference) ───────────────────────────────────────
    "QA-REVIEW": LayerDefinition(
        name="QA-REVIEW", color=1, linetype="DASHED", lineweight=25,
        description="QA 검토 마크업 (품질 확인용 오버레이)",
    ),
    "UNDERLAY": LayerDefinition(
        name="UNDERLAY", color=9, linetype="Continuous", lineweight=0,
        description="하부 래스터 이미지 배경 참조",
    ),
}
# fmt: on

# ---------------------------------------------------------------------------
# 요소 타입 → 레이어 매핑 테이블
# ---------------------------------------------------------------------------
# 검출 모델이 반환하는 클래스 이름(소문자)을 레이어 키에 매핑합니다.
# 매핑에 없는 클래스는 기본 레이어("QA-REVIEW")로 지정합니다.
_ELEMENT_TO_LAYER: Dict[str, str] = {
    # 구조체
    "column": "COL",
    "col": "COL",
    "pillar": "COL",
    # 벽체
    "wall": "WAL1",
    "wall1": "WAL1",
    "wall2": "WAL2",
    "wall3": "WAL3",
    "exterior_wall": "WAL1",
    "interior_wall": "WAL2",
    "partition": "WAL3",
    # 개구부
    "door": "DOOR",
    "entrance": "DOOR",
    "sliding_door": "DOOR",
    "window": "WIN",
    "window_bar": "WINBAR",
    # 수직 동선
    "stair": "STAIR",
    "staircase": "STAIR",
    "elevator": "ELE",
    "lift": "ELE",
    # 치수
    "dimension": "DIM",
    "dim": "DIM",
    "dimension_leader": "DIMLE",
    "center_line": "CEN",
    # 텍스트·가구
    "text": "TEXT",
    "label": "TEXT",
    "room_name": "TEXT",
    "furniture": "FURN",
    "furn": "FURN",
    "sink": "FURN",
    "toilet": "FURN",
    "bathtub": "FURN",
    "kitchen": "FURN",
}


# ---------------------------------------------------------------------------
# 공개 함수 (Public API)
# ---------------------------------------------------------------------------
def get_layer_for_element(
    element_type: str,
    *,
    default_layer: str = "QA-REVIEW",
) -> LayerDefinition:
    """검출된 요소 타입 문자열로 적절한 레이어 정의를 반환합니다.

    Args:
        element_type: 검출 모델이 반환한 클래스 이름 (대소문자 무관).
        default_layer: 매핑이 없을 때 사용할 기본 레이어 키.

    Returns:
        해당 요소에 매핑된 ``LayerDefinition``.

    Examples:
        >>> layer = get_layer_for_element("door")
        >>> layer.name
        'DOOR'
        >>> layer.color
        2
    """
    normalized = element_type.strip().lower()
    layer_key = _ELEMENT_TO_LAYER.get(normalized, default_layer)

    if layer_key not in CAD_LAYERS:
        logger.warning(
            "레이어 키 '%s'가 CAD_LAYERS에 없습니다. QA-REVIEW로 대체합니다.",
            layer_key,
        )
        layer_key = "QA-REVIEW"

    return CAD_LAYERS[layer_key]


def setup_layers(doc: ezdxf.document.Drawing) -> None:
    """ezdxf 문서에 CAD_LAYERS 딕셔너리의 모든 레이어를 등록합니다.

    이미 존재하는 레이어는 건너뛰고, 필요한 선종류(CENTER, DASHED)를
    먼저 문서에 추가합니다.

    Args:
        doc: 대상 ezdxf Drawing 객체.

    Raises:
        ImportError: ezdxf가 설치되어 있지 않을 때.
    """
    try:
        import ezdxf  # noqa: F401 — 타입 체크용
    except ImportError as exc:
        raise ImportError(
            "ezdxf 패키지가 필요합니다. 설치: pip install ezdxf"
        ) from exc

    # ── 선종류 사전 등록 ──
    # CENTER, DASHED 등 비표준 선종류를 문서에 미리 추가합니다.
    # ezdxf는 acadiso.lin 기반 선종류를 내장하므로 이름만 등록하면 됩니다.
    _ensure_linetype(doc, "CENTER", "Center line", [1.25, -0.625, 0.25, -0.625])
    _ensure_linetype(doc, "DASHED", "Dashed line", [0.75, -0.375])

    # ── 레이어 생성 ──
    for layer_def in CAD_LAYERS.values():
        if layer_def.name in doc.layers:
            logger.debug("레이어 '%s' 이미 존재 — 건너뜀", layer_def.name)
            continue

        new_layer = doc.layers.add(layer_def.name)
        new_layer.color = layer_def.color
        new_layer.dxf.lineweight = layer_def.lineweight

        # 선종류가 문서에 등록되어 있을 때만 설정
        if layer_def.linetype != "Continuous":
            try:
                _ = doc.linetypes.get(layer_def.linetype)
                new_layer.dxf.linetype = layer_def.linetype
            except ezdxf.DXFTableEntryError:
                logger.warning(
                    "선종류 '%s'를 문서에서 찾을 수 없어 Continuous로 대체합니다.",
                    layer_def.linetype,
                )

        logger.debug(
            "레이어 생성: %s (color=%d, lt=%s, lw=%d)",
            layer_def.name,
            layer_def.color,
            layer_def.linetype,
            layer_def.lineweight,
        )

    logger.info("CAD 레이어 %d개 등록 완료", len(CAD_LAYERS))


def list_layers() -> list[LayerDefinition]:
    """등록된 모든 레이어 정의를 리스트로 반환합니다."""
    return list(CAD_LAYERS.values())


# ---------------------------------------------------------------------------
# 내부 헬퍼 (Internal helpers)
# ---------------------------------------------------------------------------
def _ensure_linetype(
    doc: ezdxf.document.Drawing,
    name: str,
    description: str,
    pattern: list[float],
) -> None:
    """선종류가 문서에 없으면 추가합니다.

    Args:
        doc: ezdxf Drawing.
        name: 선종류 이름.
        description: 선종류 설명.
        pattern: 대시-간격 패턴 리스트.
    """
    try:
        import ezdxf  # noqa: F811
    except ImportError:
        return

    if name in doc.linetypes:
        return

    try:
        doc.linetypes.add(
            name,
            pattern=[sum(abs(v) for v in pattern)] + pattern,
            description=description,
        )
        logger.debug("선종류 '%s' 등록 완료", name)
    except ezdxf.DXFTableEntryError:
        logger.debug("선종류 '%s' 이미 존재합니다.", name)
