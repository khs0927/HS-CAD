from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from src.integrations.xicad_rule_engine import TEXT_ENCODINGS, read_text_korean


@dataclass
class ArchiOfficeCommand:
    alias: str
    command: str
    description: str = ""
    source_file: str = ""


@dataclass
class ArchiOfficeSteelSpec:
    source_file: str
    category: str
    name: str
    values: list[float] = field(default_factory=list)
    raw: str = ""


@dataclass
class ArchiOfficeBlockEntry:
    path: str
    filename: str
    category: str
    extension: str = ".dwg"


@dataclass
class ArchiOfficeRules:
    archioffice_root: str
    onekey_commands: list[ArchiOfficeCommand] = field(default_factory=list)
    xpress_aliases: list[ArchiOfficeCommand] = field(default_factory=list)
    steel_specs: list[ArchiOfficeSteelSpec] = field(default_factory=list)
    room_names: list[str] = field(default_factory=list)
    block_catalog: list[ArchiOfficeBlockEntry] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _numbers_from_text(text: str) -> list[float]:
    values: list[float] = []
    for token in re.findall(r"[-+]?\d+(?:\.\d+)?", text):
        try:
            values.append(abs(float(token)))
        except ValueError:
            pass
    return values


def _read_lines(path: str | Path) -> list[str]:
    p = Path(path)
    if not p.exists():
        return []
    for enc in TEXT_ENCODINGS:
        try:
            return p.read_text(encoding=enc).splitlines()
        except Exception:
            continue
    return []


def parse_onekey_lisp(path: str | Path) -> list[ArchiOfficeCommand]:
    p = Path(path)
    commands: list[ArchiOfficeCommand] = []
    for line in _read_lines(p):
        raw = line.strip()
        if not raw:
            continue
        comment_match = re.search(r"C:([A-Za-z0-9_]+)\s+(.+)$", raw)
        if raw.startswith(";;;") and comment_match:
            alias = comment_match.group(1).upper()
            commands.append(ArchiOfficeCommand(alias, f"C:{alias}", comment_match.group(2).strip(), str(p)))
            continue
        defun_match = re.search(r"\(defun\s+C:([A-Za-z0-9_]+)", raw, re.IGNORECASE)
        if defun_match:
            alias = defun_match.group(1).upper()
            commands.append(ArchiOfficeCommand(alias, f"C:{alias}", "ArchiOffice LISP command", str(p)))
    return commands


def parse_xpress_pgp(path: str | Path) -> list[ArchiOfficeCommand]:
    p = Path(path)
    aliases: list[ArchiOfficeCommand] = []
    for line in _read_lines(p):
        raw = line.strip()
        if not raw or raw.startswith((";", "#")):
            continue
        match = re.match(r"^([^,]+),\s*\*?(.+)$", raw)
        if match:
            alias = match.group(1).strip().upper()
            command = match.group(2).strip().upper()
            aliases.append(ArchiOfficeCommand(alias, command, "XPress command alias", str(p)))
    return aliases


def parse_shape_steel(path: str | Path) -> list[ArchiOfficeSteelSpec]:
    p = Path(path)
    specs: list[ArchiOfficeSteelSpec] = []
    current_category = "steel_table"
    for line in _read_lines(p):
        raw = line.strip()
        if not raw or raw.startswith((";", "#")):
            continue
        if raw.startswith("*"):
            current_category = raw.strip("* ").strip() or "steel_table"
            continue
        value_text = raw.split(",", 1)[1] if "," in raw else raw
        values = _numbers_from_text(value_text)
        if not values:
            continue
        name = raw.split(",", 1)[0].split(None, 1)[0].strip()
        if not name:
            name = f"{current_category}-{len(specs) + 1}"
        specs.append(ArchiOfficeSteelSpec(str(p), current_category, name, values, raw))
    return specs


def parse_room_names(path: str | Path) -> list[str]:
    names: list[str] = []
    for line in _read_lines(path):
        raw = line.strip()
        if raw and not raw.startswith((";", "#")):
            names.append(raw)
    return names


def parse_archioffice_block_catalog(root: str | Path) -> list[ArchiOfficeBlockEntry]:
    base = Path(root)
    entries: list[ArchiOfficeBlockEntry] = []
    if not base.exists():
        return entries
    for path in sorted(base.rglob("*.dwg")):
        try:
            rel = path.relative_to(base)
            category = rel.parts[0] if len(rel.parts) > 1 else path.stem.split("_")[0]
        except Exception:
            category = path.stem.split("_")[0]
        entries.append(ArchiOfficeBlockEntry(str(path), path.name, category or "Uncategorized", path.suffix.lower()))
    return entries


class ArchiOfficeRuleEngine:
    def __init__(self, archioffice_root: str | Path = "C:/Program Files/ArchiOfficeZW2024") -> None:
        self.root = Path(archioffice_root)

    @property
    def inercad_dir(self) -> Path:
        return self.root / "InerCAD"

    @property
    def xpress_dir(self) -> Path:
        return self.root / "XPress"

    @property
    def library_dir(self) -> Path:
        return self.inercad_dir / "Library"

    def load_all(self) -> ArchiOfficeRules:
        rules = ArchiOfficeRules(archioffice_root=str(self.root))
        if not self.root.exists():
            rules.warnings.append(f"ArchiOffice root missing: {self.root}")
            return rules

        rules.onekey_commands = parse_onekey_lisp(self.inercad_dir / "onekey.lsp")
        if not rules.onekey_commands:
            rules.warnings.append("onekey.lsp not found or no commands parsed")

        rules.xpress_aliases = parse_xpress_pgp(self.xpress_dir / "XPRESS.PGP")
        if not rules.xpress_aliases:
            rules.warnings.append("XPRESS.PGP not found or no aliases parsed")

        rules.steel_specs = parse_shape_steel(self.inercad_dir / "ShapeSteel.txt")
        if not rules.steel_specs:
            rules.warnings.append("ShapeSteel.txt not found or no steel specs parsed")

        room_candidates = [self.inercad_dir / "ROOMNAME.TXT", self.xpress_dir / "ROOMNAME.TXT"]
        for candidate in room_candidates:
            if candidate.exists():
                rules.room_names = parse_room_names(candidate)
                break
        if not rules.room_names:
            rules.warnings.append("ROOMNAME.TXT not found or no room names parsed")

        rules.block_catalog = parse_archioffice_block_catalog(self.library_dir)
        if not rules.block_catalog:
            rules.warnings.append("no ArchiOffice DWG library blocks parsed")
        return rules

    def summarize(self, rules: ArchiOfficeRules | None = None) -> dict[str, Any]:
        rules = rules or self.load_all()
        steel_by_category = Counter(spec.category for spec in rules.steel_specs)
        blocks_by_category = Counter(entry.category for entry in rules.block_catalog)
        return {
            "archioffice_root": rules.archioffice_root,
            "onekey_commands": len(rules.onekey_commands),
            "xpress_aliases": len(rules.xpress_aliases),
            "steel_specs": len(rules.steel_specs),
            "steel_categories": dict(steel_by_category),
            "room_names": len(rules.room_names),
            "block_catalog": len(rules.block_catalog),
            "block_categories": len(blocks_by_category),
            "warnings": rules.warnings,
        }

    def export_rules_to_json(self, path: str | Path, rules: ArchiOfficeRules | None = None) -> None:
        rules = rules or self.load_all()
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(rules.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    def generate_ai_drafting_prompt(self, rules: ArchiOfficeRules | None = None, limit: int = 30) -> str:
        rules = rules or self.load_all()
        summary = self.summarize(rules)
        lines = [
            "[SYSTEM DRAFTING CONSTRAINTS: ARCHIOFFICE RULE ENGINE]",
            "",
            f"ArchiOffice root: {summary['archioffice_root']}",
            f"OneKey commands parsed: {summary['onekey_commands']}",
            f"XPress aliases parsed: {summary['xpress_aliases']}",
            f"Steel specs parsed: {summary['steel_specs']}",
            f"Room names parsed: {summary['room_names']}",
            f"Library blocks indexed: {summary['block_catalog']}",
            "",
            "Rules:",
            "- Keep ArchiOffice data isolated from XiCAD rule namespaces.",
            "- Use ShapeSteel.txt as a steel-section constraint source when present.",
            "- Use Library DWG paths as insertable block candidates, not generated artifacts.",
            "- Preserve existing office DWG layers unless explicit remapping is requested.",
            "",
            "Sample commands:",
        ]
        for item in rules.onekey_commands[:limit]:
            desc = f" - {item.description}" if item.description else ""
            lines.append(f"- {item.alias} -> {item.command}{desc}")
        lines.append("")
        lines.append("Sample steel categories:")
        for category, count in Counter(spec.category for spec in rules.steel_specs).most_common(limit):
            lines.append(f"- {category}: {count}")
        lines.append("")
        lines.append("Sample block categories:")
        for category, count in Counter(entry.category for entry in rules.block_catalog).most_common(limit):
            lines.append(f"- {category}: {count}")
        return "\n".join(lines)


def load_archioffice_rules(archioffice_root: str | Path = "C:/Program Files/ArchiOfficeZW2024") -> ArchiOfficeRules:
    return ArchiOfficeRuleEngine(archioffice_root).load_all()
