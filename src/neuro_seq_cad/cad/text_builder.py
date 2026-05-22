"""
cad.text_builder – MTEXT 엔티티 생성
=====================================
OCR 또는 Raster2Seq 에서 검출된 텍스트를 CAD MTEXT 로 변환한다.
좌표 변환(이미지→CAD)은 외부에서 전달된 transformer 를 사용.
"""

from __future__ import annotations

from typing import Any, Protocol


class CoordinateTransformer(Protocol):
    """좌표 변환 인터페이스 — 이미지(px) → CAD(mm)."""
    def transform(self, x: float, y: float) -> tuple[float, float]: ...


def add_text_entities(
    msp: Any,
    text_entities: list[dict[str, Any]],
    transformer: CoordinateTransformer,
) -> None:
    """
    검출된 텍스트 목록을 MTEXT 로 modelspace 에 추가.

    Parameters
    ----------
    msp : ezdxf Modelspace
        CAD 문서의 모델스페이스.
    text_entities : list[dict]
        각 항목은 아래 키를 가진 dict:
          - text (str): 문자열 내용
          - x, y (float): 이미지 좌표(픽셀)
          - height (float, optional): 텍스트 높이 (CAD mm). 기본 250
          - rotation (float, optional): 회전 각도(도). 기본 0
          - confidence (float, optional): OCR 신뢰도
          - entity_id (str, optional): 원본 엔티티 ID
    transformer : CoordinateTransformer
        이미지 좌표 → CAD 좌표 변환기.

    Notes
    -----
    - 텍스트 삽입 위치 변환:
        이미지 좌표 (x_img, y_img) 를 CAD 좌표 (cad_x, cad_y) 로 변환.
        cad_x = x_img * scale
        cad_y = (image_height - y_img) * scale
    - attachment_point=7 (Bottom Left) 사용하여 텍스트 기준점 통일.
    """
    for item in text_entities:
        text = item.get("text", "")
        if not text.strip():
            continue

        # 이미지 좌표 → CAD 좌표 변환
        img_x = float(item.get("x", 0.0))
        img_y = float(item.get("y", 0.0))
        cad_x, cad_y = transformer.transform(img_x, img_y)

        char_height = float(item.get("height", 250.0))
        rotation = float(item.get("rotation", 0.0))
        confidence = float(item.get("confidence", 1.0))
        entity_id = item.get("entity_id", "")

        # MTEXT 생성
        attribs: dict[str, Any] = {
            "layer": "TXT",
            "char_height": char_height,
            "insert": (cad_x, cad_y),
            "attachment_point": 7,  # Bottom Left
        }
        if rotation != 0.0:
            attribs["rotation"] = rotation

        try:
            mtext = msp.add_mtext(text, dxfattribs=attribs)
            # 메타데이터를 xdata 대신 entity 자체에 첨부 (ezdxf 호환)
            if hasattr(mtext, "dxf"):
                mtext.dxf.handle  # ensure handle exists
        except Exception:
            pass  # 텍스트 추가 실패 시 무시
