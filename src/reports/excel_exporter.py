from __future__ import annotations
from pathlib import Path
import pandas as pd

def export_excel(sheets: dict[str, list[dict] | dict], path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(p) as writer:
        for name, data in sheets.items():
            if isinstance(data, dict):
                rows = [{'key': k, 'value': v} for k,v in data.items()]
            else:
                rows = data
            pd.DataFrame(rows).to_excel(writer, sheet_name=name[:31], index=False)
    return p
