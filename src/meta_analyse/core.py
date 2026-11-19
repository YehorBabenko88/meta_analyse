"""Deterministic price/volume logic shared by live runtime and tests."""
from __future__ import annotations
from dataclasses import dataclass, field
from decimal import Decimal
from market_profile_math import price_bucket, volume_profile_poc, untouched_decimal_levels, flow_window_metrics, wall_turnover_ratios
from datetime import datetime, timezone, timedelta
from collections import deque

D = Decimal

def floor_minute(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        raise ValueError("UTC offset required")
    return ts.astimezone(timezone.utc).replace(second=0, microsecond=0)

@dataclass(frozen=True)
class Candle:
    start: datetime
    high: Decimal
    low: Decimal
    open: Decimal
    close: Decimal
    volume: Decimal = D("0")

@dataclass(frozen=True)
class Level:
    price: Decimal
    kind: str
    source_start: datetime
    timeframe: str

def untouched_levels(candles: list[Candle], timeframe: str) -> list[Level]:
    """Only CLOSED candles; equal wick touch invalidates a previous level."""
    rows = [(int(c.start.timestamp()*1000),c.high,c.low) for c in candles]
    results = untouched_decimal_levels(rows)
    dates = {int(c.start.timestamp()*1000): c.start for c in candles}
    return [Level(price,kind,dates[start],timeframe) for kind,price,start in results]

@dataclass(frozen=True)
class Trade:
    symbol: str
    time: datetime
    price: Decimal
    size: Decimal
    side: str
    high: Decimal | None = None
    low: Decimal | None = None

@dataclass
class Minute:
    start: datetime
    tick: Decimal
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal = D(0)
    quote_volume: Decimal = D(0)
    buy_volume: Decimal = D(0)
    sell_volume: Decimal = D(0)
    profile: dict[Decimal, Decimal] = field(default_factory=dict)
    complete: bool = True

    @property
    def poc(self) -> Decimal:
        return volume_profile_poc(self.profile, close=self.close)

    def add(self, t: Trade) -> None:
        if floor_minute(t.time) != self.start:
            raise ValueError("trade outside candle minute")
        self.high = max(self.high, t.high if t.high is not None else t.price)
        self.low = min(self.low, t.low if t.low is not None else t.price)
        self.close = t.price
        self.volume += t.size
        self.quote_volume += t.price * t.size
        if t.side.lower() in {"buy", "1"}:
            self.buy_volume += t.size
        elif t.side.lower() in {"sell", "2"}:
            self.sell_volume += t.size
        bucket = price_bucket(t.price, self.tick)
        self.profile[bucket] = self.profile.get(bucket, D(0)) + t.size

def new_minute(t: Trade, tick: Decimal, complete: bool = True) -> Minute:
    minute = Minute(floor_minute(t.time), tick, t.price, t.price, t.price, t.price, complete=complete)
    minute.add(t)
    return minute

@dataclass
class Position:
    symbol: str
    side: str
    entry: Decimal
    target: Decimal
    stop: Decimal
    size: Decimal
    entry_time: datetime
    entry_fee: Decimal

@dataclass
class PaperFill:
    symbol: str
    side: str
    entry: Decimal
    exit: Decimal
    reason: str
    gross: Decimal
    fees: Decimal
    net: Decimal
    exit_time: datetime

class PaperEngine:
    """Next-minute POC paper mean reversion, one position per instrument."""
    def __init__(self, *, notional=D("100"), threshold=D("0.015"), stop_pct=D("0.005"), fee_rate=D("0.0006"), slippage_bps=D("2")):
        self.notional = D(notional)
        self.threshold = D(threshold)
        self.stop_pct = D(stop_pct)
        self.fee_rate = D(fee_rate)
        self.slippage = D(slippage_bps) / D(10000)
        self.reference: dict[str, tuple[datetime, Decimal]] = {}
        self.positions: dict[str, Position] = {}
        self.fills: list[PaperFill] = []
        self.enabled = False

    def on_closed_minute(self, symbol: str, minute: Minute) -> None:
        if not minute.complete:
            self.reference.pop(symbol, None)
            return
        self.reference[symbol] = (minute.start, minute.poc)

    def on_trade(self, trade: Trade) -> PaperFill | None:
        if not self.enabled:
            return None
        symbol = trade.symbol
        position = self.positions.get(symbol)
        if position:
            if position.side == "long":
                triggered = "stop" if trade.price <= position.stop else ("target" if trade.price >= position.target else "")
                exit_price = min(trade.price, position.stop) if triggered == "stop" else position.target
                exit_price *= (D(1) - self.slippage)
                gross = (exit_price - position.entry) * position.size
            else:
                triggered = "stop" if trade.price >= position.stop else ("target" if trade.price <= position.target else "")
                exit_price = max(trade.price, position.stop) if triggered == "stop" else position.target
                exit_price *= (D(1) + self.slippage)
                gross = (position.entry - exit_price) * position.size
            if not triggered:
                return None
            exit_fee = position.size * exit_price * self.fee_rate
            fill = PaperFill(symbol, position.side, position.entry, exit_price, triggered, gross,
                             position.entry_fee + exit_fee, gross - position.entry_fee - exit_fee, trade.time)
            self.fills.append(fill)
            del self.positions[symbol]
            return fill
        ref = self.reference.get(symbol)
        if not ref or floor_minute(trade.time) != ref[0] + timedelta(minutes=1):
            return None
        poc = ref[1]
        if poc <= 0:
            return None
        if trade.price >= poc * (D(1) + self.threshold):
            side = "short"
            entry = trade.price * (D(1) - self.slippage)
            stop = entry * (D(1) + self.stop_pct)
        elif trade.price <= poc * (D(1) - self.threshold):
            side = "long"
            entry = trade.price * (D(1) + self.slippage)
            stop = entry * (D(1) - self.stop_pct)
        else:
            return None
        if entry == poc:
            return None
        size = self.notional / entry
        self.positions[symbol] = Position(symbol, side, entry, poc, stop, size, trade.time, self.notional * self.fee_rate)
        self.reference.pop(symbol, None)
        return None

class RollingFlow:
    def __init__(self):
        self.trades: deque[tuple[datetime, Decimal, str]] = deque()

    def add(self, t: Trade):
        self.trades.append((t.time, t.price * t.size, t.side.lower()))
        cutoff = t.time - timedelta(hours=1)
        while self.trades and self.trades[0][0] < cutoff:
            self.trades.popleft()

    def metrics(self, now: datetime) -> dict:
        out = {}
        for seconds in (60, 300, 3600):
            rows=[(int(ts.timestamp()*1000),amt,side) for ts,amt,side in self.trades]
            out[seconds] = flow_window_metrics(rows,int(now.timestamp()*1000),seconds)
        return out

    def wall_score(self, price: Decimal, size: Decimal, now: datetime) -> dict:
        metrics = self.metrics(now)
        return wall_turnover_ratios(price,size,
                    {window:data["turnover_usd"] for window,data in metrics.items()})
