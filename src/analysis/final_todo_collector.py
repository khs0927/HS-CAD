from __future__ import annotations

import json
from pathlib import Path
from typing import Any


TODO_GLOBS = [
    "docs/VALIDATION_TODO*.md",
    "docs/*TODO*.md",
    "PATCH_*.md",
    "README_APPLY*.md",
]


def collect_final_todos(repo_root: str | Path = ".") -> dict[str, Any]:
    """Collect all TODO / patch / apply docs into one final index.

    This is a code-generation support tool. It does not run validation.
    """
    root = Path(repo_root)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    for pattern in TODO_GLOBS:
        for path in sorted(root.glob(pattern)):
            if not path.is_file():
                continue
            rel = str(path.relative_to(root))
            if rel in seen:
                continue
            seen.add(rel)
            text = path.read_text(encoding="utf-8", errors="replace")
            rows.append({
                "path": rel,
                "size_bytes": path.stat().st_size,
                "heading": _first_heading(text),
                "command_count": text.count("python -X utf8") + text.count("pytest") + text.count("git "),
                "patch_hint": rel.startswith("PATCH_"),
            })

    payload = {
        "backend": "final_todo_collector",
        "schema_version": "0.1",
        "summary": {
            "todo_file_count": len(rows),
            "patch_file_count": sum(1 for row in rows if row.get("patch_hint")),
            "command_hint_count": sum(int(row.get("command_count") or 0) for row in rows),
        },
        "todos": rows,
        "todo": [
            "Run this after all ZIPs are applied.",
            "Use FINAL_TODO_INDEX.md as the single checklist before push.",
            "Do not treat TODO collection as validation.",
        ],
    }

    out = root / "outputs"
    out.mkdir(parents=True, exist_ok=True)
    (out / "FINAL_TODO_INDEX.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "FINAL_TODO_INDEX.md").write_text(_markdown(payload), encoding="utf-8")
    return payload


def _first_heading(text: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return None


def _markdown(payload: dict[str, Any]) -> str:
    s = payload.get("summary") or {}
    lines = [
        "# Final TODO Index",
        "",
        f"- TODO files: `{s.get('todo_file_count')}`",
        f"- Patch files: `{s.get('patch_file_count')}`",
        f"- Command hints: `{s.get('command_hint_count')}`",
        "",
        "| Path | Heading | Commands | Patch |",
        "|---|---|---:|---:|",
    ]
    for row in payload.get("todos") or []:
        lines.append(f"| {row.get('path')} | {row.get('heading') or ''} | {row.get('command_count')} | {row.get('patch_hint')} |")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    collect_final_todos(".")
