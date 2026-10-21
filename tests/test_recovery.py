from decimal import Decimal as D
from types import SimpleNamespace
from meta_analyse.recovery import decide_recovery
from meta_analyse.crossing_quality import CrossingObservation,crossed_prices

def test_pending_journal_cannot_mutate_without_verified_history():
    record=SimpleNamespace(state="pending")
    d=decide_recovery(record,history_verified=False,connection_verified=True,instrument_verified=True)
    assert d.requires_recompute and not d.can_mutate_terminal

def test_recovery_requires_verified_terminal_mapping():
    record=SimpleNamespace(state="failed")
    d=decide_recovery(record,history_verified=True,connection_verified=False,instrument_verified=True)
    assert not d.can_mutate_terminal

def test_crossing_from_gap_does_not_delete_level():
    o=CrossingObservation(D("90"),D("110"),False,"exchange_execution")
    assert not crossed_prices(o,D("100"))

def test_contiguous_execution_crossing_is_eligible():
    o=CrossingObservation(D("90"),D("110"),True,"exchange_execution")
    assert crossed_prices(o,D("100"))
