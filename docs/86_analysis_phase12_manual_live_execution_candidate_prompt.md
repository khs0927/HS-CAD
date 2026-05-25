# HS-CAD Phase 12 Manual Live Execution Candidate Prompt

## Goal

Apply Phase 12 manual-only live execution candidate guard.

This phase still does not execute CAD. It only checks whether a manual live execution candidate could be prepared from copied-DWG plan + XiCAD allowlist + operator approval flags.

## Branch

```powershell
git fetch origin feat/analysis-phase10-11-domain-copy-validation
git switch feat/analysis-phase10-11-domain-copy-validation
git switch -c feat/analysis-phase12-manual-live-execution-candidate
```

## Apply patch ZIP

Save the ZIP at:

```text
C:\Users\user\Downloads\HS-CAD-phase12-manual-live-execution-candidate-patch.zip
```

Apply from repo root:

```powershell
cd C:\CODE\HS-CAD
Expand-Archive -Path "C:\Users\user\Downloads\HS-CAD-phase12-manual-live-execution-candidate-patch.zip" -DestinationPath ".\_phase12_patch" -Force
Copy-Item -Path ".\_phase12_patch\*" -Destination "." -Recurse -Force
```

## Optional CLI registration

Add to `src/main.py` only if CLI registration is included in this PR:

```python
import src.app.analysis_phase12_cli  # noqa: F401,E402
```

Otherwise keep CLI registration separate.

## Targeted tests

```powershell
python -X utf8 -m pytest -q tests/test_analysis_phase12_manual_live_execution_candidate.py
python -X utf8 -m src.main --help
```

## Optional CLI smoke

If CLI registration was added:

```powershell
python -X utf8 -m src.main hscad-analysis-phase12-manual-live-candidate --workspace outputs\phase10_11_domain_copy_verify --alias WAL --out-dir outputs\phase12_manual_live_candidate_verify
```

This should be blocked by default because manual flags are not provided.

Manual-ready candidate smoke, still no execution:

```powershell
python -X utf8 -m src.main hscad-analysis-phase12-manual-live-candidate --workspace outputs\phase10_11_domain_copy_verify --alias WAL --manual-live-flag --operator-approved --out-dir outputs\phase12_manual_live_candidate_verify
```

Expected outputs:

```text
PHASE12_MANUAL_LIVE_EXECUTION_CANDIDATE.json
PHASE12_MANUAL_LIVE_EXECUTION_CANDIDATE.md
PHASE12_FINAL_RUNNER_GUARD.json
```

## Safety checks

Confirm:

- `execution_allowed` is false
- `sendcommand_allowed` is false
- final runner is `not_implemented`
- original and copied DWG paths differ
- blocked alias is rejected
- unknown alias is rejected
- outputs are not committed
- no DWG/DXF files are committed

## Commit

```powershell
git add src/analysis/phase12_manual_live_execution_candidate.py
git add src/workers/analysis_phase12_manual_live_execution_candidate_worker.py
git add src/app/analysis_phase12_cli.py
git add tests/test_analysis_phase12_manual_live_execution_candidate.py
git add docs/86_analysis_phase12_manual_live_execution_candidate_prompt.md
git add docs/87_analysis_phase12_manual_live_execution_candidate_report.md
git add config/worker_manifest.phase12.patch.json
git add MAIN_IMPORT_PHASE12_PATCH.txt
git add README_APPLY_PHASE12.md

git commit -m "feat: add phase12 manual live execution candidate guard"
git push -u origin feat/analysis-phase12-manual-live-execution-candidate
```

## PR

Base:

```text
feat/analysis-phase10-11-domain-copy-validation
```

Head:

```text
feat/analysis-phase12-manual-live-execution-candidate
```

Title:

```text
Implement Phase 12 manual live execution candidate guard
```
