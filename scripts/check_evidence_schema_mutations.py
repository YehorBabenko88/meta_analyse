"""Independent mutations of schema, raw binding, public and persistence gates."""
import argparse
import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import types
import tempfile
import os

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
 ('raw-ascii-before-casefold','schema',"need(p.command_argument_text(config['expanded_image_path']).isascii())\n            need(p.command_argument_text(service['binary_path']).isascii())\n            need(p.command_argument_text(raw_image).isascii())",'pass'),
 ('public-private-collision','host',"if output.resolve() == private.resolve() or (output.exists() and private.exists() and output.samefile(private)):", 'if False:'),
 ('junit-counter-preservation','projection',"cases=validate_raw_structure(tree.getroot())", "cases=list(tree.getroot().iter('testcase'))"),
 ('exclusive-new-output','host',"Path(filename).open('x+b')","Path(filename).open('w+b')"),
 ('public-handle-binding','host',"public_output.write(json.dumps(report, indent=2, allow_nan=False).encode('utf-8'))","Path(args.output).write_bytes(json.dumps(report, indent=2, allow_nan=False).encode('utf-8'))"),
 ('private-handle-erasure','host',"self.stream.truncate(0)",'pass'),
 ('public-nonadmission','host',"report.update(diagnostic_status='OBSERVATION_ONLY_NOT_AUTHORIZATION',reason_codes=[])","report.update(diagnostic_status='PASS_OBSERVATION_ONLY',reason_codes=[])"),
]


def load(source,name):
    m=types.ModuleType(name);m.__file__=str(ROOT/'commissioning'/(name+'.py'))
    exec(compile(source,'<synthetic-schema-mutation>','exec'),m.__dict__);return m


def probe(module,tag):
    try:
        if tag in ('exclusive-new-output','public-handle-binding','private-handle-erasure','public-nonadmission'):
            return transaction_probe(module,tag)
        if tag=='raw-ascii-before-casefold':
            row,e=fixture()
            for suffix in ('before','after'):
                e['services_'+suffix][0]['binary_path']=e['services_'+suffix][0]['binary_path'].replace('NetworkService','Networkſervice')
                for key in ('image_path','expanded_image_path'):e['implementation_'+suffix]['DoSvc'][key]=e['implementation_'+suffix]['DoSvc'][key].replace('NetworkService','Networkſervice')
            module.validate_success(row,e,ROOTS)
            return False
        if tag=='junit-counter-preservation':
            with tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp)/'synthetic.xml'
                path.write_text('<testsuites><testsuite tests="1" errors="1"><testcase classname="tests.test_process_identity_acceptance" name="test_acceptance_complete_service_controls"/></testsuite></testsuites>')
                module.project_junit(path)
            return False
        if tag=='public-private-collision':
            module.is_elevated=lambda:True;module.collect_facts=raw_facts
            module.collector_identity=lambda *a,**k:dict(candidate_sha='a'*40,version='synthetic')
            def collision(*a,**k):raise FileExistsError('SYNTHETIC')
            module.save_private=collision
            with tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp)/'synthetic';path.write_bytes(b'SYNTHETIC_EXISTING')
                argv=sys.argv
                try:
                    sys.argv=['synthetic','diagnose','--expected-sha','a'*40,'--output',str(path),'--private-observation',str(path)]
                    with contextlib.redirect_stdout(io.StringIO()):code=module.main()
                finally:sys.argv=argv
                return code==1 and path.read_bytes()==b'SYNTHETIC_EXISTING'
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
            with tempfile.TemporaryDirectory() as tmp:
                argv=sys.argv
                try:
                    sys.argv=['synthetic','diagnose','--expected-sha','a'*40,'--output',str(Path(tmp)/'public'),'--private-observation',str(Path(tmp)/'private')]
                    with contextlib.redirect_stdout(io.StringIO()):code=module.main()
                finally:sys.argv=argv
            return code==1 and not persisted
    except (ValueError,KeyError,TypeError,AttributeError):return True
    return False


def transaction_probe(module,tag='positive',release_for_witness=False):
    module.is_elevated=lambda:True;module.collect_facts=raw_facts
    module.collector_identity=lambda *a,**k:dict(candidate_sha='a'*40,version='synthetic')
    module.dpapi=lambda *a,**k:b'SYNTHETIC_CIPHERTEXT'
    with tempfile.TemporaryDirectory() as tmp:
        public=Path(tmp)/'public';private=Path(tmp)/'private';observed=[]
        if tag=='exclusive-new-output':public.write_bytes(b'SYNTHETIC_EXISTING')
        if tag=='public-handle-binding':
            first=Path(tmp)/'first';second=Path(tmp)/'second';link=Path(tmp)/'reparse'
            first.mkdir();second.mkdir()
            private=second/'record';public=link/'record'
            private.write_bytes(b'SYNTHETIC_EXISTING')
            def create(target):
                if sys.platform=='win32':
                    import _winapi
                    _winapi.CreateJunction(str(target),str(link))
                else:link.symlink_to(target,target_is_directory=True)
            def remove():
                if sys.platform=='win32':os.rmdir(link)
                else:link.unlink()
            create(first);changed_paths=[];sharing_fence=[];handles=[]
            init=module.NewOutput.__init__
            def opened(owned,path):
                init(owned,path)
                if Path(path)==public:handles.append(owned)
            module.NewOutput.__init__=opened
            def changed():
                try:remove()
                except PermissionError:
                    if not release_for_witness:sharing_fence.append(True);raise
                    handles[0].close();remove()
                create(second);changed_paths.append(True)
                return raw_facts()
            module.collect_facts=changed
        if tag=='private-handle-erasure':
            calls=[]
            def output(*a,**k):
                if not calls:calls.append(True);raise BrokenPipeError('SYNTHETIC')
            module.print=output
        if tag=='public-nonadmission':
            original=module.NewOutput.write
            def write(owned,payload):
                observed.append(b'PASS_OBSERVATION_ONLY' in payload)
                return original(owned,payload)
            module.NewOutput.write=write
            def rejected(*a,**k):raise OSError('SYNTHETIC')
            module.save_private=rejected
        argv=sys.argv
        try:
            sys.argv=['synthetic','diagnose','--expected-sha','a'*40,'--output',str(public),'--private-observation',str(private)]
            with contextlib.redirect_stdout(io.StringIO()):code=module.main()
        finally:sys.argv=argv
        if tag=='exclusive-new-output':return code==1 and public.read_bytes()==b'SYNTHETIC_EXISTING'
        if tag=='public-handle-binding':
            preserved=private.read_bytes()==b'SYNTHETIC_EXISTING'
            remove()
            assert changed_paths==[True] or sharing_fence==[True] or (sys.platform=='win32' and not handles)
            return code==1 and preserved
        if tag=='private-handle-erasure':return code==1 and private.read_bytes()==b''
        if tag=='public-nonadmission':return code==1 and not any(observed)
        return code==0 and bool(private.read_bytes())


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    sources={'schema':(ROOT/'commissioning/evidence_schema.py').read_text(encoding='utf-8-sig'),
             'host':(ROOT/'commissioning/host_identity.py').read_text(encoding='utf-8-sig'),
             'projection':(ROOT/'scripts/project_synthetic_artifacts.py').read_text(encoding='utf-8-sig')}
    results=[]
    for tag,kind,old,new in MUTATIONS:
        baseline=load(sources[kind],kind);assert probe(baseline,tag),tag
        if kind=='schema':
            r,e=fixture();baseline.validate_success(r,e,ROOTS)
        assert sources[kind].count(old)==1,tag
        mutant=load(sources[kind].replace(old,new),kind)
        if kind=='schema':
            r,e=fixture();mutant.validate_success(r,e,ROOTS)
        if kind=='host':assert transaction_probe(load(sources[kind],kind)) and transaction_probe(load(sources[kind].replace(old,new),kind)),tag
        result=dict(predicate=tag,result='KILLED' if not probe(mutant,tag) else 'SURVIVED')
        if tag=='public-private-collision' and result['result']=='SURVIVED':
            composite=load(sources[kind].replace(old,new).replace("Path(filename).open('x+b')","Path(filename).open('w+b')"),kind)
            assert not probe(composite,tag)
            result.update(result='DEFENDED_BY_EXCLUSIVE_OUTPUT',composite_witnesses=['PUBLIC_PRIVATE_FILE_IDENTITY'])
        if tag=='public-handle-binding' and result['result']=='SURVIVED' and sys.platform=='win32':
            composite_source=sources[kind].replace(old,new).replace("Path(filename).open('x+b')","Path(filename).resolve().open('x+b')")
            assert not transaction_probe(load(composite_source,kind),tag,release_for_witness=True)
            result.update(result='DEFENDED_BY_EXCLUSIVE_OUTPUT',composite_witnesses=['PUBLIC_PRIVATE_FILE_IDENTITY'])
        results.append(result)
    report=dict(mutations=results,killed=sum(r['result']=='KILLED' for r in results),defended=sum(r['result'].startswith('DEFENDED_') for r in results),survived=sum(r['result']=='SURVIVED' for r in results))
    args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(f"Schema/cross-stage/public mutations killed={report['killed']} defended={report['defended']} survived={report['survived']}")
    if report['survived']:raise SystemExit(1)


if __name__=='__main__':main()
