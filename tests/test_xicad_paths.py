from pathlib import Path
from src.integrations.xicad_paths import detect_xicad_profile


def test_detect_xicad_profile(tmp_path: Path):
    root = tmp_path / 'xicad'
    (root / '_ZWCad').mkdir(parents=True)
    (root / 'Lisp').mkdir(parents=True)
    (root / 'Lisp' / 'xi.zelx').write_text('dummy')
    (root / 'Lisp' / 'xiShortkey_origin.key').write_text('WAL ;xiDrawWall ;벽 그리기', encoding='utf-8')
    (root / '_ZWCad' / 'xicad_ZWCAD.cuix').write_text('dummy')
    profile = detect_xicad_profile(root)
    assert profile.lisp_dir is not None
    assert profile.shortkey_file is not None
    assert profile.loader_candidates
    assert profile.menu_candidates
