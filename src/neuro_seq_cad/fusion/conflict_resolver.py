"""
conflict_resolver.py — 다중 소스 증거 데이터 간의 충돌 해결 및 통합 (Conflict Resolution)

서로 다른 탐지 모델(Raster2Seq, PlanParser, MLSD 등)에서 도출된 객체들이
공간상에서 중복되거나 충돌할 때(예: 동일 위치에 탐지된 중복 문/창문, 겹치는 방 구획 등)
공간 IoU(Intersection over Union) 및 소스 신뢰도를 평가하여 충돌을 자동으로 해결합니다.
"""

from __future__ import annotations

import logging
from typing import List, Dict, Any, Tuple

from pydantic import BaseModel, Field

from neuro_seq_cad.fusion.evidence_graph import EvidenceGraph, EvidenceEntity
from neuro_seq_cad.fusion.confidence import calculate_entity_confidence
from neuro_seq_cad.geometry.primitives import BBox2D

logger = logging.getLogger(__name__)


class ConflictRecord(BaseModel):
    """충돌 해결 기록 모델."""

    id: str
    entity_type: str
    involved_ids: List[str]
    resolution_type: str  # "merged" | "kept_higher_confidence" | "resolved"
    details: str


def get_entity_bbox(entity: EvidenceEntity) -> BBox2D | None:
    """엔티티의 기하 형태(bbox, polygon, points)로부터 바운딩 박스를 계산합니다."""
    if entity.bbox is not None:
        return BBox2D(x1=entity.bbox.x1, y1=entity.bbox.y1, x2=entity.bbox.x2, y2=entity.bbox.y2)
        
    if entity.polygon is not None and entity.polygon.points:
        xs = [p[0] for p in entity.polygon.points]
        ys = [p[1] for p in entity.polygon.points]
        return BBox2D(x1=min(xs), y1=min(ys), x2=max(xs), y2=max(ys))
        
    if entity.points:
        xs = []
        ys = []
        for segment in entity.points:
            if len(segment) >= 4:
                xs.extend([segment[0], segment[2]])
                ys.extend([segment[1], segment[3]])
        if xs and ys:
            return BBox2D(x1=min(xs), y1=min(ys), x2=max(xs), y2=max(ys))
            
    return None


def merge_entities(primary: EvidenceEntity, secondary: EvidenceEntity) -> EvidenceEntity:
    """두 엔티티의 정보(소스, 메타데이터 등)를 하나로 병합합니다. 기하 좌표는 더 신뢰도가 높은 primary 것을 유지합니다."""
    # 소스 병합 (중복 방지)
    existing_source_names = {s.name.lower() for s in primary.sources}
    for src in secondary.sources:
        if src.name.lower() not in existing_source_names:
            primary.sources.append(src)
            existing_source_names.add(src.name.lower())
            
    # 관계 병합
    existing_relation_targets = {r.target_id for r in primary.relations}
    for rel in secondary.relations:
        if rel.target_id not in existing_relation_targets:
            primary.relations.append(rel)
            existing_relation_targets.add(rel.target_id)
            
    # 텍스트 병합 (비어있으면 채움)
    if not primary.text and secondary.text:
        primary.text = secondary.text
        
    # 메타데이터 병합
    primary.metadata.update(secondary.metadata)
    primary.metadata["merged_from_id"] = secondary.id
    
    # 융합 신뢰도 재계산
    calculate_entity_confidence(primary)
    
    return primary


def resolve_conflicts(graph: EvidenceGraph, iou_threshold: float = 0.45) -> EvidenceGraph:
    """증거 그래프 내에서 충돌하는 엔티티들(중복 문, 창문, 가구 등)을 찾아 병합하거나 필터링합니다.

    알고리즘:
    1. 개구부(door, window) 및 심볼(furniture, column)에 대하여 공간 overlap 분석 수행.
    2. 높은 IoU를 가지는 한 쌍의 엔티티는 동일한 개체를 나타내는 것으로 판단.
    3. 더 높은 신뢰도나 주요 소스를 가진 객체를 Primary로 지정하고, Secondary 객체의 증거(source)를 Primary로 누적 후 Secondary 삭제.
    4. 겹치는 방 구획(room)은 면적이 더 크거나 신뢰도가 높은 구획으로 충돌 해결.

    Args:
        graph: 원본 증거 그래프 (EvidenceGraph)
        iou_threshold: 충돌로 판단할 바운딩 박스 최소 IoU 임계값

    Returns:
        충돌이 해결된 새로운 증거 그래프
    """
    logger.info("증거 그래프 충돌 해결 시작 (입력 엔티티 수: %d)", len(graph.entities))
    
    # 유형별로 엔티티 그룹 분할
    symbols: List[EvidenceEntity] = []
    rooms: List[EvidenceEntity] = []
    others: List[EvidenceEntity] = []
    
    for entity in graph.entities:
        if entity.entity_type in ("door", "window", "column", "furniture", "stair"):
            symbols.append(entity)
        elif entity.entity_type == "room":
            rooms.append(entity)
        else:
            others.append(entity)
            
    resolved_symbols: List[EvidenceEntity] = []
    eliminated_ids = set()
    records: List[ConflictRecord] = []
    
    # ─────────────────────────────────────────────────────────────
    # 1. 심볼 및 개구부 충돌 해결 (문, 창문 등)
    # ─────────────────────────────────────────────────────────────
    # 신뢰도 높은 순으로 정렬하여 신뢰도가 높은 객체가 우선적으로 Primary가 되도록 유도
    symbols.sort(key=lambda x: x.confidence, reverse=True)
    
    for i in range(len(symbols)):
        ent_i = symbols[i]
        if ent_i.id in eliminated_ids:
            continue
            
        bbox_i = get_entity_bbox(ent_i)
        if bbox_i is None:
            resolved_symbols.append(ent_i)
            continue
            
        for j in range(i + 1, len(symbols)):
            ent_j = symbols[j]
            if ent_j.id in eliminated_ids:
                continue
                
            # 타입이 다른 개구부는 겹치더라도 병합하지 않음 (예: 문과 창문은 분리)
            if ent_i.entity_type != ent_j.entity_type:
                continue
                
            bbox_j = get_entity_bbox(ent_j)
            if bbox_j is None:
                continue
                
            # 바운딩 박스 간의 IoU 계산
            iou_val = bbox_i.iou(bbox_j)
            if iou_val >= iou_threshold:
                # 충돌 감지! ent_i(신뢰도가 더 높음)를 Primary로 두고 ent_j를 병합 소스로 흡수
                logger.info(
                    "심볼 충돌 감지 및 병합: [%s:%s](conf=%.2f) <-> [%s:%s](conf=%.2f) (IoU=%.2f)",
                    ent_i.entity_type, ent_i.id, ent_i.confidence,
                    ent_j.entity_type, ent_j.id, ent_j.confidence, iou_val
                )
                
                merge_entities(ent_i, ent_j)
                eliminated_ids.add(ent_j.id)
                
                records.append(ConflictRecord(
                    id=f"REC-{ent_i.id[:4]}-{ent_j.id[:4]}",
                    entity_type=ent_i.entity_type,
                    involved_ids=[ent_i.id, ent_j.id],
                    resolution_type="merged",
                    details=f"Overlapping {ent_i.entity_type}s resolved by merging sources. IoU={iou_val:.2f}"
                ))
                
        resolved_symbols.append(ent_i)
        
    # ─────────────────────────────────────────────────────────────
    # 2. 방(Room) 구획 충돌 해결
    # ─────────────────────────────────────────────────────────────
    resolved_rooms: List[EvidenceEntity] = []
    rooms.sort(key=lambda x: x.confidence, reverse=True)
    
    for i in range(len(rooms)):
        room_i = rooms[i]
        if room_i.id in eliminated_ids:
            continue
            
        bbox_i = get_entity_bbox(room_i)
        if bbox_i is None:
            resolved_rooms.append(room_i)
            continue
            
        for j in range(i + 1, len(rooms)):
            room_j = rooms[j]
            if room_j.id in eliminated_ids:
                continue
                
            bbox_j = get_entity_bbox(room_j)
            if bbox_j is None:
                continue
                
            # 두 방 바운딩 박스가 극단적으로 겹칠 경우 (IoU > 0.7) 동일 구역에 대한 중복 감지로 간주
            iou_val = bbox_i.iou(bbox_j)
            if iou_val >= 0.70:
                logger.info(
                    "방 구획 중복 감지 및 해결: [%s](conf=%.2f) <-> [%s](conf=%.2f) (IoU=%.2f)",
                    room_i.text or "Unknown", room_i.confidence,
                    room_j.text or "Unknown", room_j.confidence, iou_val
                )
                
                # 라벨 정보가 비어있다면 합치고, 더 신뢰도 높은 room_i를 유지
                merge_entities(room_i, room_j)
                eliminated_ids.add(room_j.id)
                
                records.append(ConflictRecord(
                    id=f"REC-{room_i.id[:4]}-{room_j.id[:4]}",
                    entity_type="room",
                    involved_ids=[room_i.id, room_j.id],
                    resolution_type="merged",
                    details=f"Duplicate room zones merged. IoU={iou_val:.2f}"
                ))
                
        resolved_rooms.append(room_i)
        
    # 최종 리스트 합성
    all_resolved_entities = resolved_symbols + resolved_rooms + others
    
    # 충돌 해결 기록을 그래프 메타데이터에 주입
    graph.entities = all_resolved_entities
    if "conflict_records" not in graph.metadata:
        graph.metadata["conflict_records"] = []
    
    for r in records:
        graph.metadata["conflict_records"].append(r.model_dump())
        
    logger.info(
        "증거 그래프 충돌 해결 완료: 최종 엔티티 수: %d (제거된 중복 엔티티: %d)",
        len(graph.entities), len(eliminated_ids)
    )
    
    return graph
