from __future__ import annotations

import argparse
from pathlib import Path
import shutil

PATCH_ROOT = Path(__file__).resolve().parents[1]

COPY_PATHS = [
    "src/orchestrator/xicad_contract_workbench.py",
    "src/orchestrator/xicad_contract_bundle.py",
    "src/orchestrator/xicad_promotion_review.py",
    "src/app/xicad_contract_workbench_cli.py",
    "docs/26_xicad_contract_workbench.md",
    "tests/test_xicad_contract_workbench.py",
    "tests/test_xicad_contract_bundle.py",
    "tests/test_xicad_promotion_review.py",
]


def copy_files(repo_root: Path) -> None:
    for rel in COPY_PATHS:
        src = PATCH_ROOT / rel
        dst = repo_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        print(f"[COPY] {rel}")


def patch_main_py(repo_root: Path) -> None:
    path = repo_root / "src" / "main.py"
    if not path.exists():
        print("[WARN] src/main.py not found")
        return
    text = path.read_text(encoding="utf-8")
    line = "import src.app.xicad_contract_workbench_cli  # noqa: F401,E402"
    if line in text:
        print("[SKIP] xicad_contract_workbench_cli already registered")
        return

    anchors = [
        "import src.app.xicad_contract_cli  # noqa: F401,E402",
        "import src.app.xicad_stage2_cli  # noqa: F401,E402",
        "import src.app.orchestrated_cli  # noqa: F401,E402",
    ]
    for anchor in anchors:
        if anchor in text:
            text = text.replace(anchor, anchor + "\n" + line)
            break
    else:
        insert_after = "from src.app.cli import app\n"
        text = text.replace(insert_after, insert_after + "\n" + line + "\n")
    path.write_text(text, encoding="utf-8")
    print("[PATCH] src/main.py registered xicad_contract_workbench_cli")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="HS-CAD repository root")
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()
    copy_files(repo_root)
    patch_main_py(repo_root)
    print("")
    print("Done. Next:")
    print("  python -m src.main xicad-contract-session --alias WAL --out-dir outputs/xicad_sessions")
    print("  pytest -q tests/test_xicad_contract_workbench.py tests/test_xicad_contract_bundle.py tests/test_xicad_promotion_review.py")


if __name__ == "__main__":
    main()
