from __future__ import annotations

from neuro_seq_cad.vlm.retry_parser import parse_vlm_json_with_retry
from neuro_seq_cad.vlm.vlm_client import DummyVLMClient


def refine_with_vlm(evidence_payload: dict, client: DummyVLMClient | None = None) -> tuple[dict, list[str]]:
    """Run optional VLM review.

    VLM은 좌표를 새로 만들지 않고 topology 검수, 관계 판단, 누락 가능성
    제안만 수행한다. 기본 구현은 local dummy라서 외부 API가 필요 없다.
    """

    selected = client or DummyVLMClient()
    result, warnings = parse_vlm_json_with_retry([selected.refine(evidence_payload)])
    return result.model_dump(), warnings

