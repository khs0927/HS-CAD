from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .models import FileizedDrawingRecord


def write_optional_parquet(records: Iterable[FileizedDrawingRecord], path: Path) -> bool:
    """Write records to parquet if pandas+pyarrow are available."""
    try:
        import pandas as pd  # noqa: F401
    except Exception:
        return False
    try:
        df = pd.DataFrame([r.model_dump(mode="json") for r in records])
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path)
        return True
    except Exception:
        return False
