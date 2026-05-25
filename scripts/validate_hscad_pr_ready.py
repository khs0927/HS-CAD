from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path

FORBIDDEN_PREFIXES = (
    "outputs/",
    "_incoming/",
)
FORBIDDEN_PARTS = (
    "/__pycache__/",
    "/.pytest_cache/",
    "/.ruff_cache/",
    "/.mypy_cache/",
)
FORBIDDEN_SUFFIXES = (
    ".zip",
    ".dwg",
    ".pyc",
    ".pyo",
    ".sqlite",
    ".sqlite3",
    ".db",
)

# DXF fixtures should be generated at runtime after v2. Runtime DXF must not be
# committed unless a future explicit policy exception is added here.
FORBIDDEN_DXF_SUFFIX = ".dxf"

ALLOWED_PREFIXES = (
    ".github/workflows/",
    "docs/",
    "hscad/",
    "scripts/",
    "src/hscad/",
    "tests/",
)
ALLOWED_ROOT_FILES = {
    "APPLY_INSTRUCTIONS.md",
    "CODEX_MAIN_CODE_PROMPT.md",
    "CODEX_MAIN_CODE_V2_PROMPT.md",
    "CODEX_MAIN_CODE_V3_PROMPT.md",
    "CODEX_MAIN_CODE_V4_PROMPT.md",
    "CODEX_MAIN_CODE_V5_PROMPT.md",
    "LOCAL_AGENT_PROMPT.md",
    "MANIFEST.json",
    "src/main.py",
}

def run_git(repo_root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
    return proc.stdout

def changed_files(repo_root: Path) -> list[str]:
    out = run_git(repo_root, "status", "--porcelain=v1")
    files: list[str] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        files.append(path.replace("\\", "/"))
    return sorted(set(files))

def is_forbidden(path: str) -> tuple[bool, str]:
    normalized = path.replace("\\", "/")
    for prefix in FORBIDDEN_PREFIXES:
        if normalized.startswith(prefix):
            return True, f"forbidden runtime prefix: {prefix}"
    probe = "/" + normalized
    for part in FORBIDDEN_PARTS:
        if part in probe:
            return True, f"forbidden cache path: {part}"
    lower = normalized.lower()
    if lower.endswith(FORBIDDEN_DXF_SUFFIX):
        return True, "runtime DXF files must not be committed"
    for suffix in FORBIDDEN_SUFFIXES:
        if lower.endswith(suffix):
            return True, f"forbidden suffix: {suffix}"
    return False, ""

def is_expected(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return normalized in ALLOWED_ROOT_FILES or normalized.startswith(ALLOWED_PREFIXES)

def validate(repo_root: Path) -> dict:
    files = changed_files(repo_root)
    forbidden = []
    unexpected = []
    allowed = []

    for path in files:
        blocked, reason = is_forbidden(path)
        if blocked:
            forbidden.append({"path": path, "reason": reason})
            continue
        if not is_expected(path):
            unexpected.append(path)
        else:
            allowed.append(path)

    return {
        "changed_count": len(files),
        "allowed_count": len(allowed),
        "forbidden_count": len(forbidden),
        "unexpected_count": len(unexpected),
        "allowed": allowed,
        "forbidden": forbidden,
        "unexpected": unexpected,
        "ready": not forbidden and not unexpected and bool(allowed),
    }

def main() -> int:
    parser = argparse.ArgumentParser(description="Validate HS-CAD PR readiness and forbidden files.")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    result = validate(args.repo_root.resolve())
    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text + "\n", encoding="utf-8")
    return 0 if result["ready"] else 2

if __name__ == "__main__":
    raise SystemExit(main())
