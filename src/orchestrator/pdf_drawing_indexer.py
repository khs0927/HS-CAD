from __future__ import annotations

import json
from pathlib import Path
import fitz  # PyMuPDF

def render_pdf_to_images(pdf_path: str | Path, out_dir: str | Path) -> list[Path]:
    """Render each page of the PDF to a PNG image in out_dir/pdf_pages.
    
    Returns a list of paths to the rendered PNG files.
    """
    pdf_path = Path(pdf_path)
    out_dir = Path(out_dir)
    pages_dir = out_dir / "pdf_pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
    doc = fitz.open(pdf_path)
    rendered_paths = []
    
    for idx, page in enumerate(doc):
        # Render at 150 DPI for good readability of architectural texts
        pix = page.get_pixmap(dpi=150)
        page_num = idx + 1
        img_name = f"page_{page_num:03d}.png"
        img_path = pages_dir / img_name
        pix.save(str(img_path))
        rendered_paths.append(img_path)
        
    return rendered_paths

def generate_pdf_page_index(out_dir: str | Path) -> Path:
    """Generate the static visual classification index of pages as JSON."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    index_data = {
        "project": "hwamok_698_14",
        "pages": {
            "1": ["배치도", "대지개요", "건축개요", "조경개요", "조경식재 배식계획도 일부"],
            "2": ["조경면적 확인 배치기준", "조경면적표"],
            "3": ["조경식재계획의 배치기준", "식재수량표", "담장/조경포장 관련 수량표"]
        }
    }
    
    index_path = out_dir / "pdf_page_index.json"
    index_path.write_text(json.dumps(index_data, ensure_ascii=False, indent=2), encoding="utf-8")
    return index_path

def generate_pdf_anchors(out_dir: str | Path) -> Path:
    """Generate the predefined anchors from the PDF index to guide CAD parsing."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    anchors = [
        {"id": "architecture_overview", "title": "건축개요", "page": 1, "section": "overview"},
        {"id": "site_overview", "title": "대지개요", "page": 1, "section": "overview"},
        {"id": "landscape_overview", "title": "조경개요", "page": 1, "section": "landscape_overview"},
        {"id": "landscape_area_guidelines", "title": "조경면적 확인 배치기준", "page": 2, "section": "area_guidelines"},
        {"id": "landscape_area_table", "title": "조경면적표", "page": 2, "section": "area_table"},
        {"id": "planting_plan", "title": "조경식재 배식계획도", "page": 1, "section": "planting_plan"},
        {"id": "planting_guidelines", "title": "조경식재계획의 배치기준", "page": 3, "section": "planting_guidelines"},
        {"id": "planting_table", "title": "식재수량표", "page": 3, "section": "planting_table"}
    ]
    
    anchors_path = out_dir / "pdf_anchors.json"
    anchors_path.write_text(json.dumps(anchors, ensure_ascii=False, indent=2), encoding="utf-8")
    return anchors_path
