from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator


class PromptContract(BaseModel):
    """Observed XiCAD prompt sequence for one alias.

    Templates use Python ``str.format`` placeholders. A contract is executable
    only after ``verified`` is set from a real ZWCAD + XiCAD observation.
    """

    alias: str
    argument_templates: list[str] = Field(default_factory=list)
    verified: bool = False
    zwcad_version: str = ""
    xicad_version: str = ""
    notes: str = ""

    @field_validator("alias")
    @classmethod
    def normalize_alias(cls, value: str) -> str:
        return value.strip().upper()

    def render(self, parameters: dict[str, Any]) -> list[str]:
        if not self.verified:
            raise ValueError(f"XiCAD contract is not verified: {self.alias}")
        try:
            return [template.format_map(parameters) for template in self.argument_templates]
        except KeyError as exc:
            raise ValueError(f"Missing parameter {exc.args[0]!r} for {self.alias}") from exc


class ContractLibrary:
    def __init__(self, contracts: list[PromptContract] | None = None) -> None:
        self._contracts = {item.alias: item for item in contracts or []}

    @classmethod
    def from_directory(cls, path: str | Path) -> "ContractLibrary":
        root = Path(path)
        contracts: list[PromptContract] = []
        if not root.exists():
            return cls()
        for file in sorted(root.glob("*.json")):
            data = json.loads(file.read_text(encoding="utf-8"))
            if isinstance(data, list):
                contracts.extend(PromptContract.model_validate(item) for item in data)
            else:
                contracts.append(PromptContract.model_validate(data))
        return cls(contracts)

    def get(self, alias: str) -> PromptContract | None:
        return self._contracts.get(alias.strip().upper())

    def require_verified(self, alias: str) -> PromptContract:
        item = self.get(alias)
        if item is None:
            raise ValueError(f"No XiCAD prompt contract found: {alias}")
        if not item.verified:
            raise ValueError(f"XiCAD prompt contract is not verified: {alias}")
        return item

    def summary(self) -> dict[str, Any]:
        rows = [item.model_dump(mode="json") for item in sorted(self._contracts.values(), key=lambda x: x.alias)]
        return {
            "contract_count": len(rows),
            "verified_count": sum(1 for row in rows if row["verified"]),
            "contracts": rows,
        }
