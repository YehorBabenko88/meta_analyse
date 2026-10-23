"""Fresh synthetic transaction faults and namespace-change models; no host calls."""
import json
from pathlib import Path
import sys
import os
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'commissioning'))
import host_identity as h
sys.path.insert(0,str(Path(h.__file__).resolve().parents[1]/'tests'))
from test_diagnostic_hardening import raw_facts

def setup_main(monkeypatch,tmp_path):
    public=tmp_path/'public.json';private=tmp_path/'private.dpapi'
    monkeypatch.setattr(h,'is_elevated',lambda:True)
    monkeypatch.setattr(h,'collector_identity',lambda *a,**k:dict(candidate_sha='a'*40,version='synthetic'))
    monkeypatch.setattr(h,'collect_facts',raw_facts)
    monkeypatch.setattr(h,'dpapi',lambda *a,**k:b'SYNTHETIC_ENCRYPTED')
    monkeypatch.setattr(sys,'argv',['synthetic','diagnose','--expected-sha','a'*40,
        '--output',str(public),'--private-observation',str(private)])
    return public,private

def test_public_alias_changed_after_check_never_truncates_existing_private(monkeypatch,tmp_path):
    public,private=setup_main(monkeypatch,tmp_path)
    private.write_bytes(b'SYNTHETIC_EXISTING')
    def changed():
        if public.exists():public.unlink()
        public.hardlink_to(private)
        return raw_facts()
    monkeypatch.setattr(h,'collect_facts',changed)
    assert h.main()==1
    assert private.read_bytes()==b'SYNTHETIC_EXISTING'

def test_private_failure_and_unwritable_public_never_leaves_pass(monkeypatch,tmp_path):
    public,private=setup_main(monkeypatch,tmp_path)
    write=Path.write_text;calls=[]
    def public_write(path,*a,**k):
        calls.append(True)
        if len(calls)>1:raise OSError('SYNTHETIC_WRITE_REFUSED')
        return write(path,*a,**k)
    monkeypatch.setattr(Path,'write_text',public_write)
    monkeypatch.setattr(h,'save_private',lambda *a,**k:(_ for _ in ()).throw(OSError('SYNTHETIC_PRIVATE_FAILURE')))
    assert h.main()==1
    assert not public.exists() or 'PASS_OBSERVATION_ONLY' not in public.read_text()

def test_cleanup_never_unlinks_a_rebound_private_path(monkeypatch,tmp_path):
    target=tmp_path/'record';backing=tmp_path/'owned-open-inode'
    monkeypatch.setattr(h,'dpapi',lambda *a,**k:b'SYNTHETIC_ENCRYPTED')
    original=Path.open
    class Rebound:
        def __init__(self):self.stream=original(backing,'x+b')
        def __enter__(self):return self
        def __exit__(self,*a):self.stream.close()
        def __getattr__(self,name):return getattr(self.stream,name)
        def write(self,payload):
            # Model namespace now naming a different existing inode, while this
            # writer still owns its original open handle.
            with original(target,'wb') as other:other.write(b'SYNTHETIC_EXISTING')
            raise OSError('SYNTHETIC_WRITE_FAILED_AFTER_REBIND')
    monkeypatch.setattr(Path,'open',lambda path,*a,**k:Rebound() if path==target and a and a[0] in ('xb','x+b') else original(path,*a,**k))
    with pytest.raises(OSError):h.save_private(target,{'synthetic':True})
    assert target.exists() and target.read_bytes()==b'SYNTHETIC_EXISTING'

def test_crash_before_private_write_leaves_no_public_pass(monkeypatch,tmp_path):
    public,private=setup_main(monkeypatch,tmp_path)
    monkeypatch.setattr(h,'save_private',lambda *a,**k:(_ for _ in ()).throw(KeyboardInterrupt()))
    with pytest.raises(KeyboardInterrupt):h.main()
    assert not public.exists() or 'PASS_OBSERVATION_ONLY' not in public.read_text()

@pytest.mark.parametrize('kind',['relative','symlink','hardlink'])
def test_existing_private_survives_static_alias_spellings(monkeypatch,tmp_path,kind):
    public,private=setup_main(monkeypatch,tmp_path);private.write_bytes(b'SYNTHETIC_EXISTING')
    if kind=='relative':
        (tmp_path/'sub').mkdir();public=tmp_path/'sub'/'..'/private.name
    elif kind=='symlink':
        try:public.symlink_to(private)
        except OSError as exc:
            if sys.platform=='win32' and getattr(exc,'winerror',None)==1314:
                pytest.skip('BLOCKED: file-symlink fixture requires unavailable privilege; no settings changed')
            raise
    else:public.hardlink_to(private)
    monkeypatch.setattr(sys,'argv',['synthetic','diagnose','--expected-sha','a'*40,'--output',str(public),'--private-observation',str(private)])
    assert h.main()==1
    assert private.read_bytes()==b'SYNTHETIC_EXISTING'

def test_parent_reparse_changed_after_check_preserves_existing_inode(monkeypatch,tmp_path):
    public,private=setup_main(monkeypatch,tmp_path)
    first=tmp_path/'first';second=tmp_path/'second';link=tmp_path/'reparse'
    first.mkdir();second.mkdir();private=second/'record';private.write_bytes(b'SYNTHETIC_EXISTING')
    def create(destination):
        if sys.platform=='win32':
            import _winapi
            _winapi.CreateJunction(str(destination),str(link))
        else:link.symlink_to(destination,target_is_directory=True)
    def remove():
        if sys.platform=='win32':os.rmdir(link)
        else:link.unlink()
    create(first);public=link/'record'
    monkeypatch.setattr(sys,'argv',['synthetic','diagnose','--expected-sha','a'*40,'--output',str(public),'--private-observation',str(private)])
    changed_paths=[];sharing_fence=[]
    def changed():
        try:remove()
        except PermissionError:
            sharing_fence.append(True);raise
        create(second);changed_paths.append(True)
        return raw_facts()
    monkeypatch.setattr(h,'collect_facts',changed)
    try:
        assert h.main()==1
        # Windows may refuse exclusive creation through a reparse ancestor
        # before collection starts; that is protection, not a completed swap.
        assert changed_paths==[True] or (sys.platform=='win32' and (sharing_fence==[True] or not (first/'record').exists()))
        assert private.read_bytes()==b'SYNTHETIC_EXISTING'
    finally:remove()

def test_junction_change_between_precheck_and_exclusive_create(monkeypatch,tmp_path):
    public,private=setup_main(monkeypatch,tmp_path)
    first=tmp_path/'first';second=tmp_path/'second';link=tmp_path/'reparse'
    first.mkdir();second.mkdir();private=second/'record';private.write_bytes(b'SYNTHETIC_EXISTING')
    def create(target):
        if sys.platform=='win32':
            import _winapi
            _winapi.CreateJunction(str(target),str(link))
        else:link.symlink_to(target,target_is_directory=True)
    def remove():
        if sys.platform=='win32':os.rmdir(link)
        else:link.unlink()
    create(first);public=link/'record';changed=[];init=h.NewOutput.__init__
    def opened(owned,path):
        if Path(path)==public:
            remove();create(second);changed.append(True)
        init(owned,path)
    monkeypatch.setattr(h.NewOutput,'__init__',opened)
    monkeypatch.setattr(sys,'argv',['synthetic','diagnose','--expected-sha','a'*40,'--output',str(public),'--private-observation',str(private)])
    try:
        assert h.main()==1 and changed==[True]
        assert private.read_bytes()==b'SYNTHETIC_EXISTING'
    finally:remove()

@pytest.mark.parametrize('point',['public-write','private-write','public-close','private-close','stdout'])
def test_handled_fault_never_leaves_committed_private_or_public_pass(monkeypatch,tmp_path,point):
    public,private=setup_main(monkeypatch,tmp_path)
    write=h.NewOutput.write;close=h.NewOutput.close;fired=[]
    def is_private(owned):return Path(owned.stream.name)==private
    def fail_write(owned,payload):
        write(owned,payload)
        if not fired and point==('private-write' if is_private(owned) else 'public-write'):
            fired.append(True);raise OSError('SYNTHETIC_WRITE_FAULT')
    def fail_close(owned):
        if not fired and point==('private-close' if is_private(owned) else 'public-close'):
            fired.append(True);raise OSError('SYNTHETIC_CLOSE_FAULT')
        return close(owned)
    monkeypatch.setattr(h.NewOutput,'write',fail_write);monkeypatch.setattr(h.NewOutput,'close',fail_close)
    if point=='stdout':
        def output(*a,**k):
            if not fired:fired.append(True);raise BrokenPipeError('SYNTHETIC')
        monkeypatch.setattr('builtins.print',output)
    assert h.main()==1 and fired
    assert not private.exists() or private.read_bytes()==b''
    assert not public.exists() or b'PASS_OBSERVATION_ONLY' not in public.read_bytes()

def test_success_writes_complete_private_and_only_nonadmitting_public(monkeypatch,tmp_path):
    public,private=setup_main(monkeypatch,tmp_path)
    assert h.main()==0
    assert private.read_bytes()
    assert json.loads(public.read_text())['diagnostic_status']=='OBSERVATION_ONLY_NOT_AUTHORIZATION'

def test_after_close_error_reports_cleanup_limit_without_public_pass(monkeypatch,tmp_path,capsys):
    public,private=setup_main(monkeypatch,tmp_path);close=h.NewOutput.close;fired=[]
    def after_close(owned):
        close(owned)
        if Path(owned.stream.name)==private and not fired:
            fired.append(True);raise OSError('SYNTHETIC_ERROR_AFTER_FD_CLOSE')
    monkeypatch.setattr(h.NewOutput,'close',after_close)
    assert h.main()==1 and fired
    assert private.read_bytes()  # closed handle cannot promise residue erasure
    lines=capsys.readouterr().out.splitlines()
    assert json.loads(lines[-1])['reason_codes']==['PRIVATE_CLEANUP_FAILED']
    assert b'PASS_OBSERVATION_ONLY' not in public.read_bytes()

@pytest.mark.parametrize('point',['public-create','public-write','private-create','private-write','private-close'])
def test_abrupt_synthetic_process_exit_never_publishes_pass(tmp_path,point):
    import subprocess
    root=Path(h.__file__).resolve().parents[1]
    public=tmp_path/'public';private=tmp_path/'private'
    script="""
import sys,os
from pathlib import Path
sys.path[:0]=[REPO+'/commissioning',REPO+'/tests']
import host_identity as h
from test_diagnostic_hardening import raw_facts
h.is_elevated=lambda:True
h.collector_identity=lambda *a,**k:dict(candidate_sha='a'*40,version='synthetic')
h.collect_facts=raw_facts
h.dpapi=lambda *a,**k:b'SYNTHETIC_CIPHERTEXT'
init=h.NewOutput.__init__;write=h.NewOutput.write;close=h.NewOutput.close
def hit(owned,stage):
    kind='private' if Path(owned.stream.name)==Path(PRIVATE) else 'public'
    if kind+'-'+stage==POINT:os._exit(91)
def created(owned,path):init(owned,path);hit(owned,'create')
def written(owned,payload):write(owned,payload);hit(owned,'write')
def closed(owned):
    hit(owned,'close');close(owned)
h.NewOutput.__init__=created;h.NewOutput.write=written;h.NewOutput.close=closed
sys.argv=['synthetic','diagnose','--expected-sha','a'*40,'--output',PUBLIC,'--private-observation',PRIVATE]
raise SystemExit(h.main())
"""
    prefix='REPO='+repr(str(root))+'\nPUBLIC='+repr(str(public))+'\nPRIVATE='+repr(str(private))+'\nPOINT='+repr(point)+'\n'
    result=subprocess.run([sys.executable,'-c',prefix+script],capture_output=True,timeout=20)
    assert result.returncode==91
    assert not public.exists() or b'PASS_OBSERVATION_ONLY' not in public.read_bytes()
    # This explicitly observes residue; it is not a durability/no-residue claim.
    if point in ('public-create','public-write'):assert not private.exists()
    elif point=='private-create':assert private.read_bytes()==b''
    else:assert private.read_bytes()  # complete encrypted observation may remain

def test_property_relative_alias_spellings_are_never_overwritten(monkeypatch,tmp_path):
    from hypothesis import given,settings,strategies as st
    @settings(max_examples=24,derandomize=True,database=None,deadline=None)
    @given(depth=st.integers(min_value=1,max_value=8))
    def check(depth):
        directory=tmp_path/str(depth);directory.mkdir(exist_ok=True)
        private=directory/'record';private.write_bytes(b'SYNTHETIC_EXISTING')
        sub=directory/'sub';sub.mkdir(exist_ok=True)
        path=sub
        for _ in range(depth):path=path/'..'/'sub'
        path=path/'..'/'record'
        with pytest.raises(FileExistsError):h.save_private(path,{'synthetic':True})
        assert private.read_bytes()==b'SYNTHETIC_EXISTING'
    monkeypatch.setattr(h,'dpapi',lambda *a,**k:b'SYNTHETIC')
    check()

@pytest.mark.parametrize('field,value', [('pid',0x80000000),('pid',0xffffffff),('pid',True),('pid',123.0),('pid',None),('pid',[]),('pid',-1),('pid',{}),
    ('created',None),('created',False),('created',float('nan')),('created',-1),('created',[]),('created','123')])
def test_fresh_uint32_filetime_edges_reject_without_admission(field,value):
    import process_identity as classifier
    from test_process_identity_acceptance import fixture,ROOTS
    row,e=fixture();row[field]=value
    assert classifier.classify_missing(row,e,ROOTS)['status']=='UNRESOLVED'

@pytest.mark.parametrize('value',[None,[],{},False])
def test_fresh_null_and_collection_outer_records_are_structured_blocked(value):
    import process_identity as classifier
    from test_process_identity_acceptance import ROOTS
    assert classifier.assess_processes([value],ROOTS,[123])['unknown_process_paths']>0

@pytest.mark.parametrize('value',[None,'not-a-date','9999-12-31T23:59:59+00:00',[]])
def test_fresh_datetime_source_edges_bind_filetime(value):
    from evidence_schema import validate_source_snapshot
    from test_evidence_schema_properties import complete_raw,ROOTS
    raw=complete_raw();raw['private_inventory']['processes'][0]['CreationDate']=value
    with pytest.raises((ValueError,TypeError)):
        validate_source_snapshot(raw['private_inventory']['processes'],raw['process_evidence'],ROOTS,ROOTS['system32'])

@pytest.mark.parametrize('text',['NetworkЅervice','NetworkServіce','ＮetworkService','NetworkService\u200b'])
def test_fresh_confusable_service_arguments_are_not_contracts(text):
    import process_identity as classifier
    from test_process_identity_acceptance import fixture,ROOTS
    row,e=fixture()
    for suffix in ('before','after'):
        e['services_'+suffix][0]['binary_path']=e['services_'+suffix][0]['binary_path'].replace('NetworkService',text)
        for field in ('image_path','expanded_image_path'):e['implementation_'+suffix]['DoSvc'][field]=e['implementation_'+suffix]['DoSvc'][field].replace('NetworkService',text)
    assert classifier.classify_missing(row,e,ROOTS)['status']=='UNRESOLVED'

@pytest.mark.parametrize('shape',['duplicate','forged-root','nested-error','wrong-counter'])
def test_fresh_junit_forged_duplicate_and_nested_inputs_reject(tmp_path,shape):
    import importlib.util
    spec=importlib.util.spec_from_file_location('fresh_projection',Path(h.__file__).resolve().parents[1]/'scripts/project_synthetic_artifacts.py')
    projection=importlib.util.module_from_spec(spec);spec.loader.exec_module(projection)
    case='<testcase classname="tests.test_process_identity_acceptance" name="test_acceptance_complete_service_controls"/>'
    if shape=='duplicate':case+=case
    elif shape=='forged-root':case=case.replace('test_acceptance_complete_service_controls','test_uncollected_forged_identity')
    elif shape=='nested-error':case+='<system-out><error/></system-out>'
    path=tmp_path/'raw.xml';path.write_text('<testsuites><testsuite'+(' tests="2"' if shape=='wrong-counter' else '')+'>'+case+'</testsuite></testsuites>')
    with pytest.raises(ValueError):projection.project_junit(path)
