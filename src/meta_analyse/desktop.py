"""Minimal Windows desktop; asynchronous collector runs on a separate thread."""
from __future__ import annotations
import asyncio
import os
import sys
import threading
from datetime import datetime, timedelta, timezone
from dataclasses import replace
from PySide6.QtCore import QTimer, QObject, Signal, Slot, Qt
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                               QLabel, QListWidget, QMessageBox, QDoubleSpinBox, QCheckBox, QTabWidget,
                               QTableWidget, QTableWidgetItem, QAbstractItemView, QProgressBar, QLineEdit)
from .storage import Store
from decimal import Decimal
from .trader_theme import TRADER_QSS
from .desktop_service import DesktopService, DesktopSnapshot
from .flow_style import flow_cell_style
from .flow_diff import changed_rows
from .freshness import freshness_for_feed
from .freshness_style import freshness_colors_for_feed


class FlowTableItem(QTableWidgetItem):
    """Numeric market values sort by value; symbols/placeholders sort as text."""
    def __lt__(self, other):
        def key(text):
            try:
                number = Decimal(text)
                if number.is_finite():
                    return (0, number)
            except ArithmeticError:
                pass
            return (1, text)
        return key(self.text()) < key(other.text())



class WorkerSignals(QObject):
    snapshot = Signal(object)
    error = Signal(str)


class Window(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Meta Analyse — read-only / paper")
        self.resize(1000, 690)
        self.loop = asyncio.new_event_loop()
        self._closing = False
        self._submission_lock = threading.Lock()
        self._worker_stopped = threading.Event()
        self._closed = False
        self._snapshot = DesktopSnapshot()
        self.signals = WorkerSignals(self)
        self.signals.snapshot.connect(self._receive_snapshot, Qt.ConnectionType.QueuedConnection)
        self.signals.error.connect(self._receive_error, Qt.ConnectionType.QueuedConnection)
        dsn = os.getenv("META_ANALYSE_DSN", "")
        self.store = Store(dsn) if dsn else None
        self.service = DesktopService(self.store, self.signals.snapshot.emit)
        self.worker = threading.Thread(target=self._thread_main, name="meta-analyse-worker", daemon=False)
        self.tabs = QTabWidget()
        root = QVBoxLayout(self)
        root.addWidget(self.tabs)
        market = QWidget()
        layout = QVBoxLayout(market)
        layout.addWidget(QLabel("Top-20 Bybit USDT perpetual, 24h absolute move; min $1m turnover"))
        self.market_table = QTableWidget(0, 7)
        self.market_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.market_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.market_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.market_table.setSortingEnabled(True)
        self.market_table.setHorizontalHeaderLabels(["Symbol", "24h change", "24h turnover $", "OI contracts", "OI change 5m", "OI change 1h", "History readiness"])
        layout.addWidget(self.market_table)
        actions = QHBoxLayout()
        for name, fn in (("Refresh symbols", self.refresh), ("Open selected MetaScalp combos", self.open_selected),
                         ("Start monitoring", self.start), ("Find MetaScalp", self.find_metascalp)):
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
        flow = QWidget()
        flow_layout = QVBoxLayout(flow)
        flow_layout.addWidget(QLabel("Order flow diagnostics — read-only; data are unverified until live feeds connect"))
        self.flow_status = QLabel("No validated trade/orderbook stream attached")
        flow_layout.addWidget(self.flow_status)
        self.flow_table = QTableWidget(0, 9)
        self.flow_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.flow_table.setAlternatingRowColors(True)
        self.flow_table.setSortingEnabled(True)
        self.flow_table.setHorizontalHeaderLabels(["Symbol", "Level", "POC", "Delta", "Tape/s", "Quality", "Spread ticks", "Book imbalance", "Nearby wall"])
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
        history = QWidget()
        history_layout = QVBoxLayout(history)
        history_layout.addWidget(QLabel("PostgreSQL historical trades — UNVERIFIED; UTC interval [start, end)"))
        history_controls = QHBoxLayout()
        self.history_symbol = QLineEdit()
        self.history_symbol.setPlaceholderText("Explicit symbol, e.g. BTCUSDT")
        history_controls.addWidget(self.history_symbol)
        now = datetime.now(timezone.utc).replace(microsecond=0)
        self.history_start = QLineEdit((now - timedelta(hours=1)).isoformat())
        self.history_end = QLineEdit(now.isoformat())
        history_controls.addWidget(self.history_start)
        history_controls.addWidget(self.history_end)
        self.history_load_button = QPushButton("Load history")
        self.history_load_button.clicked.connect(self.load_flow_history)
        history_controls.addWidget(self.history_load_button)
        history_layout.addLayout(history_controls)
        self.history_status = QLabel("UNVERIFIED — no history requested")
        history_layout.addWidget(self.history_status)
        self.history_table = QTableWidget(0, 5)
        self.history_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.history_table.setHorizontalHeaderLabels(["UTC timestamp", "Trade ID", "Side", "Price", "Quantity"])
        self.history_table.setSortingEnabled(True)
        history_layout.addWidget(self.history_table)
        self.tabs.addTab(history, "Flow History")
        diagnostics = QWidget()
        diagnostics_layout = QVBoxLayout(diagnostics)
        diagnostics_layout.addWidget(QLabel("Persisted feed events and reported gaps; not proof of exchange completeness"))
        self.diagnostics_state = QLabel("Disconnected — counters hidden")
        diagnostics_layout.addWidget(self.diagnostics_state)
        self.diagnostics_table = QTableWidget(0, 5)
        self.diagnostics_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.diagnostics_table.setSortingEnabled(True)
        self.diagnostics_table.setHorizontalHeaderLabels(["Feed / symbol", "Persisted events", "Reported gaps", "Last persisted age (s)", "Freshness"])
        diagnostics_layout.addWidget(self.diagnostics_table)
        self.tabs.addTab(diagnostics, "Diagnostics")
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.repaint_state)
        self.timer.start(1500)
        self.worker.start()
        self.refresh()
    def _thread_main(self):
        asyncio.set_event_loop(self.loop)
        try:
            self.service.initialize()
            self.loop.create_task(self.service.publish_loop())
            self.loop.run_forever()
        except Exception as exc:
            self.signals.error.emit(f'Worker initialization failed ({type(exc).__name__})')
        finally:
            # Block submissions before draining, including construction failure.
            with self._submission_lock:
                self._worker_stopped.set()
            try:
                self.loop.run_until_complete(self._shutdown())
                self.loop.run_until_complete(self.loop.shutdown_asyncgens())
                self.loop.run_until_complete(self.loop.shutdown_default_executor())
            finally:
                self.loop.close()

    @Slot(object)
    def _receive_snapshot(self, snapshot):
        if not self._closing:
            self._snapshot = snapshot
            self.repaint_state()
    @Slot(str)
    def _receive_error(self, message):
        if not self._closing:
            self._snapshot = replace(self._snapshot, status=message)
            self.status.setText(message)
    def schedule(self, task):
        with self._submission_lock:
            if self._closing or self._worker_stopped.is_set():
                task.close()
                return None
            future = asyncio.run_coroutine_threadsafe(task, self.loop)
        def done(f):
            if f.cancelled():
                return
            try:
                f.result()
            except Exception as exc:
                self.signals.error.emit(f'Background operation failed ({type(exc).__name__})')
        future.add_done_callback(done)
        return future
    def refresh(self):
        self.schedule(self.service.refresh())
    def selected_symbols(self):
        table = self.market_table
        return [table.item(i.row(), 0).text() for i in table.selectionModel().selectedRows()
                if table.item(i.row(), 0) is not None]
    def open_selected(self):
        selected = self.selected_symbols()
        if not selected:
            QMessageBox.information(self, "Select tickers", "Select one or several symbols.")
            return
        self.schedule(self.service.open_selected(tuple(selected)))
    def find_metascalp(self):
        self.schedule(self.service.locate_metascalp())
    def start(self):
        self.schedule(self.service.start_monitor())
    def connect_flow(self):
        selected = tuple(self.selected_symbols())
        if not self.store:
            QMessageBox.warning(self, "Database required", "Set META_ANALYSE_DSN before connecting raw market feeds.")
            return
        if not selected or len(selected) > 20:
            QMessageBox.warning(self, "Selection required", "Select 1-20 markets.")
            return
        self.connect_flow_button.setEnabled(False)
        self.schedule(self._start_flow(selected, Decimal(str(self.level_price.value()))))
    async def _start_flow(self, symbols, level):
        self.service.connect_flow(symbols, level)
    def disconnect_flow(self):
        self.connect_flow_button.setEnabled(False)
        self.schedule(self._stop_flow())
    async def _stop_flow(self):
        await self.service.disconnect_flow()
    def load_flow_history(self):
        symbol = self.history_symbol.text().strip()
        try:
            start = datetime.fromisoformat(self.history_start.text().strip())
            end = datetime.fromisoformat(self.history_end.text().strip())
            if not symbol or start.tzinfo is None or end.tzinfo is None or start >= end:
                raise ValueError("invalid symbol or interval")
        except ValueError:
            QMessageBox.warning(self, "Flow History", "Specify symbol and timezone-aware ISO start/end.")
            return
        self.history_status.setText("Loading — UNVERIFIED")
        self.history_load_button.setEnabled(False)
        self._previous_history = None
        self._history_min_request_id = self._snapshot.flow_history_request_id + 1
        self.history_table.setRowCount(0)
        future = self.schedule(self.service.load_flow_history(symbol=symbol, start=start, end=end))
        if future is None:
            self.history_load_button.setEnabled(True)
            self.history_status.setText("Flow History unavailable: worker stopped — UNVERIFIED")

    def toggle_paper(self, enabled):
        self.schedule(self.service.configure_paper(enabled=bool(enabled)))
    def update_rules(self):
        if not all(hasattr(self, name) for name in ("threshold", "stop", "fee")):
            return
        rules = tuple(Decimal(str(spin.value())) / 100 for spin in (self.threshold, self.stop, self.fee))
        self.schedule(self.service.configure_paper(rules=rules))
    def repaint_state(self):
        self.status.setText(self._snapshot.status)
        overview = self._snapshot.overview
        readiness = dict(self._snapshot.readiness)
        table = self.market_table
        sorting = table.isSortingEnabled()
        selected = set(self.selected_symbols())
        table.setSortingEnabled(False)
        try:
            table.setRowCount(len(overview))
            for i, values in enumerate(overview):
                for j, value in enumerate(values):
                    cell = table.item(i, j)
                    if cell is None:
                        table.setItem(i, j, FlowTableItem(value))
                    elif cell.text() != value:
                        cell.setText(value)
                # No false 100%: historical ticks/trades and candle coverage are
                # not yet verified by the live market overview endpoint.
                bar = table.cellWidget(i, 6)
                if bar is None:
                    bar = QProgressBar(table)
                    bar.setRange(0, 100)
                    bar.setValue(0)
                    bar.setFormat('Not verified')
                    table.setCellWidget(i, 6, bar)
                progress = readiness.get(values[0])
                if progress is None or progress.percent is None:
                    bar.setValue(0)
                    bar.setFormat('Not verified')
                    bar.setStyleSheet('')
                else:
                    bar.setValue(progress.percent)
                    bar.setFormat(f'{progress.percent}% — {progress.status}')
                    color = '#26965c' if progress.percent == 100 and progress.status == 'verified' else '#b58b35'
                    bar.setStyleSheet(f'QProgressBar::chunk {{ background-color: {color}; }}')
        finally:
            table.setSortingEnabled(sorting)
            if selected:
                from PySide6.QtCore import QItemSelection, QItemSelectionModel
                selection = QItemSelection()
                for i in range(table.rowCount()):
                    cell = table.item(i, 0)
                    if cell is not None and cell.text() in selected:
                        selection.select(table.model().index(i, 0), table.model().index(i, table.columnCount()-1))
                table.selectionModel().select(selection, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)
        history = self._snapshot.flow_history
        if (history is None and self._snapshot.flow_history_request_id >= getattr(self, "_history_min_request_id", 0)
                and self._snapshot.status.startswith("Flow History failed")):
            self.history_load_button.setEnabled(True)
            self.history_status.setText(self._snapshot.status + " — UNVERIFIED")
        elif (history is None and self._snapshot.flow_history_request_id >= getattr(self, "_history_min_request_id", 0)
                and self._snapshot.status.startswith("Flow History unavailable")):
            self.history_load_button.setEnabled(True)
            self.history_status.setText(self._snapshot.status + " — UNVERIFIED")
        if (history is not None
                and self._snapshot.flow_history_request_id >= getattr(self, "_history_min_request_id", 0)
                and history is not getattr(self, "_previous_history", None)):
            self._previous_history = history
            self.history_load_button.setEnabled(True)
            self.history_status.setText(
                f"{history.symbol}: {len(history.trades)} trades — UNVERIFIED"
                + (" — TRUNCATED (narrow time range)" if history.truncated else ""))
            table = self.history_table
            sorting = table.isSortingEnabled()
            table.setSortingEnabled(False)
            try:
                table.setRowCount(len(history.trades))
                for row, trade in enumerate(history.trades):
                    values = (trade.timestamp.isoformat(), trade.trade_id,
                              trade.side, str(trade.price), str(trade.quantity))
                    for col, value in enumerate(values):
                        item = table.item(row, col)
                        if item is None:
                            table.setItem(row, col, FlowTableItem(value))
                        elif item.text() != value:
                            item.setText(value)
            finally:
                table.setSortingEnabled(sorting)
        self.flow_status.setText(self._snapshot.flow_status)
        self.connect_flow_button.setEnabled(self._snapshot.flow_state in ('disconnected', 'failed'))
        self.stop_flow_button.setEnabled(self._snapshot.flow_state in ('connecting', 'connected', 'failed'))
        rows = self._snapshot.flow_rows
        changed, rebuild = changed_rows(getattr(self, "_previous_flow_rows", ()), rows)
        if rebuild or changed:
            table = self.flow_table
            sorting = table.isSortingEnabled()
            updates = table.updatesEnabled()
            table.setUpdatesEnabled(False)
            table.setSortingEnabled(False)
            try:
                if rebuild:
                    table.setRowCount(len(rows))
                    positions = {entry.symbol: i for i, entry in enumerate(rows)}
                else:
                    # Sorting changes visual positions without changing snapshot order.
                    positions = {table.item(i, 0).text(): i for i in range(table.rowCount())}
                for index in changed:
                    entry = rows[index]
                    row = positions[entry.symbol]
                    values = (entry.symbol, entry.level, entry.poc, entry.delta,
                              entry.tape_rate, entry.quality, entry.spread, entry.imbalance, entry.wall)
                    for col, value in enumerate(values):
                        item = table.item(row, col)
                        if item is None:
                            item = FlowTableItem(value)
                            table.setItem(row, col, item)
                        elif item.text() != value:
                            item.setText(value)
                        foreground, background = flow_cell_style(col, value, entry.quality)
                        if item.foreground().color().name() != foreground.lower():
                            item.setForeground(QBrush(QColor(foreground)))
                        if item.background().color().name() != background.lower():
                            item.setBackground(QBrush(QColor(background)))
                self._previous_flow_rows = rows
            finally:
                table.setSortingEnabled(sorting)
                table.setUpdatesEnabled(updates)
        self.diagnostics_state.setText(
            "Connected — session counters (not exchange completeness)"
            if self._snapshot.flow_state == "connected"
            else f"{self._snapshot.flow_state.capitalize()} — counters hidden"
        )
        event_counts = dict(self._snapshot.market_events)
        gap_counts = dict(self._snapshot.market_gaps)
        ages = dict(self._snapshot.market_ages)
        keys = sorted(event_counts.keys() | gap_counts.keys() | ages.keys())
        table = self.diagnostics_table
        sorting = table.isSortingEnabled()
        table.setSortingEnabled(False)
        try:
            current_keys = {table.item(i, 0).text(): i for i in range(table.rowCount())
                            if table.item(i, 0) is not None}
            if set(current_keys) != set(keys) or len(current_keys) != table.rowCount():
                table.setRowCount(len(keys))
                for i, key in enumerate(keys):
                    table.setItem(i, 0, QTableWidgetItem(key))
                current_keys = {key: i for i, key in enumerate(keys)}
            for key in keys:
                i = current_keys[key]
                for col, value in ((1, str(event_counts.get(key, 0))),
                                   (2, str(gap_counts.get(key, 0))),
                                   (3, f"{ages[key]:.1f}" if key in ages else "—"),
                                   (4, freshness_for_feed(key, ages.get(key)))):
                    item = table.item(i, col)
                    if item is None:
                        item = FlowTableItem(value)
                        table.setItem(i, col, item)
                    elif item.text() != value:
                        item.setText(value)
                    if col == 4:
                        foreground, background = freshness_colors_for_feed(key, ages.get(key))
                        if item.foreground().color().name() != foreground.lower():
                            item.setForeground(QBrush(QColor(foreground)))
                        if item.background().color().name() != background.lower():
                            item.setBackground(QBrush(QColor(background)))
        finally:
            table.setSortingEnabled(sorting)
        self.stats.setRowCount(len(self._snapshot.stats))
        for row, values in enumerate(self._snapshot.stats):
            for col, value in enumerate(values):
                self.stats.setItem(row, col, QTableWidgetItem(value))
    async def _shutdown(self):
        # Let owners finish their one cancellation/closing handshake first.
        # Cancelling every asyncio task here a second time can interrupt an
        # already-running disconnect and abandon the WebSocket transport.
        await self.service.close()
        current = asyncio.current_task()
        tasks = [task for task in asyncio.all_tasks() if task is not current]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    def _finish_close(self):
        if self.worker.is_alive():
            return
        self.timer.stop()
        self._closed = True
        self.close()
    def closeEvent(self, event):
        if self._closed or self._worker_stopped.is_set() and not self.worker.is_alive():
            self.timer.stop()
            event.accept()
            return
        event.ignore()
        if self._closing:
            return
        self._closing = True
        self.setEnabled(False)
        self.status.setText("Closing connections...")
        self.timer.stop()
        self.timer.timeout.disconnect()
        self.timer.timeout.connect(self._finish_close)
        self.timer.start(20)
        with self._submission_lock:
            if not self._worker_stopped.is_set():
                future = asyncio.run_coroutine_threadsafe(self._shutdown(), self.loop)
                future.add_done_callback(lambda _f: self.loop.call_soon_threadsafe(self.loop.stop))


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(TRADER_QSS)
    window = Window()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
