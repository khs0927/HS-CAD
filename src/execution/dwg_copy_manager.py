from __future__ import annotations

import hashlib
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


class DWGCopySafetyError(RuntimeError):
    pass


@dataclass(frozen=True)
class DWGCopyManifest:
    original_dwg: str
    working_copy_dwg: str
    save_as_target: str
    original_sha256: str
    working_copy_sha256: str
    original_size: int
    working_copy_size: int
    safety: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    p = Path(path)
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def assert_distinct_paths(original_dwg: str | Path, working_copy_dwg: str | Path, save_as_target: str | Path = "") -> None:
    original = Path(original_dwg).resolve()
    working = Path(working_copy_dwg).resolve()
    if original == working:
        raise DWGCopySafetyError("working_copy_dwg must not equal original_dwg.")
    if save_as_target:
        save_as = Path(save_as_target).resolve()
        if save_as == original:
            raise DWGCopySafetyError("save_as_target must not equal original_dwg.")


def prepare_working_copy(
    original_dwg: str | Path,
    *,
    working_copy_dwg: str | Path,
    save_as_target: str | Path = "",
    overwrite_copy: bool = False,
) -> DWGCopyManifest:
    original = Path(original_dwg)
    working = Path(working_copy_dwg)
    if not original.exists():
        raise DWGCopySafetyError(f"original_dwg not found: {original}")
    if original.suffix.lower() != ".dwg":
        raise DWGCopySafetyError(f"original_dwg must be a DWG file: {original}")

    assert_distinct_paths(original, working, save_as_target)

    working.parent.mkdir(parents=True, exist_ok=True)
    if working.exists() and not overwrite_copy:
        raise DWGCopySafetyError(f"working_copy_dwg already exists. Use overwrite_copy only when intentional: {working}")

    shutil.copy2(original, working)

    original_hash = sha256_file(original)
    working_hash = sha256_file(working)

    return DWGCopyManifest(
        original_dwg=str(original),
        working_copy_dwg=str(working),
        save_as_target=str(save_as_target or ""),
        original_sha256=original_hash,
        working_copy_sha256=working_hash,
        original_size=original.stat().st_size,
        working_copy_size=working.stat().st_size,
        safety={
            "original_dwg_mutation_allowed": False,
            "working_copy_created": True,
            "copy_hash_matches_original": original_hash == working_hash,
            "save_as_target_is_distinct": bool(save_as_target) and Path(save_as_target).resolve() != original.resolve(),
        },
    )
