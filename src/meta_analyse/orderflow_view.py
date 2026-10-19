"""Immutable presentation models for order-flow analysis."""
from dataclasses import dataclass


@dataclass(frozen=True)
class OrderFlowViewRow:
    bucket: str
    buy: str
    sell: str
    delta: str
    cumulative_delta: str
    imbalance: str
    quality: str


def make_rows(buckets, *, quality="UNVERIFIED"):
    """Formatting only; quality must be supplied by the source validator."""
    return tuple(
        OrderFlowViewRow(
            str(key),
            str(metrics.buy_volume),
            str(metrics.sell_volume),
            str(metrics.delta),
            str(metrics.cumulative_delta),
            str(metrics.imbalance) if metrics.imbalance is not None else "—",
            quality,
        )
        for key, metrics in buckets
    )
