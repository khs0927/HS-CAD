from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RouteDefaults:
    source_root: str | None
    workspace: str
    sample: int
    limit: int
    full_run_requested: bool
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_route_defaults(
    user_prompt: str,
    source_path: str | Path | None,
    *,
    workspace: str | Path | None = None,
    sample: int | None = None,
    limit: int | None = None,
) -> RouteDefaults:
    source = Path(source_path) if source_path else None
    source_root = _source_root(source)
    full = _full_run_requested(user_prompt)
    warnings: list[str] = []

    resolved_sample = 20 if sample is None else max(0, sample)
    resolved_limit = 20 if limit is None else max(0, limit)
    if full and sample is None and limit is None:
        warnings.append('Full run was requested, but route planning keeps sample/limit at 20 by default. Raise them manually after sample QA passes.')

    resolved_workspace = str(workspace) if workspace else str(_workspace_from_source(user_prompt, source))
    return RouteDefaults(
        source_root=str(source_root) if source_root else None,
        workspace=resolved_workspace,
        sample=resolved_sample,
        limit=resolved_limit,
        full_run_requested=full,
        warnings=warnings,
    )


def _source_root(source: Path | None) -> Path | None:
    if source is None:
        return None
    if source.suffix:
        return source.parent
    return source


def _workspace_from_source(user_prompt: str, source: Path | None) -> Path:
    base = Path('outputs') / 'routed_corpus'
    seed = str(source) if source else user_prompt
    stem = source.stem if source and source.suffix else (source.name if source else 'task')
    slug = _slug(stem or 'task')
    digest = hashlib.sha1(seed.encode('utf-8')).hexdigest()[:8]
    return base / f'{slug}_{digest}'


def _slug(text: str) -> str:
    value = re.sub(r'[^0-9A-Za-z가-힣_-]+', '_', text).strip('_')
    return value[:40] or 'task'


def _full_run_requested(user_prompt: str) -> bool:
    text = user_prompt.lower()
    return any(token in text for token in ('전체', '전부', '모두', 'all', 'full', 'everything'))
