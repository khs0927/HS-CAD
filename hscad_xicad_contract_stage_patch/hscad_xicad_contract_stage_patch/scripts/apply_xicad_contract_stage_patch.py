from __future__ import annotations

import argparse
from pathlib import Path
import shutil


PATCH_ROOT = Path(__file__).resolve().parents[1]

COPY_PATHS = [
    "src/orchestrator/xicad_contracts.py",
    "src/orchestrator/xicad_contract_test_plan.py",
    "src/orchestrator/xicad_contract_validator.py",
    "src/orchestrator/xicad_contract_report.py",
    "src/app/xicad_contract_cli.py",
    "docs/25_xicad_contract_verification_stage.md",
    "tests/test_xicad_contract_registry.py",
    "tests/test_xicad_contract_validation.py",
    "tests/test_xicad_contract_cli_model.py",
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
    line = "import src.app.xicad_contract_cli  # noqa: F401,E402"
    if line in text:
        print("[SKIP] xicad_contract_cli already registered")
        return

    marker = "import src.app.xicad_stage2_cli  # noqa: F401,E402"
    if marker in text:
        text = text.replace(marker, marker + "\n" + line)
    else:
        marker2 = "import src.app.orchestrated_cli  # noqa: F401,E402"
        if marker2 in text:
            text = text.replace(marker2, marker2 + "\n" + line)
        else:
            insert_after = "from src.app.cli import app\n"
            text = text.replace(insert_after, insert_after + "\n" + line + "\n")

    path.write_text(text, encoding="utf-8")
    print("[PATCH] src/main.py registered xicad_contract_cli")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="HS-CAD repository root")
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()
    copy_files(repo_root)
    patch_main_py(repo_root)
    print("")
    print("Done. Next:")
    print("  python -m src.main --help")
    print("  python -m src.main xicad-contract-plan --aliases WAL,D1,W1,INS,COL,BE --out-dir outputs/xicad_contracts")
    print("  pytest -q tests/test_xicad_contract_registry.py tests/test_xicad_contract_validation.py tests/test_xicad_contract_cli_model.py")


if __name__ == "__main__":
    main()
