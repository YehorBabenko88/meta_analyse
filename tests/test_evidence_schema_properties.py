"""Whole-input properties and cross-stage tests on generated synthetic data only."""
import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from hypothesis import given, settings, strategies as st
from test_process_identity_acceptance import fixture, add_topology, CONTRACTS, ROOTS
from test_diagnostic_hardening import raw_facts
import process_identity as p
import host_identity as h

PROP = settings(max_examples=64, derandomize=True, database=None, deadline=None)
INVALID = st.one_of(st.none(), st.booleans(), st.integers(), st.floats(allow_nan=True, allow_infinity=True),
                    st.lists(st.integers(), max_size=3), st.dictionaries(st.text(max_size=5), st.integers(), max_size=2))


def complete_raw():
    row, evidence = fixture()
    add_topology(row, evidence)
    raw = raw_facts()
    raw['process_evidence'] = [dict(process=row, evidence=evidence)]
    raw['private_inventory']['processes'] = [dict(Name=row['name'], ProcessId=row['pid'],
        ParentProcessId=row['parent_pid'], SessionId=row['session_id'], CreationFileTime=row['created'],
        CreationDate=__import__('test_process_inventory_identity').filetime_iso(row['created']), ExecutablePath=row['cim_path'])]
    raw['terminal_processes'] = [dict(pid=777)]
    raw['grid'].update(visible_tasks=0, visible_services=0)
    return raw


def collect_mock(monkeypatch, raw):
    monkeypatch.setattr(h, 'is_elevated', lambda: True)
    monkeypatch.setattr(h.platform, 'system', lambda: 'Windows')
    monkeypatch.setattr(h, 'system_directory', lambda: Path(ROOTS['system32']))
    monkeypatch.setattr(h, 'http_sys_owner', lambda *a: 777)
    monkeypatch.setattr(h.subprocess, 'run', lambda *a, **k: SimpleNamespace(returncode=0, stdout=json.dumps(raw).encode()))
    return h.collect_facts()


@PROP
@given(name=st.sampled_from(list(CONTRACTS)), value=INVALID,
       field=st.sampled_from(['image_path', 'dll_path']))
def test_property_raw_configuration_types(name, value, field):
    row, e = fixture(name)
    for key in ('implementation_before', 'implementation_after'): e[key][name][field] = value
    assert p.classify_missing(row, e, ROOTS)['status'] == 'UNRESOLVED'


@PROP
@given(name=st.sampled_from(list(CONTRACTS)), field=st.sampled_from(['image_path', 'dll_path']))
def test_property_missing_raw_configuration_is_partial(name, field):
    row, e = fixture(name)
    for key in ('implementation_before', 'implementation_after'): e[key][name].pop(field)
    assert p.classify_missing(row, e, ROOTS)['status'] == 'UNRESOLVED'


@pytest.mark.parametrize('field', ['image_path', 'dll_path'])
@pytest.mark.parametrize('name', list(CONTRACTS))
def test_schema_raw_expanded_disagreement(name, field):
    row, e = fixture(name)
    for key in ('implementation_before', 'implementation_after'): e[key][name][field] = r'C:\Other\wrong.exe'
    assert p.classify_missing(row, e, ROOTS)['status'] == 'UNRESOLVED'


@PROP
@given(name=st.sampled_from(list(CONTRACTS)), value=INVALID)
def test_property_diagnostic_native_format_types_cannot_hide_in_success(name, value):
    row, e = fixture(name)
    for key in ('native_before', 'native_after'):
        e[key].update(native_format_query_succeeded=False, native_format_path='', native_format_win32_error=value)
    # bool, non-integer, negative and out-of-uint32 are all invalid status data.
    if type(value) is int and 0 <= value <= 0xffffffff: return
    assert p.classify_missing(row, e, ROOTS)['status'] == 'UNRESOLVED'


@pytest.mark.parametrize('name', list(CONTRACTS))
def test_schema_complete_scm_cannot_contradict_diagnostic_status(name):
    row, e = fixture(name)
    for suffix in ('before', 'after'):
        e['services_'+suffix+'_reason'] = 'SERVICE_STATUS_UNAVAILABLE'
        e['services_'+suffix+'_diagnostics'] = dict(stage='OPEN_SERVICE_STATUS', win32_error=5, failed_service='Synthetic')
    assert p.classify_missing(row, e, ROOTS)['status'] == 'UNRESOLVED'


@pytest.mark.parametrize('field,value', [('Name', 'grid.exe'), ('ParentProcessId', 999),
    ('SessionId', 3), ('CreationFileTime', 123456789012345680), ('ExecutablePath', False)])
def test_cross_stage_original_identity_must_match_evidence(monkeypatch, field, value):
    raw = complete_raw();raw['private_inventory']['processes'][0][field] = value
    try: facts = collect_mock(monkeypatch, raw); h.safe_inventory(facts)
    except (ValueError, TypeError, KeyError): return
    pytest.fail('Conflicting source identity reached successful inventory')


def test_cross_stage_roots_must_bind_to_collector_boundary(monkeypatch):
    raw = complete_raw();raw['process_roots'] = dict(ROOTS, system32=r'C:\Other')
    # Rebuild a mutually coherent forged evidence tree rooted outside the actual System32.
    def moved(x):
        if isinstance(x,str):return x.replace(ROOTS['system32'], r'C:\Other')
        if isinstance(x,list):return [moved(v) for v in x]
        if isinstance(x,dict):return {k:moved(v) for k,v in x.items()}
        return x
    raw['process_evidence'] = moved(raw['process_evidence'])
    with pytest.raises(ValueError): collect_mock(monkeypatch, raw)


@pytest.mark.parametrize('field,value', [('visible_tasks','SYNTHETIC_RAW_VALUE'),
    ('visible_processes',True), ('visible_services',float('nan')),
    ('reason_counts',{'SYNTHETIC_RAW_VALUE':float('nan')})])
def test_public_projection_rejects_untyped_values(field,value):
    facts = raw_facts();facts['grid'][field] = value
    with pytest.raises(ValueError): h.public_report(facts,'a'*64)


@pytest.mark.parametrize('failure', ['coverage','raw-counter','raw-reason'])
def test_failure_has_no_private_persistence_or_raw_projection(monkeypatch,tmp_path,capsys,failure):
    facts = raw_facts()
    if failure == 'coverage': facts['grid']['coverage_complete']=False
    if failure == 'raw-counter': facts['grid']['visible_tasks']='SYNTHETIC_RAW_VALUE'
    if failure == 'raw-reason': facts['grid']['reason_counts']={'SYNTHETIC_RAW_VALUE':float('nan')}
    persisted=[]
    monkeypatch.setattr(h,'is_elevated',lambda:True)
    monkeypatch.setattr(h,'collector_identity',lambda *a,**k:dict(candidate_sha='a'*40,version='synthetic'))
    monkeypatch.setattr(h,'collect_facts',lambda:facts)
    monkeypatch.setattr(h,'save_private',lambda *a,**k:persisted.append(True))
    monkeypatch.setattr(h.subprocess,'run',lambda *a,**k:pytest.fail('No host child'))
    monkeypatch.setattr(sys,'argv',['synthetic','diagnose','--expected-sha','a'*40,
        '--output',str(tmp_path/'public.json'),'--private-observation',str(tmp_path/'private.dpapi')])
    assert h.main()==1
    assert not persisted
    public=capsys.readouterr().out
    assert 'SYNTHETIC_RAW_VALUE' not in public and 'NaN' not in public and 'PRIVATE_SENTINEL_' not in public
    assert json.loads(public)['diagnostic_status']=='FAIL_CLOSED'


@PROP
@given(names=st.sets(st.sampled_from(['KeyIso','SamSs','VaultSvc']),min_size=1,max_size=3))
def test_property_shared_lsa_membership_positive(names):
    names=sorted(names);row,e=fixture(names[0])
    for name in names[1:]:
        _,other=fixture(name)
        for suffix in ('before','after'):
            e['services_'+suffix]+=other['services_'+suffix]
            e['implementation_'+suffix].update(other['implementation_'+suffix])
            e['modules_'+suffix]['paths']+=other['modules_'+suffix]['paths'][1:]
        e['implementation_signatures'].update(other['implementation_signatures'])
    assert p.classify_missing(row,e,ROOTS)['status']=='VERIFIED_SERVICE'


@PROP
@given(name=st.sampled_from(list(CONTRACTS)), uppercase=st.booleans(), slash=st.booleans())
def test_property_ascii_case_and_separator_positive(name,uppercase,slash):
    row,e=fixture(name)
    def transform(x):
        if isinstance(x,str) and x.startswith('C:\\'):
            return (x.upper() if uppercase else x).replace('\\','/' if slash else '\\')
        if isinstance(x,list):return [transform(v) for v in x]
        if isinstance(x,dict):return {k:transform(v) for k,v in x.items()}
        return x
    assert p.classify_missing(row,transform(e),ROOTS)['status']=='VERIFIED_SERVICE'


@PROP
@given(value=st.one_of(st.none(),st.booleans(),st.floats(allow_nan=True),st.text(max_size=20),st.lists(st.integers(),max_size=3)))
def test_property_malformed_classifier_is_explicit_unresolved(value):
    result=p.classify_missing(value,value,value)
    assert result['status']=='UNRESOLVED'


@PROP
@given(name=st.sampled_from(list(CONTRACTS)), value=st.text(max_size=20),
       region=st.sampled_from(['evidence','signature','native','config','module']))
def test_property_unknown_fields_cannot_extend_an_admission_schema(name,value,region):
    row,e=fixture(name)
    target={'evidence':e,'signature':e['signature'],'native':e['native_before'],
            'config':e['implementation_before'][name],'module':e['modules_before']}[region]
    target['unsupported_private_extension']=value
    assert p.classify_missing(row,e,ROOTS)['status']=='UNRESOLVED'


def test_cross_stage_complete_positive(monkeypatch):
    h.safe_inventory(collect_mock(monkeypatch,complete_raw()))


@pytest.mark.parametrize('value', [None,False,0,float('nan'),[],{}])
def test_identity_values_are_not_coerced_into_fingerprints(value):
    facts=raw_facts();facts['identity']['sid']=value
    with pytest.raises(ValueError):h.fingerprint(facts,'a'*64)


@pytest.mark.parametrize('value', [float('nan'),float('inf'),{'nested':float('-inf')}])
def test_private_serializer_rejects_nonfinite_before_io(monkeypatch,tmp_path,value):
    monkeypatch.setattr(h,'dpapi',lambda *a,**k:pytest.fail('No DPAPI even on synthetic bad data'))
    target=tmp_path/'uncreated'/'private.dpapi'
    with pytest.raises(ValueError):h.save_private(target,dict(value=value))
    assert not target.parent.exists()


def test_unrelated_malformed_proof_cannot_hide_in_ordinary_admission():
    from test_process_inventory_identity import sample
    row,e=sample();e.update(modules_before=float('nan'),modules_after={'bad':'malformed'})
    assert p.classify_missing(row,e,ROOTS)['status']=='UNRESOLVED'


def test_public_listener_collection_type_is_not_inferred_from_iteration():
    facts=raw_facts();facts['postgres_listeners']={}
    with pytest.raises(ValueError):h.public_report(facts,'a'*64)


@PROP
@given(value=INVALID)
def test_property_malformed_outer_aggregate_is_structured_blocked(value):
    result=p.assess_processes([value],ROOTS,[123])
    assert result['unknown_process_paths']>=1 and result['reason_counts']


@pytest.mark.parametrize('fragment', ['NaN','Infinity','-Infinity'])
def test_raw_json_nonfinite_rejected_before_collection_binding(monkeypatch,fragment):
    raw=complete_raw();wire=json.dumps(raw).replace('"visible_tasks": 0','"visible_tasks": '+fragment)
    monkeypatch.setattr(h,'is_elevated',lambda:True);monkeypatch.setattr(h.platform,'system',lambda:'Windows')
    monkeypatch.setattr(h,'system_directory',lambda:Path(ROOTS['system32']))
    monkeypatch.setattr(h.subprocess,'run',lambda *a,**k:SimpleNamespace(returncode=0,stdout=wire.encode()))
    with pytest.raises(ValueError):h.collect_facts()


def test_raw_json_duplicate_identity_key_rejected(monkeypatch):
    raw=complete_raw();wire=json.dumps(raw).replace('"ProcessId": 123','"ProcessId": 999, "ProcessId": 123')
    monkeypatch.setattr(h,'is_elevated',lambda:True);monkeypatch.setattr(h.platform,'system',lambda:'Windows')
    monkeypatch.setattr(h,'system_directory',lambda:Path(ROOTS['system32']))
    monkeypatch.setattr(h.subprocess,'run',lambda *a,**k:SimpleNamespace(returncode=0,stdout=wire.encode()))
    with pytest.raises(ValueError):h.collect_facts()


def test_unicode_full_casefold_is_not_filename_identity():
    from test_process_inventory_identity import sample
    row,e=sample();row['name']='straße.exe'
    for key in ('native_before','native_after','signature'):e[key]['path']=ROOTS['system32']+'\\strasse.exe'
    assert p.classify_missing(row,e,ROOTS)['status']=='UNRESOLVED'


@pytest.mark.parametrize('name',list(CONTRACTS))
def test_unicode_confusable_account_is_not_reviewed_ascii_contract(name):
    row,e=fixture(name)
    for suffix in ('before','after'):
        e['services_'+suffix][0]['start_name']=e['services_'+suffix][0]['start_name'].replace('S','ſ').replace('s','ſ')
        e['implementation_'+suffix][name]['account']=e['implementation_'+suffix][name]['account'].replace('S','ſ').replace('s','ſ')
    assert p.classify_missing(row,e,ROOTS)['status']=='UNRESOLVED'


@pytest.mark.parametrize('failure', ['public-file','stdout'])
def test_output_failure_leaves_no_new_private_observation(monkeypatch,tmp_path,failure):
    facts=raw_facts();private=tmp_path/'private.dpapi';public=tmp_path/'public.json'
    monkeypatch.setattr(h,'is_elevated',lambda:True)
    monkeypatch.setattr(h,'collector_identity',lambda *a,**k:dict(candidate_sha='a'*40,version='synthetic'))
    monkeypatch.setattr(h,'collect_facts',lambda:facts)
    monkeypatch.setattr(h,'dpapi',lambda *a,**k:b'SYNTHETIC_CIPHERTEXT')
    monkeypatch.setattr(sys,'argv',['synthetic','diagnose','--expected-sha','a'*40,
        '--output',str(public),'--private-observation',str(private)])
    if failure=='public-file':
        monkeypatch.setattr(h.NewOutput,'write',lambda *a,**k:(_ for _ in ()).throw(OSError('SYNTHETIC')))
    else:
        calls=[]
        def failing_once(*a,**k):
            calls.append(True)
            if len(calls)==1:raise BrokenPipeError('SYNTHETIC')
        monkeypatch.setattr('builtins.print',failing_once)
    assert h.main()==1
    assert not private.exists() or private.read_bytes()==b''


def test_private_collision_preserves_existing_file(monkeypatch,tmp_path):
    monkeypatch.setattr(h,'dpapi',lambda value:value)
    target=tmp_path/'existing';target.write_bytes(b'SYNTHETIC_EXISTING')
    with pytest.raises(FileExistsError):h.save_private(target,{'synthetic':True})
    assert target.read_bytes()==b'SYNTHETIC_EXISTING'


def test_partial_private_write_is_removed(monkeypatch,tmp_path):
    monkeypatch.setattr(h,'dpapi',lambda value:value)
    target=tmp_path/'partial';original_open=Path.open
    class Partial:
        def __init__(self):self.stream=original_open(target,'x+b')
        def __getattr__(self,name):return getattr(self.stream,name)
        def write(self,value):
            self.stream.write(value[:1])
            return 1
    monkeypatch.setattr(Path,'open',lambda path,*a,**k:Partial() if path==target and a==('x+b',) else original_open(path,*a,**k))
    with pytest.raises(OSError):h.save_private(target,{'synthetic':True})
    # Keep an empty exclusive reservation; never unlink through a mutable name.
    assert target.read_bytes()==b''


def test_private_cleanup_refusal_has_fixed_diagnostic(monkeypatch,tmp_path):
    monkeypatch.setattr(h,'dpapi',lambda value:value)
    target=tmp_path/'uncreated'
    monkeypatch.setattr(h.NewOutput,'write',lambda *a,**k:(_ for _ in ()).throw(OSError('SYNTHETIC')))
    monkeypatch.setattr(h.NewOutput,'erase',lambda *a,**k:(_ for _ in ()).throw(h.DiagnosticError('PRIVATE_CLEANUP_FAILED')))
    with pytest.raises(h.DiagnosticError) as failure:h.save_private(target,{'synthetic':True})
    assert failure.value.code=='PRIVATE_CLEANUP_FAILED'
    assert 'SYNTHETIC_PRIVATE_ERROR' not in str(failure.value)
