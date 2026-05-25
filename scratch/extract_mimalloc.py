import os
import subprocess
import time
import shutil
import sys

def main():
    installer_path = r"C:\Users\user\Downloads\ZWCAD_2026_Kor_Win_64bit.exe"
    target_dir = r"C:\Program Files\ZWSOFT\ZWCAD 2026"
    temp_dir = os.environ.get("TEMP", r"C:\Users\user\AppData\Local\Temp")

    if not os.path.exists(installer_path):
        print(f"Error: Installer not found at {installer_path}")
        # Try english installer as fallback
        installer_path = r"C:\Users\user\Downloads\ZWCAD Professional 2026 v26.10 Build 2025.09.05 (x64) [FileCR]\ZWCAD Professional 2026 v26.10 Build 2025.09.05 (x64)\ZWCAD_2026_Eng_Win_64bit_20250905.exe"
        if not os.path.exists(installer_path):
            print(f"Error: English installer also not found.")
            sys.exit(1)
    
    print(f"Starting installer: {installer_path}")
    # Run the installer in the background
    proc = subprocess.Popen([installer_path], shell=True)
    
    print("Waiting 15 seconds for installer to extract files to Temp...")
    found_dll = None
    
    # We will poll for up to 60 seconds
    for attempt in range(12):
        time.sleep(5)
        print(f"Scanning {temp_dir} for mimalloc.dll (Attempt {attempt+1}/12)...")
        for root, dirs, files in os.walk(temp_dir):
            if "mimalloc.dll" in [f.lower() for f in files]:
                found_dll = os.path.join(root, "mimalloc.dll")
                print(f"Found extracted dll at: {found_dll}")
                break
        if found_dll:
            break

    if found_dll:
        # Copy to destination
        dest_path = os.path.join(target_dir, "mimalloc.dll")
        print(f"Copying {found_dll} to {dest_path}")
        try:
            shutil.copy2(found_dll, dest_path)
            print("Successfully copied mimalloc.dll!")
        except Exception as e:
            print(f"Failed to copy file: {e}")
    else:
        print("mimalloc.dll was not found in Temp during extraction.")

    # Terminate the installer process
    print("Terminating installer process...")
    proc.terminate()
    # Also kill any other setup/installer processes that might have spawned
    os.system("taskkill /f /im ZWCAD_2026_Kor_Win_64bit.exe")
    os.system("taskkill /f /im ZWCAD_2026_Eng_Win_64bit_20250905.exe")
    os.system("taskkill /f /im setup.exe")
    os.system("taskkill /f /im _is*.exe")

if __name__ == "__main__":
    main()
