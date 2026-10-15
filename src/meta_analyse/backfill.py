"""Read-only history scheduler with explicit coverage, never claim absent bars exist."""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from .history import collect_history, validate_fixed_interval, yearly_from_daily

FIXED = {"M1":timedelta(minutes=1),"H1":timedelta(hours=1),"D1":timedelta(days=1),"W1":timedelta(weeks=1)}

class BackfillCoordinator:
    def __init__(self, exchange, store):
        self.exchange=exchange
        self.store=store

    async def instrument(self, metadata, end_ms=None, timeframes=("H1","D1","W1","MO1")):
        end_ms=end_ms or int(datetime.now(timezone.utc).timestamp()*1000)
        if metadata.launch_ms >= end_ms:
            raise ValueError("listing time is not earlier than backfill end")
        report={}
        for tf in timeframes:
            report[tf]=await collect_history(self.exchange,self.store,metadata.symbol,tf,
                                             metadata.launch_ms,end_ms)
        return report

    @staticmethod
    def validate(candles, start, end, timeframe):
        if timeframe not in FIXED:
            raise ValueError("monthly bars require calendar-month boundary validation")
        return validate_fixed_interval(candles,start,end,FIXED[timeframe])
