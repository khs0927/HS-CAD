"""
cad.dimension_builder – 치수선(Dimension) 엔티티 생성
=====================================================
OCR/파서에서 검출된 치수 정보를 ezdxf ALIGNED DIMENSION 으로
CAD 문서에 추가한다.

좌표 변환:
  이미지 좌표 (x_img, y_img)
    → CAD 좌표 (cad_x, cad_y)
  cad_x = x_img * scale
  cad_y = (image_height - y_img) * scale
"""

from __future__ import annotations

from typing import Any, Protocol


class CoordinateTransformer(Protocol):
    """좌표 변환 프로토콜."""
    def transform(self, x: float, y: float) -> tuple[float, float]: ...


def add_dimensions(
    msp: Any,
    dimension_entities: list[dict[str, Any]],
    transformer: CoordinateTransformer,
) -> None:
    """
    치수 엔티티 목록을 ALIGNED DIMENSION 으로 modelspace 에 추가.

    Parameters
    ----------
    msp : ezdxf Modelspace
        CAD 문서의 모델스페이스.
    dimension_entities : list[dict]
        각 항목은 아래 키를 포함:
          - p1: [x, y] — 시작점 (이미지 좌표)
          - p2: [x, y] — 끝점 (이미지 좌표)
          - text (str, optional): 치수 텍스트 override (예: "3,600")
          - offset (float, optional): 치수선 오프셋 거리 (CAD mm). 기본 300
          - entity_id (str, optional): 원본 엔티티 ID
    transformer : CoordinateTransformer
        이미지 좌표 → CAD 좌표 변환기.

    Notes
    -----
    치수선 텍스트 위치 계산:
      두 점의 중간점에서 법선 방향으로 offset 만큼 이동.
      이를 통해 치수선이 벽체와 겹치지 않도록 한다.
    """
    for item in dimension_entities:
        p1_raw = item.get("p1", [0.0, 0.0])
        p2_raw = item.get("p2", [0.0, 0.0])
        text_override = item.get("text", "")
        offset = float(item.get("offset", 300.0))

        # 이미지 좌표 → CAD 좌표 변환
        cad_p1 = transformer.transform(float(p1_raw[0]), float(p1_raw[1]))
        cad_p2 = transformer.transform(float(p2_raw[0]), float(p2_raw[1]))

        # 치수선 텍스트 위치 — 두 점의 중간점에서 오프셋
        # 법선 방향 계산 (dx, dy 의 수직 벡터)
        dx = cad_p2[0] - cad_p1[0]
        dy = cad_p2[1] - cad_p1[1]
        length = (dx ** 2 + dy ** 2) ** 0.5

        if length < 1e-6:
            continue  # 거의 같은 점이면 건너뜀

        # 법선 단위 벡터 (반시계 방향 90°)
        nx = -dy / length
        ny = dx / length

        # 중간점 + 법선 오프셋
        mid_x = (cad_p1[0] + cad_p2[0]) / 2.0 + nx * offset
        mid_y = (cad_p1[1] + cad_p2[1]) / 2.0 + ny * offset

        try:
            dim = msp.add_aligned_dim(
                p1=cad_p1,
                p2=cad_p2,
                distance=offset,
                override={"layer": "DIM"},
            )
            if text_override:
                dim.dimension.dxf.text = text_override
            dim.render()
        except Exception:
            # ALIGNED_DIM 이 지원되지 않는 경우 폴백: 단순 선 + 텍스트
            try:
                msp.add_line(cad_p1, cad_p2, dxfattribs={"layer": "DIM"})
                if text_override:
                    msp.add_mtext(
                        text_override,
                        dxfattribs={
                            "layer": "DIM",
                            "char_height": 200.0,
                            "insert": (mid_x, mid_y),
                            "attachment_point": 5,  # Middle Center
                        },
                    )
            except Exception:
                pass
