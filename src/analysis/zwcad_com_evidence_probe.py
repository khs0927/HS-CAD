import sys
import json
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

class ZWCADCOMEvidenceProbe:
    """Safe probe to collect ZWCAD COM evidence without implementation or mutation."""

    CANDIDATE_PROGIDS = [
        "ZWCAD.Application",
        "ZWCAD.Application.2026",
        "ZWCAD.Application.2025",
        "Zwcad.Application",
        "ZWSoft.ZWCAD.Application"
    ]

    def __init__(self):
        self.evidence = {
            "status": "pending",
            "active_progid": None,
            "candidate_progids": self.CANDIDATE_PROGIDS,
            "connected": False,
            "start_if_needed": False,
            "attach_only": True,
            "zwcad_visible": None,
            "version": None,
            "application_caption": None,
            "documents_count": None,
            "sendcommand_used": False,
            "saveas_used": False,
            "original_dwg_mutated": False,
            "xicad_alias_executed": False,
            "final_live_runner_implemented": False,
            "evidence_type": "zwcad_com_probe_only"
        }

    def collect_evidence(self, attach_only: bool = True, start_if_needed: bool = False, no_document_mutation: bool = True) -> Dict[str, Any]:
        """Collects evidence without performing any unsafe operations."""
        self.evidence["attach_only"] = attach_only
        self.evidence["start_if_needed"] = start_if_needed

        if sys.platform != "win32":
            self.evidence["status"] = "blocked"
            return self.evidence

        try:
            import win32com.client
            import pythoncom
        except ImportError:
            self.evidence["status"] = "insufficient"
            return self.evidence

        connected = False
        active_progid = None
        app = None

        for progid in self.CANDIDATE_PROGIDS:
            try:
                # Try to attach first
                app = win32com.client.GetActiveObject(progid)
                connected = True
                active_progid = progid
                break
            except Exception:
                pass

        if not connected and start_if_needed and not attach_only:
            for progid in self.CANDIDATE_PROGIDS:
                try:
                    # Try to create new instance
                    app = win32com.client.Dispatch(progid)
                    connected = True
                    active_progid = progid
                    break
                except Exception:
                    pass

        self.evidence["connected"] = connected
        if connected and app:
            self.evidence["active_progid"] = active_progid
            try:
                self.evidence["zwcad_visible"] = getattr(app, "Visible", None)
                self.evidence["version"] = getattr(app, "Version", None)
                self.evidence["application_caption"] = getattr(app, "Caption", None)
            except Exception as e:
                logger.warning(f"Error accessing app attributes: {e}")

            try:
                docs = getattr(app, "Documents", None)
                if docs:
                    self.evidence["documents_count"] = getattr(docs, "Count", None)
            except Exception as e:
                logger.warning(f"Error accessing Documents count: {e}")

            self.evidence["status"] = "confirmed"
        else:
            self.evidence["status"] = "insufficient"

        return self.evidence

    def dump_evidence(self, out_path: str):
        """Dump the collected evidence to a JSON file safely."""
        import os
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(self.evidence, f, indent=2)
