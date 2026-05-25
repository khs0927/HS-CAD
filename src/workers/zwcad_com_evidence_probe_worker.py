from typing import Dict, Any
from src.analysis.zwcad_com_evidence_probe import ZWCADCOMEvidenceProbe

def process(context: Dict[str, Any]) -> Dict[str, Any]:
    """Worker wrapper for ZWCAD COM Evidence Probe."""
    probe = ZWCADCOMEvidenceProbe()
    attach_only = context.get("attach_only", True)
    start_if_needed = context.get("start_if_needed", False)
    no_document_mutation = context.get("no_document_mutation", True)

    evidence = probe.collect_evidence(
        attach_only=attach_only,
        start_if_needed=start_if_needed,
        no_document_mutation=no_document_mutation
    )
    return evidence
