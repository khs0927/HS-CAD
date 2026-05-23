# 33. PDF / Raster Worker Plan

This document defines PR #10: optional PDF / Raster Worker.

## Goal

Add a PDF/Raster analysis worker using optional backends:

```text
PyMuPDF      -> PDF page rendering
pdfplumber   -> vector PDF objects
OpenCV       -> raster contour extraction
NumPy        -> OpenCV support
```

The worker is isolated. HS-CAD Core does not hard-require these libraries.

## Worker

Worker name:

```text
pdf_raster
```

Command:

```powershell
python -X utf8 -m src.main hscad-worker-run pdf_raster --workspace outputs\webhard_batch_100
```

## Options

```json
{
  "dpi": 180,
  "max_pages": 3
}
```

## Inputs

The worker discovers PDF files in the workspace:

```text
workspace/**/*.pdf
run_manifest.json referenced PDF paths, when present
```

## Outputs

```text
PDF_RASTER_ANALYSIS.json
PDF_VECTOR_OBJECTS.json
RASTER_CONTOURS.json
PDF_RASTER_REPORT.md
pdf_raster/rendered/*.png
WORKER_RUNS.json
WORKER_AUDIT.json
worker_logs/pdf_raster.jsonl
```

## Backends

### PyMuPDF

Used for page rendering to PNG.

### pdfplumber

Used for vector PDF object extraction:

```text
chars
lines
rects
curves
```

### OpenCV

Used for raster contour extraction after rendering.

Initial method:

```text
threshold binary inverse
find external contours
filter tiny contours
```

## Artifacts

### PDF_VECTOR_OBJECTS.json

Rows include:

```text
source_pdf
page_index
object_type
text
x0
top
x1
bottom
width
height
```

### RASTER_CONTOURS.json

Rows include:

```text
source_pdf
source_image
contour_index
x
y
width
height
area
```

### PDF_RASTER_REPORT.md

Report includes:

```text
backend availability
PDF count
vector object count
contour count
render output count
warnings
```

## Safety

The worker only reads source files and writes derived artifacts in the workspace.

If a backend is missing, the worker records availability and warnings, then still writes output artifacts.

## Validation

Run:

```powershell
python -m pytest tests/test_pdf_raster_worker.py tests/test_worker_contracts.py tests/test_worker_runner.py tests/test_worker_run_log.py -q
python -X utf8 -m src.main hscad-worker-run pdf_raster --workspace outputs\webhard_batch_100
```

Expected files:

```text
outputs\webhard_batch_100\PDF_RASTER_ANALYSIS.json
outputs\webhard_batch_100\PDF_VECTOR_OBJECTS.json
outputs\webhard_batch_100\RASTER_CONTOURS.json
outputs\webhard_batch_100\PDF_RASTER_REPORT.md
outputs\webhard_batch_100\WORKER_RUNS.json
outputs\webhard_batch_100\WORKER_AUDIT.json
outputs\webhard_batch_100\worker_logs\pdf_raster.jsonl
```

## Follow-up

Future PRs can add:

```text
vector-raster IoU
line/rectangle/table contour classification
page coordinate transform contract
OCR text region worker
layout/table/titleblock detection
```
