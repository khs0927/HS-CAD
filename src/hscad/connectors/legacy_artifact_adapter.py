"""Bridge existing HS-CAD JSON artifacts into the evidence/fusion model.

This module is intentionally review-only. It reads JSON files produced by the
legacy/earlier HS-CAD analyzer pipeline and emits normalized Evidence records.
It never opens CAD applications, never calls COM, and never mutates original DWG
files.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from hscad.core.evidence import Evidence, make_evidence
from hscad.core.models import DrawingEntity, FileizedDrawing

Json = dict[str, Any]

KNOWN_ARTIFACT_KINDS: dict[str, str] = {
    "OPEN_BACKENDS.json": "backend_inventory",
    "CAD_PLATFORMS.json": "cad_platform_inventory",
    "LAYER_SEMANTICS.json": "layer_semantics",
    "LAYER_AUDIT.json": "layer_audit",
    "TEXT_ROLE_INFERENCE.json": "text_role_inference",
    "AREA_ELEMENTS.json": "area_elements",
    "SPATIAL_GRAPH.json": "spatial_graph",
    "SHAPELY_TOPOLOGY.json": "topology_analysis",
    "SHAPELY_AREA_MATCHES.json": "area_cross_validation",
    "CROSS_VALIDATION.json": "cross_validation",
    "FUSION_MATRIX.json": "fusion_matrix",
    "DOMAIN_RULE_RESULTS.json": "domain_rule_results",
    "FILEIZED_DRAWING.json": "fileized_drawing",
    "ANALYSIS_GRAPH.json": "analysis_graph",
    "MAIN_CODE_PIPELINE_RESULT.json": "main_code_pipeline_result",
}


@dataclass(frozen=True)
class LegacyArtifact:
    name: str
    path: str
    kind: str
    payload: Any
    recognized: bool = True

    def to_record(self) -> Json:
        return {
            "name": self.name,
            "path": self.path,
            "kind": self.kind,
            "recognized": self.recognized,
            "payload_type": type(self.payload).__name__,
        }


@dataclass(frozen=True)
class LegacyArtifactBridgeResult:
    source_dir: str
    artifacts: list[LegacyArtifact]
    evidence: list[Evidence]
    warnings: list[str] = field(default_factory=list)

    def to_record(self) -> Json:
        return {
            "source_dir": self.source_dir,
            "artifact_count": len(self.artifacts),
            "evidence_count": len(self.evidence),
            "artifacts": [a.to_record() for a in self.artifacts],
            "evidence": [e.to_record() for e in self.evidence],
            "warnings": self.warnings,
        }

    @property
    def by_kind(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for evidence in self.evidence:
            counts[evidence.kind] = counts.get(evidence.kind, 0) + 1
        return counts


class LegacyArtifactAdapter:
    """Load and normalize existing HS-CAD output JSON files."""

    def __init__(self, max_detail_records: int = 50) -> None:
        self.max_detail_records = max_detail_records

    def discover(self, source_dir: str | Path) -> list[Path]:
        root = Path(source_dir)
        if not root.exists():
            raise FileNotFoundError(f"Legacy artifact directory does not exist: {root}")
        candidates = [p for p in root.glob("*.json") if p.name in KNOWN_ARTIFACT_KINDS]
        return sorted(candidates, key=lambda p: (p.name not in KNOWN_ARTIFACT_KINDS, p.name))

    def load(self, source_dir: str | Path) -> LegacyArtifactBridgeResult:
        root = Path(source_dir)
        artifacts: list[LegacyArtifact] = []
        evidence: list[Evidence] = []
        warnings: list[str] = []
        for path in self.discover(root):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:
                warnings.append(f"failed_to_read:{path.name}:{exc}")
                evidence.append(
                    make_evidence(
                        f"legacy.{path.stem}.read_failed",
                        "legacy_artifact_read_error",
                        f"Failed to read legacy artifact {path.name}",
                        module="hscad.connectors.legacy_artifact_adapter",
                        source_id=str(path),
                        confidence=0.2,
                        reason="json_read_failed",
                        data={"error": str(exc)},
                    )
                )
                continue
            kind = KNOWN_ARTIFACT_KINDS.get(path.name, "unknown_legacy_artifact")
            artifact = LegacyArtifact(path.name, str(path), kind, payload, recognized=path.name in KNOWN_ARTIFACT_KINDS)
            artifacts.append(artifact)
            evidence.extend(self.to_evidence(artifact))
        if not artifacts:
            warnings.append("no_known_legacy_artifacts_found")
            evidence.append(
                make_evidence(
                    "legacy.no_known_artifacts",
                    "legacy_artifact_gap",
                    "No known HS-CAD legacy artifacts were found in the requested directory",
                    module="hscad.connectors.legacy_artifact_adapter",
                    source_id=str(root),
                    confidence=0.25,
                    reason="empty_or_unknown_output_dir",
                    data={"known_names": sorted(KNOWN_ARTIFACT_KINDS)},
                )
            )
        return LegacyArtifactBridgeResult(str(root), artifacts, evidence, warnings)

    def to_evidence(self, artifact: LegacyArtifact) -> list[Evidence]:
        payload = artifact.payload
        evidence: list[Evidence] = [
            make_evidence(
                f"legacy.{artifact.name}.loaded",
                artifact.kind,
                f"Loaded legacy artifact {artifact.name}",
                module="hscad.connectors.legacy_artifact_adapter",
                source_id=artifact.path,
                confidence=0.86,
                reason="known_artifact_loaded",
                data={"artifact": artifact.to_record(), "summary": summarize_payload(payload)},
            )
        ]
        if artifact.name == "FILEIZED_DRAWING.json":
            evidence.extend(self._fileized_drawing_evidence(artifact))
        elif artifact.name == "ANALYSIS_GRAPH.json":
            evidence.extend(self._analysis_graph_evidence(artifact))
        elif artifact.name == "DOMAIN_RULE_RESULTS.json":
            evidence.extend(self._domain_rule_evidence(artifact))
        elif artifact.name == "CROSS_VALIDATION.json":
            evidence.extend(self._cross_validation_evidence(artifact))
        elif artifact.name == "LAYER_SEMANTICS.json":
            evidence.extend(self._layer_semantics_evidence(artifact))
        elif artifact.name == "AREA_ELEMENTS.json":
            evidence.extend(self._area_elements_evidence(artifact))
        elif artifact.name == "TEXT_ROLE_INFERENCE.json":
            evidence.extend(self._text_role_evidence(artifact))
        elif artifact.name == "SHAPELY_TOPOLOGY.json":
            evidence.extend(self._topology_evidence(artifact))
        return evidence

    def _fileized_drawing_evidence(self, artifact: LegacyArtifact) -> list[Evidence]:
        payload = artifact.payload if isinstance(artifact.payload, dict) else {}
        entities = payload.get("entities") if isinstance(payload.get("entities"), list) else []
        warnings = payload.get("warnings") if isinstance(payload.get("warnings"), list) else []
        return [
            make_evidence(
                "legacy.fileized_drawing.entity_summary",
                "fileized_entity_summary",
                f"Legacy fileized drawing contains {len(entities)} entities",
                module="hscad.connectors.legacy_artifact_adapter",
                source_id=artifact.path,
                confidence=0.9 if entities else 0.45,
                reason="entity_count_from_fileized_drawing",
                data={"entity_count": len(entities), "warning_count": len(warnings), "input_path": payload.get("input_path")},
            )
        ]

    def _analysis_graph_evidence(self, artifact: LegacyArtifact) -> list[Evidence]:
        payload = artifact.payload if isinstance(artifact.payload, dict) else {}
        evidence: list[Evidence] = []
        for key in ("layer", "text_roles", "areas", "spatial_graph", "evidence"):
            if key in payload:
                evidence.append(
                    make_evidence(
                        f"legacy.analysis_graph.{key}",
                        "analysis_graph_component",
                        f"Analysis graph includes component: {key}",
                        module="hscad.connectors.legacy_artifact_adapter",
                        source_id=artifact.path,
                        confidence=0.84,
                        reason="component_present",
                        data={"component": key, "summary": summarize_payload(payload.get(key))},
                    )
                )
        return evidence

    def _domain_rule_evidence(self, artifact: LegacyArtifact) -> list[Evidence]:
        payload = artifact.payload
        records = payload if isinstance(payload, list) else payload.get("results", []) if isinstance(payload, dict) else []
        evidence: list[Evidence] = []
        for index, record in enumerate(records[: self.max_detail_records]):
            if not isinstance(record, dict):
                continue
            status = str(record.get("status", "unknown"))
            confidence = _confidence_from_status(status, default=float(record.get("confidence", 0.75) or 0.75))
            evidence.append(
                make_evidence(
                    f"legacy.domain_rule.{record.get('rule_id', index)}",
                    "domain_rule_result",
                    str(record.get("message") or f"Domain rule result: {record.get('rule_id', index)}"),
                    module="hscad.connectors.legacy_artifact_adapter",
                    source_id=artifact.path,
                    confidence=confidence,
                    reason=f"rule_status:{status}",
                    data=record,
                )
            )
        return evidence

    def _cross_validation_evidence(self, artifact: LegacyArtifact) -> list[Evidence]:
        payload = artifact.payload if isinstance(artifact.payload, dict) else {}
        conflicts = payload.get("conflicts") if isinstance(payload.get("conflicts"), list) else []
        recs = payload.get("recommendations") if isinstance(payload.get("recommendations"), list) else []
        evidence: list[Evidence] = []
        for index, conflict in enumerate(conflicts[: self.max_detail_records]):
            evidence.append(
                make_evidence(
                    f"legacy.cross_validation.conflict.{index}",
                    "legacy_conflict",
                    str(conflict.get("message") if isinstance(conflict, dict) else conflict),
                    module="hscad.connectors.legacy_artifact_adapter",
                    source_id=artifact.path,
                    confidence=0.35,
                    reason="legacy_conflict_requires_review",
                    data=conflict if isinstance(conflict, dict) else {"value": conflict},
                )
            )
        if recs:
            evidence.append(
                make_evidence(
                    "legacy.cross_validation.recommendations",
                    "legacy_recommendations",
                    f"Legacy cross-validation contains {len(recs)} recommendations",
                    module="hscad.connectors.legacy_artifact_adapter",
                    source_id=artifact.path,
                    confidence=0.7,
                    reason="recommendations_present",
                    data={"recommendations": recs[: self.max_detail_records]},
                )
            )
        return evidence

    def _layer_semantics_evidence(self, artifact: LegacyArtifact) -> list[Evidence]:
        payload = artifact.payload
        layers = _extract_list_or_mapping(payload, preferred_keys=("layers", "layer_semantics", "items"))
        evidence: list[Evidence] = []
        for index, item in enumerate(layers[: self.max_detail_records]):
            data = item if isinstance(item, dict) else {"value": item}
            layer = str(data.get("layer") or data.get("name") or data.get("layer_name") or index)
            role = str(data.get("role") or data.get("semantic_role") or data.get("category") or "unknown")
            evidence.append(
                make_evidence(
                    f"legacy.layer_semantics.{sanitize_id(layer)}",
                    "layer_semantic_role",
                    f"Layer {layer} inferred as {role}",
                    module="hscad.connectors.legacy_artifact_adapter",
                    source_id=artifact.path,
                    confidence=float(data.get("confidence", 0.74) or 0.74) if isinstance(data, dict) else 0.65,
                    reason="legacy_layer_semantics",
                    data=data,
                )
            )
        return evidence

    def _area_elements_evidence(self, artifact: LegacyArtifact) -> list[Evidence]:
        areas = _extract_list_or_mapping(artifact.payload, preferred_keys=("areas", "area_elements", "items"))
        evidence: list[Evidence] = []
        total = 0.0
        for index, item in enumerate(areas[: self.max_detail_records]):
            data = item if isinstance(item, dict) else {"value": item}
            area = _safe_float(data.get("area") or data.get("computed_area") or data.get("value"), 0.0)
            total += area
            evidence.append(
                make_evidence(
                    f"legacy.area.{data.get('entity_id', index)}",
                    "legacy_area_element",
                    f"Legacy area candidate {index} area={area}",
                    module="hscad.connectors.legacy_artifact_adapter",
                    source_id=artifact.path,
                    confidence=float(data.get("confidence", 0.76) or 0.76) if isinstance(data, dict) else 0.65,
                    reason="legacy_area_element",
                    entity_ids=[str(data.get("entity_id"))] if data.get("entity_id") else [],
                    data=data,
                )
            )
        if areas:
            evidence.append(
                make_evidence(
                    "legacy.area.summary",
                    "legacy_area_summary",
                    f"Legacy area artifact contains {len(areas)} area records",
                    module="hscad.connectors.legacy_artifact_adapter",
                    source_id=artifact.path,
                    confidence=0.8,
                    reason="legacy_area_summary",
                    data={"area_count": len(areas), "sample_total_area": total},
                )
            )
        return evidence

    def _text_role_evidence(self, artifact: LegacyArtifact) -> list[Evidence]:
        texts = _extract_list_or_mapping(artifact.payload, preferred_keys=("text_roles", "texts", "items", "inferences"))
        evidence: list[Evidence] = []
        for index, item in enumerate(texts[: self.max_detail_records]):
            data = item if isinstance(item, dict) else {"value": item}
            role = str(data.get("role") or data.get("text_role") or data.get("category") or "unknown")
            text = str(data.get("text") or data.get("value") or "")
            evidence.append(
                make_evidence(
                    f"legacy.text_role.{index}",
                    "legacy_text_role",
                    f"Legacy text role {role}: {text[:80]}",
                    module="hscad.connectors.legacy_artifact_adapter",
                    source_id=artifact.path,
                    confidence=float(data.get("confidence", 0.72) or 0.72) if isinstance(data, dict) else 0.62,
                    reason="legacy_text_role",
                    data=data,
                )
            )
        return evidence

    def _topology_evidence(self, artifact: LegacyArtifact) -> list[Evidence]:
        payload = artifact.payload if isinstance(artifact.payload, dict) else {}
        issues = _extract_list_or_mapping(payload, preferred_keys=("issues", "warnings", "conflicts", "gaps"))
        if not issues:
            return [
                make_evidence(
                    "legacy.topology.no_explicit_issues",
                    "legacy_topology_summary",
                    "Legacy topology artifact loaded without explicit issue list",
                    module="hscad.connectors.legacy_artifact_adapter",
                    source_id=artifact.path,
                    confidence=0.7,
                    reason="topology_artifact_present",
                    data={"summary": summarize_payload(payload)},
                )
            ]
        evidence: list[Evidence] = []
        for index, issue in enumerate(issues[: self.max_detail_records]):
            data = issue if isinstance(issue, dict) else {"value": issue}
            severity = str(data.get("severity", "warning"))
            evidence.append(
                make_evidence(
                    f"legacy.topology.issue.{index}",
                    "legacy_topology_issue",
                    str(data.get("message") or data.get("value") or f"Topology issue {index}"),
                    module="hscad.connectors.legacy_artifact_adapter",
                    source_id=artifact.path,
                    confidence=0.35 if severity.lower() in {"error", "critical"} else 0.55,
                    reason=f"topology_issue:{severity}",
                    data=data,
                )
            )
        return evidence

    def drawing_from_fileized_artifact(self, bridge: LegacyArtifactBridgeResult) -> FileizedDrawing:
        for artifact in bridge.artifacts:
            if artifact.name == "FILEIZED_DRAWING.json" and isinstance(artifact.payload, dict):
                return fileized_drawing_from_payload(artifact.payload)
        return FileizedDrawing(
            input_path=bridge.source_dir,
            source_format="legacy_artifact_dir",
            entities=[],
            metadata={"artifact_count": len(bridge.artifacts), "source": "legacy_artifact_adapter"},
            evidence=bridge.evidence,
            warnings=bridge.warnings,
        )


def fileized_drawing_from_payload(payload: Json) -> FileizedDrawing:
    entities: list[DrawingEntity] = []
    raw_entities = payload.get("entities") if isinstance(payload.get("entities"), list) else []
    for index, record in enumerate(raw_entities):
        if not isinstance(record, dict):
            continue
        geometry = record.get("geometry") if isinstance(record.get("geometry"), dict) else {}
        raw = record.get("raw") if isinstance(record.get("raw"), dict) else {}
        try:
            confidence = float(record.get("confidence", 1.0) or 1.0)
        except Exception:
            confidence = 1.0
        entities.append(
            DrawingEntity(
                entity_id=str(record.get("entity_id") or record.get("id") or f"LEGACY-{index:06d}"),
                entity_type=str(record.get("entity_type") or record.get("type") or "UNKNOWN"),
                layer=str(record.get("layer") or "0"),
                geometry=geometry,
                text=record.get("text") if record.get("text") is not None else None,
                raw=raw,
                confidence=confidence,
                source=str(record.get("source") or payload.get("input_path") or "legacy_fileized_drawing"),
            )
        )
    return FileizedDrawing(
        input_path=str(payload.get("input_path") or "legacy_fileized_drawing"),
        source_format=str(payload.get("source_format") or "legacy"),
        entities=entities,
        metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
        evidence=payload.get("evidence") if isinstance(payload.get("evidence"), list) else [],
        warnings=payload.get("warnings") if isinstance(payload.get("warnings"), list) else [],
        converted_path=payload.get("converted_path"),
    )


def summarize_payload(payload: Any) -> Json:
    if isinstance(payload, dict):
        return {
            "type": "dict",
            "keys": sorted(str(k) for k in payload.keys())[:25],
            "size": len(payload),
        }
    if isinstance(payload, list):
        return {"type": "list", "size": len(payload), "sample_type": type(payload[0]).__name__ if payload else None}
    return {"type": type(payload).__name__, "value_preview": str(payload)[:120]}


def _extract_list_or_mapping(payload: Any, preferred_keys: Iterable[str]) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in preferred_keys:
            value = payload.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                return [{"name": k, **v} if isinstance(v, dict) else {"name": k, "value": v} for k, v in value.items()]
        # Common pattern: mapping of IDs to result objects.
        if payload and all(isinstance(v, (dict, str, int, float, bool, type(None))) for v in payload.values()):
            return [{"name": k, **v} if isinstance(v, dict) else {"name": k, "value": v} for k, v in payload.items()]
    return []


def _confidence_from_status(status: str, default: float) -> float:
    s = status.lower()
    if s in {"pass", "passed", "ok", "success"}:
        return 0.88
    if s in {"fail", "failed", "error", "critical"}:
        return 0.3
    if s in {"warning", "warn", "review", "manual_review"}:
        return 0.52
    return max(0.0, min(1.0, default))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def sanitize_id(value: str) -> str:
    out = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in value.strip())
    return out or "unknown"
