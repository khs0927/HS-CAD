from pathlib import Path

from src.fileizers.dwg_dxf_ezdxf_fileizer import DWGToDXFEzdxfFileizer, DwgOpenError, DwgSaveAsError


class _OpenFailAdapter:
    def open_document(self, path: str):
        raise RuntimeError('open failed')


class _SaveFailDoc:
    def SaveAs(self, *args):
        raise RuntimeError('save failed')


class _SaveFailAdapter:
    doc = _SaveFailDoc()

    def get_active_document(self):
        return self.doc


def test_open_document_failure_is_classified(tmp_path: Path):
    fileizer = DWGToDXFEzdxfFileizer(temp_root=tmp_path)
    try:
        fileizer._open_document(_OpenFailAdapter(), tmp_path / 'sample.dwg')
    except Exception as exc:
        assert isinstance(exc, DwgOpenError)
        assert 'Documents.Open failed' in str(exc)
    else:
        raise AssertionError('expected DwgOpenError')


def test_save_as_failure_is_classified(tmp_path: Path):
    fileizer = DWGToDXFEzdxfFileizer(temp_root=tmp_path)
    try:
        fileizer._save_as_dxf(_SaveFailAdapter(), tmp_path / 'sample.dxf')
    except Exception as exc:
        assert isinstance(exc, DwgSaveAsError)
        assert 'SaveAs DXF failed' in str(exc)
    else:
        raise AssertionError('expected DwgSaveAsError')
