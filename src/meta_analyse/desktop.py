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
        self.tabs.addTab(QLabel("DOM wall tracking/acceleration: planned next milestone."), "Order flow")
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
        self.loop.call_soon_threadsafe(self.loop.stop)
        super().closeEvent(event)

def main():
    app = QApplication(sys.argv)
    window = Window()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
