# 24. Free-only drawing index runtime

## Guarantee

The required HS-CAD drawing-index runtime is local, offline-capable, and free to operate.

It requires no OpenAI, Anthropic, fal.ai, Hugging Face hosted Job, Vercel, Neon, Alpic, Aleph, Network Solutions, or other paid account. No API key is required for DWG/DXF/PDF indexing and local search.

## Default architecture

```text
Local drawing folder
  -> ZWCAD COM read-only scanner or ezdxf fallback
  -> canonical text/entity records
  -> SQLite FTS5 drawing index
  -> local Markdown/JSON evidence
  -> local SQLite run-history database
  -> CLI / SketchArch / Docufinder consumer
```

All drawing bytes, extracted text, coordinates, entities, and search indexes remain on the workstation by default.

## Free components

| Function | Default component | Cost/account requirement |
|---|---|---|
| DWG native extraction | Installed ZWCAD COM | Uses the user's existing CAD installation; HS-CAD adds no service charge |
| DXF extraction | ezdxf | Open source, local |
| Text search | SQLite FTS5 | Included with Python, local |
| PDF extraction | PyMuPDF | Open source, local |
| Image metadata | Pillow | Open source, local |
| OCR | PaddleOCR or EasyOCR optional extra | Open source, local model inference |
| Run history | `drawing_index_history.sqlite` | Local, no account |
| Search export | JSON and Markdown | Local files |
| Development tests | pytest and ruff | Open source, local |

ZWCAD itself is not bundled or licensed by HS-CAD. When ZWCAD is unavailable, DWG conversion/fallback capabilities depend on the locally installed converter; DXF, PDF, image, SQLite, and search functions remain free.

## One-command local run

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"

python -m src.main corpus-run complete `
  --root "D:\CAD" `
  --workspace "outputs\drawing-index-v2" `
  --summary-backend local
```

The default is already `--summary-backend local`, so the option may be omitted.

Outputs:

```text
outputs/drawing-index-v2/
  cad_knowledge.sqlite
  drawing_index_history.sqlite
  DRAWING_INDEX_RUN_SUMMARY.json
  fileized/json/
  fileized/markdown/
  reviews/
```

## OCR without paid APIs

Install optional OCR dependencies in a Python 3.11 environment:

```powershell
pip install -e ".[ocr]"
```

PaddleOCR is the preferred Korean drawing OCR engine. EasyOCR is a local fallback. Hosted OCR, fal.ai enhancement, OpenAI vision, or other metered APIs are not part of the runtime.

For predictable offline use, pre-download the selected open model once and then set:

```text
HF_HUB_OFFLINE=1
TRANSFORMERS_OFFLINE=1
HSCAD_ALLOW_NETWORK_MODELS=0
```

Synthetic/mock OCR output is not allowed into the production corpus.

## Optional Supabase free-tier summary

Supabase is not required. It is retained only as an optional control plane for non-sensitive counts and completeness status.

```powershell
python -m src.main corpus-run complete `
  --root "D:\CAD" `
  --workspace "outputs\drawing-index-v2" `
  --summary-backend supabase
```

Only the following may leave the workstation:

- run ID and timestamps;
- relative file path;
- extractor name and status;
- entity/text/layout counts;
- completeness blockers.

Drawing bytes, absolute paths, extracted text, geometry, coordinates, and thumbnails are excluded. The service-role key must never be shipped in an EXE. Users who want a strictly offline configuration leave all Supabase variables unset.

## Services deliberately excluded from the required runtime

- OpenAI API and OpenAI-hosted models;
- fal.ai image enhancement;
- Hugging Face hosted Jobs or paid inference endpoints;
- Vercel hosting;
- Neon managed Postgres;
- Alpic deployment;
- Aleph governed data integrations;
- paid domain services;
- proprietary search SaaS and telemetry SDKs.

These services may be evaluated separately, but the local drawing index must never depend on them.

## Free-only validation

Run before release:

```powershell
python scripts\validate_free_only.py
python -m pytest -q tests/test_free_only_runtime.py tests/test_drawing_index_architecture.py
```

The validator fails when a known paid AI/telemetry/payment SDK becomes a required project dependency, when a paid-service secret is added to an environment example, or when the local summary backend is removed.

## GitHub Actions

GitHub Actions is not required for building or testing. The authoritative validation commands run locally. Workflows must not upload artifacts by default and must use local commands that can also be executed on a developer workstation.
