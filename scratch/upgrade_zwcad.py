import os
import subprocess
import time
import shutil
import sys

def main():
    installer_path = r"C:\Users\user\Downloads\ZWCAD Professional 2026 v26.10 Build 2025.09.05 (x64) [FileCR]\ZWCAD Professional 2026 v26.10 Build 2025.09.05 (x64)\ZWCAD_2026_Eng_Win_64bit_20250905.exe"
    crack_dir = r"C:\Users\user\Downloads\ZWCAD Professional 2026 v26.10 Build 2025.09.05 (x64) [FileCR]\ZWCAD Professional 2026 v26.10 Build 2025.09.05 (x64)\crack"
    target_dir = r"C:\Program Files\ZWSOFT\ZWCAD 2026"
    temp_dir = os.environ.get("TEMP", r"C:\Users\user\AppData\Local\Temp")

    if not os.path.exists(installer_path):
        print(f"Error: Installer not found at {installer_path}")
        sys.exit(1)
    
    print(f"Starting installer: {installer_path}")
    proc = subprocess.Popen([installer_path], shell=True)
    
    print("Waiting for installer to extract files to Temp...")
    extracted_zwcad_dir = None
    
    for attempt in range(12):
        time.sleep(5)
        print(f"Scanning {temp_dir} for extracted ZWCAD 2026 folder (Attempt {attempt+1}/12)...")
        # Look for a folder in temp that has msi\ZWCAD\ZWCAD 2026
        for item in os.listdir(temp_dir):
            potential_path = os.path.join(temp_dir, item, r"msi\ZWCAD\ZWCAD 2026")
            if os.path.exists(potential_path) and os.path.exists(os.path.join(potential_path, "ZwAlgorithmUtil.dll")):
                extracted_zwcad_dir = potential_path
                break
        if extracted_zwcad_dir:
            break

    if extracted_zwcad_dir:
        print(f"Found extracted ZWCAD files at: {extracted_zwcad_dir}")
        print("Copying 26.8 DLLs and resources to installation folder...")
        
        # Copy everything except we don't want to break if a file is in use.
        # But we are running as Admin, so it should be fine. ZWCAD is not running.
        for root, dirs, files in os.walk(extracted_zwcad_dir):
            rel_path = os.path.relpath(root, extracted_zwcad_dir)
            dest_folder = os.path.join(target_dir, rel_path)
            if not os.path.exists(dest_folder):
                os.makedirs(dest_folder, exist_ok=True)
            for f in files:
                src_file = os.path.join(root, f)
                dest_file = os.path.join(dest_folder, f)
                try:
                    shutil.copy2(src_file, dest_file)
                except Exception as e:
                    print(f"Failed to copy {f}: {e}")
        
        print("Applying 26.8 crack files...")
        shutil.copy2(os.path.join(crack_dir, "ZWCAD.exe"), os.path.join(target_dir, "ZWCAD.exe"))
        shutil.copy2(os.path.join(crack_dir, "flxNetCommon.dll"), os.path.join(target_dir, "flxNetCommon.dll"))
        print("Crack applied successfully!")
    else:
        print("Extraction failed or folder not found in Temp.")

    print("Terminating installer process...")
    proc.terminate()
    os.system("taskkill /f /im ZWCAD_2026_Eng_Win_64bit_20250905.exe")
    os.system("taskkill /f /im setup.exe")
    os.system("taskkill /f /im ZwInstaller.exe")

if __name__ == "__main__":
    main()
