"""Minimal Windows desktop; asynchronous collector runs on a separate thread."""
from __future__ import annotations
import asyncio
import os
import sys
import threading
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                               QLabel, QListWidget, QMessageBox, QDoubleSpinBox, QCheckBox, QTabWidget,
                               QTableWidget, QTableWidgetItem)
from .ports import MetaScalp
from .exchange import BybitPublic
from .runtime import Runtime
from .storage import Store
from .analysis_coordinator import AnalysisCoordinator
from .liquidity import large_levels
from decimal import Decimal
from .trader_theme import TRADER_QSS
from .flow_bridge import FlowBridge
from .analysis_session import AnalysisSession

class Window(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Meta Analyse — read-only / paper")
        self.resize(1000, 690)
        self.loop = asyncio.new_event_loop()
        self.api = MetaScalp()
        self.exchange = BybitPublic()
        dsn = os.getenv("META_ANALYSE_DSN", "")
        self.store = Store(dsn) if dsn else None
        self.runtime = Runtime(self.api, self.exchange, self.store)
        self.worker = threading.Thread(target=self._thread_main, daemon=True)
        self.worker.start()
        self.tabs = QTabWidget()
        root = QVBoxLayout(self)
        root.addWidget(self.tabs)
        market = QWidget()
        layout = QVBoxLayout(market)
        layout.addWidget(QLabel("Top-20 Bybit USDT perpetual, 24h absolute move; min $1m turnover"))
        self.list = QListWidget()
        self.list.setSelectionMode(QListWidget.MultiSelection)
        layout.addWidget(self.list)
        actions = QHBoxLayout()
        for name, fn in (("Refresh symbols", self.refresh), ("Open selected MetaScalp combos", self.open_selected),
                         ("Start monitoring", self.start)):
            button = QPushButton(name)
            button.clicked.connect(fn)
            actions.addWidget(button)
        layout.addLayout(actions)
        self.status = QLabel("Standby; no exchange orders are ever sent")
        layout.addWidget(self.status)
        self.tabs.addTab(market, "Markets")
        paper = QWidget()
        controls = QVBoxLayout(paper)
        self.enabled = QCheckBox("Enable paper simulator (NOT live trading)")
        self.enabled.toggled.connect(self.toggle_paper)
        controls.addWidget(self.enabled)
        for label, name, value in (("Entry deviation %", "threshold", 1.5), ("Stop %", "stop", 0.5),
                                   ("Taker fee per side %", "fee", 0.06)):
            line = QHBoxLayout()
            line.addWidget(QLabel(label))
            spin = QDoubleSpinBox()
            spin.setRange(0.001, 20)
            spin.setDecimals(3)
            spin.setValue(value)
            spin.valueChanged.connect(lambda _v: self.update_rules())
            setattr(self, name, spin)
            line.addWidget(spin)
            controls.addLayout(line)
        self.stats = QTableWidget(0, 5)
        self.stats.setHorizontalHeaderLabels(["Symbol", "Trades", "Wins", "Net PnL $", "Open position"])
        controls.addWidget(self.stats)
        self.tabs.addTab(paper, "Paper results")
        self.analysis = AnalysisCoordinator({})
        self.flow_bridge = FlowBridge()
        self.live_session = None
        self.flow_start_error = None
        self.flow_starting = False
        flow = QWidget()
        flow_layout = QVBoxLayout(flow)
        flow_layout.addWidget(QLabel("Order flow diagnostics — read-only; data are unverified until live feeds connect"))
        self.flow_status = QLabel("No validated trade/orderbook stream attached")
        flow_layout.addWidget(self.flow_status)
        self.flow_table = QTableWidget(0, 6)
        self.flow_table.setAlternatingRowColors(True)
        self.flow_table.setSortingEnabled(True)
        self.flow_table.setHorizontalHeaderLabels(["Symbol", "Level", "POC", "Delta", "Tape trades/s", "Quality"])
        flow_layout.addWidget(self.flow_table)
        controls_row = QHBoxLayout()
        self.level_price = QDoubleSpinBox()
        self.level_price.setDecimals(6)
        self.level_price.setMaximum(1000000000)
        self.level_price.setPrefix("Level: ")
        controls_row.addWidget(self.level_price)
        self.connect_flow_button = QPushButton("Connect selected flow")
        self.connect_flow_button.clicked.connect(self.connect_flow)
        controls_row.addWidget(self.connect_flow_button)
        self.stop_flow_button = QPushButton("Disconnect flow")
        self.stop_flow_button.clicked.connect(self.disconnect_flow)
        controls_row.addWidget(self.stop_flow_button)
        flow_layout.addLayout(controls_row)
        self.tabs.addTab(flow, "Order flow")
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.repaint_state)
        self.timer.start(1500)
        self.refresh()

    def _thread_main(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def schedule(self, task):
        future = asyncio.run_coroutine_threadsafe(task, self.loop)
        def done(f):
            try:
                f.result()
            except Exception as exc:
                print("Background operation failed:", exc, file=sys.stderr)
        future.add_done_callback(done)
        return future

    def refresh(self):
        self.schedule(self.runtime.refresh_watchlist())

    def open_selected(self):
        selected = [item.text() for item in self.list.selectedItems()]
        if not selected:
            QMessageBox.information(self, "Select tickers", "Select one or several symbols.")
            return
        self.schedule(self.api.open_combos(selected))

    def start(self):
        if self.store:
            self.schedule(asyncio.to_thread(self.store.initialize))
        self.schedule(self.runtime.run())
        self.status.setText("Monitor requested; see console/log for connectivity errors")

    def connect_flow(self):
        selected = [item.text() for item in self.list.selectedItems()]
        if not self.store:
            QMessageBox.warning(self, "Database required",
                                "Set META_ANALYSE_DSN before connecting raw market feeds.")
            return
        if not selected or len(selected) > 20:
            QMessageBox.warning(self, "Selection required", "Select 1–20 markets.")
            return
        if self.live_session is not None:
            QMessageBox.information(self, "Already running", "Flow session is already running.")
            return
        self.flow_start_error = None
        self.flow_starting = True
        self.connect_flow_button.setEnabled(False)
        self.flow_status.setText("Connecting; historical continuity remains unverified")
        self.schedule(self._start_flow(selected, Decimal(str(self.level_price.value()))))

    async def _start_flow(self, symbols, level):
        try:
            from .instruments import instruments
            metadata = await instruments(self.exchange)
            tick_sizes = {s: metadata[s].tick_size for s in symbols if s in metadata}
            if len(tick_sizes) != len(symbols):
                raise ValueError("Missing tick sizes for selected symbols")
            session = AnalysisSession(self.store, self.exchange, tick_sizes,
                                      on_update=self._flow_execution,
                                      on_gap=self._invalidate_flow,
                                      on_book_update=self._flow_book)
            if level > 0:
                for symbol in symbols:
                    session.select_level(symbol, level)
            await session.start()
            self.live_session = session
            self.flow_starting = False
        except Exception as exc:
            self.flow_bridge.invalidate(symbols)
            print("Flow startup failed:", exc, file=sys.stderr)
            self.flow_start_error = str(exc)
            self.flow_starting = False

    async def _flow_execution(self,symbol,footprint,tape):
        await self.flow_bridge.update(symbol,footprint,tape)
        self.flow_bridge.trade_observed(symbol)

    async def _flow_book(self,symbol):
        self.flow_bridge.book_observed(symbol)

    async def _invalidate_flow(self, symbols, reason):
        self.flow_bridge.invalidate(symbols)

    def disconnect_flow(self):
        if self.live_session is None:
            self.flow_status.setText("No active flow session")
            self.connect_flow_button.setEnabled(True)
            return
        self.schedule(self._stop_flow())

    async def _stop_flow(self):
        session = self.live_session
        if session is None:
            return
        try:
            await session.stop()
        finally:
            self.live_session = None
            self.flow_bridge.invalidate(list(session.analysis.tapes))
            self.flow_start_error = None

    def toggle_paper(self, enabled):
        self.runtime.paper.enabled = enabled

    def update_rules(self):
        if not all(hasattr(self, name) for name in ("threshold", "stop", "fee")):
            return
        from decimal import Decimal as D
        engine = self.runtime.paper
        engine.threshold = D(str(self.threshold.value())) / 100
        engine.stop_pct = D(str(self.stop.value())) / 100
        engine.fee_rate = D(str(self.fee.value())) / 100

    def repaint_state(self):
        selected = {item.text() for item in self.list.selectedItems()}
        current = [self.list.item(i).text() for i in range(self.list.count())]
        if current != self.runtime.symbols:
            self.list.clear()
            self.list.addItems(self.runtime.symbols)
            for i in range(self.list.count()):
                self.list.item(i).setSelected(self.list.item(i).text() in selected)
        if self.flow_start_error:
            self.flow_status.setText("Connection failed: " + self.flow_start_error[:180])
            self.connect_flow_button.setEnabled(True)
        elif self.live_session is not None:
            self.flow_status.setText("Streams connected — historical continuity NOT verified")
        elif not self.flow_starting:
            self.connect_flow_button.setEnabled(True)
            self.flow_status.setText("Disconnected — data marked UNVERIFIED")
        rows = self.flow_bridge.snapshot()
        self.flow_table.setSortingEnabled(False)
        self.flow_table.setRowCount(len(rows))
        for row, entry in enumerate(rows):
            values = (entry.symbol, entry.level, entry.poc, entry.delta,
                      entry.tape_rate, entry.quality)
            for col, value in enumerate(values):
                self.flow_table.setItem(row, col, QTableWidgetItem(value))
        self.flow_table.setSortingEnabled(True)
        engine = self.runtime.paper
        symbols = sorted(set(self.runtime.symbols) | {f.symbol for f in engine.fills})
        self.stats.setRowCount(len(symbols))
        for i, symbol in enumerate(symbols):
            fills = [f for f in engine.fills if f.symbol == symbol]
            values = [symbol, str(len(fills)), str(sum(f.net > 0 for f in fills)),
                      str(round(sum((f.net for f in fills), __import__('decimal').Decimal(0)), 4)),
                      engine.positions[symbol].side if symbol in engine.positions else "-"]
            for j, value in enumerate(values):
                self.stats.setItem(i, j, QTableWidgetItem(value))

    def closeEvent(self, event):
        self.runtime.stop()
        if self.live_session is not None:
            future = asyncio.run_coroutine_threadsafe(self.live_session.stop(), self.loop)
            try:
                future.result(timeout=5)
            except Exception as exc:
                print("Flow shutdown failed:", exc, file=sys.stderr)
        self.loop.call_soon_threadsafe(self.loop.stop)
        super().closeEvent(event)

def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(TRADER_QSS)
    window = Window()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
