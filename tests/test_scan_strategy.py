from src.scanners.scan_strategy import recommend_scan_strategy


def test_recommend_scan_strategy_blocks_large_full_scan():
    strategy = recommend_scan_strategy(30_000, "full")

    assert strategy.allowed is False
    assert strategy.name == "heavy_full_scan"


def test_recommend_scan_strategy_prefers_native_for_large_drawings():
    strategy = recommend_scan_strategy(50_000, "index", available_tools=["ezdxf"])

    assert strategy.allowed is True
    assert strategy.name == "native_audit_dxf_index"
