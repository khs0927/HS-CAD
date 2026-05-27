import os
import sys
import shutil
import subprocess

def clear_pip_cache():
    print("Purging Pip cache...")
    try:
        subprocess.run(["pip", "cache", "purge"], check=True)
        print("Pip cache cleared successfully.")
    except Exception as e:
        print(f"Failed to clear pip cache: {e}")

def clear_npm_cache():
    print("Clearing Npm cache...")
    try:
        # npm cache clean --force
        subprocess.run(["npm", "cache", "clean", "--force"], shell=True, check=True)
        print("Npm cache cleared successfully.")
    except Exception as e:
        print(f"Failed to clear npm cache: {e}")

def safe_delete_folder_contents(folder_path):
    print(f"Clearing contents of {folder_path}...")
    if not os.path.exists(folder_path):
        print(f"Folder {folder_path} does not exist.")
        return 0
        
    deleted_bytes = 0
    skipped_files = 0
    skipped_folders = 0
    
    # List files and directories
    try:
        entries = os.listdir(folder_path)
    except OSError as e:
        print(f"Error reading {folder_path}: {e}")
        return 0
        
    for entry in entries:
        full_path = os.path.join(folder_path, entry)
        if os.path.islink(full_path) or os.path.isfile(full_path):
            try:
                size = os.path.getsize(full_path)
                os.remove(full_path)
                deleted_bytes += size
            except OSError:
                skipped_files += 1
        elif os.path.isdir(full_path):
            try:
                # Try getting size before deleting
                dir_size = 0
                for dirpath, dirnames, filenames in os.walk(full_path):
                    for f in filenames:
                        fp = os.path.join(dirpath, f)
                        try:
                            dir_size += os.path.getsize(fp)
                        except OSError:
                            pass
                shutil.rmtree(full_path)
                deleted_bytes += dir_size
            except OSError:
                # If direct rmtree fails, let's try inside it or just skip it
                skipped_folders += 1
                
    print(f"Cleared: {deleted_bytes / (1024*1024):.2f} MB (Skipped due to lock: {skipped_files} files, {skipped_folders} folders)")
    return deleted_bytes

def format_size(size):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} TB"

if __name__ == '__main__':
    user_profile = os.environ.get('USERPROFILE', 'C:\\Users\\khs09')
    user_temp = os.path.join(user_profile, 'AppData', 'Local', 'Temp')
    sys_temp = 'C:\\Windows\\Temp'
    
    print("=== STARTING C DRIVE CLEANUP ===\n")
    sys.stdout.flush()
    
    # 1. Clear caches
    clear_pip_cache()
    print("")
    clear_npm_cache()
    print("")
    
    # 2. Clear temp directories
    user_temp_cleared = safe_delete_folder_contents(user_temp)
    print("")
    sys_temp_cleared = safe_delete_folder_contents(sys_temp)
    print("")
    
    total_cleared = user_temp_cleared + sys_temp_cleared
    print(f"=== CLEANUP COMPLETED ===")
    print(f"Total safely reclaimed space: {format_size(total_cleared)}")
    sys.stdout.flush()
