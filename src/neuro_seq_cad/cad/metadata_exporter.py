"""
cad.metadata_exporter – result.json 메타데이터 내보내기
=======================================================
EvidenceGraph 전체를 JSON 으로 직렬화하여
파이프라인 결과 파일 (result.json) 에 저장한다.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from neuro_seq_cad.fusion.evidence_graph import EvidenceGraph


def export_metadata(
    evidence_graph: EvidenceGraph,
    filepath: str | Path,
) -> None:
    """
    파이프라인 전체 결과를 result.json 으로 저장.

    Parameters
    ----------
    evidence_graph : EvidenceGraph
        융합 완료된 증거 그래프.
    filepath : str | Path
        출력 JSON 파일 경로.

    출력 JSON 구조
    ---------------
    {
      "version": "1.0",
      "pipeline": { ... },
      "summary": { "wall": 12, "door": 5, ... },
      "entities": [ ... ],
      "metadata": { ... },
      "exported_at": "..."
    }
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    # 엔티티 타입별 요약
    summary = evidence_graph.summary()

    # 파이프라인 메타데이터에 내보내기 시각 추가
    output: dict[str, Any] = {
        "version": evidence_graph.version,
        "pipeline": evidence_graph.pipeline.model_dump(),
        "summary": summary,
        "total_entities": len(evidence_graph.entities),
        "entities": [e.model_dump() for e in evidence_graph.entities],
        "metadata": evidence_graph.metadata,
        "exported_at": datetime.now(timezone.utc).isoformat(),
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)
