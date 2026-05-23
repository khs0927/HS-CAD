# 27. CAD Compatibility and Layer Intelligence Plan

This document defines the next analysis-first direction after PR #4.

## Goal

HS-CAD must analyze practical drawings across common CAD ecosystems without depending on a single CAD vendor.

Supported compatibility targets:

```text
AutoCAD
ZWCAD
GstarCAD
BricsCAD
ODA File Converter
LibreDWG
ezdxf
```

The current priority is not drawing automation. The current priority is reliable drawing analysis.

## Principles

1. Original drawings must not be mutated by analysis stages.
2. DWG should prefer headless conversion to DXF before CAD COM automation.
3. CAD-specific automation must be adapter-based and capability-detected.
4. COM ModelSpace bulk scanning must not be the default for large drawings.
5. Every external CAD/platform integration must expose capability status.
6. Layer intelligence must start with vendor-neutral signals.
7. Company-specific layer profiles must remain a calibration TODO until real Webhard drawings are analyzed.
8. Do not hardcode one office's layer standard as global truth.

## Analysis path priority

Preferred DWG analysis path:

```text
1. ODA File Converter -> DXF -> ezdxf
2. CAD application SaveAs DXF fallback: AutoCAD/ZWCAD/GstarCAD/BricsCAD adapters
3. LibreDWG candidate adapter where validated
4. ezdxf parses DXF
```

## CAD platform discovery

Run:

```powershell
python -X utf8 -m src.main hscad-cad-platforms --out-json outputs\CAD_PLATFORMS.json
```

Expected:

- missing optional CAD platforms should not fail analysis
- preferred_analysis_path should show available providers in priority order
- ezdxf should be available when DXF parsing dependencies are installed

## Layer intelligence

Layer semantics must infer practical meaning using vendor-neutral evidence first:

```text
layer name
entity type distribution
color distribution
linetype distribution
text samples
block name samples
dimension/hatch/block signals
```

Output:

```text
LAYER_SEMANTICS.json
```

Example:

```json
{
  "layer": "A-WALL",
  "predicted_semantic": "wall",
  "confidence": 0.75,
  "evidence": ["layer name matches wall", "linework-heavy layer"]
}
```

## Company-specific calibration TODO

Company-specific layer naming must be calibrated later with the user's actual Webhard corpus.

Do not implement this in the current foundation as hardcoded logic.

Later calibration should use:

```text
Z:\내 드라이브\#웹하드 corpus results
layer frequency by project
object distribution by layer
block names by layer
text samples by layer
manual review corrections
company/project-specific mapping overrides
```

Future output candidates:

```text
COMPANY_LAYER_PROFILE.json
COMPANY_LAYER_PROFILE.md
LAYER_MAPPING_REVIEW.md
```

## Required validation

Run:

```powershell
python -m pytest tests/test_cad_platforms.py tests/test_layer_semantic_inferer.py -q
python -X utf8 -m src.main hscad-cad-platforms --out-json outputs\CAD_PLATFORMS.json
python -X utf8 -m src.main hscad-layer-semantics --workspace outputs\webhard_batch_100
```

Expected files:

```text
outputs\CAD_PLATFORMS.json
outputs\webhard_batch_100\LAYER_SEMANTICS.json
```

## Follow-up development

After this foundation:

1. Validate generic layer inference on Webhard sample batches.
2. Tune generic layer confidence rules without company-specific hardcoding.
3. Add layer-aware spatial/text/area inference.
4. Add layer-aware graph export.
5. Add company-specific profile learner only after enough real corpus results are reviewed.
6. Only after analysis stabilizes: mutation plan / drawing automation.

## Deferred TODO

```text
CompanyLayerProfileLearner
layer mapping report
per-company canonical layer mapping
manual correction workflow
```

These are intentionally deferred until practical drawing analysis results are reviewed.
