"""Opt-in, read-only public Bybit orderbook E2E probe.

No account credentials, order placement, DB mutation, or GUI control.
Requires explicit --enable-public-network; never run from ordinary CI.
"""
from __future__ import annotations
import argparse
import asyncio
import json
import os
from pathlib import Path
import time

from meta_analyse.orderbook_stream import OrderBookStream


def evaluate(record, *, min_snapshots=1):
    """Fail closed: a successful transport connection is not an E2E PASS."""
    if record.get("event_budget_exhausted") or record["snapshots"] < min_snapshots:
        return "BLOCKED"
    if record["false_valid"] or record["callback_errors"] or record["unexpected_exits"]:
        return "FAIL"
    if record["stale_symbols"] or record["pending_symbols"]:
        return "FAIL"
    return "PASS"


async def probe(symbols, duration, *, depth=50, max_events=200000):
    stop = asyncio.Event()
    now = time.monotonic()
    record = {
        "schema": 1, "symbols": list(symbols), "duration_seconds": duration,
        "snapshots": 0, "updates": 0, "gaps": 0, "false_valid": 0,
        "callback_errors": 0, "unexpected_exits": 0,
        "stale_symbols": [], "pending_symbols": list(symbols),
        "connection_epochs": 0, "event_limit": max_events,
        "event_budget_exhausted": False,
    }
    seen = set()
    last_update = {}
    async def on_book(symbol, book, timestamp):
        if not book.valid or book.update_id is None or book.sequence is None:
            record["false_valid"] += 1
            return
        if symbol not in seen:
            record["snapshots"] += 1
            seen.add(symbol)
        record["updates"] += 1
        last_update[symbol] = time.monotonic()
        if record["updates"] >= max_events:
            record["event_budget_exhausted"] = True
            stop.set()
    async def on_gap(symbols, reason):
        record["gaps"] += 1
        for symbol in symbols:
            seen.discard(symbol)
    stream = OrderBookStream(on_book, on_gap, depth=depth)
    task = asyncio.create_task(stream.run(list(symbols), stop))
    try:
        await asyncio.sleep(duration)
    finally:
        stop.set()
        try:
            await asyncio.wait_for(task, timeout=10)
        except asyncio.TimeoutError:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            record["unexpected_exits"] += 1
        except Exception:
            record["unexpected_exits"] += 1
    record["connection_epochs"] = stream.connection_epoch
    record["pending_symbols"] = sorted(set(symbols) - set(last_update))
    record["stale_symbols"] = sorted(s for s in symbols
                                      if s in last_update and time.monotonic() - last_update[s] > stream.silence_timeout)
    record["elapsed_seconds"] = round(time.monotonic() - now, 3)
    record["verdict"] = evaluate(record, min_snapshots=len(symbols))
    return record


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--enable-public-network", action="store_true")
    p.add_argument("--symbols", nargs="+", default=["BTCUSDT"])
    p.add_argument("--minutes", type=float, default=0.5)
    p.add_argument("--max-events", type=int, default=200000)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if not args.enable_public_network:
        p.error("Public network probe is opt-in: pass --enable-public-network")
    if os.getenv("CI"):
        p.error("Public network probe is forbidden in ordinary CI")
    if not (0 < args.minutes <= 1440) or not (1 <= len(args.symbols) <= 10):
        p.error("minutes must be (0,1440], symbols 1..10")
    if args.max_events < 1 or any(not s.isascii() or not s.isalnum() or len(s) > 20 for s in args.symbols):
        p.error("invalid event budget or symbol")
    result = asyncio.run(probe(tuple(args.symbols), args.minutes * 60, max_events=args.max_events))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"verdict": result["verdict"], "output": str(args.output)}))
    raise SystemExit(0 if result["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
