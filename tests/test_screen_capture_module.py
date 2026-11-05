from src.semantics import screen_capture
from src.semantics.screen_capture import (
    ScreenCaptureResult,
    analyze_screen_image,
    capture_screen,
    capture_window,
)


def test_analyze_missing_screen_image_is_safe(tmp_path):
    result = analyze_screen_image(tmp_path / 'missing.png')
    assert result['ok'] is False


def test_capture_screen_gracefully_handles_missing_optional_dependency(tmp_path):
    result = capture_screen(tmp_path / 'capture.png')
    # Depending on environment, pyautogui may or may not exist/display may not be available.
    assert hasattr(result, 'ok')


def test_capture_window_uses_compatible_fallback_region(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setattr(
        screen_capture,
        '_find_visible_windows',
        lambda _title: [(101, 'ZWCAD 2026 - [Drawing1.dwg]', (10, 20, 810, 620))],
    )
    monkeypatch.setattr(screen_capture, '_capture_native_window', lambda *_args: None)

    def fake_capture(path, region=None):
        captured['path'], captured['region'] = path, region
        return ScreenCaptureResult(True, path=str(path), metadata={})

    monkeypatch.setattr(screen_capture, 'capture_screen', fake_capture)
    result = capture_window(tmp_path / 'zwcad.png')
    assert result.ok
    assert captured['region'] == (10, 20, 800, 600)
    assert result.metadata['window_title'].startswith('ZWCAD 2026')
    assert 'IsBorderRequired' in result.metadata['native_capture_compatibility']


def test_capture_window_rejects_missing_match(monkeypatch, tmp_path):
    monkeypatch.setattr(screen_capture, '_find_visible_windows', lambda _title: [])
    result = capture_window(tmp_path / 'zwcad.png')
    assert not result.ok
    assert 'no visible window' in result.warning


def test_capture_window_prefers_largest_matching_window(monkeypatch, tmp_path):
    observed = {}
    monkeypatch.setattr(
        screen_capture,
        '_find_visible_windows',
        lambda _title: [
            (1, 'ZWCAD text window', (100, 100, 500, 400)),
            (2, 'ZWCAD 2026 main', (0, 0, 1920, 1040)),
        ],
    )
    monkeypatch.setattr(screen_capture, '_capture_native_window', lambda *_args: None)

    def fake_capture(path, region=None):
        observed['region'] = region
        return ScreenCaptureResult(True, path=str(path), metadata={})

    monkeypatch.setattr(screen_capture, 'capture_screen', fake_capture)
    result = capture_window(tmp_path / 'zwcad.png')
    assert result.ok
    assert observed['region'] == (0, 0, 1920, 1040)
    assert result.metadata['window_handle'] == 2
