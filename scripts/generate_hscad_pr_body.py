from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

DEFAULT_TITLE = "Add review-only main-code pipeline and evidence bridge"

def run(repo_root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        return ""
    return proc.stdout

def changed_files(repo_root: Path) -> list[str]:
    out = run(repo_root, "status", "--porcelain=v1")
    files = []
    for line in out.splitlines():
        if line.strip():
            path = line[3:]
            if " -> " in path:
                path = path.split(" -> ", 1)[1]
            files.append(path.replace("\\", "/"))
    return sorted(set(files))

def bucket(path: str) -> str:
    if path.startswith("src/hscad/fileizers/"):
        return "Fileizers"
    if path.startswith("src/hscad/analyzers/"):
        return "Analyzers"
    if path.startswith("src/hscad/fusion/"):
        return "Evidence/Fusion"
    if path.startswith("src/hscad/domain_rules/"):
        return "Domain rules"
    if path.startswith("src/hscad/cad/"):
        return "CAD review outputs"
    if path.startswith("src/hscad/connectors/"):
        return "Legacy artifact bridge"
    if path.startswith("src/hscad/pipelines/"):
        return "Pipelines"
    if path.startswith("src/hscad/app/"):
        return "Review-only CLI"
    if path.startswith("src/hscad/indexing/"):
        return "Indexing"
    if path.startswith("src/hscad/reports/"):
        return "Reports"
    if path.startswith("tests/"):
        return "Tests"
    if path.startswith("scripts/"):
        return "Scripts"
    if path.startswith("docs/"):
        return "Docs"
    if path.startswith(".github/"):
        return "CI"
    return "Other"

def render(repo_root: Path, title: str) -> str:
    branch = run(repo_root, "branch", "--show-current") or "<unknown>"
    files = changed_files(repo_root)
    buckets: dict[str, list[str]] = {}
    for path in files:
        if path.startswith(("outputs/", "_incoming/")):
            continue
        if path.lower().endswith((".zip", ".dwg", ".dxf", ".sqlite3", ".pyc")):
            continue
        buckets.setdefault(bucket(path), []).append(path)

    bucket_lines = []
    for name in sorted(buckets):
        bucket_lines.append(f"### {name}")
        for path in buckets[name]:
            bucket_lines.append(f"- `{path}`")
        bucket_lines.append("")

    return f"""# {title}

## Summary

This PR introduces a review-only HS-CAD main-code pipeline and evidence bridge layer. It keeps CAD execution disabled while adding structured fileizers, analysis graph outputs, evidence fusion, domain-rule planning, review DXF output generation, legacy artifact bridging, and PR hygiene tooling.

Branch: `{branch}`

## What changed

{chr(10).join(bucket_lines).strip()}

## Safety posture

- No CAD live execution is introduced.
- No ZWCAD COM call is introduced.
- No SendCommand execution is introduced.
- No XiCAD alias execution is introduced.
- Original DWG mutation remains disabled.
- Domain rule outputs remain plan-only/review-only.
- Runtime artifacts under `outputs/**` and `_incoming/**` are not intended for commit.

## Validation checklist

Run these before opening the PR:

```bash
python -X utf8 -m pytest -q tests/test_main_code_overlay_contracts.py tests/test_main_code_pipeline_smoke.py
python -X utf8 -m pytest -q tests/test_main_code_overlay_v2_contracts.py tests/test_main_code_pipeline_v2_smoke.py
python -X utf8 -m pytest -q tests/test_evidence_bridge_contracts.py tests/test_evidence_bridge_pipeline_smoke.py tests/test_commit_candidate_filter.py
python -X utf8 -m pytest -q tests/test_review_cli_v4_contracts.py tests/test_pr_hygiene_v4.py
python -X utf8 -m pytest -q tests/test_pr_readiness_v5.py
python -m ruff check . --select F821,E9,F63,F7,F82
python -X utf8 -m src.main --help
python -X utf8 -m pytest -q
python -X utf8 scripts\\validate_hscad_pr_ready.py --repo-root .
```

Expected baseline after v3/v4/v5 local validation:
- Full pytest should remain green.
- Ruff critical rules should pass.
- `src.main --help` should pass.
- Forbidden runtime files should be excluded from commit.

## Migration notes

- The new `src/hscad/*` pipeline can coexist with the older pipeline while integration proceeds.
- `src.main` registration should remain review-only and must not execute CAD commands.
- DXF fixtures should be generated at runtime rather than committed as binary/runtime artifacts.
- Future work should connect real analyzer/exporter outputs into the evidence bridge with golden artifacts.

## Follow-up PRs

1. Connect existing analyzer outputs to the new evidence model with real golden samples.
2. Strengthen optional `ezdxf` writer behavior and geometry fidelity.
3. Add more domain-rule checks while preserving plan-only safety.
4. Add Windows CAD adapter smoke tests that verify boundaries without live mutation.
"""

def main() -> int:
    parser = argparse.ArgumentParser(description="Generate HS-CAD PR body for main-code overlay.")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path, default=Path("docs/35_main_code_overlay_pr_body.md"))
    parser.add_argument("--title", default=DEFAULT_TITLE)
    args = parser.parse_args()

    body = render(args.repo_root.resolve(), args.title)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(body + "\n", encoding="utf-8")
    print(args.out)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
