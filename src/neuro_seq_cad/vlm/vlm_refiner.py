"""
vlm_refiner.py — VLM 피드백 기반 증거 그래프 보정 및 가시화 반영 엔진

VLM(Vision-Language Model)이 반환한 구조화된 보정 지침(VLMFloorplanRefinementOutput)을
입력받아, 증거 그래프(EvidenceGraph) 내에 기 존재하던 객체들을 
기하학적으로 평행이동(Y축/X축 shift) 시키거나, 방 이름을 보정(Label Rename)하고, 
잘못 감지된 이중 라인을 삭제하거나, 누락된 핵심 구성 요소를 동적으로 추가합니다.
"""

from __future__ import annotations

import logging
from typing import List

from neuro_seq_cad.fusion.evidence_graph import EvidenceGraph, EvidenceEntity, BBox, Polygon2D
from neuro_seq_cad.vlm.schemas import VLMFloorplanRefinementOutput, CorrectionInstruction

logger = logging.getLogger(__name__)


class VLMFloorplanRefiner:
    """VLM 피드백 데이터를 실제 증거 그래프 기하 좌표 및 속성에 주입하는 리파이너."""

    def __init__(self) -> None:
        pass

    def refine(
        self,
        graph: EvidenceGraph,
        feedback: VLMFloorplanRefinementOutput
    ) -> EvidenceGraph:
        """VLM의 보정 피드백 지침에 맞춰 증거 그래프를 실제 기하 구조적으로 변환합니다."""
        logger.info("VLM 피드백 기반 도면 보정 주입을 시작합니다. (지침 수: %d)", len(feedback.instructions))
        
        # 1. Mock 모드 ID 매핑 사전 조율
        # API가 구동되지 않는 가상 검증 모드(Mock Mode)일 때, 
        # mock 지침에 기술된 'find_bath_id' 및 'find_door_id'를 실제 그래프 엔티티 ID로 미리 전환해 줍니다.
        self._pre_resolve_mock_ids(graph, feedback.instructions)
        
        entities_to_keep: List[EvidenceEntity] = []
        entities_to_add: List[EvidenceEntity] = []
        deleted_ids = set()
        
        # 2. 보정 지침 적용 루프
        for inst in feedback.instructions:
            if inst.action == "none":
                continue
                
            if inst.action == "delete":
                deleted_ids.add(inst.target_entity_id)
                logger.info("엔티티 삭제 예약 (ID: %s, 사유: %s)", inst.target_entity_id, inst.reason)
                continue
                
            if inst.action == "add":
                # 신규 요소 추가
                new_ent = self._create_new_entity(inst)
                if new_ent:
                    entities_to_add.append(new_ent)
                continue
                
            if inst.action == "modify":
                # 대상 요소 탐색
                target = graph.by_id(inst.target_entity_id)
                if not target:
                    logger.debug("보정 타겟 엔티티를 찾을 수 없습니다: %s (건너뜀)", inst.target_entity_id)
                    continue
                    
                logger.info("엔티티 속성/좌표 보정 수행 (ID: %s, 유형: %s, 사유: %s)", target.id, target.entity_type, inst.reason)
                
                # 가. 텍스트 라벨 또는 방 이름 수정
                if "new_label" in inst.parameters:
                    new_lbl = inst.parameters["new_label"]
                    logger.info("  - 텍스트 변경: '%s' -> '%s'", target.text, new_lbl)
                    target.text = new_lbl
                    if target.metadata:
                        target.metadata["label"] = new_lbl
                        
                # 나. 기하학적 평행 이동 (Shift)
                if "shift_px" in inst.parameters:
                    dx, dy = inst.parameters["shift_px"]
                    self._shift_entity_geometry(target, dx, dy)
                    
                # 다. 전체 좌표 업데이트 (직접 선분 지정)
                if "endpoints" in inst.parameters:
                    endpoints = inst.parameters["endpoints"]
                    logger.info("  - 선분 좌표 강제 업데이트: %s", endpoints)
                    target.points = endpoints
                    
                # VLM 보정 증거 소스 추가
                target.add_source(name="vlm", confidence=0.90, action="modify_by_vlm")
                
        # 3. 보정 반영 결과 합성
        # 삭제 대상 제외
        for ent in graph.entities:
            if ent.id not in deleted_ids:
                entities_to_keep.append(ent)
                
        # 추가 대상 합류
        entities_to_keep.extend(entities_to_add)
        graph.entities = entities_to_keep
        
        # 보정 기록 메타데이터 등록
        if "vlm_refinements_applied" not in graph.metadata:
            graph.metadata["vlm_refinements_applied"] = []
            
        for inst in feedback.instructions:
            graph.metadata["vlm_refinements_applied"].append({
                "target_id": inst.target_entity_id,
                "action": inst.action,
                "reason": inst.reason,
                "desc": inst.description
            })
            
        graph.pipeline.notes.append(
            f"VLM 보정 완료: {len(feedback.instructions)}개 보정 지침 주입 (최종 신뢰도: {feedback.quality_score:.2f})"
        )
        
        logger.info(
            "VLM 도면 보정 완료. 최종 엔티티 수: %d (추가: %d, 삭제: %d)",
            len(graph.entities), len(entities_to_add), len(deleted_ids)
        )
        
        return graph

    def _shift_entity_geometry(self, entity: EvidenceEntity, dx: float, dy: float) -> None:
        """엔티티의 기하 형태(bbox, polygon, points)에 평행 이동을 일괄 적용합니다."""
        logger.info("  - 기하 이동: dx=%.1f, dy=%.1f", dx, dy)
        
        # Bounding Box 이동
        if entity.bbox:
            entity.bbox.x1 += dx
            entity.bbox.x2 += dx
            entity.bbox.y1 += dy
            entity.bbox.y2 += dy
            
        # Polygon 이동
        if entity.polygon and entity.polygon.points:
            shifted_pts = []
            for pt in entity.polygon.points:
                shifted_pts.append([pt[0] + dx, pt[1] + dy])
            entity.polygon.points = shifted_pts
            
        # Line Segments 이동
        if entity.points:
            shifted_lines = []
            for line in entity.points:
                if len(line) >= 4:
                    shifted_lines.append([
                        line[0] + dx,
                        line[1] + dy,
                        line[2] + dx,
                        line[3] + dy
                    ])
                else:
                    shifted_lines.append(line)
            entity.points = shifted_lines

    def _create_new_entity(self, inst: CorrectionInstruction) -> EvidenceEntity | None:
        """VLM 지침에 기초하여 결손되어 있던 신규 증거 엔티티를 동적으로 생성합니다."""
        logger.info("VLM 지침에 따른 신규 객체 생성: type=%s, 요약=%s", inst.element_type, inst.description)
        
        try:
            # 기본 바운딩 박스 파라미터가 있는 경우
            bbox_coords = inst.parameters.get("bbox")
            bbox_ent = None
            if bbox_coords and len(bbox_coords) >= 4:
                bbox_ent = BBox(
                    x1=bbox_coords[0],
                    y1=bbox_coords[1],
                    x2=bbox_coords[2],
                    y2=bbox_coords[3]
                )
                
            pts = inst.parameters.get("endpoints", [])
            polygon_pts = inst.parameters.get("points", [])
            poly_ent = None
            if polygon_pts:
                # points 파라미터가 존재하면 Polygon으로 래핑
                poly_ent = Polygon2D(points=polygon_pts, closed=True)
                
            new_entity = EvidenceEntity(
                entity_type=inst.element_type,
                bbox=bbox_ent,
                polygon=poly_ent,
                points=pts,
                text=inst.parameters.get("new_label", inst.parameters.get("text", "")),
                confidence=0.85,
                needs_review=False
            )
            
            # VLM 감지 소스 정보 주입
            new_entity.add_source(
                name="vlm",
                confidence=0.85,
                reason="Added via VLM Visual Inspection",
                details=inst.description
            )
            return new_entity
            
        except Exception as e:
            logger.error("신규 VLM 엔티티 생성 실패: %s", e)
            return None

    def _pre_resolve_mock_ids(self, graph: EvidenceGraph, instructions: list[CorrectionInstruction]) -> None:
        """가상(Mock) 보정 시나리오일 때 가상 ID를 실제 생성된 Mock 엔티티 ID로 조인합니다."""
        bath_entity = None
        door_entity = None
        
        for ent in graph.entities:
            if ent.entity_type == "room" and ent.text.lower() == "bath":
                bath_entity = ent
            elif ent.entity_type == "door" and ent.sources and "mock" in ent.sources[0].name:
                door_entity = ent
                
        for inst in instructions:
            if inst.target_entity_id == "find_bath_id" and bath_entity:
                inst.target_entity_id = bath_entity.id
            elif inst.target_entity_id == "find_door_id" and door_entity:
                inst.target_entity_id = door_entity.id
