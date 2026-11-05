# 24. Free-only drawing index runtime

## Guarantee

The required HS-CAD drawing-index runtime is local, offline-capable, and free to operate. It requires no hosted AI, paid inference endpoint, cloud database, or API key for DWG/DXF/PDF indexing and local search.

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

Drawing bytes, paths, extracted text, coordinates, entities, and search indexes remain on the workstation by default.

## Free components

| Function | Default component | Cost/account requirement |
|---|---|---|
| DWG native extraction | Installed ZWCAD COM | Uses the user's existing CAD installation |
| DXF extraction | ezdxf | Open source, local |
| Text search | SQLite FTS5 | Included with Python, local |
| PDF extraction | PyMuPDF | Open source, local |
| Image metadata | Pillow | Open source, local |
| OCR | PaddleOCR or EasyOCR optional extra | Open source, local model inference |
| Run history | `drawing_index_history.sqlite` | Local, no account |
| Search export | JSON and Markdown | Local files |
| Development tests | pytest and ruff | Open source, local |

ZWCAD itself is not bundled or licensed by HS-CAD. When ZWCAD is unavailable, DWG conversion depends on a locally installed converter; DXF, PDF, image, SQLite, and search functions remain free.

## One-command Windows setup

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_free_local.ps1
```

Manual equivalent:

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

```powershell
pip install -e ".[ocr]"
```

PaddleOCR is the preferred Korean drawing OCR engine. EasyOCR is a local fallback. Hosted OCR, generative enhancement, or metered vision APIs are not part of the required runtime.

For predictable offline use:

```text
HF_HUB_OFFLINE=1
TRANSFORMERS_OFFLINE=1
HSCAD_ALLOW_NETWORK_MODELS=0
```

Synthetic or mock OCR output is not allowed into the production corpus.

## Optional Supabase free-tier summary

Supabase is not required. It is retained only as an optional control plane for non-sensitive aggregate counts and completeness status. The operator must explicitly opt in.

```powershell
$env:HSCAD_ALLOW_EXTERNAL_SUMMARY = "1"
$env:HSCAD_SUPABASE_URL = "https://YOUR_FREE_PROJECT.supabase.co"
$env:HSCAD_SUPABASE_SERVICE_ROLE_KEY = "set-only-in-this-trusted-session"

python -m src.main corpus-run complete `
  --root "D:\CAD" `
  --workspace "outputs\drawing-index-v2" `
  --summary-backend supabase
```

Only the following may leave the workstation:

- run ID, timestamps, and a hashed workspace identifier;
- opaque file ID and file extension;
- extractor name and status;
- entity, text-occurrence, layout, and XREF counts;
- completeness blockers and allowlisted extraction metrics.

The remote compatibility column named `relative_path` always receives the fixed marker `<redacted>`. Real relative paths remain only in local SQLite history.

Never uploaded:

- drawing bytes;
- absolute or relative source paths;
- extracted text;
- entity payloads;
- geometry or coordinates;
- thumbnails or rendered drawing images.

The service-role key must never be shipped in an EXE. Users who want a strictly offline configuration leave all Supabase variables unset.

## Services deliberately excluded from the required runtime

- OpenAI or Anthropic APIs;
- fal.ai enhancement;
- Hugging Face hosted Jobs or paid endpoints;
- Vercel hosting;
- Neon managed Postgres;
- Alpic or Aleph services;
- paid domains;
- proprietary search, telemetry, payment, or vector-database SDKs.

## Free-only validation

```powershell
python scripts\validate_free_only.py
python -m pytest -q tests/test_free_only_runtime.py tests/test_drawing_index_architecture.py
```

The validator fails when a known paid AI, telemetry, payment, or vector-database SDK becomes a required dependency, when a paid-service secret is added to an environment example, or when the local summary backend is removed.

## GitHub Actions

GitHub Actions is not required for building or testing. The authoritative commands run locally. Workflows must use the same local commands and must not upload private drawing evidence.
