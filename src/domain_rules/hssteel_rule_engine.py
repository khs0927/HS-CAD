from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from src.domain_rules.models import DomainRuleFinding, DomainRuleKnowledgePack, DraftingActionCandidate


class HSSteelRuleEngine:
    """Rule helper for steel member evidence and correction planning."""

    KEYWORDS = ('H', 'BEAM', 'COLUMN', 'COL', 'STEEL', '철골', '강재', '각관')

    def __init__(self, root: str | Path | None = None):
        self.root = Path(root).expanduser().resolve() if root else None

    def build_knowledge_pack(self) -> DomainRuleKnowledgePack:
        assets = self._catalog_assets() if self.root else []
        return DomainRuleKnowledgePack(
            source='hssteel',
            title='HS-Steel structural drafting rules',
            summary={
                'root': str(self.root) if self.root else '',
                'asset_count': len(assets),
                'by_category': dict(Counter(item.get('category', 'unknown') for item in assets)),
            },
            assets=assets,
            warnings=[] if not self.root or self.root.exists() else [f'HS-Steel root not found: {self.root}'],
        )

    def review_drawing(self, objects: list[dict[str, Any]]) -> tuple[list[DomainRuleFinding], list[DraftingActionCandidate]]:
        findings: list[DomainRuleFinding] = []
        actions: list[DraftingActionCandidate] = []
        steel_like = [item for item in objects if self._looks_like_steel(item)]
        layer_counts = Counter(str(item.get('layer') or '0') for item in objects)
        if steel_like:
            findings.append(
                DomainRuleFinding(
                    source='hssteel',
                    rule_id='HS-MEMBER-001',
                    title='Steel member candidates detected',
                    severity='info',
                    message='Steel-like evidence exists and should be checked against member rules before mutation.',
                    evidence={'count': len(steel_like), 'sample': steel_like[:10]},
                    recommendation='Resolve member identity before placing, moving, or resizing steel objects.',
                )
            )
        if steel_like and not any(token in ' '.join(layer_counts.keys()).upper() for token in ('STEEL', 'BEAM', 'COL')):
            actions.append(
                DraftingActionCandidate(
                    source='hssteel',
                    action_id='HS-ACTION-STEEL-LAYER-REVIEW',
                    title='Prepare steel layer normalization plan',
                    risk='review_required',
                    reason='Steel changes need stable member identity and layer separation.',
                    command_hint='hscad-tool-plan "steel layer normalization" --has-dwg',
                )
            )
        return findings, actions

    def prompt_constraints(self) -> list[str]:
        return [
            'Resolve steel member identity before any steel geometry mutation.',
            'Keep steel edits review-gated and SaveAs-based.',
            'Use member rules before drafting beams, columns, caps, or connection details.',
        ]

    def _catalog_assets(self) -> list[dict[str, Any]]:
        if not self.root or not self.root.exists():
            return []
        rows: list[dict[str, Any]] = []
        for path in self.root.rglob('*'):
            if path.is_file() and path.suffix.lower() in {'.dat', '.txt', '.csv', '.dwg', '.dxf', '.lsp'}:
                rows.append({'name': path.name, 'path': str(path), 'suffix': path.suffix.lower(), 'category': self._infer_category(path)})
        return rows

    def _looks_like_steel(self, item: dict[str, Any]) -> bool:
        haystack = ' '.join(str(item.get(key) or '') for key in ('layer', 'name', 'effective_name', 'text', 'object_name')).upper()
        return any(keyword.upper() in haystack for keyword in self.KEYWORDS)

    @staticmethod
    def _infer_category(path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix in {'.dat', '.csv'}:
            return 'steel-table'
        if suffix in {'.dwg', '.dxf'}:
            return 'steel-block'
        return 'steel-rule'
