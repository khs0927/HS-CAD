# 23. Drawing Index Modular Framework

## Objective

Keep HS-CAD as the single authoritative ingestion and indexing engine while
separating CAD extraction, completeness policy, orchestration, persistence, and
optional cloud monitoring. The local SQLite index remains the source of truth.

## Package boundaries

```text
src/adapters/
  zwcad_*_scanner.py          Native ZWCAD object extraction
  ezdxf_corpus_scanner.py    DXF object extraction

src/fileizers/
  *.py                        File open/convert wrappers only

src/corpus/
  schema.py                   Stable FileizedDrawingRecord contract
  text_extraction.py          Canonical text occurrence expansion
  indexer.py                  Local SQLite + FTS5 persistence
  query.py                    Evidence-rich local search

src/drawing_index/domain/
  completeness.py             One PASS/REVIEW policy for every extractor
  models.py                   Privacy-conscious run/file summaries

src/drawing_index/application/
  fileizer_registry.py        Ordered fallback and best-result selection
  run_service.py              End-to-end application orchestration
  contracts.py                External summary sink port

src/drawing_index/infrastructure/
  supabase_summary_sink.py    Optional run telemetry; no drawings or text
```

## Fallback behavior

For a DWG file the registry now:

1. runs native ZWCAD extraction;
2. applies the shared completeness policy;
3. stops immediately only when the result is complete;
4. otherwise continues to DWG-to-DXF/ezdxf;
5. selects the highest-quality result and records every attempt.

This fixes the previous behavior where the first `status=ok` result was accepted
even when its extraction report was incomplete.

## DXF adapter improvements

The dedicated ezdxf scanner now covers:

- ModelSpace and every PaperSpace layout;
- normal and constant block attributes;
- dimension geometry block text;
- MLeader content and Leader annotation handles;
- XREF insert declarations;
- tables where the entity exposes cells;
- raster/OLE OCR-required signals;
- unsupported proxy signals;
- structured layout, block, and entity failure counts.

The implementation follows the current ezdxf APIs for `INSERT.attribs`,
`INSERT.block()`, `ATTRIB/ATTDEF.is_const`, `DIMENSION.get_geometry_block()`,
`MLEADER.context.mtext`, and `INSERT.is_xref`.

## Complete run command

```powershell
python -m src.main corpus-run complete `
  --root "D:\CAD" `
  --workspace "outputs\drawing-index-v2" `
  --sample 5
```

The command exits with code `1` when any drawing remains in REVIEW. The result
file is:

```text
outputs/drawing-index-v2/DRAWING_INDEX_RUN_SUMMARY.json
```

## Optional Supabase control plane

Supabase is not used as the authoritative drawing index. It stores run and
per-file completeness statistics only.

Never uploaded:

- DWG/DXF/PDF/image bytes;
- absolute source paths;
- entity payloads;
- extracted text;
- coordinates or geometry.

The schema is in:

```text
supabase/migrations/20260713040000_cad_index_run_summaries.sql
```

To publish summaries from a trusted runner:

```powershell
$env:HSCAD_SUPABASE_URL="https://PROJECT.supabase.co"
$env:HSCAD_SUPABASE_SERVICE_ROLE_KEY="..."
python -m src.main corpus-run complete `
  --root "D:\CAD" `
  --workspace "outputs\drawing-index-v2" `
  --cloud-summary
```

The service-role key must never be included in the desktop executable.

## Selected integrations

- **GitHub**: source, branch, pull request, code review and release history.
- **Context7**: current ezdxf API verification.
- **Supabase**: optional privacy-conscious run monitoring.
- **Linear**: remaining Windows/ZWCAD fixture and release work.
- **Hugging Face**: future local OCR/model evaluation only; no model is bundled.
- **fal.ai**: optional scan enhancement research only; generative enhancement is
  not allowed to replace source evidence.

Neon, Vercel, Alpic, Aleph, Network Solutions, Miro, Resume Builder, and OpenAI
API keys are intentionally not runtime dependencies of the local indexing core.
They should be introduced only when a concrete deployment, data, visual-planning,
resume, domain, or hosted-agent requirement exists.
