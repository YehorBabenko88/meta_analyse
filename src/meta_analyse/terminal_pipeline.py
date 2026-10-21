"""Attach the terminal crossing service to the durable Bybit pipeline.

An operator must explicitly supply a verified symbol-to-connection mapping.
"""
from __future__ import annotations
from .crossing_service import CrossingService
from .pipeline import RawPipeline

def build_terminal_pipeline(store, tick_sizes, level_sync, connection_for_symbol,
                            *, on_closed=None):
    crossing = CrossingService(level_sync, connection_for_symbol)

    async def on_execution(event, *, contiguous):
        await crossing.execution(event, contiguous=contiguous)

    async def on_gap(symbols, reason):
        for symbol in symbols:
            crossing.gap(symbol)

    pipeline = RawPipeline(store, tick_sizes, on_closed=on_closed,
                           on_execution=on_execution, on_gap=on_gap)
    return pipeline, crossing
