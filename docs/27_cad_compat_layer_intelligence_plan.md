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
6. Layer intelligence must be company-profile-friendly because every office uses different layer standards.

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

Layer semantics must infer practical meaning using:

```text
layer name
entity type distribution
color distribution
linetype distribution
text samples
block name samples
dimension/hatch/block signals
company profile mappings
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

1. CompanyLayerProfileLearner
2. layer mapping report
3. layer semantic confidence tuning
4. per-company canonical layer mapping
5. layer-aware spatial/text/area inference
6. layer-aware graph export
7. only after analysis stabilizes: mutation plan / drawing automation
