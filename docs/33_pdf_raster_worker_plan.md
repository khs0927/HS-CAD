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
PDF_COORDINATE_CONTRACT.json
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

## Coordinate contract

PR #10 now defines the first PDF coordinate contract so vector objects and raster contours can be compared in the same space.

Coordinate spaces:

```text
pdf_points_top_left
pixel_top_left
normalized_page
```

`PDF_COORDINATE_CONTRACT.json` contains one row per rendered page:

```text
page_contract_id
source_pdf
page_index
dpi
page_width_pdf
page_height_pdf
pixel_width
pixel_height
pixel_to_pdf_scale_x
pixel_to_pdf_scale_y
pdf_to_pixel_scale_x
pdf_to_pixel_scale_y
pdf_origin
pixel_origin
```

## Artifacts

### PDF_VECTOR_OBJECTS.json

Rows include:

```text
source_pdf
page_index
object_type
text
pdf_bbox
normalized_bbox
page_width_pdf
page_height_pdf
coordinate_space
page_contract_id
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
page_index
page_contract_id
contour_index
pixel_bbox
pdf_bbox
normalized_bbox
coordinate_space
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
page contract count
vector object count
contour count
render output count
coordinate contract summary
warnings
```

## Vector-raster comparison helpers

The module includes helper functions for future cross-validation:

```text
pixel_bbox_to_pdf_bbox
normalize_bbox
bbox_iou
```

These prepare the next step:

```text
PDF vector line/rect/text bbox ↔ OpenCV contour bbox IoU
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
outputs\webhard_batch_100\PDF_COORDINATE_CONTRACT.json
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
vector-raster IoU report
line/rectangle/table contour classification
OCR text region worker
layout/table/titleblock detection
```
