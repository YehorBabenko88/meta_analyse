"""Final integration workflow contract; synthetic-only, no target probes."""
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
BRANCH='integration/adminit-final-20261025'


def test_final_workflow_checks_exact_candidate_and_synthetic_bounds():
    s=(ROOT/'.github/workflows/adminit-final-synthetic.yml').read_text()
    assert BRANCH in s and 'ubuntu-latest' in s and 'windows-latest' in s
    assert 'github.event.pull_request.head.sha || github.sha' in s
    assert 'pytest --noconftest' in s and '-p scripts.integration_synthetic_boundary' in s
    assert '--minimum 1619' in s and 'scripts/record_ci_source.py' in s
    for forbidden in ('services:','initdb','pg_ctl','run_readonly.py','--enable-public-network','collect-host.ps1','Add-Type'):
        assert forbidden not in s


def test_final_branch_excludes_full_and_storage_jobs():
    for filename,count in [('ci.yml',3),('storage-ingestion.yml',1)]:
        assert (ROOT/'.github/workflows'/filename).read_text().count('"'+BRANCH+'"')==count


def test_final_workflow_only_uploads_projected_evidence():
    s=(ROOT/'.github/workflows/adminit-final-synthetic.yml').read_text()
    assert "if: always() && steps.privacy.outcome == 'success'" in s
    assert 'path: public-evidence/' in s and 'if-no-files-found: error' in s
    assert 'scripts/project_public_ci_evidence.py --validate public-evidence' in s
    assert 'set -euo pipefail' in s


def test_final_active_boundary_denies_live_database():
    import psycopg
    with pytest.raises(AssertionError,match='SYNTHETIC_ONLY_BOUNDARY'):psycopg.connect('synthetic-never-connected')


def test_final_active_boundary_denies_native_child():
    import subprocess
    with pytest.raises(AssertionError,match='SYNTHETIC_ONLY_BOUNDARY'):subprocess.Popen(['powershell.exe','-NoProfile','-Command','exit'])
