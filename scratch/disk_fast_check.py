import os
import sys
import subprocess

def get_directory_size_fast(path):
    if not os.path.exists(path):
        return "Does not exist"
    try:
        # Robocopy trick
        cmd = f'robocopy "{path}" NULL /L /S /XJ /R:0 /W:0'
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, _ = proc.communicate()
        lines = stdout.decode('cp949', errors='ignore').splitlines()
        for line in lines:
            if "Bytes :" in line:
                return line.strip()
    except Exception as e:
        return f"Error: {e}"
    return "Unknown"

if __name__ == '__main__':
    paths_to_check = [
        "C:\\pinokio",
        "C:\\LDPlayer",
        "C:\\Riot Games",
        "C:\\Nexon",
        "C:\\cad",
        "C:\\CODE",
        "C:\\xicad",
        "C:\\xicad_backup",
        "C:\\Users\\khs09\\AppData\\Local\\Temp",
        "C:\\Users\\khs09\\AppData\\Local\\pip\\cache",
        "C:\\Users\\khs09\\AppData\\Local\\npm-cache",
        "C:\\Users\\khs09\\AppData\\Roaming\\npm-cache",
        "C:\\Users\\khs09\\.nuget\\packages",
        "C:\\Users\\khs09\\.cache",
        "C:\\Windows\\Temp",
    ]
    
    print("Checking sizes of major directories (flushing)...")
    sys.stdout.flush()
    
    for path in paths_to_check:
        print(f"Checking {path}...", end=" ", flush=True)
        size_info = get_directory_size_fast(path)
        print(f"-> {size_info}", flush=True)
