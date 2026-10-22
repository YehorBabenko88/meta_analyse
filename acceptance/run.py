"""Independent exact-source acceptance harness. Never imports a live collector."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

TARGET = '289c414011afdd52eb7b8dab6dbfd3166c8fdbcb'
TREE = '85af7270f78a91d987e6b4d9784339b4ae2e874d'
HERE = Path(__file__).resolve().parent
SYNTHETIC = ['tests/test_kernel_identity_evidence.py', 'tests/test_process_inventory_identity.py', 'tests/test_host_identity_authorization.py', 'tests/test_diagnostic_hardening.py', 'tests/test_windows_service_contracts.py', 'tests/test_service_host_fallback.py']
NATIVE = ['tests/test_diagnostic_hardening.py::test_private_evidence_real_dpapi_roundtrip_or_platform_refusal', 'tests/test_host_identity_authorization.py::test_windows_dpapi_tamper_or_other_platform_fails_closed']
STORAGE = ['tests/test_storage_ingestion_unit.py', 'tests/test_storage_ingestion_postgres.py', 'tests/test_flow_history_storage.py', 'tests/test_integration_contract_shutdown.py']


def git(*args, cwd=None):
    return subprocess.check_output(['git', *args], cwd=cwd, text=True).strip()


def verify():
    if git('rev-parse', 'HEAD') != TARGET or git('rev-parse', 'HEAD^{tree}') != TREE or git('status', '--porcelain', '--untracked-files=no'):
        raise ValueError('EXACT_SOURCE_CHECK_REJECTED')


def identity(node):
    module, *parts = node.split('::')
    return '.'.join([module.removesuffix('.py').replace('/', '.'), *parts])


def validate(root, expected, allowed=()):
    cases = list(root.iter('testcase'))
    actual = [c.get('classname', '')+'.'+c.get('name', '') for c in cases]
    if not expected or len(actual) != len(set(actual)) or set(actual) != set(expected):
        raise ValueError('JUNIT_IDENTITY_COMPLETENESS_REJECTED')
    suites = list(root.iter('testsuite'))
    if not suites or sum(int(s.get('tests', '-1')) for s in suites) != len(cases):
        raise ValueError('JUNIT_COUNT_REJECTED')
    for s in suites:
        for attr, tag in [('failures', 'failure'), ('errors', 'error'), ('skipped', 'skipped')]:
            if int(s.get(attr, '0')) != sum(c.find(tag) is not None for c in s.iter('testcase')):
                raise ValueError('JUNIT_COUNTER_REJECTED')
    for c in cases:
        if c.find('failure') is not None or c.find('error') is not None:
            raise ValueError('JUNIT_FAILURE_REJECTED')
        if c.find('skipped') is not None and c.get('classname', '')+'.'+c.get('name', '') not in allowed:
            raise ValueError('JUNIT_UNEXPECTED_SKIP_REJECTED')
    return cases


def safe(path):
    """Schema projection plus conservative scan; never echo a rejected value."""
    text = path.read_text(encoding='utf-8')
    import re
    if re.search(r'hostname\s*=|["\'](?:hostname|username|services_before|services_after|kernel_before|kernel_after|native_before|native_after|private_inventory|machine_guid|sid|binary_path)["\']\s*:', text, re.I):
        raise ValueError('PUBLIC_PRIVACY_REJECTED')
    if re.search(r'[A-Z]:[\\/]+(?:Users|Windows[\\/]+Temp)[\\/]+|/(?:tmp|home/runner|Users|private/var)/|PRIVATE_SENTINEL_|\bS-1-5-(?:\d+-){2,}\d+', text, re.I):
        raise ValueError('PUBLIC_PRIVACY_REJECTED')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['synthetic', 'full', 'storage', 'native', 'archive'])
    args = parser.parse_args()
    verify()
    if args.mode in ('full', 'storage', 'native') and os.environ.get('GITHUB_ACTIONS') != 'true':
        raise SystemExit('DISPOSABLE_ACTIONS_RUNNER_REQUIRED')
    selections = {'synthetic': SYNTHETIC, 'full': [], 'storage': STORAGE, 'native': NATIVE, 'archive': ['tests/test_archive_http_server.py', 'tests/test_archive_resumable_faults.py']}
    deselect = [] if args.mode in ('storage', 'native') else ['--deselect='+n for n in NATIVE]
    base = [sys.executable, '-m', 'pytest', *selections[args.mode], *deselect]
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen')
    if args.mode == 'synthetic':
        env['PR18_SYNTHETIC_BOUNDARY'] = '1'
        env['PYTHONPATH'] = str(HERE)+os.pathsep+env.get('PYTHONPATH', '')
        base.extend(['-p', 'synthetic_boundary'])
    collection = subprocess.run([*base, '--collect-only', '-q'], env=env, capture_output=True, text=True)
    if collection.returncode: raise SystemExit('COLLECTION_REJECTED')
    expected = [identity(line.strip()) for line in collection.stdout.splitlines() if line.startswith('tests/') and '::' in line]
    pinned = json.loads((HERE/'identities'/f'{args.mode}.json').read_text())
    if not expected or len(expected) != len(set(expected)) or set(expected) != set(pinned):
        raise SystemExit('PINNED_IDENTITIES_REJECTED')
    code = subprocess.call([*base, '-q', '-W', 'error::RuntimeWarning', '--junitxml=acceptance-raw.xml'], env=env)
    verify()
    root = ET.parse('acceptance-raw.xml').getroot()
    allowed = ['tests.test_installer.test_failed_pip_install_never_reports_success_or_creates_launcher'] if sys.platform != 'win32' and args.mode == 'full' else []
    try:
        cases = validate(root, expected, allowed)
        valid = code == 0
    except ValueError:
        cases, valid = list(root.iter('testcase')), False
    out = Path('acceptance-public'); out.mkdir(exist_ok=True)
    suite = ET.Element('testsuite', tests=str(len(cases)))
    counts = dict(passed=0, skipped=0, failures=0, errors=0)
    for c in cases:
        item = ET.SubElement(suite, 'testcase', classname=c.get('classname', ''), name=c.get('name', ''), time=c.get('time', '0'))
        status = next((tag for tag in ('error', 'failure', 'skipped') if c.find(tag) is not None), None)
        if status:
            ET.SubElement(item, status, message='Details withheld by privacy projection')
            counts[{'error': 'errors', 'failure': 'failures', 'skipped': 'skipped'}[status]] += 1
        else: counts['passed'] += 1
    for attr in ('failures', 'errors', 'skipped'): suite.set(attr, str(counts[attr]))
    ET.ElementTree(suite).write(out/'junit.xml', encoding='utf-8', xml_declaration=True)
    provenance = dict(candidate_sha=TARGET, candidate_tree=TREE, harness_sha=git('rev-parse', 'HEAD', cwd=HERE), harness_tree=git('rev-parse', 'HEAD^{tree}', cwd=HERE),
                      mode=args.mode, valid=valid, collected=len(expected), counts=counts, required_identities=sorted(expected),
                      junit_sha256=hashlib.sha256((out/'junit.xml').read_bytes()).hexdigest(), platform=sys.platform,
                      native_execution=args.mode=='native', production_contact=False)
    (out/'provenance.json').write_text(json.dumps(provenance, indent=2)+'\n')
    for path in (out/'junit.xml', out/'provenance.json'): safe(path)
    print(f'Exact-source {args.mode}: valid={valid}, counts={counts}')
    return 0 if valid else 1


if __name__ == '__main__': raise SystemExit(main())
