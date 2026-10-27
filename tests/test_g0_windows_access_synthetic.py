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
        self.fault=fault;self.calls=[];self.handles=[];self.closed=[];self.counter=100
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
            self.closed.append(getattr(args[0],'value',args[0]));return True
        if name=='LocalFree':return None
        if name=='OpenThreadToken':
            if self.fault=='impersonation':args[-1]._obj.value=30;return True
            return False
        if name in ('OpenProcessToken','DuplicateToken'):
            if self.fault==name:return False
            self.counter+=1;args[-1]._obj.value=self.counter;self.handles.append(self.counter);return True
        if name=='GetTokenInformation':
            if self.fault==name:return False
            stats=args[2]._obj
            stats.token.low=1;stats.authentication.low=2;stats.modified.low=3
            if self.fault=='token_replaced' and sum(n==name for n,_ in self.calls)>1:
                stats.token.low=99
            args[-1]._obj.value=C.sizeof(stats);return True
        if name=='CreateFileW':
            assert args[1]==0x20080 and args[2]==3 and args[4]==3
            assert args[5]==0x02200000 and args[0] in ('C:\\','C:\\ProgramData')
            if self.fault=='CreateFileW':return C.c_void_p(-1).value
            self.counter+=1;self.handles.append(self.counter);return self.counter
        if name=='GetFileInformationByHandle':
            if self.fault==name:return False
            info=args[1]._obj;info.attributes=0x10|(0x400 if self.fault=='reparse' else 0)
            info.volume=1;info.index_high=0;info.index_low=5;return True
        if name=='GetSecurityInfo':
            if self.fault==name:return 5
            args[-1]._obj.value=C.addressof(self.sd);return 0
        if name=='IsValidSecurityDescriptor':return self.fault!=name
        if name=='GetSecurityDescriptorLength':return 0 if self.fault=='empty_sd' else len(self.sd)
        if name=='AccessCheck':
            if self.fault==name:return False
            args[-2]._obj.value=0 if self.fault=='denied' else args[2]
            args[-1]._obj.value=self.fault!='denied';return True
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
