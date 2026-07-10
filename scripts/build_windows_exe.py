from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
BUILD = ROOT / "build" / "pyinstaller"
SPEC = ROOT / "build" / "spec"
APP_NAME = "HS-CAD"


def _data_arguments() -> list[str]:
    args: list[str] = []
    for relative in ("config", "examples", "schemas", "templates"):
        source = ROOT / relative
        if source.exists():
            args.append(f"--add-data={source}{os.pathsep}{relative}")
    return args


def _pyinstaller_arguments() -> list[str]:
    args = [
        str(ROOT / "src" / "main.py"),
        "--name",
        APP_NAME,
        "--onefile",
        "--console",
        "--clean",
        "--noconfirm",
        "--distpath",
        str(DIST),
        "--workpath",
        str(BUILD),
        "--specpath",
        str(SPEC),
        "--paths",
        str(ROOT),
        "--paths",
        str(ROOT / "src"),
        "--hidden-import=pythoncom",
        "--hidden-import=pywintypes",
        "--hidden-import=win32com",
        "--hidden-import=win32com.client",
        "--hidden-import=comtypes",
        "--collect-submodules=src.workers",
        "--collect-submodules=src.analysis",
        "--collect-submodules=src.app",
        "--collect-submodules=src.spatial",
        "--collect-submodules=src.graph",
        "--collect-submodules=src.analytics",
        "--collect-submodules=src.neuro_seq_cad",
        "--collect-submodules=neuro_seq_cad",
        "--exclude-module=paddle",
        "--exclude-module=paddleocr",
        "--exclude-module=easyocr",
        "--exclude-module=torch",
        "--exclude-module=torchvision",
    ]
    args.extend(_data_arguments())
    return args


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build(*, clean: bool, smoke: bool) -> Path:
    if os.name != "nt":
        raise SystemExit("HS-CAD.exe must be built on Windows because it bundles pywin32/comtypes.")

    if clean:
        shutil.rmtree(BUILD, ignore_errors=True)
        shutil.rmtree(SPEC, ignore_errors=True)
        for output in (DIST / f"{APP_NAME}.exe", DIST / f"{APP_NAME}.exe.sha256"):
            output.unlink(missing_ok=True)

    DIST.mkdir(parents=True, exist_ok=True)
    BUILD.mkdir(parents=True, exist_ok=True)
    SPEC.mkdir(parents=True, exist_ok=True)

    try:
        import PyInstaller.__main__
    except ImportError as exc:
        raise SystemExit('PyInstaller is missing. Run: python -m pip install -e ".[build]"') from exc

    PyInstaller.__main__.run(_pyinstaller_arguments())
    executable = DIST / f"{APP_NAME}.exe"
    if not executable.is_file():
        raise SystemExit(f"Build finished without expected executable: {executable}")

    checksum = _sha256(executable)
    (DIST / f"{APP_NAME}.exe.sha256").write_text(f"{checksum}  {executable.name}\n", encoding="ascii")

    if smoke:
        subprocess.run([str(executable), "--help"], cwd=ROOT, check=True, timeout=120)
        subprocess.run([str(executable), "doctor"], cwd=ROOT, check=True, timeout=120)
        subprocess.run([str(executable), "floorplan-analyze", "--help"], cwd=ROOT, check=True, timeout=120)

    print(f"Built: {executable}")
    print(f"SHA256: {checksum}")
    return executable


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the portable HS-CAD Windows executable.")
    parser.add_argument("--no-clean", action="store_true", help="Keep prior PyInstaller work directories.")
    parser.add_argument("--no-smoke", action="store_true", help="Skip --help and doctor smoke tests.")
    args = parser.parse_args()
    build(clean=not args.no_clean, smoke=not args.no_smoke)


if __name__ == "__main__":
    main()
