"""One-shot S0 import smoke. No stage chaining, authorization or baseline creation."""
import argparse
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
        if not all(type(p) is str and Path(p).is_absolute() for p in (repo,python,git)):
            return r
        def call(argv,limit):
            remaining=deadline-clock()
            if remaining<=0:raise TimeoutError()
            value=runner(argv,timeout=min(limit,remaining))
            if type(value.returncode) is not int or not -(2**31)<=value.returncode<2**32:
                raise ValueError()
            if argv[0]==python:r['child_exit_code']=value.returncode
            if type(value.stdout) is not bytes or len(value.stdout)>4096:raise ValueError()
            if clock()>deadline:raise TimeoutError()
            return value
        prefix=[git,'--no-optional-locks','-c','core.fsmonitor=false','-c','core.hooksPath='+os.devnull,
                '-C',repo]
        checks=((['rev-parse','HEAD'],expected_sha),
                              (['rev-parse','HEAD^{tree}'],expected_tree),
                              (['status','--porcelain=v1','--untracked-files=all'],''))
        def bound():
            for args,expected in checks:
                value=call(prefix+args,2)
                if value.returncode!=0 or value.stdout.decode('ascii').strip()!=expected:return False
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
