'''XiCAD taxonomy parsing and searching utilities.

This module parses XiCAD shortkey files (the official xiShortkey_origin.key and the
user specific xiShortkey.key) and builds a searchable taxonomy of commands.
It provides lightweight data structures that the rest of the HS-CAD orchestrator
can use without loading the full protected LISP files.
'''  

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Iterable, Optional

from .xicad_safety_policy import classify_xicad_risk

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class XiCADCommand:
    """Immutable representation of a XiCAD command entry.

    Attributes
    ----------
    section: str
        The section name taken from the shortkey file (e.g. ``SecDraw``).
    alias: str
        The short alias used on the keyboard (e.g. ``WAL``).
    function: str
        The actual LISP function name (e.g. ``xiDrawWall``).
    description: str
        Human readable description from the shortkey file.
    category: str
        High-level functional category (DRAW_ARCH, DRAW_STRUCT, ...).
    risk: str
        Risk classification (SAFE_LOOKUP, INTERACTIVE_PREVIEW, REVIEW_REQUIRED,
        HIGH_RISK, BLOCKED).
    keywords: Tuple[str, ...]
        Tokenised words used for simple keyword search.
    source_file: str
        Path of the origin shortkey file (for debugging).
    """

    section: str
    alias: str
    function: str
    description: str
    category: str
    risk: str
    keywords: Tuple[str, ...]
    source_file: str

# ---------------------------------------------------------------------------
# Helper functions - file reading with fallback encodings
# ---------------------------------------------------------------------------

def _read_lines_safe(file_path: Path) -> List[str]:
    """Read a text file trying common Korean encodings.

    Parameters
    ----------
    file_path: Path
        Path to the file.

    Returns
    -------
    List[str]
        List of stripped lines. Empty list if the file does not exist.
    """
    if not file_path.exists():
        return []
    encodings = ["cp949", "utf-8", "euc-kr", "latin1"]
    for enc in encodings:
        try:
            return [ln.rstrip('\n') for ln in file_path.read_text(encoding=enc).splitlines()]
        except Exception:
            continue
    return []

# ---------------------------------------------------------------------------
# Category classification
# ---------------------------------------------------------------------------

# Mapping of shortkey sections to our high-level categories.
_SECTION_TO_CATEGORY = {
    "SecDraw": "DRAW_ARCH",
    "SecLayer": "LAYER_MANAGE",
    "SecShape": "EDIT_GEOM",
    "SecArea": "AREA_QTY",
    "SecBlock": "BLOCK_SYMBOL",
    "SecMulti": "EDIT_GEOM",
    "SecTxt1": "TEXT_DIM",
    "SecDim": "TEXT_DIM",
    "SecHatch": "HATCH",
    "SecPlot": "PLOT",
    "SecCut": "EDIT_GEOM",
    "SecPaper": "PAPER_PLOT",
}

def _classify_category(section: str, alias: str, description: str) -> str:
    """Return a high-level category for a command.

    If the section is unknown, fall back to ``UNKNOWN``.
    """
    return _SECTION_TO_CATEGORY.get(section, "UNKNOWN")

def _classify_risk(alias: str, description: str) -> str:
    """Classify risk through the centralized XiCAD safety policy."""
    return classify_xicad_risk(alias, description=description)

def _extract_keywords(text: str) -> Tuple[str, ...]:
    # Split on non-alphanumeric Korean/ASCII characters, lower-case.
    tokens = re.split(r"[\W_]+", text.lower())
    return tuple(t for t in tokens if t)

# ---------------------------------------------------------------------------
# Core parsing logic
# ---------------------------------------------------------------------------

def parse_xicad_shortkey(file_path: Path) -> List[XiCADCommand]:
    """Parse a XiCAD shortkey file into a list of :class:`XiCADCommand`.

    The shortkey file format is roughly::

        WAL ; xiDrawWall ; 벽 그리기
        D1  ; xiDoor1    ; 간단문 그리기

    Empty lines and comment lines (starting with ``;``) are ignored.
    """
    lines = _read_lines_safe(file_path)
    commands: List[XiCADCommand] = []
    current_section: str = "UNKNOWN"
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        # Section change - lines that start with *SecXXX (no ';')
        if line.startswith("*Sec"):
            # e.g. "*SecDraw" - we keep the suffix as the section name.
            current_section = line.lstrip("*")
            continue
        # Skip comment lines that start with ';'
        if line.startswith(";"):
            continue
        # Expected format: alias ; function ; description (description optional)
        parts = [p.strip() for p in line.split(";")]
        if len(parts) < 2:
            continue
        alias = parts[0]
        function = parts[1]
        description = parts[2] if len(parts) >= 3 else ""
        category = _classify_category(current_section, alias, description)
        risk = _classify_risk(alias, description)
        keywords = _extract_keywords(f"{alias} {function} {description}")
        commands.append(
            XiCADCommand(
                section=current_section,
                alias=alias,
                function=function,
                description=description,
                category=category,
                risk=risk,
                keywords=keywords,
                source_file=str(file_path),
            )
        )
    return commands

def build_xicad_taxonomy(xicad_root: str | Path = "C:/xicad") -> List[XiCADCommand]:
    """Build the full taxonomy from a XiCAD installation.

    The function looks for two possible shortkey files (the official one and the
    user-specific one). If neither exists, an empty list is returned - callers
    should handle the empty case (e.g. by using a fixture during tests).
    """
    root = Path(xicad_root)
    origin = root / "Lisp" / "xiShortkey_origin.key"
    user = root / "xiLib" / "xiShortkey.key"
    commands_by_alias: dict[str, XiCADCommand] = {}
    for p in (origin, user):
        if p.exists():
            for command in parse_xicad_shortkey(p):
                commands_by_alias[command.alias.upper()] = command
    return list(commands_by_alias.values())

# ---------------------------------------------------------------------------
# Simple search API - keyword matching & optional category filter
# ---------------------------------------------------------------------------

def search_xicad_commands(
    query: str,
    category: Optional[str] = None,
    limit: int = 12,
    taxonomy: Optional[Iterable[XiCADCommand]] = None,
) -> List[XiCADCommand]:
    """Search the taxonomy for commands matching ``query``.

    Parameters
    ----------
    query: str
        Free-text search string.
    category: Optional[str]
        If supplied, only commands whose ``category`` matches (case-insensitive)
        are considered.
    limit: int
        Maximum number of results.
    taxonomy: Optional[Iterable[XiCADCommand]]
        Pre-computed taxonomy - if ``None`` the function will call
        :func:`build_xicad_taxonomy` with the default root.
    """
    if taxonomy is None:
        taxonomy = build_xicad_taxonomy()
    query_tokens = set(_extract_keywords(query))
    candidates: List[Tuple[int, XiCADCommand]] = []
    for cmd in taxonomy:
        if category and cmd.category.upper() != category.upper():
            continue
        # Simple token overlap plus substring matching for Korean compound nouns
        # such as "단열" vs. "단열재".
        match_score = 0
        for query_token in query_tokens:
            for keyword in cmd.keywords:
                if query_token == keyword:
                    match_score += 2
                    break
                if query_token in keyword or keyword in query_token:
                    match_score += 1
                    break
        if match_score:
            candidates.append((match_score, cmd))
    # Sort by descending score, then alphabetically by alias.
    candidates.sort(key=lambda x: (-x[0], x[1].alias))
    return [c[1] for c in candidates[:limit]]

# ---------------------------------------------------------------------------
# Convenience: build a markdown block for VLM prompts
# ---------------------------------------------------------------------------

def build_xicad_prompt_context(
    query: str,
    category: Optional[str] = None,
    limit: int = 12,
    xicad_root: str | Path = "C:/xicad",
) -> str:
    """Return a Markdown string that can be inserted into a VLM prompt.

    The block lists the top matching commands and a short set of usage rules.
    """
    matches = search_xicad_commands(query, category, limit, taxonomy=build_xicad_taxonomy(xicad_root))
    if not matches:
        return "[XiCAD] No matching commands found."
    lines = ["[XiCAD Candidate Commands]"]
    for cmd in matches:
        lines.append(
            f"- {cmd.alias:<4} / {cmd.function:<12} / {cmd.description or '-'} / risk={cmd.risk}"
        )
    lines.append("\nRules:")
    lines.append("- Do not fabricate XiCAD commands; use only the listed aliases/functions.")
    lines.append("- High-risk or BLOCKED commands require explicit human review and must not be auto-executed.")
    lines.append("- If a command lacks a verified recipe, treat it as a *plan* (no script will be generated).")
    return "\n".join(lines)
