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
from pathlib import Path
from dataclasses import replace
from PySide6.QtCore import QTimer, Slot
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
    return ordered[min(len(ordered)-1,int((len(ordered)-1)*p))] if ordered else 0

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds',type=float,default=10)
    parser.add_argument('--events-per-second',type=int,default=20000)
    parser.add_argument('--renderer',choices=['partial','full'],default='partial')
    parser.add_argument('--platform',default='offscreen')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.seconds <= 0 or args.events_per_second <= 0:
        parser.error('duration and event rate must be positive')
    import os
    os.environ['QT_QPA_PLATFORM']=args.platform
    symbols=tuple(f'SYM{i:02d}USDT' for i in range(20))
    frames,latencies,heartbeats=[],[],[]
    published,lock={},threading.Lock()
    state={'events':0,'producer_seconds':0,'close_event_ms':None,'closed':False}
    def initialize(service):
        service.runtime=Runtime(None,None)
        service.runtime.symbols=list(symbols)
        original=service.publish
        def publish(snapshot):
            with lock:
                published[id(snapshot)]=time.perf_counter()
            original(snapshot)
        service.publish=publish
    async def refresh(service):
        pass
    DesktopService.initialize=initialize
    DesktopService.refresh=refresh
    class MeasuredWindow(Window):
        @Slot(object)
        def _receive_snapshot(self,snapshot):
            before=time.perf_counter()
            super()._receive_snapshot(snapshot)
            with lock:
                stamp=published.pop(id(snapshot),None)
            if stamp is not None and snapshot.flow_rows:
                latencies.append((time.perf_counter()-stamp)*1000)
        def repaint_state(self):
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
            if len(self._snapshot.flow_rows)==20:
                frames.append((time.perf_counter()-before)*1000)
    app=QApplication([])
    window=MeasuredWindow()
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
    async def produce():
        started=time.perf_counter()
        batch=max(20,args.events_per_second//100)
        while time.perf_counter()-started < args.seconds:
            for _ in range(batch):
                index=state['events']%20
                await window.service._flow_execution(symbols[index],
                    {'poc':'100','delta':str(state['events']),'trusted':False},None)
                state['events']+=1
            target=started+state['events']/args.events_per_second
            await asyncio.sleep(max(0,target-time.perf_counter()))
        state['producer_seconds']=time.perf_counter()-started
    cpu_start=time.process_time()
    wall_start=time.perf_counter()
    producer=window.schedule(produce())
    heartbeat=QTimer()
    heartbeat.setInterval(10)
    heartbeat.timeout.connect(lambda: heartbeats.append(time.perf_counter()))
    heartbeat.start()
    closer=QTimer()
    closer.setInterval(20)
    def check_done():
        if not producer.done() or state['closed']:
            return
        producer.result()
        state['closed']=True
        before=time.perf_counter()
        window.close()
        state['close_event_ms']=(time.perf_counter()-before)*1000
    closer.timeout.connect(check_done)
    closer.start()
    app.exec()
    heartbeat.stop()
    closer.stop()
    gaps=[(b-a)*1000 for a,b in zip(heartbeats,heartbeats[1:])]
    result={'platform':platform.platform(),'python':platform.python_version(),'qt_platform':app.platformName(),
        'pyside6':PySide6.__version__,'process_cpu_percent_one_core':100*(time.process_time()-cpu_start)/(time.perf_counter()-wall_start),
        'renderer':args.renderer,'instruments':20,'target_events_per_second':args.events_per_second,
        'events':state['events'],'producer_seconds':state['producer_seconds'],
        'actual_events_per_second':state['events']/state['producer_seconds'],'publication_hz':10,
        'render_samples':len(frames),'render_median_ms':statistics.median(frames),
        'render_p95_ms':percentile(frames,.95),'render_max_ms':max(frames),
        'snapshot_to_render_p95_ms':percentile(latencies,.95),'heartbeat_target_ms':10,
        'heartbeat_p95_ms':percentile(gaps,.95),'heartbeat_max_ms':max(gaps),
        'close_event_ms':state['close_event_ms'],'worker_stopped':not window.worker.is_alive(),
        'loop_closed':window.loop.is_closed(),'microbenchmark':micro,
        'limits':'Synthetic callbacks/Qt only; excludes exchange parsing, SQL persistence, network and microstructure algorithms.'}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))
    shiboken6.delete(window)
    shiboken6.delete(app)

if __name__=='__main__':
    main()
