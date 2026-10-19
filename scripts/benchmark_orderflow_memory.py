"""Measure Order Flow aggregation time and peak Python allocations.

Run: python scripts/benchmark_orderflow_memory.py
Uses deterministic synthetic data; no network or live orders.
"""
from __future__ import annotations

import argparse
import gc
import time
import tracemalloc
from decimal import Decimal

from meta_analyse.orderflow_aggregation import aggregate_by_price, aggregate_by_time
from meta_analyse.orderflow_metrics import Trade


def sample_trades(count: int):
    price = Decimal("100.00")
    volume = Decimal("0.125")
    for index in range(count):
        yield Trade(
            timestamp_ms=index * 10,
            price=price + Decimal(index % 100) / Decimal(100),
            volume=volume,
            side=("buy", "sell", "unknown")[index % 3],
        )


def measure(name: str, trades: tuple[Trade, ...], aggregate, bucket):
    gc.collect()
    tracemalloc.start()
    start = time.perf_counter()
    try:
        rows = aggregate(iter(trades), bucket)
        elapsed = time.perf_counter() - start
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    print(f"{name}: trades={len(trades)} buckets={len(rows)} elapsed_s={elapsed:.3f} peak_mib={peak / (1024 * 1024):.2f}")
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trades", type=int, default=100_000)
    args = parser.parse_args()
    if args.trades < 0:
        parser.error("--trades must be nonnegative")
    trades = tuple(sample_trades(args.trades))
    measure("time", trades, aggregate_by_time, 1000)
    measure("price", trades, aggregate_by_price, Decimal("0.10"))


if __name__ == "__main__":
    main()
