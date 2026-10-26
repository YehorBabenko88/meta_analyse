"""Adversarial guards. All RED probes are synthetic/owned loopback only."""
import asyncio
import gc
import os
import socket
import subprocess
import sys
import psycopg
import pytest
from scripts.integration_synthetic_boundary import synthetic_only

CACHED_CONNECT=psycopg.connect
CACHED_CLASS_CONNECT=psycopg.Connection.connect
CACHED_ASYNC=psycopg.AsyncConnection.connect
CACHED_POPEN=subprocess.Popen
CACHED_SOCKET_CONNECT=socket.socket.connect
CACHED_DNS=socket.getaddrinfo

@pytest.mark.parametrize('call',[CACHED_CONNECT,CACHED_CLASS_CONNECT],ids=['cached-module','cached-class'])
def test_cached_psycopg_alias_denied_before_parsing_or_connection(call):
    with pytest.raises(AssertionError,match='^SYNTHETIC_ONLY_BOUNDARY$'):call('synthetic-never-connected')

@pytest.mark.asyncio
async def test_cached_async_psycopg_denied_before_loop_or_dsn():
    with pytest.raises(AssertionError,match='^SYNTHETIC_ONLY_BOUNDARY$'):await CACHED_ASYNC('synthetic-never-connected')


def test_cached_native_socket_method_is_denied_on_owned_loopback():
    with socket.socket() as server,socket.socket() as client:
        server.bind(('127.0.0.1',0));server.listen(1)
        with pytest.raises(AssertionError,match='^SYNTHETIC_ONLY_BOUNDARY$'):
            CACHED_SOCKET_CONNECT(client,server.getsockname())


def test_cached_dns_numeric_address_is_denied_without_resolver():
    with pytest.raises(AssertionError,match='^SYNTHETIC_ONLY_BOUNDARY$'):
        CACHED_DNS('127.0.0.1',9,flags=socket.AI_NUMERICHOST)

@pytest.mark.parametrize('event,args',[
 ('socket.getaddrinfo',('unit.invalid',443,0,0,0)),
 ('socket.connect',(None,('192.0.2.1',9))),
 ('socket.sendto',(None,('192.0.2.1',9))),
 ('os.system',(b'echo synthetic',)),
 ('os.posix_spawn',('synthetic',[],{})),
 ('subprocess.Popen',('synthetic',['synthetic'],None,None)),
])
def test_native_audit_events_are_denied_before_action(event,args):
    # Direct audit emission, not an actual OS operation/network request.
    with pytest.raises(AssertionError,match='^SYNTHETIC_ONLY_BOUNDARY$'):sys.audit(event,*args)

@pytest.mark.parametrize('cached',[False,True])
def test_python_child_not_implicitly_allowed(cached):
    with pytest.raises(AssertionError,match='^SYNTHETIC_ONLY_BOUNDARY$'):
        if cached:
            with CACHED_POPEN([sys.executable,'-c','raise SystemExit(0)']) as child:child.wait()
        else:subprocess.run([sys.executable,'-c','raise SystemExit(0)'],check=True)
    gc.collect()  # Blocked construction must not generate unraisable ResourceWarning.


def test_approved_python_child_cannot_connect_or_spawn():
    code="""import sys,subprocess,psycopg,json
results=[]
for call in (lambda:psycopg.connect('synthetic-never-connected'),
             lambda:sys.audit('socket.connect',None,('192.0.2.1',9)),
             lambda:subprocess.run([sys.executable,'-c','raise SystemExit(0)'])):
    try:call()
    except AssertionError as e:results.append(str(e)=='SYNTHETIC_ONLY_BOUNDARY')
    except Exception:results.append(False)
    else:results.append(False)
print(json.dumps(results))
"""
    child=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=20)
    assert child.returncode==0 and child.stdout.strip()=='[true, true, true]'
@pytest.mark.parametrize('kind',['connect_ex','create_connection','gethostbyname','sendto'])
def test_additional_cached_socket_entrypoints_are_denied(kind):
    with socket.socket() as server:
        server.bind(('127.0.0.1',0));server.listen(1);address=server.getsockname()
        with pytest.raises(AssertionError,match='^SYNTHETIC_ONLY_BOUNDARY$'):
            if kind=='connect_ex':
                with socket.socket() as client:socket.socket.connect_ex(client,address)
            elif kind=='create_connection':socket.create_connection(address)
            elif kind=='gethostbyname':socket.gethostbyname('127.0.0.1')
            else:
                with socket.socket(type=socket.SOCK_DGRAM) as client:client.sendto(b'synthetic',address)
