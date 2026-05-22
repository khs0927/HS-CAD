from __future__ import annotations

import shutil
import time
from pathlib import Path

from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter
from src.corpus.schema import FileizedDrawingRecord
from src.fileizers.base import DrawingFileizer
from src.fileizers.dxf_ezdxf_fileizer import DXFEzdxfFileizer


class DWGToDXFEzdxfFileizer(DrawingFileizer):
    """Fast DWG corpus fileizer: save DWG as DXF, then parse with ezdxf.

    COM is used only for the CAD-native Open/SaveAs operation. Python does not
    walk ModelSpace through COM, avoiding per-object IPC bottlenecks on large
    DWGs.
    """

    engine_name = 'zwcad_saveas_dxf_ezdxf'
    supported_extensions = ('.dwg',)

    def __init__(self, temp_root: str | Path | None = None):
        self.temp_root = Path(temp_root) if temp_root else None

    def is_available(self) -> tuple[bool, str]:
        try:
            import comtypes.client  # noqa: F401
        except Exception as exc:
            return False, f'comtypes unavailable: {exc}'
        ok, reason = DXFEzdxfFileizer().is_available()
        if not ok:
            return False, reason
        try:
            adapter = ZWCADCOMAdapter(visible=False)
            adapter.connect()
            return True, 'ZWCAD COM and ezdxf available'
        except Exception as exc:
            return False, f'ZWCAD COM unavailable: {exc}'

    def fileize(self, path: str | Path, *, file_id: str, relative_path: str | Path) -> FileizedDrawingRecord:
        src = Path(path)
        available, reason = self.is_available()
        if not available:
            return FileizedDrawingRecord.unavailable(
                file_id=file_id,
                source_path=src,
                relative_path=relative_path,
                extension=src.suffix,
                engine=self.engine_name,
                reason=reason,
            )

        temp_dir = self._temp_dir(file_id)
        staged_dwg = self._stage_dwg(src, temp_dir, file_id)
        temp_dxf = temp_dir / f'{file_id}.dxf'
        started = time.time()
        adapter = ZWCADCOMAdapter(visible=False)
        try:
            adapter.connect()
            self._open_document(adapter, staged_dwg)
            self._save_as_dxf(adapter, temp_dxf)
            adapter.close()
            record = DXFEzdxfFileizer().fileize(temp_dxf, file_id=file_id, relative_path=relative_path)
            record.source_path = str(src)
            record.extension = src.suffix.lower()
            record.engine = self.engine_name
            record.metadata['staged_dwg_path'] = str(staged_dwg)
            record.metadata['converted_dxf_path'] = str(temp_dxf)
            record.metadata['conversion_seconds'] = round(time.time() - started, 3)
            record.warnings.append({'type': 'dwg_converted_to_dxf', 'path': str(temp_dxf)})
            return record
        except DwgOpenError as exc:
            return FileizedDrawingRecord.failed(
                file_id=file_id,
                source_path=src,
                relative_path=relative_path,
                extension=src.suffix,
                engine=self.engine_name,
                reason=str(exc),
                error_type='open_document_failed',
            )
        except DwgSaveAsError as exc:
            return FileizedDrawingRecord.failed(
                file_id=file_id,
                source_path=src,
                relative_path=relative_path,
                extension=src.suffix,
                engine=self.engine_name,
                reason=str(exc),
                error_type='save_as_dxf_failed',
            )
        except Exception as exc:
            return FileizedDrawingRecord.failed(
                file_id=file_id,
                source_path=src,
                relative_path=relative_path,
                extension=src.suffix,
                engine=self.engine_name,
                reason=str(exc),
            )
        finally:
            try:
                adapter.close()
            except Exception:
                pass

    def _temp_dir(self, file_id: str) -> Path:
        root = self.temp_root or Path('outputs') / 'corpus_tmp_dxf'
        path = root / file_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _stage_dwg(self, src: Path, temp_dir: Path, file_id: str) -> Path:
        staged = temp_dir / f'{file_id}.dwg'
        staged.parent.mkdir(parents=True, exist_ok=True)
        if staged.exists():
            staged.unlink()
        shutil.copy2(src, staged)
        return staged.resolve()

    def _open_document(self, adapter: ZWCADCOMAdapter, staged_dwg: Path) -> None:
        try:
            adapter.open_document(str(staged_dwg))
        except Exception as exc:
            raise DwgOpenError(f'ZWCAD Documents.Open failed for staged DWG: {staged_dwg}; {exc}') from exc

    def _save_as_dxf(self, adapter: ZWCADCOMAdapter, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            target.unlink()
        doc = adapter.doc or adapter.get_active_document()
        last_error: Exception | None = None

        # ZWCAD/AutoCAD COM SaveAs format constants vary by vendor/version.
        # Try DXF-oriented candidates first, then fall back to older values and
        # extension inference. Any failure is reported separately from Open.
        for fmt in (13, 25, 26, 27, 28, 29, 24, 12, 0, None):
            try:
                if fmt is None:
                    doc.SaveAs(str(target))
                else:
                    doc.SaveAs(str(target), fmt)
                if target.exists() and target.stat().st_size > 0:
                    return
            except Exception as exc:
                last_error = exc
        if last_error:
            raise DwgSaveAsError(f'DWG SaveAs DXF failed for target {target}: {last_error}')
        raise DwgSaveAsError(f'DWG SaveAs DXF did not create output file: {target}')


class DwgOpenError(RuntimeError):
    pass


class DwgSaveAsError(RuntimeError):
    pass
