"""Standalone synthetic regressions, runnable against historical classifier files."""
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'commissioning'))
import process_identity as p

ROOTS = dict(system32=r'C:\Windows\System32', program_files=r'C:\Program Files')


def synthetic_host(name='svchost.exe', directory=ROOTS['system32']):
    path = directory + '\\' + name
    row = dict(pid=123, name=name, created=123456789012345670, cim_path='',parent_pid=4,session_id=0)
    native = dict(pid=123, path=path, created=row['created'], alive=True,
                  image_query_succeeded=True, error_stage='', win32_error=0)
    proof = dict(native_before=native, native_after=copy.deepcopy(native),
                 signature=dict(path=path, status='Valid', subject='CN=Microsoft Windows',
                                sha256='a'*64, sha256_after='a'*64, reparse_point=False),
                 services_before=[], services_after=[],
                 services_before_complete=True, services_after_complete=True)
    return row, proof


def test_signed_svchost_with_empty_scm_cannot_use_system_image_fallback():
    row, proof = synthetic_host()
    assert p.classify_missing(row, proof, ROOTS) == dict(
        status='UNRESOLVED', reason_code='SERVICE_IDENTITY_UNAVAILABLE')


def test_ordinary_system_image_with_empty_scm_keeps_existing_trust():
    row, proof = synthetic_host('winlogon.exe')
    assert p.classify_missing(row, proof, ROOTS)['status'] == 'VERIFIED_SYSTEM_IMAGE'


@pytest.mark.parametrize('endpoint', ['services_before_complete', 'services_after_complete'])
def test_incomplete_scm_never_means_empty_membership(endpoint):
    row, proof = synthetic_host()
    proof[endpoint] = False
    assert p.classify_missing(row, proof, ROOTS) == dict(
        status='UNRESOLVED', reason_code='SERVICE_MEMBERSHIP_UNAVAILABLE')


@pytest.mark.parametrize('fault,reason', [
    ('unknown-service', 'SERVICE_RULE_UNREVIEWED'),
    ('spoofed-host', 'UNREVIEWED_PROCESS_IMAGE'),
    ('membership-changed', 'SERVICE_MEMBERSHIP_CHANGED'),
    ('configuration-changed', 'SERVICE_CONFIGURATION_CHANGED'),
    ('native-image-changed', 'IMAGE_PATH_CHANGED'),
])
def test_service_host_boundary_rejects_conflicts(fault, reason):
    row, proof = synthetic_host(directory=r'C:\Other' if fault == 'spoofed-host' else ROOTS['system32'])
    if fault in ('unknown-service', 'membership-changed', 'configuration-changed'):
        service = dict(name='UnreviewedSyntheticService', pid=row['pid'], state=4,
                       binary_path=proof['native_before']['path'], error_stage='', win32_error=0)
        proof['services_before'] = [service]
        proof['services_after'] = [copy.deepcopy(service)]
        if fault == 'membership-changed': proof['services_after'] = []
        if fault == 'configuration-changed': proof['services_after'][0]['binary_path'] += ' --changed'
    if fault == 'native-image-changed': proof['native_after']['path'] = r'C:\Other\svchost.exe'
    assert p.classify_missing(row, proof, ROOTS) == dict(status='UNRESOLVED', reason_code=reason)
