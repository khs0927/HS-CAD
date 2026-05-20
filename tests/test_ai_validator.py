from src.ai.command_parser import parse_command
from src.ai.command_validator import validate_allowed

def test_allowed():
    cmd = parse_command({'command':'scan_all','params':{}})
    validate_allowed(cmd)
