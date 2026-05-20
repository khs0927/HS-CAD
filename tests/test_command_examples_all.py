import json
from pathlib import Path

from src.ai.command_parser import parse_command
from src.ai.command_validator import validate_allowed


def test_all_example_commands_are_valid():
    for path in Path('examples/commands').glob('*.json'):
        data = json.loads(path.read_text(encoding='utf-8'))
        cmd = parse_command(data)
        validate_allowed(cmd)
