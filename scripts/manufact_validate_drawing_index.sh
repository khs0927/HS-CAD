#!/usr/bin/env bash
set -euo pipefail

python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

python scripts/validate_free_only.py
python scripts/validate_drawing_index_v2.py
python -m compileall -q \
  src/drawing_index \
  src/adapters/ezdxf_corpus_scanner.py \
  src/corpus \
  src/corpus_run \
  src/fileizers \
  scripts \
  tests

python -m pytest -q --disable-warnings --maxfail=1 \
  tests/test_corpus_foundation.py \
  tests/test_drawing_index_v2.py \
  tests/test_drawing_index_architecture.py \
  tests/test_drawing_index_privacy.py \
  tests/test_drawing_index_fallback_resilience.py \
  tests/test_compare_drawing_index_fixture_runs.py \
  tests/test_free_only_runtime.py

python -m ruff check \
  src/drawing_index \
  src/adapters/ezdxf_corpus_scanner.py \
  src/corpus \
  src/corpus_run \
  src/fileizers \
  scripts/validate_free_only.py \
  scripts/validate_drawing_index_v2.py \
  scripts/compare_drawing_index_fixture_runs.py \
  tests/test_drawing_index_v2.py \
  tests/test_drawing_index_architecture.py \
  tests/test_drawing_index_privacy.py \
  tests/test_drawing_index_fallback_resilience.py \
  tests/test_compare_drawing_index_fixture_runs.py \
  tests/test_free_only_runtime.py

echo "MANUFACT_VALIDATION_OK drawing-index-v2"
