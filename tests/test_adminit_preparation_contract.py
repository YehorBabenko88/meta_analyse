"""Offline preparation contracts; never run G0 or any physical/native collector."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def test_native_source_workflow_has_no_fixture_or_database_dependency():
    source=(ROOT/'.github/workflows/windows-native-abi-static.yml').read_text()
    assert 'pytest --noconftest' in source
    assert '-c requirements.lock pytest' in source
    assert 'fail-fast: false' in source
    assert 'python-version: \'3.12\'' in source


def test_native_source_workflow_preserves_public_evidence_boundary():
    source=(ROOT/'.github/workflows/windows-native-abi-static.yml').read_text()
    assert 'python scripts/record_ci_source.py' in source
    assert '--junitxml=native-source-tests.xml' in source
    assert '--junit native-source-tests.xml' in source
    assert 'path: public-evidence/' in source
    assert "if: always() && steps.privacy.outcome == 'success'" in source


def test_g0_requires_explicit_source_and_tree_without_implicit_install_location():
    source=(ROOT/'commissioning/adminit-g0-readonly.ps1').read_text()
    assert source.count('Mandatory=$true')==3
    assert '[string]$ExpectedTree' in source
    assert "rev-parse 'HEAD^{tree}'" in source
    assert '$tree -ne $ExpectedTree' in source
    assert "C:\\MetaAnalyse-Test\\git-pr13" not in source


def test_g0_listener_discovery_is_fail_closed_and_single_snapshot():
    source=(ROOT/'commissioning/adminit-g0-readonly.ps1').read_text()
    assert source.count('Get-NetTCPConnection')==1
    assert 'Get-NetTCPConnection -State Listen -ErrorAction Stop' in source
    assert '$listeners | Where-Object' in source
    assert '-ErrorAction SilentlyContinue' not in source


def test_g0_never_installs_or_bypasses_policy():
    source=(ROOT/'commissioning/adminit-g0-readonly.ps1').read_text()
    for forbidden in ('Add-Type','Set-ExecutionPolicy','ExecutionPolicy Bypass','Start-Service','Set-Service','New-Service','initdb','psql','Set-Acl'):
        assert forbidden not in source
    assert "Authorization='NONE'" in source
    assert 'OBSERVATION_ONLY' in source
