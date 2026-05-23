from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from src.orchestrator.route_defaults import build_route_defaults


@dataclass
class RoutedTool:
    name: str
    command: str
    reason: str
    stage: str
    review_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TaskRoute:
    user_prompt: str
    source_path: str | None
    source_extension: str | None
    intent: str
    pipeline: str
    tools: list[RoutedTool]
    workspace: str | None = None
    sample: int | None = None
    limit: int | None = None
    source_root: str | None = None
    warnings: list[str] = field(default_factory=list)
    missing_context: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            'user_prompt': self.user_prompt,
            'source_path': self.source_path,
            'source_extension': self.source_extension,
            'intent': self.intent,
            'pipeline': self.pipeline,
            'workspace': self.workspace,
            'sample': self.sample,
            'limit': self.limit,
            'source_root': self.source_root,
            'tools': [tool.to_dict() for tool in self.tools],
            'warnings': self.warnings,
            'missing_context': self.missing_context,
        }


class TaskRouter:
    def route(
        self,
        user_prompt: str,
        source_path: str | Path | None = None,
        *,
        workspace: str | Path | None = None,
        sample: int | None = None,
        limit: int | None = None,
    ) -> TaskRoute:
        text = user_prompt.lower()
        source = str(source_path) if source_path else None
        ext = Path(source).suffix.lower() if source else None
        defaults = build_route_defaults(user_prompt, source_path, workspace=workspace, sample=sample, limit=limit)
        intent = self._intent(text, ext)
        pipeline = self._pipeline(intent)
        tools = self._tools(pipeline, defaults.source_root, defaults.workspace, defaults.sample, defaults.limit)
        warnings: list[str] = list(defaults.warnings)
        missing: list[str] = []
        if not source and pipeline != 'safe_inspection':
            missing.append('source_path is required for this route')
        if ext == '.dwg':
            warnings.append('DWG bulk import should use SaveAs DXF plus ezdxf, not COM ModelSpace iteration.')
        return TaskRoute(
            user_prompt=user_prompt,
            source_path=source,
            source_extension=ext,
            intent=intent,
            pipeline=pipeline,
            tools=tools,
            workspace=defaults.workspace,
            sample=defaults.sample,
            limit=defaults.limit,
            source_root=defaults.source_root,
            warnings=warnings,
            missing_context=missing,
        )

    def _intent(self, text: str, ext: str | None) -> str:
        if ext == '.ifc' or _has(text, ('ifc', 'bim', '물량')):
            return 'bim_extract'
        if ext == '.dwg' or 'dwg' in text:
            return 'dwg_index'
        if ext == '.dxf' or 'dxf' in text:
            return 'dxf_index'
        if ext == '.pdf' or 'pdf' in text:
            return 'pdf_extract'
        if ext in {'.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff'} or _has(text, ('이미지', '스캔', '도면화', 'floorplan')):
            return 'image_to_cad'
        if _has(text, ('공간', '인접', '연결', '경로')):
            return 'spatial_graph'
        return 'safe_inspection'

    def _pipeline(self, intent: str) -> str:
        return {
            'dwg_index': 'dwg_bulk_index',
            'dxf_index': 'dxf_index',
            'pdf_extract': 'pdf_index',
            'image_to_cad': 'image_analysis',
            'bim_extract': 'ifc_bim',
            'spatial_graph': 'spatial_graph',
        }.get(intent, 'safe_inspection')

    def _tools(self, pipeline: str, source_root: str | None, workspace: str, sample: int, limit: int) -> list[RoutedTool]:
        root = source_root or '<source_folder>'
        if pipeline == 'dwg_bulk_index':
            return [
                RoutedTool('DWG SaveAs DXF fileizer', 'zwcad_saveas_dxf_ezdxf', 'Convert DWG to temporary DXF and parse with ezdxf.', 'fileize'),
                RoutedTool('corpus prepare', f'corpus-run prepare --root "{root}" --workspace "{workspace}" --sample {sample}', 'Build a safe sample manifest.', 'prepare'),
                RoutedTool('corpus fileize', f'corpus-run fileize --workspace "{workspace}" --limit {limit}', 'Fileize using the selected engine.', 'fileize'),
                RoutedTool('corpus validate', f'corpus-run validate --workspace "{workspace}"', 'Validate fileized JSON before indexing.', 'qa'),
                RoutedTool('corpus index', f'corpus-run index --workspace "{workspace}"', 'Build SQLite knowledge base.', 'index'),
                RoutedTool('corpus learn', f'corpus-run learn --workspace "{workspace}"', 'Write learning summary.', 'learn'),
                RoutedTool('corpus quality', f'corpus-run quality --workspace "{workspace}"', 'Write quality audit.', 'qa'),
                RoutedTool('corpus report', f'corpus-run report --workspace "{workspace}"', 'Write final report.', 'report'),
            ]
        if pipeline == 'dxf_index':
            return [
                RoutedTool('ezdxf', 'corpus-run fileize', 'Read DXF directly.', 'fileize'),
                RoutedTool('corpus validate/index', f'corpus-run validate --workspace "{workspace}"', 'Validate DXF extraction before index.', 'qa'),
            ]
        if pipeline == 'pdf_index':
            return [RoutedTool('PyMuPDF', 'corpus-run fileize', 'Extract PDF page and text blocks.', 'fileize')]
        if pipeline == 'image_analysis':
            return [RoutedTool('Pillow/OpenCV', 'floorplan-analyze', 'Start with metadata, then optional vision analysis.', 'vision')]
        if pipeline == 'ifc_bim':
            return [RoutedTool('IfcOpenShell', 'ifc-fileize', 'Planned BIM extraction route.', 'bim')]
        if pipeline == 'spatial_graph':
            return [RoutedTool('Shapely/NetworkX', 'spatial-graph', 'Planned spatial graph route.', 'graph')]
        return [RoutedTool('hscad-tools', 'hscad-tools', 'List safe available tools.', 'inspect')]


def _has(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)
