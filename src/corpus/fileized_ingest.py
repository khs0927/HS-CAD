from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .architectural_element_mapper import map_many_to_elements
from .detail_pattern_extractor import build_detail_patterns
from .dimension_extractor import extract_dimensions_from_texts
from .knowledge_store import KnowledgeStore
from .material_extractor import extract_materials_from_texts
from .situation_extractor import extract_situations_from_texts
from .specification_extractor import extract_specifications_from_texts


def load_fileized_record(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def collect_texts_from_fileized(record: dict[str, Any]) -> list[str]:
    """FileizedDrawingRecord에서 검색/학습에 사용할 텍스트를 최대한 모은다."""
    texts: list[str] = []

    def add(value: Any):
        if value is None:
            return
        if isinstance(value, str) and value.strip():
            texts.append(value.strip())

    for item in record.get("texts") or []:
        if isinstance(item, str):
            add(item)
        elif isinstance(item, dict):
            add(item.get("text") or item.get("value") or item.get("raw_text"))

    for item in record.get("dimensions") or []:
        if isinstance(item, str):
            add(item)
        elif isinstance(item, dict):
            add(item.get("text") or item.get("raw_text") or item.get("measurement"))

    for item in record.get("entities") or []:
        if isinstance(item, dict):
            add(item.get("text"))
            add(item.get("layer"))
            add(item.get("block_name"))

    for item in record.get("layers") or []:
        if isinstance(item, str):
            add(item)
        elif isinstance(item, dict):
            add(item.get("name") or item.get("layer"))

    for item in record.get("blocks") or []:
        if isinstance(item, str):
            add(item)
        elif isinstance(item, dict):
            add(item.get("name") or item.get("block_name"))

    metadata = record.get("metadata") or {}
    if isinstance(metadata, dict):
        for key in ("drawing_title", "title", "subject", "keywords", "file_name", "filename"):
            add(metadata.get(key))

    # 순서 보존 중복 제거
    seen = set()
    deduped = []
    for text in texts:
        if text not in seen:
            seen.add(text)
            deduped.append(text)
    return deduped


def ingest_fileized_record(record_path: str | Path, store: KnowledgeStore) -> dict[str, Any]:
    path = Path(record_path)
    record = load_fileized_record(path)
    file_id = str(record.get("file_id") or path.stem)
    record.setdefault("file_id", file_id)

    store.upsert_fileized_record(record, json_path=str(path))
    texts = collect_texts_from_fileized(record)
    store.add_texts(file_id, texts, source="fileized")

    full_text = "\n".join(texts)
    materials = extract_materials_from_texts([full_text])
    specifications = extract_specifications_from_texts([full_text])
    dimensions = extract_dimensions_from_texts([full_text])
    situations = extract_situations_from_texts([full_text])
    elements = map_many_to_elements(texts, source_kind="fileized")
    patterns = build_detail_patterns(
        file_id=file_id,
        situations=situations,
        elements=elements,
        materials=materials,
        dimensions=dimensions,
    )

    store.add_materials(file_id, materials)
    store.add_specifications(file_id, specifications)
    store.add_dimensions(file_id, dimensions)
    store.add_situations(file_id, situations)
    store.add_elements(file_id, elements)
    store.add_detail_patterns(file_id, patterns)

    return {
        "file_id": file_id,
        "texts": len(texts),
        "materials": len(materials),
        "specifications": len(specifications),
        "dimensions": len(dimensions),
        "situations": len(situations),
        "elements": len(elements),
        "patterns": len(patterns),
    }


def iter_fileized_jsons(fileized_root: str | Path) -> list[Path]:
    root = Path(fileized_root)
    if root.is_file() and root.suffix.lower() == ".json":
        return [root]

    candidates: list[Path] = []
    for sub in (root / "json", root):
        if sub.exists():
            candidates.extend(sorted(sub.glob("*.json")))
    # 중복 제거
    seen = set()
    result = []
    for p in candidates:
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            result.append(p)
    return result


def ingest_fileized_folder(fileized_root: str | Path, db_path: str | Path, limit: int | None = None) -> dict[str, Any]:
    store = KnowledgeStore(db_path)
    files = iter_fileized_jsons(fileized_root)
    if limit is not None:
        files = files[:limit]

    stats = {"total": len(files), "success": 0, "failed": 0, "items": []}
    for path in files:
        try:
            item = ingest_fileized_record(path, store)
            stats["success"] += 1
            stats["items"].append(item)
        except Exception as exc:  # noqa: BLE001
            stats["failed"] += 1
            stats["items"].append({"path": str(path), "error": str(exc)})
    stats["counts"] = store.table_counts()
    store.close()
    return stats
