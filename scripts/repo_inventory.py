from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any


EXCLUDED_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "outputs",
    "output",
    "scratch",
}

GENERATED_PREFIXES = (
    "_phase",
    "_main_readiness_patch",
    "_post_pr53_patch",
    "_main_merge_decision_patch",
    "_pr55_main_ready_patch",
)

SAFETY_FLAGS = {
    "final_live_runner_implemented": False,
    "sendcommand_allowed_by_default": False,
    "cad_execution_allowed_by_default": False,
    "zwcad_com_allowed_by_default": False,
    "xicad_alias_execution_allowed_by_default": False,
}


def _iter_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        if any(part in EXCLUDED_DIRS for part in rel.parts):
            continue
        if path.is_file():
            files.append(path)
    return sorted(files)


def _commands_from_main(root: Path) -> list[str]:
    main = root / "src" / "main.py"
    if not main.exists():
        return []
    try:
        tree = ast.parse(main.read_text(encoding="utf-8"))
    except Exception:
        return []
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names if alias.name.startswith("src.app."))
    return sorted(imports)


def build_repo_inventory(repo_root: str | Path = ".") -> dict[str, Any]:
    root = Path(repo_root).resolve()
    files = _iter_files(root)
    suffix_counts: dict[str, int] = {}
    top_level_counts: dict[str, int] = {}
    generated_artifacts: list[str] = []

    for path in files:
        rel = path.relative_to(root).as_posix()
        suffix = path.suffix.lower() or "<none>"
        suffix_counts[suffix] = suffix_counts.get(suffix, 0) + 1
        top = rel.split("/", 1)[0]
        top_level_counts[top] = top_level_counts.get(top, 0) + 1
        if rel.startswith(GENERATED_PREFIXES) or "/__pycache__/" in rel:
            generated_artifacts.append(rel)

    docs = sorted(path.relative_to(root).as_posix() for path in (root / "docs").glob("*.md")) if (root / "docs").exists() else []
    tests = sorted(path.relative_to(root).as_posix() for path in (root / "tests").glob("test_*.py")) if (root / "tests").exists() else []

    pyproject = root / "pyproject.toml"
    workflows = sorted(
        path.relative_to(root).as_posix()
        for path in (root / ".github" / "workflows").glob("*.yml")
    ) if (root / ".github" / "workflows").exists() else []

    return {
        "schema_version": "0.1",
        "repo_root": str(root),
        "summary": {
            "file_count": len(files),
            "test_count": len(tests),
            "doc_count": len(docs),
            "workflow_count": len(workflows),
        },
        "pyproject": {
            "exists": pyproject.exists(),
            "path": "pyproject.toml",
        },
        "src_main": {
            "exists": (root / "src" / "main.py").exists(),
            "registered_app_imports": _commands_from_main(root),
        },
        "tests": tests,
        "docs": docs,
        "workflows": workflows,
        "suffix_counts": dict(sorted(suffix_counts.items())),
        "top_level_counts": dict(sorted(top_level_counts.items())),
        "outputs_policy": {
            "outputs_committed": False,
            "scratch_committed": False,
            "generated_runtime_artifacts_committed": False,
        },
        "generated_artifacts": generated_artifacts[:200],
        "safety_flags": SAFETY_FLAGS,
    }


def write_repo_inventory(repo_root: str | Path = ".", out: str | Path = "outputs/repo_inventory/REPO_INVENTORY.json") -> Path:
    payload = build_repo_inventory(repo_root)
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate HS-CAD repository inventory.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--out", default="outputs/repo_inventory/REPO_INVENTORY.json")
    args = parser.parse_args()
    path = write_repo_inventory(args.repo_root, args.out)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
