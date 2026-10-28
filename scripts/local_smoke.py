"""One-shot S0 import smoke. No stage chaining, authorization or baseline creation."""
import argparse
import hashlib
import stat
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

CHILD='''import sys,struct,json,hashlib,hmac,pathlib,ctypes
print(json.dumps(dict(schema=1,isolated=bool(sys.flags.isolated),
 no_site=bool(sys.flags.no_site),bytecode_disabled=bool(sys.dont_write_bytecode),
 python312=sys.version_info[:2]==(3,12),bits64=struct.calcsize("P")==8,imports_ok=True)))
'''
STAGES={
 'S0':('ISOLATED_IMPORT_ONLY','EXPLICIT_S0_OPERATOR_DECISION'),
 'S1':('UNIMPLEMENTED_READ_ONLY_G0','INDEPENDENT_G0_APPROVAL'),
 'S2':('UNIMPLEMENTED_PG55480','SEPARATE_G1_APPROVAL_AND_S1_ACCEPTANCE'),
 'S3':('UNIMPLEMENTED_SYNTHETIC_DESKTOP','EXPLICIT_UI_APPROVAL_AND_PREVIOUS_ACCEPTANCE'),
 'S4':('UNIMPLEMENTED_PUBLIC_BYBIT','SEPARATE_PUBLIC_NETWORK_E2E_APPROVAL'),
}

def hex40(value):return type(value) is str and re.fullmatch('[0-9a-f]{40}',value) is not None

def command(argv,timeout):
    return subprocess.run(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL,timeout=timeout,check=False)

def run_smoke(*,stage,expected_sha,expected_tree,repo,python,git,operator_approved,
              runner=command,clock=time.monotonic):
    start=clock();deadline=start+15
    r=dict(schema=1,stage=stage if type(stage) is str and stage in STAGES else 'UNKNOWN',
        source_sha=expected_sha if hex40(expected_sha) else None,
        source_tree=expected_tree if hex40(expected_tree) else None,source_bound=False,
        production_sha='0cc8c44d57514de6808fbbb6fdc7b9d9fd20ce30',
        production_tree='a85846d46df6e95f3d757e25399d991ee1db872b',
        outcome='BLOCKED',reason='PRECONDITIONS_REQUIRED',exit_code=2,child_exit_code=None,
        elapsed_ms=0,authorization='NONE',g0_status='FAIL_CLOSED',next_stage='BLOCKED',
        approval_authenticity='EXTERNAL_REVIEW_REQUIRED',attempts=0)
    try:
        if stage!='S0' or operator_approved is not True or not all(hex40(v) for v in (expected_sha,expected_tree)):
            return r
        # Inherited Git overrides may redirect repository/config or persist trace data.
        if any(k.upper().startswith('GIT_') and k.upper() not in
               {'GIT_CONFIG_SYSTEM','GIT_CONFIG_GLOBAL','GIT_CONFIG_NOSYSTEM'} for k in os.environ):return r
        if not all(type(p) is str and Path(p).is_absolute() for p in (repo,python,git)):
            return r
        def call(argv,limit):
            remaining=deadline-clock()
            if remaining<=0:raise TimeoutError()
            value=runner(argv,timeout=min(limit,remaining))
            if type(value.returncode) is not int or not -(2**31)<=value.returncode<2**32:
                raise ValueError()
            if argv[0]==python:r['child_exit_code']=value.returncode
            if type(value.stdout) is not bytes or len(value.stdout)>(4*1024*1024 if 'ls-tree' in argv or 'ls-files' in argv else 4096):raise ValueError()
            if clock()>deadline:raise TimeoutError()
            return value
        prefix=[git,'--no-pager','--no-lazy-fetch','--no-replace-objects','--no-optional-locks','-c','core.fsmonitor=false','-c','core.hooksPath='+os.devnull,
                '--work-tree='+repo,'-C',repo]
        checks=((['rev-parse','HEAD'],expected_sha),
                              (['rev-parse','HEAD^{tree}'],expected_tree))
        def bound():
            # Read effective active includes/scopes, never filter command values.
            filters=call(prefix+['config','--includes','--null','--name-only','--get-regexp',
                                 r'^filter\..*\.(clean|smudge|process|required)$'],2)
            overrides=[]
            if filters.returncode==1:
                if filters.stdout:return False
            elif filters.returncode==0:
                if not filters.stdout or not filters.stdout.endswith(b'\0'):return False
                drivers=set()
                for key in filters.stdout[:-1].decode('utf-8').split('\0'):
                    match=re.fullmatch(r'(?i:filter)\.([A-Za-z0-9_.-]{1,64})\.(?i:clean|smudge|process|required)',key)
                    if not match:return False
                    drivers.add(match[1])
                if len(drivers)>16:return False
                for driver in sorted(drivers):
                    for setting,value in (('clean',''),('smudge',''),('process',''),('required','false')):
                        overrides+=['-c','filter.'+driver+'.'+setting+'='+value]
            else:return False
            for args,expected in checks:
                value=call(prefix+overrides+args,2)
                if value.returncode!=0 or value.stdout.decode('ascii').strip()!=expected:return False
            # Do not ask status/diff to convert worktree data: those execute filters.
            tree=call(prefix+['ls-tree','-r','-z','--full-tree',expected_tree],2)
            index=call(prefix+['ls-files','--stage','-z'],2)
            others=call(prefix+['ls-files','--others','--exclude-standard','-z'],2)
            if any(v.returncode!=0 for v in (tree,index,others)) or others.stdout:return False
            def entries(raw,tree_format):
                if not raw or not raw.endswith(b'\0'):raise ValueError()
                result={};folded=set()
                for row in raw[:-1].split(b'\0'):
                    head,name=row.split(b'\t',1);mode,second,third=head.split(b' ')
                    oid=third if tree_format else second
                    if (mode not in (b'100644',b'100755') or
                        (second!=b'blob' if tree_format else third!=b'0') or
                        not re.fullmatch(b'[0-9a-f]{40}',oid)):raise ValueError()
                    name=name.decode('utf-8');parts=name.split('/')
                    if any(part in ('','.','..') or any(c in part for c in '\\:') for part in parts):raise ValueError()
                    if name.casefold() in folded:raise ValueError()
                    folded.add(name.casefold());result[name]=(mode,oid.decode('ascii'))
                return result
            files=entries(tree.stdout,True)
            if files!=entries(index.stdout,False):return False
            total=0;root=Path(repo)
            root_stat=root.lstat()
            if root.is_symlink() or getattr(root_stat,'st_file_attributes',0)&0x400:return False
            for name,(_mode,oid) in files.items():
                if clock()>deadline:raise TimeoutError()
                path=root
                for part in name.split('/'):
                    path=path/part;st=path.lstat()
                    if stat.S_ISLNK(st.st_mode) or getattr(st,'st_file_attributes',0)&0x400:return False
                if not stat.S_ISREG(st.st_mode) or st.st_nlink!=1:return False
                total+=st.st_size
                if st.st_size>16*1024*1024 or total>128*1024*1024:return False
                with path.open('rb') as stream:data=stream.read(16*1024*1024+1)
                if len(data)!=st.st_size or len(data)>16*1024*1024:return False
                digest=hashlib.sha1(b'blob '+str(len(data)).encode('ascii')+b'\0'+data).hexdigest()
                if digest!=oid:return False
            return True
        if not bound():r['reason']='SOURCE_UNAVAILABLE';return r
        r['attempts']=1;r['outcome']='FAIL';r['exit_code']=1
        r['reason']='S0_UNAVAILABLE'
        value=call([python,'-I','-S','-B','-c',CHILD],8)
        r['child_exit_code']=value.returncode
        if value.returncode!=0:return r
        def unique(pairs):
            result={}
            for k,v in pairs:
                if k in result:raise ValueError()
                result[k]=v
            return result
        data=json.loads(value.stdout.decode('utf-8'),object_pairs_hook=unique)
        keys={'schema','isolated','no_site','bytecode_disabled','python312','bits64','imports_ok'}
        if type(data) is not dict or set(data)!=keys or type(data['schema']) is not int or data['schema']!=1:
            return r
        if any(data[k] is not True for k in keys-{'schema'}):return r
        if not bound():
            r['source_bound']=False;r['reason']='SOURCE_CHANGED';return r
        r['source_bound']=True
        r.update(outcome='PASS_SMOKE_ONLY',reason='IMPORTS_OBSERVED_NOT_ATTESTED',exit_code=0)
    except Exception:
        r['reason']='S0_UNAVAILABLE' if r['attempts'] else 'SOURCE_UNAVAILABLE'
    finally:
        r['elapsed_ms']=max(0,int((clock()-start)*1000))
    return r

def main(argv=None):
    class PrivateParser(argparse.ArgumentParser):
        def error(self,_message):raise ValueError('CLI_UNAVAILABLE')
    parser=PrivateParser(description=__doc__)
    parser.add_argument('--stage',required=True)
    parser.add_argument('--expected-sha',required=True)
    parser.add_argument('--expected-tree',required=True)
    parser.add_argument('--repo',required=True)
    parser.add_argument('--python',required=True)
    parser.add_argument('--git',required=True)
    parser.add_argument('--operator-approved-s0',action='store_true')
    try:
        a=parser.parse_args(argv)
        approved=a.operator_approved_s0 and bool(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode)
        r=run_smoke(stage=a.stage,expected_sha=a.expected_sha,expected_tree=a.expected_tree,
                    repo=a.repo,python=a.python,git=a.git,operator_approved=approved)
    except Exception:
        r=dict(schema=1,stage='UNKNOWN',outcome='BLOCKED',reason='CLI_UNAVAILABLE',exit_code=2,
               source_sha=None,source_tree=None,source_bound=False,elapsed_ms=0,child_exit_code=None,
               authorization='NONE',g0_status='FAIL_CLOSED',next_stage='BLOCKED',attempts=0)
    print(json.dumps(r,sort_keys=True,allow_nan=False))
    return r['exit_code']

if __name__=='__main__':sys.exit(main())
