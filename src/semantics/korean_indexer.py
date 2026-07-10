# -*- coding: utf-8 -*-
from __future__ import annotations

import re
import json
from pathlib import Path

# Choseung (Initial Consonants) in Korean
CHOSEUNG_LIST = [
    'ㄱ', 'ㄲ', 'ㄴ', 'ㄷ', 'ㄸ', 'ㄹ', 'ㅁ', 'ㅂ', 'ㅃ', 'ㅅ', 
    'ㅆ', 'ㅇ', 'ㅈ', 'ㅉ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ'
]

def disassemble_choseung(text: str) -> str:
    """Extract initial consonants (choseung) from Korean text for smart search."""
    result = []
    for char in text:
        code = ord(char)
        # Check if the character is in the Korean Syllables range (가 ~ 힣)
        if 0xAC00 <= code <= 0xD7A3:
            syl_index = code - 0xAC00
            choseung_index = (syl_index // 28) // 21
            result.append(CHOSEUNG_LIST[choseung_index])
        else:
            result.append(char)
    return "".join(result)


class KoreanMaterialIndexer:
    """Index and search cataloged material text files from ZWCAD scans."""
    
    def __init__(self, raw_file_path: str | Path):
        self.raw_file_path = Path(raw_file_path)
        self.materials: list[str] = []
        self.indexed_materials: list[dict[str, str]] = []
        self.sources_map: dict[str, list[str]] = {}
        self.load_and_index()

    def clean_cad_text(self, text: str) -> str:
        """Clean MTEXT formatting codes and raw CAD prefixes, including coordinates and handles."""
        # 1. Strip ZWCAD dump format: <Handle> <Layer> <Type> <X> <Y> <Z> <Rot> <ActualText>
        # Supports spaces in layer names (e.g. "Layer 1") via non-greedy (.+?) matching
        pattern = r"^[0-9A-Fa-f]{3,8}\s+(.+?)\s+(TEXT|MTEXT|LEADER|INSERT)\s+[0-9.-]+\s+[0-9.-]+\s+[0-9.-]+\s+[0-9.-]+\s+(.*)$"
        match = re.match(pattern, text)
        if match:
            text = match.group(3)

        # 2. Remove "Layer: XXX | Text: " prefix
        text = re.sub(r"^Layer:\s*[^\s|]+\s*\|\s*Text:\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"^Text:\s*", "", text, flags=re.IGNORECASE)

        # 3. Remove common MTEXT formatting braces and backslashes
        text = re.sub(r"\\[Aa][0-9];", "", text)
        text = re.sub(r"\\[Ff][^;]+;", "", text)
        text = re.sub(r"\\[Cc][0-9]+;", "", text)
        text = re.sub(r"\\[Hh][0-9.]+;", "", text)
        text = re.sub(r"\\[Ww][0-9.]+;", "", text)
        text = re.sub(r"\\[Pp]", " ", text)
        text = re.sub(r"[{}\\]", "", text)

        # 4. Clean whitespaces and strip leading colons
        text = re.sub(r"\s+", " ", text)
        text = text.lstrip(":")
        return text.strip()

    def load_and_index(self) -> None:
        """Load drawing materials and generate indices for choseung and substrings."""
        if not self.raw_file_path.exists():
            # Fallback to an empty list if file doesn't exist
            self.materials = []
            return
            
        unique_materials = set()
        
        # Try multiple encodings for robustness (prioritizing CP949 for native dumps)
        encodings = ['cp949', 'utf-8', 'utf-8-sig', 'euc-kr', 'latin1']
        content = ""
        
        for enc in encodings:
            try:
                with open(self.raw_file_path, 'r', encoding=enc) as f:
                    content = f.read()
                break
            except Exception:
                continue
                
        if not content:
            return
            
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("==="):
                continue
                
            clean_text = self.clean_cad_text(line)
            # Filter out non-material text or structural headers
            if clean_text and len(clean_text) > 2:
                # Avoid inserting duplicates
                unique_materials.add(clean_text)

        self.materials = sorted(list(unique_materials))
        
        # Generate indexing objects
        self.indexed_materials = []
        for mat in self.materials:
            self.indexed_materials.append({
                "original": mat,
                "choseung": disassemble_choseung(mat).lower(),
                "lower": mat.lower()
            })

        # Load sources mapping if it exists
        sources_path = self.raw_file_path.parent / "oriental_materials_sources.json"
        if sources_path.exists():
            try:
                with open(sources_path, 'r', encoding='utf-8') as f_json:
                    self.sources_map = json.load(f_json)
            except Exception:
                self.sources_map = {}

    def search(self, query: str) -> list[str]:
        """Search materials using full text match, choseung match, or substring search."""
        if not query:
            return self.materials
            
        query = query.strip()
        query_choseung = disassemble_choseung(query).lower()
        query_lower = query.lower()
        
        results: list[str] = []
        
        # Determine if query is choseung-only (e.g. "ㄱㄹㅅㅇ", "ㅍㄴ")
        is_choseung_only = all(char in CHOSEUNG_LIST or char.isspace() or char.isdigit() for char in query)
        
        for item in self.indexed_materials:
            if is_choseung_only:
                # Choseung matching (starts with or contains)
                if query_choseung in item["choseung"]:
                    results.append(item["original"])
            else:
                # Standard substring search
                if query_lower in item["lower"]:
                    results.append(item["original"])
                    
        return results

    def get_sources(self, original_text: str) -> list[str]:
        """Return the list of source drawing/file names for a given material note."""
        return self.sources_map.get(original_text, ["Unknown Source"])
