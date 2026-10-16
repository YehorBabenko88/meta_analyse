"""Worker-owned desktop services. Only frozen value snapshots cross into Qt."""
from __future__ import annotations
import asyncio
import time
from dataclasses import dataclass
from decimal import Decimal
from .analysis_session import AnalysisSession
from .exchange import BybitPublic
from .ports import MetaScalp
from .runtime import Runtime
from .flow_bridge import FlowBridge

@dataclass(frozen=True)
class DesktopSnapshot:
    symbols: tuple = ()
    stats: tuple = ()
    flow_rows: tuple = ()
    flow_state: str = 'disconnected'
    flow_status: str = 'Disconnected — data marked UNVERIFIED'
    status: str = 'Standby; no exchange orders are ever sent'
    market_events: tuple = ()
    market_gaps: tuple = ()
    market_ages: tuple = ()
    overview: tuple = ()

class DesktopService:
    def __init__(self, store, publish):
        self.store, self.publish = store, publish
        self.api = self.exchange = self.runtime = None
        self.bridge = FlowBridge()
        self.session = self.flow_task = self.monitor_task = None
        self.flow_state = 'disconnected'
        self.flow_status = 'Disconnected — data marked UNVERIFIED'
        self.status = 'Standby; no exchange orders are ever sent'
        self.closing = False
        self.disconnect_task = None
        self.overview = {}
        self.oi_history = {}
        self.overview_updated = 0.0

    def initialize(self):
        self.api = MetaScalp()
        self.exchange = BybitPublic()
        self.runtime = Runtime(self.api, self.exchange, self.store, on_status=self._monitor_status)

    def _monitor_status(self, text):
        self.status = text

    def error(self, operation, exc):
        # Exception text may contain DSNs, passwords or HTTP payloads.
        self.status = f'{operation} failed ({type(exc).__name__}); check connectivity and configuration'

    async def refresh(self):
        try:
            await self.runtime.refresh_watchlist()
            # Publish the watchlist without waiting for optional market metrics.
            self.overview_updated = time.monotonic()
            asyncio.create_task(self._refresh_overview_safe())
            self.status = 'Symbols refreshed; read-only / paper'
        except Exception as exc:
            self.error('Refresh', exc)

    async def _refresh_overview_safe(self):
        try:
            await self.refresh_overview()
        except Exception:
            # Overview is optional; missing metrics must not block selection.
            pass

    async def refresh_overview(self):
        symbols = tuple(self.runtime.symbols)
        rows = await self.exchange.market_overview(symbols)
        now = time.monotonic()
        for symbol, (_, _, oi) in rows.items():
            history = self.oi_history.setdefault(symbol, [])
            history.append((now, oi))
            self.oi_history[symbol] = [(t, value) for t, value in history if now - t <= 3900]
        self.overview = rows
        self.overview_updated = now

    async def locate_metascalp(self):
        from .metascalp_locator import find_metascalp
        try:
            endpoint = await self.api.discover()
            self.status = f"MetaScalp API available: {endpoint}"
        except (ConnectionError, OSError):
            paths = await asyncio.to_thread(find_metascalp)
            if paths:
                self.status = f"MetaScalp installed (not connected): {paths[0]}"
            else:
                self.status = "MetaScalp not found in common Windows locations; API unavailable"

    async def open_selected(self, symbols):
        try:
            await self.api.open_combos(symbols)
        except Exception as exc:
            self.error('Open combos', exc)

    async def start_monitor(self):
        if self.closing or self.monitor_task is not None and not self.monitor_task.done():
            return
        async def run():
            try:
                if self.store:
                    await asyncio.to_thread(self.store.initialize)
                self.status = 'Monitor running; MetaScalp feed is aggregated and unverified'
                await self.runtime.run()
            except Exception as exc:
                self.error('Monitor', exc)
        self.monitor_task = asyncio.create_task(run())

    def connect_flow(self, symbols, level):
        if (self.closing or self.flow_state in ('connecting', 'connected', 'stopping')
                or self.flow_task is not None and not self.flow_task.done()
                or self.disconnect_task is not None and not self.disconnect_task.done()):
            return
        self.flow_state = 'connecting'
        self.flow_status = 'Connecting; historical continuity remains unverified'
        self.flow_task = asyncio.create_task(self._start_flow(tuple(symbols), level))

    async def _start_flow(self, symbols, level):
        try:
            from .instruments import instruments
            metadata = await instruments(self.exchange)
            ticks = {s: metadata[s].tick_size for s in symbols if s in metadata}
            if len(ticks) != len(symbols):
                raise ValueError('Missing tick sizes')
            self.session = AnalysisSession(self.store, self.exchange, ticks,
                                           on_update=self._flow_execution, on_gap=self._gap,
                                           on_book_update=self._flow_book)
            if level > 0:
                for symbol in symbols:
                    self.session.select_level(symbol, level)
            await self.session.start()
            self.flow_state = 'connected'
            self.flow_status = 'Collectors running — feed health and historical continuity NOT verified'
        except asyncio.CancelledError:
            # Cancellation can interrupt startup after collectors allocated tasks.
            # Release them before propagating cancellation to the disconnect owner.
            session, self.session = self.session, None
            if session is not None:
                try:
                    await session.stop()
                except Exception as cleanup_exc:
                    self.error('Cancelled flow cleanup', cleanup_exc)
            raise
        except Exception as exc:
            self.bridge.invalidate(symbols)
            self.flow_state = 'failed'
            self.flow_status = f'Connection failed ({type(exc).__name__}); data UNVERIFIED'
            self.error('Flow startup', exc)
            session, self.session = self.session, None
            if session is not None:
                try:
                    await session.stop()
                except Exception as cleanup_exc:
                    self.error('Flow startup cleanup', cleanup_exc)

    async def _flow_execution(self, symbol, footprint, tape):
        await self.bridge.update(symbol, footprint, tape)
        self.bridge.trade_observed(symbol)

    async def _flow_book(self, symbol, summary):
        self.bridge.book_observed(symbol, summary)

    async def _gap(self, symbols, reason):
        self.bridge.invalidate(symbols)

    async def disconnect_flow(self):
        if (self.flow_state == 'disconnected' and self.session is None
                and (self.flow_task is None or self.flow_task.done())
                and (self.disconnect_task is None or self.disconnect_task.done())):
            return
        # Repeated clicks join one cleanup; they cannot publish disconnected early
        # or queue a second stop that accidentally cancels a later new session.
        if self.disconnect_task is None or self.disconnect_task.done():
            self.disconnect_task = asyncio.create_task(self._disconnect_flow())
        await asyncio.shield(self.disconnect_task)

    async def _disconnect_flow(self):
        self.flow_state = 'stopping'
        task, self.flow_task = self.flow_task, None
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        session = self.session
        try:
            if session is not None:
                await session.stop()
        except Exception as exc:
            self.error('Flow shutdown', exc)
        finally:
            self.session = None
            self.bridge.invalidate([row.symbol for row in self.bridge.snapshot()])
            self.flow_state = 'disconnected'
            self.flow_status = 'Disconnected — data marked UNVERIFIED'

    async def configure_paper(self, enabled=None, rules=None):
        if enabled is not None:
            self.runtime.paper.enabled = enabled
        if rules is not None:
            self.runtime.paper.threshold, self.runtime.paper.stop_pct, self.runtime.paper.fee_rate = rules

    def snapshot(self):
        if self.runtime is None:
            return DesktopSnapshot(flow_state=self.flow_state, flow_status=self.flow_status, status=self.status)
        engine = self.runtime.paper
        symbols = tuple(self.runtime.symbols)
        stats = []
        for symbol in sorted(set(symbols) | {f.symbol for f in engine.fills}):
            fills = [f for f in engine.fills if f.symbol == symbol]
            stats.append((symbol, str(len(fills)), str(sum(f.net > 0 for f in fills)),
                          str(round(sum((f.net for f in fills), Decimal(0)), 4)),
                          engine.positions[symbol].side if symbol in engine.positions else '-'))
        telemetry = (self.session.market.telemetry.snapshot()
                     if self.flow_state == 'connected' and self.session is not None
                     and hasattr(self.session.market, 'telemetry') else None)
        overview = []
        now = time.monotonic()
        for symbol in symbols:
            row = self.overview.get(symbol)
            if row is None:
                overview.append((symbol, 'N/A', 'N/A', 'N/A', 'N/A', 'N/A'))
                continue
            change, turnover, oi = row
            history = self.oi_history.get(symbol, [])
            def delta(seconds):
                prior = next((value for t, value in reversed(history) if now - t >= seconds), None)
                return f'{(oi / prior - 1) * 100:+.2f}%' if prior and prior > 0 else 'N/A'
            overview.append((symbol, f'{change:+.2f}%', f'{turnover:,.0f}', f'{oi:,.0f}', delta(300), delta(3600)))
        return DesktopSnapshot(symbols, tuple(stats), self.bridge.snapshot(),
                               self.flow_state, self.flow_status, self.status,
                               telemetry.events if telemetry else (), telemetry.gaps if telemetry else (),
                               self.session.market.telemetry.ages() if telemetry else (), tuple(overview))

    async def check_health(self):
        if self.flow_state != 'connected' or self.session is None:
            return
        tasks = self.session.raw.tasks + self.session.market.tasks
        ended = next((task for task in tasks if task.done()), None)
        if ended is not None:
            exc = asyncio.CancelledError() if ended.cancelled() else ended.exception()
            # A user-initiated disconnect takes precedence over health reporting.
            # No await occurs between the ownership check and scheduling cleanup.
            if self.flow_state != 'connected' or self.closing:
                return
            if self.disconnect_task is not None and not self.disconnect_task.done():
                return
            await self.disconnect_flow()
            # A newer connection may have started after cleanup completed.
            if self.closing or self.flow_state != 'disconnected':
                return
            self.flow_state = 'failed'
            self.flow_status = f'Collector stopped ({type(exc).__name__}); data UNVERIFIED'

    async def publish_loop(self):
        while True:
            if self.runtime and self.runtime.symbols and time.monotonic() - self.overview_updated >= 300:
                try:
                    await self.refresh_overview()
                except Exception as exc:
                    self.error('Market overview', exc)
                    self.overview_updated = time.monotonic()
            await self.check_health()
            self.publish(self.snapshot())
            await asyncio.sleep(.1)

    async def close(self):
        self.closing = True
        await self.disconnect_flow()
        if self.runtime:
            try:
                self.runtime.stop()
            except Exception as exc:
                self.error('Monitor shutdown', exc)
        if self.monitor_task:
            self.monitor_task.cancel()
            await asyncio.gather(self.monitor_task, return_exceptions=True)
        for client in (self.api, self.exchange):
            if client is not None:
                try:
                    await client.close()
                except Exception as exc:
                    self.error('Client shutdown', exc)
