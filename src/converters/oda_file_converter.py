from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class ConversionResult:
    ok: bool
    engine: str
    source: str
    output: str
    command: list[str]
    stdout: str = ''
    stderr: str = ''
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ODAFileConverter:
    """Headless DWG/DXF converter adapter for ODA File Converter.

    The adapter shells out to an installed converter. It never mutates the
    original drawing. It stages the input in a temporary directory, asks the
    converter to produce DXF, then copies the first matching DXF to the target.
    """

    engine_name = 'oda_file_converter'

    def __init__(self, executable: str | Path | None = None, *, timeout_seconds: int = 120):
        self.executable = Path(executable) if executable else self.find_executable()
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def find_executable() -> Path | None:
        env = os.environ.get('ODA_FILE_CONVERTER') or os.environ.get('ODAFileConverter')
        if env and Path(env).exists():
            return Path(env)
        names = ['ODAFileConverter.exe', 'ODAFileConverter', 'ODA File Converter.exe']
        for name in names:
            found = shutil.which(name)
            if found:
                return Path(found)
        candidates = [
            Path('C:/Program Files/ODA/ODAFileConverter/ODAFileConverter.exe'),
            Path('C:/Program Files/ODA/ODA File Converter/ODAFileConverter.exe'),
            Path('C:/Program Files/Open Design Alliance/ODAFileConverter/ODAFileConverter.exe'),
            Path('C:/Program Files (x86)/ODA/ODAFileConverter/ODAFileConverter.exe'),
            Path('C:/Program Files (x86)/ODA/ODA File Converter/ODAFileConverter.exe'),
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def is_available(self) -> tuple[bool, str]:
        if self.executable and self.executable.exists():
            return True, str(self.executable)
        return False, 'ODA File Converter executable not found. Set ODA_FILE_CONVERTER to the executable path.'

    def convert_to_dxf(self, source: str | Path, target: str | Path) -> ConversionResult:
        src = Path(source).resolve()
        dst = Path(target).resolve()
        ok, reason = self.is_available()
        if not ok:
            return ConversionResult(False, self.engine_name, str(src), str(dst), [], reason=reason)
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            dst.unlink()

        with tempfile.TemporaryDirectory(prefix='hscad_oda_') as tmp:
            tmp_path = Path(tmp)
            input_dir = tmp_path / 'in'
            output_dir = tmp_path / 'out'
            input_dir.mkdir()
            output_dir.mkdir()
            staged = input_dir / src.name
            shutil.copy2(src, staged)
            command = self._build_command(input_dir, output_dir)
            try:
                proc = subprocess.run(
                    command,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    capture_output=True,
                    timeout=self.timeout_seconds,
                )
            except Exception as exc:
                return ConversionResult(False, self.engine_name, str(src), str(dst), command, reason=str(exc))
            dxf_files = sorted(output_dir.rglob('*.dxf')) + sorted(output_dir.rglob('*.DXF'))
            if proc.returncode != 0 and not dxf_files:
                return ConversionResult(False, self.engine_name, str(src), str(dst), command, proc.stdout, proc.stderr, reason=f'exit_code={proc.returncode}')
            if not dxf_files:
                return ConversionResult(False, self.engine_name, str(src), str(dst), command, proc.stdout, proc.stderr, reason='converter did not create a DXF file')
            shutil.copy2(dxf_files[0], dst)
            return ConversionResult(dst.exists() and dst.stat().st_size > 0, self.engine_name, str(src), str(dst), command, proc.stdout, proc.stderr)

    def _build_command(self, input_dir: Path, output_dir: Path) -> list[str]:
        exe = str(self.executable)
        # ODA File Converter CLI convention:
        # ODAFileConverter <input> <output> <out_version> <out_type> <recurse> <audit>
        # ACAD2018 DXF 0 1 is intentionally conservative for broad compatibility.
        return [exe, str(input_dir), str(output_dir), 'ACAD2018', 'DXF', '0', '1']
