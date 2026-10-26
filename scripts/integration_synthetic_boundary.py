"""Tripwires for the reviewed synthetic suite; not process/OS containment."""
from pathlib import Path
import subprocess
import socket
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'commissioning'))

@pytest.fixture(autouse=True)
def synthetic_only(monkeypatch,request):
    from scripts.synthetic_boundary import boundary
    with boundary(monkeypatch,root=request.node.name.split('[',1)[0]):
        yield


def pytest_collection_finish(session):
    """Emit source-collected opaque identities before any fixture/test executes."""
    import hashlib,json,os
    from _pytest.junitxml import mangle_test_address
    output=os.environ.get('META_ANALYSE_SYNTHETIC_IDENTITIES')
    if not output:return
    rows=[];skips=[]
    for item in session.items:
        names=mangle_test_address(item.nodeid)
        pair=['.'.join(names[:-1]),item.name]
        digest=hashlib.sha256((json.dumps(pair,sort_keys=True,separators=(',',':'))+'\n').encode()).hexdigest()
        public='case_'+digest;rows.append(public)
        if item.name in ('test_symlink_is_rejected','test_existing_private_survives_static_alias_spellings[symlink]'):skips.append(public)
        if os.environ.get('META_ANALYSE_CI_IDENTITY_SCOPE')=='full' and sys.platform!='win32' and item.name=='test_failed_pip_install_never_reports_success_or_creates_launcher':skips.append(public)
    def git(arg):return subprocess.check_output(['git','rev-parse',arg],text=True).strip()
    manifest=dict(schema=1,sha=git('HEAD'),tree=git('HEAD^{tree}'),identities=sorted(rows),allowed_skips=sorted(skips))
    Path(output).write_text(json.dumps(manifest,sort_keys=True)+'\n',encoding='utf-8')


@pytest.fixture(scope='session')
def app():
    """Offscreen-only Qt fixture; no physical window, user settings or database."""
    import os,gc
    if os.environ.get('QT_QPA_PLATFORM')!='offscreen':pytest.fail('OFFSCREEN_QT_REQUIRED')
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QCoreApplication,QEvent
    application=QApplication.instance() or QApplication([])
    yield application
    for widget in application.topLevelWidgets():
        widget.close();widget.deleteLater()
    QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
    application.processEvents();gc.collect()
    import shiboken6
    shiboken6.delete(application)
