from __future__ import annotations
from src.scanners.block_scanner import block_summary

def block_quantity(objects: list[dict]) -> list[dict]:
    return [{'block': k, 'count': v['count']} for k,v in block_summary(objects).items()]
