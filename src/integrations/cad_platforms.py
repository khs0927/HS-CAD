from __future__ import annotations

import importlib.util
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class CADPlatformStatus:
    id: str
    display_name: str
    available: bool
    reason: str
    analysis_role: str
    capabilities: list[str]
    required_for_analysis: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CADPlatformRegistry:
    def __init__(self, config_path: str | Path = 'config/cad_platforms.json'):
        self.config_path = Path(config_path)

    def load(self) -> dict[str, Any]:
        return json.loads(self.config_path.read_text(encoding='utf-8'))

    def statuses(self) -> list[CADPlatformStatus]:
        payload = self.load()
        rows: list[CADPlatformStatus] = []
        for platform in payload.get('platforms', []):
            available, reason = self._detect(platform)
            rows.append(CADPlatformStatus(
                id=str(platform.get('id') or ''),
                display_name=str(platform.get('display_name') or ''),
                available=available,
                reason=reason,
                analysis_role=str(platform.get('analysis_role') or ''),
                capabilities=list(platform.get('capabilities') or []),
                required_for_analysis=bool(platform.get('required_for_analysis', False)),
            ))
        return rows

    def summary(self) -> dict[str, Any]:
        statuses = self.statuses()
        preferred = self.preferred_analysis_path(statuses)
        return {
            'config_path': str(self.config_path),
            'platform_count': len(statuses),
            'available_count': sum(1 for item in statuses if item.available),
            'missing_required_count': sum(1 for item in statuses if item.required_for_analysis and not item.available),
            'preferred_analysis_path': preferred,
            'platforms': [item.to_dict() for item in statuses],
        }

    def preferred_analysis_path(self, statuses: list[CADPlatformStatus] | None = None) -> list[str]:
        statuses = statuses or self.statuses()
        by_id = {item.id: item for item in statuses}
        path: list[str] = []
        if by_id.get('oda_file_converter') and by_id['oda_file_converter'].available:
            path.append('oda_file_converter')
        for cad_id in ['autocad', 'zwcad', 'gstarcad', 'bricscad']:
            status = by_id.get(cad_id)
            if status and status.available:
                path.append(cad_id)
        if by_id.get('libredwg') and by_id['libredwg'].available:
            path.append('libredwg')
        if by_id.get('ezdxf') and by_id['ezdxf'].available:
            path.append('ezdxf')
        return path

    def _detect(self, platform: dict[str, Any]) -> tuple[bool, str]:
        platform_id = str(platform.get('id') or '')
        if platform_id == 'ezdxf':
            return self._python_import_available('ezdxf')
        if platform_id == 'oda_file_converter':
            exe = os.environ.get('ODA_FILE_CONVERTER')
            if exe and Path(exe).exists():
                return True, f'ODA_FILE_CONVERTER={exe}'
            known = [
                Path('C:/Program Files/ODA/ODAFileConverter 27.1.0/ODAFileConverter.exe'),
                Path('C:/Program Files/ODA/ODAFileConverter/ODAFileConverter.exe'),
            ]
            for path in known:
                if path.exists():
                    return True, str(path)
            return False, 'ODA File Converter not found'
        if platform_id in {'autocad', 'zwcad', 'gstarcad', 'bricscad'}:
            env_name = f'HSCAD_{platform_id.upper()}_AVAILABLE'
            if os.environ.get(env_name) in {'1', 'true', 'TRUE', 'yes'}:
                return True, f'{env_name}=true'
            return False, f'{env_name} not set; COM/ProgID probing should be done on Windows adapter host'
        if platform_id == 'libredwg':
            env_name = 'LIBREDWG_EXE'
            exe = os.environ.get(env_name)
            if exe and Path(exe).exists():
                return True, f'{env_name}={exe}'
            return False, 'LibreDWG executable not configured'
        return False, 'unknown platform detector'

    @staticmethod
    def _python_import_available(module_name: str) -> tuple[bool, str]:
        available = importlib.util.find_spec(module_name) is not None
        return available, 'python import available' if available else f'python import missing: {module_name}'
