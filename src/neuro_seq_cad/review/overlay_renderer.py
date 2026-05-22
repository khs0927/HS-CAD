"""
overlay_renderer.py — 검출 및 융합된 건축 요소를 원본 도면 위에 시각화 오버레이하는 렌더러
======================================================================================
원본 평면도 이미지 배경 위에 벽체(검정), 기둥(빨강), 문(노랑/아크), 창문(파랑) 등의
최종 융합 데이터를 반투명 알파 블렌딩 오버레이로 그려 시각적 검수용 이미지를 생성합니다.
이 결과물은 사용자의 육안 검수 및 VLM(Vision-Language Model)의 2차 피드백/보정용 분석 이미지로 활용됩니다.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont
from neuro_seq_cad.fusion.evidence_graph import EvidenceGraph, EvidenceEntity

logger = logging.getLogger(__name__)


class OverlayRenderer:
    """EvidenceGraph 데이터를 원본 도면 이미지에 오버레이 렌더링하는 시각화 도구."""

    def __init__(self, evidence_graph: EvidenceGraph) -> None:
        """
        OverlayRenderer 초기화.

        Parameters
        ----------
        evidence_graph : EvidenceGraph
            오버레이할 요소들이 담긴 증거 그래프.
        """
        self.graph = evidence_graph

    def render(self, base_image_path: str | Path, output_path: str | Path) -> Path:
        """
        원본 이미지 위에 증거 요소를 드로잉하여 오버레이 분석 이미지를 저장합니다.

        Parameters
        ----------
        base_image_path : str | Path
            배경으로 사용할 원본 평면도 이미지 파일 경로.
        output_path : str | Path
            오버레이 완료된 이미지를 저장할 출력 경로.

        Returns
        -------
        Path
            저장된 오버레이 이미지의 절대 경로.
        """
        base_image_path = Path(base_image_path).resolve()
        output_path = Path(output_path).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 1. 배경 이미지 로드 (RGBA 변환)
        if not base_image_path.exists():
            # 이미지가 없을 경우 대체용 흰색 캔버스 생성
            logger.warning(
                "배경 이미지가 없어 흰색 임시 캔버스를 만듭니다. 경로: %s",
                base_image_path
            )
            width = self.graph.pipeline.image_width or 1200
            height = self.graph.pipeline.image_height or 800
            bg_img = Image.new("RGBA", (width, height), (255, 255, 255, 255))
        else:
            try:
                bg_img = Image.open(base_image_path).convert("RGBA")
            except Exception as e:
                logger.error("이미지 파일 로드 실패: %s. 흰색 캔버스로 폴백합니다.", e)
                width = self.graph.pipeline.image_width or 1200
                height = self.graph.pipeline.image_height or 800
                bg_img = Image.new("RGBA", (width, height), (255, 255, 255, 255))

        # 2. 오버레이 드로잉용 반투명 레이어 생성 (배경과 동일 크기)
        overlay = Image.new("RGBA", bg_img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # 3. 요소 렌더링 순서 설정 (방 구역 → 가구 → 벽체 → 문/창문 → 기둥 → 텍스트)
        # 밑에 깔리는 구역계나 가구를 먼저 그린 뒤 벽과 심볼을 올려 가독성을 확보합니다.
        self._draw_rooms(draw)
        self._draw_furniture(draw)
        self._draw_walls(draw)
        self._draw_windows(draw)
        self._draw_doors(draw)
        self._draw_columns(draw)
        self._draw_texts_and_dimensions(draw)

        # 4. 반투명 레이어와 배경 이미지 알파 합성 (Alpha composite)
        fused_image = Image.alpha_composite(bg_img, overlay)

        # 5. 결과물 저장 (JPG/PNG 변환 호환성 처리)
        if output_path.suffix.lower() in [".jpg", ".jpeg"]:
            # JPG는 알파 채널이 없으므로 RGB 변환하여 저장
            final_img = fused_image.convert("RGB")
        else:
            final_img = fused_image

        try:
            final_img.save(output_path)
            logger.info("성공적으로 QA 오버레이 리포트 이미지를 저장했습니다: %s", output_path)
        except Exception as e:
            logger.error("오버레이 이미지 저장 실패: %s", e)
            raise RuntimeError(f"Overlay save failed: {e}") from e

        return output_path

    def _draw_walls(self, draw: ImageDraw.ImageDraw) -> None:
        """벽체 레이어 시각화 (짙은 차콜색 벽감 및 두꺼운 외곽선)."""
        walls = self.graph.by_type("wall")
        # RGBA: (44, 62, 80, 200) — 다크 네이비 / 차콜
        fill_color = (44, 62, 80, 50)
        outline_color = (44, 62, 80, 220)

        for wall in walls:
            if wall.polygon and wall.polygon.points:
                pts = [tuple(p) for p in wall.polygon.points]
                if len(pts) >= 2:
                    # 닫힌 폴리곤은 채우기 및 아웃라인 드로잉
                    if wall.polygon.closed:
                        draw.polygon(pts, fill=fill_color, outline=outline_color, width=4)
                    else:
                        draw.line(pts, fill=outline_color, width=4)
            elif wall.points:
                for seg in wall.points:
                    if len(seg) >= 4:
                        draw.line(
                            [(seg[0], seg[1]), (seg[2], seg[3])],
                            fill=outline_color,
                            width=4
                        )
            elif wall.bbox:
                b = wall.bbox
                draw.rectangle(
                    [b.x1, b.y1, b.x2, b.y2],
                    fill=fill_color,
                    outline=outline_color,
                    width=4
                )

    def _draw_columns(self, draw: ImageDraw.ImageDraw) -> None:
        """기둥 시각화 (빨강색 단색 채우기 및 선명한 아웃라인)."""
        columns = self.graph.by_type("column")
        # RGBA: (231, 76, 60) — 코랄 레드
        fill_color = (231, 76, 60, 140)
        outline_color = (231, 76, 60, 255)

        for col in columns:
            if col.bbox:
                b = col.bbox
                draw.rectangle(
                    [b.x1, b.y1, b.x2, b.y2],
                    fill=fill_color,
                    outline=outline_color,
                    width=3
                )

    def _draw_doors(self, draw: ImageDraw.ImageDraw) -> None:
        """문 시각화 (노란색 상자 및 힌지 스윙 점선 아크 흉내)."""
        doors = self.graph.by_type("door")
        # RGBA: (241, 196, 15) — 선명한 엘로우
        fill_color = (241, 196, 15, 60)
        outline_color = (241, 196, 15, 255)

        for door in doors:
            if door.bbox:
                b = door.bbox
                # 1. 문 검출 영역 바운딩 박스 드로잉
                draw.rectangle(
                    [b.x1, b.y1, b.x2, b.y2],
                    fill=fill_color,
                    outline=outline_color,
                    width=2
                )
                
                # 2. 열리는 스윙 아크 시각 지시선 드로잉 (대각 X선 및 원호 삽입)
                # 시각적으로 문 블록임을 한눈에 알 수 있게 상자 내부에 대각선 표시
                cx, cy = b.center
                # 힌지 추정 위치에서 회전 스윙 가이드라인 추가
                if b.width >= b.height:
                    # 가로문: 좌측 하단에서 우측 상단으로 열리는 아크 모사
                    draw.line([(b.x1, b.y2), (b.x2, b.y1)], fill=outline_color, width=1)
                else:
                    # 세로문: 우측 하단에서 좌측 상단으로
                    draw.line([(b.x2, b.y2), (b.x1, b.y1)], fill=outline_color, width=1)

    def _draw_windows(self, draw: ImageDraw.ImageDraw) -> None:
        """창문 시각화 (하늘색 시안 계열의 이중선 프레임 모사)."""
        windows = self.graph.by_type("window")
        # RGBA: (52, 152, 219) — 스카이 블루
        fill_color = (52, 152, 219, 80)
        outline_color = (52, 152, 219, 255)

        for win in windows:
            if win.bbox:
                b = win.bbox
                draw.rectangle(
                    [b.x1, b.y1, b.x2, b.y2],
                    fill=fill_color,
                    outline=outline_color,
                    width=2
                )
                
                # 내부 유리창 창살 효과를 주기 위해 정중앙 축선(Glass Line) 드로잉
                if b.width >= b.height:
                    # 가로로 긴 창
                    mid_y = (b.y1 + b.y2) / 2.0
                    draw.line([(b.x1, mid_y), (b.x2, mid_y)], fill=outline_color, width=1)
                else:
                    # 세로로 긴 창
                    mid_x = (b.x1 + b.x2) / 2.0
                    draw.line([(mid_x, b.y1), (mid_x, b.y2)], fill=outline_color, width=1)

    def _draw_rooms(self, draw: ImageDraw.ImageDraw) -> None:
        """구역/방 영역 시각화 (반투명 파스텔 그린 구역 채우기)."""
        rooms = self.graph.by_type("room")
        # RGBA: (46, 204, 113) — 연녹색
        fill_color = (46, 204, 113, 30)
        outline_color = (46, 204, 113, 120)

        for room in rooms:
            if room.polygon and room.polygon.points:
                pts = [tuple(p) for p in room.polygon.points]
                if len(pts) >= 3:
                    draw.polygon(pts, fill=fill_color, outline=outline_color, width=2)
            elif room.bbox:
                b = room.bbox
                draw.rectangle(
                    [b.x1, b.y1, b.x2, b.y2],
                    fill=fill_color,
                    outline=outline_color,
                    width=2
                )

    def _draw_furniture(self, draw: ImageDraw.ImageDraw) -> None:
        """가구 시각화 (연한 보라색/갈색 박스)."""
        furniture = self.graph.by_type("furniture")
        # RGBA: (155, 89, 182) — 아메지스트 퍼플
        fill_color = (155, 89, 182, 35)
        outline_color = (155, 89, 182, 150)

        for furn in furniture:
            if furn.bbox:
                b = furn.bbox
                draw.rectangle(
                    [b.x1, b.y1, b.x2, b.y2],
                    fill=fill_color,
                    outline=outline_color,
                    width=1
                )

    def _draw_texts_and_dimensions(self, draw: ImageDraw.ImageDraw) -> None:
        """텍스트 및 치수선 시각 지시 마크업 렌더링."""
        texts = self.graph.by_type("text")
        dimensions = self.graph.by_type("dimension")

        # 1. 치수선
        # RGBA: (149, 165, 166) — 차분한 그레이
        dim_color = (149, 165, 166, 220)
        for dim in dimensions:
            if dim.points:
                for seg in dim.points:
                    if len(seg) >= 4:
                        # 시작점에서 끝점선분 드로잉
                        draw.line(
                            [(seg[0], seg[1]), (seg[2], seg[3])],
                            fill=dim_color,
                            width=2
                        )
                        # 끝마디 단부에 크로스 해치 슬래시 표시 (건축용 치수 사선)
                        d_size = 5.0
                        draw.line([(seg[0] - d_size, seg[1] - d_size), (seg[0] + d_size, seg[1] + d_size)], fill=dim_color, width=2)
                        draw.line([(seg[2] - d_size, seg[3] - d_size), (seg[2] + d_size, seg[3] + d_size)], fill=dim_color, width=2)
            elif dim.bbox:
                b = dim.bbox
                draw.rectangle([b.x1, b.y1, b.x2, b.y2], outline=dim_color, width=1)

        # 2. 문자/OCR 검출 바운딩 박스
        # RGBA: (155, 89, 182)
        txt_box_color = (155, 89, 182, 200)
        for t in texts:
            if t.bbox:
                b = t.bbox
                # 텍스트가 담겨 있는 bbox 테두리 드로잉
                draw.rectangle([b.x1, b.y1, b.x2, b.y2], outline=txt_box_color, width=1)
                
                # 폰트 로드 실패 대비 디폴트 텍스트 렌더링
                # Pillow의 기본 폰트 또는 시스템 기본 폰트 로드 시도
                try:
                    # Windows 표준 맑은 고딕(Malgun Gothic) 또는 Arial 시도
                    font = ImageFont.truetype("malgun.ttf", size=14)
                except Exception:
                    font = ImageFont.load_default()

                # 반투명 박스 배경 위에 텍스트를 인쇄하여 가독성 증대
                tx, ty = b.x1, max(0.0, b.y1 - 18.0)
                draw.rectangle(
                    [tx, ty, tx + len(t.text) * 8.5 + 4, ty + 16],
                    fill=(50, 50, 50, 200)
                )
                draw.text(
                    (tx + 2, ty + 1),
                    t.text,
                    fill=(255, 255, 255, 255),
                    font=font
                )
