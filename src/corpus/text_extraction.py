from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any, Iterable

_MTEXT_COMMAND = re.compile(
    r"""\\(?:[ACFHQSTWacfhqstw][^;{}]*;|[LlOoPpKkXx~{}\\])"""
)
_FIELD_WRAPPER = re.compile(r"%<(?P<field>.*?)>%")
_WHITESPACE = re.compile(r"\s+")
_DXF_ESCAPED_UNICODE = re.compile(r"\\U\+(?P<hex>[0-9A-Fa-f]{4,8})")


def _decode_dxf_unicode(value: str) -> str:
    def repl(match: re.Match[str]) -> str:
        try:
            return chr(int(match.group("hex"), 16))
        except (ValueError, OverflowError):
            return match.group(0)

    return _DXF_ESCAPED_UNICODE.sub(repl, value)


def plain_cad_text(value: object) -> str:
    """Return searchable visible text while preserving engineering symbols."""

    if value is None:
        return ""
    text = _decode_dxf_unicode(str(value).replace("\r\n", "\n").replace("\r", "\n"))
    text = text.replace(r"\P", "\n").replace(r"\~", " ")
    text = text.replace("%%d", "°").replace("%%p", "±").replace("%%c", "⌀")
    text = _MTEXT_COMMAND.sub("", text)
    text = text.replace("{", "").replace("}", "")

    def field_repl(match: re.Match[str]) -> str:
        field = _WHITESPACE.sub(" ", match.group("field")).strip()
        return f"[FIELD {field}]" if field else ""

    text = _FIELD_WRAPPER.sub(field_repl, text)
    lines = [_WHITESPACE.sub(" ", line).strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line).strip()


def normalize_search_text(value: object) -> str:
    text = plain_cad_text(value)
    text = unicodedata.normalize("NFC", text)
    text = "".join(
        ch
        for ch in text
        if ch == "\n" or ch == "\t" or unicodedata.category(ch)[0] != "C"
    )
    return _WHITESPACE.sub(" ", text).strip().casefold()


def _point(value: Any) -> list[float] | None:
    if value is None:
        return None
    try:
        items = list(value)
    except Exception:
        return None
    out: list[float] = []
    for item in items[:3]:
        try:
            out.append(float(item))
        except (TypeError, ValueError):
            return None
    while len(out) < 3:
        out.append(0.0)
    return out


def _candidate(
    *,
    raw_text: object,
    entity: dict[str, Any],
    source_kind: str,
    sub_handle: object = None,
    tag: object = None,
    row: int | None = None,
    column: int | None = None,
    confidence: float = 1.0,
) -> dict[str, Any] | None:
    raw = "" if raw_text is None else str(raw_text)
    plain = plain_cad_text(raw)
    normalized = normalize_search_text(raw)
    if not plain and not normalized:
        return None

    block_path = entity.get("block_path") or []
    if isinstance(block_path, str):
        block_path = [block_path]
    position = (
        entity.get("text_position")
        or entity.get("insert")
        or entity.get("position")
        or entity.get("point")
    )
    identity = {
        "handle": entity.get("handle"),
        "sub_handle": sub_handle,
        "layout": entity.get("layout"),
        "block_path": block_path,
        "source_kind": source_kind,
        "tag": tag,
        "row": row,
        "column": column,
        "plain": plain,
    }
    occurrence_id = hashlib.sha256(
        json.dumps(identity, ensure_ascii=False, sort_keys=True, default=str).encode(
            "utf-8"
        )
    ).hexdigest()

    return {
        "occurrence_id": occurrence_id,
        "handle": entity.get("handle"),
        "sub_handle": sub_handle,
        "layer": entity.get("layer") or entity.get("Layer"),
        "entity_type": entity.get("entity_type")
        or entity.get("type")
        or entity.get("object_name"),
        "layout": entity.get("layout") or "Model",
        "space": entity.get("space") or "model",
        "block_path": list(block_path),
        "source_kind": source_kind,
        "tag": tag,
        "row": row,
        "column": column,
        "raw_text": raw,
        "plain_text": plain,
        "normalized_text": normalized,
        "text": plain,
        "insert": _point(position),
        "bbox": entity.get("bbox"),
        "confidence": float(confidence),
        "xref_path": entity.get("xref_path"),
        "payload": {
            "object_name": entity.get("object_name"),
            "owner_handle": entity.get("owner_handle"),
            "field_code": entity.get("field_code"),
        },
    }


def text_rows_from_entities_v2(
    entities: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Expand every searchable text occurrence from canonical entity records."""

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(row: dict[str, Any] | None) -> None:
        if row is None:
            return
        key = str(row["occurrence_id"])
        if key in seen:
            return
        seen.add(key)
        rows.append(row)

    for entity in entities:
        kind = str(
            entity.get("entity_type")
            or entity.get("type")
            or entity.get("object_name")
            or ""
        ).upper()

        for item in entity.get("text_items") or []:
            if not isinstance(item, dict):
                continue
            add(
                _candidate(
                    raw_text=item.get("raw_text", item.get("text")),
                    entity={
                        **entity,
                        **{
                            k: v
                            for k, v in item.items()
                            if k
                            in {
                                "layout",
                                "space",
                                "block_path",
                                "insert",
                                "position",
                                "bbox",
                                "xref_path",
                                "field_code",
                            }
                        },
                    },
                    source_kind=str(item.get("source_kind") or "text_item"),
                    sub_handle=item.get("handle"),
                    tag=item.get("tag"),
                    row=item.get("row"),
                    column=item.get("column"),
                    confidence=float(item.get("confidence", 1.0)),
                )
            )

        direct = entity.get("text")
        if direct is not None:
            add(_candidate(raw_text=direct, entity=entity, source_kind="entity_text"))

        if "DIMENSION" in kind:
            override = entity.get("text_override")
            display = entity.get("display_text") or entity.get("text_string")
            measurement = entity.get("measurement")
            if override not in (None, "", "<>"):
                add(
                    _candidate(
                        raw_text=override,
                        entity=entity,
                        source_kind="dimension_override",
                    )
                )
            if display:
                add(
                    _candidate(
                        raw_text=display,
                        entity=entity,
                        source_kind="dimension_display",
                    )
                )
            elif measurement is not None:
                add(
                    _candidate(
                        raw_text=str(measurement),
                        entity=entity,
                        source_kind="dimension_measurement",
                    )
                )

        for attr in entity.get("attributes") or []:
            if not isinstance(attr, dict):
                continue
            add(
                _candidate(
                    raw_text=attr.get("text") or attr.get("TextString"),
                    entity={
                        **entity,
                        "insert": attr.get("insert") or entity.get("insert"),
                    },
                    source_kind="block_attribute",
                    sub_handle=attr.get("handle"),
                    tag=attr.get("tag") or attr.get("TagString"),
                )
            )

        for attr in entity.get("constant_attributes") or []:
            if not isinstance(attr, dict):
                continue
            add(
                _candidate(
                    raw_text=attr.get("text") or attr.get("TextString"),
                    entity={
                        **entity,
                        "insert": attr.get("insert") or entity.get("insert"),
                    },
                    source_kind="block_constant_attribute",
                    sub_handle=attr.get("handle"),
                    tag=attr.get("tag") or attr.get("TagString"),
                )
            )

        for cell in entity.get("table_cells") or []:
            if not isinstance(cell, dict):
                continue
            add(
                _candidate(
                    raw_text=cell.get("text") or cell.get("value"),
                    entity=entity,
                    source_kind="table_cell",
                    row=cell.get("row"),
                    column=cell.get("column"),
                )
            )

        for leader_text in entity.get("leader_texts") or []:
            if isinstance(leader_text, dict):
                value = leader_text.get("text")
                sub_handle = leader_text.get("handle")
            else:
                value = leader_text
                sub_handle = None
            add(
                _candidate(
                    raw_text=value,
                    entity=entity,
                    source_kind="leader_text",
                    sub_handle=sub_handle,
                )
            )

    return rows
