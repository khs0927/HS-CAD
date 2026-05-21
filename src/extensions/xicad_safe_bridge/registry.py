from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
import re

from .models import XicadAlias, XicadCategory, XicadRisk


_CATEGORY_RULES: list[tuple[set[str], XicadCategory]] = [
    ({"WAL"}, XicadCategory.wall),
    ({"COL", "CLI"}, XicadCategory.column),
    ({"BLI", "BLS"}, XicadCategory.beam),
    ({"BE", "STB"}, XicadCategory.steel),
    ({"D1", "D2", "D3"}, XicadCategory.door),
    ({"W1", "W2", "W3", "WO", "CW"}, XicadCategory.window),
    ({"STP", "STC"}, XicadCategory.stair),
    ({"ELV", "EPD", "EED"}, XicadCategory.elevator),
    ({"PK"}, XicadCategory.parking),
    ({"INS"}, XicadCategory.insulation),
    ({"SCB", "PZ"}, XicadCategory.annotation),
]


_DEFAULT_ALIASES: list[XicadAlias] = [
    XicadAlias(alias="WAL", name="벽 그리기", category=XicadCategory.wall, risk=XicadRisk.medium),
    XicadAlias(alias="COL", name="기둥 그리기", category=XicadCategory.column, risk=XicadRisk.medium),
    XicadAlias(alias="CLI", name="기둥 일람표", category=XicadCategory.column, risk=XicadRisk.medium),
    XicadAlias(alias="BLI", name="보 일람표", category=XicadCategory.beam, risk=XicadRisk.medium),
    XicadAlias(alias="BLS", name="보 스케줄", category=XicadCategory.beam, risk=XicadRisk.medium),
    XicadAlias(alias="BE", name="철골 부재 그리기", category=XicadCategory.steel, risk=XicadRisk.medium),
    XicadAlias(alias="STB", name="철골보 평면", category=XicadCategory.steel, risk=XicadRisk.medium),
    XicadAlias(alias="D1", name="간단문 그리기", category=XicadCategory.door, risk=XicadRisk.medium),
    XicadAlias(alias="D2", name="문 그리기", category=XicadCategory.door, risk=XicadRisk.medium),
    XicadAlias(alias="D3", name="문 그리기", category=XicadCategory.door, risk=XicadRisk.medium),
    XicadAlias(alias="W1", name="간단창 그리기", category=XicadCategory.window, risk=XicadRisk.medium),
    XicadAlias(alias="W2", name="미서기창 그리기", category=XicadCategory.window, risk=XicadRisk.medium),
    XicadAlias(alias="W3", name="미서기창 그리기", category=XicadCategory.window, risk=XicadRisk.medium),
    XicadAlias(alias="WO", name="개구부 그리기", category=XicadCategory.window, risk=XicadRisk.medium),
    XicadAlias(alias="CW", name="커튼월 그리기", category=XicadCategory.window, risk=XicadRisk.medium),
    XicadAlias(alias="STP", name="계단 평면", category=XicadCategory.stair, risk=XicadRisk.medium),
    XicadAlias(alias="STC", name="계단 입면/단면", category=XicadCategory.stair, risk=XicadRisk.medium),
    XicadAlias(alias="ELV", name="엘리베이터", category=XicadCategory.elevator, risk=XicadRisk.medium),
    XicadAlias(alias="EPD", name="에스컬레이터 평면", category=XicadCategory.elevator, risk=XicadRisk.medium),
    XicadAlias(alias="EED", name="에스컬레이터 입면", category=XicadCategory.elevator, risk=XicadRisk.medium),
    XicadAlias(alias="PK", name="주차장 그리기", category=XicadCategory.parking, risk=XicadRisk.medium),
    XicadAlias(alias="INS", name="단열재 그리기", category=XicadCategory.insulation, risk=XicadRisk.medium),
    XicadAlias(alias="SCB", name="축척 막대", category=XicadCategory.annotation, risk=XicadRisk.low),
    XicadAlias(alias="PZ", name="부분 확대도", category=XicadCategory.annotation, risk=XicadRisk.low),
]


def infer_category(alias: str) -> XicadCategory:
    normalized = alias.strip().upper()
    for aliases, category in _CATEGORY_RULES:
        if normalized in aliases:
            return category
    return XicadCategory.unknown


class XicadAliasRegistry:
    """Registry for XiCAD aliases exposed to AI.

    This class is deliberately independent from config/xicad_commands.yaml so it
    can be tested without the full application.
    """

    def __init__(self, aliases: Iterable[XicadAlias] | None = None) -> None:
        self._items: dict[str, XicadAlias] = {}
        for item in aliases or []:
            self.add(item)

    def add(self, item: XicadAlias) -> None:
        self._items[item.alias] = item

    def get(self, alias: str) -> XicadAlias | None:
        return self._items.get(alias.strip().upper())

    def require(self, alias: str) -> XicadAlias:
        item = self.get(alias)
        if item is None:
            raise ValueError(f"XiCAD alias is not allowed or unknown: {alias!r}")
        return item

    def list(self) -> list[XicadAlias]:
        return sorted(self._items.values(), key=lambda item: item.alias)

    @classmethod
    def from_key_file(cls, path: str | Path) -> "XicadAliasRegistry":
        """Parse a XiCAD shortcut key file.

        The parser is intentionally tolerant because XiCAD key files may contain
        mixed Korean comments, spacing, and command formats.
        """
        registry = cls(_DEFAULT_ALIASES)
        key_path = Path(path)
        if not key_path.exists():
            return registry
        from src.integrations.xicad_command_catalog import read_text_korean
        text = read_text_korean(key_path)
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith(("#", ";", "//")):
                continue
            # Typical patterns can be:
            # WAL, *WAL
            # WAL : 벽 그리기
            # WAL=...
            match = re.match(r"^([A-Za-z][A-Za-z0-9]{0,8})\s*[,=:;\t ]+\s*(.*)$", stripped)
            if not match:
                continue
            alias = match.group(1).upper()
            rest = match.group(2).strip()
            if len(alias) > 10:
                continue
            category = infer_category(alias)
            existing = registry.get(alias)
            if existing:
                if rest and not existing.description:
                    existing.description = rest
                continue
            registry.add(
                XicadAlias(
                    alias=alias,
                    name=rest[:80],
                    category=category,
                    description=rest,
                    interactive_required=True,
                    risk=XicadRisk.medium,
                    raw={"source": str(key_path)},
                )
            )
        return registry


def default_xicad_registry() -> XicadAliasRegistry:
    return XicadAliasRegistry(_DEFAULT_ALIASES)
