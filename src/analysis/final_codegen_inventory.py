from __future__ import annotations

import json
from pathlib import Path
from typing import Any


INCLUDE_DIRS = ["src", "docs", "config", "scripts"]
CODE_EXTENSIONS = {".py", ".ps1", ".json", ".md", ".toml", ".yaml", ".yml"}


def build_final_codegen_inventory(repo_root: str | Path = ".") -> dict[str, Any]:
    root = Path(repo_root)
    rows = []
    for dirname in INCLUDE_DIRS:
        base = root / dirname
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in CODE_EXTENSIONS:
                continue
            rel = str(path.relative_to(root))
            rows.append({
                "path": rel,
                "suffix": path.suffix.lower(),
                "size_bytes": path.stat().st_size,
                "category": _category(rel),
            })

    payload = {
        "backend": "final_codegen_inventory",
        "schema_version": "0.1",
        "summary": {
            "file_count": len(rows),
            "total_size_bytes": sum(int(row["size_bytes"]) for row in rows),
            "src_py_count": sum(1 for row in rows if row["path"].startswith("src/") and row["suffix"] == ".py"),
            "docs_md_count": sum(1 for row in rows if row["path"].startswith("docs/") and row["suffix"] == ".md"),
            "scripts_count": sum(1 for row in rows if row["path"].startswith("scripts/")),
        },
        "files": rows,
        "todo": [
            "Generate after all ZIPs are applied.",
            "Use this inventory for one-time push review.",
            "Add git diff summary after local repo is available.",
        ],
    }

    out_dir = root / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "FINAL_CODEGEN_INVENTORY.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "FINAL_CODEGEN_INVENTORY.md").write_text(_markdown(payload), encoding="utf-8")
    return payload


def _category(path: str) -> str:
    if path.startswith("src/workers/"):
        return "worker"
    if path.startswith("src/analysis/"):
        return "analysis"
    if path.startswith("src/app/"):
        return "cli"
    if path.startswith("docs/"):
        return "docs"
    if path.startswith("scripts/"):
        return "script"
    if path.startswith("config/"):
        return "config"
    return "other"


def _markdown(payload: dict[str, Any]) -> str:
    s = payload.get("summary") or {}
    lines = [
        "# Final Codegen Inventory",
        "",
        f"- Files: `{s.get('file_count')}`",
        f"- Total bytes: `{s.get('total_size_bytes')}`",
        f"- src/*.py count: `{s.get('src_py_count')}`",
        f"- docs/*.md count: `{s.get('docs_md_count')}`",
        f"- scripts count: `{s.get('scripts_count')}`",
        "",
        "| Path | Category | Size |",
        "|---|---|---:|",
    ]
    for row in (payload.get("files") or [])[:500]:
        lines.append(f"| {row.get('path')} | {row.get('category')} | {row.get('size_bytes')} |")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    build_final_codegen_inventory(".")
