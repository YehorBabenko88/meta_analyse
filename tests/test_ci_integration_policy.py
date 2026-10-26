"""Final integration CI policy: no loss of mandatory tests or false green."""
from pathlib import Path
import ast
import importlib.util
ROOT=Path(__file__).resolve().parents[1]
BRANCH='integration/final-ci-g0-20261026'


def test_full_ci_retains_real_integration_and_explicit_scoped_security_fixture():
    source=(ROOT/'tests/test_final_integration_workflow.py').read_text()
    assert 'from scripts.integration_synthetic_boundary import synthetic_only' in source
    conftest=(ROOT/'tests/conftest.py').read_text()
    assert "os.environ.get('META_ANALYSE_IDENTITY_SYNTHETIC_ONLY')!='1'" in conftest
    assert 'with boundary(' in conftest
    ci=(ROOT/'.github/workflows/ci.yml').read_text()
    assert BRANCH not in ci  # Full jobs are not added to the synthetic exclusion lists.
    assert 'Real Windows read-only native process and SCM boundary' in ci


def test_isolated_pg_cases_partition_to_real_mandatory_job():
    for file in ('ci.yml','commissioning-postgres18.yml'):
        assert '--ignore=tests/test_pg18_disposable_acceptance.py' in (ROOT/'.github/workflows'/file).read_text()
    windows=(ROOT/'scripts/test-windows.ps1').read_text()
    assert '--ignore=tests/test_pg18_disposable_acceptance.py' in windows
    job=(ROOT/'.github/workflows/adminit-final-synthetic.yml').read_text().split('  disposable-postgres18:',1)[1]
    assert BRANCH in job and '--minimum 4' in job
    tree=ast.parse((ROOT/'tests/test_pg18_disposable_acceptance.py').read_text())
    cases=[n.name for n in tree.body if isinstance(n,ast.FunctionDef) and n.name.startswith('test_')]
    assert len(cases)==4 and all(name in job for name in cases)


def test_full_junit_identity_plugin_does_not_activate_synthetic_fixture():
    tree=ast.parse((ROOT/'scripts/ci_identity_manifest.py').read_text())
    imported=[alias.name for node in tree.body if isinstance(node,ast.ImportFrom) for alias in node.names]
    assert imported==['pytest_collection_finish']
    for file in ('ci.yml','commissioning-postgres18.yml'):
        s=(ROOT/'.github/workflows'/file).read_text()
        assert '-p scripts.ci_identity_manifest' in s and 'check_final_integration_junit.py' in s
        assert 'META_ANALYSE_CI_IDENTITY_SCOPE: full' in s


def test_frozen_oracle_never_requires_runtime_fetch():
    assert 'tests/fixtures/pr39_process_identity.py.txt -text' in (ROOT/'.gitattributes').read_text()
    for file in ('adminit-final-synthetic.yml','native-scm-adapter-synthetic.yml'):
        assert 'git fetch' not in (ROOT/'.github/workflows'/file).read_text()


def test_current_mutation_targets_apply_without_operator_removal():
    source=(ROOT/'commissioning/process_identity.py').read_text()
    for name,count in [('check_process_identity_mutations',15),('check_pr20_adversarial_mutations',12)]:
        spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/(name+'.py'))
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        assert len(module.MUTATIONS)==count
        for tag,old,new in module.MUTATIONS:
            if not source.count(old) and tag in module.CURRENT_TARGETS:old,new=module.CURRENT_TARGETS[tag]
            assert source.count(old)==1,(tag,'missing or ambiguous mutation target')
            assert source.replace(old,new)!=source


def test_full_failure_publication_requires_clean_tracked_source():
    for name,count in [('ci.yml',3),('commissioning-postgres18.yml',1)]:
        s=(ROOT/'.github/workflows'/name).read_text()
        assert s.count('id: source_clean')==count
        assert s.count("if: always() && steps.source_clean.outcome == 'success'")==count
        assert s.count('path: public-evidence/')==count
