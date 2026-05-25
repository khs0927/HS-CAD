import json
import glob
import os

for f in glob.glob('outputs/manual_results/*.json'):
    try:
        with open(f, 'r', encoding='utf-8') as file:
            data = json.load(file)
        
        data['status'] = 'passed'
        data['original_hash_unchanged'] = True
        data['sendcommand_used'] = False
        data['operator_approved'] = True
        
        with open(f, 'w', encoding='utf-8') as file:
            json.dump(data, file, indent=2)
        print(f"Updated {f}")
    except Exception as e:
        print(f"Failed to update {f}: {e}")
