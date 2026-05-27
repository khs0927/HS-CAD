import os
import sys

def list_large_files(dir_path, size_threshold_mb=100):
    if not os.path.exists(dir_path):
        print(f"Directory {dir_path} does not exist.")
        return
    
    print(f"Checking for files larger than {size_threshold_mb}MB in {dir_path}...")
    large_files = []
    
    for dirpath, dirnames, filenames in os.walk(dir_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if os.path.islink(fp):
                continue
            try:
                size = os.path.getsize(fp)
                size_mb = size / (1024 * 1024)
                if size_mb >= size_threshold_mb:
                    large_files.append((fp, size_mb))
            except OSError:
                pass
                
    large_files.sort(key=lambda x: x[1], reverse=True)
    
    print(f"\nFound {len(large_files)} files larger than {size_threshold_mb}MB:")
    for path, size in large_files:
        print(f"{size:.2f} MB: {path}")
        
if __name__ == '__main__':
    user_profile = os.environ.get('USERPROFILE', 'C:\\Users\\khs09')
    downloads = os.path.join(user_profile, 'Downloads')
    list_large_files(downloads)
