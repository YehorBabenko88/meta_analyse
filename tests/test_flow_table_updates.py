from dataclasses import replace
import pytest
from PySide6.QtCore import Qt
from meta_analyse.desktop import Window
from meta_analyse.desktop_service import DesktopService, DesktopSnapshot
from meta_analyse.flow_bridge import FlowRow
from test_desktop_lifecycle import pump

@pytest.fixture
def flow_window(app, monkeypatch):
    async def idle(*args):
        import asyncio
        await asyncio.Event().wait()
    async def refresh(*args):
        pass
    monkeypatch.setattr(DesktopService, 'publish_loop', idle)
    monkeypatch.setattr(DesktopService, 'refresh', refresh)
    window = Window()
    window.timer.stop()
    window.tabs.setCurrentIndex(2)
    window.show()
    yield window
    window.close()
    pump(app, lambda: not window.worker.is_alive() and not window.isVisible())

def row(symbol, delta='1', quality='UNVERIFIED'):
    return FlowRow(symbol, '100', '100', delta, '5', quality, '2', '.1', 'bid 99')

def render(window, rows):
    window._receive_snapshot(DesktopSnapshot(flow_rows=tuple(rows)))

def contents(window):
    return {window.flow_table.item(i,0).text(): tuple(window.flow_table.item(i,c).text() for c in range(9))
            for i in range(window.flow_table.rowCount())}

@pytest.mark.parametrize('column,order', [(0,Qt.AscendingOrder),(0,Qt.DescendingOrder),(3,Qt.AscendingOrder),(3,Qt.DescendingOrder)])
def test_changed_instrument_keeps_identity_after_sort(flow_window, column, order):
    a, b, c = row('AAAUSDT','9'), row('BBBUSDT','100'), row('CCCUSDT','20')
    render(flow_window, [a,b,c])
    flow_window.flow_table.sortItems(column,order)
    render(flow_window, [replace(a,delta='7',poc='102'),b,c])
    values = contents(flow_window)
    assert values['AAAUSDT'][2:4] == ('102','7')
    assert values['BBBUSDT'][3] == '100'
    assert values['CCCUSDT'][3] == '20'
    assert flow_window.flow_table.isSortingEnabled()

def test_membership_reorder_and_empty_snapshot(flow_window):
    for rows in [(row('AAAUSDT'),), (row('BBBUSDT'),row('AAAUSDT')),
                 (row('AAAUSDT','2'),row('BBBUSDT')), (row('BBBUSDT','3'),), ()]:
        render(flow_window, rows)
        assert set(contents(flow_window)) == {r.symbol for r in rows}
        for r in rows:
            assert contents(flow_window)[r.symbol][3] == r.delta
    assert flow_window.flow_table.rowCount() == 0

def test_unchanged_snapshot_retains_items_and_selection(flow_window):
    rows = (row('AAAUSDT'),row('BBBUSDT'))
    render(flow_window,rows)
    table = flow_window.flow_table
    item = table.item(0,3)
    table.setCurrentCell(0,3)
    render(flow_window,rows)
    assert table.item(0,3) is item
    assert table.currentItem() is item

def test_numeric_columns_sort_numerically(flow_window):
    render(flow_window,[row('AAAUSDT','9'),row('BBBUSDT','100'),row('CCCUSDT','20')])
    flow_window.flow_table.sortItems(3,Qt.AscendingOrder)
    assert [flow_window.flow_table.item(i,3).text() for i in range(3)] == ['9','20','100']

def test_quality_style_updates_and_user_can_disable_sorting(flow_window):
    r = row('AAAUSDT','2','PROVISIONAL')
    render(flow_window,[r])
    table = flow_window.flow_table
    original = table.item(0,3).foreground().color().name()
    table.setSortingEnabled(False)
    render(flow_window,[replace(r,quality='UNVERIFIED')])
    assert table.item(0,3).foreground().color().name() != original
    assert not table.isSortingEnabled()
