# -*- coding: utf-8 -*-
import sqlite3
import json
import re
from pathlib import Path

def inspect_arch_data():
    db_path = Path("G:/내 드라이브/#김호삼/1. 대구동. 주택설계,감리/Databases/revision_4_0.db")
    print(f"\n--- Checking revision DB: {db_path} ---")
    if db_path.exists():
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            print(f"  Tables: {tables}")
            
            for table in tables:
                tname = table[0]
                cursor.execute(f"SELECT COUNT(*) FROM {tname};")
                count = cursor.fetchone()[0]
                print(f"    Table {tname}: {count} rows")
                
                # Show samples
                if count > 0:
                    cursor.execute(f"SELECT * FROM {tname} LIMIT 5;")
                    print("      Samples:")
                    for row in cursor.fetchall():
                        print(f"        {str(row)[:120]}")
            conn.close()
        except Exception as e:
            print(f"  Error: {e}")
            
    # Check master symbol index json for Z: references
    json_path = Path("C:/CODE/CAD/HS-CAD/generated/xicad_symbols_staging/master_xicad_symbol_library_index.json")
    print(f"\n--- Checking master symbol library index JSON: {json_path} ---")
    if json_path.exists():
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(f"  JSON loaded successfully. Keys: {list(data.keys())[:10]}")
            # Check Z: references count
            data_str = json.dumps(data, ensure_ascii=False)
            z_refs = len(re.findall(r"Z:\\", data_str, re.IGNORECASE))
            print(f"  Found {z_refs} references to 'Z:\\' drive in symbol library index.")
            if z_refs > 0:
                print("  Sample matching nodes in symbol index:")
                # print some items
                for idx, (k, v) in enumerate(list(data.items())[:5]):
                    print(f"    Item {idx+1}: {k} -> {str(v)[:150]}...")
        except Exception as e:
            print(f"  Error: {e}")

if __name__ == '__main__':
    inspect_arch_data()
