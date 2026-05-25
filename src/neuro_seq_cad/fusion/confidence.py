"""
confidence.py — 다중 소스 증거 데이터의 신뢰도(Confidence) 계산 및 융합

다양한 탐지 소스(Raster2Seq, PlanParser, MLSD 등)가 제공한 정보의 신뢰도를 결합합니다.
각 탐지기 모델의 고유 신뢰도 가중치(Source Reliability Weight)를 적용하고,
동일 요소에 대해 여러 모델이 중복으로 증거를 제시했을 때 신뢰도가 상승하는
다중 센서 융합(Probabilistic Sensor Fusion) 알고리즘을 사용합니다.
"""

from __future__ import annotations

import logging
from typing import Dict

from neuro_seq_cad.fusion.evidence_graph import EvidenceEntity

logger = logging.getLogger(__name__)

# 각 검출 소스별 신뢰도 가중치 (Source Reliability Weights)
# AI 모델의 정확도, 기하학적 정밀도, 오탐율을 기준으로 가중치를 책정합니다.
SOURCE_WEIGHTS: Dict[str, float] = {
    "raster2seq": 0.90,     # 전체 벽체 레이아웃 및 방 폐쇄 루프 구성력이 가장 뛰어남
    "opencv_lsd": 0.85,     # 기하학적 정밀도가 극도로 높으나 기하학적 시맨틱 없음
    "mlsd": 0.80,           # 딥러닝 기반 선분 검출로 노이즈에 강함
    "ocr": 0.80,            # 텍스트 오인식 가능성이 존재하지만 기재된 치수의 신뢰도가 큼
    "planparser": 0.75,     # 문/창문 탐지 성능이 양호하지만 YOLO 기반 바운딩박스 특성상 정밀 오차가 있음
    "vlm": 0.70,            # 도면 전반의 에러를 짚어내는 정성적 신뢰도는 높으나 직접 정밀 좌표 제시는 불리함
    "unknown": 0.50
}


def get_source_weight(source_name: str) -> float:
    """소스로부터 가중치를 조회합니다 (대소문자 구분 없음, 기본값 제공)."""
    name_lower = source_name.lower().strip()
    return SOURCE_WEIGHTS.get(name_lower, SOURCE_WEIGHTS["unknown"])


def calculate_entity_confidence(entity: EvidenceEntity) -> float:
    """단일 엔티티에 대한 다중 소스 융합 신뢰도를 계산합니다.

    융합 알고리즘: 확률적 합집합 (Probabilistic Union / Noisy-OR Model)
      독립된 다중 소스 S_1, S_2, ... S_k의 검출 확률을 결합할 때,
      전체 신뢰도 C_fused = 1 - Π (1 - C_i * w_i)
      여기서 C_i는 개별 소스의 검출 신뢰도, w_i는 해당 소스 채널의 신뢰 가중치입니다.
      
      이 방식은 단일 우수 소스의 지배력을 존중하면서도, 
      여러 소스가 동시에 일치하는 의견을 낼 경우 신뢰도가 점진적으로 1.0에 수렴하는 특성을 가집니다.

    Args:
        entity: 신뢰도를 계산할 EvidenceEntity 객체

    Returns:
        최종 융합 신뢰도 (0.0 ~ 1.0)
    """
    if not entity.sources:
        # 소스가 아예 등록되어 있지 않다면 엔티티 자체의 기존 신뢰도를 유지하거나 기본값 부여
        return entity.confidence if entity.confidence > 0 else 0.5
        
    # 각 소스의 가중 신뢰도를 수집합니다.
    # 1 - (C_i * w_i) 값을 누적 곱합니다.
    complement_product = 1.0
    
    for src in entity.sources:
        weight = get_source_weight(src.name)
        # 소스 자체 신뢰도와 소스 가중치 결합
        src_confidence = src.confidence
        weighted_conf = src_confidence * weight
        
        # 확률 보수 누적 곱
        complement_product *= (1.0 - weighted_conf)
        
    # 확률 합집합 계산
    fused_confidence = 1.0 - complement_product
    
    # 여러 소스가 매칭된 경우 추가적인 다중 합의 부스트 (Multi-Source Agreement Boost)
    # 단, 부스트 결과도 1.0을 넘을 수 없음
    if len(entity.sources) > 1:
        # 소스가 많을수록 +0.05 가중 (최대 0.1)
        boost = min(0.1, (len(entity.sources) - 1) * 0.05)
        fused_confidence += boost
        
    fused_confidence = min(1.0, max(0.0, fused_confidence))
    
    # 엔티티 필드 갱신
    entity.confidence = fused_confidence
    
    # 신뢰도가 너무 낮으면 검수 필요(needs_review) 플래그 설정
    if fused_confidence < 0.5:
        entity.needs_review = True
        
    return fused_confidence


def fuse_graph_confidence(entities: list[EvidenceEntity]) -> list[EvidenceEntity]:
    """증거 그래프 내 모든 엔티티의 신뢰도를 일괄적으로 융합 및 계산합니다."""
    for entity in entities:
        calculate_entity_confidence(entity)
    return entities
