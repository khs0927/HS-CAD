import os
from pathlib import Path

root_path = Path("Z:/내 드라이브/#웹하드")
print(f"Scanning {root_path}...")

dwg_count = 0
dxf_count = 0
other_count = 0
total_count = 0

try:
    for root, dirs, files in os.walk(root_path):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext == '.dwg':
                dwg_count += 1
            elif ext == '.dxf':
                dxf_count += 1
            else:
                other_count += 1
            total_count += 1
except Exception as e:
    print(f"Error walking directory: {e}")

print(f"Total DWG files: {dwg_count}")
print(f"Total DXF files: {dxf_count}")
print(f"Total other files: {other_count}")
print(f"Total files: {total_count}")
