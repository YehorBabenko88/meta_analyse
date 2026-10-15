"""MarketCollector telemetry must count only successfully persisted events."""
from unittest.mock import AsyncMock
import pytest
from meta_analyse.market_collector import MarketCollector
from meta_analyse.market_telemetry import MarketTelemetry

@pytest.mark.asyncio
async def test_book_telemetry_after_persistence(monkeypatch):
    telemetry=MarketTelemetry()
    collector=MarketCollector(object(),object(),telemetry=telemetry)
    calls=[]
    def persisted(*args):
        calls.append("persist")
    monkeypatch.setattr(collector.db,"book",persisted)
    collector.on_book=AsyncMock(side_effect=lambda *args:calls.append("callback"))
    await collector._book("BTCUSDT",object(),1000)
    assert calls==["persist","callback"]
    assert telemetry.snapshot().events==(("orderbook:BTCUSDT",1),)

@pytest.mark.asyncio
async def test_failed_persistence_does_not_count_book(monkeypatch):
    telemetry=MarketTelemetry()
    collector=MarketCollector(object(),object(),telemetry=telemetry)
    def fail(*args):
        raise OSError("disk unavailable")
    monkeypatch.setattr(collector.db,"book",fail)
    with pytest.raises(OSError):
        await collector._book("BTCUSDT",object(),1000)
    assert telemetry.snapshot().events==()

@pytest.mark.asyncio
async def test_gap_counted_per_symbol():
    telemetry=MarketTelemetry()
    collector=MarketCollector(object(),object(),telemetry=telemetry)
    await collector._gap(["BTCUSDT","ETHUSDT"],"reconnect")
    assert telemetry.snapshot().gaps==(("orderbook:BTCUSDT",1),("orderbook:ETHUSDT",1))
