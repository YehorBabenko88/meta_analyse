"""Scoped environment for fake-only PG callers; never used by production."""
import os
import pytest


@pytest.fixture(autouse=True)
def isolated_pg_environment(monkeypatch):
    # Restore every original name/value after each test. Negative tests may
    # explicitly inject forbidden PG* again after this fixture runs.
    for name in tuple(os.environ):
        if name.upper().startswith('PG'):
            monkeypatch.delenv(name)
