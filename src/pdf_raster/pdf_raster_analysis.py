from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

from src.workers.provenance import build_provenance


class PDFRasterAnalyzer:
    backend_id = 'pdf_raster_analysis'

    def availability(self) -> dict[str, dict[str, Any]]:
        return {
            'pymupdf': _available('fitz'),
            'pdfplumber': _available('pdfplumber'),
            'opencv': _available('cv2'),
            'numpy': _available('numpy'),
        }

    def analyze_workspace(self, workspace: str | Path, *, dpi: int = 180, max_pages: int = 3) -> dict[str, Any]:
        base = Path(workspace)
        pdfs = _discover_pdfs(base)
        availability = self.availability()
        vector_objects: list[dict[str, Any]] = []
        contours: list[dict[str, Any]] = []
        render_outputs: list[str] = []
        warnings: list[str] = []

        if not pdfs:
            warnings.append('no pdf files discovered')

        for pdf_path in pdfs:
            if availability['pdfplumber']['available']:
                try:
                    vector_objects.extend(_extract_pdfplumber_objects(pdf_path, max_pages=max_pages))
                except Exception as exc:
                    warnings.append(f'pdfplumber failed for {pdf_path}: {exc}')
            else:
                warnings.append('pdfplumber unavailable')

            if availability['pymupdf']['available']:
                try:
                    rendered = _render_pymupdf_pages(pdf_path, base / 'pdf_raster' / 'rendered', dpi=dpi, max_pages=max_pages)
                    render_outputs.extend(rendered)
                    if availability['opencv']['available'] and availability['numpy']['available']:
                        for image_path in rendered:
                            contours.extend(_extract_opencv_contours(Path(image_path), source_pdf=pdf_path))
                    else:
                        warnings.append('opencv or numpy unavailable; contours skipped')
                except Exception as exc:
                    warnings.append(f'pymupdf/opencv failed for {pdf_path}: {exc}')
            else:
                warnings.append('pymupdf unavailable')

        provenance = build_provenance(
            workspace=base,
            backend=self.backend_id,
            algorithm='pymupdf_render_pdfplumber_vector_opencv_contours',
            source_artifacts=[str(path) for path in pdfs],
            worker_name='pdf_raster',
        )
        vector_payload = {
            'backend': self.backend_id,
            'source': 'pdfplumber',
            'object_count': len(vector_objects),
            'objects': vector_objects,
            'provenance': provenance,
        }
        contour_payload = {
            'backend': self.backend_id,
            'source': 'pymupdf+opencv',
            'contour_count': len(contours),
            'contours': contours,
            'render_outputs': render_outputs,
            'provenance': provenance,
        }
        (base / 'PDF_VECTOR_OBJECTS.json').write_text(json.dumps(vector_payload, ensure_ascii=False, indent=2), encoding='utf-8')
        (base / 'RASTER_CONTOURS.json').write_text(json.dumps(contour_payload, ensure_ascii=False, indent=2), encoding='utf-8')
        report_path = base / 'PDF_RASTER_REPORT.md'
        result = {
            'backend': self.backend_id,
            'status': 'ok' if vector_objects or contours else 'warning',
            'workspace': str(base),
            'pdf_count': len(pdfs),
            'availability': availability,
            'vector_object_count': len(vector_objects),
            'contour_count': len(contours),
            'render_output_count': len(render_outputs),
            'artifacts': [
                str(base / 'PDF_VECTOR_OBJECTS.json'),
                str(base / 'RASTER_CONTOURS.json'),
                str(report_path),
            ],
            'warnings': warnings,
            'provenance': provenance,
        }
        report_path.write_text(_markdown(result), encoding='utf-8')
        return result


def write_pdf_raster_analysis(workspace: str | Path, *, dpi: int = 180, max_pages: int = 3) -> dict[str, Any]:
    base = Path(workspace)
    result = PDFRasterAnalyzer().analyze_workspace(base, dpi=dpi, max_pages=max_pages)
    (base / 'PDF_RASTER_ANALYSIS.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result


def _available(module_name: str) -> dict[str, Any]:
    spec = importlib.util.find_spec(module_name)
    return {'available': spec is not None, 'module': module_name, 'reason': 'installed' if spec is not None else 'not installed'}


def _discover_pdfs(base: Path) -> list[Path]:
    pdfs: list[Path] = []
    manifest = base / 'run_manifest.json'
    if manifest.exists():
        payload = _read_json(manifest)
        for item in payload.get('files') or []:
            rel = item.get('relative_path') or item.get('path')
            if rel and str(rel).lower().endswith('.pdf'):
                candidate = base / rel
                if candidate.exists():
                    pdfs.append(candidate)
    for path in sorted(base.rglob('*.pdf')):
        if 'pdf_raster' in path.parts:
            continue
        if path not in pdfs:
            pdfs.append(path)
    return pdfs


def _extract_pdfplumber_objects(pdf_path: Path, *, max_pages: int) -> list[dict[str, Any]]:
    import pdfplumber

    rows: list[dict[str, Any]] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_index, page in enumerate(pdf.pages[:max_pages]):
            for obj_type in ('chars', 'lines', 'rects', 'curves'):
                for obj in getattr(page, obj_type, []) or []:
                    rows.append({
                        'source_pdf': str(pdf_path),
                        'page_index': page_index,
                        'object_type': obj_type[:-1] if obj_type.endswith('s') else obj_type,
                        'text': obj.get('text'),
                        'x0': _float(obj.get('x0')),
                        'top': _float(obj.get('top')),
                        'x1': _float(obj.get('x1')),
                        'bottom': _float(obj.get('bottom')),
                        'width': _float(obj.get('width')),
                        'height': _float(obj.get('height')),
                    })
    return rows


def _render_pymupdf_pages(pdf_path: Path, out_dir: Path, *, dpi: int, max_pages: int) -> list[str]:
    import fitz

    out_dir.mkdir(parents=True, exist_ok=True)
    rendered: list[str] = []
    doc = fitz.open(str(pdf_path))
    try:
        for page_index in range(min(max_pages, len(doc))):
            page = doc.load_page(page_index)
            pix = page.get_pixmap(dpi=dpi, alpha=False)
            out = out_dir / f'{pdf_path.stem}_p{page_index + 1}_{dpi}dpi.png'
            pix.save(str(out))
            rendered.append(str(out))
    finally:
        doc.close()
    return rendered


def _extract_opencv_contours(image_path: Path, *, source_pdf: Path) -> list[dict[str, Any]]:
    import cv2

    image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        return []
    # Binary inverse catches dark lines/text on light background.
    _, thresh = cv2.threshold(image, 200, 255, cv2.THRESH_BINARY_INV)
    contours, _hierarchy = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    rows: list[dict[str, Any]] = []
    for index, contour in enumerate(contours):
        x, y, w, h = cv2.boundingRect(contour)
        area = float(cv2.contourArea(contour))
        if area < 10 or w < 2 or h < 2:
            continue
        rows.append({
            'source_pdf': str(source_pdf),
            'source_image': str(image_path),
            'contour_index': index,
            'x': int(x),
            'y': int(y),
            'width': int(w),
            'height': int(h),
            'area': area,
        })
    return rows


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _markdown(result: dict[str, Any]) -> str:
    availability = result.get('availability') or {}
    lines = [
        '# PDF Raster Report',
        '',
        f"- Backend: `{result.get('backend')}`",
        f"- Status: `{result.get('status')}`",
        f"- PDF count: `{result.get('pdf_count')}`",
        f"- Vector object count: `{result.get('vector_object_count')}`",
        f"- Contour count: `{result.get('contour_count')}`",
        f"- Render output count: `{result.get('render_output_count')}`",
        '',
        '## Backend Availability',
        '',
    ]
    for name, info in availability.items():
        lines.append(f"- `{name}`: `{info.get('available')}` ({info.get('reason')})")
    lines.extend(['', '## Warnings', ''])
    for warning in result.get('warnings') or []:
        lines.append(f'- {warning}')
    if not result.get('warnings'):
        lines.append('- None')
    lines.append('')
    return '\n'.join(lines)
