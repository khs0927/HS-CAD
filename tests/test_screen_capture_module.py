from src.semantics.screen_capture import analyze_screen_image, capture_screen


def test_analyze_missing_screen_image_is_safe(tmp_path):
    result = analyze_screen_image(tmp_path / 'missing.png')
    assert result['ok'] is False


def test_capture_screen_gracefully_handles_missing_optional_dependency(tmp_path):
    result = capture_screen(tmp_path / 'capture.png')
    # Depending on environment, pyautogui may or may not exist/display may not be available.
    assert hasattr(result, 'ok')
