from __future__ import annotations

import argparse
import subprocess

PATTERNS = ["generated", "outputs", "temp_overlay", "hs-cad_fileizer_corpus_patch.zip", "samples/sample_plan.png"]


def git_ls_files(pattern: str) -> list[str]:
    proc = subprocess.run(["git", "ls-files", pattern], check=False, capture_output=True, text=True, encoding="utf-8")
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Remove tracked runtime artifacts from HS-CAD PR branch.")
    parser.add_argument("--apply", action="store_true", help="Actually run git rm --cached for tracked artifacts.")
    args = parser.parse_args()
    tracked: list[str] = []
    for pattern in PATTERNS:
        tracked.extend(git_ls_files(pattern))
    tracked = sorted(set(tracked))
    print("Tracked runtime artifacts:")
    if not tracked:
        print("- none")
        return 0
    for item in tracked:
        print(f"- {item}")
    if not args.apply:
        print("\nDry-run only. Re-run with --apply to remove from git tracking.")
        return 0
    for item in tracked:
        cmd = ["git", "rm", "-r", "--cached", "--ignore-unmatch", item]
        print("+ " + " ".join(cmd))
        subprocess.run(cmd, check=False)
    print("\nDone. Review with: git status")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
