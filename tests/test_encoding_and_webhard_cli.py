from pathlib import Path


from src.app.cli import app
from src.utils.encoding import ensure_utf8_stdio


def test_utf8_stdio_guard_does_not_raise():
    ensure_utf8_stdio()


def test_webhard_cli_registered():
    commands = app.registered_commands
    names = {command.name for command in commands}
    assert 'hscad-webhard-sample' in names


def test_korean_webhard_path_assembly():
    root = Path('Z:/') / '내 드라이브' / '#웹하드'
    assert str(root).replace('\\', '/').endswith('내 드라이브/#웹하드')
