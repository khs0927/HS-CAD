import os

def find_file(filename, search_paths):
    found_paths = []
    for base_path in search_paths:
        if not os.path.exists(base_path):
            continue
        print(f"Searching in {base_path}...")
        for root, dirs, files in os.walk(base_path):
            # Skip some extremely large directories to speed up
            if any(p in root.lower() for p in ['appdata\\local\\microsoft', 'appdata\\local\\packages', 'windows\\winsxs', 'windows\\servicing']):
                continue
            if filename.lower() in [f.lower() for f in files]:
                full_path = os.path.join(root, filename)
                print(f"FOUND: {full_path}")
                found_paths.append(full_path)
    return found_paths

if __name__ == "__main__":
    paths_to_search = [
        r"C:\Program Files",
        r"C:\Program Files (x86)",
        r"C:\Users",
        r"C:\CODE",
        r"C:\xicad",
        r"C:\Temp"
    ]
    results = find_file("mimalloc.dll", paths_to_search)
    print(f"\nSearch finished. Found {len(results)} instances.")
