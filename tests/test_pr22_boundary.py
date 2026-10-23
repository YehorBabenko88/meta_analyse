"""Fresh offline negative tests against an explicitly selected frozen checkout."""
import importlib.util
import json
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'commissioning'))
import host_identity as h
sys.path.insert(0,str(Path(h.__file__).resolve().parents[1]/'tests'))
from test_diagnostic_hardening import raw_facts

spec=importlib.util.spec_from_file_location('projection',Path(h.__file__).resolve().parents[1]/'scripts/project_synthetic_artifacts.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)

@pytest.mark.parametrize('alias',['same','hardlink'])
def test_public_private_alias_preserves_private_collision(monkeypatch,tmp_path,alias):
    private=tmp_path/'observation';public=private if alias=='same' else tmp_path/'public'
    private.write_bytes(b'SYNTHETIC_EXISTING_ENCRYPTED')
    if alias=='hardlink':public.hardlink_to(private)
    monkeypatch.setattr(h,'is_elevated',lambda:True)
    monkeypatch.setattr(h,'collector_identity',lambda *a,**k:dict(candidate_sha='a'*40,version='synthetic'))
    monkeypatch.setattr(h,'collect_facts',raw_facts)
    monkeypatch.setattr(h,'dpapi',lambda data,**k:b'SYNTHETIC_ENCRYPTED')
    monkeypatch.setattr(sys,'argv',['synthetic','diagnose','--expected-sha','a'*40,
        '--output',str(public),'--private-observation',str(private)])
    assert h.main()==1
    assert private.read_bytes()==b'SYNTHETIC_EXISTING_ENCRYPTED'

@pytest.mark.parametrize('shape',['declared-error','suite-error','root-error','declared-failure','double-status','properties-error','duplicate-failure'])
def test_projection_rejects_unrepresented_or_ambiguous_errors(tmp_path,shape):
    case='<testcase classname="tests.test_process_identity_acceptance" name="test_acceptance_complete_service_controls"/>'
    attrs='tests="1" errors="0" failures="0" skipped="0"'
    extra=''
    if shape=='declared-error':attrs=attrs.replace('errors="0"','errors="1"')
    if shape=='declared-failure':attrs=attrs.replace('failures="0"','failures="1"')
    if shape=='suite-error':extra='<error message="SYNTHETIC_ERROR"/>'
    if shape=='root-error':extra=''
    if shape=='double-status':case=case[:-2]+'><failure/><skipped/></testcase>'
    if shape=='properties-error':extra='<properties><error/></properties>'
    if shape=='duplicate-failure':case=case[:-2]+'><failure/><failure/></testcase>'
    wire='<testsuites><testsuite '+attrs+'>'+case+extra+'</testsuite>'+('<error/>' if shape=='root-error' else '')+'</testsuites>'
    path=tmp_path/'junit.xml';path.write_text(wire)
    with pytest.raises(ValueError):p.project_junit(path)

@pytest.mark.parametrize('name,word,spoof',[('DoSvc','NetworkService','Networkſervice'),('wscsvc','LocalServiceNetworkRestricted','LocalServiceNetworkReſtricted')])
@pytest.mark.parametrize('region',['all','raw-only','scm-only'])
def test_raw_service_arguments_are_ascii_before_casefold(name,word,spoof,region):
    import process_identity as classifier
    from test_process_identity_acceptance import fixture,ROOTS
    row,evidence=fixture(name)
    for suffix in ('before','after'):
        if region!='raw-only':evidence['services_'+suffix][0]['binary_path']=evidence['services_'+suffix][0]['binary_path'].replace(word,spoof)
        for field in (('image_path',) if region=='raw-only' else ('image_path','expanded_image_path') if region=='all' else ()):
            config=evidence['implementation_'+suffix][name]
            config[field]=config[field].replace(word,spoof)
    assert classifier.classify_missing(row,evidence,ROOTS)['status']=='UNRESOLVED'

@pytest.mark.parametrize('separator',['\u00a0','\u2003'])
def test_unicode_argument_whitespace_is_not_removed_before_ascii_guard(separator):
    import process_identity as classifier
    from test_process_identity_acceptance import fixture,ROOTS
    row,evidence=fixture()
    for suffix in ('before','after'):
        evidence['services_'+suffix][0]['binary_path']=evidence['services_'+suffix][0]['binary_path'].replace(' -k',' '+separator+'-k')
    assert classifier.classify_missing(row,evidence,ROOTS)['status']=='UNRESOLVED'

@pytest.mark.parametrize('status',['pass','error','failure','skipped'])
def test_projection_preserves_status_and_parameter_identity(tmp_path,status):
    import hashlib
    name='test_acceptance_complete_service_controls[SYNTHETIC_PARAMETER]'
    content='' if status=='pass' else '<'+status+' message="SYNTHETIC_RAW">SYNTHETIC_RAW</'+status+'>'
    path=tmp_path/'junit.xml';path.write_text('<testsuites><testsuite><testcase classname="tests.test_process_identity_acceptance" name="'+name+'">'+content+'</testcase></testsuite></testsuites>')
    p.project_junit(path)
    import xml.etree.ElementTree as ET
    suite=ET.parse(path).getroot()[0];case=suite[0]
    assert case.get('name')==name.split('[',1)[0]+'[sha256:'+hashlib.sha256(name.encode()).hexdigest()+']'
    assert len(case)==int(status!='pass')
    assert not list(case) or case[0].tag==status
    assert 'SYNTHETIC_RAW' not in path.read_text()
