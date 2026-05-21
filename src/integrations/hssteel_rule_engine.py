# -*- coding: utf-8 -*-
"""
HSSTEEL Rule Engine for structural steel CAD automation.
Parses hssteel.pgp aliases and indexes dwg structural blocks.
"""
from pathlib import Path
from typing import Any

class HSSteelRuleEngine:
    def __init__(self, base_dir: str = "C:\\cad\\HSSTEEL"):
        self.base_dir = Path(base_dir)
        self.support_dir = self.base_dir / "support"
        self.block_dir = self.base_dir / "block"
        
        self.aliases: dict[str, str] = {}
        self.blocks: list[str] = []
        self.is_loaded = False

    def load_all(self) -> None:
        """Loads both pgp shortcuts and drawing blocks."""
        self._load_aliases()
        self._load_blocks()
        self.is_loaded = True

    def _load_aliases(self) -> None:
        pgp_path = self.support_dir / "hssteel.pgp"
        if not pgp_path.exists():
            return
            
        try:
            with open(pgp_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except Exception:
            return

        for line in lines:
            line = line.strip()
            if not line or line.startswith(";"):
                continue
            if "," in line:
                parts = line.split(",", 1)
                alias = parts[0].strip().upper()
                cmd = parts[1].strip().lstrip("*").upper()
                if alias and cmd:
                    self.aliases[alias] = cmd

    def _load_blocks(self) -> None:
        if not self.block_dir.exists():
            return
            
        try:
            # Index all .dwg files as block references
            for f in self.block_dir.glob("*.dwg"):
                self.blocks.append(f.stem)
        except Exception:
            pass

    def get_aliases(self) -> dict[str, str]:
        return self.aliases

    def get_block_catalog(self) -> dict[str, Any]:
        categorized: dict[str, list[str]] = {
            "기성품": [],
            "weld": [],
            "table": [],
            "general": []
        }
        
        for b in self.blocks:
            up = b.upper()
            if "기성품" in b or "DK" in up:
                categorized["기성품"].append(b)
            elif "WELD" in up or "개선" in b:
                categorized["weld"].append(b)
            elif "TABLE" in up or "LIST" in up or "BOM" in up:
                categorized["table"].append(b)
            else:
                categorized["general"].append(b)
                
        return {
            "all_blocks": self.blocks,
            "categorized": categorized,
            "total_count": len(self.blocks)
        }
