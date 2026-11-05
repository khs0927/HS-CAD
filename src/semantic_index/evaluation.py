from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from statistics import fmean
from typing import Any

from src.semantic_index.service import SemanticIndexService, load_record


def evaluate_group_csv(
    service: SemanticIndexService,
    labels_csv: str | Path,
    *,
    top_k: int = 5,
) -> dict[str, Any]:
    """Evaluate retrieval using a CSV with columns: record,group.

    Each file ID may appear exactly once. Repeated rows or assigning the same
    file ID to multiple groups would weight the metrics incorrectly and are
    rejected. Singleton groups are skipped because they have no relevant peer.
    """

    source = Path(labels_csv)
    if not source.exists():
        raise FileNotFoundError(source)
    top_k = max(1, int(top_k))

    entries: list[dict[str, str | Path]] = []
    seen_file_ids: dict[str, tuple[str, int]] = {}
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        required = {"record", "group"}
        if not required.issubset(fields):
            missing = ", ".join(sorted(required.difference(fields)))
            raise ValueError(f"labels CSV missing columns: {missing}")
        for row_number, row in enumerate(reader, start=2):
            record_value = str(row.get("record") or "").strip()
            group = str(row.get("group") or "").strip()
            if not record_value or not group:
                raise ValueError(
                    f"labels CSV row {row_number} requires record and group"
                )
            record_path = Path(record_value)
            if not record_path.is_absolute():
                record_path = source.parent / record_path
            record = load_record(record_path)
            previous = seen_file_ids.get(record.file_id)
            if previous is not None:
                previous_group, previous_row = previous
                if previous_group != group:
                    raise ValueError(
                        f"file_id {record.file_id!r} is assigned to multiple groups "
                        f"at rows {previous_row} and {row_number}"
                    )
                raise ValueError(
                    f"duplicate file_id {record.file_id!r} at rows "
                    f"{previous_row} and {row_number}"
                )
            seen_file_ids[record.file_id] = (group, row_number)
            entries.append(
                {
                    "record_path": record_path,
                    "file_id": record.file_id,
                    "group": group,
                }
            )

    groups: dict[str, set[str]] = defaultdict(set)
    for entry in entries:
        groups[str(entry["group"])].add(str(entry["file_id"]))

    per_query: list[dict[str, Any]] = []
    for entry in entries:
        file_id = str(entry["file_id"])
        group = str(entry["group"])
        relevant = groups[group] - {file_id}
        if not relevant:
            continue
        hits = service.search_record(Path(entry["record_path"]), limit=top_k)
        returned = [hit.file_id for hit in hits]
        true_positive = len(relevant.intersection(returned))
        precision = true_positive / max(1, len(returned))
        recall = true_positive / len(relevant)
        per_query.append(
            {
                "file_id": file_id,
                "group": group,
                "relevant_count": len(relevant),
                "returned_count": len(returned),
                "true_positive": true_positive,
                f"precision_at_{top_k}": precision,
                f"recall_at_{top_k}": recall,
                f"hit_at_{top_k}": 1.0 if true_positive else 0.0,
                "returned_file_ids": returned,
            }
        )

    precision_key = f"precision_at_{top_k}"
    recall_key = f"recall_at_{top_k}"
    hit_key = f"hit_at_{top_k}"
    return {
        "labels_csv": str(source),
        "top_k": top_k,
        "labeled_records": len(entries),
        "evaluated_queries": len(per_query),
        precision_key: (
            fmean(item[precision_key] for item in per_query) if per_query else 0.0
        ),
        recall_key: (
            fmean(item[recall_key] for item in per_query) if per_query else 0.0
        ),
        hit_key: fmean(item[hit_key] for item in per_query) if per_query else 0.0,
        "per_query": per_query,
    }
