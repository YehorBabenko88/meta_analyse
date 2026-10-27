"""Synthetic only: no Windows APIs, real tools, domain lookup or host probes."""
import copy
import hashlib
import json

import pytest

from scripts import g0_access_review as gate

ROLES=('PYTHON_EXE','PYTHON_DLL','PYTHON_STDLIB','PYTHON_LOADER','CRT',
       'POWERSHELL','GIT','GIT_RUNTIME','NETSH','DOTNET_RUNTIME','NATIVE_DLLS','CONTROL_CODE')
SHA='0cc8c44d57514de6808fbbb6fdc7b9d9fd20ce30'
TREE='a85846d46df6e95f3d757e25399d991ee1db872b'
SECRET='PRIVATE_SENTINEL_HOST_PATH_TOKEN'

def fixture():
    files=[dict(role=r,path='C:\\approved\\'+r+'.bin',sha256=hashlib.sha256(r.encode()).hexdigest(),
                authority_sha256='a'*64,basis='SIGNED_DISTRIBUTION') for r in ROLES]
    value=dict(schema=1,target_sha=SHA,target_tree=TREE,files=files)
    raw=json.dumps(value).encode()
    return value,raw,hashlib.sha256(raw).hexdigest()

def reader(path):
    role=path.rsplit('\\',1)[1][:-4]
    return hashlib.sha256(role.encode()).hexdigest()

def verify(value=None, digest=None, read=reader):
    v,raw,pin=fixture()
    if value is not None:raw=json.dumps(value,allow_nan=True).encode();pin=hashlib.sha256(raw).hexdigest()
    return gate.verify_manifest(raw,digest or pin,read=read)

def test_actual_bytes_match_is_only_baseline_consistency():
    result=verify()
    assert result['provenance']=='APPROVED_MANIFEST_BYTES_MATCH'
    assert result['status']=='FAIL_CLOSED' and result['authorization']=='NONE'
    assert result['readiness']=='BLOCKED'
    assert result['loader_scope']=='INDEPENDENT_REVIEW_REQUIRED'

@pytest.mark.parametrize('role',ROLES)
def test_missing_role_refuses(role):
    v,_,_=fixture();v['files']=[x for x in v['files'] if x['role']!=role]
    assert verify(v)['provenance']=='UNAVAILABLE'

@pytest.mark.parametrize('fault',['bool_schema','sha','tree','unknown','duplicate','relative','unc','ads',
    'dotdot','trailing','bad_digest','bad_authority','unknown_basis','empty','float_schema','raw_extra'])
def test_manifest_malformed_or_unsupported_refuses_privately(fault):
    v,_,_=fixture();item=v['files'][0]
    if fault=='bool_schema':v['schema']=True
    elif fault=='float_schema':v['schema']=1.0
    elif fault in ('sha','tree'):v['target_'+fault]='f'*40
    elif fault=='unknown':item['role']=SECRET
    elif fault=='duplicate':v['files'].append(copy.deepcopy(item))
    elif fault=='relative':item['path']='relative.bin'
    elif fault=='unc':item['path']='\\\\server\\share\\x'
    elif fault=='ads':item['path']='C:\\approved\\file:stream'
    elif fault=='dotdot':item['path']='C:\\approved\\..\\x'
    elif fault=='trailing':item['path']='C:\\approved \\x'
    elif fault=='bad_digest':item['sha256']=None
    elif fault=='bad_authority':item['authority_sha256']=SECRET
    elif fault=='unknown_basis':item['basis']='SELF_MEASURED'
    elif fault=='empty':v['files']=[]
    elif fault=='raw_extra':item[SECRET]=SECRET
    result=verify(v)
    assert result['provenance']=='UNAVAILABLE'
    assert SECRET not in json.dumps(result)

@pytest.mark.parametrize('raw',[b'{"schema":1,"schema":1}',b'{"x":NaN}',b'{"x":Infinity}',b'[]',b'null',b'\xff',b'{}'*600000],
                         ids=['duplicate','nan','infinity','array','null','encoding','oversize'])
def test_strict_json(raw):
    result=gate.verify_manifest(raw,hashlib.sha256(raw).hexdigest(),read=reader)
    assert result['provenance']=='UNAVAILABLE'

def test_unapproved_digest_cannot_trigger_file_reads():
    calls=[]
    def forbidden(path):calls.append(path);return reader(path)
    assert verify(digest='0'*64,read=forbidden)['provenance']=='UNAVAILABLE'
    assert calls==[]

@pytest.mark.parametrize('return_value',[None,True,'f'*64,{},1.0])
def test_actual_file_mismatch_or_malformed_refuses(return_value):
    assert verify(read=lambda _:return_value)['provenance']=='UNAVAILABLE'

def test_reader_exception_is_private():
    def bad(_):raise OSError(SECRET)
    result=verify(read=bad)
    assert result['provenance']=='UNAVAILABLE' and SECRET not in json.dumps(result)

RIGHTS=('CREATE_DIRECTORY','CREATE_FILE','DELETE_CHILD','DELETE','WRITE_DAC','WRITE_OWNER','WRITE_ATTRIBUTES')
def observation():
    return dict(identity=[1,2,3],token_identity=[1,2,3,4,5,6],descriptor_sha256='e'*64,
                rights={r:False for r in RIGHTS})

def snapshots():
    return {label:[observation(),observation()] for label in ('ROOT','PROGRAMDATA')}

def test_current_token_rights_never_imply_other_subject_or_namespace_safety():
    data=snapshots();data['PROGRAMDATA'][0]['rights']['CREATE_DIRECTORY']=True
    data['PROGRAMDATA'][1]['rights']['CREATE_DIRECTORY']=True
    result=gate.project_access(data)
    assert result['current_token']['PROGRAMDATA']['CREATE_DIRECTORY'] is True
    assert result['other_subjects']=='NOT_EVALUATED'
    assert result['namespace_safety']=='NOT_ATTESTED'
    assert result['readiness']=='BLOCKED' and result['authorization']=='NONE'

@pytest.mark.parametrize('fault',['missing','extra','none','bool_identity','float_identity','negative_identity',
    'snapshot_change','descriptor_change','rights_change','bool_mask','missing_right','extra_right','extra_metadata',
    'token_change','token_bool','cross_target_token'])
def test_bad_access_snapshots_refuse_without_partial_projection(fault):
    data=snapshots();item=data['ROOT'][1]
    if fault=='missing':data.pop('PROGRAMDATA')
    elif fault=='extra':data[SECRET]=data['ROOT']
    elif fault=='none':data['ROOT']=None
    elif fault=='bool_identity':item['identity'][0]=True
    elif fault=='float_identity':item['identity'][0]=1.0
    elif fault=='negative_identity':item['identity'][0]=-1
    elif fault=='snapshot_change':item['identity'][0]=99
    elif fault=='descriptor_change':item['descriptor_sha256']='f'*64
    elif fault=='rights_change':item['rights']['DELETE_CHILD']=True
    elif fault=='bool_mask':item['rights']['DELETE_CHILD']=1
    elif fault=='missing_right':item['rights'].pop('DELETE')
    elif fault=='extra_right':item['rights'][SECRET]=True
    elif fault=='extra_metadata':item[SECRET]=SECRET
    elif fault=='token_change':item['token_identity'][0]=99
    elif fault=='token_bool':item['token_identity'][0]=True
    elif fault=='cross_target_token':
        for observed in data['PROGRAMDATA']:observed['token_identity'][0]=99
    result=gate.project_access(data)
    assert result['access']=='UNAVAILABLE' and 'current_token' not in result
    assert SECRET not in json.dumps(result)

def test_collection_has_only_two_fixed_targets_and_no_partial_output():
    calls=[]
    def sample(path):
        calls.append(path)
        if len(calls)==2:raise OSError(SECRET)
        return [observation(),observation()]
    result=gate.collect_access(sample)
    assert calls==['C:\\','C:\\ProgramData']
    assert result['access']=='UNAVAILABLE' and 'current_token' not in result
    assert SECRET not in json.dumps(result)

def test_collection_positive_still_blocks():
    assert gate.collect_access(lambda _:[observation(),observation()])['readiness']=='BLOCKED'

def test_cli_never_collects_after_failed_provenance(monkeypatch,capsys,tmp_path):
    path=tmp_path/'manifest.json';path.write_text('{}')
    calls=[]
    def forbidden():calls.append(True);return gate.project_access(None)
    monkeypatch.setattr(gate,'collect_access',forbidden)
    assert gate.main(['--manifest',str(path),'--approved-manifest-sha256','0'*64,'--current-token'])==1
    result=json.loads(capsys.readouterr().out)
    assert result['provenance']=='UNAVAILABLE' and result['authorization']=='NONE'
    assert calls==[]

def test_malformed_cli_does_not_echo_private_arguments(capsys):
    assert gate.main(['--unknown',SECRET])==1
    captured=capsys.readouterr()
    assert SECRET not in captured.out+captured.err
    assert json.loads(captured.out)['readiness']=='BLOCKED'

@pytest.mark.parametrize('name',['CON','NUL.txt','com1.exe','LPT9','AUX'])
def test_device_path_refuses(name):
    v,_,_=fixture();v['files'][0]['path']='C:\\approved\\'+name
    assert verify(v)['provenance']=='UNAVAILABLE'

def test_case_variant_duplicate_paths_refuse():
    v,_,_=fixture();item=copy.deepcopy(v['files'][0]);item['path']=item['path'].lower();v['files'].append(item)
    assert verify(v)['provenance']=='UNAVAILABLE'

def test_only_approved_catalog_manifest_can_allow_servicing_links(monkeypatch):
    v,_,_=fixture();v['files'][0]['basis']='CATALOG';calls=[]
    def hashed(path,*,allow_servicing_links):
        calls.append(allow_servicing_links);return reader(path)
    monkeypatch.setattr(gate,'hash_regular_file',hashed)
    raw=json.dumps(v).encode()
    assert gate.verify_manifest(raw,hashlib.sha256(raw).hexdigest())['provenance']=='APPROVED_MANIFEST_BYTES_MATCH'
    assert calls==[True]+[False]*(len(ROLES)-1)

@pytest.mark.parametrize('changing',[False,True],ids=['stable','handle_mutation'])
def test_windows_path_and_handle_ctime_have_separate_stable_domains(monkeypatch,tmp_path,changing):
    import os
    from types import SimpleNamespace
    file=tmp_path/'unchanged.bin';file.write_bytes(b'UNCHANGED')
    path_stat=file.lstat()
    calls=[]
    def handle_stat(fd):
        calls.append(True)
        actual=os.fstat(fd)
        return SimpleNamespace(**{name:getattr(actual,name) for name in
            ('st_dev','st_ino','st_size','st_mtime_ns','st_nlink')},
            st_ctime_ns=path_stat.st_ctime_ns+1000000+(len(calls) if changing else 0))
    monkeypatch.setattr(gate,'local_file_path',lambda _:None)
    monkeypatch.setattr(gate,'os',SimpleNamespace(name='nt',fstat=handle_stat))
    if changing:
        with pytest.raises(ValueError):gate.hash_regular_file(str(file))
    else:
        assert gate.hash_regular_file(str(file))==hashlib.sha256(b'UNCHANGED').hexdigest()

@pytest.mark.parametrize('change',['none','hardlink','replace','content'])
def test_real_synthetic_file_digest_and_mutation(monkeypatch,tmp_path,change):
    import os
    from types import SimpleNamespace
    file=tmp_path/'tool.bin';file.write_bytes(b'APPROVED_SYNTHETIC')
    monkeypatch.setattr(gate,'local_file_path',lambda _:None)
    monkeypatch.setattr(gate,'os',SimpleNamespace(name='nt',fstat=os.fstat))
    if change=='hardlink':
        os.link(file,tmp_path/'alias.bin')
    elif change in ('replace','content'):
        original_open=open
        class Wrapper:
            def __enter__(self):
                self.stream=original_open(file,'rb');self.changed=False;return self
            def fileno(self):return self.stream.fileno()
            def read(self,n):
                data=self.stream.read(n)
                if data and not self.changed:
                    self.changed=True
                    if change=='content':
                        with original_open(file,'ab') as writer:writer.write(b'CHANGED')
                    else:
                        # Path replacement may be denied by Windows sharing semantics;
                        # denied mutation is also a safe read failure, never a match.
                        try:
                            self.stream.close();file.unlink();file.write_bytes(b'REPLACED')
                        except OSError:raise OSError('REPLACEMENT_BLOCKED')
                return data
            def __exit__(self,*_):self.stream.close()
        monkeypatch.setattr(gate,'open',lambda *_:Wrapper(),raising=False)
    if change=='none':
        assert gate.hash_regular_file(str(file))==hashlib.sha256(b'APPROVED_SYNTHETIC').hexdigest()
    else:
        with pytest.raises((ValueError,OSError)):
            gate.hash_regular_file(str(file))
