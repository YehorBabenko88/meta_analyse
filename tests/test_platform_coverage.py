"""Fixed native policy and opaque same-run receipts; no Windows PASS fabrication."""
import copy
import pytest
from scripts import platform_coverage as p


def ledger(platform='linux',suite='main'):
    native=p.native_identities()
    portable=['case_'+'0'*64,'case_'+'1'*64]
    selected=sorted(native+portable if platform=='windows' and suite=='main' else native if platform=='windows' else portable)
    return dict(schema='meta.platform.ledger.v1',sha='a'*40,tree='b'*40,
        source_files_sha256='c'*64,source_bound=True,platform=platform,suite=suite,
        identities=sorted(native+portable),native_identities=native,selected=selected,
        deferred=sorted(set(native+portable)-set(selected)))


def receipt(platform='linux',suite='main'):
    l=ledger(platform,suite)
    return dict(schema='meta.platform.receipt.v1',ledger=l,run_id='123',attempt='1',
        passed=l['selected'][:],skipped=[],source_authenticity='NOT_EVALUATED',physical='NOT_RUN')


@pytest.mark.parametrize('suite',['main','commissioning'])
def test_real_lane_partition_union_requires_native_windows(suite):
    linux,windows=receipt(suite=suite),receipt('windows',suite)
    assert p.aggregate([linux,windows],sha='a'*40,tree='b'*40,run_id='123',attempt='1',suite=suite)['status']=='PASS_SOURCE_TESTS_ONLY'
    with pytest.raises(ValueError):p.aggregate([linux],sha='a'*40,tree='b'*40,run_id='123',attempt='1',suite=suite)


@pytest.mark.parametrize('fault',['missing','duplicate','extra','wrong_sha','wrong_tree','wrong_run','wrong_attempt','native_skip','native_omitted','wrong_platform','wrong_scope','unbound','foreign_source','failed'])
def test_aggregate_rejects_incomplete_or_substituted_evidence(fault):
    r=[receipt(),receipt('windows')]
    if fault=='missing':r.pop()
    if fault=='duplicate':r.append(copy.deepcopy(r[0]))
    if fault=='extra':r[1]['ledger']['selected'].append('case_'+'f'*64)
    if fault=='wrong_sha':r[1]['ledger']['sha']='d'*40
    if fault=='wrong_tree':r[1]['ledger']['tree']='d'*40
    if fault=='wrong_run':r[1]['run_id']='124'
    if fault=='wrong_attempt':r[1]['attempt']='2'
    if fault=='native_skip':
        case=r[1]['ledger']['native_identities'][0];r[1]['passed'].remove(case);r[1]['skipped']=[case]
    if fault=='native_omitted':r[1]['passed']=r[1]['passed'][1:]
    if fault=='wrong_platform':r[1]['ledger']['platform']='linux'
    if fault=='wrong_scope':r[1]['ledger']['suite']='commissioning'
    if fault=='unbound':r[1]['ledger']['source_bound']=False
    if fault=='foreign_source':r[1]['ledger']['source_files_sha256']='d'*64
    if fault=='failed':r[1]['passed']=[]
    with pytest.raises(ValueError):p.aggregate(r,sha='a'*40,tree='b'*40,run_id='123',attempt='1',suite='main')


def test_native_catalog_refuses_new_function_variant_missing_and_duplicate():
    rows=[('tests/test_s1_supervisor.py', 'test_supervisor_bounded_projection',v) for v in p.NATIVE_VARIANTS]
    assert len(p.classify_native(rows))==21
    for bad in [rows[:-1],rows+rows[:1],rows+[('tests/test_s1_supervisor.py','test_other',None)],rows+[('tests/test_s1_supervisor.py','test_supervisor_bounded_projection','new_case')]]:
        with pytest.raises(ValueError):p.classify_native(bad)


def test_ledger_refuses_fake_native_identity_or_duplicate_catalog():
    for key in ('identities','native_identities','selected','deferred'):
        l=ledger();l[key]=l[key]+[l['identities'][0]]
        with pytest.raises(ValueError):p.validate_ledger(l)


def test_full_schema_one_identity_manifest_remains_unchanged():
    from scripts.check_final_integration_junit import check
    raw=b'<testsuite><testcase classname="tests.test_example" name="test_one"/></testsuite>'
    manifest=dict(schema=1,sha='a'*40,tree='b'*40,identities=[p.identity('tests.test_example','test_one')],allowed_skips=[])
    assert check(raw,manifest,'a'*40,'b'*40)==1


def test_receipt_requires_actual_junit_pass_for_every_native_case():
    l=ledger('windows','commissioning')
    raw=('<testsuite>'+''.join('<testcase classname="tests.test_s1_supervisor" name="test_supervisor_bounded_projection['+v+']"/>' for v in p.NATIVE_VARIANTS)+'</testsuite>').encode()
    manifest=dict(schema=1,sha=l['sha'],tree=l['tree'],identities=l['selected'],allowed_skips=[])
    result=p.make_receipt(raw,manifest,l,run_id='123',attempt='1')
    assert result['passed']==p.native_identities() and result['skipped']==[]
    for status in ('<skipped/>','<failure/>','<error/>'):
        corrupted=raw.replace(b'/>',('>'+status+'</testcase>').encode(),1)
        with pytest.raises(ValueError):p.make_receipt(corrupted,manifest,l,run_id='123',attempt='1')


def test_public_platform_staging_refuses_raw_metadata_and_extra_files(tmp_path):
    stage=tmp_path/'public-platform'
    p.write_receipt(stage,receipt())
    assert p.validate_directory(stage)['ledger']['platform']=='linux'
    (stage/'raw.log').write_text('PRIVATE_PATH_HOST')
    with pytest.raises(ValueError):p.validate_directory(stage)
    r=receipt();r['raw']='PRIVATE_PATH_HOST'
    with pytest.raises(ValueError):p.write_receipt(tmp_path/'other',r)


def test_new_platform_jobs_cannot_qualify_without_both_real_lanes():
    from pathlib import Path
    root=Path(__file__).parents[1]
    ci=(root/'.github/workflows/ci.yml').read_text()
    commissioning=(root/'.github/workflows/commissioning-postgres18.yml').read_text()
    assert 'needs: [linux, windows]' in ci
    assert 'needs: [postgres18-linux, native-windows]' in commissioning
    for text,suite in ((ci,'main'),(commissioning,'commissioning')):
        assert '-p scripts.ci_identity_manifest -p scripts.ci_platform_coverage' in text
        assert 'python scripts/platform_coverage.py aggregate --linux platform-linux --windows platform-windows --suite '+suite in text
        assert "os.environ['LINUX_RESULT']=='success' and os.environ['WINDOWS_RESULT']=='success'" in text
        assert 'actions/download-artifact@v4' in text
        assert "if: always() && steps.platform_receipt.outcome == 'success'" in text
        assert '--ignore=tests/test_s1_supervisor.py' not in text
    windows=(root/'scripts/test-windows.ps1').read_text()
    assert '-p scripts.ci_identity_manifest -p scripts.ci_platform_coverage' in windows
    assert "META_ANALYSE_PLATFORM_SUITE='main'" in windows
    native=(root/'tests/test_s1_supervisor.py').read_text()
    assert "assert os.name == 'nt'" in native and 'skipif' not in native


def test_collection_policy_forbids_unreviewed_omission_or_partial_selection():
    from types import SimpleNamespace
    from scripts import ci_platform_coverage as plugin
    from unittest.mock import patch
    # Refuse before any collection can be labelled complete or any ledger written.
    base=dict(keyword='',markexpr='',deselect=[],ignore=['tests/test_pg18_disposable_acceptance.py'],ignore_glob=[],pyargs=False)
    options=[dict(base,keyword='portable'),dict(base,markexpr='not native'),dict(base,deselect=['tests/test_x.py']),dict(base,ignore=['tests/test_s1_supervisor.py']),dict(base,ignore_glob=['*native*']),dict(base,pyargs=True)]
    with patch.dict('os.environ',{'META_ANALYSE_PLATFORM_LEDGER':'must-not-write','META_ANALYSE_CI_IDENTITY_SCOPE':'full'}):
        for option in options:
            config=SimpleNamespace(option=SimpleNamespace(**option),args=['tests'])
            with pytest.raises(ValueError):plugin.pytest_collection_modifyitems(None,config,[])
        config=SimpleNamespace(option=SimpleNamespace(**base),args=['tests/test_platform_coverage.py'])
        with pytest.raises(ValueError):plugin.pytest_collection_modifyitems(None,config,[])
