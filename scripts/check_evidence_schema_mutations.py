"""Independent mutations of schema, raw binding, public and persistence gates."""
import argparse
import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import types

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'commissioning'),str(ROOT/'tests')]
from test_process_identity_acceptance import fixture,ROOTS
from test_evidence_schema_properties import complete_raw
from test_diagnostic_hardening import raw_facts

MUTATIONS=[
 ('raw-image-expansion','schema',"need(p.command_executable(raw_image)==p.command_executable(config['expanded_image_path']) and\n                 p.command_arguments(raw_image)==p.command_arguments(config['expanded_image_path']))",'pass'),
 ('scm-diagnostic-reason','schema',"need(evidence.get(reason)=='COMPLETE_REGISTRY_SCM_COVERAGE')",'pass'),
 ('diagnostic-numeric-type','schema',"integer(native['native_format_win32_error'],DWORD_MAX)",'pass'),
 ('full-native-snapshot','schema',"need(evidence['native_before']==evidence['native_after'])",'pass'),
 ('source-row-binding','schema',"need(process['name']==source['Name'] and process['parent_pid']==source['ParentProcessId'] and\n             process['session_id']==source['SessionId'] and process['created']==source['CreationFileTime'] and\n             process.get('cim_path')==source['ExecutablePath'])",'pass'),
 ('source-time-binding','schema',"need(ticks//10==item['CreationFileTime']//10)",'pass'),
 ('public-counter-type','schema',"if key in grid:integer(grid[key])",'if key in grid:pass'),
 ('failed-observation-persistence','host',"            if reasons:\n                raise DiagnosticError(reasons[0])",'            if reasons:pass'),
]


def load(source,name):
    m=types.ModuleType(name);m.__file__=str(ROOT/'commissioning'/(name+'.py'))
    exec(compile(source,'<synthetic-schema-mutation>','exec'),m.__dict__);return m


def probe(module,tag):
    try:
        if tag in ('raw-image-expansion','scm-diagnostic-reason','diagnostic-numeric-type','full-native-snapshot'):
            row,e=fixture()
            if tag=='raw-image-expansion':
                for key in ('implementation_before','implementation_after'):e[key]['DoSvc']['image_path']=r'C:\Other\wrong.exe'
            if tag=='scm-diagnostic-reason':
                for suffix in ('before','after'):
                    e['services_'+suffix+'_reason']='SERVICE_STATUS_UNAVAILABLE'
                    e['services_'+suffix+'_diagnostics']=dict(stage='',win32_error=0,failed_service='')
            if tag=='diagnostic-numeric-type':
                for key in ('native_before','native_after'):
                    e[key].update(native_format_path='',native_format_query_succeeded=False,native_format_win32_error=False)
            if tag=='full-native-snapshot':e['native_after']['path']=e['native_after']['path'].upper()
            module.validate_success(row,e,ROOTS)
        elif tag in ('source-row-binding','source-time-binding'):
            raw=complete_raw();original=raw['private_inventory']['processes']
            if tag=='source-row-binding':original[0]['Name']='grid.exe'
            else:original[0]['CreationDate']='2026-01-01T00:00:00Z'
            module.validate_source_snapshot(original,raw['process_evidence'],raw['process_roots'],ROOTS['system32'])
        elif tag=='public-counter-type':
            facts=raw_facts();facts['grid']['visible_tasks']='SYNTHETIC_RAW_VALUE';module.validate_public(facts)
        else:
            facts=raw_facts();facts['grid']['coverage_complete']=False;persisted=[]
            module.is_elevated=lambda:True
            module.collector_identity=lambda *a,**k:dict(candidate_sha='a'*40,version='synthetic')
            module.collect_facts=lambda:facts;module.save_private=lambda *a,**k:persisted.append(True)
            class Output:
                def write_text(self,*a,**k):pass
            module.Path=lambda *a:Output()
            argv=sys.argv
            try:
                sys.argv=['synthetic','diagnose','--expected-sha','a'*40,'--output','none','--private-observation','none']
                with contextlib.redirect_stdout(io.StringIO()):code=module.main()
            finally:sys.argv=argv
            return code==1 and not persisted
    except (ValueError,KeyError,TypeError,AttributeError):return True
    return False


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    sources={'schema':(ROOT/'commissioning/evidence_schema.py').read_text(encoding='utf-8-sig'),
             'host':(ROOT/'commissioning/host_identity.py').read_text(encoding='utf-8-sig')}
    results=[]
    for tag,kind,old,new in MUTATIONS:
        baseline=load(sources[kind],kind);assert probe(baseline,tag),tag
        if kind=='schema':
            r,e=fixture();baseline.validate_success(r,e,ROOTS)
        assert sources[kind].count(old)==1,tag
        mutant=load(sources[kind].replace(old,new),kind)
        if kind=='schema':
            r,e=fixture();mutant.validate_success(r,e,ROOTS)
        results.append(dict(predicate=tag,result='KILLED' if not probe(mutant,tag) else 'SURVIVED'))
    report=dict(mutations=results,killed=sum(r['result']=='KILLED' for r in results),survived=sum(r['result']=='SURVIVED' for r in results))
    args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(f"Schema/cross-stage/public mutations killed={report['killed']} survived={report['survived']}")
    if report['survived']:raise SystemExit(1)


if __name__=='__main__':main()
