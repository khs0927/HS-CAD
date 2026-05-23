import json
from pathlib import Path
from src.ocr.text_evidence_fusion import write_text_evidence_fusion, build_text_evidence_fusion

def test_custom_policy_patch_loading(tmp_path: Path):
    # 1. Write mock text input files
    (tmp_path / 'OCR_TEXT_REGIONS.json').write_text(json.dumps({
        'regions': [{'text': '사무실', 'confidence': 0.8, 'source_pdf': 'a.pdf', 'page_index': 0}]
    }))
    (tmp_path / 'OCR_VECTOR_TEXT_MATCHES.json').write_text(json.dumps({'matches': []}))
    (tmp_path / 'OCR_CAD_TEXT_MATCHES.json').write_text(json.dumps({'matches': []}))

    # 2. Write custom policy patch: set cad_match weight to 0.8
    policy_patch = {
        "text_evidence_fusion": {
            "weights": {
                "ocr_confidence": 0.1,
                "vector_match": 0.1,
                "cad_match": 0.8,
                "coverage": 0.0,
                "conflict_penalty": 0.0
            },
            "review_threshold": 0.4,
            "conflict_threshold": 0.3
        }
    }
    (tmp_path / 'TEXT_FUSION_POLICY.json').write_text(json.dumps(policy_patch))

    result = write_text_evidence_fusion(tmp_path)
    assert result['status'] == 'ok'
    
    # Read output
    output = json.loads((tmp_path / 'TEXT_EVIDENCE_FUSION.json').read_text(encoding='utf-8'))
    assert output['policy']['weights']['cad_match'] == 0.8
    # confidence = 0.1 * 0.8 (ocr) = 0.08
    assert output['items'][0]['confidence'] == 0.08
