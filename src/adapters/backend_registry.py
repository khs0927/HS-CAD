from __future__ import annotations

from dataclasses import asdict, dataclass, field
from importlib.util import find_spec
from typing import Any


@dataclass(frozen=True)
class CADBackendCapability:
    """Describes one CAD backend candidate without importing heavy runtimes."""

    name: str
    adapter_module: str
    adapter_class: str
    status: str
    purpose: str
    default: bool = False
    requires_active_cad: bool = False
    optional_dependencies: tuple[str, ...] = ()
    strengths: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    planned_integration: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)

    def dependency_status(self) -> dict[str, bool]:
        return {dep: find_spec(dep) is not None for dep in self.optional_dependencies}

    def to_dict(self, *, include_dependency_status: bool = True) -> dict[str, Any]:
        row = asdict(self)
        if include_dependency_status:
            row["dependency_status"] = self.dependency_status()
        return row


class CADBackendRegistry:
    def __init__(self, backends: list[CADBackendCapability] | None = None):
        self.backends = backends or []

    def add(self, backend: CADBackendCapability) -> None:
        self.backends.append(backend)

    def all(self) -> list[CADBackendCapability]:
        return sorted(self.backends, key=lambda item: (not item.default, item.status, item.name))

    def find(self, query: str = "") -> list[CADBackendCapability]:
        q = query.lower().strip()
        if not q:
            return self.all()
        rows: list[CADBackendCapability] = []
        for backend in self.all():
            haystack = " ".join(
                (
                    backend.name,
                    backend.adapter_module,
                    backend.adapter_class,
                    backend.status,
                    backend.purpose,
                    backend.planned_integration,
                    *backend.strengths,
                    *backend.limitations,
                    *backend.tags,
                )
            ).lower()
            if q in haystack or any(token in haystack for token in q.split()):
                rows.append(backend)
        return rows

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend_count": len(self.backends),
            "backends": [backend.to_dict() for backend in self.all()],
        }


def build_default_backend_registry() -> CADBackendRegistry:
    """Return the planned backend matrix for HS-CAD.

    This registry is intentionally metadata-only. It must not import COM, PyRx,
    pyzwcad, ezdxf, or any runtime that requires a local CAD installation.
    """
    registry = CADBackendRegistry()
    add = registry.add

    add(
        CADBackendCapability(
            name="ZWCAD COM/ActiveX",
            adapter_module="src.adapters.zwcad_com_adapter",
            adapter_class="ZWCADCOMAdapter",
            status="stable-default",
            purpose="Default Windows ZWCAD automation backend for active DWG scan and safe mutations.",
            default=True,
            requires_active_cad=True,
            optional_dependencies=("comtypes",),
            strengths=("highest current feature coverage", "active drawing mutation", "ZWCAD 2024/2026 ProgID fallback"),
            limitations=("Windows and active CAD session required", "full COM scans can be slow for very large drawings"),
            planned_integration="Keep as default execution backend; use other backends to prefilter or validate large drawings.",
            tags=("dwg", "zwcad", "com", "active-cad"),
        )
    )
    add(
        CADBackendCapability(
            name="PyRx/cad-pyrx",
            adapter_module="src.adapters.pyrx_adapter",
            adapter_class="PyRxAdapter",
            status="experimental",
            purpose="Future high-performance local backend for object-heavy ZWCAD drawings.",
            requires_active_cad=True,
            optional_dependencies=("pyrx",),
            strengths=("potentially faster entity traversal", "lower-level DB access", "better fit for huge modelspaces"),
            limitations=("runtime setup differs by ZWCAD/PyRx version", "adapter methods are intentionally skeletons"),
            planned_integration="Prototype after confirming the local ZWCAD 2025/2026 + cad-pyrx runtime.",
            tags=("dwg", "zwcad", "pyrx", "large-drawings"),
        )
    )
    add(
        CADBackendCapability(
            name="pyzwcad compatibility shim",
            adapter_module="src.adapters.pyzwcad_adapter",
            adapter_class="PyZWCADAdapter",
            status="optional-shim",
            purpose="Optional pyzwcad-aware entry point while falling back to the robust COM adapter.",
            requires_active_cad=True,
            optional_dependencies=("pyzwcad",),
            strengths=("can host pyzwcad-specific helpers later", "currently preserves COM fallback behavior"),
            limitations=("no pyzwcad-specific features yet", "candidate for removal if it never adds value"),
            planned_integration="Keep until backend registry proves whether pyzwcad adds useful helpers beyond COM.",
            tags=("dwg", "zwcad", "pyzwcad", "compatibility"),
        )
    )
    add(
        CADBackendCapability(
            name="ezdxf offline DXF",
            adapter_module="src.adapters.ezdxf_adapter",
            adapter_class="EzDxfAdapter",
            status="offline-fallback",
            purpose="Read DXF entities without launching ZWCAD for evidence extraction and fallback inspection.",
            optional_dependencies=("ezdxf",),
            strengths=("no active CAD required", "good for exported/fileized DXF", "safe read-only analysis"),
            limitations=("DXF only", "does not mutate active DWG", "geometry extraction still minimal"),
            planned_integration="Consolidate with DXF fileizers and evidence workers after scanner outputs stabilize.",
            tags=("dxf", "offline", "fileizer", "evidence"),
        )
    )

    return registry
