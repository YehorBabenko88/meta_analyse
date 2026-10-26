"""Final integration workflow contract; synthetic-only, no target probes."""
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
BRANCH='integration/adminit-security-readiness-20261025'


def test_final_workflow_checks_exact_candidate_and_synthetic_bounds():
    s=(ROOT/'.github/workflows/adminit-final-synthetic.yml').read_text()
    assert BRANCH in s and 'ubuntu-latest' in s and 'windows-latest' in s
    assert 'fix/pr51-hosted-isolation-20261026' in s
    assert "if: runner.os == 'Linux'" in s and 'libegl1' in s
    assert s.index('libegl1') < s.index('pytest --noconftest')
    assert 'github.event.pull_request.head.sha || github.sha' in s
    assert 'pytest --noconftest' in s and '-p scripts.integration_synthetic_boundary' in s
    assert '--minimum 1744' in s and 'scripts/record_ci_source.py' in s
    synthetic=s.split('  disposable-postgres18:',1)[0]
    for forbidden in ('services:','initdb','pg_ctl','run_readonly.py','--enable-public-network','collect-host.ps1','Add-Type'):
        assert forbidden not in synthetic


def test_final_branch_excludes_full_and_storage_jobs():
    for filename,count in [('ci.yml',3),('storage-ingestion.yml',1)]:
        assert (ROOT/'.github/workflows'/filename).read_text().count('"'+BRANCH+'"')==count


def test_final_workflow_only_uploads_projected_evidence():
    s=(ROOT/'.github/workflows/adminit-final-synthetic.yml').read_text()
    assert "if: always() && steps.privacy.outcome == 'success'" in s
    assert 'path: public-evidence/' in s and 'if-no-files-found: error' in s
    assert 'scripts/project_public_ci_evidence.py --validate public-evidence' in s
    assert 'set -euo pipefail' in s
    assert s.count('id: source_clean')==2
    assert s.count('git diff --exit-code HEAD')==2
    assert s.count("if: always() && steps.source_clean.outcome == 'success'")==2


def test_final_active_boundary_denies_live_database():
    import psycopg
    with pytest.raises(AssertionError,match='SYNTHETIC_ONLY_BOUNDARY'):psycopg.connect('synthetic-never-connected')


def test_final_active_boundary_denies_native_child():
    import subprocess
    with pytest.raises(AssertionError,match='SYNTHETIC_ONLY_BOUNDARY'):subprocess.Popen(['powershell.exe','-NoProfile','-Command','exit'])


def test_disposable_pg_is_separate_explicit_hosted_linux_after_synthetic():
    s=(ROOT/'.github/workflows/adminit-final-synthetic.yml').read_text()
    job=s.split('  disposable-postgres18:',1)[1]
    assert 'needs: synthetic' in job and 'runs-on: ubuntu-latest' in job
    assert "META_ANALYSE_DISPOSABLE_PG18: '1'" in job
    assert '--minimum 4' in job and 'run_pg18_disposable_ci.py' in job
    assert '-p scripts.integration_synthetic_boundary' not in job
    assert 'GITHUB_ACTIONS' in (ROOT/'scripts/run_pg18_disposable_ci.py').read_text()

@pytest.mark.asyncio
async def test_final_http_boundary_rejects_external_request_before_dns(monkeypatch):
    import socket,httpx
    monkeypatch.setattr(socket,'getaddrinfo',lambda *a,**k:(_ for _ in ()).throw(AssertionError('RESOLUTION_ATTEMPTED')))
    async with httpx.AsyncClient(trust_env=False) as client:
        with pytest.raises(AssertionError,match='SYNTHETIC_ONLY_BOUNDARY'):
            await client.get('https://unit.invalid/')
