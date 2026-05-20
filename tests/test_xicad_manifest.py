from pathlib import Path
from src.integrations.xicad_manifest import build_manifest


def test_build_manifest(tmp_path: Path):
    (tmp_path / 'a').mkdir()
    (tmp_path / 'a' / 'x.lsp').write_text('(princ)')
    (tmp_path / 'b.dwg').write_bytes(b'abc')
    data = build_manifest(tmp_path)
    assert data['file_count'] == 2
    assert data['extensions']['.lsp'] == 1
    assert data['extensions']['.dwg'] == 1
