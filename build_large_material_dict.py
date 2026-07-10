# -*- coding: utf-8 -*-
from __future__ import annotations

import re
import json
import sqlite3
from pathlib import Path

# Paths to all exported CAD note text files
TARGET_FILES = [
    Path("oriental_materials.txt"),
    Path("outputs/active_hwamok_698_14/texts_lisp_export.txt"),
    Path("outputs/active_hwamok_698_14_roof_removed/texts_before_roof_removed.txt"),
    Path("outputs/oda_hwamok_0526/reference_pdf_text/hwamok_arch_0526_all.txt"),
    Path("outputs/oda_hwamok_0526/reference_pdf_text/smlab_arch_struct_all.txt"),
    Path("outputs/oda_hwamok_0526/reference_pdf_text/smlab_construction_drawings.txt"),
    Path("outputs/oda_hwamok_0526/reference_pdf_text/smlab_office_all.txt"),
]

DB_PATH = Path("outputs/oda_hwamok_0526/analysis/oda_dxf_index.sqlite")
SOURCE_MAP_PATH = Path("oriental_materials_sources.json")

def translate_z_to_g_drive(path_str: str) -> str:
    """Automatically convert old Z:\\ Google Drive prefixes into G:\\ for robust cross-machine references."""
    if not path_str:
        return ""
        
    # Replace Z:\ or Z:/ with G:\ or G:/
    # Also handles Z:\\ or z:\\
    path_str = re.sub(r"^[Zz]:\\", r"G:\\", path_str)
    path_str = re.sub(r"^[Zz]:/", r"G:/", path_str)
    return path_str

def clean_cad_formatting(text: str) -> str:
    """Strip coordinates, handles, layers, MTEXT overrides, and keep ONLY the raw note text."""
    # 1. Advanced Non-Greedy regex pattern to handle whitespace-containing layers (e.g. "Layer 1")
    pattern = r"^[0-9A-Fa-f]{3,8}\s+(.+?)\s+(TEXT|MTEXT|LEADER|INSERT)\s+[0-9.-]+\s+[0-9.-]+\s+[0-9.-]+\s+[0-9.-]+\s+(.*)$"
    match = re.match(pattern, text)
    if match:
        text = match.group(3)

    # 2. Remove CAD Layer text extraction headers
    text = re.sub(r"^Layer:\s*[^\s|]+\s*\|\s*Text:\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^Text:\s*", "", text, flags=re.IGNORECASE)
    
    # 3. Clean common AutoCAD MTEXT code blocks
    text = re.sub(r"\\[Aa][0-9];", "", text)
    text = re.sub(r"\\[Ff][^;]+;", "", text)
    text = re.sub(r"\\[Cc][0-9]+;", "", text)
    text = re.sub(r"\\[Hh][0-9.]+;", "", text)
    text = re.sub(r"\\[Ww][0-9.]+;", "", text)
    text = re.sub(r"\\[Pp]", " ", text)
    text = re.sub(r"[{}\\]", "", text)
    
    # Clean multiple spaces and colon prefixes
    text = re.sub(r"\s+", " ", text)
    text = text.lstrip(":")
    return text.strip()

def is_valid_construction_note(text: str) -> bool:
    """Filter out CAD noise like pure coordinates, tiny numbers, or standard short symbols."""
    if len(text) < 4:
        return False
    if re.match(r"^[0-9.,\s]+$", text):
        return False
    if text.upper() in {"TXT", "TEXT", "MTEXT", "LINE", "NULL", "NONE"}:
        return False
    if re.match(r"^[^a-zA-Z0-9가-힣]+$", text):
        return False
        
    has_korean = bool(re.search(r"[가-힣]", text))
    has_specs = bool(re.search(r"\b(THK|T[0-9]|H-[0-9]|D[0-9]|W[0-9]|PL|SUS|CON|GL)\b", text, re.IGNORECASE))
    
    return has_korean or has_specs

def merge_and_build_dictionary():
    print("=== Starting Large Material Dictionary Construction ===")
    all_notes = set()
    note_sources: dict[str, set[str]] = {}
    
    def add_to_catalog(clean_note: str, src_path_str: str):
        all_notes.add(clean_note)
        if clean_note not in note_sources:
            note_sources[clean_note] = set()
        
        # Translate old Z: Google Drive paths to current G: Drive paths dynamically
        corrected_src = translate_z_to_g_drive(src_path_str)
        note_sources[clean_note].add(corrected_src)

    # --- PHASE 1: Query pre-indexed SQLite Database ---
    if DB_PATH.exists():
        print(f"\nProcessing pre-indexed database: {DB_PATH}")
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT t.text, e.source 
                FROM texts t 
                LEFT JOIN entities e ON t.handle = e.handle;
            """)
            texts_rows = cursor.fetchall()
            db_added = 0
            for row in texts_rows:
                if row[0]:
                    cleaned = clean_cad_formatting(row[0])
                    if is_valid_construction_note(cleaned):
                        src = row[1] or "oda_dxf_index.sqlite"
                        add_to_catalog(cleaned, src)
                        db_added += 1
            print(f"  Added {db_added} notes from texts database table.")
            
            cursor.execute("SELECT text, source FROM entities WHERE text IS NOT NULL;")
            entities_rows = cursor.fetchall()
            ent_added = 0
            for row in entities_rows:
                if row[0]:
                    cleaned = clean_cad_formatting(row[0])
                    if is_valid_construction_note(cleaned):
                        src = row[1] or "oda_dxf_index.sqlite"
                        add_to_catalog(cleaned, src)
                        ent_added += 1
            print(f"  Added {ent_added} notes from entities database table.")
            
            conn.close()
        except Exception as e:
            print(f"  Database parsing warning: {e}")
    else:
        print(f"\nDatabase not found at: {DB_PATH}")

    # --- PHASE 2: Scan exported text files ---
    print("\nScanning raw text logs...")
    encodings = ['cp949', 'utf-8', 'utf-8-sig', 'euc-kr', 'latin1']
    
    for file_path in TARGET_FILES:
        if not file_path.exists():
            print(f"Skipping (not found): {file_path}")
            continue
            
        print(f"Scanning: {file_path} ...")
        content = ""
        
        for enc in encodings:
            try:
                with open(file_path, 'r', encoding=enc) as f:
                    content = f.read()
                break
            except Exception:
                continue
                
        if not content:
            continue
            
        lines = content.splitlines()
        added_count = 0
        
        for line in lines:
            line_str = line.strip()
            if not line_str or line_str.startswith("==="):
                continue
                
            cleaned = clean_cad_formatting(line_str)
            if is_valid_construction_note(cleaned):
                # Map to G-drive corrected paths if files exist or default to file_path name
                add_to_catalog(cleaned, str(file_path))
                added_count += 1
                
        print(f"  Added {added_count} candidate notes from {file_path.name}")

    # Sort dictionary alphabetically
    sorted_notes = sorted(list(all_notes), key=lambda x: (not re.match(r'^[가-힣]', x), x))
    
    # Save the giant dictionary
    output_path = Path("oriental_materials_utf8.txt")
    with open(output_path, 'w', encoding='utf-8') as f_out:
        f_out.write("=== HS-CAD LARGE INTEGRATED CONSTRUCTION NOTE DICTIONARY ===\n")
        for note in sorted_notes:
            f_out.write(f"Layer: HS-CAD-AUTO-GEN | Text: {note}\n")
            
    # Serialize note sources
    serialized_sources = {k: sorted(list(v)) for k, v in note_sources.items()}
    with open(SOURCE_MAP_PATH, 'w', encoding='utf-8') as f_json:
        json.dump(serialized_sources, f_json, indent=2, ensure_ascii=False)
        
    print("\n=== Build Complete: oriental_materials_utf8.txt ===")
    print(f"Total high-fidelity construction notes indexed: {len(sorted_notes)} items.")
    print(f"Source mapping compiled to: {SOURCE_MAP_PATH}")

if __name__ == '__main__':
    merge_and_build_dictionary()
