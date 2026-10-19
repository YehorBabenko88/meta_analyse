"""Independent audit fixtures: disposable PostgreSQL, offscreen Qt, no public HTTP."""
import os
import uuid
import pytest
import psycopg
from psycopg import sql
from meta_analyse.storage import Store

@pytest.fixture
def audit_store():
    admin = os.environ['META_ANALYSE_TEST_ADMIN_DSN']  # Missing DSN is a failure.
    name = 'independent_v2_' + uuid.uuid4().hex
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    from psycopg.conninfo import make_conninfo
    try:
        yield Store(make_conninfo(admin, dbname=name))
    finally:
        with psycopg.connect(admin, autocommit=True) as conn:
            conn.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))

@pytest.fixture(scope='session')
def audit_app():
    import gc
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QCoreApplication, QEvent
    import shiboken6
    app = QApplication.instance() or QApplication([])
    yield app
    for widget in app.topLevelWidgets():
        widget.close()
        widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
    gc.collect()
    shiboken6.delete(app)

@pytest.fixture(autouse=True)
def no_public_http(monkeypatch):
    import httpx
    original = httpx.AsyncHTTPTransport.handle_async_request
    async def handle(transport, request):
        assert request.url.host in ('127.0.0.1', 'localhost', '::1'), 'public HTTP forbidden in audit'
        return await original(transport, request)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, 'handle_async_request', handle)
