from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

from src.pdf_raster.pdf_raster_analysis import normalize_bbox, pixel_bbox_to_pdf_bbox
from src.workers.provenance import build_provenance


class OCRTextRegionAnalyzer:
    backend_id = 'ocr_text_region_analysis'

    def availability(self) -> dict[str, dict[str, Any]]:
        return {
            'paddleocr': _available('paddleocr'),
            'pymupdf_rendered_images': {'available': True, 'module': 'workspace', 'reason': 'workspace image discovery'},
        }

    def analyze_workspace(self, workspace: str | Path, *, max_images: int = 20, language: str = 'korean') -> dict[str, Any]:
        base = Path(workspace)
        base.mkdir(parents=True, exist_ok=True)
        availability = self.availability()
        image_paths = _discover_rendered_images(base)[:max_images]
        contracts = _load_page_contracts(base)
        regions: list[dict[str, Any]] = []
        warnings: list[str] = []

        if not image_paths:
            warnings.append('no rendered images discovered; run pdf_raster worker first')

        if availability['paddleocr']['available'] and image_paths:
            try:
                regions.extend(_run_paddleocr(image_paths, contracts, language=language))
            except Exception as exc:
                warnings.append(f'paddleocr failed: {exc}')
        elif not availability['paddleocr']['available']:
            warnings.append('paddleocr unavailable')

        provenance = build_provenance(
            workspace=base,
            backend=self.backend_id,
            algorithm='paddleocr_text_regions_with_pdf_coordinate_contract',
            source_artifacts=[str(path) for path in image_paths] + [str(base / 'PDF_COORDINATE_CONTRACT.json')],
            worker_name='ocr_text_region',
        )
        payload = {
            'backend': self.backend_id,
            'source': 'paddleocr',
            'language': language,
            'image_count': len(image_paths),
            'region_count': len(regions),
            'regions': regions,
            'availability': availability,
            'warnings': warnings,
            'provenance': provenance,
        }
        (base / 'OCR_TEXT_REGIONS.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        report_path = base / 'OCR_REGION_REPORT.md'
        result = {
            'backend': self.backend_id,
            'status': 'ok' if regions else 'warning',
            'workspace': str(base),
            'image_count': len(image_paths),
            'region_count': len(regions),
            'availability': availability,
            'artifacts': [str(base / 'OCR_TEXT_REGIONS.json'), str(report_path)],
            'warnings': warnings,
            'provenance': provenance,
        }
        report_path.write_text(_markdown(result), encoding='utf-8')
        return result


def write_ocr_text_regions(workspace: str | Path, *, max_images: int = 20, language: str = 'korean') -> dict[str, Any]:
    base = Path(workspace)
    result = OCRTextRegionAnalyzer().analyze_workspace(base, max_images=max_images, language=language)
    (base / 'OCR_REGION_ANALYSIS.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result


def _available(module_name: str) -> dict[str, Any]:
    spec = importlib.util.find_spec(module_name)
    return {'available': spec is not None, 'module': module_name, 'reason': 'installed' if spec is not None else 'not installed'}


def _discover_rendered_images(base: Path) -> list[Path]:
    image_dir = base / 'pdf_raster' / 'rendered'
    images: list[Path] = []
    if image_dir.exists():
        for pattern in ('*.png', '*.jpg', '*.jpeg'):
            images.extend(sorted(image_dir.glob(pattern)))
    if not images:
        for pattern in ('*.png', '*.jpg', '*.jpeg'):
            images.extend(sorted(base.rglob(pattern)))
    return [path for path in images if path.is_file()]


def _load_page_contracts(base: Path) -> dict[str, dict[str, Any]]:
    path = base / 'PDF_COORDINATE_CONTRACT.json'
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}
    contracts: dict[str, dict[str, Any]] = {}
    for page in payload.get('pages') or []:
        cid = str(page.get('page_contract_id') or '')
        if cid:
            contracts[cid] = page
    return contracts


def _infer_contract_for_image(image_path: Path, contracts: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    stem = image_path.stem
    for cid, contract in contracts.items():
        source_stem = Path(str(contract.get('source_pdf') or '')).stem
        page_index = int(contract.get('page_index') or 0) + 1
        if stem.startswith(f'{source_stem}_p{page_index}_') or cid.replace(':', '_') in stem:
            return contract
    if len(contracts) == 1:
        return next(iter(contracts.values()))
    return None


def _run_paddleocr(image_paths: list[Path], contracts: dict[str, dict[str, Any]], *, language: str) -> list[dict[str, Any]]:
    from paddleocr import PaddleOCR

    lang = _paddle_language(language)
    ocr = PaddleOCR(use_angle_cls=True, lang=lang)
    rows: list[dict[str, Any]] = []
    for image_path in image_paths:
        contract = _infer_contract_for_image(image_path, contracts)
        result = ocr.ocr(str(image_path), cls=True)
        for line_index, item in enumerate(_iter_paddle_lines(result)):
            points, text, score = item
            pixel_bbox = _points_to_bbox(points)
            pdf_bbox = pixel_bbox_to_pdf_bbox(pixel_bbox, contract) if contract else None
            normalized_bbox = normalize_bbox(pdf_bbox, float(contract.get('page_width_pdf') or 0.0), float(contract.get('page_height_pdf') or 0.0)) if contract and pdf_bbox else None
            rows.append({
                'source_image': str(image_path),
                'source_pdf': contract.get('source_pdf') if contract else None,
                'page_index': contract.get('page_index') if contract else None,
                'page_contract_id': contract.get('page_contract_id') if contract else None,
                'line_index': line_index,
                'text': text,
                'confidence': score,
                'pixel_bbox': pixel_bbox,
                'pdf_bbox': pdf_bbox,
                'normalized_bbox': normalized_bbox,
                'coordinate_space': 'pixel_top_left+pdf_points_top_left' if contract else 'pixel_top_left',
                'points': points,
            })
    return rows


def _paddle_language(language: str) -> str:
    normalized = language.lower().strip()
    if normalized in {'ko', 'kor', 'korean'}:
        return 'korean'
    if normalized in {'en', 'eng', 'english'}:
        return 'en'
    return normalized or 'korean'


def _iter_paddle_lines(result: Any):
    if not result:
        return
    for page in result:
        if not page:
            continue
        for line in page:
            if not line or len(line) < 2:
                continue
            points = line[0]
            payload = line[1]
            if isinstance(payload, (list, tuple)) and len(payload) >= 2:
                text = str(payload[0])
                score = float(payload[1])
            else:
                text = str(payload)
                score = 0.0
            yield points, text, score


def _points_to_bbox(points: Any) -> list[float]:
    xs: list[float] = []
    ys: list[float] = []
    for point in points or []:
        if isinstance(point, (list, tuple)) and len(point) >= 2:
            xs.append(float(point[0]))
            ys.append(float(point[1]))
    if not xs or not ys:
        return [0.0, 0.0, 0.0, 0.0]
    return [min(xs), min(ys), max(xs), max(ys)]


def _markdown(result: dict[str, Any]) -> str:
    availability = result.get('availability') or {}
    lines = [
        '# OCR Region Report',
        '',
        f"- Backend: `{result.get('backend')}`",
        f"- Status: `{result.get('status')}`",
        f"- Image count: `{result.get('image_count')}`",
        f"- OCR region count: `{result.get('region_count')}`",
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
