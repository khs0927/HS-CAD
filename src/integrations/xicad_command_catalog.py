from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterable


@dataclass(frozen=True)
class XiCADCommand:
    alias: str
    function: str
    description: str = ""
    section: str = ""


def read_text_korean(path: str | Path) -> str:
    data = Path(path).read_bytes()
    for enc in ("utf-8-sig", "cp949", "euc-kr", "utf-8", "latin1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("latin1", errors="ignore")


def parse_xicad_shortkey(path: str | Path) -> list[XiCADCommand]:
    """Parse XiCAD Lisp/xiShortkey_origin.key into command metadata.

    The file uses lines like:
        WAL ;xiDrawWall ;벽 그리기
    """
    text = read_text_korean(path)
    commands: list[XiCADCommand] = []
    section = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("*Sec"):
            section = line[1:].strip()
            continue
        if line.startswith(";") or ";" not in line:
            continue
        parts = [p.strip() for p in line.split(";")]
        alias = parts[0]
        if not alias or not re.match(r"^[A-Za-z0-9_\-]+$", alias):
            continue
        function = parts[1] if len(parts) > 1 else ""
        description = ";".join(parts[2:]).strip() if len(parts) > 2 else ""
        commands.append(XiCADCommand(alias=alias, function=function, description=description, section=section))
    return commands


def filter_architecture_commands(commands: Iterable[XiCADCommand]) -> list[XiCADCommand]:
    preferred = {
        "STT", "COL", "CLI", "BLI", "BLS", "BE", "STB", "D1", "D2", "D3",
        "W1", "W2", "W3", "CW", "WO", "WAL", "INS", "ELV", "EED", "EPD",
        "STP", "STC", "PK", "SCB", "PZ", "DEV", "CEN", "CEP", "HGRID",
        "C2E", "E2C", "TAJ", "TB", "SEB", "SER", "SE", "FLT",
    }
    return [cmd for cmd in commands if cmd.alias.upper() in preferred]


def command_table_rows(commands: Iterable[XiCADCommand]) -> list[dict[str, str]]:
    return [
        {
            "alias": cmd.alias,
            "function": cmd.function,
            "description": cmd.description,
            "section": cmd.section,
        }
        for cmd in commands
    ]
