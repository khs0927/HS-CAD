from __future__ import annotations
from pathlib import Path
from datetime import datetime
import shutil

def backup_file(path: str | Path, backup_dir: str | Path = 'backups') -> Path:
    src = Path(path)
    if not src.exists():
        raise FileNotFoundError(f"Cannot backup missing file: {src}")
    outdir = Path(backup_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    dst = outdir / f"{src.stem}_{stamp}{src.suffix}"
    shutil.copy2(src, dst)
    return dst
