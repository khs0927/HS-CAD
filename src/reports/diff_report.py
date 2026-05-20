from __future__ import annotations
from src.scanners.layer_scanner import layer_counts
from src.scanners.block_scanner import block_summary

def compare_objects(before: list[dict], after: list[dict]) -> dict:
    return {
        'object_count_before': len(before),
        'object_count_after': len(after),
        'layer_counts_before': layer_counts(before),
        'layer_counts_after': layer_counts(after),
        'block_counts_before': {k:v['count'] for k,v in block_summary(before).items()},
        'block_counts_after': {k:v['count'] for k,v in block_summary(after).items()},
    }
