import py7zr
import os
import shutil

zip_file = r"C:\Users\user\AppData\Local\Temp\ZWCAD_2026_Eng_Win_64bit\msi\ZWCAD\ZWCAD.7z"
install_dir = r"C:\Program Files\ZWSOFT\ZWCAD 2026"
crack_dir = r"C:\Users\user\Downloads\ZWCAD Professional 2026 v26.10 Build 2025.09.05 (x64) [FileCR]\ZWCAD Professional 2026 v26.10 Build 2025.09.05 (x64)\crack"

print("Extracting 26.8 DLLs to installation directory...")
try:
    with py7zr.SevenZipFile(zip_file, mode='r') as z:
        z.extractall(path=install_dir)
    print("Extraction completed successfully.")
except Exception as e:
    print(f"Extraction failed: {e}")

print("Applying 26.8 crack files...")
try:
    shutil.copy2(os.path.join(crack_dir, "ZWCAD.exe"), os.path.join(install_dir, "ZWCAD.exe"))
    shutil.copy2(os.path.join(crack_dir, "flxNetCommon.dll"), os.path.join(install_dir, "flxNetCommon.dll"))
    print("Crack applied successfully.")
except Exception as e:
    print(f"Crack application failed: {e}")
