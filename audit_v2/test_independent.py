"""Independent invariants: failures are audit findings, never xfailed or suppressed."""
import asyncio
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import gzip
import hashlib
from pathlib import Path
import pytest
from meta_analyse.archive_db_import import parse_trade, import_verified_archive
from meta_analyse.bybit_archive_audit import audit_trade_gzip
from meta_analyse.desktop_service import DesktopService


def row(timestamp='1735689600', size='2'):
    return dict(trdMatchID='id1', timestamp=timestamp, price='100.000000000000000000000001', size=size, side='Buy')


def archive(path, rows):
    import csv
    with gzip.open(path, 'wt', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['trdMatchID', 'timestamp', 'price', 'size', 'side'])
        writer.writeheader()
        writer.writerows(rows)
    return path


@pytest.mark.parametrize('timestamp,expected', [
    ('1735775999.999999999999999999999', datetime(2025,1,1,23,59,59,999999,tzinfo=timezone.utc)),
    ('1735689600.000000999999999999999', datetime(2025,1,1,tzinfo=timezone.utc)),
])
def test_decimal_timestamp_floor_does_not_round(timestamp, expected):
    assert parse_trade(row(timestamp))[1] == expected


def test_audit_timestamp_below_maximum_stays_in_range(tmp_path):
    path = archive(tmp_path/'max.csv.gz', [row('253402300799.99999999999999999')])
    result = audit_trade_gzip(path)
    assert result.valid
    assert result.first_ms < 253402300800000


def test_csv_auditor_and_importer_agree_on_zero_quantity(tmp_path):
    record = row(size='0')
    path = archive(tmp_path/'zero.csv.gz', [record])
    audited = audit_trade_gzip(path).valid
    try:
        parse_trade(record)
        imported = True
    except ValueError:
        imported = False
    assert audited == imported


@pytest.mark.asyncio
@pytest.mark.parametrize('outcome', ['unavailable', 'error', 'cancelled'])
async def test_history_terminal_state_stops_showing_loading(monkeypatch, outcome):
    import meta_analyse.desktop_service as module
    service = DesktopService(None if outcome == 'unavailable' else object(), lambda _: None)
    entered = asyncio.Event()
    async def read(*args, **kwargs):
        entered.set()
        if outcome == 'error':
            raise ConnectionError('controlled audit DB failure')
        await asyncio.Event().wait()
    monkeypatch.setattr(module.asyncio, 'to_thread', read)
    start = datetime(2025,1,1,tzinfo=timezone.utc)
    task = asyncio.create_task(service.load_flow_history(symbol='BTCUSDT', start=start, end=start+timedelta(days=1)))
    if outcome == 'cancelled':
        await entered.wait()
        task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    assert 'loading' not in service.snapshot().orderflow_status.lower()


def test_pr9_fail_closed_gate_is_present_in_integration():
    assert Path('scripts/check_integration_junit.py').is_file()
    text = Path('.github/workflows/ci.yml').read_text()
    assert '.[test,archive]' in text
    assert 'Verify baseline suite ran without skips' in text


@pytest.mark.asyncio
async def test_cancelled_lock_wait_does_not_leak_lock(tmp_path):
    from meta_analyse.archive_file_lock import async_archive_file_lock, archive_file_lock
    destination = tmp_path/'audit.gz'
    entered = asyncio.Event()
    async def waiter():
        entered.set()
        async with async_archive_file_lock(destination):
            pytest.fail('contended lock unexpectedly acquired')
    with archive_file_lock(destination):
        waiting = asyncio.create_task(waiter())
        await entered.wait()
        waiting.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiting
    async with async_archive_file_lock(destination, timeout=0):
        pass


@pytest.mark.asyncio
async def test_full_archive_postgres_orderflow_desktop_user_path(audit_store, audit_app, tmp_path, monkeypatch):
    from aiohttp import ClientSession, web
    from meta_analyse.archive_ingestion import acquire_archive
    from meta_analyse.desktop import Window
    from meta_analyse.flow_history_storage import read_flow_history
    rows = [row(), dict(row('1735689601', '1'), trdMatchID='id2', side='Sell')]
    source = archive(tmp_path/'source.gz', rows).read_bytes()
    application = web.Application()
    async def handler(request):
        assert request.method == 'GET'
        return web.Response(body=source, headers={'ETag':'"audit-v2"'})
    application.router.add_get('/archive', handler)
    runner = web.AppRunner(application)
    await runner.setup()
    site = web.TCPSite(runner, '127.0.0.1', 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    public_url = 'https://public.bybit.com/trading/BTCUSDT/BTCUSDT2025-01-01.csv.gz'
    try:
        async with ClientSession() as client:
            class LoopbackSession:
                def get(self, url, **kwargs):
                    assert url == public_url
                    return client.get(f'http://127.0.0.1:{port}/archive', **kwargs)
            path = tmp_path/'downloaded.csv.gz'
            receipt = await acquire_archive(LoopbackSession(), public_url, path, day=date(2025,1,1))
        assert receipt.valid and not receipt.complete
        result = await asyncio.to_thread(import_verified_archive, audit_store, path, asdict(receipt), symbol='BTCUSDT', batch_size=1)
        assert result['rows'] == 2
        again = await asyncio.to_thread(import_verified_archive, audit_store, path, asdict(receipt), symbol='BTCUSDT', batch_size=1)
        assert again['resumed_from'] == 2
        start = datetime(2025,1,1,tzinfo=timezone.utc)
        history = read_flow_history(audit_store, symbol='BTCUSDT', start=start, end=start+timedelta(days=1))
        assert len(history.trades) == 2 and history.status == 'UNVERIFIED'
        assert history.trades[0].price == Decimal(rows[0]['price'])
        async def refresh(self):
            pass
        monkeypatch.setattr(DesktopService, 'refresh', refresh)
        monkeypatch.setenv('META_ANALYSE_DSN', audit_store.dsn)
        window = Window()
        window.show()
        async def until(predicate):
            async with asyncio.timeout(10):
                while not predicate():
                    audit_app.processEvents()
                    await asyncio.sleep(.005)
        try:
            window.history_symbol.setText('BTCUSDT')
            window.history_start.setText(start.isoformat())
            window.history_end.setText((start+timedelta(days=1)).isoformat())
            window.history_load_button.click()
            await until(lambda: window.history_table.rowCount()==2 and window.orderflow_history_table.rowCount()==1)
            assert window._snapshot.flow_history.trades[0].price == Decimal(rows[0]['price'])
            assert window._snapshot.orderflow_rows[0].delta == '1'
            assert 'UNVERIFIED' in window.orderflow_history_status.text()
            assert window.history_load_button.isEnabled()
        finally:
            window.close()
            await until(lambda: not window.worker.is_alive() and not window.isVisible())
            assert window.loop.is_closed()
    finally:
        await runner.cleanup()


def test_original_postgres_error_survives_both_cleanup_failures(audit_store, tmp_path):
    import psycopg
    from meta_analyse.storage_migrations import initialize_archive_schema
    initialize_archive_schema(audit_store)
    with audit_store.connect() as conn:
        conn.execute("ALTER TABLE meta_analyse.historical_trades ADD CONSTRAINT audit_original_failure CHECK (trade_id <> 'id1')")
    path = archive(tmp_path/'bad-insert.gz', [row()])
    receipt = dict(valid=True, complete=False, url='https://audit.invalid/archive', rows=1,
                   bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    cleanup = []
    class Connection:
        def __init__(self, real):
            self.real = real
        def __enter__(self):
            self.real.__enter__()
            return self
        def __exit__(self, *args):
            return self.real.__exit__(*args)
        def __getattr__(self, key):
            return getattr(self.real, key)
        @property
        def autocommit(self):
            return self.real.autocommit
        @autocommit.setter
        def autocommit(self, value):
            self.real.autocommit = value
        def execute(self, query, *args, **kwargs):
            text = str(query)
            if "SET status='failed'" in text:
                cleanup.append('checkpoint')
                raise RuntimeError('secondary failed-checkpoint error')
            if 'pg_advisory_unlock(' in text:
                cleanup.append('unlock')
                raise RuntimeError('secondary unlock error')
            return self.real.execute(query, *args, **kwargs)
    class Store:
        def connect(self):
            return Connection(audit_store.connect())
    with pytest.raises(psycopg.errors.CheckViolation, match='audit_original_failure'):
        import_verified_archive(Store(), path, receipt, symbol='BTCUSDT', batch_size=1)
    assert cleanup == ['checkpoint', 'unlock']
