"""Strict bounded benchmark projection with existing exact Actions provenance."""
import argparse
import hashlib
import math
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import project_public_ci_evidence as public

REASONS = {'NONE', 'NO_RENDER_SAMPLES', 'NO_SNAPSHOT_LATENCY_SAMPLES',
           'NO_HEARTBEAT_SAMPLES', 'INVALID_MEASUREMENT', 'PRODUCER_FAILED',
           'PRODUCER_INCOMPLETE', 'BENCHMARK_TIMEOUT', 'ASYNC_OR_UI_ERROR',
           'SHUTDOWN_INCOMPLETE', 'INCOMPLETE_TABLE'}
COUNTERS = {'published','published_twenty_rows','received','repaints',
            'twenty_row_repaints','bridge_rows','async_errors','ui_errors',
            'thread_violations','stamp_overflow'}
SAMPLES = {'render_median_ms','render_p95_ms','render_max_ms','render_fps',
           'snapshot_to_render_p95_ms','heartbeat_p95_ms','heartbeat_max_ms'}
NUMBERS = {'process_cpu_percent_one_core','producer_seconds','measurement_seconds'}
INTEGERS = {'events','render_samples','python_heap_peak_bytes','target_events_per_second'}
FIXED = dict(schema_version=1,instruments=20,publication_hz=10,heartbeat_target_ms=10,
             limits='Synthetic callbacks/Qt only; excludes exchange parsing, SQL persistence, network and microstructure algorithms.')


def checked(data):
    value = public.decode(data)
    need = public.need
    if type(value) is dict and value.get('reason') in ('BENCHMARK_TIMEOUT','BENCHMARK_INTERNAL_ERROR') and 'metrics_status' in value:
        need(set(value)=={'schema_version','status','reason','metrics_status','diagnostics_status','supervisor_timeout_seconds'})
        need(type(value['schema_version']) is int and value['schema_version']==1)
        need(value['status']=='FAIL_CLOSED' and value['metrics_status']=='UNAVAILABLE' and value['diagnostics_status']=='UNAVAILABLE')
        need(type(value['supervisor_timeout_seconds']) in (int,float) and math.isfinite(value['supervisor_timeout_seconds']) and 15 < value['supervisor_timeout_seconds'] <= 75)
        return public.json_bytes(value)
    need(type(value) is dict and set(value) == set(FIXED)|SAMPLES|NUMBERS|INTEGERS|
         {'status','reason','platform','python','qt_platform','pyside6','renderer',
          'actual_events_per_second','diagnostics','close_event_ms','worker_stopped',
          'loop_closed','microbenchmark'})
    for key, expected in FIXED.items():
        need(type(value[key]) is type(expected) and value[key] == expected)
    need(type(value['reason']) is str and value['reason'] in REASONS)
    need(value['status'] == ('PASS' if value['reason']=='NONE' else 'FAIL_CLOSED'))
    need(value['platform'] in ('Windows','Linux','Darwin'))
    need(value['qt_platform'] in ('offscreen','windows'))
    need(value['renderer'] in ('partial','full'))
    for key in ('python','pyside6'):
        need(type(value[key]) is str and re.fullmatch(r'[0-9]{1,2}(\.[0-9]{1,3}){1,3}',value[key]) is not None)
    def numeric(number):
        return type(number) in (int,float) and math.isfinite(number) and 0 <= number <= 1e12
    for key in NUMBERS: need(numeric(value[key]))
    for key in INTEGERS: need(type(value[key]) is int and 0 <= value[key] <= 10**10)
    for key in SAMPLES|{'actual_events_per_second','close_event_ms'}:
        need(value[key] is None or numeric(value[key]))
    for key in ('worker_stopped','loop_closed'): need(type(value[key]) is bool)
    counters=value['diagnostics']
    need(type(counters) is dict and set(counters)==COUNTERS)
    need(all(type(n) is int and 0 <= n <= 10000000 for n in counters.values()))
    need(counters['bridge_rows'] <= 20)
    micro=value['microbenchmark']
    need(type(micro) is dict and set(micro)=={'unchanged','one_changed','all_changed'})
    for row in micro.values():
        need(type(row) is dict and set(row)=={'median_ms','p95_ms'})
        need(all(numeric(n) for n in row.values()))
    if value['render_samples']==0:
        need(all(value[k] is None for k in ('render_median_ms','render_p95_ms','render_max_ms','render_fps')))
        need(value['status']=='FAIL_CLOSED')
    if value['status']=='PASS':
        need(value['render_samples']>0 and all(value[k] is not None for k in SAMPLES))
        need(value['events']>0 and value['producer_seconds']>0 and value['measurement_seconds']>0)
        need(value['actual_events_per_second'] is not None and value['actual_events_per_second']>0)
        need(value['worker_stopped'] and value['loop_closed'] and value['close_event_ms'] is not None)
        need(all(counters[k]>0 for k in ('published_twenty_rows','received','twenty_row_repaints')))
        need(counters['bridge_rows']==20)
        need(all(counters[k]==0 for k in ('async_errors','ui_errors','thread_violations','stamp_overflow')))
    return public.json_bytes(value)


def publish(output, source, benchmark, expected_outcome=None):
    output=public.safe_path(output)
    public.need(not output.exists() and output.parent.is_dir())
    source=public.decode(public.read(source))
    receipt=public.provenance(source)
    raw=public.read(benchmark)
    data=checked(raw)
    if expected_outcome is not None:
        public.need(expected_outcome in ('success','failure'))
        public.need((public.decode(data)['status']=='PASS')==(expected_outcome=='success'))
    stage=Path(tempfile.mkdtemp(prefix='.benchmark-',dir=output.parent))
    try:
        files={'ui-benchmark.json':data,'source-sha.json':public.json_bytes(source)}
        manifest=dict(schema_version=1,provenance=receipt,input_sha256=hashlib.sha256(raw).hexdigest(),
                      files={k:hashlib.sha256(v).hexdigest() for k,v in files.items()})
        for name,content in files.items(): (stage/name).write_bytes(content)
        (stage/'manifest.json').write_bytes(public.json_bytes(manifest))
        validate(stage)
        public.safe_path(output)
        public.need(not output.exists())
        os.rename(stage,output)
    finally:
        if stage.exists(): shutil.rmtree(stage)


def validate(directory):
    directory=public.safe_path(directory)
    need=public.need
    need({p.name for p in directory.iterdir()}=={'manifest.json','source-sha.json','ui-benchmark.json'})
    manifest=public.decode(public.read(directory/'manifest.json'))
    need(type(manifest) is dict and set(manifest)=={'schema_version','provenance','input_sha256','files'})
    need(type(manifest['schema_version']) is int and manifest['schema_version']==1)
    need(type(manifest['input_sha256']) is str and re.fullmatch('[0-9a-f]{64}',manifest['input_sha256']) is not None)
    source=public.decode(public.read(directory/'source-sha.json'))
    public.source_check(source)
    need(manifest['provenance']==public.provenance(source))
    files=manifest['files']
    need(type(files) is dict and set(files)=={'source-sha.json','ui-benchmark.json'})
    for name,digest in files.items():
        data=public.read(directory/name)
        need(hashlib.sha256(data).hexdigest()==digest)
        if name=='ui-benchmark.json': need(checked(data)==data)
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    parser.add_argument('--source',required=True)
    parser.add_argument('--benchmark',required=True)
    parser.add_argument('--expected-outcome',choices=['success','failure'],required=True)
    args=parser.parse_args()
    try:
        publish(args.output,args.source,args.benchmark,args.expected_outcome)
    except Exception:
        print('BLOCKED: UI_BENCHMARK_EVIDENCE_REJECTED',file=sys.stderr)
        return 1
    return 0


if __name__=='__main__': raise SystemExit(main())
