import json
from pathlib import Path

def main():
    ws = Path("outputs/validation_sandbox")
    json_dir = ws / "fileized" / "json"
    json_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. fileized record
    record = {
        "file_id": "sample_dxf",
        "relative_path": "sample_dxf.dxf",
        "engine": "ezdxf",
        "entities": [
            {"handle": "P1", "entity_type": "POLYLINE", "layer": "ROOM", "closed": True, "points": [[0, 0], [10, 0], [10, 10], [0, 10]], "bbox": [0, 0, 10, 10]},
            {"handle": "T1", "entity_type": "TEXT", "layer": "TEXT", "text": "사무실", "insert": [5, 5], "bbox": [4, 4, 6, 6]},
            {"handle": "L1", "entity_type": "LINE", "layer": "WALL", "start": [0, 0], "end": [10, 0], "bbox": [0, 0, 10, 0]},
            {"handle": "DIM1", "entity_type": "DIMENSION", "layer": "DIM", "text": "1000", "bbox": [0, -1, 10, -1]}
        ]
    }
    (json_dir / "sample_dxf.json").write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    # 2. AREA_ELEMENTS.json
    areas = {
        "areas": [
            {"file_id": "sample_dxf", "handle": "P1", "label": "사무실", "source_type": "closed_polyline", "area": 100.0, "confidence": 0.9, "bbox": [0, 0, 10, 10]}
        ]
    }
    (ws / "AREA_ELEMENTS.json").write_text(json.dumps(areas, ensure_ascii=False), encoding="utf-8")

    # 3. TEXT_ROLE_INFERENCE.json
    roles = {
        "roles": [
            {"file_id": "sample_dxf", "handle": "T1", "text": "사무실", "role": "room_or_space_name", "layer": "TEXT", "confidence": 0.9, "bbox": [4, 4, 6, 6]}
        ]
    }
    (ws / "TEXT_ROLE_INFERENCE.json").write_text(json.dumps(roles, ensure_ascii=False), encoding="utf-8")

    # 4. AREA_BOUNDARY_INFERENCE.json
    (ws / "AREA_BOUNDARY_INFERENCE.json").write_text(json.dumps({"areas": []}, ensure_ascii=False), encoding="utf-8")
    
    # 5. LEADER_NOTE_INFERENCE.json
    (ws / "LEADER_NOTE_INFERENCE.json").write_text(json.dumps({"leaders": []}, ensure_ascii=False), encoding="utf-8")

    # 6. DIMENSION_TEXT_INFERENCE.json
    (ws / "DIMENSION_TEXT_INFERENCE.json").write_text(json.dumps({"dimensions": []}, ensure_ascii=False), encoding="utf-8")

    # 7. TABLE_REGION_INFERENCE.json
    (ws / "TABLE_REGION_INFERENCE.json").write_text(json.dumps({"tables": []}, ensure_ascii=False), encoding="utf-8")

    # 8. TITLEBLOCK_INFERENCE.json
    (ws / "TITLEBLOCK_INFERENCE.json").write_text(json.dumps({"titleblocks": []}, ensure_ascii=False), encoding="utf-8")

    print("Sandbox setup completed successfully.")

if __name__ == "__main__":
    main()
