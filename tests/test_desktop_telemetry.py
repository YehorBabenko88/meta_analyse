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

def test_reconnect_uses_new_session_counters_not_previous():
    service=DesktopService(None,lambda snapshot:None)
    service.runtime=SimpleNamespace(symbols=[],paper=SimpleNamespace(fills=[],positions={}))
    first=MarketTelemetry()
    first.observe("orderbook","BTCUSDT")
    first.observe("orderbook","BTCUSDT")
    service.session=SimpleNamespace(market=SimpleNamespace(telemetry=first))
    service.flow_state="connected"
    assert service.snapshot().market_events==(("orderbook:BTCUSDT",2),)
    service.flow_state="disconnected"
    service.session=None
    assert service.snapshot().market_events==()
    second=MarketTelemetry()
    second.observe("orderbook","ETHUSDT")
    service.session=SimpleNamespace(market=SimpleNamespace(telemetry=second))
    service.flow_state="connected"
    assert service.snapshot().market_events==(("orderbook:ETHUSDT",1),)

def test_persisted_ages_hidden_during_failure_and_reset_on_reconnect():
    """Never leak a previous session's freshness into a new connection."""
    service = DesktopService(None, lambda snapshot: None)
    service.runtime = SimpleNamespace(
        symbols=[], paper=SimpleNamespace(fills=[], positions={}))
    first = MarketTelemetry()
    first.observe("orderbook", "BTCUSDT")
    first.gap("orderbook", "BTCUSDT")
    service.session = SimpleNamespace(market=SimpleNamespace(telemetry=first))
    service.flow_state = "connected"
    first_snapshot = service.snapshot()
    assert len(first_snapshot.market_ages) == 1
    assert first_snapshot.market_ages[0][0] == "orderbook:BTCUSDT"
    for state in ("stopping", "failed", "disconnected", "connecting"):
        service.flow_state = state
        hidden = service.snapshot()
        assert hidden.market_events == ()
        assert hidden.market_gaps == ()
        assert hidden.market_ages == ()
    second = MarketTelemetry()
    second.gap("orderbook", "ETHUSDT")
    service.session = SimpleNamespace(market=SimpleNamespace(telemetry=second))
    service.flow_state = "connected"
    new_snapshot = service.snapshot()
    assert new_snapshot.market_events == ()
    assert new_snapshot.market_ages == ()
    assert new_snapshot.market_gaps == (("orderbook:ETHUSDT", 1),)
    assert first_snapshot.market_events == (("orderbook:BTCUSDT", 1),)
