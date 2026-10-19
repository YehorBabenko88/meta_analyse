"""Bounded comparison of immutable UI rows to avoid needless Qt cell repainting."""
from __future__ import annotations

def changed_rows(previous, current):
    """Return changed row indices; row count changes require full rebuild."""
    if len(previous)!=len(current):
        return tuple(range(len(current))),True
    if any(a.symbol!=b.symbol for a,b in zip(previous,current)):
        return tuple(range(len(current))),True
    return tuple(i for i,(a,b) in enumerate(zip(previous,current)) if a!=b),False
