from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class FusionSignal:
    id: str
    backend: str
    weight: float
    status: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FusionTarget:
    target_type: str
    signals: list[FusionSignal]

    def to_dict(self) -> dict[str, Any]:
        return {
            'target_type': self.target_type,
            'signals': [signal.to_dict() for signal in self.signals],
            'implemented_weight': self.implemented_weight(),
            'planned_weight': self.planned_weight(),
            'deferred_weight': self.deferred_weight(),
        }

    def implemented_weight(self) -> float:
        return round(sum(signal.weight for signal in self.signals if signal.status == 'implemented'), 6)

    def planned_weight(self) -> float:
        return round(sum(signal.weight for signal in self.signals if signal.status.startswith('planned')), 6)

    def deferred_weight(self) -> float:
        return round(sum(signal.weight for signal in self.signals if signal.status == 'deferred'), 6)


class OpenSourceFusionMatrix:
    def __init__(self, config_path: str | Path = 'config/open_source_fusion_matrix.json'):
        self.config_path = Path(config_path)

    def load(self) -> dict[str, Any]:
        return json.loads(self.config_path.read_text(encoding='utf-8'))

    def targets(self) -> list[FusionTarget]:
        payload = self.load()
        rows: list[FusionTarget] = []
        for target in payload.get('targets', []):
            signals = [
                FusionSignal(
                    id=str(signal.get('id') or ''),
                    backend=str(signal.get('backend') or ''),
                    weight=float(signal.get('weight') or 0.0),
                    status=str(signal.get('status') or ''),
                )
                for signal in target.get('signals', [])
            ]
            rows.append(FusionTarget(target_type=str(target.get('target_type') or ''), signals=signals))
        return rows

    def summary(self) -> dict[str, Any]:
        targets = self.targets()
        backend_counts: dict[str, int] = {}
        status_counts: dict[str, int] = {}
        for target in targets:
            for signal in target.signals:
                backend_counts[signal.backend] = backend_counts.get(signal.backend, 0) + 1
                status_counts[signal.status] = status_counts.get(signal.status, 0) + 1
        return {
            'config_path': str(self.config_path),
            'target_count': len(targets),
            'signal_count': sum(len(target.signals) for target in targets),
            'backend_counts': backend_counts,
            'status_counts': status_counts,
            'targets': [target.to_dict() for target in targets],
        }

    def target(self, target_type: str) -> FusionTarget | None:
        for target in self.targets():
            if target.target_type == target_type:
                return target
        return None
