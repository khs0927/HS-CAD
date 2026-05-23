from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from src.domain_rules.models import DomainRuleFinding, DomainRuleKnowledgePack, DraftingActionCandidate


class ArchiOfficeRuleEngine:
    """ArchiOffice-style architectural drafting rule interpreter.

    This engine is intentionally conservative. It does not reverse engineer or
    execute proprietary ArchiOffice commands. It builds a local rule knowledge
    layer from folders, block names, layer names, and scanned drawing evidence so
    HS-CAD can decide what should be corrected before sending any CAD command.
    """

    def __init__(self, root: str | Path | None = None):
        self.root = Path(root).expanduser().resolve() if root else None

    def build_knowledge_pack(self) -> DomainRuleKnowledgePack:
        assets = self._catalog_assets() if self.root else []
        summary = {
            'root': str(self.root) if self.root else '',
            'asset_count': len(assets),
            'by_category': dict(Counter(item.get('category', 'unknown') for item in assets)),
        }
        warnings: list[str] = []
        if self.root and not self.root.exists():
            warnings.append(f'ArchiOffice root not found: {self.root}')
        return DomainRuleKnowledgePack(
            source='archioffice',
            title='ArchiOffice architectural drafting rules',
            summary=summary,
            assets=assets,
            warnings=warnings,
        )

    def review_drawing(self, objects: list[dict[str, Any]]) -> tuple[list[DomainRuleFinding], list[DraftingActionCandidate]]:
        findings: list[DomainRuleFinding] = []
        actions: list[DraftingActionCandidate] = []
        layer_counts = Counter(str(item.get('layer') or '0') for item in objects)
        text_like = [item for item in objects if str(item.get('entity_type') or item.get('object_name') or '').upper() in {'TEXT', 'MTEXT'}]
        if not any(layer.upper().startswith(('WAL', 'COL', 'DOOR', 'WIN', 'DIM', 'CEN')) for layer in layer_counts):
            findings.append(
                DomainRuleFinding(
                    source='archioffice',
                    rule_id='AO-LAYER-001',
                    title='Architecture layer scheme is weak or missing',
                    severity='warning',
                    message='No HS-CAD architecture semantic layer prefix was detected in the scanned objects.',
                    evidence={'layer_counts': dict(layer_counts)},
                    recommendation='Run a layer normalization review before modification.',
                )
            )
            actions.append(
                DraftingActionCandidate(
                    source='archioffice',
                    action_id='AO-ACTION-LAYER-REVIEW',
                    title='Prepare layer normalization plan',
                    risk='review_required',
                    reason='Architecture drafting tools need stable semantic layers before safe modification.',
                    command_hint='hscad-tool-plan "layer normalization" --has-dwg',
                )
            )
        if len(text_like) == 0:
            findings.append(
                DomainRuleFinding(
                    source='archioffice',
                    rule_id='AO-TEXT-001',
                    title='No note/text evidence detected',
                    severity='info',
                    message='No TEXT/MTEXT evidence was found. Room names, material notes, and finish notes may need OCR/vector fusion.',
                    evidence={'text_count': 0},
                    recommendation='Use OCR/vector evidence before changing rooms, finishes, or door/window annotations.',
                )
            )
        return findings, actions

    def prompt_constraints(self) -> list[str]:
        return [
            'Respect semantic architecture layers before generating or modifying objects.',
            'Do not rename or merge architectural layers without a review table.',
            'Use ArchiOffice-style architectural consistency checks before geometry mutation.',
        ]

    def _catalog_assets(self) -> list[dict[str, Any]]:
        if not self.root or not self.root.exists():
            return []
        rows: list[dict[str, Any]] = []
        for path in self.root.rglob('*'):
            if not path.is_file():
                continue
            suffix = path.suffix.lower()
            if suffix not in {'.dwg', '.dxf', '.lsp', '.fas', '.zelx', '.dat', '.txt', '.cfg'}:
                continue
            rows.append(
                {
                    'name': path.name,
                    'path': str(path),
                    'suffix': suffix,
                    'category': self._infer_category(path),
                }
            )
        return rows

    @staticmethod
    def _infer_category(path: Path) -> str:
        name = path.name.lower()
        if 'door' in name or '문' in name:
            return 'door'
        if 'win' in name or '창' in name:
            return 'window'
        if 'wall' in name or '벽' in name:
            return 'wall'
        if 'stair' in name or '계단' in name:
            return 'stair'
        if path.suffix.lower() == '.dwg':
            return 'block-library'
        return 'general'
