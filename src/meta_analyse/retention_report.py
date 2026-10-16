"""Conservative lifecycle policy for historical archive storage.

This module never deletes data. It distinguishes raw archives from durable
derived outputs and produces auditable dry-run summaries.
"""
from __future__ import annotations

from dataclasses import dataclass

from .history_retention import RetentionDecision, RetentionRecord, plan_retention


@dataclass(frozen=True)
class RetentionSummary:
    total_files: int
    eligible_files: int
    reclaimable_bytes: int
    blocked_files: int
    decisions: tuple[RetentionDecision, ...]


def summarize_retention(records: list[RetentionRecord], *,
                        min_age_days: int = 90, now=None) -> RetentionSummary:
    decisions = tuple(plan_retention(records, now=now, min_age_days=min_age_days))
    eligible = sum(1 for item in decisions if item.eligible)
    return RetentionSummary(len(decisions), eligible,
                            sum(item.bytes_reclaimable for item in decisions),
                            len(decisions) - eligible, decisions)
