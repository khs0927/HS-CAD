from __future__ import annotations

from enum import Enum


class WorkflowStep(str, Enum):
    SELECT_DWG = "select_dwg"
    SELECT_XICAD = "select_xicad"
    SCAN = "scan"
    ANALYZE = "analyze"
    PREVIEW = "preview"
    EXECUTE = "execute"
    POST_SCAN = "post_scan"
    REPORT = "report"
