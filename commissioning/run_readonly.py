"""Manually approved read-only Qt session. Every non-read HTTP method is denied."""
import argparse, json, os, sys, time
from pathlib import Path
from datetime import datetime, timezone
from preflight import target_guard, verify_manifest, validate_local_database, verify_package_source


def install_http_read_guard():
    from meta_analyse.http_client import ManagedAsyncClient
    original_send=ManagedAsyncClient.send
    async def guarded_send(self,request,**kwargs):
        if request.method not in ('GET','HEAD','OPTIONS'):raise PermissionError('commissioning forbids HTTP writes')
        return await original_send(self,request,**kwargs)
    ManagedAsyncClient.send=guarded_send


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('manifest','expected-sha','expected-computer','log-dir'):p.add_argument('--'+name,required=True)
    p.add_argument('--operator-approved-readonly-run',action='store_true',required=True)
    a=p.parse_args();target_guard(a.expected_computer)
    root=verify_manifest(a.manifest,a.expected_sha);verify_package_source(root)
    if any(os.environ.get(k) for k in ('BYBIT_API_KEY','BYBIT_API_SECRET')):raise ValueError('trading credentials must be absent')
    dsn=os.environ['META_ANALYSE_COMMISSIONING_DSN']
    from psycopg.conninfo import make_conninfo
    os.environ['META_ANALYSE_DSN']=make_conninfo(**validate_local_database(dsn))
    install_http_read_guard()
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QTimer
    from meta_analyse.desktop import Window
    from meta_analyse.trader_theme import TRADER_QSS
    import logging
    out=Path(a.log_dir);out.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(filename=out/'application.log',level=logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s %(message)s')
    app=QApplication(sys.argv[:1]);app.setStyleSheet(TRADER_QSS);window=Window();window.show()
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
    with (out/'session.json').open('w',encoding='utf-8') as f:
        json.dump(dict(candidate_sha=a.expected_sha,computer=os.environ.get('COMPUTERNAME'),pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),mode='HTTP_READ_ONLY'),f,indent=2)
    raise SystemExit(app.exec())

if __name__=='__main__':main()
