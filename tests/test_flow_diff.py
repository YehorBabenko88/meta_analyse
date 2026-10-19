from meta_analyse.flow_diff import changed_rows
from meta_analyse.flow_bridge import FlowRow

def row(symbol="BTCUSDT",delta="0"):
    return FlowRow(symbol,"—","100",delta,"1","PROVISIONAL")

def test_identical_rows_do_not_repaint():
    assert changed_rows((row(),),(row(),))==((),False)

def test_only_changed_row_repaints():
    assert changed_rows((row(),row("ETHUSDT")),(row(delta="5"),row("ETHUSDT")))==((0,),False)

def test_reordering_or_length_change_requires_full_rebuild():
    assert changed_rows((row(),row("ETHUSDT")),(row("ETHUSDT"),row()))==((0,1),True)
    assert changed_rows((row(),),(row(),row("ETHUSDT")))==((0,1),True)
