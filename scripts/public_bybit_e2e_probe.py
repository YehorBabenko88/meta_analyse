"""Opt-in, read-only public Bybit orderbook E2E probe.

No account credentials, order placement, DB mutation, or GUI control.
Requires explicit --enable-public-network; never run from ordinary CI.
"""
from __future__ import annotations
import argparse
import asyncio
import json
import math
import threading
import tempfile
import os
from pathlib import Path
import time

from meta_analyse.orderbook_stream import OrderBookStream


def health_state(*, valid, age_seconds, max_age_seconds):
    """Freshness classification only; never certifies persisted or displayed data."""
    if valid is not True:
        return "UNVERIFIED"
    if (type(age_seconds) not in (int, float) or type(max_age_seconds) not in (int, float)
            or not math.isfinite(age_seconds) or age_seconds < 0
            or not math.isfinite(max_age_seconds) or max_age_seconds <= 0
            or age_seconds > max_age_seconds):
        return "STALE"
    return "CURRENT"


def evaluate(record, *, min_snapshots=1):
    """Transport-only verdict; detected corruption takes precedence over missing proof."""
    if any(record[key] for key in ("false_valid", "callback_errors", "unexpected_exits")):
        return "FAIL"
    if (record.get("resource_budget_exhausted") or record.get("event_budget_exhausted")
            or record.get("shutdown_budget_exhausted")):
        return "BLOCKED"
    if record["snapshots"] < min_snapshots:
        return "BLOCKED"
    if record["stale_symbols"] or record["pending_symbols"]:
        return "FAIL"
    epoch = record.get("connection_epochs", 0)
    witnesses = record.get("snapshot_epoch_by_symbol", {})
    if (type(epoch) is not int or epoch < 1 or not record.get("symbols")
            or any(witnesses.get(s) != epoch for s in record["symbols"])):
        return "BLOCKED"
    return "TRANSPORT_PASS"


def sample_resources():
    # Portable, bounded process counters. These are not RSS/CPU measurements.
    return {"threads": threading.active_count(), "tasks": len(asyncio.all_tasks())}


async def probe(symbols, duration, *, depth=50, max_events=200000,
                stream_factory=None, clock=time.monotonic,
                resource_sampler=sample_resources, resource_limits=None,
                sample_interval=1.0, shutdown_timeout=10.0):
    """Observe transport with bounded records and cooperative shutdown.

    The shutdown timeout requests cancellation and blocks a successful verdict.
    It is not a hard execution deadline: retain ownership until the transport
    finishes cancellation, including a transport that resists cancellation.
    """
    symbols = tuple(symbols)
    if (not symbols or len(symbols) > 10 or len(set(symbols)) != len(symbols)
            or not math.isfinite(duration) or not 0 < duration <= 86400
            or type(max_events) is not int or max_events < 1
            or not math.isfinite(sample_interval) or sample_interval <= 0
            or not math.isfinite(shutdown_timeout) or shutdown_timeout <= 0):
        raise ValueError("invalid probe bounds")
    limits = dict(resource_limits or {"threads": 128, "tasks": 1024})
    if not limits or any(not math.isfinite(v) or v < 1 for v in limits.values()):
        raise ValueError("invalid resource limits")
    stop = asyncio.Event()
    now = clock()
    record = {
        "schema": 2, "scope": "public-orderbook-transport-only", "symbols": list(symbols),
        "duration_seconds": duration, "snapshots": 0, "updates": 0, "gaps": 0,
        "false_valid": 0, "callback_errors": 0, "unexpected_exits": 0,
        "stale_symbols": [], "pending_symbols": list(symbols),
        "connection_epochs": 0, "event_limit": max_events,
        "event_budget_exhausted": False, "resource_budget_exhausted": False,
        "shutdown_budget_exhausted": False,
        "resource_limits": limits, "resource_peaks": {}, "resource_samples": 0,
    }
    pending = set(symbols)
    last_update, last_sequence, last_update_id, snapshot_epochs = {}, {}, {}, {}
    latest_epoch = 0

    async def on_book(symbol, book, timestamp):
        nonlocal latest_epoch
        try:
            epoch = stream.connection_epoch
            if type(epoch) is not int or epoch < 1 or epoch < latest_epoch:
                record["false_valid"] += 1
                pending.update(symbols)
                return
            if epoch != latest_epoch:
                latest_epoch = epoch
                pending.update(symbols)
                last_sequence.clear()
                last_update_id.clear()
                snapshot_epochs.clear()
            kind = getattr(book, "message_type", None)
            if (symbol not in symbols or not book.valid
                    or type(book.update_id) is not int or book.update_id < 0
                    or type(book.sequence) is not int or book.sequence < 0
                    or kind not in ("snapshot", "delta")
                    or (symbol in pending and kind != "snapshot")
                    or (kind == "delta" and (book.sequence <= last_sequence.get(symbol, -1)
                        or book.update_id <= last_update_id.get(symbol, -1)))):
                record["false_valid"] += 1
                if symbol in symbols:
                    pending.add(symbol)
                return
            if kind == "snapshot":
                record["snapshots"] += 1
                snapshot_epochs[symbol] = epoch
                pending.discard(symbol)
            last_sequence[symbol] = book.sequence
            last_update_id[symbol] = book.update_id
            record["updates"] += 1
            last_update[symbol] = clock()
            if record["updates"] >= max_events:
                record["event_budget_exhausted"] = True
                stop.set()
        except Exception:
            record["callback_errors"] += 1
            stop.set()
            raise

    async def on_gap(affected, reason):
        record["gaps"] += 1
        for symbol in affected:
            pending.add(symbol)
            snapshot_epochs.pop(symbol, None)
            last_sequence.pop(symbol, None)
            last_update_id.pop(symbol, None)

    async def monitor():
        while not stop.is_set():
            try:
                sample = resource_sampler()
                record["resource_samples"] += 1
                for key, limit in limits.items():
                    value = sample[key]
                    if not math.isfinite(value) or value < 0:
                        raise ValueError("invalid resource sample")
                    record["resource_peaks"][key] = max(record["resource_peaks"].get(key, 0), value)
                    if value > limit:
                        record["resource_budget_exhausted"] = True
                if record["resource_budget_exhausted"]:
                    stop.set()
                    return
            except Exception:
                record["resource_budget_exhausted"] = True
                stop.set()
                return
            try:
                await asyncio.wait_for(stop.wait(), timeout=sample_interval)
            except asyncio.TimeoutError:
                pass

    stream = (stream_factory or OrderBookStream)(on_book, on_gap, depth=depth)
    task = asyncio.create_task(stream.run(list(symbols), stop))
    monitor_task = asyncio.create_task(monitor())
    stopper = asyncio.create_task(stop.wait())
    try:
        done, _ = await asyncio.wait((task, stopper), timeout=duration,
                                     return_when=asyncio.FIRST_COMPLETED)
        if task in done and not stop.is_set():
            record["unexpected_exits"] += 1
    finally:
        stop.set()
        # Cancellation is cooperative. Do not orphan a task merely to return
        # within a deadline; a resistant transport can keep this drain pending.
        done, _ = await asyncio.wait((task,), timeout=shutdown_timeout)
        if not done:
            record["shutdown_budget_exhausted"] = True
            task.cancel()
        result = await asyncio.gather(task, return_exceptions=True)
        if (isinstance(result[0], BaseException) and not record["unexpected_exits"]
                and not record["shutdown_budget_exhausted"]):
            record["unexpected_exits"] += 1
        await asyncio.gather(monitor_task, stopper, return_exceptions=True)
    record["connection_epochs"] = stream.connection_epoch
    record["snapshot_epoch_by_symbol"] = snapshot_epochs
    record["last_sequence_by_symbol"] = last_sequence
    record["pending_symbols"] = sorted(pending)
    record["unverified_at_exit"] = bool(pending)
    record["stale_symbols"] = sorted(s for s in symbols if s in last_update
        and clock() - last_update[s] > stream.silence_timeout)
    record["elapsed_seconds"] = round(clock() - now, 3)
    record["verdict"] = evaluate(record, min_snapshots=len(symbols))
    return record


def publish_new_output(output, result):
    """Publish closed JSON exclusively; never truncate an existing destination."""
    data=json.dumps(result,indent=2,sort_keys=True,allow_nan=False)
    output.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.metaanalyse-probe-',dir=output.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as stream:
            stream.write(data);stream.flush();os.fsync(stream.fileno())
        os.link(name,output)
    finally:
        Path(name).unlink(missing_ok=True)


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
    if os.path.lexists(args.output):p.error('Output already exists; refusing before network')
    result = asyncio.run(probe(tuple(args.symbols), args.minutes * 60, max_events=args.max_events))
    try:publish_new_output(args.output,result)
    except (OSError,ValueError):
        print('BLOCKED: public probe output unavailable');raise SystemExit(1)
    print(json.dumps({'verdict':result['verdict']}))
    raise SystemExit(0 if result["verdict"] == "TRANSPORT_PASS" else 1)


if __name__ == "__main__":
    main()
