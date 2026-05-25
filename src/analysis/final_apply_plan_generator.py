from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ORDERED_ZIPS = [
    "HS-CAD-cli-finalization-megapack.zip",
    "HS-CAD-analysis-export-megapack.zip",
    "HS-CAD-analysis-storage-megapack.zip",
    "HS-CAD-analysis-report-megapack.zip",
    "HS-CAD-zip-integration-megapack.zip",
    "HS-CAD-pipeline-execution-megapack.zip",
    "HS-CAD-final-orchestration-megapack.zip",
]


def generate_final_apply_plan(repo_root: str | Path = ".") -> dict[str, Any]:
    """Generate final local apply/push plan.

    This is a plan-only artifact. It never modifies git state.
    """
    root = Path(repo_root)
    steps = [
        {
            "order": 1,
            "name": "checkout-local-branch",
            "command": "git switch -C local-megapack-final origin/analysis-evidence-megapack-pr25",
            "mode": "manual",
        },
        {
            "order": 2,
            "name": "apply-generated-zips",
            "command": "python -X utf8 scripts\\apply_megapack_zips.py --zip-dir . --repo-root .",
            "mode": "codegen",
        },
        {
            "order": 3,
            "name": "update-worker-manifest",
            "command": "python -X utf8 scripts\\update_worker_manifest_from_fragments.py --repo-root .",
            "mode": "codegen",
        },
        {
            "order": 4,
            "name": "update-main-imports",
            "command": "python -X utf8 scripts\\update_main_imports.py --repo-root .",
            "mode": "codegen",
        },
        {
            "order": 5,
            "name": "collect-final-todos",
            "command": "python -X utf8 scripts\\collect_final_todos.py",
            "mode": "codegen",
        },
        {
            "order": 6,
            "name": "generate-final-inventory",
            "command": "python -X utf8 scripts\\build_final_codegen_inventory.py",
            "mode": "codegen",
        },
        {
            "order": 7,
            "name": "build-final-codegen-zip",
            "command": "python -X utf8 scripts\\build_final_codegen_zip.py --repo-root . --out outputs\\HS-CAD-final-codegen-bundle.zip",
            "mode": "codegen",
        },
        {
            "order": 8,
            "name": "validation-todo-only",
            "command": "Open outputs\\FINAL_TODO_INDEX.md and follow TODOs later.",
            "mode": "todo",
        },
    ]

    payload = {
        "backend": "final_apply_plan_generator",
        "schema_version": "0.1",
        "summary": {
            "zip_count": len(ORDERED_ZIPS),
            "step_count": len(steps),
        },
        "ordered_zips": ORDERED_ZIPS,
        "steps": steps,
        "warnings": [
            "This is a plan only. It does not run git, tests, or validation.",
            "Validation remains deferred to TODO documents.",
        ],
    }

    out = root / "outputs"
    out.mkdir(parents=True, exist_ok=True)
    (out / "FINAL_APPLY_PLAN.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "FINAL_APPLY_PLAN.md").write_text(_markdown(payload), encoding="utf-8")
    return payload


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Final Apply Plan",
        "",
        "## Ordered ZIPs",
        "",
    ]
    for name in payload.get("ordered_zips") or []:
        lines.append(f"- `{name}`")
    lines.extend([
        "",
        "## Steps",
        "",
        "| Order | Name | Mode | Command |",
        "|---:|---|---|---|",
    ])
    for row in payload.get("steps") or []:
        lines.append(f"| {row.get('order')} | {row.get('name')} | {row.get('mode')} | `{row.get('command')}` |")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    generate_final_apply_plan(".")
