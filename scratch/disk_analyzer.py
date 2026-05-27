import os
import sys

def get_size(path):
    total_size = 0
    try:
        if os.path.isfile(path):
            return os.path.getsize(path)
        elif os.path.islink(path):
            return 0
        
        # Walk directory
        for dirpath, dirnames, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if not os.path.islink(fp):
                    try:
                        total_size += os.path.getsize(fp)
                    except OSError:
                        pass
    except OSError:
        pass
    return total_size

def format_size(size):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} TB"

def analyze_root_folders():
    print("\nAnalyzing top-level directories on C:\\...")
    root = "C:\\"
    results = []
    
    try:
        entries = os.listdir(root)
    except OSError as e:
        print(f"Error reading C:\\: {e}")
        return
        
    for entry in entries:
        full_path = os.path.join(root, entry)
        # Skip system protected folders that are extremely slow or locked
        if entry.lower() in ['$recycle.bin', 'system volume information', 'windows', 'documents and settings', 'recovery', 'config.msi']:
            continue
            
        print(f"Checking C:\\{entry}...")
        size = get_size(full_path)
        if size > 100 * 1024 * 1024:  # > 100 MB
            results.append((full_path, size))
            
    print("\n--- C:\\ Root Directories (> 100MB) ---")
    results.sort(key=lambda x: x[1], reverse=True)
    for path, size in results:
        print(f"{format_size(size)}: {path}")

def analyze_appdata():
    print("\nAnalyzing AppData directories...")
    user_profile = os.environ.get('USERPROFILE', 'C:\\Users\\khs09')
    appdata_local = os.path.join(user_profile, 'AppData', 'Local')
    appdata_roaming = os.path.join(user_profile, 'AppData', 'Roaming')
    
    results = []
    for path in [appdata_local, appdata_roaming]:
        if os.path.exists(path):
            try:
                entries = os.listdir(path)
                for entry in entries:
                    full_path = os.path.join(path, entry)
                    print(f"Checking {entry} in AppData...")
                    size = get_size(full_path)
                    if size > 100 * 1024 * 1024:  # > 100 MB
                        results.append((full_path, size))
            except OSError:
                pass
                
    print("\n--- AppData Subdirectories (> 100MB) ---")
    results.sort(key=lambda x: x[1], reverse=True)
    for path, size in results:
        print(f"{format_size(size)}: {path}")

if __name__ == '__main__':
    analyze_root_folders()
    analyze_appdata()
