"""Event-time freshness gates for asynchronous market-data sources."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class FeedState:
    timestamp_ms: int | None = None
    trusted: bool = False

@dataclass(frozen=True)
class Alignment:
    valid: bool
    reason: str
    skew_ms: int | None

class MarketClock:
    def __init__(self, max_skew_ms=2000, max_age_ms=5000):
        if max_skew_ms < 0 or max_age_ms <= 0:
            raise ValueError("invalid freshness limits")
        self.max_skew_ms=max_skew_ms
        self.max_age_ms=max_age_ms
        self.feeds={}

    def observe(self,source,symbol,timestamp_ms,*,trusted):
        if timestamp_ms <= 0:
            raise ValueError("invalid exchange timestamp")
        key=(source,symbol)
        previous=self.feeds.get(key)
        if previous and previous.timestamp_ms and timestamp_ms < previous.timestamp_ms:
            self.feeds[key]=FeedState(timestamp_ms,False)
            return False
        self.feeds[key]=FeedState(timestamp_ms,bool(trusted))
        return bool(trusted)

    def gap(self,source,symbol):
        self.feeds[(source,symbol)]=FeedState()

    def align(self,symbol,now_ms,sources=("trades","orderbook"),*,require_oi=False):
        if require_oi:
            sources=(*sources,"open_interest")
        states=[self.feeds.get((source,symbol),FeedState()) for source in sources]
        if any(not state.trusted or state.timestamp_ms is None for state in states):
            return Alignment(False,"unverified_feed",None)
        stamps=[state.timestamp_ms for state in states]
        if any(stamp>now_ms or now_ms-stamp>self.max_age_ms for stamp in stamps):
            return Alignment(False,"stale_or_future_data",None)
        skew=max(stamps)-min(stamps)
        if skew>self.max_skew_ms:
            return Alignment(False,"cross_feed_skew",skew)
        return Alignment(True,"aligned",skew)
