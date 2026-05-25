# Apply Execution Candidate Planner

This package adds a review-only execution-candidate planner.

It should be stacked after PR #90 or applied after PR #90 is merged.

## Safety

This package does not perform live CAD work, does not change drawings, and keeps all action flags false.

## Validation

Run:

```powershell
python -X utf8 -m pytest -q tests/test_execution_candidate_planner.py
python -X utf8 -m compileall -q src tests
python -X utf8 -m pytest -q
python -X utf8 -m src.main --help
```

CLI smoke can be run after registering the CLI in `src/main.py`.
