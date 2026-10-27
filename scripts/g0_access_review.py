"""Read-only control. No authorization, arbitrary-SID simulation or repair."""
import argparse
import hashlib
import hmac
import json
import ntpath
import os
from pathlib import Path
import re
import stat
import sys

TARGET_SHA='0cc8c44d57514de6808fbbb6fdc7b9d9fd20ce30'
TARGET_TREE='a85846d46df6e95f3d757e25399d991ee1db872b'
ROLES=frozenset(('PYTHON_EXE','PYTHON_DLL','PYTHON_STDLIB','PYTHON_LOADER','CRT',
                'POWERSHELL','GIT','GIT_RUNTIME','NETSH','DOTNET_RUNTIME','NATIVE_DLLS','CONTROL_CODE'))
RIGHTS={'CREATE_DIRECTORY':4,'CREATE_FILE':2,'DELETE_CHILD':64,'DELETE':65536,
        'WRITE_DAC':262144,'WRITE_OWNER':524288,'WRITE_ATTRIBUTES':256}

def require(value):
    if not value:raise ValueError('REVIEW_REFUSED')

def hex64(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}',value) is not None

def base():
    return dict(schema=1,target_sha=TARGET_SHA,target_tree=TARGET_TREE,
                status='FAIL_CLOSED',authorization='NONE',readiness='BLOCKED')

def local_file_path(value):
    require(type(value) is str and re.match(r'^[A-Za-z]:\\',value) is not None)
    require(not any(c in value[2:] for c in ':<>"|?*\x00/'))
    parts=value[3:].split('\\')
    require(parts and all(p and p not in ('.','..') and not p.endswith((' ','.')) for p in parts))
    # Device basenames are not ordinary files, even with an extension.
    require(all(not re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])',p.split('.')[0],re.I) for p in parts))

def strict_json(raw):
    require(type(raw) is bytes and len(raw)<=1024*1024)
    def unique(pairs):
        result={}
        for k,v in pairs:
            require(k not in result);result[k]=v
        return result
    def invalid(_):raise ValueError('NONFINITE')
    return json.loads(raw.decode('utf-8-sig'),object_pairs_hook=unique,parse_constant=invalid)

def hash_regular_file(path,*,allow_servicing_links=False):
    """Byte consistency, not race-proof traversal or independent loader approval."""
    local_file_path(path)
    require(os.name=='nt')
    chain=list(Path(path).parents)
    for parent in chain:
        info=parent.lstat()
        require(stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode) and
                not getattr(info,'st_file_attributes',0)&0x400)
    before=Path(path).lstat()
    require(stat.S_ISREG(before.st_mode) and not getattr(before,'st_file_attributes',0)&0x400 and
            before.st_nlink>=1 and (allow_servicing_links or before.st_nlink==1) and before.st_size<=1024**3)
    digest=hashlib.sha256()
    with open(path,'rb') as stream:
        held=os.fstat(stream.fileno())
        require((held.st_dev,held.st_ino)==(before.st_dev,before.st_ino))
        remaining=1024**3+1
        while remaining:
            block=stream.read(min(1024*1024,remaining))
            if not block:break
            digest.update(block);remaining-=len(block)
        require(remaining>0)
        after=os.fstat(stream.fileno())
    final=Path(path).lstat()
    key=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_nlink)
    require(key(before)==key(held)==key(after)==key(final))
    # Windows 3.12 lstat/fstat may expose different creation/change timestamps.
    # Compare ctime within each API domain, never drop either mutation check.
    require(before.st_ctime_ns==final.st_ctime_ns and held.st_ctime_ns==after.st_ctime_ns)
    require(not getattr(final,'st_file_attributes',0)&0x400)
    for parent in chain:
        info=parent.lstat()
        require(stat.S_ISDIR(info.st_mode) and not getattr(info,'st_file_attributes',0)&0x400)
    return digest.hexdigest()

def verify_manifest(raw,approved_digest,*,read=None,authority_raw=None,approved_authority_digest=None):
    result=base();result.update(provenance='UNAVAILABLE',loader_scope='INDEPENDENT_REVIEW_REQUIRED',
        authority_reference='NOT_BOUND',approval_authenticity='EXTERNAL_REVIEW_REQUIRED')
    try:
        require(type(raw) is bytes and hex64(approved_digest) and
                hmac.compare_digest(hashlib.sha256(raw).hexdigest(),approved_digest))
        value=strict_json(raw)
        require(type(value) is dict and set(value)=={'schema','target_sha','target_tree','files'})
        require(type(value['schema']) is int and value['schema']==1)
        require(value['target_sha']==TARGET_SHA and value['target_tree']==TARGET_TREE)
        files=value['files'];require(type(files) is list and 1<=len(files)<=10000)
        paths=set();roles=set()
        # Validate the whole manifest before opening any of its files.
        for item in files:
            require(type(item) is dict and set(item)=={'role','path','sha256','authority_sha256','basis'})
            require(type(item['role']) is str and item['role'] in ROLES|{'CSHARP_COMPILER'})
            require(hex64(item['sha256']) and hex64(item['authority_sha256']))
            require(item['basis'] in ('AUTHENTICODE','CATALOG','SIGNED_DISTRIBUTION'))
            local_file_path(item['path'])
            path=ntpath.normcase(item['path']);require(path not in paths)
            paths.add(path);roles.add(item['role'])
        require(ROLES<=roles)
        reference=False
        if authority_raw is not None or approved_authority_digest is not None:
            require(type(authority_raw) is bytes and 0<len(authority_raw)<=1024*1024)
            require(hex64(approved_authority_digest) and
                    hmac.compare_digest(hashlib.sha256(authority_raw).hexdigest(),approved_authority_digest))
            require(all(item['authority_sha256']==approved_authority_digest for item in files))
            reference=True
        for item in files:
            actual=(read(item['path']) if read is not None else
                    hash_regular_file(item['path'],allow_servicing_links=item['basis']=='CATALOG'))
            require(hex64(actual) and hmac.compare_digest(actual,item['sha256']))
        result['provenance']='PINNED_MANIFEST_BYTES_MATCH'
        if reference:result['authority_reference']='PINNED_PACKET_MATCH'
    except Exception:
        pass  # No input strings, exception details, paths or hashes in public projection.
    return result

def project_access(data):
    result=base();result.update(access='UNAVAILABLE',other_subjects='NOT_EVALUATED',namespace_safety='NOT_ATTESTED')
    try:
        require(type(data) is dict and set(data)=={'ROOT','PROGRAMDATA'})
        public={};bound_token=None
        for label,pair in data.items():
            require(type(pair) is list and len(pair)==2)
            for item in pair:
                require(type(item) is dict and set(item)=={'identity','token_identity','descriptor_sha256','rights'})
                identity=item['identity']
                require(type(identity) is list and len(identity)==3 and
                        all(type(n) is int and 0<=n<2**64 for n in identity))
                require(hex64(item['descriptor_sha256']))
                token=item['token_identity']
                require(type(token) is list and len(token)==6 and
                        all(type(n) is int and 0<=n<2**32 for n in token))
                if bound_token is None:bound_token=token
                require(token==bound_token)
                require(type(item['rights']) is dict and set(item['rights'])==set(RIGHTS) and
                        all(type(v) is bool for v in item['rights'].values()))
            require(pair[0]==pair[1])
            public[label]=dict(pair[0]['rights'])
        result.update(access='CURRENT_TOKEN_DESCRIPTOR_CHECKED',current_token=public)
    except Exception:
        pass
    return result

def collect_access(sample=None):
    try:
        if sample is None:
            # No ctypes DLL load at import or in offline manifest mode.
            from g0_windows_access import sample_current_token
            sample=sample_current_token
        data={label:sample(path) for label,path in (('ROOT','C:\\'),('PROGRAMDATA','C:\\ProgramData'))}
        return project_access(data)
    except Exception:
        return project_access(None)

def main(argv=None):
    class PrivateParser(argparse.ArgumentParser):
        def error(self,_message):
            raise ValueError('CLI_REFUSED')
    parser=PrivateParser(description=__doc__)
    parser.add_argument('--manifest',required=True)
    parser.add_argument('--approved-manifest-sha256',required=True)
    parser.add_argument('--authority-packet')
    parser.add_argument('--approved-authority-sha256')
    parser.add_argument('--current-token',action='store_true',help='Explicit Windows read-only API call; no other subjects')
    try:
        args=parser.parse_args(argv)
        with open(args.manifest,'rb') as stream:raw=stream.read(1024*1024+1)
        authority_raw=None
        if args.authority_packet:
            with open(args.authority_packet,'rb') as stream:authority_raw=stream.read(1024*1024+1)
        result=verify_manifest(raw,args.approved_manifest_sha256,authority_raw=authority_raw,
                               approved_authority_digest=args.approved_authority_sha256)
        if (args.current_token and result['provenance']=='PINNED_MANIFEST_BYTES_MATCH' and
            result['authority_reference']=='PINNED_PACKET_MATCH'):
            result.update(collect_access())
        elif args.current_token:
            result.update(project_access(None))
    except Exception:
        result=base();result['provenance']='UNAVAILABLE'
    print(json.dumps(result,sort_keys=True,allow_nan=False))
    return 1

if __name__=='__main__':
    sys.exit(main())
