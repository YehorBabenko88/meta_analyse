"""Identity collection ONLY: does not register synthetic-only fixtures.

Full CI must retain real disposable DB and ordinary loopback integration paths.
"""
from scripts.integration_synthetic_boundary import pytest_collection_finish
