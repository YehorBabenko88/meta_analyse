"""Tests for worker-owned telemetry values exposed to the Qt thread."""
from types import SimpleNamespace
from meta_analyse.desktop_service import DesktopService
from meta_analyse.market_telemetry import MarketTelemetry

def test_snapshot_exposes_immutable_telemetry():
    service=DesktopService(None,lambda snapshot:None)
    service.runtime=SimpleNamespace(symbols=[],paper=SimpleNamespace(fills=[],positions={}))
    telemetry=MarketTelemetry()
    telemetry.observe("orderbook","BTCUSDT")
    telemetry.gap("orderbook","BTCUSDT")
    service.session=SimpleNamespace(market=SimpleNamespace(telemetry=telemetry))
    service.flow_state="connected"
    snapshot=service.snapshot()
    assert snapshot.market_events==(("orderbook:BTCUSDT",1),)
    assert snapshot.market_gaps==(("orderbook:BTCUSDT",1),)
    telemetry.observe("orderbook","BTCUSDT")
    assert snapshot.market_events==(("orderbook:BTCUSDT",1),)
    assert service.snapshot().market_events==(("orderbook:BTCUSDT",2),)

def test_snapshot_without_session_has_empty_diagnostics():
    service=DesktopService(None,lambda snapshot:None)
    snapshot=service.snapshot()
    assert snapshot.market_events==()
    assert snapshot.market_gaps==()

def test_disconnecting_hides_previous_feed_counters():
    service=DesktopService(None,lambda snapshot:None)
    service.runtime=SimpleNamespace(symbols=[],paper=SimpleNamespace(fills=[],positions={}))
    telemetry=MarketTelemetry()
    telemetry.observe("orderbook","BTCUSDT")
    service.session=SimpleNamespace(market=SimpleNamespace(telemetry=telemetry))
    service.flow_state="connected"
    assert service.snapshot().market_events==(("orderbook:BTCUSDT",1),)
    for state in ("stopping","disconnected","failed","connecting"):
        service.flow_state=state
        assert service.snapshot().market_events==()
        assert service.snapshot().market_gaps==()
