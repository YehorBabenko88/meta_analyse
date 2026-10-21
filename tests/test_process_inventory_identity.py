import copy
import json
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'commissioning'))
import process_identity as p

ROOTS=dict(system32=r'C:\Windows\System32',program_files=r'C:\Program Files')

def sample(service=False):
    path=r'C:\Program Files\Norton\Suite\NortonSvc.exe' if service else r'C:\Windows\System32\winlogon.exe'
    row=dict(pid=123,name='NortonSvc.exe' if service else 'winlogon.exe',created=123456789012345670,parent_pid=4,session_id=0,cim_path='')
    native=dict(pid=123,path=path,created=row['created'],alive=True,image_query_succeeded=True,error_stage='',win32_error=0)
    sig=dict(path=path,status='Valid',subject='CN=Gen Digital Inc., O=Gen Digital Inc.' if service else 'CN=Microsoft Windows, O=Microsoft Corporation',sha256='a'*64,sha256_after='a'*64,reparse_point=False)
    svc=[dict(name='Norton Antivirus',pid=123,state=4,binary_path='"'+path+'" /runassvc',win32_error=0)]
    e=dict(native_before=native,native_after=copy.deepcopy(native),signature=sig,services_before=svc if service else [],services_after=copy.deepcopy(svc) if service else [],services_before_complete=True,services_after_complete=True)
    return row,e

@pytest.mark.parametrize('service',[True,False])
def test_native_runtime_and_signature_resolve_missing_wmi_path(service):
    row,e=sample(service)
    assert p.classify_missing(row,e,ROOTS)['status'].startswith('VERIFIED_')

@pytest.mark.parametrize('fault',['pid-reuse','pid-conflict','creation-missing','process-exited','path-switch','unsigned','wrong-publisher','hash-change','reparse','unknown','missing-native','missing-signature'])
def test_unknown_or_conflicting_identity_remains_fail_closed(fault):
    row,e=sample()
    if fault=='pid-reuse':e['native_after']['created']+=10
    if fault=='pid-conflict':e['native_after']['pid']+=1
    if fault=='creation-missing':row['created']=None
    if fault=='process-exited':e['native_after']['alive']=False
    if fault=='path-switch':e['native_after']['path']=r'C:\Windows\System32\svchost.exe'
    if fault=='unsigned':e['signature']['status']='NotSigned'
    if fault=='wrong-publisher':e['signature']['subject']='CN=Unknown vendor'
    if fault=='hash-change':e['signature']['sha256_after']='b'*64
    if fault=='reparse':e['signature']['reparse_point']=True
    if fault=='unknown':
        for n in ('native_before','native_after','signature'):e[n]['path']=r'C:\Unknown\lsass.exe'
    if fault=='missing-native':e['native_before']={}
    if fault=='missing-signature':e['signature']={}
    assert p.classify_missing(row,e,ROOTS)['status']=='UNRESOLVED'

@pytest.mark.parametrize('fault',['service-pid','service-stopped','service-name','service-binary','service-change','services-unavailable','native-unavailable'])
def test_signed_service_path_and_name_are_not_runtime_authorization(fault):
    row,e=sample(True)
    if fault=='service-pid':e['services_before'][0]['pid']=999
    if fault=='service-stopped':e['services_before'][0]['state']=1
    if fault=='service-name':e['services_before'][0]['name']='Renamed service'
    if fault=='service-binary':e['services_before'][0]['binary_path']=r'C:\Windows\System32\svchost.exe'
    if fault=='service-change':e['services_after'][0]['binary_path']+=' --changed'
    if fault=='services-unavailable':e['services_after']=[]
    if fault=='native-unavailable':e['native_after']={}
    assert p.classify_missing(row,e,ROOTS)['status']=='UNRESOLVED'

def test_grid_indicators_cannot_hide_behind_valid_signature():
    row,e=sample(True)
    row['name']='bybit-grid.exe'
    assert p.classify_missing(row,e,ROOTS)['reason_code']=='GRID_PROCESS_INDICATOR'

def test_no_name_only_exemptions_for_protected_processes():
    for name in ('Registry','Secure System','Memory Compression','lsass.exe','NortonSvc.exe'):
        row,e=sample();row['name']=name
        assert p.classify_missing(row,{},ROOTS)['status']=='UNRESOLVED'

def test_kernel_pseudo_process_needs_independent_kernel_snapshot():
    row=dict(pid=4,name='System',parent_pid=0,session_id=0,created=123456789012345670,cim_path='')
    k=dict(pid=4,name='System',parent_pid=0,session_id=0,created=row['created'])
    e=dict(kernel_before=k,kernel_after=copy.deepcopy(k))
    assert p.classify_missing(row,e,ROOTS)['status']=='VERIFIED_KERNEL'
    e['kernel_after']['created']+=10
    assert p.classify_missing(row,e,ROOTS)['status']=='UNRESOLVED'
    assert p.classify_missing(row,{},ROOTS)['status']=='UNRESOLVED'

def test_idle_kernel_identity_uses_observed_creation_time():
    row=dict(pid=0,name='System Idle Process',parent_pid=0,session_id=0,created=123456789012345670)
    kernel=dict(pid=0,name='',parent_pid=0,session_id=0,created=row['created'])
    assert p.classify_missing(row,dict(kernel_before=kernel,kernel_after=copy.deepcopy(kernel)),ROOTS)['status']=='VERIFIED_KERNEL'

@pytest.mark.parametrize('service_name',list(p.SERVICE_RULES))
def test_all_reviewed_services_need_native_scm_and_matching_publisher(service_name):
    import ntpath
    root,relative,publishers=p.SERVICE_RULES[service_name]
    row,e=sample(True);path=ntpath.join(ROOTS[root],relative);row['name']=ntpath.basename(path)
    for key in ('native_before','native_after','signature'):e[key]['path']=path
    e['signature']['subject']='CN='+sorted(publishers)[0]+', O=Fixture'
    for key in ('services_before','services_after'):
        e[key][0].update(name=service_name,binary_path='"'+path+'"')
    assert p.classify_missing(row,e,ROOTS)['status']=='VERIFIED_SERVICE'
    e['services_before']=[];e['services_after']=[]
    assert p.classify_missing(row,e,ROOTS)['status']=='UNRESOLVED'

def test_partial_native_probe_exception_is_not_ignored():
    row,e=sample();e['collection_error']='PROCESS_EVIDENCE_UNAVAILABLE'
    assert p.classify_missing(row,e,ROOTS)['status']=='UNRESOLVED'

def test_unresolved_counts_cannot_be_hidden_by_coverage_flag():
    import host_identity as h
    with pytest.raises(ValueError):h.safe_inventory(dict(collector_elevated=True,grid=dict(coverage_complete=True,errors=[],findings=[],unknown_process_paths=1)))

@pytest.mark.parametrize('key',['services_before','services_after','services_before_complete','services_after_complete'])
def test_missing_scm_membership_evidence_is_not_empty_membership(key):
    row,e=sample();e.pop(key)
    assert p.classify_missing(row,e,ROOTS)['status']=='UNRESOLVED'

def test_service_attached_during_collection_invalidates_system_image():
    row,e=sample()
    e['services_after']=[dict(name='NewlyAttachedService',pid=row['pid'],state=4,binary_path='"'+e['native_before']['path']+'"')]
    assert p.classify_missing(row,e,ROOTS)['status']=='UNRESOLVED'

def test_every_missing_cim_pid_requires_evidence_exactly_once():
    row,e=sample()
    for records,expected in [([], [123]),([dict(process=row,evidence=e)],[123,999]),([dict(process=row,evidence=e),dict(process=row,evidence=e)],[123])]:
        assessment=p.assess_processes(records,ROOTS,expected)
        assert assessment['unknown_process_paths']>0
        assert assessment['reason_counts']

def test_diagnose_has_single_sanitized_report_for_inventory_rejection(monkeypatch,tmp_path,capsys):
    import host_identity as h
    facts=dict(collector_elevated=True,identity=dict(hostname='PRIVATE_HOST',username='PRIVATE_USER',sid='PRIVATE_SID',machine_guid='PRIVATE_GUID',install_id='PRIVATE_INSTALL',hardware_uuid='PRIVATE_HARDWARE'),
        os=dict(system='Windows',edition='Professional',build=26300),grid=dict(findings=[],errors=['Some process identities unresolved'],coverage_complete=False,unknown_process_paths=1),credential_names=[],production_dsn_names=[],api_listeners=[{}])
    monkeypatch.setattr(h,'collect_facts',lambda:facts)
    monkeypatch.setattr(h,'is_elevated',lambda:True)
    monkeypatch.setattr(h,'collector_identity',lambda *a,**kw:dict(version='synthetic',candidate_sha='1'*40,source_hashes={}))
    monkeypatch.setattr(h,'save_private',lambda *a:None)
    monkeypatch.setattr(sys,'argv',['guard','diagnose','--expected-sha','1'*40,'--output',str(tmp_path/'public.json'),'--private-observation',str(tmp_path/'private.dpapi')])
    assert h.main()==1
    output=capsys.readouterr().out
    result=json.loads(output)
    assert result['diagnostic_status']=='FAIL_CLOSED'
    assert result['reason_codes']==['INCOMPLETE_INVENTORY']
    assert json.loads((tmp_path/'public.json').read_text())==result
    assert 'PRIVATE_' not in output
