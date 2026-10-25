"""Tripwires for the reviewed synthetic suite; not process/OS containment."""
from pathlib import Path
import subprocess
import socket
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'commissioning'))

@pytest.fixture(autouse=True)
def synthetic_only(monkeypatch):
    import psycopg
    import host_identity
    def blocked(*args,**kwargs):raise AssertionError('SYNTHETIC_ONLY_BOUNDARY')
    for name in ('dpapi','is_elevated','system_directory'):monkeypatch.setattr(host_identity,name,blocked)
    monkeypatch.setattr(psycopg,'connect',blocked)
    original_popen=subprocess.Popen
    def popen(command,*args,**kwargs):
        executable=Path(command[0]).name.lower() if isinstance(command,(list,tuple)) and command else ''
        if executable not in ('git','git.exe',Path(sys.executable).name.lower()):blocked()
        return original_popen(command,*args,**kwargs)
    monkeypatch.setattr(subprocess,'Popen',popen)
    original_connect=socket.socket.connect
    def connect(sock,address):
        if not isinstance(address,tuple) or address[0] not in ('127.0.0.1','::1','localhost'):blocked()
        return original_connect(sock,address)
    monkeypatch.setattr(socket.socket,'connect',connect)

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
    def git(arg):return subprocess.check_output(['git','rev-parse',arg],text=True).strip()
    manifest=dict(schema=1,sha=git('HEAD'),tree=git('HEAD^{tree}'),identities=sorted(rows),allowed_skips=sorted(skips))
    Path(output).write_text(json.dumps(manifest,sort_keys=True)+'\n',encoding='utf-8')
