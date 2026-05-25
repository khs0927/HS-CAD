from __future__ import annotations

from pathlib import Path


PROMPT = r"""
You are working on the private HS-CAD repository.

Goal:
Apply all generated megapack ZIPs locally, keep validation deferred as TODO, build one final codegen bundle, and prepare for one-time push later.

Important:
- Do not modify original DWG/PDF/image files.
- Do not run full validation unless explicitly asked later.
- Apply generated ZIPs only.
- Preserve every VALIDATION_TODO*.md file.
- Generate final inventory and final apply plan.

Expected ZIPs:
1. HS-CAD-cli-finalization-megapack.zip
2. HS-CAD-analysis-export-megapack.zip
3. HS-CAD-analysis-storage-megapack.zip
4. HS-CAD-analysis-report-megapack.zip
5. HS-CAD-zip-integration-megapack.zip
6. HS-CAD-pipeline-execution-megapack.zip
7. HS-CAD-final-orchestration-megapack.zip

Commands:

```powershell
git fetch origin analysis-evidence-megapack-pr25
git switch -C local-megapack-final origin/analysis-evidence-megapack-pr25

python -X utf8 scripts\apply_megapack_zips.py --zip-dir . --repo-root .
python -X utf8 scripts\update_worker_manifest_from_fragments.py --repo-root .
python -X utf8 scripts\update_main_imports.py --repo-root .
python -X utf8 scripts\collect_final_todos.py
python -X utf8 scripts\generate_final_apply_plan.py
python -X utf8 scripts\build_final_codegen_inventory.py
python -X utf8 scripts\build_final_codegen_zip.py --repo-root . --out outputs\HS-CAD-final-codegen-bundle.zip
```

Do not run tests now.
Do not run worker chain now.
Only report:
1. files applied
2. manifest updated
3. imports updated
4. final TODO index path
5. final bundle path
6. remaining validation TODO path list
"""


def write_codex_prompt(repo_root: str | Path = ".") -> Path:
    root = Path(repo_root)
    out = root / "outputs" / "CODEX_FINAL_APPLY_PROMPT.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(PROMPT.strip() + "\n", encoding="utf-8")
    return out


if __name__ == "__main__":
    print(write_codex_prompt("."))
