# HS-CAD Final Live Runner Manual Copy-only Interface

## Proposed future CLI

```powershell
python -X utf8 -m src.main hscad-final-live-runner `
  --candidate-json outputs/phase12_manual_live_candidate_verify/PHASE12_MANUAL_LIVE_EXECUTION_CANDIDATE.json `
  --working-copy-dwg "C:/cad/test_work/copy.dwg" `
  --save-as-target "C:/cad/test_work/result.dwg" `
  --alias WAL `
  --manual-live-flag `
  --operator-approved `
  --out-dir outputs/final_live_runner_verify
```

## Status

Interface proposal only. Do not implement until safety spec PR is approved.
