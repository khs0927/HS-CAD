# 31. HS-CAD Local Semantic Index

## Final direction

The first production target is an offline module inside HS-CAD, not a separate cloud service.

Reasons:

1. HS-CAD already produces the stable `FileizedDrawingRecord` contract.
2. DWG/DXF/PDF conversion and evidence paths already exist.
3. A local SQLite index avoids drawing-data uploads and recurring costs.
4. The semantic package is isolated so it can later move into a standalone app without changing the record contract.

A separate repository should be created only when one of these becomes true:

- GPU models make the installer too large;
- Linux/GPU batch indexing is required;
- multiple users need a shared server;
- the desktop release cadence must differ from HS-CAD;
- GPL or research-only dependencies must be distributed separately.

## Implemented framework

```text
HS-CAD fileizers
  -> FileizedDrawingRecord JSON
  -> remove TEXT/MTEXT/ATTRIB/ATTDEF entities
  -> GeometryFeatureExtractor
  -> normalized geometry-v1 vector
  -> local SQLite vector store
  -> vectorized cosine similarity search
  -> Typer CLI or Tk desktop UI
```

The first vector uses:

- entity-type distribution;
- line-angle distribution;
- orthogonal-line ratio;
- closed-polyline ratio;
- non-text layer distribution statistics;
- block distribution statistics;
- insert, dimension, circle, and arc ratios;
- drawing complexity and aspect ratio.

No OCR result, TEXT/MTEXT/ATTRIB/ATTDEF object, file name, project name, or address contributes to the score. Empty drawings are skipped during indexing and cannot be used as queries.

## Commands

Prepare normal HS-CAD corpus JSON first:

```powershell
python -m src.main corpus-run prepare --root "C:/cad/source" --workspace "outputs/corpus_workspace" --sample 20
python -m src.main corpus-run fileize --workspace "outputs/corpus_workspace" --limit 20
```

Build the text-independent index:

```powershell
python -m src.main semantic-index build `
  --records-dir "outputs/corpus_workspace/fileized" `
  --db "outputs/semantic_index/semantic.sqlite3" `
  --clear
```

Query with one fileized drawing:

```powershell
python -m src.main semantic-index query `
  --record "outputs/corpus_workspace/fileized/example.json" `
  --db "outputs/semantic_index/semantic.sqlite3" `
  --top-k 20
```

### Evaluate retrieval quality

Copy `examples/semantic_labels.example.csv` and assign records that should be considered similar to the same group.

```csv
record,group
outputs/corpus_workspace/fileized/project_a_plan_01.json,project_a_plan
outputs/corpus_workspace/fileized/project_a_plan_02.json,project_a_plan
outputs/corpus_workspace/fileized/project_b_plan_01.json,project_b_plan
outputs/corpus_workspace/fileized/project_b_plan_02.json,project_b_plan
```

Run Precision@K, Recall@K, and Hit@K evaluation:

```powershell
python -m src.main semantic-index evaluate `
  --labels "examples/semantic_labels.csv" `
  --db "outputs/semantic_index/semantic.sqlite3" `
  --top-k 5 `
  --out "outputs/semantic_index/evaluation.json"
```

Relative record paths are resolved from the CSV directory. Groups containing only one drawing are skipped because no relevant peer exists.

Open the local desktop UI:

```powershell
python -m src.main semantic-index gui
```

Or run:

```text
scripts\start_semantic_index_app.bat
```

## Noncommercial model policy

The local core does not download or bundle model weights.

Optional research integrations are registered in `config/semantic_models.yaml`:

| Resource | Intended use | Distribution policy |
|---|---|---|
| DINOv2 Small | whole drawing and tile embeddings | optional Apache-2.0 runtime |
| FloorPlanCAD | symbol research and evaluation | do not bundle; preserve CC-BY-SA obligations |
| CubiCasa5K | room/wall/door/window research | noncommercial only; use the verified upstream source |
| SymPoint | primitive-based symbol experiments | verify upstream license before use |

Even for noncommercial work, attribution, share-alike, dataset terms, and model-card restrictions still apply.

## Next phases

### Phase A — framework implemented, real-corpus validation pending

- local geometry vector;
- complete text-entity removal;
- SQLite storage;
- vectorized cosine ranking;
- deterministic tie ordering;
- CLI;
- simple Windows desktop UI;
- empty and damaged input handling;
- group-label Precision@K evaluation;
- unit tests;
- no cloud dependency.

Before merge, validate at least 20 actual architectural drawings and record Top-5 quality in the evaluation JSON.

### Phase B — optional visual retrieval

- canonical black-and-white rendering;
- title-block masking;
- TEXT/MTEXT/ATTRIB/ATTDEF/DIMENSION masking;
- DINOv2 whole-image and tile embeddings;
- offline-only model loading with `local_files_only=True`;
- weighted fusion with geometry-v1.

Recommended score:

```text
0.55 geometry similarity
+ 0.35 visual embedding similarity
+ 0.10 symbol distribution similarity
```

### Phase C — architectural semantics

- wall-pair detection;
- closed room graph;
- door/window/column/stair detection;
- graph hash and graph embedding;
- plan/elevation/section classification.

### Phase D — standalone application split

Move `src/semantic_index`, `src/local_app`, and the JSON schemas into a separate repository while retaining `FileizedDrawingRecord` as the boundary.

## Cloud tools decision

Supabase, Neon, Vercel, Alpic, and domain services are intentionally not runtime dependencies of the local application. They may be introduced later for an optional shared catalog or remote administration portal, but original CAD files and extracted geometry should remain local by default.

Fal is not used for the core index because it is a hosted inference service. Hugging Face is the preferred source for optional locally cached research weights and datasets.
