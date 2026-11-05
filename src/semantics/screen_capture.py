from __future__ import annotations

import json
import platform
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class ScreenCaptureResult:
    ok: bool
    path: str | None = None
    warning: str | None = None
    metadata: dict[str, Any] | None = None


def capture_screen(path: str | Path = 'outputs/screen_capture.png', region: tuple[int, int, int, int] | None = None) -> ScreenCaptureResult:
    """Capture the current screen using PIL ImageGrab, mss, or pyautogui.

    This is a fallback/assistive workflow only. CAD object classification should
    primarily use DWG object data. Screenshot analysis is useful when COM access
    fails or a user wants to visually document what ZWCAD shows.
    """
    metadata: dict[str, Any] = {
        'timestamp': datetime.now().isoformat(timespec='seconds'),
        'platform': platform.platform(),
        'bbox': list(region) if region else None,
        'method': None,
        'success': False,
        'error': None,
        'note': 'Screen capture is secondary evidence and does not replace CAD object data.',
    }
    try:
        from PIL import ImageGrab  # type: ignore
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        box = None
        if region:
            left, top, width, height = region
            box = (left, top, left + width, top + height)
        image = ImageGrab.grab(bbox=box)
        image.save(out)
        metadata.update({'method': 'PIL.ImageGrab', 'success': True, 'size': list(getattr(image, 'size', []))})
        _write_meta(out, metadata)
        return ScreenCaptureResult(True, path=str(out), metadata=metadata)
    except Exception as pil_exc:
        metadata['error'] = f'PIL.ImageGrab failed: {pil_exc}'

    try:
        import mss  # type: ignore
        from PIL import Image  # type: ignore
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with mss.mss() as sct:
            monitor = {'left': region[0], 'top': region[1], 'width': region[2], 'height': region[3]} if region else sct.monitors[0]
            shot = sct.grab(monitor)
            image = Image.frombytes('RGB', shot.size, shot.rgb)
            image.save(out)
        metadata.update({'method': 'mss', 'success': True, 'size': list(getattr(image, 'size', []))})
        _write_meta(out, metadata)
        return ScreenCaptureResult(True, path=str(out), metadata=metadata)
    except Exception as mss_exc:
        metadata['error'] = f"{metadata.get('error')}; mss failed: {mss_exc}"

    try:
        import pyautogui  # type: ignore
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        image = pyautogui.screenshot(region=region)
        image.save(out)
        metadata.update({'method': 'pyautogui', 'success': True, 'size': list(getattr(image, 'size', []))})
        _write_meta(out, metadata)
        return ScreenCaptureResult(True, path=str(out), metadata=metadata)
    except Exception as exc:
        metadata['error'] = f"{metadata.get('error')}; pyautogui failed: {exc}"
        _write_meta(Path(path), metadata)
        return ScreenCaptureResult(False, warning=metadata['error'], metadata=metadata)


def _find_visible_windows(title_contains: str) -> list[tuple[int, str, tuple[int, int, int, int]]]:
    if platform.system() != 'Windows':
        return []
    import win32gui  # type: ignore

    matches: list[tuple[int, str, tuple[int, int, int, int]]] = []

    def collect(hwnd: int, _extra: object) -> None:
        title = win32gui.GetWindowText(hwnd)
        if win32gui.IsWindowVisible(hwnd) and title_contains.casefold() in title.casefold():
            matches.append((hwnd, title, tuple(int(value) for value in win32gui.GetWindowRect(hwnd))))

    win32gui.EnumWindows(collect, None)
    return matches


def _capture_native_window(
    hwnd: int,
    path: str | Path,
    width: int,
    height: int,
) -> ScreenCaptureResult | None:
    """Use Win32 PrintWindow when another app overlaps the target window."""
    if platform.system() != 'Windows':
        return None
    try:
        import ctypes

        import win32gui  # type: ignore
        import win32ui  # type: ignore
        from PIL import Image  # type: ignore

        window_dc = win32gui.GetWindowDC(hwnd)
        source_dc = win32ui.CreateDCFromHandle(window_dc)
        target_dc = source_dc.CreateCompatibleDC()
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(source_dc, width, height)
        target_dc.SelectObject(bitmap)
        try:
            if not ctypes.windll.user32.PrintWindow(hwnd, target_dc.GetSafeHdc(), 3):
                return None
            info = bitmap.GetInfo()
            bits = bitmap.GetBitmapBits(True)
            image = Image.frombuffer(
                'RGB',
                (info['bmWidth'], info['bmHeight']),
                bits,
                'raw',
                'BGRX',
                0,
                1,
            )
            if image.getbbox() is None:
                return None
            out = Path(path)
            out.parent.mkdir(parents=True, exist_ok=True)
            image.save(out)
            return ScreenCaptureResult(
                True,
                path=str(out),
                metadata={
                    'timestamp': datetime.now().isoformat(timespec='seconds'),
                    'platform': platform.platform(),
                    'method': 'Win32.PrintWindow',
                    'success': True,
                    'size': [width, height],
                },
            )
        finally:
            win32gui.DeleteObject(bitmap.GetHandle())
            target_dc.DeleteDC()
            source_dc.DeleteDC()
            win32gui.ReleaseDC(hwnd, window_dc)
    except Exception:
        return None


def capture_window(
    path: str | Path = 'outputs/window_capture.png',
    *,
    title_contains: str = 'ZWCAD',
) -> ScreenCaptureResult:
    """Capture a visible window without Windows.Graphics.Capture."""
    matches = _find_visible_windows(title_contains)
    if not matches:
        return ScreenCaptureResult(
            False,
            warning=f'no visible window contains {title_contains!r}',
            metadata={'title_contains': title_contains, 'match_count': 0},
        )
    hwnd, title, (left, top, right, bottom) = max(
        matches,
        key=lambda item: max(0, item[2][2] - item[2][0]) * max(0, item[2][3] - item[2][1]),
    )
    width, height = right - left, bottom - top
    if width <= 0 or height <= 0:
        return ScreenCaptureResult(False, warning=f'invalid window bounds for {title!r}')
    result = _capture_native_window(hwnd, path, width, height)
    if result is None:
        result = capture_screen(path, region=(left, top, width, height))
    if result.metadata is not None:
        result.metadata.update(
            {
                'window_handle': hwnd,
                'window_title': title,
                'window_rect': [left, top, right, bottom],
                'native_capture_compatibility': 'PrintWindow/ImageGrab path; does not require IsBorderRequired',
            }
        )
        _write_meta(Path(path), result.metadata)
    return result


def _write_meta(path: Path, metadata: dict[str, Any]) -> None:
    meta_path = path.with_suffix('.meta.json')
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')


def analyze_screen_image(path: str | Path) -> dict[str, Any]:
    """Return lightweight image metadata and optional OpenCV edge statistics.

    We intentionally keep this as a non-authoritative visual aid. It does not
    replace layer/geometry classification.
    """
    p = Path(path)
    if not p.exists():
        return {'ok': False, 'warning': f'Image not found: {p}'}
    result: dict[str, Any] = {'ok': True, 'path': str(p)}
    try:
        from PIL import Image  # type: ignore
        with Image.open(p) as im:
            result['size'] = list(im.size)
            result['mode'] = im.mode
    except Exception as exc:
        result['pil_warning'] = str(exc)
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
        img = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
        if img is not None:
            edges = cv2.Canny(img, 50, 150)
            result['edge_pixel_count'] = int(np.count_nonzero(edges))
            result['edge_density'] = float(np.count_nonzero(edges) / edges.size)
    except Exception as exc:
        result['opencv_warning'] = f'OpenCV unavailable or failed: {exc}'
    return result
