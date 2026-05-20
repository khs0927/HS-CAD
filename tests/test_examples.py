from __future__ import annotations

import json
from pathlib import Path

from src.ai.command_parser import parse_command
from src.ai.command_validator import validate_allowed


def test_all_example_commands_are_valid() -> None:
    examples_dir = Path('examples/commands')
    assert examples_dir.exists()
    for path in sorted(examples_dir.glob('*.json')):
        data = json.loads(path.read_text(encoding='utf-8'))
        command = parse_command(data)
        validate_allowed(command)
