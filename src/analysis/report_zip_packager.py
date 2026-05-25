from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any

from src.analysis.entity_loader import read_json, write_json_and_md


def create_report_zip_package(
    workspace: str | Path,
    *,
    create_zip: bool = False,
    redact_private_paths: bool = True,
) -> dict[str, Any]:
    """Create or plan a validation report zip package.

    Default create_zip=False for safety. When enabled, only files from REPORT_PACKAGE_MANIFEST.json
    are included. This does not include original DWG/PDF/image sources.
    """
    base = Path(workspace)
    manifest = read_json(base / "REPORT_PACKAGE_MANIFEST.json")
    package_name = str(manifest.get("package_name") or f"{base.name}_hscad_validation_report")
    zip_path = base / f"{package_name}.zip"

    included = []
    skipped = []
    for row in manifest.get("files") or []:
        rel = str(row.get("path") or "")
        if not rel or rel.startswith("..") or Path(rel).is_absolute():
            skipped.append({"path": rel, "reason": "unsafe_path"})
            continue
        path = base / rel
        if not path.exists() or not path.is_file():
            skipped.append({"path": rel, "reason": "missing"})
            continue
        included.append({"path": rel, "size_bytes": path.stat().st_size})

    if create_zip:
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for row in included:
                source = base / row["path"]
                arcname = row["path"]
                zf.write(source, arcname=arcname)

    payload = {
        "backend": "report_zip_packager",
        "schema_version": "0.1",
        "parameters": {
            "create_zip": create_zip,
            "redact_private_paths": redact_private_paths,
        },
        "summary": {
            "zip_path": str(zip_path),
            "zip_created": bool(create_zip and zip_path.exists()),
            "included_count": len(included),
            "skipped_count": len(skipped),
            "included_size_bytes": sum(int(row.get("size_bytes") or 0) for row in included),
        },
        "included": included,
        "skipped": skipped,
        "todo": [
            "Add private path redaction inside markdown/json content.",
            "Add package checksum and manifest signature.",
            "Add optional exclusion of large rendered images.",
            "Add CLI flag to create zip after review.",
        ],
        "warnings": [] if create_zip else ["dry-run package plan only; zip not created"],
    }
    return write_json_and_md(base, "REPORT_ZIP_PACKAGE", payload, _markdown(payload))


def _markdown(payload: dict[str, Any]) -> str:
    s = payload.get("summary") or {}
    return "\n".join([
        "# Report ZIP Package",
        "",
        f"- ZIP path: `{s.get('zip_path')}`",
        f"- ZIP created: `{s.get('zip_created')}`",
        f"- Included files: `{s.get('included_count')}`",
        f"- Skipped files: `{s.get('skipped_count')}`",
        f"- Included size bytes: `{s.get('included_size_bytes')}`",
        "",
    ])
