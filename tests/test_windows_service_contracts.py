"""Synthetic proof-gated OS service contracts; no host collection."""
import copy
import ntpath
import sys
from pathlib import Path

import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'commissioning'))
import process_identity as p
from test_process_inventory_identity import sample, ROOTS

CONTRACTS={
    'KeyIso':('lsass.exe','keyiso.dll','','LocalSystem','parameters'),
    'SamSs':('lsass.exe','samsrv.dll','','LocalSystem','integrated'),
    'VaultSvc':('lsass.exe','vaultsvc.dll','','LocalSystem','parameters'),
    'DoSvc':('svchost.exe','dosvc.dll','-k NetworkService -p',r'NT Authority\NetworkService','root'),
    'wscsvc':('svchost.exe','wscsvc.dll','-k LocalServiceNetworkRestricted -p',r'NT Authority\LocalService','parameters'),
}

def evidence(name='DoSvc'):
    host,dll,args,account,source=CONTRACTS[name]
    row,e=sample()
    path=ntpath.join(ROOTS['system32'],host)
    module=ntpath.join(ROOTS['system32'],dll)
    row['name']=host
    for key in ('native_before','native_after','signature'):e[key]['path']=path
    command=path+(' '+args if args else '')
    svc=dict(name=name,pid=row['pid'],state=4,binary_path=command,service_type=32,start_name=account,error_stage='',win32_error=0)
    for key in ('services_before','services_after'):e[key]=[copy.deepcopy(svc)]
    config=dict(complete=True,name=name,service_type=32,account=account,expanded_image_path=command,
        image_path=command,dll_source=source,dll_present=source!='integrated',expanded_dll_path=module if source!='integrated' else '',
        dll_path=module if source!='integrated' else '',error_stage='')
    e['implementation_before']={name:config}
    e['implementation_after']=copy.deepcopy(e['implementation_before'])
    modules=dict(complete=True,pid=row['pid'],created=row['created'],alive=True,paths=[path,module],error_stage='',win32_error=0)
    e['modules_before']=modules
    e['modules_after']=copy.deepcopy(modules)
    sig=copy.deepcopy(e['signature']);sig['path']=module
    e['implementation_signatures']={name:sig}
    return row,e

@pytest.mark.parametrize('name',list(CONTRACTS))
def test_complete_named_service_implementation_proof_can_verify(name):
    row,e=evidence(name)
    assert p.classify_missing(row,e,ROOTS)['status']=='VERIFIED_SERVICE'

@pytest.mark.parametrize('name', list(CONTRACTS))
@pytest.mark.parametrize('fault',[
    'missing-proof','registry-denied','registry-changed','wrong-dll-source','wrong-dll','wrong-host-command',
    'wrong-account','wrong-type','scm-registry-disagree','missing-modules','module-access-denied',
    'module-pid-reuse','module-pid-mismatch','module-exited','module-changed','module-absent','module-path-spoof',
    'dll-signature-missing','dll-unsigned','dll-publisher','dll-hash','dll-reparse','dll-signed-other-path',
    'scm-incomplete','scm-config-change','native-pid-reuse','native-image-change','extra-service',
])
def test_unproved_or_spoofed_service_implementation_stays_unresolved(fault, name):
    row,e=evidence(name)
    if fault=='missing-proof':e.pop('implementation_before')
    if fault=='registry-denied':e['implementation_before'][name]['complete']=False
    if fault=='registry-changed':e['implementation_after'][name]['image_path']+=' changed'
    if fault=='wrong-dll-source':
        for key in ('implementation_before','implementation_after'):e[key][name]['dll_source']='ambiguous'
    if fault=='wrong-dll':
        for key in ('implementation_before','implementation_after'):e[key][name]['expanded_dll_path']=r'C:\Other\dosvc.dll'
    if fault=='wrong-host-command':
        for key in ('services_before','services_after'):e[key][0]['binary_path']+=' -s OTHER'
        for key in ('implementation_before','implementation_after'):e[key][name]['expanded_image_path']+=' -s OTHER'
    if fault=='wrong-account':
        for key in ('services_before','services_after'):e[key][0]['start_name']='OtherAccount'
        for key in ('implementation_before','implementation_after'):e[key][name]['account']='OtherAccount'
    if fault=='wrong-type':
        for key in ('services_before','services_after'):e[key][0]['service_type']=16
        for key in ('implementation_before','implementation_after'):e[key][name]['service_type']=16
    if fault=='scm-registry-disagree':
        for key in ('implementation_before','implementation_after'):e[key][name]['expanded_image_path']+=' -s OTHER'
    if fault=='missing-modules':e.pop('modules_before')
    if fault=='module-access-denied':e['modules_before'].update(complete=False,error_stage='OPEN_PROCESS_MODULES',win32_error=5)
    if fault=='module-pid-reuse':e['modules_after']['created']+=10
    if fault=='module-pid-mismatch':e['modules_before']['pid']+=1
    if fault=='module-exited':e['modules_after']['alive']=False
    if fault=='module-changed':e['modules_after']['paths'].append(r'C:\Windows\System32\other.dll')
    if fault=='module-absent':
        for key in ('modules_before','modules_after'):e[key]['paths']=e[key]['paths'][:1]
    if fault=='module-path-spoof':
        for key in ('modules_before','modules_after'):e[key]['paths'][1]=r'C:\Other\dosvc.dll'
    if fault=='dll-signature-missing':e.pop('implementation_signatures')
    if fault=='dll-unsigned':e['implementation_signatures'][name]['status']='NotSigned'
    if fault=='dll-publisher':e['implementation_signatures'][name]['subject']='CN=Unreviewed Publisher'
    if fault=='dll-hash':e['implementation_signatures'][name]['sha256_after']='b'*64
    if fault=='dll-reparse':e['implementation_signatures'][name]['reparse_point']=True
    if fault=='dll-signed-other-path':e['implementation_signatures'][name]['path']=r'C:\Other\dosvc.dll'
    if fault=='scm-incomplete':e['services_before_complete']=False
    if fault=='scm-config-change':e['services_after'][0]['binary_path']+=' changed'
    if fault=='native-pid-reuse':e['native_after']['created']+=1
    if fault=='native-image-change':e['native_after']['path']=r'C:\Windows\System32\other.exe'
    if fault=='extra-service':
        for key in ('services_before','services_after'):e[key].append(dict(name='UnknownAttachedService',pid=row['pid'],state=4,binary_path=e[key][0]['binary_path']))
    assert p.classify_missing(row,e,ROOTS)['status']=='UNRESOLVED'

def test_new_service_name_alone_does_not_extend_trust():
    row,e=evidence();e.pop('implementation_before')
    assert p.classify_missing(row,e,ROOTS)['reason_code']=='SERVICE_IMPLEMENTATION_UNVERIFIED'


@pytest.mark.parametrize('name', list(CONTRACTS))
def test_service_host_cannot_fall_back_to_system_image_with_empty_membership(name):
    row,e=evidence(name)
    for key in ('services_before','services_after'):e[key]=[]
    for key in ('implementation_before','implementation_after','implementation_signatures','modules_before','modules_after'):
        e.pop(key)
    assert p.classify_missing(row,e,ROOTS)==dict(status='UNRESOLVED',reason_code='SERVICE_IDENTITY_UNAVAILABLE')


@pytest.mark.parametrize('snapshot', ['services_before','services_after','both'])
def test_duplicate_service_membership_is_not_complete_evidence(snapshot):
    row,e=evidence()
    for key in ('services_before','services_after'):
        if snapshot in (key,'both'):e[key].append(copy.deepcopy(e[key][0]))
    assert p.classify_missing(row,e,ROOTS)==dict(status='UNRESOLVED',reason_code='SERVICE_IDENTITY_UNAVAILABLE')


@pytest.mark.parametrize('first', [True,False])
def test_mixed_membership_cannot_verify_in_either_order(first):
    row,e=evidence()
    for key in ('services_before','services_after'):
        unreviewed=dict(e[key][0],name='UnreviewedSyntheticService')
        e[key].insert(0,unreviewed) if first else e[key].append(unreviewed)
    assert p.classify_missing(row,e,ROOTS)==dict(status='UNRESOLVED',reason_code='SERVICE_RULE_UNREVIEWED')

def test_integrated_service_cannot_ignore_configured_dll():
    row,e=evidence('SamSs')
    for key in ('implementation_before','implementation_after'):
        e[key]['SamSs'].update(dll_present=True,dll_source='root',expanded_dll_path=r'C:\Windows\System32\samsrv.dll')
    assert p.classify_missing(row,e,ROOTS)['status']=='UNRESOLVED'

def test_unavailable_dll_file_proof_has_precise_refusal():
    row,e=evidence();e['implementation_signatures']['DoSvc']=None
    assert p.classify_missing(row,e,ROOTS)['reason_code']=='SERVICE_DLL_SIGNATURE_UNVERIFIED'

def test_combined_lsa_membership_requires_every_implementation():
    row,e=evidence('KeyIso')
    for name in ('SamSs','VaultSvc'):
        _,other=evidence(name)
        for key in ('services_before','services_after'):e[key]+=other[key]
        for key in ('implementation_before','implementation_after','implementation_signatures'):e[key].update(other[key])
        for key in ('modules_before','modules_after'):e[key]['paths']+=other[key]['paths'][1:]
    assert p.classify_missing(row,e,ROOTS)['status']=='VERIFIED_SERVICE'
    e['implementation_signatures'].pop('VaultSvc')
    assert p.classify_missing(row,e,ROOTS)['status']=='UNRESOLVED'

@pytest.mark.parametrize('name',['Registry','Secure System','Memory Compression'])
def test_native_format_and_kernel_label_never_authorize_error31(name):
    row,e=sample();row['name']=name
    for key in ('native_before','native_after'):
        e[key].update(path='',image_query_succeeded=False,error_stage='QUERY_IMAGE',win32_error=31,
            native_format_query_succeeded=True,native_format_path=r'\Device\Synthetic\image.exe')
    kernel=dict(pid=row['pid'],name=name,created=row['created'],parent_pid=4,session_id=0)
    e.update(kernel_before=kernel,kernel_after=copy.deepcopy(kernel))
    assert p.classify_missing(row,e,ROOTS)==dict(status='UNRESOLVED',reason_code='IMAGE_PATH_UNAVAILABLE')

@pytest.mark.parametrize('name', list(CONTRACTS))
@pytest.mark.parametrize('key', ['native_before', 'native_after', 'services_before', 'services_after',
    'implementation_before', 'implementation_after', 'implementation_signatures', 'modules_before', 'modules_after'])
def test_every_contract_requires_each_evidence_source(name, key):
    row, e = evidence(name)
    e.pop(key)
    assert p.classify_missing(row, e, ROOTS)['status'] == 'UNRESOLVED'


@pytest.mark.parametrize('name', list(CONTRACTS))
@pytest.mark.parametrize('source,field,value', [
    ('modules', 'pid', 123.0), ('modules', 'created', 123456789012345670.0),
    ('modules', 'win32_error', False), ('services', 'pid', 123.0),
    ('services', 'state', 4.0), ('services', 'service_type', 32.0),
    ('implementation', 'service_type', 32.0),
])
def test_contract_numeric_identity_types_fail_closed(name, source, field, value):
    row, e = evidence(name)
    for suffix in ('before', 'after'):
        item = e[source + '_' + suffix]
        if source == 'services': item = item[0]
        if source == 'implementation': item = item[name]
        item[field] = value
    assert p.classify_missing(row, e, ROOTS)['status'] == 'UNRESOLVED'


@pytest.mark.parametrize('name', list(CONTRACTS))
@pytest.mark.parametrize('value', [None, False, 0.0, 5, '0'])
def test_scm_requires_explicit_success_error_code(name, value):
    row, e = evidence(name)
    for key in ('services_before', 'services_after'):
        if value is None: e[key][0].pop('win32_error')
        else: e[key][0]['win32_error'] = value
    assert p.classify_missing(row, e, ROOTS)['status'] == 'UNRESOLVED'


@pytest.mark.parametrize('field,value', [('win32_error', 5), ('error_stage', 'QUERY_IMAGE')])
def test_successful_native_image_requires_consistent_success_status(field, value):
    row, e = evidence()
    for key in ('native_before', 'native_after'): e[key][field] = value
    assert p.classify_missing(row, e, ROOTS)['status'] == 'UNRESOLVED'
