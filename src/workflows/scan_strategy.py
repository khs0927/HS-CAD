from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ScanStrategyStep:
    order: int
    name: str
    backend: str
    purpose: str
    default_enabled: bool
    mutates_drawing: bool = False
    notes: str = ''

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ScanStrategy:
    task: str
    drawing_size_hint: str
    steps: tuple[ScanStrategyStep, ...]
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            'task': self.task,
            'drawing_size_hint': self.drawing_size_hint,
            'steps': [step.to_dict() for step in self.steps],
            'warnings': list(self.warnings),
        }


def plan_scan_strategy(task: str, *, has_dxf: bool = False, object_count_hint: int | None = None) -> ScanStrategy:
    """Plan a read-first scan workflow for HS-CAD.

    Full COM ModelSpace scans should not be the default for large drawings. This
    planner keeps the preferred order explicit: cheap offline or native evidence
    first, then targeted active-CAD inspection only when needed.
    """
    size = _size_hint(object_count_hint)
    steps: list[ScanStrategyStep] = []
    order = 1

    if has_dxf:
        steps.append(
            ScanStrategyStep(
                order=order,
                name='Offline DXF evidence package',
                backend='ezdxf',
                purpose='Build layer/entity/boundary/dimension evidence without opening ZWCAD.',
                default_enabled=True,
            )
        )
        order += 1

    steps.append(
        ScanStrategyStep(
            order=order,
            name='Native or minimal active drawing audit',
            backend='ZWCAD COM minimal/native helper',
            purpose='Collect layer, block, text, and handle indexes before expensive full traversal.',
            default_enabled=True,
            notes='Use targeted scans whenever the evidence already narrows the scope.',
        )
    )
    order += 1

    if object_count_hint is not None and object_count_hint > 50000:
        steps.append(
            ScanStrategyStep(
                order=order,
                name='Experimental PyRx candidate path',
                backend='PyRx/cad-pyrx',
                purpose='Evaluate lower-level traversal for very large modelspaces after local runtime verification.',
                default_enabled=False,
                notes='Metadata-only until the local ZWCAD/PyRx runtime is confirmed.',
            )
        )
        order += 1

    steps.append(
        ScanStrategyStep(
            order=order,
            name='Targeted COM scan',
            backend='ZWCAD COM/ActiveX',
            purpose='Inspect only selected handles, layers, windows, or suspected entities after prefiltering.',
            default_enabled=True,
        )
    )
    order += 1

    steps.append(
        ScanStrategyStep(
            order=order,
            name='Full COM scan fallback',
            backend='ZWCAD COM/ActiveX',
            purpose='Use only for initial baseline, regression verification, or when no cheaper route is sufficient.',
            default_enabled=False,
            notes='Avoid as the default path for object-heavy drawings.',
        )
    )

    warnings = (
        'Analysis stages must not mutate the original DWG.',
        'Mutation tools remain review-gated and SaveAs-based.',
    )
    return ScanStrategy(task=task, drawing_size_hint=size, steps=tuple(steps), warnings=warnings)


def _size_hint(object_count_hint: int | None) -> str:
    if object_count_hint is None:
        return 'unknown'
    if object_count_hint > 50000:
        return 'large'
    if object_count_hint > 10000:
        return 'medium'
    return 'small'
