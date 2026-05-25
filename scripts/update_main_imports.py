from __future__ import annotations

import argparse
from pathlib import Path


IMPORTS = [
    "import src.app.analysis_shortcut_cli  # noqa: F401,E402",
    "import src.app.analysis_shortcut_cli_v2  # noqa: F401,E402",
    "import src.app.analysis_shortcut_cli_v3  # noqa: F401,E402",
]


def update_main_imports(repo_root: Path) -> Path:
    main_path = repo_root / "src" / "main.py"
    if not main_path.exists():
        raise FileNotFoundError(f"missing {main_path}")

    text = main_path.read_text(encoding="utf-8")
    changed = False
    insert_block = []
    for line in IMPORTS:
        if line not in text:
            insert_block.append(line)
            changed = True

    if not changed:
        return main_path

    lines = text.splitlines()
    insert_at = 0
    for idx, line in enumerate(lines):
        if line.startswith("import ") or line.startswith("from "):
            insert_at = idx + 1

    new_lines = lines[:insert_at] + insert_block + lines[insert_at:]
    main_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return main_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args()
    path = update_main_imports(Path(args.repo_root))
    print(f"updated {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
