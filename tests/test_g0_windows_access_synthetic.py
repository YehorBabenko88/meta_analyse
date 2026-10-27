"""Fake WinAPI entry points only; never load DLLs or inspect the real host."""
import ctypes as C
from types import SimpleNamespace
import sys

import pytest

from scripts import g0_access_review as gate
from scripts import g0_windows_access as native

class Function:
    def __init__(self,name,env):self.name=name;self.env=env
    def __call__(self,*args):return self.env.call(self.name,args)

class FakeWindows:
    def __init__(self,fault=None):
        self.fault=fault;self.calls=[];self.handles=[];self.closed=[];self.counter=100;self.duplicate=None
        self.sd=C.create_string_buffer(b'SYNTHETIC_DESCRIPTOR')
    def dll(self,*_args,**_kwargs):
        return SimpleNamespace(**{name:Function(name,self) for name in (
            'GetCurrentProcess','GetCurrentThread','CloseHandle','LocalFree','OpenProcessToken',
            'OpenThreadToken','DuplicateToken','GetTokenInformation','CreateFileW','GetFileInformationByHandle',
            'GetSecurityInfo','IsValidSecurityDescriptor','GetSecurityDescriptorLength','AccessCheck')})
    def call(self,name,args):
        self.calls.append((name,args))
        if name in ('GetCurrentProcess','GetCurrentThread'):return 1
        if name=='CloseHandle':
            self.closed.append(getattr(args[0],'value',args[0]))
            if self.fault=='close_raise':raise OSError('PRIVATE_CLEANUP_FAILURE')
            return self.fault!='close_failure'
        if name=='LocalFree':
            if self.fault=='free_raise':raise OSError('PRIVATE_CLEANUP_FAILURE')
            return 1 if self.fault=='free_failure' else None
        if name=='OpenThreadToken':
            if self.fault=='impersonation' or (self.fault=='late_impersonation' and
                sum(n==name for n,_ in self.calls)>1):args[-1]._obj.value=30;return True
            return False
        if name in ('OpenProcessToken','DuplicateToken'):
            if self.fault==name:return False
            if ((name=='OpenProcessToken' and self.fault=='primary_null') or
                (name=='DuplicateToken' and self.fault=='duplicate_null')):
                args[-1]._obj.value=None;return True
            if name=='OpenProcessToken' and self.fault=='final_null' and sum(n==name for n,_ in self.calls)>1:
                args[-1]._obj.value=None;return True
            if name=='DuplicateToken':self.duplicate=self.counter+1
            self.counter+=1;args[-1]._obj.value=self.counter;self.handles.append(self.counter);return True
        if name=='GetTokenInformation':
            if self.fault==name:return False
            stats=args[2]._obj
            stats.token.low=1;stats.authentication.low=2;stats.modified.low=3
            is_duplicate=getattr(args[0],'value',args[0])==self.duplicate
            stats.type=2 if is_duplicate else 1;stats.level=2
            if self.fault=='primary_type' and not is_duplicate:stats.type=2
            if self.fault=='duplicate_type' and is_duplicate:stats.type=1
            if self.fault=='duplicate_level' and is_duplicate:stats.level=1
            if self.fault=='duplicate_auth' and is_duplicate:stats.authentication.low=999
            if self.fault=='duplicate_modified' and is_duplicate and sum(n==name and
                getattr(a[0],'value',a[0])==self.duplicate for n,a in self.calls)>1:
                stats.modified.low=999
            if self.fault=='token_replaced' and sum(n==name for n,_ in self.calls)>1:
                stats.token.low=99
            args[-1]._obj.value=1 if self.fault=='short_stats' else C.sizeof(stats);return True
        if name=='CreateFileW':
            assert args[1]==0x20080 and args[2]==3 and args[4]==3
            assert args[5]==0x02200000 and args[0] in ('C:\\','C:\\ProgramData')
            if self.fault=='CreateFileW':return C.c_void_p(-1).value
            if self.fault=='file_null':return None
            self.counter+=1;self.handles.append(self.counter);return self.counter
        if name=='GetFileInformationByHandle':
            if self.fault==name:return False
            info=args[1]._obj;info.attributes=0x10|(0x400 if self.fault=='reparse' else 0)
            info.volume=1;info.index_high=0;info.index_low=5;return True
        if name=='GetSecurityInfo':
            if self.fault==name:return 5
            args[-1]._obj.value=None if self.fault=='null_sd' else C.addressof(self.sd);return 0
        if name=='IsValidSecurityDescriptor':return self.fault!=name
        if name=='GetSecurityDescriptorLength':return 0 if self.fault=='empty_sd' else len(self.sd)
        if name=='AccessCheck':
            if self.fault==name:return False
            if self.fault=='unset_status':return True
            args[-2]._obj.value=0 if self.fault=='denied' else args[2]
            args[-1]._obj.value=self.fault!='denied'
            if self.fault=='grant_missing':args[-2]._obj.value=0
            if self.fault=='grant_extra':args[-2]._obj.value=args[2]|0x80000000
            if self.fault=='deny_with_grant':args[-1]._obj.value=0
            if self.fault=='privilege_short':args[5]._obj.value=0
            if self.fault=='privilege_overflow':args[5]._obj.value=8193
            if self.fault=='privilege_count':C.cast(args[4],C.POINTER(C.c_uint32))[0]=10000
            return True
        raise AssertionError(name)

def install(monkeypatch,fault=None):
    api=FakeWindows(fault)
    monkeypatch.setattr(native,'os',SimpleNamespace(name='nt'))
    monkeypatch.setattr(C,'WinDLL',api.dll,raising=False)
    monkeypatch.setattr(C,'get_last_error',lambda:5 if fault=='thread_error' else 1008,raising=False)
    monkeypatch.setitem(sys.modules,'g0_access_review',gate)
    return api

@pytest.mark.parametrize('path',['C:\\','C:\\ProgramData'])
@pytest.mark.parametrize('fault',[None,'denied'])
def test_windows_adapter_uses_real_token_shape_and_read_only_fixed_handles(monkeypatch,path,fault):
    api=install(monkeypatch,fault)
    pair=native.sample_current_token(path)
    assert pair[0]==pair[1]
    assert set(pair[0]['rights'].values())=={fault!='denied'}
    assert sorted(api.handles)==sorted(api.closed)
    assert sum(name=='AccessCheck' for name,_ in api.calls)==14
    assert next(args for name,args in api.calls if name=='DuplicateToken')[1]==2

@pytest.mark.parametrize('fault',['impersonation','thread_error','OpenProcessToken','DuplicateToken',
    'CreateFileW','GetFileInformationByHandle','reparse','GetSecurityInfo',
    'IsValidSecurityDescriptor','empty_sd','AccessCheck','GetTokenInformation','token_replaced'])
def test_native_failures_close_every_acquired_handle_and_refuse(monkeypatch,fault):
    api=install(monkeypatch,fault)
    with pytest.raises(OSError):native.sample_current_token('C:\\ProgramData')
    assert set(api.handles)<=set(api.closed)

@pytest.mark.parametrize('path',['C:\\Other','D:\\','\\\\host\\share','C:\\ProgramData\\child'])
def test_no_arbitrary_target_or_remote_lookup(monkeypatch,path):
    api=install(monkeypatch)
    with pytest.raises(ValueError):native.sample_current_token(path)
    assert api.calls==[]

@pytest.mark.parametrize('fault',['late_impersonation','close_failure','close_raise','free_failure','free_raise'])
def test_late_context_and_cleanup_failures_are_not_successful_samples(monkeypatch,fault):
    api=install(monkeypatch,fault)
    with pytest.raises(OSError):native.sample_current_token('C:\\ProgramData')
    assert set(api.handles)<=set(api.closed)

def test_abi_layout_is_windows_x64_not_host_c_long():
    assert native.abi_layout()==dict(mapping_size=16,file_info_size=52,token_stats_size=56,
        token_type_offset=24,token_modified_offset=48)

@pytest.mark.parametrize('fault',['primary_null','duplicate_null','file_null','final_null','short_stats',
    'primary_type','duplicate_type','duplicate_level','duplicate_auth','duplicate_modified','null_sd','unset_status'])
def test_malformed_native_token_outputs_are_unavailable(monkeypatch,fault):
    api=install(monkeypatch,fault)
    with pytest.raises(OSError):native.sample_current_token('C:\\ProgramData')
    assert set(api.handles)<=set(api.closed)

@pytest.mark.parametrize('corrupt',['mapping_size','file_info_size','token_stats_size','token_type_offset','token_modified_offset'])
def test_abi_mismatch_refuses_before_any_dll_call(monkeypatch,corrupt):
    api=install(monkeypatch)
    actual=native.abi_layout();actual[corrupt]+=1
    monkeypatch.setattr(native,'abi_layout',lambda:actual)
    with pytest.raises(OSError):native.sample_current_token('C:\\')
    assert not api.calls

@pytest.mark.parametrize('fault',['grant_missing','grant_extra','deny_with_grant',
                                'privilege_short','privilege_overflow','privilege_count'])
def test_accesscheck_contradictions_are_not_negative_permission_evidence(monkeypatch,fault):
    api=install(monkeypatch,fault)
    with pytest.raises(OSError):native.sample_current_token('C:\\ProgramData')
    assert set(api.handles)<=set(api.closed)
