# HS-CAD Local Evidence Finalization + Safety Spec Approval Prompt

## Context

This follows Local Validation Evidence Review.

It finalizes whether manually gathered local evidence is sufficient for a human final-live-runner safety spec approval review.

This PR does not implement final live runner.

## Branch

```powershell
git fetch origin local/local-validation-evidence-review
git switch local/local-validation-evidence-review
git pull --ff-only
git switch -c review/local-evidence-finalization-safety-spec-approval
```

## Apply ZIP

Save ZIP:

```text
C:\Users\user\Downloads\HS-CAD-local-evidence-finalization-safety-spec-approval.zip
```

Apply:

```powershell
Expand-Archive -Path "C:\Users\user\Downloads\HS-CAD-local-evidence-finalization-safety-spec-approval.zip" -DestinationPath ".\_local_evidence_finalization_patch" -Force
Copy-Item -Path ".\_local_evidence_finalization_patch\*" -Destination "." -Recurse -Force
```

## Optional CLI registration

```python
import src.app.local_evidence_finalization_cli  # noqa: F401,E402
```

## Validate

```powershell
python -X utf8 -m pytest -q tests/test_local_evidence_finalization_safety_spec_approval.py
python -X utf8 -m compileall -q src tests
python -X utf8 -m pytest -q
python -X utf8 -m src.main --help
```

If CLI registered:

```powershell
python -X utf8 -m src.main hscad-local-evidence-finalization --repo-root . --out-dir outputs\local_evidence_finalization_safety_spec_approval
```

## Expected outputs

```text
LOCAL_EVIDENCE_FINALIZATION_SAFETY_SPEC_APPROVAL.json
LOCAL_EVIDENCE_FINALIZATION_SAFETY_SPEC_APPROVAL.md
HUMAN_SAFETY_SPEC_APPROVAL_PROMPT.md
IMPLEMENTATION_PR_HARD_GATES.json
```

## Commit

```powershell
git add src/analysis/local_evidence_finalization_safety_spec_approval.py
git add src/workers/local_evidence_finalization_safety_spec_approval_worker.py
git add src/app/local_evidence_finalization_cli.py
git add tests/test_local_evidence_finalization_safety_spec_approval.py
git add docs/138_local_evidence_finalization_safety_spec_approval_prompt.md
git add docs/139_local_evidence_finalization_safety_spec_approval_report.md
git add config/worker_manifest.local_evidence_finalization.patch.json
git add MAIN_IMPORT_LOCAL_EVIDENCE_FINALIZATION_PATCH.txt
git add README_APPLY_LOCAL_EVIDENCE_FINALIZATION.md
git add PROMPT_LOCAL_EVIDENCE_FINALIZATION_SAFETY_SPEC_APPROVAL.txt

git commit -m "review: add local evidence finalization and safety spec approval gate"
git push -u origin review/local-evidence-finalization-safety-spec-approval
```
