from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


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
    warnings: list[str] = field(default_factory=list)
    missing_context: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            'user_prompt': self.user_prompt,
            'source_path': self.source_path,
            'source_extension': self.source_extension,
            'intent': self.intent,
            'pipeline': self.pipeline,
            'tools': [tool.to_dict() for tool in self.tools],
            'warnings': self.warnings,
            'missing_context': self.missing_context,
        }


class TaskRouter:
    def route(self, user_prompt: str, source_path: str | Path | None = None, *, workspace: str | Path = 'outputs/routed_corpus') -> TaskRoute:
        text = user_prompt.lower()
        source = str(source_path) if source_path else None
        ext = Path(source).suffix.lower() if source else None
        intent = self._intent(text, ext)
        pipeline = self._pipeline(intent)
        tools = self._tools(pipeline, source, str(workspace))
        warnings: list[str] = []
        missing: list[str] = []
        if not source and pipeline != 'safe_inspection':
            missing.append('source_path is required for this route')
        if ext == '.dwg':
            warnings.append('DWG bulk import should use SaveAs DXF plus ezdxf, not COM ModelSpace iteration.')
        return TaskRoute(user_prompt, source, ext, intent, pipeline, tools, warnings, missing)

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

    def _tools(self, pipeline: str, source: str | None, workspace: str) -> list[RoutedTool]:
        src = source or '<source_path>'
        root = str(Path(src).parent) if source else '<source_folder>'
        if pipeline == 'dwg_bulk_index':
            return [
                RoutedTool('DWG SaveAs DXF fileizer', 'zwcad_saveas_dxf_ezdxf', 'Convert DWG to temporary DXF and parse with ezdxf.', 'fileize'),
                RoutedTool('corpus prepare', f'corpus-run prepare --root "{root}" --workspace "{workspace}" --sample 20', 'Build a safe sample manifest.', 'prepare'),
                RoutedTool('corpus fileize', f'corpus-run fileize --workspace "{workspace}" --limit 20', 'Fileize using the selected engine.', 'fileize'),
                RoutedTool('corpus quality', f'corpus-run validate --workspace "{workspace}"', 'Validate fileized JSON before indexing.', 'qa'),
            ]
        if pipeline == 'dxf_index':
            return [RoutedTool('ezdxf', 'corpus-run fileize', 'Read DXF directly.', 'fileize')]
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
