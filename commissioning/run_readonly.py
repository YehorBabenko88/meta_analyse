"""Manually approved read-only Qt session. Every non-read HTTP method is denied."""
import argparse, json, os, sys, time
from pathlib import Path
from datetime import datetime, timezone
from preflight import inspect


def install_http_read_guard():
    from meta_analyse.http_client import ManagedAsyncClient
    original_send=ManagedAsyncClient.send
    async def guarded_send(self,request,**kwargs):
        if request.method not in ('GET','HEAD','OPTIONS'):raise PermissionError('commissioning forbids HTTP writes')
        return await original_send(self,request,**kwargs)
    ManagedAsyncClient.send=guarded_send


def bind_terminal_endpoint(verified,executable):
    import asyncio
    from host_identity import collect_facts,validate_metascalp
    from meta_analyse.ports import MetaScalp
    original=MetaScalp.request
    async def discover(self):
        try:
            current=validate_metascalp(await asyncio.to_thread(collect_facts),executable)
        except ValueError as exc:
            raise ConnectionError('approved MetaScalp process/API identity unavailable') from exc
        if current['sha256']!=verified['metascalp_exe_sha256'] or current['port']!=verified['metascalp_api_port'] or current['pid']!=verified['metascalp_pid'] or current['process_started']!=verified['metascalp_process_started']:
            raise ConnectionError('approved MetaScalp process/API identity changed')
        self.base=f"http://127.0.0.1:{current['port']}"
        return self.base
    async def request(self,method,endpoint,**kwargs):
        await discover(self)
        return await original(self,method,endpoint,**kwargs)
    MetaScalp.discover=discover
    MetaScalp.request=request


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('manifest','manifest-sha256','expected-sha','expected-computer','enrollment','metascalp-exe','log-dir'):p.add_argument('--'+name,required=True)
    p.add_argument('--cluster-system-identifier',required=True)
    p.add_argument('--operator-approved-readonly-run',action='store_true',required=True)
    a=p.parse_args()
    # Never accept stale/tampered PASS JSON: rerun all read-only checks now.
    import asyncio
    verified=asyncio.run(inspect(a))
    dsn=os.environ['META_ANALYSE_COMMISSIONING_DSN']
    from psycopg.conninfo import make_conninfo
    from host_identity import load_private,validate_bound_database
    bound_config=validate_bound_database(dsn,load_private(a.enrollment),os.environ)
    from meta_analyse.pg_cluster_attestation import ExpectedCluster
    expected_cluster=ExpectedCluster(a.cluster_system_identifier,bound_config['dbname'],bound_config['user'])
    os.environ['META_ANALYSE_DSN']=make_conninfo(**bound_config)
    install_http_read_guard()
    bind_terminal_endpoint(verified,a.metascalp_exe)
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QTimer
    from meta_analyse.desktop import Window
    from meta_analyse.trader_theme import TRADER_QSS
    import logging
    out=Path(a.log_dir);out.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(filename=out/'application.log',level=logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s %(message)s')
    app=QApplication(sys.argv[:1]);app.setStyleSheet(TRADER_QSS);window=Window(expected_cluster=expected_cluster);window.show()
    last=time.monotonic();samples=[]
    def heartbeat():
        nonlocal last
        now=time.monotonic();samples.append((now-last)*1000);last=now
    def record():
        values=sorted(samples);snapshot=window._snapshot
        item=dict(utc=datetime.now(timezone.utc).isoformat(),monotonic=time.monotonic(),candidate_sha=a.expected_sha,
            flow_state=snapshot.flow_state,flow_status=snapshot.flow_status,
            ui_heartbeat_p95_ms=values[min(len(values)-1,int(.95*len(values)))] if values else None,
            persisted_events=snapshot.market_events,reported_gaps=snapshot.market_gaps,persisted_ages=snapshot.market_ages,
            queue_depth=None,dropped_events=None,reconciliation='UNVERIFIED')
        with (out/'ui-runtime.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(item)+'\n')
        samples.clear()
    pulse=QTimer(window);pulse.timeout.connect(heartbeat);pulse.start(100)
    timer=QTimer(window);timer.timeout.connect(record);timer.start(5000)
    app.aboutToQuit.connect(record)
    # This authorization covers smoke only. Normal close still drains writes;
    # never force-exit the worker or silently promote to a longer stage.
    QTimer.singleShot(30*60*1000,window.close)
    with (out/'session.json').open('w',encoding='utf-8') as f:
        json.dump(dict(candidate_sha=a.expected_sha,computer=verified['computer'],host_fingerprint=verified['host_fingerprint'],enrollment_id=verified['enrollment_id'],pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),mode='HTTP_READ_ONLY'),f,indent=2)
    raise SystemExit(app.exec())

if __name__=='__main__':
    try: main()
    except Exception as exc:
        print('Commissioning blocked ('+type(exc).__name__+'); no private configuration published')
        raise SystemExit(1)
