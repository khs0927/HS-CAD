from __future__ import annotations

from pathlib import Path

from tools.prepare_public_release import prepare_public_release


def test_prepare_public_release_excludes_vendor_and_runtime_dirs(tmp_path: Path):
    source = tmp_path / "srcpkg"
    (source / "src").mkdir(parents=True)
    (source / "src" / "main.py").write_text("print('ok')", encoding="utf-8")
    (source / "vendor" / "xicad").mkdir(parents=True)
    (source / "vendor" / "xicad" / "secret.zelx").write_text("binary", encoding="utf-8")
    (source / "outputs").mkdir()
    (source / "outputs" / "objects.json").write_text("[]", encoding="utf-8")
    out = tmp_path / "public"
    copied = prepare_public_release(source, out)
    assert Path("src/main.py") in copied
    assert not (out / "vendor").exists()
    assert not (out / "outputs").exists()
    assert (out / "README_PUBLIC.md").exists()
