from pathlib import Path

from src.scanners.native_audit import parse_native_audit_tsv


def test_parse_native_audit_tsv(tmp_path: Path):
    audit = tmp_path / "audit.tsv"
    audit.write_text(
        "section\tkey\tvalue\n"
        "entity\tTEXT\t2\n"
        "entity\tLINE\t3\n"
        "layer\tWAL1\t4\n"
        "block\tDOOR\t1\n",
        encoding="utf-8",
    )

    payload = parse_native_audit_tsv(audit)

    assert payload["total_objects"] == 5
    assert payload["text_count"] == 2
    assert payload["layer_counts"]["WAL1"] == 4
    assert payload["block_counts"]["DOOR"] == 1
