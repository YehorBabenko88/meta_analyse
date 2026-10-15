import os
import uuid
import pytest
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from meta_analyse.storage import Store

@pytest.fixture
def postgres_store():
    admin_dsn = os.environ.get('META_ANALYSE_TEST_ADMIN_DSN')
    if not admin_dsn:
        pytest.skip('Set META_ANALYSE_TEST_ADMIN_DSN for disposable PostgreSQL integration')
    name = 'meta_audit_' + uuid.uuid4().hex
    role = name + '_owner'
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        conn.execute(sql.SQL('CREATE ROLE {} LOGIN').format(sql.Identifier(role)))
        conn.execute(sql.SQL('CREATE DATABASE {} OWNER {}').format(sql.Identifier(name), sql.Identifier(role)))
    store = Store(make_conninfo(admin_dsn, dbname=name, user=role))
    try:
        with store.connect() as conn:
            conn.execute('CREATE TABLE public.audit_sentinel (value TEXT)')
            conn.execute("INSERT INTO public.audit_sentinel VALUES ('preserve')")
        yield store
        with store.connect() as conn:
            assert conn.execute('SELECT value FROM public.audit_sentinel').fetchall() == [('preserve',)]
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as conn:
            conn.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
            conn.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(role)))


@pytest.fixture(scope='session')
def app():
    # Keep one application alive until every Qt test and all worker threads end.
    # Delete widgets on the Qt thread before interpreter shutdown; allowing Python
    # cycle collection to do this after QApplication teardown aborts on Windows.
    import gc
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication
    application = QApplication.instance() or QApplication([])
    yield application
    for widget in application.topLevelWidgets():
        widget.close()
        widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    application.processEvents()
    gc.collect()
    import shiboken6
    shiboken6.delete(application)
