# HS-CAD Review Output Quality Plan

## Purpose

This document defines the next implementation step after the schema-aware evidence bridge. The goal is to improve generated review outputs so that QA markers, low-confidence findings, and evidence references are easier to inspect.

## Scope

- Add structured QA issue labels.
- Add a manifest describing generated review files.
- Keep original drawing inputs unchanged.
- Keep all workflows review-only.
- Add focused tests for output manifests, QA label text, and low-confidence markers.

## Planned files

- `src/hscad/cad/review_output.py`
- `src/hscad/cad/dxf_builders.py`
- `scripts/inspect_review_dxf_outputs.py`
- `tests/test_review_dxf_output_v7.py`

## Validation

```bash
python -X utf8 -m pytest -q tests/test_review_dxf_output_v7.py
python -m ruff check . --select F821,E9,F63,F7,F82
python -X utf8 -m src.main --help
python -X utf8 -m pytest -q
```

## Safety

This stage must remain review-only. It should generate derived review artifacts only and must not modify original inputs.

## Branch note

Use `feature/review-output-quality-v2` for the clean continuation branch. Do not use the abandoned intermediate branch `feature/review-dxf-output-fidelity`.
