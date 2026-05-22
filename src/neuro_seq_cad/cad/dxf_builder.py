"""
dxf_builder.py — EvidenceGraph를 다중 레이어 DXF 도면으로 최종 조립 및 빌드
==========================================================================
이 모듈은 융합 및 VLM 미세 조정이 완료된 EvidenceGraph 데이터를 로드하여,
ezdxf 라이브러리를 사용해 최종 .dxf CAD 도면 파일을 작성합니다.

주요 특징:
  1. ezdxf 문서 생성 및 표준 레이어 자동 등록 (config.layer_schema.setup_layers 사용)
  2. 표준 블록 정의 등록 (cad.block_factory.create_all_blocks 사용)
  3. 이미지(px) ↔ CAD(mm) 좌표 변환을 위한 ImageToCADTransformer 적용
  4. 벽체(wall), 기둥(column), 문(door), 창문(window), 텍스트(text), 치수선(dimension)의
     물리 좌표계 변환 및 정확한 기하 인스턴스/블록 생성
  5. 기하 형상(Polygon, BBox, Points)의 정밀한 레이어 매핑 및 예외 처리
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from neuro_seq_cad.config.settings import get_settings
from neuro_seq_cad.config.layer_schema import setup_layers, get_layer_for_element
from neuro_seq_cad.cad.block_factory import create_all_blocks
from neuro_seq_cad.cad.text_builder import add_text_entities
from neuro_seq_cad.cad.dimension_builder import add_dimensions
from neuro_seq_cad.io.coordinate_system import ImageToCADTransformer, Point2D
from neuro_seq_cad.fusion.evidence_graph import EvidenceGraph, EvidenceEntity

try:
    import ezdxf
except ImportError:
    ezdxf = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class DXFBuilder:
    """EvidenceGraph 데이터를 기반으로 고품질 다중 레이어 DXF 도면을 컴파일하는 빌더."""

    def __init__(self, evidence_graph: EvidenceGraph) -> None:
        """
        DXFBuilder 초기화.

        Parameters
        ----------
        evidence_graph : EvidenceGraph
            융합 및 검증이 완료된 도면 데이터 그래프.
        """
        self.graph = evidence_graph
        self.settings = get_settings()

        # 이미지 메타데이터
        self.image_height = self.graph.pipeline.image_height or 800
        self.scale_pixels_per_mm = self.graph.pipeline.scale_pixels_per_mm or 1.0

        # 좌표 변환기 초기화 (Image px ↔ CAD mm)
        self.transformer = ImageToCADTransformer(
            image_height=self.image_height,
            scale_factor=self.scale_pixels_per_mm
        )

        logger.info(
            "DXFBuilder 초기화 완료 — H=%d px, Scale=%.4f mm/px",
            self.image_height, self.scale_pixels_per_mm
        )

    def build(self, output_path: str | Path) -> Path:
        """
        도면 데이터를 기반으로 DXF 파일을 빌드 및 저장합니다.

        Parameters
        ----------
        output_path : str | Path
            출력할 DXF 파일 경로.

        Returns
        -------
        Path
            저장된 DXF 파일의 절대 경로.
        """
        if ezdxf is None:
            raise ImportError(
                "DXF 파일을 생성하려면 'ezdxf' 패키지가 필요합니다. 'pip install ezdxf'를 실행하십시오."
            )

        output_path = Path(output_path).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 1. DXF 문서 생성 (설정된 버전에 맞춰 생성)
        dxf_ver = self.settings.dxf_version
        try:
            doc = ezdxf.new(dxfversion=dxf_ver)
            logger.info("새 DXF 문서 생성 완료 (버전: %s)", dxf_ver)
        except Exception as e:
            logger.warning("DXF 버전 %s 생성 실패, R2010으로 폴백합니다. 에러: %s", dxf_ver, e)
            doc = ezdxf.new(dxfversion="R2010")

        # 2. 표준 레이어 설정
        setup_layers(doc)

        # 3. 표준 블록 설정
        create_all_blocks(doc)

        # 4. 모델 스페이스 획득
        msp = doc.modelspace()

        # 5. 엔티티 유형별 렌더링 파티셔닝
        self._render_walls(msp)
        self._render_columns(msp)
        self._render_doors(msp)
        self._render_windows(msp)
        self._render_text_and_dimensions(msp)
        self._render_other_entities(msp)

        # 6. DXF 파일 저장
        try:
            doc.saveas(output_path)
            logger.info("성공적으로 DXF 도면을 내보냈습니다: %s", output_path)
        except Exception as e:
            logger.error("DXF 도면 파일 저장 실패: %s", e)
            raise RuntimeError(f"DXF 저장 실패: {e}") from e

        return output_path

    def _render_walls(self, msp: Any) -> None:
        """벽체 엔티티들을 CAD 도면에 선 및 폴리라인으로 드로잉."""
        walls = self.graph.by_type("wall")
        logger.info("벽체 렌더링 중... 개수: %d", len(walls))

        for wall in walls:
            layer = wall.resolve_layer() or "WAL1"

            # 1. 폴리곤 기하 정보가 있는 경우 우선 렌더링
            if wall.polygon and wall.polygon.points:
                cad_points = self.transformer.transform_points(
                    [tuple(p) for p in wall.polygon.points],
                    to_cad=True
                )
                try:
                    msp.add_lwpolyline(
                        cad_points,
                        dxfattribs={"layer": layer},
                        close=wall.polygon.closed
                    )
                except Exception as e:
                    logger.debug("벽체 폴리라인 생성 오류: %s. 선분 단위로 대체합니다.", e)

            # 2. 선분 목록(points)이 있는 경우 선분 드로잉
            elif wall.points:
                for seg in wall.points:
                    if len(seg) >= 4:
                        p1_cad = self.transformer.to_cad(seg[0], seg[1])
                        p2_cad = self.transformer.to_cad(seg[2], seg[3])
                        msp.add_line(p1_cad, p2_cad, dxfattribs={"layer": layer})

            # 3. 바운딩 박스(bbox)가 있는 경우 닫힌 직사각형 폴리라인 생성
            elif wall.bbox:
                try:
                    cad_box = self.transformer.transform_bbox(wall.bbox.as_list())
                    pts = [
                        (cad_box.min_x, cad_box.min_y),
                        (cad_box.max_x, cad_box.min_y),
                        (cad_box.max_x, cad_box.max_y),
                        (cad_box.min_x, cad_box.max_y)
                    ]
                    msp.add_lwpolyline(pts, dxfattribs={"layer": layer}, close=True)
                except Exception as e:
                    logger.warning("벽체 바운딩 박스 변환 오류: %s", e)

    def _render_columns(self, msp: Any) -> None:
        """기둥 엔티티를 COLUMN_BLOCK 참조 인스턴스로 변환 삽입."""
        columns = self.graph.by_type("column")
        logger.info("기둥 렌더링 중... 개수: %d", len(columns))

        for col in columns:
            if not col.bbox:
                # 기둥은 바운딩 박스가 주된 정보임
                continue

            try:
                # 픽셀 좌표 → CAD 실제 mm 물리 좌표
                cad_box = self.transformer.transform_bbox(col.bbox.as_list())
                
                # COLUMN_BLOCK 원본 기준 크기: 400 x 400 mm
                block_w = 400.0
                block_h = 400.0
                
                # 기둥의 실제 치수에 맞춰 X, Y 축척 팩터 계산
                sx = cad_box.width / block_w
                sy = cad_box.height / block_h

                # ezdxf의 insert_point: 블록 기준점 (0,0)에 해당하는 CAD 좌표
                # 블록이 (0,0) ~ (400, 400)에 기하를 갖기 때문에 min_x, min_y가 타겟 위치임
                msp.add_blockref(
                    name="COLUMN_BLOCK",
                    insert=(cad_box.min_x, cad_box.min_y),
                    dxfattribs={
                        "layer": "COL",
                        "xscale": sx,
                        "yscale": sy,
                    }
                )
            except Exception as e:
                logger.warning("기둥 블록 삽입 실패 (ID: %s): %s", col.id, e)
                # 실패 시 대체용 솔리드 직사각형 드로잉
                try:
                    cad_box = self.transformer.transform_bbox(col.bbox.as_list())
                    pts = [
                        (cad_box.min_x, cad_box.min_y),
                        (cad_box.max_x, cad_box.min_y),
                        (cad_box.max_x, cad_box.max_y),
                        (cad_box.min_x, cad_box.max_y)
                    ]
                    msp.add_lwpolyline(pts, dxfattribs={"layer": "COL"}, close=True)
                except Exception:
                    pass

    def _render_doors(self, msp: Any) -> None:
        """문 엔티티를 DOOR_BLOCK 참조 인스턴스로 삽입."""
        doors = self.graph.by_type("door")
        logger.info("문 렌더링 중... 개수: %d", len(doors))

        for door in doors:
            if not door.bbox:
                continue

            try:
                cad_box = self.transformer.transform_bbox(door.bbox.as_list())
                
                # DOOR_BLOCK 기본 치수: 900mm (힌지 원점)
                door_width = max(cad_box.width, cad_box.height)
                scale_val = door_width / 900.0

                # 회전각 및 삽입기준점 결정
                # 종횡비에 따라 문짝 개폐 방향 예측
                if cad_box.height > cad_box.width:
                    # 세로형 문: 90도 회전
                    insert_pt = (cad_box.min_x, cad_box.min_y)
                    rotation = 90.0
                else:
                    # 가로형 문: 0도 회전
                    insert_pt = (cad_box.min_x, cad_box.min_y)
                    rotation = 0.0

                # VLM 또는 어댑터가 부여한 각도가 있다면 오버라이드
                if door.angle != 0.0:
                    rotation = door.angle

                msp.add_blockref(
                    name="DOOR_BLOCK",
                    insert=insert_pt,
                    dxfattribs={
                        "layer": "DOOR",
                        "xscale": scale_val,
                        "yscale": scale_val,
                        "rotation": rotation
                    }
                )
            except Exception as e:
                logger.warning("문 블록 삽입 오류: %s. 단순 아크/라인 폴백.", e)

    def _render_windows(self, msp: Any) -> None:
        """창문 엔티티를 WINDOW_BLOCK 참조 인스턴스로 삽입."""
        windows = self.graph.by_type("window")
        logger.info("창문 렌더링 중... 개수: %d", len(windows))

        for win in windows:
            if not win.bbox:
                continue

            try:
                cad_box = self.transformer.transform_bbox(win.bbox.as_list())
                
                # WINDOW_BLOCK 기본 치수: 1200mm (가로) x 200mm (두께)
                # 가로 형태인지 세로 형태인지 판별
                if cad_box.width >= cad_box.height:
                    # 가로형 창문
                    sx = cad_box.width / 1200.0
                    sy = cad_box.height / 200.0
                    insert_pt = (cad_box.min_x, cad_box.min_y)
                    rotation = 0.0
                else:
                    # 세로형 창문
                    # 블록이 회전하여 Y축을 따라 연장되므로, 
                    # 블록의 X축 스케일링이 실제 CAD의 세로(Y) 높이에 해당하고
                    # 블록의 Y축 스케일링이 실제 CAD의 가로(X) 두께에 해당
                    sx = cad_box.height / 1200.0
                    sy = cad_box.width / 200.0
                    # 회전축 및 스케일 방향 상, (max_x, min_y)에 삽입 후 90도 회전해야
                    # 본래의 [min_x, max_x] X축 영역에 기하 구조가 유지됨
                    insert_pt = (cad_box.max_x, cad_box.min_y)
                    rotation = 90.0

                if win.angle != 0.0:
                    rotation = win.angle

                msp.add_blockref(
                    name="WINDOW_BLOCK",
                    insert=insert_pt,
                    dxfattribs={
                        "layer": "WIN",
                        "xscale": sx,
                        "yscale": sy,
                        "rotation": rotation
                    }
                )
            except Exception as e:
                logger.warning("창문 블록 삽입 오류: %s. 사각형으로 대체합니다.", e)
                try:
                    cad_box = self.transformer.transform_bbox(win.bbox.as_list())
                    pts = [
                        (cad_box.min_x, cad_box.min_y),
                        (cad_box.max_x, cad_box.min_y),
                        (cad_box.max_x, cad_box.max_y),
                        (cad_box.min_x, cad_box.max_y)
                    ]
                    msp.add_lwpolyline(pts, dxfattribs={"layer": "WIN"}, close=True)
                except Exception:
                    pass

    def _render_text_and_dimensions(self, msp: Any) -> None:
        """텍스트 및 치수선 엔티티 렌더링."""
        texts = self.graph.by_type("text")
        dimensions = self.graph.by_type("dimension")

        # 1. 텍스트 처리
        if texts:
            logger.info("문자(TEXT) 렌더링 중... 개수: %d", len(texts))
            text_entities_list = []
            for t in texts:
                # bounding box의 중심점을 텍스트 삽입점으로 사용
                if t.bbox:
                    cx, cy = t.bbox.center
                elif t.points and len(t.points[0]) >= 2:
                    cx, cy = t.points[0][0], t.points[0][1]
                else:
                    cx, cy = 0.0, 0.0

                text_entities_list.append({
                    "text": t.text,
                    "x": cx,
                    "y": cy,
                    "height": t.text_height or 250.0,
                    "rotation": t.angle or 0.0,
                    "confidence": t.confidence,
                    "entity_id": t.id
                })
            
            try:
                add_text_entities(msp, text_entities_list, self.transformer)
            except Exception as e:
                logger.error("문자 렌더링 중 예외 발생: %s", e)

        # 2. 치수선 처리
        if dimensions:
            logger.info("치수선(DIMENSION) 렌더링 중... 개수: %d", len(dimensions))
            dim_entities_list = []
            for d in dimensions:
                # 시작점, 끝점 좌표 확인
                if d.points and len(d.points) > 0 and len(d.points[0]) >= 4:
                    p1 = [d.points[0][0], d.points[0][1]]
                    p2 = [d.points[0][2], d.points[0][3]]
                elif d.bbox:
                    p1 = [d.bbox.x1, d.bbox.y1]
                    p2 = [d.bbox.x2, d.bbox.y2]
                else:
                    continue

                dim_entities_list.append({
                    "p1": p1,
                    "p2": p2,
                    "text": d.text,
                    "offset": d.metadata.get("offset", 300.0),
                    "entity_id": d.id
                })
            
            try:
                add_dimensions(msp, dim_entities_list, self.transformer)
            except Exception as e:
                logger.error("치수선 렌더링 중 예외 발생: %s", e)

    def _render_other_entities(self, msp: Any) -> None:
        """기타 건축 요소 (stair, furniture, room, unknown 등) 처리."""
        other_types = ["stair", "furniture", "room", "unknown"]
        for etype in other_types:
            entities = self.graph.by_type(etype)
            if not entities:
                continue

            logger.info("기타 요소 '%s' 렌더링 중... 개수: %d", etype, len(entities))
            for entity in entities:
                layer = entity.resolve_layer()

                # 1. 폴리곤 형태 우선
                if entity.polygon and entity.polygon.points:
                    cad_pts = self.transformer.transform_points(
                        [tuple(p) for p in entity.polygon.points],
                        to_cad=True
                    )
                    msp.add_lwpolyline(cad_pts, dxfattribs={"layer": layer}, close=entity.polygon.closed)

                # 2. 선분 형태
                elif entity.points:
                    for seg in entity.points:
                        if len(seg) >= 4:
                            p1 = self.transformer.to_cad(seg[0], seg[1])
                            p2 = self.transformer.to_cad(seg[2], seg[3])
                            msp.add_line(p1, p2, dxfattribs={"layer": layer})

                # 3. 바운딩 박스 형태
                elif entity.bbox:
                    cad_box = self.transformer.transform_bbox(entity.bbox.as_list())
                    pts = [
                        (cad_box.min_x, cad_box.min_y),
                        (cad_box.max_x, cad_box.min_y),
                        (cad_box.max_x, cad_box.max_y),
                        (cad_box.min_x, cad_box.max_y)
                    ]
                    msp.add_lwpolyline(pts, dxfattribs={"layer": layer}, close=True)
