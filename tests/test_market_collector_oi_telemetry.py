"""Open-interest telemetry records successful persistence only."""
import asyncio
import pytest
from meta_analyse.market_collector import MarketCollector
from meta_analyse.market_telemetry import MarketTelemetry

@pytest.mark.asyncio
async def test_open_interest_success_then_failed_write_does_not_increment(monkeypatch):
    telemetry = MarketTelemetry()
    collector = MarketCollector(object(), object(), telemetry=telemetry)
    attempts = []
    async def fetch(*args):
        return [object(), object()]
    def persist(*args):
        attempts.append(1)
        if len(attempts) == 2:
            raise OSError("simulated PostgreSQL write failure")
    monkeypatch.setattr("meta_analyse.market_collector.fetch_open_interest", fetch)
    monkeypatch.setattr(collector.db, "open_interest", persist)
    async def stop_after_first_cycle(event, timeout):
        collector.stop_event.set()
        return True
    monkeypatch.setattr(asyncio, "wait_for", stop_after_first_cycle)
    await collector._oi_loop(["BTCUSDT"])
    assert len(attempts) == 2
    assert telemetry.snapshot().events == (("open_interest:BTCUSDT", 1),)
    assert telemetry.ages()[0][0] == "open_interest:BTCUSDT"

@pytest.mark.asyncio
async def test_open_interest_fetch_failure_does_not_count(monkeypatch):
    telemetry = MarketTelemetry()
    collector = MarketCollector(object(), object(), telemetry=telemetry)
    async def fail(*args):
        raise ConnectionError("simulated exchange failure")
    monkeypatch.setattr("meta_analyse.market_collector.fetch_open_interest", fail)
    async def stop_after_first_cycle(event, timeout):
        collector.stop_event.set()
        return True
    monkeypatch.setattr(asyncio, "wait_for", stop_after_first_cycle)
    await collector._oi_loop(["ETHUSDT"])
    assert telemetry.snapshot().events == ()
