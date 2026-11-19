"""Installed Math SDK is the real calculation owner for Meta runtime callers.

These tests exercise production import paths, not test-only helper code, and
reject reintroduction of independent local mathematical implementations.
They do not claim real market provenance or a released Unified deployment.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from importlib import metadata
from types import SimpleNamespace

import market_profile_math as math

from meta_analyse import core, footprint, orderflow_aggregation, orderflow_metrics
from meta_analyse import tape_velocity, wall_tracker


def test_runtime_calls_same_installed_math_symbols():
    assert metadata.version("unified-math-kernels") == "0.1.0"
    assert core.price_bucket is math.price_bucket
    assert core.volume_profile_poc is math.volume_profile_poc
    assert core.untouched_decimal_levels is math.untouched_decimal_levels
    assert core.flow_window_metrics is math.flow_window_metrics
    assert core.wall_turnover_ratios is math.wall_turnover_ratios
    assert footprint.price_bucket is math.price_bucket
    assert footprint.volume_profile_poc is math.volume_profile_poc
    assert footprint.executed_volume_delta is math.executed_volume_delta
    assert orderflow_metrics.orderflow_volume_metrics is math.orderflow_volume_metrics
    from market_compute_api import STREAM_ABI
    assert STREAM_ABI == "math.market.orderflow.stream.v1"
    assert orderflow_aggregation.aggregate_orderflow_stream is math.aggregate_orderflow_stream
    assert tape_velocity.tape_velocity_metrics is math.tape_velocity_metrics
    assert wall_tracker.wall_notional is math.wall_notional


def test_real_minute_and_footprint_call_math_preserving_distinct_poc_ties():
    base = datetime(2026, 10, 19, tzinfo=timezone.utc)
    first = core.Trade("BTCUSDT", base, D("99"), D("2"), "Buy")
    second = core.Trade("BTCUSDT", base + timedelta(seconds=1), D("101"), D("2"), "Sell")
    minute = core.new_minute(first, D("1"))
    minute.add(second)
    assert minute.poc == D("101")  # equal volumes: closest to latest close
    assert minute.poc == math.volume_profile_poc(minute.profile, close=minute.close)

    view = footprint.Footprint("BTCUSDT", 0, 60_000, D("1"))
    view.add(SimpleNamespace(symbol="BTCUSDT", timestamp_ms=1_000,
                             price=D("99"), quantity=D("2"), taker_side="Buy"),
             contiguous=True)
    view.add(SimpleNamespace(symbol="BTCUSDT", timestamp_ms=2_000,
                             price=D("101"), quantity=D("2"), taker_side="Sell"),
             contiguous=True)
    assert view.poc == D("99")  # footprint resolves equal volumes to lower price
    assert view.delta == D("0")
    assert view.trusted is True
    assert view.poc == math.volume_profile_poc({
        price: cell.buy + cell.sell for price, cell in view.cells.items()
    })
    view.add(SimpleNamespace(symbol="BTCUSDT", timestamp_ms=3_000,
                             price=D("101"), quantity=D("1"), taker_side="Buy"),
             contiguous=False)
    assert view.trusted is False  # Math never manufactures gap continuity


def test_orderflow_actual_adapter_preserves_unknown_volume_and_delta():
    trade = orderflow_metrics.Trade
    rows = [trade(1000, D("100"), D("2"), "buy"),
            trade(2000, D("100"), D("1"), "sell"),
            trade(3000, D("100"), D("7"), "unknown")]
    result = orderflow_metrics.calculate(rows, initial_delta=D("4"))
    assert result.delta == D("1")
    assert result.cumulative_delta == D("5")
    assert result.unknown_volume == D("7")
    assert result.imbalance == D("1") / D("3")
    buckets = orderflow_aggregation.aggregate_by_time(rows, 1000, initial_delta=D("4"))
    assert sum(item.trade_count for _, item in buckets) == 3
    assert buckets[-1][1].cumulative_delta == D("5")


def test_math_import_is_required_and_fail_closed_for_nonpositive_market_inputs():
    import pytest
    with pytest.raises(ValueError):
        core.price_bucket(D("0"), D("1"))
    with pytest.raises(ValueError):
        math.volume_profile_poc({D("100"): D("-1")}, close=D("100"))


def test_legacy_runtime_paper_consumer_is_terminan_owner():
    from meta_analyse.runtime import Runtime, PaperEngine as RuntimePaper
    from terminan.paper import PaperEngine as TerminanPaper, ExecutionTrade
    from meta_analyse.core import PaperEngine as OriginalOracle

    assert RuntimePaper is TerminanPaper
    runtime = Runtime(None, None)
    assert type(runtime.paper) is TerminanPaper
    assert runtime.paper.enabled is False
    assert not hasattr(runtime.paper, "submit_order")
    assert not hasattr(runtime.paper, "place_order")

    # Identical UTC event sequence: legacy original is a frozen parity oracle,
    # only the migrated Terminan engine runs inside the actual Meta Runtime.
    base = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
    oracle = OriginalOracle()
    oracle.enabled = runtime.paper.enabled = True
    first = core.Trade("BTCUSDT", base, D("100"), D("1"), "Buy")
    oracle.on_closed_minute("BTCUSDT", core.new_minute(first, D("1")))
    runtime.symbols = ["BTCUSDT"]

    def packet(seconds, price):
        stamp = base + timedelta(seconds=seconds)
        return {"Type": "trade_update", "Data": {
            "ticker": "BTCUSDT",
            "trades": [{"price": str(price), "size": "1", "side": "Buy",
                        "time": stamp.isoformat()}],
        }}

    assert runtime.receive(packet(0, "100")) == []
    assert runtime.receive(packet(60, "102"))[0][0] == "closed_minute"
    oracle.on_trade(core.Trade("BTCUSDT", base + timedelta(seconds=60),
                               D("102"), D("1"), "Buy"))
    assert runtime.paper.positions["BTCUSDT"].side == oracle.positions["BTCUSDT"].side
    events = runtime.receive(packet(61, "100"))
    expected = oracle.on_trade(core.Trade("BTCUSDT", base + timedelta(seconds=61),
                                          D("100"), D("1"), "Buy"))
    assert events == [("paper_fill", "BTCUSDT", runtime.paper.fills[0])]
    actual = runtime.paper.fills[0]
    for attr in ("symbol", "side", "entry", "exit", "reason", "gross",
                 "fees", "net", "exit_time"):
        assert getattr(actual, attr) == getattr(expected, attr)

    assert runtime.receive(packet(190, "103"))[0][0] == "closed_minute"
    assert "BTCUSDT" not in runtime.paper.reference
