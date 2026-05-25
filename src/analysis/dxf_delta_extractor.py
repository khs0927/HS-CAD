from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from src.execution.scan_snapshot import DrawingScanSnapshot


@dataclass(frozen=True)
class DXFEntityModification:
    handle: str
    old_state: dict[str, Any]
    new_state: dict[str, Any]
    changed_keys: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DXFDeltaReport:
    command_hint: str
    added_count: int
    deleted_count: int
    modified_count: int
    added: list[dict[str, Any]]
    deleted: list[dict[str, Any]]
    modified: list[DXFEntityModification]

    def to_dict(self) -> dict[str, Any]:
        return {
            "command_hint": self.command_hint,
            "added_count": self.added_count,
            "deleted_count": self.deleted_count,
            "modified_count": self.modified_count,
            "added": self.added,
            "deleted": self.deleted,
            "modified": [m.to_dict() for m in self.modified],
        }


def extract_dxf_delta(
    before: DrawingScanSnapshot,
    after: DrawingScanSnapshot,
    *,
    command_hint: str = "unknown",
) -> DXFDeltaReport:
    before_dict = {str(item.get("handle")): item for item in before.objects if item.get("handle")}
    after_dict = {str(item.get("handle")): item for item in after.objects if item.get("handle")}

    added_handles = set(after_dict.keys()) - set(before_dict.keys())
    deleted_handles = set(before_dict.keys()) - set(after_dict.keys())
    common_handles = set(before_dict.keys()) & set(after_dict.keys())

    added = [after_dict[h] for h in sorted(added_handles)]
    deleted = [before_dict[h] for h in sorted(deleted_handles)]

    modified: list[DXFEntityModification] = []
    for h in sorted(common_handles):
        old_val = before_dict[h]
        new_val = after_dict[h]
        if old_val != new_val:
            changed_keys = _find_changed_keys(old_val, new_val)
            # Only consider it modified if meaningful keys changed
            if changed_keys:
                modified.append(
                    DXFEntityModification(
                        handle=h,
                        old_state=old_val,
                        new_state=new_val,
                        changed_keys=changed_keys,
                    )
                )

    return DXFDeltaReport(
        command_hint=command_hint,
        added_count=len(added),
        deleted_count=len(deleted),
        modified_count=len(modified),
        added=added,
        deleted=deleted,
        modified=modified,
    )


def _find_changed_keys(old_val: dict[str, Any], new_val: dict[str, Any]) -> list[str]:
    keys = set(old_val.keys()) | set(new_val.keys())
    changed = []
    for k in keys:
        if k in ("timestamp", "_id"):  # Ignore metadata keys that might fluctuate
            continue
        v1 = old_val.get(k)
        v2 = new_val.get(k)
        if isinstance(v1, dict) and isinstance(v2, dict):
            if v1 != v2:  # Simplified deep check
                changed.append(k)
        elif isinstance(v1, list) and isinstance(v2, list):
            if v1 != v2:
                changed.append(k)
        elif v1 != v2:
            changed.append(k)
    return sorted(changed)
