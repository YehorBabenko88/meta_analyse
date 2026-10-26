"""Synthetic 20-instrument Qt benchmark; no network, DB, orders or MetaScalp writes.

python scripts/benchmark_flow_ui.py --platform windows --seconds 10 --output result.json
Run --renderer full for a full-cell-replacement reference under the same workload.
"""
import argparse
import asyncio
import json
import platform
import statistics
import threading
import time
import math
import tracemalloc
import os
import tempfile
import sys
import subprocess
from pathlib import Path
from dataclasses import replace
from PySide6.QtCore import QTimer, Slot, QThread
from PySide6.QtGui import QColor,QBrush
from PySide6.QtWidgets import QApplication,QTableWidgetItem
import shiboken6
import PySide6
from meta_analyse.desktop import Window
from meta_analyse.desktop_service import DesktopService,DesktopSnapshot
from meta_analyse.runtime import Runtime
from meta_analyse.flow_bridge import FlowRow
from meta_analyse.flow_style import flow_cell_style


def percentile(values,p):
    ordered=sorted(values)
    return ordered[min(len(ordered)-1,int((len(ordered)-1)*p))] if ordered else None


def initialize_synthetic(service, symbols):
    service.runtime = Runtime(None, None)
    service.runtime.symbols = list(symbols)
    # Exercise the real callback's admitted state, without a live session/client.
    # 'connecting' does not claim connected, trusted, or verified market data.
    service.flow_state = 'connecting'
    service.overview_updated = time.monotonic()


def producer_outcome(producer):
    if producer is None or not producer.done():
        return 'PRODUCER_INCOMPLETE'
    try:
        producer.result()  # Always consume asynchronous failures; never echo text.
    except BaseException:
        return 'PRODUCER_FAILED'
    return 'NONE'


def sample_summary(frames, latencies, heartbeats, elapsed):
    gaps = [(b-a)*1000 for a,b in zip(heartbeats, heartbeats[1:])]
    reason = ('NO_RENDER_SAMPLES' if not frames else
              'NO_SNAPSHOT_LATENCY_SAMPLES' if not latencies else
              'NO_HEARTBEAT_SAMPLES' if not gaps else 'NONE')
    if not all(type(v) in (int, float) and math.isfinite(v) and v >= 0
               for v in [*frames, *latencies, *gaps, elapsed]) or elapsed <= 0:
        reason = 'INVALID_MEASUREMENT'
    def valid(values):
        return values and all(math.isfinite(v) and v >= 0 for v in values)
    return dict(reason=reason, render_samples=len(frames),
                render_median_ms=statistics.median(frames) if valid(frames) else None,
                render_p95_ms=percentile(frames,.95) if valid(frames) else None,
                render_max_ms=max(frames) if valid(frames) else None,
                render_fps=len(frames)/elapsed if valid(frames) and elapsed > 0 else None,
                snapshot_to_render_p95_ms=percentile(latencies,.95) if valid(latencies) else None,
                heartbeat_p95_ms=percentile(gaps,.95) if valid(gaps) else None,
                heartbeat_max_ms=max(gaps) if valid(gaps) else None)

async def produce_events(service, symbols, args, state, lock, counters):
    started=time.perf_counter()
    batch=max(20,args.events_per_second//100)
    while time.perf_counter()-started < args.seconds:
        for _ in range(batch):
            index=state['events']%20
            await service._flow_execution(symbols[index],
                {'poc':'100','delta':str(state['events']),'trusted':False},None)
            state['events']+=1
        with lock:
            counters['bridge_rows']=len(service.bridge.snapshot())
        target=started+state['events']/args.events_per_second
        await asyncio.sleep(max(0,target-time.perf_counter()))
    state['producer_seconds']=time.perf_counter()-started


def arguments(argv):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds',type=float,default=10)
    parser.add_argument('--events-per-second',type=int,default=20000)
    parser.add_argument('--renderer',choices=['partial','full'],default='partial')
    parser.add_argument('--platform',choices=['offscreen','windows'],default='offscreen')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    if not math.isfinite(args.seconds) or not 0 < args.seconds <= 60 or not 0 < args.events_per_second <= 100000:
        parser.error('duration or event rate outside bounded synthetic workload')
    return args


def write_result(path, result):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.ui-benchmark-',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as stream:
            stream.write(json.dumps(result,indent=2,allow_nan=False)+'\n')
        os.replace(name,path)
    finally:
        if os.path.exists(name): os.unlink(name)


def supervise(argv):
    """Hard deadline outside Qt/worker threads; timeout never invents samples."""
    args=arguments(argv)
    deadline=args.seconds+15
    try:
        child=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--_worker',*argv],
                             stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=deadline)
        if __package__ in (None,''):
            sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
        from scripts.project_ui_benchmark import checked
        result=json.loads(checked(args.output.read_bytes()))
        if child.returncode not in (0,1) or (child.returncode==0)!=(result['status']=='PASS'):
            raise ValueError('INCONSISTENT_CHILD_OUTCOME')
    except Exception as exc:
        result=dict(schema_version=1,status='FAIL_CLOSED',
                    reason='BENCHMARK_TIMEOUT' if isinstance(exc,subprocess.TimeoutExpired) else 'BENCHMARK_INTERNAL_ERROR',
                    metrics_status='UNAVAILABLE',diagnostics_status='UNAVAILABLE',
                    supervisor_timeout_seconds=deadline)
        write_result(args.output,result)
    print(json.dumps(result,indent=2,allow_nan=False))
    return 0 if result['status']=='PASS' else 1


def main(argv=None):
    args=arguments(argv)
    os.environ['QT_QPA_PLATFORM']=args.platform
    symbols=tuple(f'SYM{i:02d}USDT' for i in range(20))
    frames,latencies,heartbeats=[],[],[]
    published,lock={},threading.Lock()
    state={'events':0,'producer_seconds':0,'close_event_ms':None,'closed':False,
           'measuring':False,'reason':'NONE'}
    counters={key:0 for key in ('published','published_twenty_rows','received','repaints',
                                'twenty_row_repaints','bridge_rows','async_errors','ui_errors',
                                'thread_violations','stamp_overflow')}
    def count(key):
        with lock:
            counters[key]=min(10000000,counters[key]+1)
    def initialize(service):
        initialize_synthetic(service,symbols)
        def loop_error(loop,context):
            count('async_errors')  # Context/exception may be private: never persist it.
        asyncio.get_event_loop().set_exception_handler(loop_error)
        original=service.publish
        def publish(snapshot):
            with lock:
                if state['measuring']:
                    counters['published']=min(10000000,counters['published']+1)
                    if len(snapshot.flow_rows)==20:
                        counters['published_twenty_rows']=min(10000000,counters['published_twenty_rows']+1)
                    if len(published)<1024:
                        published[id(snapshot)]=time.perf_counter()
                    else:
                        counters['stamp_overflow']=1
            original(snapshot)
        service.publish=publish
    async def refresh(service):
        pass
    old_initialize,old_refresh=DesktopService.initialize,DesktopService.refresh
    DesktopService.initialize=initialize
    DesktopService.refresh=refresh
    class MeasuredWindow(Window):
        def _thread_main(self):
            try:
                super()._thread_main()
            except BaseException:
                count('async_errors')
        async def _shutdown(self):
            try:
                await super()._shutdown()
            except BaseException:
                count('async_errors')
                raise
        @Slot(object)
        def _receive_snapshot(self,snapshot):
            if QThread.currentThread()!=self.thread():
                count('thread_violations')
                return
            if state['measuring']: count('received')
            try:
                super()._receive_snapshot(snapshot)
            except Exception:
                count('ui_errors')
                return
            finally:
                with lock:
                    stamp=published.pop(id(snapshot),None)
            if stamp is not None and len(snapshot.flow_rows)==20:
                latencies.append((time.perf_counter()-stamp)*1000)
        def repaint_state(self):
            try:
                self._repaint_measured()
            except Exception:
                count('ui_errors')
        def _repaint_measured(self):
            if QThread.currentThread()!=self.thread():
                count('thread_violations')
                return
            before=time.perf_counter()
            if args.renderer=='full':
                table=self.flow_table
                table.setSortingEnabled(False)
                table.setRowCount(len(self._snapshot.flow_rows))
                for row,entry in enumerate(self._snapshot.flow_rows):
                    values=(entry.symbol,entry.level,entry.poc,entry.delta,entry.tape_rate,
                            entry.quality,entry.spread,entry.imbalance,entry.wall)
                    for column,value in enumerate(values):
                        item=QTableWidgetItem(value)
                        foreground,background=flow_cell_style(column,value,entry.quality)
                        item.setForeground(QBrush(QColor(foreground)))
                        item.setBackground(QBrush(QColor(background)))
                        table.setItem(row,column,item)
                table.setSortingEnabled(True)
                self._previous_flow_rows=self._snapshot.flow_rows
            super().repaint_state()
            if state['measuring']:
                count('repaints')
                if len(self._snapshot.flow_rows)==20 and self.flow_table.rowCount()==20:
                    count('twenty_row_repaints')
                    frames.append((time.perf_counter()-before)*1000)
    owns_app=QApplication.instance() is None
    app=QApplication.instance() or QApplication([])
    window=MeasuredWindow()
    window.signals.error.connect(lambda _message: count('ui_errors'))
    window.tabs.setCurrentIndex(2)
    window.show()
    # Widget-update microbenchmark: unchanged snapshots and one-symbol deltas.
    rows=tuple(FlowRow(s,'100','100','1','5','UNVERIFIED') for s in symbols)
    window._receive_snapshot(DesktopSnapshot(symbols=symbols,flow_rows=rows))
    micro={}
    for mode in ('unchanged','one_changed','all_changed'):
        timings=[]
        for iteration in range(300):
            if mode=='one_changed':
                index=iteration%20
                rows=rows[:index]+(replace(rows[index],delta=str(iteration)),)+rows[index+1:]
            elif mode=='all_changed':
                rows=tuple(replace(r,delta=str(iteration)) for r in rows)
            before=time.perf_counter()
            window._receive_snapshot(DesktopSnapshot(symbols=symbols,flow_rows=rows))
            timings.append((time.perf_counter()-before)*1000)
        micro[mode]={'median_ms':statistics.median(timings),'p95_ms':percentile(timings,.95)}
    frames.clear()
    latencies.clear()
    # Never let microbenchmark rows satisfy the load measurement.
    window._receive_snapshot(DesktopSnapshot())
    state['measuring']=True
    tracemalloc.start()
    cpu_start=time.process_time()
    wall_start=time.perf_counter()
    producer=window.schedule(produce_events(window.service,symbols,args,state,lock,counters))
    heartbeat=QTimer()
    heartbeat.setInterval(10)
    heartbeat.timeout.connect(lambda: heartbeats.append(time.perf_counter()))
    heartbeat.start()
    closer=QTimer()
    closer.setInterval(20)
    def check_done():
        if state['closed'] or (producer is not None and not producer.done()):
            return
        state['reason']=producer_outcome(producer)
        state['closed']=True
        before=time.perf_counter()
        window.close()
        state['close_event_ms']=(time.perf_counter()-before)*1000
    closer.timeout.connect(check_done)
    closer.start()
    watchdog=QTimer()
    watchdog.setSingleShot(True)
    def timeout():
        state['reason']='BENCHMARK_TIMEOUT'
        if producer is not None: producer.cancel()
        window.close()
    watchdog.timeout.connect(timeout)
    watchdog.start(int((args.seconds+15)*1000))
    app.exec()
    heartbeat.stop()
    closer.stop()
    watchdog.stop()
    elapsed=time.perf_counter()-wall_start
    _,peak_bytes=tracemalloc.get_traced_memory()
    tracemalloc.stop()
    outcome=producer_outcome(producer)
    summary=sample_summary(frames,latencies,heartbeats,elapsed)
    reason=state['reason'] if state['reason']!='NONE' else outcome
    if reason=='NONE': reason=summary['reason']
    if reason=='NONE' and any(counters[k] for k in ('async_errors','ui_errors','thread_violations','stamp_overflow')):
        reason='ASYNC_OR_UI_ERROR'
    if reason=='NONE' and (window.worker.is_alive() or not window.loop.is_closed()): reason='SHUTDOWN_INCOMPLETE'
    if reason=='NONE' and counters['bridge_rows']!=20: reason='INCOMPLETE_TABLE'
    result={'schema_version':1,'status':'PASS' if reason=='NONE' else 'FAIL_CLOSED','reason':reason,
        'platform':platform.system(),'python':platform.python_version(),'qt_platform':app.platformName(),
        'pyside6':PySide6.__version__,'process_cpu_percent_one_core':100*(time.process_time()-cpu_start)/(time.perf_counter()-wall_start),
        'renderer':args.renderer,'instruments':20,'target_events_per_second':args.events_per_second,
        'events':state['events'],'producer_seconds':state['producer_seconds'],
        'actual_events_per_second':state['events']/state['producer_seconds'] if state['producer_seconds']>0 else None,'publication_hz':10,
        **{k:v for k,v in summary.items() if k!='reason'},'heartbeat_target_ms':10,
        'python_heap_peak_bytes':peak_bytes,'measurement_seconds':elapsed,'diagnostics':counters,
        'close_event_ms':state['close_event_ms'],'worker_stopped':not window.worker.is_alive(),
        'loop_closed':window.loop.is_closed(),'microbenchmark':micro,
        'limits':'Synthetic callbacks/Qt only; excludes exchange parsing, SQL persistence, network and microstructure algorithms.'}
    try:
        write_result(args.output,result)
        print(json.dumps(result,indent=2,allow_nan=False))
    finally:
        shiboken6.delete(window)
        if owns_app: shiboken6.delete(app)
        DesktopService.initialize,DesktopService.refresh=old_initialize,old_refresh
    return 0 if result['status']=='PASS' else 1

if __name__=='__main__':
    try:
        code=main(sys.argv[2:]) if sys.argv[1:2]==['--_worker'] else supervise(sys.argv[1:])
    except Exception:
        print('FAIL_CLOSED: BENCHMARK_INTERNAL_ERROR')
        code=1
    raise SystemExit(code)
