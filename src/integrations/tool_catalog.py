from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_CATALOG_PATH = Path('config/cad_automation_tools.json')


def load_tool_catalog(path: str | Path = DEFAULT_CATALOG_PATH) -> dict[str, Any]:
    source = Path(path)
    if not source.exists():
        return {'tools': [], 'warnings': [{'type': 'missing_catalog', 'path': str(source)}]}
    payload = json.loads(source.read_text(encoding='utf-8'))
    tools = sorted(payload.get('tools', []), key=lambda item: int(item.get('priority') or 9999))
    return {'tools': tools, 'tool_count': len(tools), 'warnings': []}


def find_catalog_tools(query: str = '', path: str | Path = DEFAULT_CATALOG_PATH) -> dict[str, Any]:
    payload = load_tool_catalog(path)
    q = query.lower().strip()
    tools = payload.get('tools', [])
    if q:
        tools = [tool for tool in tools if q in json.dumps(tool, ensure_ascii=False).lower()]
    return {'query': query, 'tools': tools, 'tool_count': len(tools), 'warnings': payload.get('warnings', [])}
