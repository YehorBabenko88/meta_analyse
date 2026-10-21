"""Collector telemetry counts committed persistence, never attempted writes."""
from unittest.mock import AsyncMock
import pytest
from meta_analyse.market_collector import MarketCollector
from meta_analyse.market_telemetry import MarketTelemetry

@pytest.mark.asyncio
async def test_book_counts_only_after_persistence(monkeypatch):
    telemetry=MarketTelemetry()
    collector=MarketCollector(object(),object(),telemetry=telemetry)
    calls=[]
    monkeypatch.setattr(collector.db,"book",lambda *args:calls.append("persist"))
    collector.on_book=AsyncMock(side_effect=lambda *args:calls.append("callback"))
    await collector._book("BTCUSDT",object(),1000)
    assert calls==["persist","callback"]
    assert telemetry.snapshot().events==(("orderbook:BTCUSDT",1),)
    assert telemetry.ages()[0][0]=="orderbook:BTCUSDT"

@pytest.mark.asyncio
async def test_failed_book_persistence_does_not_count(monkeypatch):
    telemetry=MarketTelemetry()
    collector=MarketCollector(object(),object(),telemetry=telemetry)
    def fail(*args):
        raise OSError("disk unavailable")
    monkeypatch.setattr(collector.db,"book",fail)
    with pytest.raises(OSError):
        await collector._book("BTCUSDT",object(),1000)
    assert telemetry.snapshot().events==()
    assert telemetry.ages()==()

@pytest.mark.asyncio
async def test_gap_counted_per_symbol():
    telemetry=MarketTelemetry()
    collector=MarketCollector(object(),object(),telemetry=telemetry)
    await collector._gap(["BTCUSDT","ETHUSDT"],"reconnect")
    assert telemetry.snapshot().gaps==(("orderbook:BTCUSDT",1),("orderbook:ETHUSDT",1))
