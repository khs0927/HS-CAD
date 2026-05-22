#!/usr/bin/env python3
"""
check_img2cadseq_release.py
============================
Check whether the Img2CADSeq repository has actual code published
or is still just a README placeholder.

Uses the public GitHub API (no API key required).

Usage:
    python scripts/check_img2cadseq_release.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

try:
    import requests
except ImportError:
    print("[ERROR] 'requests' package is required.  pip install requests")
    sys.exit(1)


REPO = "Rilpraa0110/Img2CADSeq"
API_BASE = f"https://api.github.com/repos/{REPO}"
HEADERS = {"Accept": "application/vnd.github.v3+json"}


def _get(endpoint: str) -> dict | list | None:
    """GET helper with basic error handling."""
    url = f"{API_BASE}/{endpoint}" if endpoint else API_BASE
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        print(f"[WARN] Request failed for {url}: {exc}")
        return None


def check_repo_info() -> dict | None:
    """Fetch basic repository metadata."""
    data = _get("")
    if data is None:
        print(f"[ERROR] Repository {REPO} not found or API unreachable.")
        return None

    print(f"  Repository : {data.get('full_name')}")
    print(f"  Description: {data.get('description', '(none)')}")
    print(f"  Created    : {data.get('created_at')}")
    print(f"  Updated    : {data.get('updated_at')}")
    print(f"  Stars      : {data.get('stargazers_count', 0)}")
    print(f"  Forks      : {data.get('forks_count', 0)}")
    print(f"  Language   : {data.get('language', '(none)')}")
    print(f"  Default Br : {data.get('default_branch', 'main')}")
    print(f"  Size (KB)  : {data.get('size', 0)}")
    return data


def check_releases() -> list:
    """Check for GitHub Releases."""
    data = _get("releases")
    if not data:
        print("  Releases   : None")
        return []
    print(f"  Releases   : {len(data)}")
    for rel in data[:5]:
        tag = rel.get("tag_name", "?")
        name = rel.get("name", "?")
        date = rel.get("published_at", "?")
        assets = len(rel.get("assets", []))
        print(f"    - {tag} ({name}) — {date}, {assets} asset(s)")
    return data


def check_tags() -> list:
    """Check for git tags."""
    data = _get("tags")
    if not data:
        print("  Tags       : None")
        return []
    print(f"  Tags       : {len(data)}")
    for tag in data[:5]:
        print(f"    - {tag.get('name')}")
    return data


def check_contents() -> int:
    """Count files in the repository root to gauge if code is present."""
    data = _get("contents")
    if not data or not isinstance(data, list):
        print("  Root files : Unable to read")
        return 0
    file_count = len(data)
    print(f"  Root items : {file_count}")

    # 분류: 디렉토리 vs 파일
    dirs = [f for f in data if f.get("type") == "dir"]
    files = [f for f in data if f.get("type") == "file"]
    print(f"    Dirs     : {len(dirs)}  {[d['name'] for d in dirs]}")
    print(f"    Files    : {len(files)}  {[f['name'] for f in files]}")

    # 코드 파일 확인 (.py, .yaml, .json, etc.)
    code_extensions = {".py", ".yaml", ".yml", ".json", ".toml", ".cfg", ".sh"}
    code_files = [
        f["name"]
        for f in files
        if any(f["name"].endswith(ext) for ext in code_extensions)
    ]
    if code_files:
        print(f"    Code files in root: {code_files}")
    return file_count


def check_commits() -> int:
    """Check recent commit count (first page only)."""
    data = _get("commits?per_page=5")
    if not data:
        print("  Commits    : Unable to read")
        return 0
    print(f"  Recent commits (up to 5):")
    for c in data:
        sha = c.get("sha", "?")[:7]
        msg = c.get("commit", {}).get("message", "").split("\n")[0][:80]
        date = c.get("commit", {}).get("committer", {}).get("date", "?")
        print(f"    - {sha} {date} — {msg}")
    return len(data)


def main() -> None:
    """Run all checks and produce a verdict."""
    print("=" * 60)
    print(f"  Img2CADSeq Repository Status Check")
    print(f"  {API_BASE}")
    print(f"  Checked at: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)
    print()

    repo = check_repo_info()
    if repo is None:
        sys.exit(1)

    print()
    releases = check_releases()
    tags = check_tags()
    print()
    file_count = check_contents()
    print()
    commit_count = check_commits()

    # ── Verdict ──────────────────────────────────────────────
    print()
    print("=" * 60)
    print("  VERDICT")
    print("=" * 60)

    repo_size = repo.get("size", 0)
    has_code = file_count > 3  # More than just README + LICENSE + .gitignore
    has_releases = len(releases) > 0
    has_language = repo.get("language") is not None

    if has_releases and has_code:
        verdict = "✅ PUBLISHED — Code and releases are available."
    elif has_code and has_language:
        verdict = "🟡 CODE EXISTS — Repository has code but no formal releases."
    elif repo_size > 100 and file_count > 2:
        verdict = "🟡 SOME CONTENT — Repo has content beyond README, worth checking."
    else:
        verdict = "❌ PLACEHOLDER — Repository appears to be README-only (no real code yet)."

    print(f"  {verdict}")
    print()
    print(f"  Size: {repo_size} KB | Root items: {file_count} | "
          f"Releases: {len(releases)} | Tags: {len(tags)} | "
          f"Language: {repo.get('language', 'none')}")
    print()


if __name__ == "__main__":
    main()
