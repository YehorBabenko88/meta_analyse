"""Private, stateless loopback transport for the existing causal history adapter.

No GUI, exchange client, task scheduler, persistent store or execution authority.
A clean exact raw source capsule is required before binding any listener.
"""
from __future__ import annotations

import argparse
import configparser
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import re
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import threading

MAX_BODY=8*1024*1024
MAX_RESPONSE=16*1024*1024
IO_DEADLINE=3.0
ROOT=Path(__file__).absolute().parents[2]


def need(ok):
    if not ok:raise ValueError('HEADLESS_SERVICE_REJECTED')


def regular(path,*,unique=True):
    """Reject existing linked/reparse ancestors; no native namespace race claim."""
    path=Path(path)
    need(path.is_absolute() and not str(path).replace('\\','/').startswith('//'))
    for ancestor in reversed((path,*path.parents)):
        info=ancestor.lstat()
        need(not stat.S_ISLNK(info.st_mode) and not getattr(info,'st_file_attributes',0)&1024)
    info=path.lstat()
    need(stat.S_ISREG(info.st_mode) and (not unique or info.st_nlink==1))
    return path


def directory(path):
    path=Path(path)
    need(path.is_absolute() and not str(path).replace('\\','/').startswith('//'))
    for ancestor in reversed((path,*path.parents)):
        info=ancestor.lstat()
        need(not stat.S_ISLNK(info.st_mode) and not getattr(info,'st_file_attributes',0)&1024)
    need(stat.S_ISDIR(info.st_mode))
    return path


@dataclass(frozen=True)
class Identity:
    version:str
    release_id:str
    token:str
    source_commit:str
    git_executable:Path
    git_sha256:str

    @classmethod
    def from_environment(cls,env):
        need(env.get('UNIFIED_MODULE_ID')=='meta_analyse')
        values=[env.get(k,'') for k in ('UNIFIED_MODULE_VERSION','UNIFIED_RELEASE_ID','UNIFIED_INSTANCE_TOKEN','UNIFIED_SOURCE_COMMIT','UNIFIED_GIT_EXECUTABLE','UNIFIED_GIT_SHA256')]
        version,release,token,commit,exe,digest=values
        need(len(version)<=64 and re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?',version) is not None)
        need(re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}',release) is not None)
        for value,size in ((token,64),(commit,40),(digest,64)):
            need(re.fullmatch('[0-9a-f]{'+str(size)+'}',value) is not None)
        return cls(version,release,token,commit,regular(Path(exe),unique=False),digest)

    def health(self):
        return dict(module_id='meta_analyse',version=self.version,release_id=self.release_id,instance_token=self.token,ready=True)


class SourceVerifier:
    """Bounded pinned Git object/raw-byte comparison, never filters or status."""
    def __init__(self,root,identity):
        self.root=Path(root).absolute();self.identity=identity;self.snapshot=None

    def git(self,*args,input=b'',limit=40*1024*1024):
        executable=regular(self.identity.git_executable,unique=False)
        need(executable.stat().st_size<=64*1024*1024)
        need(hashlib.sha256(executable.read_bytes()).hexdigest()==self.identity.git_sha256)
        env={k:v for k,v in os.environ.items() if not k.upper().startswith('GIT_')}
        env.update(GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_SYSTEM=os.devnull,GIT_CONFIG_GLOBAL=os.devnull,GIT_ATTR_NOSYSTEM='1',GIT_NO_REPLACE_OBJECTS='1',GIT_NO_LAZY_FETCH='1',GIT_TERMINAL_PROMPT='0')
        with tempfile.TemporaryFile() as stdin:
            stdin.write(input);stdin.seek(0)
            process=subprocess.Popen([str(self.identity.git_executable),'--no-replace-objects','--no-optional-locks','-c','core.fsmonitor=false','-C',str(self.root),*args],stdin=stdin,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,env=env)
            timer=threading.Timer(5,process.kill);timer.daemon=True;timer.start()
            try:
                raw=process.stdout.read(limit+1)
                if len(raw)>limit:process.kill()
                process.wait(timeout=1)
                need(process.returncode==0 and len(raw)<=limit)
                return raw
            finally:
                timer.cancel()
                if process.poll() is None:process.kill()
                process.wait();process.stdout.close();timer.join()

    def verify(self):
        need(not any(k.upper() in {'GIT_DIR','GIT_WORK_TREE','GIT_COMMON_DIR','GIT_OBJECT_DIRECTORY','GIT_ALTERNATE_OBJECT_DIRECTORIES','GIT_CONFIG_PARAMETERS','GIT_CONFIG_COUNT','GIT_INDEX_FILE','GIT_REPLACE_REF_BASE'} for k in os.environ))
        directory(self.root)
        gitdir=directory(self.root/'.git')
        # Reject links inside Git metadata before asking Git to inspect refs or
        # objects. No alternate object/index/config path may escape this root.
        count=0
        for folder,dirs,names in os.walk(gitdir,followlinks=False):
            for name in dirs+names:
                info=(Path(folder)/name).lstat();count+=1
                need(not name.endswith('.promisor'))
                need(count<=20000 and not stat.S_ISLNK(info.st_mode)
                     and not getattr(info,'st_file_attributes',0)&1024)
                need(stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode))
        config_path=regular(gitdir/'config');need(config_path.stat().st_size<65536)
        with config_path.open('rb') as stream:config_raw=stream.read(65536)
        need(len(config_raw)<65536)
        for relative in ('commondir','objects/info/alternates','objects/info/http-alternates','info/attributes'):
            need(not (gitdir/relative).exists())
        config=configparser.RawConfigParser(strict=False);config.read_string(config_raw.decode('utf-8'))
        for section in config.sections():
            name=section.casefold();need(not name.startswith(('include','filter')))
            if name=='core':
                need('worktree' not in config[section])
                for key in ('attributesfile','hookspath'):
                    if key in config[section]:need(config[section][key]==os.devnull)
                if 'fsmonitor' in config[section]:need(config[section]['fsmonitor'].casefold()=='false')
            if name=='extensions':need('worktreeconfig' not in config[section] and 'partialclone' not in config[section])
            if name.startswith('remote '):need('promisor' not in config[section])
        need(not self.git('for-each-ref','--format=%(refname)','refs/replace',limit=65536).strip())
        head=self.git('rev-parse','HEAD',limit=128).decode().strip();need(head==self.identity.source_commit)
        need(Path(self.git('rev-parse','--show-toplevel',limit=4096).decode().strip()).resolve()==self.root.resolve())
        tree=self.git('ls-tree','-rz','--full-tree','HEAD',limit=2*1024*1024)
        files={}
        expected_index=[]
        for row in tree.split(b'\0'):
            if not row:continue
            meta,raw_path=row.split(b'\t',1);mode,kind,oid=meta.split();name=raw_path.decode('utf-8')
            need(mode in (b'100644',b'100755') and kind==b'blob')
            need(not name.startswith('/') and not any(x in ('.','..') for x in name.split('/')) and '\\' not in name and ':' not in name)
            need(len(files)<4096)
            files[name]=oid
            expected_index.append(mode+b' '+oid+b' 0\t'+raw_path)
        need(files and self.git('ls-files','--stage','-z',limit=2*1024*1024).split(b'\0')[:-1]==expected_index)
        untracked=self.git('ls-files','--others','-z',limit=2*1024*1024)
        source_extensions={'.py','.pyc','.pyo','.pyd','.so','.dll','.js','.mjs','.cjs'}
        need(not any(Path(p.decode()).suffix.lower() in source_extensions for p in untracked.split(b'\0') if p))
        unique=list(dict.fromkeys(files.values()));queries=b'\n'.join(unique)+b'\n'
        sizes=self.git('cat-file','--batch-check',input=queries,limit=1024*1024).splitlines()
        need(len(sizes)==len(unique))
        total=0
        for oid,line in zip(unique,sizes):
            actual,kind,size=line.split();need(actual==oid and kind==b'blob');total+=int(size)
        need(total<=32*1024*1024)
        batch=self.git('cat-file','--batch',input=queries,limit=total+len(unique)*128)
        blobs={};offset=0
        for oid in unique:
            end=batch.index(b'\n',offset);actual,kind,size=batch[offset:end].split();size=int(size);offset=end+1
            body=batch[offset:offset+size];offset+=size+1
            need(actual==oid and kind==b'blob' and hashlib.sha1(b'blob '+str(size).encode()+b'\0'+body).hexdigest().encode()==oid)
            blobs[oid]=body
        need(offset==len(batch))
        raw_hashes={}
        for name,oid in files.items():
            path=regular(self.root/name);need(path.stat().st_size==len(blobs[oid]))
            with path.open('rb') as stream:raw=stream.read(len(blobs[oid])+1)
            need(raw==blobs[oid]);raw_hashes[name]=hashlib.sha256(raw).hexdigest()
        snapshot=(head,hashlib.sha256(config_raw).hexdigest(),raw_hashes)
        if self.snapshot is not None:need(snapshot==self.snapshot)
        self.snapshot=snapshot
        return snapshot


def owned_profile():
    # -B alone does not stop reading a poisoned .pyc. The trusted owner's
    # -I -S -B bootstrap must establish this fresh cache before importing ANY
    # Meta package. An entry module cannot authenticate a poisoned loader itself.
    need(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode)
    need(sys.pycache_prefix is not None)
    cache=Path(sys.pycache_prefix)
    directory(cache)
    private=directory(Path(os.environ.get('UNIFIED_PRIVATE_CACHE_ROOT','')))
    need(cache.parent==private and cache!=private)
    if os.name!='nt':
        need(private.stat().st_uid==os.getuid() and not stat.S_IMODE(private.stat().st_mode)&0o077)
    need(not cache.is_relative_to(ROOT) and not any(cache.iterdir()))
    for ancestor in reversed((cache,*cache.parents)):
        info=ancestor.lstat()
        need(not stat.S_ISLNK(info.st_mode) and not getattr(info,'st_file_attributes',0)&1024)
    return cache


def attest_module(module,relative):
    cache=owned_profile()
    need(Path(module.__file__).absolute()==ROOT/relative)
    cached=getattr(module,'__cached__',None)
    need(cached is not None and Path(cached).is_relative_to(cache) and not Path(cached).exists())


def selfcheck():
    from . import core
    attest_module(core,'src/meta_analyse/core.py')
    from .core import Candle,untouched_levels
    levels=untouched_levels([Candle(datetime(2000,1,1,tzinfo=timezone.utc),Decimal(2),Decimal(1),Decimal(1),Decimal(2)),Candle(datetime(2000,1,2,tzinfo=timezone.utc),Decimal(3),Decimal(1),Decimal(2),Decimal(3))],'1m')
    need({(x.kind,x.price) for x in levels}=={('high',Decimal(3)),('low',Decimal(1))})


def strict_json(raw):
    def pairs(items):
        result={}
        for key,value in items:need(key not in result);result[key]=value
        return result
    def nonfinite(_):raise ValueError('NONFINITE')
    def number(raw):
        value=float(raw);need(math.isfinite(value));return value
    return json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_constant=nonfinite,parse_float=number)


def admitted_result(value):
    # Reject backend contract drift. Never repair forged authority into success.
    need(type(value) is dict and value.get('schema')=='meta.grid.history.analysis.v1')
    need(all(value.get(k) is False for k in ('execution_authority','trading_authorized','training_authorized')))
    need(value.get('source_authenticity')=='NOT_EVALUATED' and value.get('quality_status')=='UNKNOWN')
    return value


class PrivateServer(ThreadingHTTPServer):
    request_queue_size=8
    daemon_threads=False
    block_on_close=True
    allow_reuse_address=False

    def __init__(self,identity,*,port=0):
        need(type(port) is int and 0<=port<=65535)
        cache=owned_profile()
        attest_module(sys.modules['meta_analyse'],'src/meta_analyse/__init__.py')
        need(Path(__file__).absolute()==ROOT/'src/meta_analyse/headless_service.py')
        need(__cached__ is not None and Path(__cached__).is_relative_to(cache) and not Path(__cached__).exists())
        self.identity=identity;self.verifier=SourceVerifier(ROOT,identity)
        self.verifier.verify();selfcheck()
        self.slots=threading.BoundedSemaphore(4)
        super().__init__(('127.0.0.1',port),Handler)
        self.timeout=.2

    def get_request(self):
        request,address=super().get_request();request.settimeout(IO_DEADLINE);return request,address

    def process_request(self,request,address):
        if not self.slots.acquire(blocking=False):
            try:request.sendall(b'HTTP/1.0 503 Service Unavailable\r\nContent-Length: 0\r\n\r\n')
            finally:self.shutdown_request(request)
            return
        try:super().process_request(request,address)
        except BaseException:self.slots.release();raise

    def process_request_thread(self,request,address):
        def expire():
            try:request.shutdown(socket.SHUT_RDWR)
            except OSError:pass
        timer=threading.Timer(IO_DEADLINE,expire);timer.daemon=True;timer.start()
        try:super().process_request_thread(request,address)
        finally:timer.cancel();timer.join();self.slots.release()

    def handle_error(self,request,address):pass


class Handler(BaseHTTPRequestHandler):
    protocol_version='HTTP/1.0'
    server_version='PrivateMeta'

    def log_message(self,*args):pass

    def __getattr__(self,name):
        if name.startswith('do_'):return self.dispatch
        raise AttributeError(name)

    def reply(self,status,value):
        raw=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
        need(len(raw)<=MAX_RESPONSE)
        self.send_response(status);self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store')
        self.send_header('Connection','close');self.end_headers();self.wfile.write(raw)

    def fail(self,status):
        self.reply(status,dict(error='REQUEST_UNAVAILABLE',execution_authority=False,trading_authorized=False,training_authorized=False,source_authenticity='NOT_EVALUATED'))

    def dispatch(self):
        try:
            self.close_connection=True
            auth=self.headers.get_all('Authorization',[])
            if len(auth)!=1 or not auth[0].isascii() or not hmac.compare_digest(auth[0],'Bearer '+self.server.identity.token):return self.fail(401)
            hosts=self.headers.get_all('Host',[])
            if (len(hosts)!=1 or hosts[0] not in ('127.0.0.1:'+str(self.server.server_port),'localhost:'+str(self.server.server_port)) or self.headers.get_all('Origin',[])):return self.fail(403)
            if sum(len(k)+len(v) for k,v in self.headers.items())>16384:return self.fail(431)
            if self.headers.get_all('Transfer-Encoding',[]):return self.fail(400)
            lengths=self.headers.get_all('Content-Length',[])
            if len(lengths)>1:return self.fail(400)
            if self.command not in ('GET','POST'):return self.fail(405)
            if self.command=='GET':
                if self.path!='/internal/v2/module/health':return self.fail(404)
                if lengths and lengths!=['0']:return self.fail(400)
                try:self.server.verifier.verify()
                except (OSError,ValueError,subprocess.SubprocessError,configparser.Error):return self.fail(503)
                return self.reply(200,self.server.identity.health())
            if self.path!='/internal/v1/history/analyze':return self.fail(404)
            if self.headers.get_all('Content-Type',[])!=['application/json']:return self.fail(415)
            if len(lengths)!=1 or not re.fullmatch('[0-9]{1,8}',lengths[0]) or not 2<=int(lengths[0])<=MAX_BODY:return self.fail(413)
            raw=self.rfile.read(int(lengths[0]));need(len(raw)==int(lengths[0]))
            value=strict_json(raw)
            need(type(value) is dict and set(value)=={'payload','decision_ms'})
            self.server.verifier.verify()
            from . import grid_history_adapter
            attest_module(grid_history_adapter,'src/meta_analyse/grid_history_adapter.py')
            result=grid_history_adapter.analyze_grid_history(value['payload'],decision_ms=value['decision_ms'])
            return self.reply(200,admitted_result(result))
        except (ValueError,TypeError,KeyError,OverflowError,RecursionError,UnicodeError,configparser.Error,subprocess.SubprocessError):
            return self.fail(422)
        except (OSError,TimeoutError):return


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true');parser.add_argument('--port',type=int,default=8769)
    args=parser.parse_args(argv)
    if not args.execute:
        print(json.dumps(dict(module_id='meta_analyse',mode='PREPARE_ONLY',listening=False,execution_authority=False,trading_authorized=False)))
        return 0
    server=None
    try:
        identity=Identity.from_environment(os.environ)
        server=PrivateServer(identity,port=args.port)
        stop=threading.Event()
        def halt(*_):stop.set()
        signal.signal(signal.SIGTERM,halt);signal.signal(signal.SIGINT,halt)
        print(json.dumps(dict(port=server.server_port)),flush=True)
        while not stop.is_set():server.handle_request()
        return 0
    except (OSError,ValueError,TypeError,configparser.Error,subprocess.SubprocessError):
        print('BLOCKED: HEADLESS_SERVICE_UNAVAILABLE',file=sys.stderr);return 2
    finally:
        if server is not None:server.server_close()


if __name__=='__main__':raise SystemExit(main())
