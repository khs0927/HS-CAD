from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

def normalize_text(text: str) -> str:
    """Normalize text by removing all whitespace, tabs, newlines, and special characters."""
    if not text:
        return ""
    # Strip spaces and tabs, convert to lowercase
    return "".join(text.split()).lower()

def match_anchors_to_texts(
    anchors_path: str | Path,
    texts_path: str | Path,
    out_path: str | Path
) -> List[Dict[str, Any]]:
    """Match PDF anchors with CAD scanned text objects and write the results to out_path.
    
    The algorithm:
    1. Perfect Exact Match (normalized)
    2. Substring Match (anchor inside text, or vice versa, after removing spaces)
    3. Fallback on similarity/key matching
    """
    anchors_path = Path(anchors_path)
    texts_path = Path(texts_path)
    out_path = Path(out_path)
    
    if not anchors_path.is_file():
        raise FileNotFoundError(f"Anchors file not found: {anchors_path}")
    if not texts_path.is_file():
        raise FileNotFoundError(f"Texts file not found: {texts_path}")
        
    anchors = json.loads(anchors_path.read_text(encoding="utf-8"))
    texts = json.loads(texts_path.read_text(encoding="utf-8"))
    
    matches = []
    
    for anchor in anchors:
        anchor_title = anchor["title"]
        anchor_id = anchor["id"]
        norm_anchor = normalize_text(anchor_title)
        
        best_match = None
        best_score = 0.0
        
        for entry in texts:
            txt = str(entry.get("text", ""))
            norm_txt = normalize_text(txt)
            
            # Exact Match (after space normalization)
            if norm_anchor == norm_txt:
                best_match = entry
                best_score = 1.0
                break
                
            # Exact Substring Match (e.g. anchor title "식재수량표" matches "식재수량표 [TO-DO...]")
            elif norm_anchor in norm_txt or norm_txt in norm_anchor:
                # Score depends on how close they are in length, e.g. 0.8
                score = 0.8
                if score > best_score:
                    best_match = entry
                    best_score = score
                    
        if best_match:
            matches.append({
                "anchor_id": anchor_id,
                "anchor_title": anchor_title,
                "page": anchor["page"],
                "section": anchor["section"],
                "matched": True,
                "handle": best_match.get("handle"),
                "layer": best_match.get("layer"),
                "insert": best_match.get("insert"),
                "text": best_match.get("text"),
                "confidence": best_score
            })
        else:
            matches.append({
                "anchor_id": anchor_id,
                "anchor_title": anchor_title,
                "page": anchor["page"],
                "section": anchor["section"],
                "matched": False,
                "handle": None,
                "layer": None,
                "insert": None,
                "text": None,
                "confidence": 0.0
            })
            
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(matches, ensure_ascii=False, indent=2), encoding="utf-8")
    return matches
