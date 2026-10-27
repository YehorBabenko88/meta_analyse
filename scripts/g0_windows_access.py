"""Windows read-only AccessCheck adapter. Synthetic tests replace every DLL call.

Actual process token only; no account lookups, S4U, AdjustTokenPrivileges, writes,
Add-Type, subprocess, arbitrary paths, authentication or admission.
"""
import ctypes as C
from ctypes import wintypes as W
import hashlib
import os

D=C.c_uint32
B=C.c_int32

class Mapping(C.Structure):
    _fields_=[('read',D),('write',D),('execute',D),('all',D)]

class FileTime(C.Structure):
    _fields_=[('low',D),('high',D)]

class FileInfo(C.Structure):
    _fields_=[('attributes',D),('creation',FileTime),('access',FileTime),
              ('write',FileTime),('volume',D),('size_high',D),('size_low',D),
              ('links',D),('index_high',D),('index_low',D)]

class Luid(C.Structure):
    _fields_=[('low',D),('high',C.c_int32)]

class TokenStats(C.Structure):
    _fields_=[('token',Luid),('authentication',Luid),('expiration',C.c_int64),
              ('type',D),('level',D),('charged',D),('available',D),
              ('groups',D),('privileges',D),('modified',Luid)]

def abi_layout():
    return dict(mapping_size=C.sizeof(Mapping),file_info_size=C.sizeof(FileInfo),
                token_stats_size=C.sizeof(TokenStats),token_type_offset=TokenStats.type.offset,
                token_modified_offset=TokenStats.modified.offset)


def sample_current_token(path):
    if os.name!='nt' or path not in ('C:\\','C:\\ProgramData'):
        raise ValueError('ACCESS_UNAVAILABLE')
    if C.sizeof(C.c_void_p)!=8 or abi_layout()!=dict(mapping_size=16,file_info_size=52,
        token_stats_size=56,token_type_offset=24,token_modified_offset=48):
        raise OSError('ABI_UNAVAILABLE')
    from g0_access_review import RIGHTS
    kernel=C.WinDLL('kernel32',use_last_error=True)
    adv=C.WinDLL('advapi32',use_last_error=True)
    def bind(dll,name,args,result):
        fn=getattr(dll,name);fn.argtypes=args;fn.restype=result;return fn
    ptr=C.c_void_p;out=C.POINTER
    current=bind(kernel,'GetCurrentProcess',[],W.HANDLE)
    thread=bind(kernel,'GetCurrentThread',[],W.HANDLE)
    close=bind(kernel,'CloseHandle',[W.HANDLE],B)
    free=bind(kernel,'LocalFree',[ptr],ptr)
    open_token=bind(adv,'OpenProcessToken',[W.HANDLE,D,out(W.HANDLE)],B)
    thread_token=bind(adv,'OpenThreadToken',[W.HANDLE,D,B,out(W.HANDLE)],B)
    duplicate=bind(adv,'DuplicateToken',[W.HANDLE,C.c_int,out(W.HANDLE)],B)
    token_info=bind(adv,'GetTokenInformation',[W.HANDLE,C.c_int,ptr,D,out(D)],B)
    create=bind(kernel,'CreateFileW',[W.LPCWSTR,D,D,ptr,D,D,W.HANDLE],W.HANDLE)
    info=bind(kernel,'GetFileInformationByHandle',[W.HANDLE,out(FileInfo)],B)
    security=bind(adv,'GetSecurityInfo',[W.HANDLE,C.c_int,D,ptr,ptr,ptr,ptr,out(ptr)],D)
    valid=bind(adv,'IsValidSecurityDescriptor',[ptr],B)
    length=bind(adv,'GetSecurityDescriptorLength',[ptr],D)
    access=bind(adv,'AccessCheck',[ptr,W.HANDLE,D,out(Mapping),ptr,out(D),out(D),out(B)],B)
    handles=[]
    def need(v):
        if not v:raise OSError('ACCESS_UNAVAILABLE')
    def owned(handle):
        value=getattr(handle,'value',handle)
        need(type(value) is int and value not in (0,C.c_void_p(-1).value))
        handles.append(handle)
    def no_thread_token():
        impersonating=W.HANDLE()
        if thread_token(thread(),8,True,C.byref(impersonating)):
            owned(impersonating);raise OSError('IMPERSONATION_UNREVIEWED')
        need(C.get_last_error()==1008)  # ERROR_NO_TOKEN; other failures are not absence.
    try:
        no_thread_token()
        primary=W.HANDLE();need(open_token(current(),8|2,C.byref(primary)));owned(primary)
        def token_identity(handle,expected_type=1):
            stats=TokenStats();returned=D()
            need(token_info(handle,10,C.byref(stats),C.sizeof(stats),C.byref(returned)))
            need(returned.value==C.sizeof(stats))
            need(stats.type==expected_type)
            if expected_type==2:need(stats.level==2)
            return [value for luid in (stats.token,stats.authentication,stats.modified)
                    for value in (luid.low,luid.high&0xffffffff)]
        bound=token_identity(primary)
        token=W.HANDLE();need(duplicate(primary,2,C.byref(token)));owned(token)
        duplicate_bound=token_identity(token,2)
        need(duplicate_bound[2:4]==bound[2:4])
        # OPEN_EXISTING, BACKUP_SEMANTICS|OPEN_REPARSE_POINT; no FILE_SHARE_DELETE.
        def open_dir(name):
            h=create(name,0x20000|0x80,3,None,3,0x02000000|0x00200000,None)
            owned(h)
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
                    privileges=C.create_string_buffer(8192);capacity=D(8192)
                    granted=D(0xffffffff);status=B(0x7f7f7f7f)
                    need(access(sd,token,mask,C.byref(mapping),privileges,C.byref(capacity),
                                C.byref(granted),C.byref(status)))
                    count=C.cast(privileges,C.POINTER(D))[0]
                    need(8<=capacity.value<=8192 and 8+12*count<=capacity.value)
                    need(status.value in (0,1))
                    need(granted.value==(mask if status.value else 0))
                    rights[name]=bool(status.value)
                return dict(identity=[fi.volume,fi.index_high,fi.index_low],
                            token_identity=bound,descriptor_sha256=digest,rights=rights)
            finally:
                if sd.value:need(not free(sd))
        before=snapshot(h)
        after=snapshot(open_dir(path))
        final_token=W.HANDLE();need(open_token(current(),8,C.byref(final_token)));owned(final_token)
        need(token_identity(primary)==bound==token_identity(final_token))
        need(token_identity(token,2)==duplicate_bound)
        no_thread_token()
        return [before,after]
    finally:
        failed=False
        for handle in reversed(handles):
            try:
                if not close(handle):failed=True
            except Exception:
                failed=True
        if failed:raise OSError('CLEANUP_UNAVAILABLE') from None
