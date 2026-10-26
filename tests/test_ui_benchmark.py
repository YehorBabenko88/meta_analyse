"""Deterministic synthetic Qt benchmark admission and refusal regressions."""
import asyncio
import json

import pytest
from scripts import benchmark_flow_ui as bench
from scripts import project_ui_benchmark as projection
from meta_analyse.desktop_service import DesktopService


def test_benchmark_initialization_admits_real_callback_without_live_clients():
    service = DesktopService(None, lambda snapshot: None)
    symbols = tuple(f'SYM{i:02d}USDT' for i in range(20))
    bench.initialize_synthetic(service, symbols)
    asyncio.run(service._flow_execution(symbols[0], {'poc': '100', 'delta': '1'}, None))
    assert len(service.bridge.snapshot()) == 1
    assert service.api is service.exchange is service.session is None
    assert service.bridge.snapshot()[0].quality == 'UNVERIFIED'


def test_empty_render_samples_refuse_without_zero_or_pass():
    result = bench.sample_summary([], [], [], 1)
    assert result['reason'] == 'NO_RENDER_SAMPLES'
    assert result['render_median_ms'] is None
    assert result['render_p95_ms'] is None
    assert result['render_fps'] is None


@pytest.mark.parametrize('frames,latencies,beats,reason', [
    ([1], [], [1, 1.01], 'NO_SNAPSHOT_LATENCY_SAMPLES'),
    ([1], [1], [], 'NO_HEARTBEAT_SAMPLES'),
    ([float('nan')], [1], [1, 1.01], 'INVALID_MEASUREMENT'),
    ([1], [float('inf')], [1, 1.01], 'INVALID_MEASUREMENT'),
])
def test_partial_or_nonfinite_measurements_fail_closed(frames, latencies, beats, reason):
    assert bench.sample_summary(frames, latencies, beats, 1)['reason'] == reason


def test_real_measurements_are_preserved():
    result = bench.sample_summary([1, 3, 2], [4, 5], [1, 1.01, 1.03], 2)
    assert result['reason'] == 'NONE'
    assert result['render_median_ms'] == 2
    assert result['render_fps'] == 1.5
    assert result['render_max_ms'] == 3


def test_producer_exception_is_consumed_and_sanitized():
    from concurrent.futures import Future
    future = Future()
    future.set_exception(RuntimeError('private-dsn-token-host-path'))
    assert bench.producer_outcome(future) == 'PRODUCER_FAILED'
    assert 'private' not in json.dumps(bench.producer_outcome(future))


def test_incomplete_or_cancelled_producer_never_passes():
    from concurrent.futures import Future
    future = Future()
    assert bench.producer_outcome(future) == 'PRODUCER_INCOMPLETE'
    future.cancel()
    assert bench.producer_outcome(future) == 'PRODUCER_FAILED'


def test_supervisor_timeout_replaces_stale_pass_with_unavailable_metrics(monkeypatch,tmp_path,capsys):
    output=tmp_path/'result.json'
    output.write_text('{"status":"PASS"}')
    def timeout(*args,**kwargs):
        assert kwargs['timeout']==15.4
        assert kwargs['stdout']==kwargs['stderr']==bench.subprocess.DEVNULL
        raise bench.subprocess.TimeoutExpired('private-command-token-path',15.4)
    monkeypatch.setattr(bench.subprocess,'run',timeout)
    assert bench.supervise(['--seconds','.4','--output',str(output)])==1
    result=json.loads(projection.checked(output.read_bytes()))
    assert result['reason']=='BENCHMARK_TIMEOUT'
    assert result['metrics_status']==result['diagnostics_status']=='UNAVAILABLE'
    assert 'private-command-token-path' not in output.read_text()+capsys.readouterr().out


@pytest.mark.parametrize('fault', ['none', 'disconnected', 'producer_exception', 'async_task_exception',
                                 'qt_repaint_exception','shutdown_exception'])
def test_actual_offscreen_pipeline_and_faults(app, monkeypatch, tmp_path, fault, capsys):
    """Real Qt queued signals, worker callbacks and shutdown, not fake frames."""
    if fault == 'disconnected':
        original = bench.initialize_synthetic
        def disconnected(service, symbols):
            original(service, symbols)
            service.flow_state = 'disconnected'
        monkeypatch.setattr(bench, 'initialize_synthetic', disconnected)
    if fault == 'producer_exception':
        async def fail(*args):
            raise RuntimeError('private-dsn-token-host-path')
        monkeypatch.setattr(bench, 'produce_events', fail)
    if fault == 'async_task_exception':
        original = bench.initialize_synthetic
        def initialize(service, symbols):
            original(service, symbols)
            async def fail():
                raise RuntimeError('private-dsn-token-host-path')
            asyncio.get_event_loop().call_soon(lambda: asyncio.create_task(fail()))
        monkeypatch.setattr(bench, 'initialize_synthetic', initialize)
    if fault == 'qt_repaint_exception':
        original = bench.Window.repaint_state
        original_produce = bench.produce_events
        failing = [False]
        def repaint(window):
            if failing[0]: raise RuntimeError('private-dsn-token-host-path')
            return original(window)
        async def produce(*args):
            async def later():
                await asyncio.sleep(.2)
                failing[0] = True
            asyncio.create_task(later())
            return await original_produce(*args)
        monkeypatch.setattr(bench.Window,'repaint_state',repaint)
        monkeypatch.setattr(bench,'produce_events',produce)
    if fault == 'shutdown_exception':
        async def close(service):
            raise RuntimeError('private-dsn-token-host-path')
        monkeypatch.setattr(bench.DesktopService,'close',close)
    output = tmp_path/'result.json'
    code = bench.main(['--seconds', '.4', '--events-per-second', '1000', '--output', str(output)])
    result = json.loads(output.read_text())
    assert json.loads(projection.checked(output.read_bytes())) == result
    assert result['worker_stopped'] and result['loop_closed']
    assert result['diagnostics']['thread_violations'] == 0
    if fault == 'none':
        assert code == 0 and result['status'] == 'PASS'
        assert result['render_samples'] > 0
        assert result['diagnostics']['published_twenty_rows'] > 0
        assert result['diagnostics']['bridge_rows'] == 20
    else:
        assert code == 1 and result['status'] == 'FAIL_CLOSED'
        assert result['reason'] == {'disconnected':'NO_RENDER_SAMPLES',
                                   'producer_exception':'PRODUCER_FAILED',
                                   'async_task_exception':'ASYNC_OR_UI_ERROR',
                                   'qt_repaint_exception':'ASYNC_OR_UI_ERROR',
                                   'shutdown_exception':'ASYNC_OR_UI_ERROR'}[fault]
        if fault in ('disconnected','producer_exception'):
            assert result['render_samples'] == 0
            assert result['render_median_ms'] is None
        elif fault == 'async_task_exception':
            assert result['diagnostics']['async_errors'] > 0
    captured = capsys.readouterr()
    assert 'private-dsn-token-host-path' not in output.read_text()+captured.out+captured.err
    for key, value in [('platform','private-hostname'),('reason','private-exception'),
                       ('pid',123),('events',True),('render_p95_ms',float('nan'))]:
        malformed = dict(result, **{key:value})
        with pytest.raises(ValueError,match='PUBLIC_EVIDENCE_REJECTED'):
            projection.checked(json.dumps(malformed).encode())
    source = dict(sha='a'*40,expected_sha='a'*40,tree_sha='b'*40,event='push',event_sha='a'*40)
    receipt = dict(sha='a'*40,tree='b'*40,event='push',event_sha='a'*40,run_id='123',run_attempt='1',job='test')
    monkeypatch.setattr(projection.public,'provenance',lambda value: receipt)
    source_path = tmp_path/'source.json'
    source_path.write_text(json.dumps(source))
    public = tmp_path/'public'
    projection.publish(public,source_path,output)
    projection.validate(public)
    wrong='failure' if result['status']=='PASS' else 'success'
    with pytest.raises(ValueError):
        projection.publish(tmp_path/'mismatched-outcome',source_path,output,wrong)
    assert not (tmp_path/'mismatched-outcome').exists()
    assert 'private-dsn-token-host-path' not in ''.join(p.read_text() for p in public.iterdir())
    monkeypatch.setattr(projection.public,'provenance',lambda value: dict(receipt,run_attempt='2'))
    with pytest.raises(ValueError): projection.validate(public)
    monkeypatch.setattr(projection.public,'provenance',lambda value: receipt)
    (public/'ui-benchmark.json').write_text('{}')
    with pytest.raises(ValueError): projection.validate(public)
