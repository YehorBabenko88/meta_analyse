"""Policy truth table for real push/PR contexts, with no runner allocation."""
import json
from pathlib import Path
import re
import pytest
ROOT=Path(__file__).resolve().parents[1]
LEGACY=['parallel/adminit-kernel-identity-evidence','parallel/adminit-identity-integration-20261021',
    'parallel/adminit-identity-acceptance-fix-20261022','parallel/adminit-pr20-security-fix-20261022',
    'parallel/adminit-pr21-evidence-schema-20261022','parallel/adminit-pr22-boundary-review-20261022',
    'parallel/adminit-pr23-output-transaction-20261023']
NEW=['maintenance/repository-ci-hygiene-20261023','maintenance/actions-audit-hardening-20261023']

def policies():
    ci=(ROOT/'.github/workflows/ci.yml').read_text()
    storage=(ROOT/'.github/workflows/storage-ingestion.yml').read_text()
    result=re.findall(r"^    if: \$\{\{ !contains\(fromJSON\('([^']+)'\), github.head_ref \|\| github.ref_name\) \}\}$",ci+'\n'+storage,re.M)
    assert len(result)==4 and len(set(result))==1
    return json.loads(result[0])

@pytest.mark.parametrize('event',['push','pull_request'])
@pytest.mark.parametrize('branch',LEGACY+NEW+['main','feature/synthetic-safe-control','parallel/storage-ingestion','audit/control'])
def test_policy_preserves_old_exclusions_and_blocks_maintenance(event,branch):
    blocked=policies()
    ref,head=(branch,'') if event=='push' else ('999/merge',branch)
    old=all(ref!=b and head!=b for b in LEGACY)
    actual=(head or ref) not in blocked
    assert actual==(old and branch not in NEW)

def test_synthetic_workflow_scope_and_permissions():
    text=(ROOT/'.github/workflows/ci-audit-synthetic.yml').read_text()
    assert 'contents: read' in text and 'max-parallel: 2' in text and 'fail-fast: false' in text
    assert '--noconftest' in text and 'pytest hypothesis\n' in text
    assert 'if-no-files-found: error' in text
    for forbidden in ('check-process-probe','prepare-ci-postgres','services:','workflow_dispatch:','self-hosted','pull_request_target:'):
        assert forbidden not in text

def test_property_test_dependency_is_in_standard_test_extra():
    import tomllib
    project=tomllib.loads((ROOT/'pyproject.toml').read_text())
    pin='hypothesis==6.170.6'
    assert pin in project['project']['optional-dependencies']['test']
    lock=(ROOT/'requirements.lock').read_text()
    assert pin in lock and 'sortedcontainers==2.4.0' in lock
