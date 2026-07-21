from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


def _aliases(key_file: Path) -> list[str]:
    raw_bytes = key_file.read_bytes()
    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        text = raw_bytes.decode("cp949")
    aliases: list[str] = []
    seen: set[str] = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("*Sec") or ";" not in line:
            continue
        alias = line.split(";", 1)[0].strip().split()[0]
        key = alias.casefold()
        if alias and key not in seen:
            aliases.append(alias)
            seen.add(key)
    return aliases


def _lisp_string(value: str) -> str:
    return value.replace("\\", "/").replace('"', '\\"')


def probe(
    *,
    xicad_root: Path,
    document_name: str,
    output: Path,
    timeout: float,
    load_runtime: bool,
) -> dict[str, object]:
    import win32com.client

    key_file = xicad_root / "xiLib" / "xiShortkey.key"
    runtime = xicad_root / "Lisp" / "xi.zelx"
    aliases = _aliases(key_file)
    if len(aliases) != 357:
        raise RuntimeError(f"expected 357 aliases, found {len(aliases)} in {key_file}")

    app = win32com.client.GetActiveObject("ZWCAD.Application.2026")
    matches = [doc for doc in app.Documents if doc.Name.casefold() == document_name.casefold()]
    if len(matches) != 1:
        raise RuntimeError(f"expected one open document named {document_name!r}, found {len(matches)}")
    doc = matches[0]
    doc.Activate()

    if load_runtime:
        doc.SendCommand(f'(load "{_lisp_string(str(runtime))}")\n')
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline and int(doc.GetVariable("CMDACTIVE")) != 0:
            time.sleep(0.2)
        if int(doc.GetVariable("CMDACTIVE")) != 0:
            doc.SendCommand("\x1b\x1b")
            raise TimeoutError(f"xiCAD runtime load did not finish within {timeout:.1f}s")

    rows: list[dict[str, object]] = []
    for offset in range(0, len(aliases), 20):
        batch = aliases[offset : offset + 20]
        checks = " ".join(f'(if (fboundp \'C:{alias}) "1" "0")' for alias in batch)
        marker = f"HSCAD:{offset}:"
        doc.SetVariable("USERS1", f"WAIT:{offset}")
        doc.SendCommand(f'(setvar "USERS1" (strcat "{marker}" {checks}))(princ)\n')
        deadline = time.monotonic() + timeout
        value = ""
        while time.monotonic() < deadline:
            value = str(doc.GetVariable("USERS1"))
            if value.startswith(marker):
                break
            time.sleep(0.1)
        else:
            doc.SendCommand("\x1b\x1b")
            raise TimeoutError(f"xiCAD runtime probe batch at offset {offset} timed out")
        flags = value.removeprefix(marker)
        if len(flags) != len(batch):
            raise RuntimeError(f"probe batch {offset} returned {len(flags)} flags for {len(batch)} aliases")
        rows.extend(
            {"alias": alias, "available": flag == "1"}
            for alias, flag in zip(batch, flags, strict=True)
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "".join(f"{row['alias']}\t{int(bool(row['available']))}\n" for row in rows),
        encoding="utf-8",
    )
    available = [row["alias"] for row in rows if row["available"]]
    missing = [row["alias"] for row in rows if not row["available"]]
    return {
        "document": doc.Name,
        "runtime": str(runtime),
        "runtime_load_requested": load_runtime,
        "total": len(rows),
        "available_count": len(available),
        "missing_count": len(missing),
        "missing": missing,
        "drawing_object_count": len(doc.ModelSpace),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe all frozen xiCAD aliases in an open ZWCAD document.")
    parser.add_argument("--xicad-root", type=Path, default=Path(r"C:\xicad"))
    parser.add_argument("--document", default="Drawing1.dwg")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/xicad-runtime-probe.tsv"),
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument(
        "--load-runtime",
        action="store_true",
        help="Load xi.zelx before probing. This can invoke the legacy startup UI.",
    )
    args = parser.parse_args()
    result = probe(
        xicad_root=args.xicad_root.resolve(),
        document_name=args.document,
        output=args.output.resolve(),
        timeout=args.timeout,
        load_runtime=args.load_runtime,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
