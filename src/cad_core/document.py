from __future__ import annotations
from dataclasses import dataclass

@dataclass
class CADDocumentRef:
    path: str | None = None
    name: str | None = None
