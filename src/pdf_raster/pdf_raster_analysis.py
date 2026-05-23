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
        page_contracts: list[dict[str, Any]] = []
        warnings: list[str] = []

        if not pdfs:
            warnings.append('no pdf files discovered')

        for pdf_path in pdfs:
            contracts_for_pdf: list[dict[str, Any]] = []
            if availability['pymupdf']['available']:
                try:
                    rendered_pages = _render_pymupdf_pages(pdf_path, base / 'pdf_raster' / 'rendered', dpi=dpi, max_pages=max_pages)
                    render_outputs.extend([row['image_path'] for row in rendered_pages])
                    contracts_for_pdf = [row['page_contract'] for row in rendered_pages]
                    page_contracts.extend(contracts_for_pdf)
                    if availability['opencv']['available'] and availability['numpy']['available']:
                        for rendered in rendered_pages:
                            contours.extend(_extract_opencv_contours(Path(rendered['image_path']), source_pdf=pdf_path, page_contract=rendered['page_contract']))
                    else:
                        warnings.append('opencv or numpy unavailable; contours skipped')
                except Exception as exc:
                    warnings.append(f'pymupdf/opencv failed for {pdf_path}: {exc}')
            else:
                warnings.append('pymupdf unavailable')

            if availability['pdfplumber']['available']:
                try:
                    vector_objects.extend(_extract_pdfplumber_objects(pdf_path, max_pages=max_pages, page_contracts=contracts_for_pdf))
                except Exception as exc:
                    warnings.append(f'pdfplumber failed for {pdf_path}: {exc}')
            else:
                warnings.append('pdfplumber unavailable')

        provenance = build_provenance(
            workspace=base,
            backend=self.backend_id,
            algorithm='pymupdf_render_pdfplumber_vector_opencv_contours_with_coordinate_contract',
            source_artifacts=[str(path) for path in pdfs],
            worker_name='pdf_raster',
        )
        iou_payload = build_vector_raster_iou_report(vector_objects, contours, provenance=provenance)
        coordinate_payload = {
            'backend': self.backend_id,
            'contract_version': '1.0',
            'coordinate_spaces': {
                'pdf_points_top_left': 'PDF point units with top-left origin, aligned to pdfplumber top/bottom fields.',
                'pixel_top_left': 'Rendered pixel coordinates with top-left origin.',
                'normalized_page': '0..1 coordinates relative to page width/height.',
            },
            'pages': page_contracts,
            'provenance': provenance,
        }
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
        (base / 'PDF_COORDINATE_CONTRACT.json').write_text(json.dumps(coordinate_payload, ensure_ascii=False, indent=2), encoding='utf-8')
        (base / 'PDF_VECTOR_OBJECTS.json').write_text(json.dumps(vector_payload, ensure_ascii=False, indent=2), encoding='utf-8')
        (base / 'RASTER_CONTOURS.json').write_text(json.dumps(contour_payload, ensure_ascii=False, indent=2), encoding='utf-8')
        (base / 'PDF_VECTOR_RASTER_IOU.json').write_text(json.dumps(iou_payload, ensure_ascii=False, indent=2), encoding='utf-8')
        report_path = base / 'PDF_RASTER_REPORT.md'
        result = {
            'backend': self.backend_id,
            'status': 'ok' if vector_objects or contours else 'warning',
            'workspace': str(base),
            'pdf_count': len(pdfs),
            'availability': availability,
            'page_contract_count': len(page_contracts),
            'vector_object_count': len(vector_objects),
            'contour_count': len(contours),
            'render_output_count': len(render_outputs),
            'iou_summary': iou_payload.get('summary'),
            'artifacts': [
                str(base / 'PDF_COORDINATE_CONTRACT.json'),
                str(base / 'PDF_VECTOR_OBJECTS.json'),
                str(base / 'RASTER_CONTOURS.json'),
                str(base / 'PDF_VECTOR_RASTER_IOU.json'),
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


def build_vector_raster_iou_report(vector_objects: list[dict[str, Any]], contours: list[dict[str, Any]], *, provenance: dict[str, Any] | None = None, min_iou: float = 0.01) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    unmatched_vectors = 0
    contours_by_page: dict[tuple[str, int, str], list[dict[str, Any]]] = {}
    for contour in contours:
        key = (str(contour.get('source_pdf')), int(contour.get('page_index') or 0), str(contour.get('page_contract_id') or ''))
        contours_by_page.setdefault(key, []).append(contour)

    for vector_index, vector in enumerate(vector_objects):
        vector_bbox = vector.get('pdf_bbox') or []
        key = (str(vector.get('source_pdf')), int(vector.get('page_index') or 0), str(vector.get('page_contract_id') or ''))
        candidates = contours_by_page.get(key, [])
        best: dict[str, Any] | None = None
        best_iou = 0.0
        for contour in candidates:
            iou = bbox_iou(vector_bbox, contour.get('pdf_bbox') or [])
            if iou > best_iou:
                best_iou = iou
                best = contour
        if best is None or best_iou < min_iou:
            unmatched_vectors += 1
            continue
        matches.append({
            'vector_index': vector_index,
            'object_type': vector.get('object_type'),
            'text': vector.get('text'),
            'source_pdf': vector.get('source_pdf'),
            'page_index': vector.get('page_index'),
            'page_contract_id': vector.get('page_contract_id'),
            'vector_pdf_bbox': vector_bbox,
            'contour_index': best.get('contour_index'),
            'contour_pdf_bbox': best.get('pdf_bbox'),
            'iou': round(best_iou, 6),
        })
    object_type_summary: dict[str, dict[str, Any]] = {}
    for match in matches:
        object_type = str(match.get('object_type') or 'unknown')
        row = object_type_summary.setdefault(object_type, {'match_count': 0, 'iou_sum': 0.0, 'max_iou': 0.0})
        row['match_count'] += 1
        row['iou_sum'] += float(match.get('iou') or 0.0)
        row['max_iou'] = max(row['max_iou'], float(match.get('iou') or 0.0))
    for row in object_type_summary.values():
        count = int(row['match_count'] or 0)
        row['avg_iou'] = round(float(row.pop('iou_sum')) / count, 6) if count else 0.0
        row['max_iou'] = round(float(row['max_iou']), 6)
    avg_iou = round(sum(float(m.get('iou') or 0.0) for m in matches) / len(matches), 6) if matches else 0.0
    return {
        'backend': PDFRasterAnalyzer.backend_id,
        'source': 'pdf_vector_objects+raster_contours',
        'min_iou': min_iou,
        'summary': {
            'vector_count': len(vector_objects),
            'contour_count': len(contours),
            'match_count': len(matches),
            'unmatched_vector_count': unmatched_vectors,
            'avg_iou': avg_iou,
            'object_type_summary': object_type_summary,
        },
        'matches': matches,
        'provenance': provenance or {},
    }


def bbox_iou(a: list[float] | tuple[float, float, float, float], b: list[float] | tuple[float, float, float, float]) -> float:
    if len(a) != 4 or len(b) != 4:
        return 0.0
    ax0, ay0, ax1, ay1 = [float(v) for v in a]
    bx0, by0, bx1, by1 = [float(v) for v in b]
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    iw, ih = max(0.0, ix1 - ix0), max(0.0, iy1 - iy0)
    inter = iw * ih
    area_a = max(0.0, ax1 - ax0) * max(0.0, ay1 - ay0)
    area_b = max(0.0, bx1 - bx0) * max(0.0, by1 - by0)
    union = area_a + area_b - inter
    return 0.0 if union <= 0 else round(inter / union, 6)


def pixel_bbox_to_pdf_bbox(pixel_bbox: list[float] | tuple[float, float, float, float], page_contract: dict[str, Any]) -> list[float]:
    px0, py0, px1, py1 = [float(v) for v in pixel_bbox]
    scale_x = float(page_contract.get('pixel_to_pdf_scale_x') or 1.0)
    scale_y = float(page_contract.get('pixel_to_pdf_scale_y') or 1.0)
    return [round(px0 * scale_x, 6), round(py0 * scale_y, 6), round(px1 * scale_x, 6), round(py1 * scale_y, 6)]


def normalize_bbox(pdf_bbox: list[float] | tuple[float, float, float, float], page_width: float, page_height: float) -> list[float]:
    if not page_width or not page_height:
        return [0.0, 0.0, 0.0, 0.0]
    x0, y0, x1, y1 = [float(v) for v in pdf_bbox]
    return [round(x0 / page_width, 6), round(y0 / page_height, 6), round(x1 / page_width, 6), round(y1 / page_height, 6)]


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


def _extract_pdfplumber_objects(pdf_path: Path, *, max_pages: int, page_contracts: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    import pdfplumber

    rows: list[dict[str, Any]] = []
    contracts_by_page = {int(item.get('page_index') or 0): item for item in page_contracts or []}
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_index, page in enumerate(pdf.pages[:max_pages]):
            page_width = float(getattr(page, 'width', 0.0) or 0.0)
            page_height = float(getattr(page, 'height', 0.0) or 0.0)
            contract = contracts_by_page.get(page_index) or _page_contract(str(pdf_path), page_index, page_width, page_height, None, None, dpi=None)
            for obj_type in ('chars', 'lines', 'rects', 'curves'):
                for obj in getattr(page, obj_type, []) or []:
                    pdf_bbox = [_float(obj.get('x0')) or 0.0, _float(obj.get('top')) or 0.0, _float(obj.get('x1')) or 0.0, _float(obj.get('bottom')) or 0.0]
                    rows.append({
                        'source_pdf': str(pdf_path),
                        'page_index': page_index,
                        'object_type': obj_type[:-1] if obj_type.endswith('s') else obj_type,
                        'text': obj.get('text'),
                        'pdf_bbox': pdf_bbox,
                        'normalized_bbox': normalize_bbox(pdf_bbox, page_width, page_height),
                        'page_width_pdf': page_width,
                        'page_height_pdf': page_height,
                        'coordinate_space': 'pdf_points_top_left',
                        'page_contract_id': contract.get('page_contract_id'),
                        'x0': pdf_bbox[0],
                        'top': pdf_bbox[1],
                        'x1': pdf_bbox[2],
                        'bottom': pdf_bbox[3],
                        'width': _float(obj.get('width')),
                        'height': _float(obj.get('height')),
                    })
    return rows


def _render_pymupdf_pages(pdf_path: Path, out_dir: Path, *, dpi: int, max_pages: int) -> list[dict[str, Any]]:
    import fitz

    out_dir.mkdir(parents=True, exist_ok=True)
    rendered: list[dict[str, Any]] = []
    doc = fitz.open(str(pdf_path))
    try:
        for page_index in range(min(max_pages, len(doc))):
            page = doc.load_page(page_index)
            page_rect = page.rect
            pix = page.get_pixmap(dpi=dpi, alpha=False)
            out = out_dir / f'{pdf_path.stem}_p{page_index + 1}_{dpi}dpi.png'
            pix.save(str(out))
            contract = _page_contract(str(pdf_path), page_index, float(page_rect.width), float(page_rect.height), pix.width, pix.height, dpi=dpi)
            rendered.append({'image_path': str(out), 'page_contract': contract})
    finally:
        doc.close()
    return rendered


def _page_contract(source_pdf: str, page_index: int, page_width_pdf: float, page_height_pdf: float, pixel_width: int | None, pixel_height: int | None, *, dpi: int | None) -> dict[str, Any]:
    pixel_width = int(pixel_width or 0)
    pixel_height = int(pixel_height or 0)
    return {
        'page_contract_id': f'{Path(source_pdf).stem}:p{page_index + 1}',
        'source_pdf': source_pdf,
        'page_index': page_index,
        'dpi': dpi,
        'page_width_pdf': page_width_pdf,
        'page_height_pdf': page_height_pdf,
        'pixel_width': pixel_width,
        'pixel_height': pixel_height,
        'pixel_to_pdf_scale_x': (page_width_pdf / pixel_width) if pixel_width else None,
        'pixel_to_pdf_scale_y': (page_height_pdf / pixel_height) if pixel_height else None,
        'pdf_to_pixel_scale_x': (pixel_width / page_width_pdf) if page_width_pdf else None,
        'pdf_to_pixel_scale_y': (pixel_height / page_height_pdf) if page_height_pdf else None,
        'pdf_origin': 'top_left',
        'pixel_origin': 'top_left',
    }


def _extract_opencv_contours(image_path: Path, *, source_pdf: Path, page_contract: dict[str, Any]) -> list[dict[str, Any]]:
    import cv2

    image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        return []
    _, thresh = cv2.threshold(image, 200, 255, cv2.THRESH_BINARY_INV)
    contours, _hierarchy = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    rows: list[dict[str, Any]] = []
    page_width = float(page_contract.get('page_width_pdf') or 0.0)
    page_height = float(page_contract.get('page_height_pdf') or 0.0)
    for index, contour in enumerate(contours):
        x, y, w, h = cv2.boundingRect(contour)
        area = float(cv2.contourArea(contour))
        if area < 10 or w < 2 or h < 2:
            continue
        pixel_bbox = [float(x), float(y), float(x + w), float(y + h)]
        pdf_bbox = pixel_bbox_to_pdf_bbox(pixel_bbox, page_contract)
        rows.append({
            'source_pdf': str(source_pdf),
            'source_image': str(image_path),
            'page_index': page_contract.get('page_index'),
            'page_contract_id': page_contract.get('page_contract_id'),
            'contour_index': index,
            'pixel_bbox': pixel_bbox,
            'pdf_bbox': pdf_bbox,
            'normalized_bbox': normalize_bbox(pdf_bbox, page_width, page_height),
            'coordinate_space': 'pixel_top_left+pdf_points_top_left',
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
    iou_summary = result.get('iou_summary') or {}
    lines = [
        '# PDF Raster Report',
        '',
        f"- Backend: `{result.get('backend')}`",
        f"- Status: `{result.get('status')}`",
        f"- PDF count: `{result.get('pdf_count')}`",
        f"- Page contract count: `{result.get('page_contract_count')}`",
        f"- Vector object count: `{result.get('vector_object_count')}`",
        f"- Contour count: `{result.get('contour_count')}`",
        f"- Render output count: `{result.get('render_output_count')}`",
        '',
        '## Coordinate Contract',
        '',
        '- PDF-space bbox: `pdf_points_top_left`',
        '- Pixel-space bbox: `pixel_top_left`',
        '- Normalized bbox: `normalized_page`',
        '- Contours include both `pixel_bbox` and `pdf_bbox` for vector-raster comparison.',
        '',
        '## Vector-Raster IoU',
        '',
        f"- Vector count: `{iou_summary.get('vector_count')}`",
        f"- Contour count: `{iou_summary.get('contour_count')}`",
        f"- Match count: `{iou_summary.get('match_count')}`",
        f"- Unmatched vector count: `{iou_summary.get('unmatched_vector_count')}`",
        f"- Average IoU: `{iou_summary.get('avg_iou')}`",
        f"- Object type summary: `{iou_summary.get('object_type_summary')}`",
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
