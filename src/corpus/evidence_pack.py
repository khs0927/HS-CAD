"""Build query evidence packages for review and downstream drafting planning."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .query_expander import expand_query
from .search_ranker import CorpusSearchRanker


@dataclass
class EvidencePack:
    query: str
    expanded_terms: list[str]
    hits: list[dict[str, Any]] = field(default_factory=list)
    grouped: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    confidence: float = 0.0
    warnings: list[str] = field(default_factory=list)


def _confidence_from_hits(hits: list[dict[str, Any]]) -> float:
    if not hits:
        return 0.0
    top = max(float(h.get("score", 0.0)) for h in hits)
    coverage = min(len(hits) / 10.0, 1.0)
    return round(min(0.95, 0.25 + min(top / 5.0, 0.5) + coverage * 0.2), 3)


def build_evidence_pack(kb_path: str | Path, query: str, out_dir: str | Path, limit: int = 30) -> EvidencePack:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    expanded = expand_query(query)
    ranker = CorpusSearchRanker(kb_path)
    hits = [
        {
            "table": hit.table,
            "rowid": hit.rowid,
            "file_id": hit.file_id,
            "title": hit.title,
            "text": hit.text,
            "score": round(hit.score, 4),
            "payload": hit.payload,
        }
        for hit in ranker.search(query, limit=limit)
    ]

    grouped: dict[str, list[dict[str, Any]]] = {}
    for hit in hits:
        grouped.setdefault(hit["table"], []).append(hit)

    pack = EvidencePack(
        query=query,
        expanded_terms=expanded.all_terms,
        hits=hits,
        grouped=grouped,
        confidence=_confidence_from_hits(hits),
    )
    if not hits:
        pack.warnings.append("No evidence found for the query.")

    (out / "evidence_pack.json").write_text(
        json.dumps(asdict(pack), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out / "evidence_pack.md").write_text(render_evidence_pack_markdown(pack), encoding="utf-8")
    return pack


def render_evidence_pack_markdown(pack: EvidencePack) -> str:
    lines: list[str] = []
    lines.append("# CAD Corpus Evidence Pack")
    lines.append("")
    lines.append(f"## Query")
    lines.append("")
    lines.append(pack.query)
    lines.append("")
    lines.append("## Expanded Terms")
    lines.append("")
    lines.append(", ".join(pack.expanded_terms) if pack.expanded_terms else "-")
    lines.append("")
    lines.append(f"## Confidence")
    lines.append("")
    lines.append(str(pack.confidence))
    lines.append("")
    lines.append("## Evidence by Table")
    lines.append("")
    for table, hits in pack.grouped.items():
        lines.append(f"### {table}")
        lines.append("")
        for idx, hit in enumerate(hits[:10], 1):
            lines.append(f"{idx}. **score={hit.get('score')}** file={hit.get('file_id') or '-'}")
            text = (hit.get("text") or "").replace("\n", " ")
            lines.append(f"   - {text[:500]}")
        lines.append("")
    if pack.warnings:
        lines.append("## Warnings")
        lines.append("")
        for warning in pack.warnings:
            lines.append(f"- {warning}")
    return "\n".join(lines).rstrip() + "\n"


def load_evidence_pack(path: str | Path) -> EvidencePack:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return EvidencePack(**data)
