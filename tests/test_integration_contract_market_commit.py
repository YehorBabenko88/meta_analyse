"""Offline, bounded integration-contract witness; no external connections.

This is NOT a full Bybit→PostgreSQL→Qt E2E proof. It checks that a
production-style market callback cannot promote a failed write to telemetry.
"""
import asyncio
from decimal import Decimal
from types import SimpleNamespace
import pytest
from meta_analyse.market_collector import MarketCollector


@pytest.mark.asyncio
async def test_failed_orderbook_commit_never_promotes_telemetry():
    class FailingDB:
        def book(self, *_):
            raise OSError("synthetic database failure")
    class Telemetry:
        def __init__(self):
            self.observed = []
        def observe(self, *args):
            self.observed.append(args)
    telemetry = Telemetry()
    collector = MarketCollector(None, None, telemetry=telemetry)
    collector.db = FailingDB()
    published = []
    async def on_book(*args):
        published.append(args)
    collector.on_book = on_book
    snapshot = SimpleNamespace(valid=True, symbol="BTCUSDT",
        bids={Decimal("100"): Decimal("1")},
        asks={Decimal("101"): Decimal("1")}, update_id=1, sequence=1)
    with pytest.raises(OSError, match="synthetic database failure"):
        await collector._book("BTCUSDT", snapshot, 1)
    assert telemetry.observed == []
    assert published == []


@pytest.mark.asyncio
async def test_successful_commit_precedes_telemetry_and_publish():
    order = []
    class SuccessfulDB:
        def book(self, *_):
            order.append("commit")
    class Telemetry:
        def observe(self, *_):
            order.append("telemetry")
    async def published(*_):
        order.append("publish")
    collector = MarketCollector(None, None, telemetry=Telemetry(), on_book=published)
    collector.db = SuccessfulDB()
    await collector._book("BTCUSDT", SimpleNamespace(valid=True), 1)
    assert order == ["commit", "telemetry", "publish"]
