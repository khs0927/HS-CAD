from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolCapability:
    """One callable HS-CAD capability and the conditions for using it."""

    name: str
    command: str
    family: str
    purpose: str
    priority: int
    safe_default: bool = True
    requires_dwg: bool = False
    requires_active_zwcad: bool = False
    requires_execute: bool = False
    requires_save_as: bool = False
    requires_gpu: bool = False
    optional_dependencies: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
    blocked_by_default_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ToolRegistry:
    tools: list[ToolCapability] = field(default_factory=list)

    def add(self, tool: ToolCapability) -> None:
        self.tools.append(tool)

    def all(self) -> list[ToolCapability]:
        return sorted(self.tools, key=lambda item: (item.priority, item.family, item.name))

    def families(self) -> dict[str, list[ToolCapability]]:
        grouped: dict[str, list[ToolCapability]] = {}
        for tool in self.all():
            grouped.setdefault(tool.family, []).append(tool)
        return grouped

    def find(self, *, query: str = "", family: str | None = None) -> list[ToolCapability]:
        q = query.lower().strip()
        rows: list[ToolCapability] = []
        for tool in self.all():
            if family and tool.family != family:
                continue
            haystack = " ".join((tool.name, tool.command, tool.family, tool.purpose, *tool.keywords)).lower()
            if not q or q in haystack or any(token in haystack for token in q.split()):
                rows.append(tool)
        return rows

    def to_dict(self) -> dict[str, Any]:
        return {"tool_count": len(self.tools), "families": {k: [t.to_dict() for t in v] for k, v in self.families().items()}}


def build_default_registry() -> ToolRegistry:
    """Register every major HS-CAD tool family in priority order.

    Lower priority numbers are preferred. Mutating tools are registered too, but
    marked as execute-gated so planners can include them only after preview/safety
    checks.
    """

    reg = ToolRegistry()
    add = reg.add

    # 0. Always start with environment/availability when the user asks broad work.
    add(ToolCapability("Unified environment check", "hscad-tool-plan --check-env", "orchestration", "Check which HS-CAD tools can be used before choosing a workflow.", 5, keywords=("check", "env", "available", "tools"), outputs=("tool_plan.json",)))
    add(ToolCapability("Tool registry", "hscad-tools", "orchestration", "List all available HS-CAD tool families and commands.", 6, keywords=("list", "registry", "tools"), outputs=("tool_registry.json",)))

    # 1. Passive drawing inspection.
    add(ToolCapability("DWG object scan", "scan", "inspection", "Scan modelspace objects to JSON.", 10, requires_dwg=True, keywords=("scan", "objects", "dwg"), outputs=("objects.json",)))
    add(ToolCapability("Layer counts", "layers", "inspection", "Count layers before choosing layer-sensitive tools.", 11, requires_dwg=True, keywords=("layer", "layers")))
    add(ToolCapability("Block counts", "blocks", "inspection", "Count blocks and symbols before replacement or quantity work.", 12, requires_dwg=True, keywords=("block", "blocks", "symbol")))
    add(ToolCapability("Text extraction", "texts", "inspection", "Extract TEXT/MTEXT for notes, labels, and replacement planning.", 13, requires_dwg=True, keywords=("text", "mtext", "label", "ocr")))
    add(ToolCapability("Architecture audit", "analyze-architecture", "inspection", "Build architecture-focused scan and quality report.", 14, requires_dwg=True, keywords=("audit", "architecture", "quality", "polyline"), outputs=("architecture_summary.json", "drawing_audit.md")))
    add(ToolCapability("Quantity report", "quantity", "reporting", "Generate block quantity report.", 18, requires_dwg=True, keywords=("quantity", "count", "report"), outputs=("quantity.json",)))

    # 2. Drawing grammar and standards.
    add(ToolCapability("XiCAD profile detect", "detect-xicad", "standards", "Detect XiCAD install/profile before using XiCAD aliases.", 20, keywords=("xicad", "profile", "detect")))
    add(ToolCapability("XiCAD manifest", "xicad-manifest", "standards", "Write XiCAD file manifest.", 21, keywords=("xicad", "manifest")))
    add(ToolCapability("XiCAD catalog", "xicad-catalog", "standards", "List architecture-related XiCAD aliases.", 22, keywords=("xicad", "alias", "catalog")))
    add(ToolCapability("XiCAD safe catalog", "xicad-safe-catalog", "standards", "List safe XiCAD bridge aliases and risk levels.", 23, keywords=("xicad", "safe", "bridge")))
    add(ToolCapability("Local drawing grammar sample", "python tools/sample_style_near_handle.py", "standards", "Sample nearby CAD style and emit cad-drawing-grammar/1 for reuse by other CAD runtimes.", 24, requires_active_zwcad=True, keywords=("grammar", "style", "layer", "text", "dimension"), outputs=("local_style_sample.json", "local_style_sample.md")))

    # 3. Image/PDF to CAD.
    add(ToolCapability("Floorplan image analyze", "floorplan-analyze", "floorplan", "Run neuro_seq_cad image/PDF-to-DXF pipeline in dry-run by default.", 30, keywords=("image", "pdf", "scan", "floorplan", "dxf", "vectorize", "도면", "이미지"), outputs=("*.dxf", "*_qa_report.html", "*_overlay_qa.png")))
    add(ToolCapability("neuro_seq_cad analyze", "python -X utf8 -m neuro_seq_cad.app.cli analyze", "floorplan", "Direct unified floorplan pipeline entrypoint.", 31, optional_dependencies=("requirements-floorplan.txt",), keywords=("neuro", "raster2seq", "mlsd", "vlm"), outputs=("synthetic_floorplan.dxf",)))

    # 4. Preview/safe mutation.
    add(ToolCapability("JSON command dry-run", "run-command --dry-run", "mutation-preview", "Validate and preview any allowed JSON command before execution.", 40, requires_dwg=True, keywords=("dry-run", "preview", "json", "command")))
    add(ToolCapability("XiCAD safe plan", "xicad-safe-plan", "mutation-preview", "Plan XiCAD action without running it.", 41, keywords=("xicad", "plan", "preview")))
    add(ToolCapability("XiCAD safe run", "xicad-safe-run --execute", "mutation-execute", "Run approved XiCAD safe command.", 80, requires_dwg=True, requires_execute=True, requires_save_as=True, keywords=("xicad", "execute", "run"), blocked_by_default_reason="Requires explicit --execute and usually --save-as."))
    add(ToolCapability("Command execution", "run-command --execute", "mutation-execute", "Execute an approved JSON command on a DWG copy.", 90, requires_dwg=True, requires_execute=True, requires_save_as=True, keywords=("execute", "modify", "save"), blocked_by_default_reason="Mutates drawings; use dry-run first and SaveAs."))

    # 5. Third-party/model setup.
    add(ToolCapability("Third-party setup", "scripts/setup_third_party.ps1", "setup", "Clone Raster2Seq, PlanParser, MLSD and related sources.", 100, optional_dependencies=("git",), keywords=("setup", "third_party", "raster2seq", "mlsd")))
    add(ToolCapability("Raster2Seq checkpoints", "scripts/download_raster2seq_checkpoints.ps1", "setup", "Download Raster2Seq checkpoints.", 101, requires_gpu=True, optional_dependencies=("gdown", "CUDA", "PyTorch"), keywords=("checkpoint", "raster2seq", "weights")))

    return reg
