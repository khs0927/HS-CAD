from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Any

from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter
from src.converters.oda_file_converter import ODAFileConverter
from src.corpus.schema import FileizedDrawingRecord
from src.fileizers.base import DrawingFileizer
from src.fileizers.dxf_ezdxf_fileizer import DXFEzdxfFileizer


class DWGToDXFEzdxfFileizer(DrawingFileizer):
    """Fast DWG corpus fileizer: convert DWG to DXF, then parse with ezdxf.

    Preferred order:
    1. External headless converter, currently ODA File Converter when available.
    2. ZWCAD COM Open/SaveAs.
    3. ZWCAD SendCommand Open/SaveAs/DXFOUT fallback.

    Python never walks ModelSpace through COM for bulk fileization.
    """

    engine_name = 'zwcad_saveas_dxf_ezdxf'
    supported_extensions = ('.dwg',)

    def __init__(self, temp_root: str | Path | None = None, *, command_timeout_seconds: float = 45.0, prefer_external_converter: bool = True):
        self.temp_root = Path(temp_root) if temp_root else None
        self.command_timeout_seconds = command_timeout_seconds
        self.prefer_external_converter = prefer_external_converter
        self.command_fallback_used = False
        self.external_converter_used = False
        self.external_converter_result: dict[str, Any] | None = None

    def is_available(self) -> tuple[bool, str]:
        ok, reason = DXFEzdxfFileizer().is_available()
        if not ok:
            return False, reason
        oda_ok, oda_reason = ODAFileConverter().is_available()
        if oda_ok:
            return True, f'ODA File Converter and ezdxf available: {oda_reason}'
        try:
            import comtypes.client  # noqa: F401
        except Exception as exc:
            return False, f'No external converter and comtypes unavailable: {exc}'
        try:
            adapter = ZWCADCOMAdapter(visible=False)
            adapter.connect()
            return True, f'ZWCAD COM and ezdxf available; external converter unavailable: {oda_reason}'
        except Exception as exc:
            return False, f'No external converter and ZWCAD COM unavailable: {exc}; converter={oda_reason}'

    def fileize(self, path: str | Path, *, file_id: str, relative_path: str | Path) -> FileizedDrawingRecord:
        self.command_fallback_used = False
        self.external_converter_used = False
        self.external_converter_result = None
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
            external_error = self._try_external_converter(staged_dwg, temp_dxf) if self.prefer_external_converter else None
            if not temp_dxf.exists() or temp_dxf.stat().st_size == 0:
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
            record.metadata['command_fallback_used'] = self.command_fallback_used
            record.metadata['external_converter_used'] = self.external_converter_used
            if self.external_converter_result:
                record.metadata['external_converter_result'] = self.external_converter_result
            record.warnings.append({'type': 'dwg_converted_to_dxf', 'path': str(temp_dxf)})
            if self.external_converter_used:
                record.warnings.append({'type': 'external_converter_used', 'engine': 'oda_file_converter'})
            if self.command_fallback_used:
                record.warnings.append({'type': 'zwcad_sendcommand_fallback_used'})
            if external_error:
                record.warnings.append({'type': 'external_converter_failed_then_fallback', 'reason': external_error})
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

    def _try_external_converter(self, staged_dwg: Path, temp_dxf: Path) -> str | None:
        result = ODAFileConverter().convert_to_dxf(staged_dwg, temp_dxf)
        self.external_converter_result = result.to_dict()
        if result.ok and temp_dxf.exists() and temp_dxf.stat().st_size > 0:
            self.external_converter_used = True
            return None
        return result.reason or 'external converter did not create DXF'

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
        direct_error: Exception | None = None
        try:
            adapter.open_document(str(staged_dwg))
            return
        except Exception as exc:
            direct_error = exc
        try:
            self._open_document_via_sendcommand(adapter, staged_dwg)
            self.command_fallback_used = True
            return
        except Exception as fallback_exc:
            raise DwgOpenError(
                f'ZWCAD Documents.Open failed for staged DWG: {staged_dwg}; direct={direct_error}; sendcommand={fallback_exc}'
            ) from fallback_exc

    def _save_as_dxf(self, adapter: ZWCADCOMAdapter, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            target.unlink()
        doc = adapter.doc or adapter.get_active_document()
        last_error: Exception | None = None
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
        try:
            self._save_as_dxf_via_sendcommand(adapter, target)
            self.command_fallback_used = True
            return
        except Exception as fallback_exc:
            if last_error:
                raise DwgSaveAsError(f'DWG SaveAs DXF failed for target {target}: direct={last_error}; sendcommand={fallback_exc}') from fallback_exc
            raise DwgSaveAsError(f'DWG SaveAs DXF did not create output file: {target}; sendcommand={fallback_exc}') from fallback_exc

    def _open_document_via_sendcommand(self, adapter: ZWCADCOMAdapter, staged_dwg: Path) -> None:
        doc = self._ensure_command_document(adapter)
        command = f'_.OPEN\n"{self._cmd_path(staged_dwg)}"\n'
        self._send_command(doc, command)
        deadline = time.time() + self.command_timeout_seconds
        while time.time() < deadline:
            active = self._try_active_document(adapter)
            if active is not None and self._document_matches_path(active, staged_dwg):
                adapter.doc = active
                return
            time.sleep(0.5)
        raise TimeoutError(f'SendCommand OPEN did not activate staged DWG within {self.command_timeout_seconds}s: {staged_dwg}')

    def _save_as_dxf_via_sendcommand(self, adapter: ZWCADCOMAdapter, target: Path) -> None:
        doc = adapter.doc or adapter.get_active_document()
        command_candidates = [
            f'_.SAVEAS\nDXF\n"{self._cmd_path(target)}"\n',
            f'_.SAVEAS\n"{self._cmd_path(target)}"\n',
            f'_.DXFOUT\n"{self._cmd_path(target)}"\n16\n',
        ]
        errors: list[str] = []
        for command in command_candidates:
            if target.exists():
                target.unlink()
            try:
                self._send_command(doc, command)
                self._wait_for_file(target, self.command_timeout_seconds)
                return
            except Exception as exc:
                errors.append(str(exc))
        raise TimeoutError(f'SendCommand DXF export failed for {target}: {errors}')

    def _ensure_command_document(self, adapter: ZWCADCOMAdapter) -> Any:
        active = self._try_active_document(adapter)
        if active is not None:
            return active
        app = adapter.app
        if app is None:
            adapter.connect()
            app = adapter.app
        try:
            return app.Documents.Add()
        except Exception:
            return app.ActiveDocument

    @staticmethod
    def _try_active_document(adapter: ZWCADCOMAdapter) -> Any | None:
        try:
            if adapter.app is None:
                return None
            return adapter.app.ActiveDocument
        except Exception:
            return None

    @staticmethod
    def _send_command(doc: Any, command: str) -> None:
        doc.SendCommand(command if command.endswith('\n') else command + '\n')

    @staticmethod
    def _cmd_path(path: Path) -> str:
        return str(path.resolve()).replace('\\', '/')

    @staticmethod
    def _document_matches_path(doc: Any, path: Path) -> bool:
        wanted = str(path.resolve()).lower().replace('\\', '/')
        for attr in ('FullName', 'Path'):
            try:
                value = str(getattr(doc, attr)).lower().replace('\\', '/')
                if value == wanted or value in wanted or wanted in value:
                    return True
            except Exception:
                continue
        try:
            return str(getattr(doc, 'Name')).lower() == path.name.lower()
        except Exception:
            return False

    @staticmethod
    def _wait_for_file(path: Path, timeout_seconds: float) -> None:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            if path.exists() and path.stat().st_size > 0:
                return
            time.sleep(0.5)
        raise TimeoutError(f'Output file was not created within {timeout_seconds}s: {path}')


class DwgOpenError(RuntimeError):
    pass


class DwgSaveAsError(RuntimeError):
    pass
