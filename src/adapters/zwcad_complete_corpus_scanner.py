from __future__ import annotations

from typing import Any

from src.adapters.zwcad_corpus_scanner import ZWCADCorpusScanner


class ZWCADCompleteCorpusScanner(ZWCADCorpusScanner):
    """Final native text enrichment for ZWCAD objects not classified by the base adapter."""

    def _enrich_entity(
        self,
        obj: Any,
        *,
        layout: str,
        space: str,
        block_path: list[str] | None = None,
        source_kind: str = "drawing_entity",
    ) -> dict[str, Any]:
        item = super()._enrich_entity(
            obj,
            layout=layout,
            space=space,
            block_path=block_path,
            source_kind=source_kind,
        )
        upper = str(item.get("object_name") or self._safe_get(obj, "ObjectName") or "").upper()

        # AcDbAttributeDefinition does not contain the word "Text", so the
        # legacy adapter classifies it as an unknown entity. Capture it here.
        if "ATTRIBUTEDEFINITION" in upper or upper.endswith("ATTDEF"):
            item["entity_type"] = "ATTDEF"
            item["text"] = self._safe_get(obj, "TextString")
            item["tag"] = self._safe_get(obj, "TagString")
            item["insert"] = self._safe_get(obj, "InsertionPoint")
            item["height"] = self._safe_get(obj, "Height")
            item["style_name"] = self._safe_get(obj, "StyleName")
        elif "ATTRIBUTE" in upper:
            item["entity_type"] = "ATTRIB"
            item["text"] = self._safe_get(obj, "TextString")
            item["tag"] = self._safe_get(obj, "TagString")
            item["insert"] = self._safe_get(obj, "InsertionPoint")
            item["height"] = self._safe_get(obj, "Height")
            item["style_name"] = self._safe_get(obj, "StyleName")

        # Product-specific annotation objects often expose TextString or
        # Contents even when their ObjectName is not a standard TEXT class.
        if not item.get("text"):
            for attribute in ("TextString", "Contents", "TextContent", "Value"):
                value = self._safe_get(obj, attribute)
                if isinstance(value, str) and value.strip():
                    item["text"] = value
                    item["generic_text_property"] = attribute
                    break

        field_code = self._safe_get(obj, "FieldCode")
        if field_code in (None, ""):
            try:
                field_code = obj.GetFieldCode()
            except Exception:
                field_code = None
        if field_code not in (None, ""):
            item["field_code"] = str(field_code)

        hyperlink_rows: list[dict[str, Any]] = []
        hyperlinks = self._safe_get(obj, "Hyperlinks")
        for link in self._iter_collection(hyperlinks):
            name = self._safe_get(link, "Name")
            description = self._safe_get(link, "Description")
            if name or description:
                hyperlink_rows.append(
                    {"name": name, "description": description}
                )
        if hyperlink_rows:
            item["hyperlinks"] = hyperlink_rows

        return item
