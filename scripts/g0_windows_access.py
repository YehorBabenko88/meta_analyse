"""Windows read-only AccessCheck adapter. Never imported by synthetic tests.

Actual process token only; no account lookups, S4U, AdjustTokenPrivileges, writes,
Add-Type, subprocess, arbitrary paths, authentication or admission.
"""
import ctypes as C
from ctypes import wintypes as W
import hashlib
import os


def sample_current_token(path):
    if os.name!='nt' or path not in ('C:\\','C:\\ProgramData'):
        raise ValueError('ACCESS_UNAVAILABLE')
    from g0_access_review import RIGHTS
    kernel=C.WinDLL('kernel32',use_last_error=True)
    adv=C.WinDLL('advapi32',use_last_error=True)
    class Mapping(C.Structure):
        _fields_=[('read',W.DWORD),('write',W.DWORD),('execute',W.DWORD),('all',W.DWORD)]
    class FileInfo(C.Structure):
        _fields_=[('attributes',W.DWORD),('creation',W.FILETIME),('access',W.FILETIME),
                  ('write',W.FILETIME),('volume',W.DWORD),('size_high',W.DWORD),
                  ('size_low',W.DWORD),('links',W.DWORD),('index_high',W.DWORD),('index_low',W.DWORD)]
    class Luid(C.Structure):
        _fields_=[('low',C.c_uint32),('high',C.c_int32)]
    class TokenStats(C.Structure):
        _fields_=[('token',Luid),('authentication',Luid),('expiration',C.c_int64),
                  ('type',W.DWORD),('level',W.DWORD),('charged',W.DWORD),('available',W.DWORD),
                  ('groups',W.DWORD),('privileges',W.DWORD),('modified',Luid)]
    def bind(dll,name,args,result):
        fn=getattr(dll,name);fn.argtypes=args;fn.restype=result;return fn
    ptr=C.c_void_p;out=C.POINTER
    current=bind(kernel,'GetCurrentProcess',[],W.HANDLE)
    thread=bind(kernel,'GetCurrentThread',[],W.HANDLE)
    close=bind(kernel,'CloseHandle',[W.HANDLE],W.BOOL)
    free=bind(kernel,'LocalFree',[ptr],ptr)
    open_token=bind(adv,'OpenProcessToken',[W.HANDLE,W.DWORD,out(W.HANDLE)],W.BOOL)
    thread_token=bind(adv,'OpenThreadToken',[W.HANDLE,W.DWORD,W.BOOL,out(W.HANDLE)],W.BOOL)
    duplicate=bind(adv,'DuplicateToken',[W.HANDLE,C.c_int,out(W.HANDLE)],W.BOOL)
    token_info=bind(adv,'GetTokenInformation',[W.HANDLE,C.c_int,ptr,W.DWORD,out(W.DWORD)],W.BOOL)
    create=bind(kernel,'CreateFileW',[W.LPCWSTR,W.DWORD,W.DWORD,ptr,W.DWORD,W.DWORD,W.HANDLE],W.HANDLE)
    info=bind(kernel,'GetFileInformationByHandle',[W.HANDLE,out(FileInfo)],W.BOOL)
    security=bind(adv,'GetSecurityInfo',[W.HANDLE,C.c_int,W.DWORD,ptr,ptr,ptr,ptr,out(ptr)],W.DWORD)
    valid=bind(adv,'IsValidSecurityDescriptor',[ptr],W.BOOL)
    length=bind(adv,'GetSecurityDescriptorLength',[ptr],W.DWORD)
    access=bind(adv,'AccessCheck',[ptr,W.HANDLE,W.DWORD,out(Mapping),ptr,out(W.DWORD),out(W.DWORD),out(W.BOOL)],W.BOOL)
    handles=[]
    def need(v):
        if not v:raise OSError('ACCESS_UNAVAILABLE')
    try:
        impersonating=W.HANDLE()
        if thread_token(thread(),8,True,C.byref(impersonating)):
            close(impersonating);raise OSError('IMPERSONATION_UNREVIEWED')
        need(C.get_last_error()==1008)  # ERROR_NO_TOKEN; other failures are not absence.
        primary=W.HANDLE();need(open_token(current(),8|2,C.byref(primary)));handles.append(primary)
        def token_identity(handle):
            stats=TokenStats();returned=W.DWORD()
            need(token_info(handle,10,C.byref(stats),C.sizeof(stats),C.byref(returned)))
            need(returned.value==C.sizeof(stats))
            return [value for luid in (stats.token,stats.authentication,stats.modified)
                    for value in (luid.low,luid.high&0xffffffff)]
        bound=token_identity(primary)
        token=W.HANDLE();need(duplicate(primary,2,C.byref(token)));handles.append(token)
        # OPEN_EXISTING, BACKUP_SEMANTICS|OPEN_REPARSE_POINT; no FILE_SHARE_DELETE.
        def open_dir(name):
            h=create(name,0x20000|0x80,3,None,3,0x02000000|0x00200000,None)
            need(h is not None and h!=C.c_void_p(-1).value);handles.append(h)
            fi=FileInfo();need(info(h,C.byref(fi)))
            need(fi.attributes&0x10 and not fi.attributes&0x400)
            return h
        # Hold the root while opening ProgramData; never traverse an unchecked root.
        root=open_dir('C:\\')
        h=root if path=='C:\\' else open_dir(path)
        def snapshot(handle):
            fi=FileInfo();need(info(handle,C.byref(fi)))
            need(fi.attributes&0x10 and not fi.attributes&0x400)
            sd=ptr()
            need(security(handle,1,7,None,None,None,None,C.byref(sd))==0)
            try:
                need(sd.value and valid(sd));size=length(sd);need(0<size<=65536)
                digest=hashlib.sha256(C.string_at(sd,size)).hexdigest()
                rights={}
                for name,mask in RIGHTS.items():
                    mapping=Mapping(0x120089,0x120116,0x1200a0,0x1f01ff)
                    privileges=C.create_string_buffer(8192);capacity=W.DWORD(8192)
                    granted=W.DWORD();status=W.BOOL()
                    need(access(sd,token,mask,C.byref(mapping),privileges,C.byref(capacity),
                                C.byref(granted),C.byref(status)))
                    need(capacity.value<=8192)
                    rights[name]=bool(status.value and (granted.value&mask)==mask)
                return dict(identity=[fi.volume,fi.index_high,fi.index_low],
                            token_identity=bound,descriptor_sha256=digest,rights=rights)
            finally:
                if sd.value:free(sd)
        before=snapshot(h)
        after=snapshot(open_dir(path))
        final_token=W.HANDLE();need(open_token(current(),8,C.byref(final_token)));handles.append(final_token)
        need(token_identity(primary)==bound==token_identity(final_token))
        return [before,after]
    finally:
        for handle in reversed(handles):close(handle)
