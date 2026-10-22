"""Runtime tripwires for synthetic jobs; candidate files remain unchanged."""
import pytest


@pytest.fixture(autouse=True)
def no_platform_collection(monkeypatch):
    import sys
    from pathlib import Path
    import subprocess
    import psycopg
    sys.path.insert(0, str(Path.cwd()/'commissioning'))
    import host_identity as h
    def forbidden(*args, **kwargs):
        raise AssertionError('SYNTHETIC_NATIVE_DPAPI_DATABASE_FORBIDDEN')
    monkeypatch.setattr(h, 'dpapi', forbidden)
    monkeypatch.setattr(psycopg, 'connect', forbidden)
    original = subprocess.Popen
    def popen(command, *args, **kwargs):
        values = command if isinstance(command, (list, tuple)) else [command]
        if any('powershell' in str(v).lower() or 'pwsh' in str(v).lower() or 'add-type' in str(v).lower() for v in values): forbidden()
        return original(command, *args, **kwargs)
    monkeypatch.setattr(subprocess, 'Popen', popen)
