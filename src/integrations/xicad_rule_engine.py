from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

TEXT_ENCODINGS = ("utf-8-sig", "cp949", "euc-kr", "utf-8", "latin1")

@dataclass
class ShortkeyEntry:
    alias: str
    function: str
    description: str = ""
    source_file: str = ""

@dataclass
class PgpAlias:
    alias: str
    command: str
    source_file: str = ""

@dataclass
class SteelSpec:
    source_file: str
    category: str
    name: str
    values: list[float] = field(default_factory=list)
    raw: str = ""

@dataclass
class BlockCatalogEntry:
    path: str
    filename: str
    category: str
    prefix: str
    extension: str = ".dwg"

@dataclass
class ProtectedLispFile:
    path: str
    filename: str
    protected: bool
    signature: str = ""

@dataclass
class WallStyle:
    name: str
    total_thickness: float | None = None
    offsets: list[float] = field(default_factory=list)
    layers: list[str] = field(default_factory=list)
    raw: str = ""

@dataclass
class BlockLayerRule:
    pattern: str
    layer: str
    color: str | int | None = None
    linetype: str | None = None
    raw: str = ""

@dataclass
class XiCadRules:
    xicad_root: str
    shortkeys: list[ShortkeyEntry] = field(default_factory=list)
    pgp_aliases: list[PgpAlias] = field(default_factory=list)
    steel_specs: list[SteelSpec] = field(default_factory=list)
    block_catalog: list[BlockCatalogEntry] = field(default_factory=list)
    protected_lisp_files: list[ProtectedLispFile] = field(default_factory=list)
    wall_styles: list[WallStyle] = field(default_factory=list)
    block_layer_rules: list[BlockLayerRule] = field(default_factory=list)
    config_values: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def read_text_korean(path: str | Path) -> tuple[str, str]:
    p = Path(path)
    last_error: Exception | None = None
    for enc in TEXT_ENCODINGS:
        try:
            return p.read_text(encoding=enc), enc
        except Exception as exc:
            last_error = exc
    raise UnicodeError(f"failed to decode {p}: {last_error}")


def _numbers_from_text(text: str) -> list[float]:
    out: list[float] = []
    for token in re.findall(r"[-+]?\d+(?:\.\d+)?", text):
        try:
            out.append(float(token))
        except ValueError:
            pass
    return out


def is_binary_or_protected_lisp(path: str | Path) -> ProtectedLispFile:
    p = Path(path)
    try:
        raw = p.read_bytes()[:256]
    except Exception:
        raw = b""
    upper = raw.upper()
    protected = b"PROTECTED" in upper or b"BWF" in upper or b"FAS" in upper or b"ZELX" in upper
    signature = raw[:80].decode("latin1", errors="ignore")
    return ProtectedLispFile(path=str(p), filename=p.name, protected=protected, signature=signature)


def parse_shortkeys(path: str | Path) -> list[ShortkeyEntry]:
    p = Path(path)
    if not p.exists():
        return []
    text, _ = read_text_korean(p)
    entries: list[ShortkeyEntry] = []
    for line in text.splitlines():
        raw = line.strip()
        if not raw or raw.startswith((";", "#")) or "," not in raw:
            continue
        parts = [x.strip() for x in raw.split(",")]
        if len(parts) >= 2 and parts[0] and parts[1]:
            entries.append(ShortkeyEntry(parts[0], parts[1], ",".join(parts[2:]).strip(), str(p)))
    return entries


def parse_pgp_aliases(path: str | Path) -> list[PgpAlias]:
    p = Path(path)
    if not p.exists():
        return []
    text, _ = read_text_korean(p)
    entries: list[PgpAlias] = []
    for line in text.splitlines():
        raw = line.strip()
        if not raw or raw.startswith((";", "#")):
            continue
        m = re.match(r"^([^,]+),\s*\*?(.+)$", raw)
        if m:
            entries.append(PgpAlias(m.group(1).strip(), m.group(2).strip(), str(p)))
    return entries


def _steel_category_from_filename(path: Path) -> str:
    name = path.stem.lower()
    if "hbe" in name or "h_beam" in name or "hbeam" in name:
        return "h_beam"
    if "sqp" in name or "square" in name or "pipe" in name:
        return "square_pipe"
    if "ang" in name or "angle" in name:
        return "angle"
    if "chn" in name or "channel" in name:
        return "channel"
    if "ibe" in name or "ipe" in name:
        return "i_beam"
    return "steel_table"


def parse_dat_file(path: str | Path) -> list[SteelSpec]:
    p = Path(path)
    if not p.exists():
        return []
    text, _ = read_text_korean(p)
    specs: list[SteelSpec] = []
    category = _steel_category_from_filename(p)
    for line in text.splitlines():
        raw = line.strip()
        if not raw or raw.startswith((";", "#")):
            continue
        # Steel names often use hyphens as separators, e.g. ``L-50x50x6``.
        # Prefer the comma-separated value columns when present so that the
        # profile prefix is not interpreted as a negative dimension.
        value_text = raw.split(",", 1)[1] if "," in raw else raw
        nums = [abs(n) for n in _numbers_from_text(value_text)]
        if nums:
            name = raw.split(",")[0].strip() if "," in raw else raw.split()[0].strip()
            specs.append(SteelSpec(str(p), category, name, nums, raw))
    return specs


def parse_dat_files(lisp_dir: str | Path) -> list[SteelSpec]:
    root = Path(lisp_dir)
    specs: list[SteelSpec] = []
    if root.exists():
        for path in sorted(root.rglob("*.dat")):
            specs.extend(parse_dat_file(path))
    return specs


def parse_block_catalog(lib_dir: str | Path) -> list[BlockCatalogEntry]:
    root = Path(lib_dir)
    entries: list[BlockCatalogEntry] = []
    if not root.exists():
        return entries
    for path in sorted(root.rglob("*.dwg")):
        try:
            rel = path.relative_to(root)
            folder = rel.parts[0] if len(rel.parts) > 1 else ""
        except Exception:
            folder = ""
        stem = path.stem
        prefix = stem.split("_")[0] if "_" in stem else stem.split("-")[0]
        entries.append(BlockCatalogEntry(str(path), path.name, folder or prefix or "Uncategorized", prefix, path.suffix.lower()))
    return entries


def parse_wall_styles(path: str | Path) -> list[WallStyle]:
    p = Path(path)
    if not p.exists():
        return []
    text, _ = read_text_korean(p)
    styles: list[WallStyle] = []
    for line in text.splitlines():
        raw = line.strip()
        if not raw or raw.startswith((";", "#")):
            continue
        nums = _numbers_from_text(raw)
        layers = re.findall(r"\b[A-Za-z][A-Za-z0-9_-]{1,}\b", raw)
        name = raw.split(",")[0].strip() if "," in raw else raw[:48]
        total = max(nums) - min(nums) if len(nums) >= 2 else (nums[0] if nums else None)
        styles.append(WallStyle(name, total, nums, layers, raw))
    return styles


def parse_block_layer_rules(path: str | Path) -> list[BlockLayerRule]:
    p = Path(path)
    if not p.exists():
        return []
    text, _ = read_text_korean(p)
    rules: list[BlockLayerRule] = []
    for line in text.splitlines():
        raw = line.strip()
        if not raw or raw.startswith((";", "#")):
            continue
        parts = [x.strip() for x in re.split(r"[,|\t]", raw) if x.strip()]
        if len(parts) >= 2:
            rules.append(BlockLayerRule(parts[0], parts[1], parts[2] if len(parts) > 2 else None, parts[3] if len(parts) > 3 else None, raw))
    return rules


def parse_config_values(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {}
    text, _ = read_text_korean(p)
    values: dict[str, Any] = {}
    for line in text.splitlines():
        raw = line.strip()
        if not raw or raw.startswith((";", "#")):
            continue
        if "=" in raw:
            k, v = raw.split("=", 1)
            values[k.strip()] = v.strip()
        elif "," in raw:
            parts = [x.strip() for x in raw.split(",")]
            if len(parts) >= 2:
                values[parts[0]] = parts[1:]
    return values


class XiCadRuleEngine:
    def __init__(self, xicad_root: str | Path = "C:/xicad") -> None:
        self.root = Path(xicad_root)

    @property
    def lisp_dir(self) -> Path:
        return self.root / "Lisp"

    @property
    def xilib_dir(self) -> Path:
        return self.root / "xiLib"

    @property
    def zwcad_dir(self) -> Path:
        return self.root / "_ZWCad"

    @property
    def lib_dir(self) -> Path:
        return self.root / "Lib"

    def load_all(self) -> XiCadRules:
        rules = XiCadRules(xicad_root=str(self.root))
        if not self.root.exists():
            rules.warnings.append(f"XiCAD root missing: {self.root}")
            return rules

        for candidate in [self.xilib_dir / "xiShortkey.key", self.lisp_dir / "xiShortkey.key", self.root / "xiShortkey.key"]:
            if candidate.exists():
                rules.shortkeys = parse_shortkeys(candidate)
                break
        if not rules.shortkeys:
            rules.warnings.append("xiShortkey.key not found or no entries parsed")

        for candidate in [self.zwcad_dir / "zwcad.pgp", self.root / "zwcad.pgp"]:
            if candidate.exists():
                rules.pgp_aliases = parse_pgp_aliases(candidate)
                break
        if not rules.pgp_aliases:
            rules.warnings.append("zwcad.pgp not found or no aliases parsed")

        rules.steel_specs = parse_dat_files(self.lisp_dir)
        if not rules.steel_specs:
            rules.warnings.append("no .dat steel specs parsed")

        rules.block_catalog = parse_block_catalog(self.lib_dir)
        if not rules.block_catalog:
            rules.warnings.append("no DWG library blocks parsed")

        if self.lisp_dir.exists():
            for path in sorted(self.lisp_dir.rglob("*.des")):
                rules.protected_lisp_files.append(is_binary_or_protected_lisp(path))

        rules.wall_styles = parse_wall_styles(self.xilib_dir / "xiDrawWall.txt")
        rules.block_layer_rules = parse_block_layer_rules(self.xilib_dir / "xiBlkLayerSet.txt")
        rules.config_values = parse_config_values(self.xilib_dir / "xiConfig.cfg")
        return rules

    def summarize(self, rules: XiCadRules | None = None) -> dict[str, Any]:
        rules = rules or self.load_all()
        steel_by_category = Counter(spec.category for spec in rules.steel_specs)
        blocks_by_category = Counter(entry.category for entry in rules.block_catalog)
        protected_count = sum(1 for item in rules.protected_lisp_files if item.protected)
        return {
            "xicad_root": rules.xicad_root,
            "shortkeys": len(rules.shortkeys),
            "pgp_aliases": len(rules.pgp_aliases),
            "steel_specs": len(rules.steel_specs),
            "steel_categories": dict(steel_by_category),
            "block_catalog": len(rules.block_catalog),
            "block_categories": len(blocks_by_category),
            "protected_lisp_files": protected_count,
            "wall_styles": len(rules.wall_styles),
            "block_layer_rules": len(rules.block_layer_rules),
            "config_values": len(rules.config_values),
            "warnings": rules.warnings,
        }

    def export_rules_to_json(self, path: str | Path, rules: XiCadRules | None = None) -> None:
        rules = rules or self.load_all()
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(rules.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    def generate_ai_drafting_prompt(self, rules: XiCadRules | None = None, limit: int = 30) -> str:
        rules = rules or self.load_all()
        summary = self.summarize(rules)
        lines = [
            "[SYSTEM DRAFTING CONSTRAINTS: XICAD RULE ENGINE V2]",
            "",
            f"XiCAD root: {summary['xicad_root']}",
            f"Shortkeys parsed: {summary['shortkeys']}",
            f"PGP aliases parsed: {summary['pgp_aliases']}",
            f"Steel specs parsed: {summary['steel_specs']}",
            f"Library blocks indexed: {summary['block_catalog']}",
            f"Protected LISP files isolated: {summary['protected_lisp_files']}",
            "",
            "Rules:",
            "- Treat protected .des/.fas/.zelx files as non-parseable binary assets.",
            "- Use parsed xiShortkey aliases to connect user CAD commands to XiCAD LISP functions.",
            "- Use .dat steel tables as real section-size constraints.",
            "- Use Lib/ DWG catalog entries as insertable block candidates, not runtime artifacts.",
            "- Preserve existing office DWG layers unless explicit remapping is requested.",
            "",
            "Sample shortkeys:",
        ]
        for entry in rules.shortkeys[:limit]:
            desc = f" - {entry.description}" if entry.description else ""
            lines.append(f"- {entry.alias} -> {entry.function}{desc}")
        lines.append("")
        lines.append("Sample steel categories:")
        for category, count in Counter(spec.category for spec in rules.steel_specs).most_common(limit):
            lines.append(f"- {category}: {count}")
        lines.append("")
        lines.append("Sample block categories:")
        for category, count in Counter(entry.category for entry in rules.block_catalog).most_common(limit):
            lines.append(f"- {category}: {count}")
        return "\n".join(lines)


def load_xicad_rules(xicad_root: str | Path = "C:/xicad") -> XiCadRules:
    return XiCadRuleEngine(xicad_root).load_all()


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Extract parseable XiCAD drafting rules into JSON/Markdown prompt.")
    parser.add_argument("--xicad-root", default="C:/xicad")
    parser.add_argument("--out-json", default="outputs/xicad_extracted_rules.json")
    parser.add_argument("--out-prompt", default="outputs/xicad_drafting_prompt.md")
    args = parser.parse_args()
    engine = XiCadRuleEngine(args.xicad_root)
    rules = engine.load_all()
    engine.export_rules_to_json(args.out_json, rules)
    prompt = engine.generate_ai_drafting_prompt(rules)
    out_prompt = Path(args.out_prompt)
    out_prompt.parent.mkdir(parents=True, exist_ok=True)
    out_prompt.write_text(prompt, encoding="utf-8")
    print(json.dumps(engine.summarize(rules), ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
