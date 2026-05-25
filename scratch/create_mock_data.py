import json
from pathlib import Path

def setup_mock_data():
    base = Path('outputs/sample_test')
    base.mkdir(parents=True, exist_ok=True)
    
    # 1. fileized/json/sample.json
    json_dir = base / 'fileized' / 'json'
    json_dir.mkdir(parents=True, exist_ok=True)
    (json_dir / 'sample.json').write_text(json.dumps({
        'file_id': 'sample',
        'relative_path': 'sample.dxf',
        'entities': [
            {'entity_type': 'TEXT', 'handle': 'T1', 'layer': 'ROOM', 'text': '사무실', 'bbox': [0, 0, 10, 10]},
            {'entity_type': 'MTEXT', 'handle': 'M1', 'layer': 'NOTE', 'text': '복도', 'bbox': [20, 20, 30, 30]},
            {'entity_type': 'LINE', 'handle': 'L1', 'layer': 'WALL'}
        ]
    }, ensure_ascii=False), encoding='utf-8')

    # 2. OCR_TEXT_REGIONS.json
    (base / 'OCR_TEXT_REGIONS.json').write_text(json.dumps({
        'regions': [
            {
                'text': '사무실',
                'confidence': 0.95,
                'source_pdf': 'sample.pdf',
                'page_index': 0,
                'page_contract_id': 'sample:p1',
                'pdf_bbox': [0, 0, 10, 10]
            },
            {
                'text': '복도',
                'confidence': 0.90,
                'source_pdf': 'sample.pdf',
                'page_index': 0,
                'page_contract_id': 'sample:p1',
                'pdf_bbox': [20, 20, 30, 30]
            },
            {
                'text': '회의실',
                'confidence': 0.85,
                'source_pdf': 'sample.pdf',
                'page_index': 0,
                'page_contract_id': 'sample:p1',
                'pdf_bbox': [100, 100, 110, 110]
            }
        ]
    }, ensure_ascii=False), encoding='utf-8')

    # 3. OCR_VECTOR_TEXT_MATCHES.json
    (base / 'OCR_VECTOR_TEXT_MATCHES.json').write_text(json.dumps({
        'summary': {
            'ocr_region_count': 3,
            'match_count': 2,
            'avg_match_score': 0.9
        },
        'matches': [
            {
                'ocr_index': 0,
                'ocr_text': '사무실',
                'match_score': 0.95,
                'vector_text': '사무실',
                'bbox_iou': 1.0,
                'text_similarity': 1.0
            },
            {
                'ocr_index': 1,
                'ocr_text': '복도',
                'match_score': 0.90,
                'vector_text': '복도',
                'bbox_iou': 1.0,
                'text_similarity': 1.0
            }
        ]
    }, ensure_ascii=False), encoding='utf-8')

    print("Successfully set up mock data in outputs/sample_test!")

if __name__ == '__main__':
    setup_mock_data()
