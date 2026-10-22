"""Independent synthetic admission checks. No host collection or OS API calls."""
import copy
import ntpath
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'commissioning'))
import process_identity as p

ROOTS = dict(system32=r'C:\Windows\System32', program_files=r'C:\Program Files')
CONTRACTS = {
    'KeyIso': ('lsass.exe', 'keyiso.dll', '', 'LocalSystem', 'parameters'),
    'SamSs': ('lsass.exe', 'samsrv.dll', '', 'LocalSystem', 'integrated'),
    'VaultSvc': ('lsass.exe', 'vaultsvc.dll', '', 'LocalSystem', 'parameters'),
    'DoSvc': ('svchost.exe', 'dosvc.dll', '-k NetworkService -p', r'NT Authority\NetworkService', 'root'),
    'wscsvc': ('svchost.exe', 'wscsvc.dll', '-k LocalServiceNetworkRestricted -p', r'NT Authority\LocalService', 'parameters'),
}


def fixture(name='DoSvc'):
    host, dll, args, account, source = CONTRACTS[name]
    path = ntpath.join(ROOTS['system32'], host)
    module = ntpath.join(ROOTS['system32'], dll)
    created = 123456789012345670
    row = dict(pid=123, name=host, created=created, parent_pid=4, session_id=0, cim_path='')
    native = dict(pid=123, created=created, path=path, alive=True,
                  image_query_succeeded=True, error_stage='', win32_error=0)
    signature = dict(path=path, status='Valid', subject='CN=Microsoft Windows',
                     sha256='a' * 64, sha256_after='a' * 64, reparse_point=False)
    command = path + (' ' + args if args else '')
    scm = dict(name=name, pid=123, state=4, binary_path=command, service_type=32,
               start_name=account, error_stage='', win32_error=0)
    config = dict(complete=True, name=name, service_type=32, account=account,
                  image_path=command, expanded_image_path=command, dll_source=source,
                  dll_present=source != 'integrated', dll_path=module if source != 'integrated' else '',
                  expanded_dll_path=module if source != 'integrated' else '', error_stage='')
    modules = dict(complete=True, pid=123, created=created, alive=True,
                   paths=[path, module], error_stage='', win32_error=0)
    proof = dict(signature=signature, implementation_signatures={name: dict(signature, path=module)})
    for suffix in ('before', 'after'):
        proof['native_' + suffix] = copy.deepcopy(native)
        proof['services_' + suffix] = [copy.deepcopy(scm)]
        proof['services_' + suffix + '_complete'] = True
        proof['implementation_' + suffix] = {name: copy.deepcopy(config)}
        proof['modules_' + suffix] = copy.deepcopy(modules)
    return row, proof


def add_topology(row, proof):
    topology = {key: row[key] for key in ('pid', 'created', 'parent_pid', 'session_id', 'name')}
    proof.update(kernel_before=topology, kernel_after=copy.deepcopy(topology))


@pytest.mark.parametrize('name', list(CONTRACTS))
@pytest.mark.parametrize('topology', [False, True])
def test_acceptance_complete_service_controls(name, topology):
    row, proof = fixture(name)
    if topology: add_topology(row, proof)
    assert p.classify_missing(row, proof, ROOTS)['status'] == 'VERIFIED_SERVICE'


@pytest.mark.parametrize('name', list(CONTRACTS))
@pytest.mark.parametrize('field,value', [('pid', 123.0), ('state', 4.0),
    ('service_type', 32.0), ('win32_error', False), ('win32_error', 0.0)])
def test_acceptance_after_scm_types_are_independently_validated(name, field, value):
    row, proof = fixture(name)
    proof['services_after'][0][field] = value
    assert p.classify_missing(row, proof, ROOTS)['status'] == 'UNRESOLVED'


@pytest.mark.parametrize('name', list(CONTRACTS))
@pytest.mark.parametrize('source', ['services', 'implementation', 'modules'])
@pytest.mark.parametrize('value', ['missing', None, False, 0, [], {}])
def test_acceptance_explicit_success_stage_required(name, source, value):
    row, proof = fixture(name)
    for suffix in ('before', 'after'):
        item = proof[source + '_' + suffix]
        if source == 'services': item = item[0]
        if source == 'implementation': item = item[name]
        if value == 'missing': item.pop('error_stage')
        else: item['error_stage'] = value
    assert p.classify_missing(row, proof, ROOTS)['status'] == 'UNRESOLVED'


@pytest.mark.parametrize('name', list(CONTRACTS))
@pytest.mark.parametrize('fault', ['pid-reuse', 'pid', 'parent', 'session', 'name',
                                  'missing-before', 'missing-after', 'null', 'bool-pid'])
def test_acceptance_successful_service_rejects_conflicting_topology(name, fault):
    row, proof = fixture(name)
    add_topology(row, proof)
    if fault == 'pid-reuse': proof['kernel_after']['created'] += 1
    if fault == 'pid': proof['kernel_after']['pid'] += 1
    if fault == 'parent': proof['kernel_after']['parent_pid'] += 1
    if fault == 'session': proof['kernel_after']['session_id'] += 1
    if fault == 'name':
        for key in ('kernel_before', 'kernel_after'): proof[key]['name'] = 'Registry'
    if fault == 'missing-before': proof.pop('kernel_before')
    if fault == 'missing-after': proof.pop('kernel_after')
    if fault == 'null': proof['kernel_before'] = proof['kernel_after'] = None
    if fault == 'bool-pid':
        for key in ('kernel_before', 'kernel_after'): proof[key]['pid'] = True
    assert p.classify_missing(row, proof, ROOTS)['status'] == 'UNRESOLVED'


@pytest.mark.parametrize('pid', [0, 4])
@pytest.mark.parametrize('extra', ['native_before', 'native_after', 'services_before',
    'services_after', 'signature', 'modules_before', 'implementation_before'])
def test_acceptance_special_pid_rejects_mixed_file_service_proof(pid, extra):
    row = dict(pid=pid, name='System' if pid else 'System Idle Process',
               parent_pid=0, session_id=0, created=123456789012345670)
    topology = dict(row, name='System' if pid else '')
    proof = dict(kernel_before=topology, kernel_after=copy.deepcopy(topology))
    assert p.classify_missing(row, proof, ROOTS)['status'] == 'VERIFIED_KERNEL'
    proof[extra] = {'synthetic_conflicting_evidence': True}
    assert p.classify_missing(row, proof, ROOTS)['status'] == 'UNRESOLVED'


def test_acceptance_ordinary_image_control_and_conflicting_topology():
    row, proof = fixture()
    path = ntpath.join(ROOTS['system32'], 'winlogon.exe')
    row['name'] = 'winlogon.exe'
    for key in ('native_before', 'native_after', 'signature'): proof[key]['path'] = path
    for key in ('services_before', 'services_after'): proof[key] = []
    for key in ('modules_before', 'modules_after', 'implementation_before', 'implementation_after', 'implementation_signatures'):
        proof.pop(key)
    assert p.classify_missing(row, proof, ROOTS)['status'] == 'VERIFIED_SYSTEM_IMAGE'
    add_topology(row, proof)
    assert p.classify_missing(row, proof, ROOTS)['status'] == 'VERIFIED_SYSTEM_IMAGE'
    proof['kernel_after']['created'] += 1
    assert p.classify_missing(row, proof, ROOTS)['status'] == 'UNRESOLVED'
