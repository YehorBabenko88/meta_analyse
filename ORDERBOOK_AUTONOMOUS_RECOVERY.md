# Orderbook autonomous recovery — 20 October 2026

## Scope and root cause

Baseline: independent candidate `13901274dac527f0aacfaf48481414b0971d6012` (PR #12).
In `OrderBookStream.run`, invalid delta called `on_gap` but continued receiving
from the same WebSocket. No resubscription was triggered; silent feeds also
had no stale-data watchdog.

## Recovery contract

1. At the beginning of each connection epoch, reset all books and publish a gap.
2. Only a valid snapshot from that epoch may establish VALID.
3. An invalid delta, malformed snapshot, sequence regression or malformed JSON
   invalidates data and forces the socket context to close.
4. Reconnect with bounded exponential backoff and jitter, then resubscribe.
5. A per-symbol inactivity watchdog also reconnects when no book messages arrive
   within the configured threshold. A quiet market is possible, so the default
   threshold (90 seconds) is a conservative heuristic, not proof of data loss.
6. Shutdown interrupts backoff through the stop event. No trading orders are sent.

## Fault-injection coverage

`tests/test_orderbook_autonomous_recovery.py` exercises invalid delta to
new socket/fresh snapshot, silent socket to new snapshot, and stop during
reconnect failure. Existing `tests/test_orderbook_recovery.py` covers duplicate,
out-of-order, malformed snapshots and the prohibition on delta bootstrapping.

## Remaining risks

No independent replay of the full PR #12 candidate with these changes has
yet been completed. Real Bybit outage behaviour, network queue overflow,
long-running reconnect exhaustion and exact Windows/Linux results require
confirmation. Therefore commissioning remains **NO-GO** pending evidence.
