# 22. Complete Drawing Index V2 Architecture

## Decision

HS-CAD is the authoritative drawing-ingestion and indexing engine.

The small indexer previously added to `-sketcharch-open` remains a lightweight consumer/UI prototype only. It must not become a second CAD parser. Docufinder is also a consumer: HS-CAD can export searchable Markdown/JSON, but Docufinder is not embedded because its BSL license and Tauri/Rust build make it unsuitable as the core proprietary CAD extraction engine.

## Existing HS-CAD assets reused

HS-CAD already contains the correct foundation:

- ZWCAD COM adapter and DWG open/read support;
- DWG-to-DXF fallback;
- ezdxf DXF parsing;
- corpus record writer;
- SQLite/FTS index;
- file, layer, entity, text, block, dimension and failure tables;
- evidence packages and query/report commands;
- PDF raster, PaddleOCR text-region, OCR-to-CAD matching and text-evidence fusion workers.

V2 extends these components rather than starting over.

## Evaluated open-source components

| Component | License | Decision | Role |
|---|---:|---|---|
| `mozman/ezdxf` | MIT | Adopt | Primary DXF parser and non-Windows test engine |
| SQLite FTS5 | Public domain | Adopt | Local full-text index |
| `PaddlePaddle/PaddleOCR` | Apache-2.0 | Reuse existing | Korean/rotated raster text OCR |
| EasyOCR | Apache-2.0 | Existing optional fallback | OCR fallback in non-corpus workflows |
| `tesseract-ocr/tesseract` | Apache-2.0 | Future lightweight fallback | CPU OCR fallback |
| `LibreDWG/libredwg` | GPL-3.0 | External optional only | DWG recovery/conversion when CAD is absent |
| `DomCR/ACadSharp` | MIT | Keep as .NET fallback candidate | Independent DWG/DXF cross-check, not Python core |
| `LibreCAD/libdxfrw` | GPL-2.0 | Do not embed | C++ integration cost and weaker fit than ezdxf |
| LibreCAD application | GPL-2.0 | Do not embed | Viewer/editor, not an indexing library |
| Docufinder/Anything | BSL-1.1 | Consumer only | Search UI through exported Markdown/JSON |
| ODA File Converter | Freeware, not OSS | Existing optional fallback | DWG-to-DXF conversion only |

### Why ZWCAD COM remains primary for DWG

The user already operates ZWCAD 2026. Native COM exposes evaluated text, attributes, layouts, block references and product-specific objects that may be lost or flattened by conversion. Therefore the complete profile runs native ZWCAD first and falls back to DWG-to-DXF only when native extraction is unavailable or fails.

## V2 canonical text occurrence

Every extracted string becomes an independent evidence row:

```json
{
  "occurrence_id": "sha256...",
  "file_id": "drawing-id",
  "handle": "3FA2",
  "sub_handle": "3FA3",
  "entity_type": "MTEXT",
  "layer": "A-ANNO",
  "layout": "1층 평면도",
  "space": "paper",
  "block_path": ["TITLE_BLOCK", "NOTE_BLOCK"],
  "source_kind": "block_attribute",
  "tag": "DOOR_NO",
  "raw_text": "{\\H2.5x;D-101}",
  "plain_text": "D-101",
  "normalized_text": "d-101",
  "insert": [12450.2, 8630.8, 0.0],
  "bbox": null,
  "confidence": 1.0,
  "xref_path": null
}
```

Raw, visible and normalized text are all retained. Search never replaces the evidence text with a lossy normalized value.

## Native coverage

The V2 ZWCAD scanner covers:

- ModelSpace;
- every paper-space Layout whose layout block is exposed by COM;
- TEXT, MTEXT, ATTRIB and constant attributes;
- block definitions and block-reference attributes;
- dimensions: override, evaluated display and measurement fallback;
- MLeader/Leader text;
- Table cell values;
- XREF declarations and paths;
- handles, layers, layout names, block paths and positions;
- raster/OLE detection with an explicit OCR-required flag;
- proxy-object detection.

A missing layout block is never replaced with the active `PaperSpace`, because that would duplicate and mislabel text. It is recorded as incomplete instead.

DXF receives the same canonical structure through ezdxf and scans all layouts, block definitions and INSERT attributes.

## Completeness contract

“Complete” is not inferred from a successful file open. Each record includes an `extraction_report` with:

- entity and text occurrence counts;
- layout and block-definition counts;
- XREF and unresolved-XREF counts;
- warning count;
- raster/OLE OCR-required count;
- unsupported proxy-object count;
- per-capability coverage flags;
- fallback attempts.

A drawing is marked complete only when no extraction warnings remain, all exposed layouts were scanned, XREF declarations are resolved, no unsupported proxy object remains and no unprocessed raster/OLE text source is detected. Password-protected/corrupt files and unavailable engines remain visible as failures, not silently ignored.

## Storage

V1 tables remain for backward compatibility. V2 adds:

- `text_occurrences`;
- `text_fts_v2`;
- `layouts`;
- `xrefs`;
- `extraction_runs`.

The V2 FTS index stores file path, layer, layout, block path, visible text and normalized text. Search results return the original file, layout, layer, handle, block path, coordinates, bbox and confidence.

## Fallback order

For DWG:

1. native ZWCAD COM complete scanner;
2. DWG-to-DXF conversion and complete ezdxf scanner;
3. optional external LibreDWG adapter in a separate process;
4. metadata-only failure record.

The runner continues to the next fileizer when an earlier engine is unavailable or fails, and records every attempt. Availability checks do not launch a second ZWCAD instance.

## Raster/OCR phase

Native CAD text and OCR text must not be mixed without provenance.

- The existing `src/ocr/text_region_analysis.py` is the corpus-safe OCR route: it runs real PaddleOCR when installed and otherwise reports `paddleocr unavailable`; it does not fabricate text.
- The older `neuro_seq_cad/ocr/paddleocr_adapter.py` mock fallback is excluded from corpus indexing because synthetic text must never enter the search index.
- Native CAD text uses confidence `1.0`.
- OCR rows use `source_kind=ocr`, engine/model metadata and per-box confidence.
- Embedded images and OLE objects are first recorded as OCR-required evidence.
- Existing OCR-to-CAD matching now reads canonical V2 text occurrences, including attributes, dimensions, leaders and tables.
- Existing text-evidence fusion remains the review/conflict layer.
- OCR output is supplemental and never overwrites native text.

## Local validation

Pure-Python tests do not require ZWCAD:

```powershell
python -m pytest -q tests/test_drawing_index_v2.py
python -m pytest -q tests/test_corpus_foundation.py
```

Windows/ZWCAD fixture test:

```powershell
python -m src.main corpus-run prepare --root "D:\CAD" --workspace "outputs\index-v2" --sample 5
python -m src.main corpus-run fileize --workspace "outputs\index-v2" --limit 5
python -m src.main corpus-run index --workspace "outputs\index-v2"
python -m src.main corpus-run query "방화구획" --workspace "outputs\index-v2"
```

For each sample, inspect `fileized/json/*.json` and confirm:

- all layouts are listed;
- native and block-attribute strings are present;
- table/leader/dimension strings are present where applicable;
- raster/OLE and proxy objects are explicitly reported;
- `extraction_report.complete` is true, or every missing category has a reason.

No claim of complete production coverage is valid until this real ZWCAD fixture matrix passes.
