"""Scoped test tripwires, NOT an OS sandbox or protection from malicious Python.

Audit hooks cover cached native socket/subprocess aliases while active. Real PG
integration tests don't enter this scope. Reviewed Python helpers are bootstrapped
in a fresh guarded interpreter; arbitrary child commands are never implicit.
"""
from contextlib import contextmanager
from pathlib import Path
import os
import json
import shutil
import socket
import subprocess
import sys
import threading
import builtins

ROOT=Path(__file__).resolve().parents[1]
ACTIVE=None
PERMIT=threading.local()
LOOPBACK={'127.0.0.1','::1','localhost'}
HELPERS={
 'test_ci_records_pull_request_head_instead_of_synthetic_merge',
 'test_artifact_gate_rejects_raw_private_payload_without_echo',
 'test_abrupt_synthetic_process_exit_never_publishes_pass',
 'test_stage_source_checks_survive_optimized_python',
 'test_enrollment_binding_cannot_be_disabled_by_python_optimization',
 'test_disposable_fixture_refuses_production_port_under_optimized_python',
 'test_cli_refusal_does_not_echo_os_error_path',
 'test_approved_python_child_cannot_connect_or_spawn',
}


def denied(*args,**kwargs):raise AssertionError('SYNTHETIC_ONLY_BOUNDARY')


async def async_denied(*args,**kwargs):raise AssertionError('SYNTHETIC_ONLY_BOUNDARY')


def audit(event,args):
    policy=ACTIVE
    if policy is None:return
    if event in ('subprocess.Popen','os.system','os.exec','os.posix_spawn','os.fork','os.forkpty','os.spawn'):
        if not getattr(PERMIT,'depth',0):denied()
    elif event=='socket.bind':
        address=args[1]
        if not isinstance(address,tuple) or address[0] not in ('127.0.0.1','::1'):denied()
    elif event in ('socket.connect','socket.sendto','socket.sendmsg'):
        address=args[-1]
        if not (policy['loopback'] or getattr(PERMIT,'socketpair',False)) or not isinstance(address,tuple) or address[0] not in LOOPBACK:denied()
    elif event in ('socket.getaddrinfo','socket.gethostbyname','socket.gethostbyaddr','socket.getnameinfo'):
        address=args[0]
        host=address[0] if isinstance(address,tuple) else address
        if not (policy['loopback'] or getattr(PERMIT,'socketpair',False)) or host not in LOOPBACK:denied()


sys.addaudithook(audit)


def git_command(command):
    executable=command[0]
    trusted=shutil.which('git')
    if not trusted:return None
    if executable not in ('git','git.exe') and Path(executable).resolve()!=Path(trusted).resolve():return None
    tokens=command[1:];index=0
    if tokens[:1]==['-C']:index=2
    if index>=len(tokens):denied()
    verb=tokens[index]
    if verb not in ('rev-parse','status','show','cat-file','init','config','add','commit','ls-files','diff','checkout'):denied()
    if verb=='checkout' and tokens[index+1:index+2]!=['--']:denied()
    if verb=='config' and (index+1>=len(tokens) or tokens[index+1] not in ('user.name','user.email')):denied()
    if any(t.startswith(('--ext-diff','--textconv','--exec-path','--upload-pack','--receive-pack','--config-env')) for t in tokens):denied()
    if verb in ('show','diff'):tokens=tokens[:index+1]+['--no-ext-diff','--no-textconv']+tokens[index+1:]
    # Disable executable config hooks/filters inherited from machine/user env.
    return [trusted,'--no-pager','-c','core.hooksPath='+os.devnull,'-c','core.fsmonitor=false',
            '-c','commit.gpgsign=false','-c','protocol.allow=never',*tokens]


@contextmanager
def boundary(monkeypatch,root='',child=False):
    global ACTIVE
    import psycopg,httpx
    sys.path.insert(0,str(ROOT/'commissioning')) if str(ROOT/'commissioning') not in sys.path else None
    previous=ACTIVE
    ACTIVE={'root':root,'loopback':root=='test_close_drains_real_loopback_http_and_refuses_late_requests'}
    try:
        def guard_host(module):
            for name in ('dpapi','is_elevated','system_directory'):monkeypatch.setattr(module,name,denied)
        if child:
            original_import=builtins.__import__
            def importing(*args,**kwargs):
                value=original_import(*args,**kwargs)
                if getattr(value,'__name__','')=='host_identity' and not getattr(value,'_synthetic_guarded',False):
                    guard_host(value);value._synthetic_guarded=True
                return value
            monkeypatch.setattr(builtins,'__import__',importing)
        else:
            import host_identity
            guard_host(host_identity)
        # Aliases imported before the fixture retain the function object: patch
        # that object's code, not just the module attribute. Reversible per test.
        monkeypatch.setattr(psycopg.Connection.connect.__func__,'__code__',denied.__code__)
        monkeypatch.setattr(psycopg.AsyncConnection.connect.__func__,'__code__',async_denied.__code__)
        monkeypatch.setattr(psycopg,'connect',denied)
        original_pair=socket.socketpair
        def socketpair(*args,**kwargs):
            previous_pair=getattr(PERMIT,'socketpair',False)
            PERMIT.socketpair=True
            try:return original_pair(*args,**kwargs)
            finally:PERMIT.socketpair=previous_pair
        monkeypatch.setattr(socket,'socketpair',socketpair)
        original_http=httpx.AsyncHTTPTransport.handle_async_request
        async def http(transport,request):
            if not ACTIVE or not ACTIVE['loopback'] or request.url.host not in LOOPBACK:denied()
            return await original_http(transport,request)
        monkeypatch.setattr(httpx.AsyncHTTPTransport,'handle_async_request',http)
        original_init=subprocess.Popen.__init__
        def init(owned,args,*positional,**kwargs):
            owned._child_created=False
            if kwargs.get('shell') or kwargs.get('executable') or kwargs.get('preexec_fn'):denied()
            if not isinstance(args,(list,tuple)) or not args:denied()
            command=[os.fspath(x) for x in args]
            environment=dict(kwargs['env'] if kwargs.get('env') is not None else os.environ)
            git=git_command(command)
            if git is not None:
                command=git
                for key in tuple(environment):
                    if key.startswith('GIT_'):environment.pop(key)
                environment.update(GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL=os.devnull,
                                   GIT_CONFIG_COUNT='0',GIT_TERMINAL_PROMPT='0')
            elif Path(command[0]).resolve()==Path(sys.executable).resolve() and not child and root in HELPERS:
                flags=[];original=command[1:]
                while original and original[0] in ('-O','-B'):
                    flags.append(original.pop(0))
                if not original or original[0].startswith('-') and original[0]!='-c':denied()
                policy=dict(argv=original,paths=[str(ROOT),str(ROOT/'src'),str(ROOT/'tests'),
                    str(ROOT/'commissioning'),*[x for x in sys.path if x and Path(x).is_absolute()]],
                    cwd=str(kwargs['cwd']) if kwargs.get('cwd') else None)
                command=[sys.executable,*flags,'-I','-S','-B',str(ROOT/'scripts/synthetic_child.py'),json.dumps(policy)]
            else:denied()
            kwargs['env']=environment
            PERMIT.depth=getattr(PERMIT,'depth',0)+1
            try:return original_init(owned,command,*positional,**kwargs)
            finally:PERMIT.depth-=1
        monkeypatch.setattr(subprocess.Popen,'__init__',init)
        yield
    finally:ACTIVE=previous
