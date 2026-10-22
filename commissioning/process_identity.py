"""Pure fail-closed classification of read-only Windows process evidence.

File signatures alone never establish which image is executing in a PID.
All returned paths and per-process details are private inventory inputs.
"""
import ntpath
import re

WINDOWS_PUBLISHERS={'Microsoft Windows','Microsoft Windows Publisher','Microsoft Corporation'}
SERVICE_RULES={
    'MDCoreSvc':('program_files',r'Windows Defender\MpDefenderCoreService.exe',WINDOWS_PUBLISHERS),
    'nllbIDSAgent':('program_files',r'Norton\Suite\aswidsagent.exe',{'Gen Digital Inc.'}),
    'Norton Antivirus':('program_files',r'Norton\Suite\NortonSvc.exe',{'Gen Digital Inc.'}),
    'NortonWscReporter':('program_files',r'Norton\Suite\wsc_proxy.exe',{'NortonLifeLock Inc.','Gen Digital Inc.'}),
    'SecurityHealthService':('system32','SecurityHealthService.exe',WINDOWS_PUBLISHERS),
}
# Standard OS-relative contracts, never learned from a private observation.
# These require independent registry, loaded-module and signed-DLL evidence.
WINDOWS_SERVICE_CONTRACTS={
    'KeyIso':('lsass.exe','keyiso.dll',(),'localsystem','parameters'),
    'SamSs':('lsass.exe','samsrv.dll',(),'localsystem','integrated'),
    'VaultSvc':('lsass.exe','vaultsvc.dll',(),'localsystem','parameters'),
    'DoSvc':('svchost.exe','dosvc.dll',('-k','networkservice','-p'),r'nt authority\networkservice','root'),
    'wscsvc':('svchost.exe','wscsvc.dll',('-k','localservicenetworkrestricted','-p'),r'nt authority\localservice','parameters'),
}
GRID=re.compile(r'grid|^(?:coordinator|worker|collector)(?:\.exe)?$',re.I)

def canonical(path):
    if (not isinstance(path,str) or not re.match(r'^[a-zA-Z]:[\\/]',path)
            or any(c in path for c in ('\x00','\r','\n','"')) or ':' in path[2:]):
        return ''
    return ntpath.normcase(ntpath.normpath(path))

def command_executable(command):
    if not isinstance(command,str): return ''
    # Reject ambiguous unquoted paths containing spaces (service path spoofing).
    match=re.fullmatch(r'"([^"\r\n]+\.exe)"(?:\s+[^\r\n]*)?|([^\s"\r\n]+\.exe)(?:\s+[^\r\n]*)?',command,re.I)
    return canonical(match[1] or match[2]) if match else ''

def same_creation(left,right):
    # CIM DMTF has microsecond resolution; native FILETIME has 100ns resolution.
    return type(left) is int and type(right) is int and left>0 and left//10==right//10


def command_arguments(command):
    if not command_executable(command):return None
    match=re.fullmatch(r'(?:"[^"\r\n]+\.exe"|[^\s"\r\n]+\.exe)(.*)',command,re.I)
    return tuple(match[1].casefold().split()) if match else None


def service_implementation_refusal(svc,evidence,roots,native):
    name=svc['name'];host,dll,args,account,source=WINDOWS_SERVICE_CONTRACTS[name]
    host_path=canonical(ntpath.join(roots['system32'],host))
    dll_path=canonical(ntpath.join(roots['system32'],dll))
    if canonical(native['path'])!=host_path:return 'SERVICE_IMAGE_NOT_REVIEWED'
    before=evidence.get('implementation_before',{}).get(name)
    after=evidence.get('implementation_after',{}).get(name)
    if not isinstance(before,dict) or not isinstance(after,dict) or any(c.get('complete') is not True or c.get('error_stage')!='' for c in (before,after)):
        return 'SERVICE_IMPLEMENTATION_UNVERIFIED'
    if before!=after:return 'SERVICE_IMPLEMENTATION_CHANGED'
    for c in (before,after):
        if (c.get('name')!=name or type(c.get('service_type')) is not int or c.get('service_type')!=32
                or type(svc.get('service_type')) is not int or svc.get('service_type')!=32
                or str(c.get('account','')).casefold()!=account or str(svc.get('start_name','')).casefold()!=account
                or command_executable(c.get('expanded_image_path'))!=host_path
                or command_arguments(c.get('expanded_image_path'))!=args or command_arguments(svc.get('binary_path'))!=args):
            return 'SERVICE_HOST_CONFIGURATION_UNREVIEWED'
        if c.get('dll_source')!=source:return 'SERVICE_DLL_CONFIGURATION_UNREVIEWED'
        if source=='integrated':
            if c.get('dll_present') is not False or c.get('expanded_dll_path')!='':return 'SERVICE_DLL_CONFIGURATION_UNREVIEWED'
        elif c.get('dll_present') is not True or canonical(c.get('expanded_dll_path'))!=dll_path:
            return 'SERVICE_DLL_CONFIGURATION_UNREVIEWED'
    sets=[]
    for key in ('modules_before','modules_after'):
        modules=evidence.get(key)
        if (not isinstance(modules,dict) or modules.get('complete') is not True or modules.get('error_stage')!=''
                or type(modules.get('win32_error')) is not int or modules.get('win32_error')!=0):
            return 'SERVICE_MODULES_UNAVAILABLE'
        if (type(modules.get('pid')) is not int or type(modules.get('created')) is not int
                or modules.get('pid')!=native['pid'] or modules.get('created')!=native['created'] or modules.get('alive') is not True):
            return 'SERVICE_MODULE_LIFETIME_MISMATCH'
        paths=modules.get('paths')
        if not isinstance(paths,list) or not paths or any(not canonical(v) for v in paths):return 'SERVICE_MODULES_UNAVAILABLE'
        normalized=[canonical(v) for v in paths]
        if len(normalized)!=len(set(normalized)):return 'SERVICE_MODULES_UNAVAILABLE'
        sets.append(set(normalized))
    if sets[0]!=sets[1]:return 'SERVICE_MODULES_CHANGED'
    if not {host_path,dll_path}.issubset(sets[0]):return 'SERVICE_IMPLEMENTATION_NOT_LOADED'
    sig=evidence.get('implementation_signatures',{}).get(name) or {}
    subject=sig.get('subject')
    cn=re.search(r'(?:^|,\s*)CN=([^,]+)(?:,|$)',subject) if isinstance(subject,str) else None
    if (sig.get('status')!='Valid' or canonical(sig.get('path'))!=dll_path or not cn or cn[1] not in WINDOWS_PUBLISHERS
            or sig.get('reparse_point') is not False or not re.fullmatch('[0-9a-f]{64}',sig.get('sha256',''))
            or sig['sha256']!=sig.get('sha256_after')):
        return 'SERVICE_DLL_SIGNATURE_UNVERIFIED'
    return None

def _classify_missing(row,evidence,roots):
    def blocked(code):return dict(status='UNRESOLVED',reason_code=code)
    try:
        if evidence.get('collection_error'):return blocked('PROCESS_EVIDENCE_UNAVAILABLE')
        if GRID.search(str(row.get('name',''))) or any(GRID.search(str((n or {}).get('path',''))) for n in (evidence.get('native_before'),evidence.get('native_after'))):
            return blocked('GRID_PROCESS_INDICATOR')
        pid=row['pid']
        if type(pid) is not int or pid<0:return blocked('PROCESS_ID_CONFLICT')
        if pid in (0,4):
            # The collector emits topology only for these PIDs. Contradictory
            # file/service proof cannot be silently bypassed by this shortcut.
            if set(evidence)-{'kernel_before','kernel_after','collection_error'}:
                return blocked('KERNEL_EVIDENCE_CONFLICT')
            refusal=snapshot_refusal(row,evidence)
            if refusal:return blocked(refusal)
            before=evidence.get('kernel_before',{});after=evidence.get('kernel_after',{})
            if not before or before!=after or before.get('pid')!=pid or before.get('parent_pid')!=0 or before.get('session_id')!=0 or row.get('parent_pid')!=0 or row.get('session_id')!=0:
                return blocked('KERNEL_IDENTITY_UNAVAILABLE')
            if pid==0:
                valid=before.get('name') in ('','Idle') and row.get('name')=='System Idle Process' and (same_creation(row.get('created'),before.get('created')) or (type(row.get('created')) is int and row['created']==before.get('created')==0))
            else:
                valid=before.get('name')=='System' and row.get('name')=='System' and same_creation(row.get('created'),before.get('created'))
            return dict(status='VERIFIED_KERNEL',reason_code='KERNEL_SNAPSHOT_IDENTITY') if valid else blocked('KERNEL_IDENTITY_CONFLICT')
        before=evidence.get('native_before');after=evidence.get('native_after')
        if any(not isinstance(n,dict) or not n or n.get('error_stage') not in ('','QUERY_IMAGE')
               or type(n.get('pid')) is not int or type(n.get('win32_error')) is not int
               or n['win32_error']<0 or type(n.get('path')) is not str
               or type(n.get('image_query_succeeded')) is not bool for n in (before,after)):
            return blocked('NATIVE_PROCESS_API_UNAVAILABLE')
        if any(n.get('pid')!=pid for n in (before,after)):return blocked('PROCESS_ID_CONFLICT')
        if any(n.get('alive') is not True for n in (before,after)):return blocked('PROCESS_NOT_ALIVE')
        if any(type(n.get('created')) is not int or n['created']<=0 for n in (row,before,after)):
            return blocked('PROCESS_CREATION_UNAVAILABLE')
        if before['created']!=after['created']:return blocked('PROCESS_CREATION_CHANGED')
        if any(not same_creation(row['created'],n['created']) for n in (before,after)):
            return blocked('CIM_CREATION_MISMATCH')
        if any(n.get('image_query_succeeded') is not True or not n.get('path') for n in (before,after)):
            if before!=after:return blocked('NATIVE_PROCESS_EVIDENCE_CHANGED')
            refusal=snapshot_refusal(row,evidence,before)
            if refusal:return blocked(refusal)
            # Even coherent native snapshots prove neither a non-file image nor
            # its kernel role. No arbitrary-PID exception is supported.
            return blocked('IMAGE_PATH_UNAVAILABLE')
        path=canonical(before.get('path'))
        if any(n['win32_error']!=0 or n['error_stage']!='' for n in (before,after)):
            return blocked('NATIVE_PROCESS_API_UNAVAILABLE')
        # File-backed identity needs no kernel-role exception, but any topology
        # supplied by the collector must still be complete and consistent.
        if 'kernel_before' in evidence or 'kernel_after' in evidence:
            refusal=snapshot_refusal(row,evidence,before)
            if refusal:return blocked(refusal)
        if not path or not canonical(after.get('path')):return blocked('IMAGE_PATH_INVALID')
        if path!=canonical(after['path']):return blocked('IMAGE_PATH_CHANGED')
        if ntpath.basename(path)!=str(row.get('name','')).casefold():return blocked('CIM_IMAGE_NAME_MISMATCH')
        if row.get('cim_path') and canonical(row['cim_path'])!=path:return blocked('CIM_IMAGE_PATH_MISMATCH')
        sig=evidence.get('signature',{})
        if sig.get('status')!='Valid':return blocked('IMAGE_SIGNATURE_UNVERIFIED')
        if canonical(sig.get('path'))!=path:return blocked('SIGNATURE_IMAGE_PATH_MISMATCH')
        subject=sig.get('subject')
        cn=re.search(r'(?:^|,\s*)CN=([^,]+)(?:,|$)',subject) if isinstance(subject,str) else None
        if not cn:return blocked('IMAGE_PUBLISHER_UNAVAILABLE')
        if sig.get('reparse_point') is not False:return blocked('IMAGE_REPARSE_UNVERIFIED')
        if not re.fullmatch('[0-9a-f]{64}',sig.get('sha256','')):return blocked('IMAGE_HASH_UNAVAILABLE')
        if sig['sha256']!=sig.get('sha256_after'):return blocked('IMAGE_HASH_CHANGED')
        # Services must satisfy the reviewed service rule even for System32.
        if evidence.get('services_before_complete') is not True or evidence.get('services_after_complete') is not True or 'services_before' not in evidence or 'services_after' not in evidence:
            return blocked('SERVICE_MEMBERSHIP_UNAVAILABLE')
        services=evidence['services_before'];after_services=evidence['services_after']
        if not isinstance(services,list) or not isinstance(after_services,list):return blocked('SERVICE_IDENTITY_UNAVAILABLE')
        for snapshot in (services,after_services):
            names=[s.get('name') for s in snapshot]
            if any(not isinstance(name,str) or not name for name in names):return blocked('SERVICE_IDENTITY_UNAVAILABLE')
            if len(names)!=len({name.casefold() for name in names}):return blocked('SERVICE_IDENTITY_UNAVAILABLE')
            # Validate both endpoints before equality: bool/float substitutions
            # can compare equal to genuine integer identity/status fields.
            for svc in snapshot:
                if svc.get('error_stage')!='' or type(svc.get('win32_error')) is not int or svc['win32_error']!=0:
                    return blocked('SERVICE_API_UNAVAILABLE')
                if type(svc.get('pid')) is not int or type(svc.get('state')) is not int:
                    return blocked('SERVICE_IDENTITY_UNAVAILABLE')
                if svc['name'] in WINDOWS_SERVICE_CONTRACTS and type(svc.get('service_type')) is not int:
                    return blocked('SERVICE_IDENTITY_UNAVAILABLE')
        known_service_image=any(path==canonical(ntpath.join(roots[root],relative)) for root,relative,_ in SERVICE_RULES.values())
        # Hosts covered by implementation contracts cannot bypass those contracts
        # through the generic signed-System32 fallback when SCM reports no service.
        known_service_image=known_service_image or any(path==canonical(ntpath.join(roots['system32'],host)) for host,_,_,_,_ in WINDOWS_SERVICE_CONTRACTS.values())
        if known_service_image and not services:return blocked('SERVICE_IDENTITY_UNAVAILABLE')
        if services or after_services:
            if sorted(s['name'] for s in services)!=sorted(s['name'] for s in after_services):return blocked('SERVICE_MEMBERSHIP_CHANGED')
            for first,last in zip(sorted(services,key=lambda s:s['name']),sorted(after_services,key=lambda s:s['name'])):
                if first.get('pid')!=last.get('pid'):return blocked('SERVICE_PID_CHANGED')
                if first.get('state')!=last.get('state'):return blocked('SERVICE_STATE_CHANGED')
                if first.get('binary_path')!=last.get('binary_path'):return blocked('SERVICE_CONFIGURATION_CHANGED')
                if first!=last:return blocked('SERVICE_EVIDENCE_CHANGED')
            for svc in services:
                rule=SERVICE_RULES.get(svc.get('name'))
                contract=svc.get('name') in WINDOWS_SERVICE_CONTRACTS
                if not rule and not contract:return blocked('SERVICE_RULE_UNREVIEWED')
                if svc.get('pid')!=pid:return blocked('SERVICE_PID_MISMATCH')
                if svc.get('state')!=4:return blocked('SERVICE_NOT_RUNNING')
                configured=command_executable(svc.get('binary_path'))
                if not configured:return blocked('SERVICE_CONFIG_PATH_INVALID')
                if configured!=path:return blocked('SERVICE_CONFIG_IMAGE_MISMATCH')
                if contract:
                    if cn[1] not in WINDOWS_PUBLISHERS:return blocked('SERVICE_PUBLISHER_NOT_REVIEWED')
                    refusal=service_implementation_refusal(svc,evidence,roots,before)
                    if refusal:return blocked(refusal)
                    continue
                root,relative,publishers=rule
                if path!=canonical(ntpath.join(roots[root],relative)):return blocked('SERVICE_IMAGE_NOT_REVIEWED')
                if cn[1] not in publishers:return blocked('SERVICE_PUBLISHER_NOT_REVIEWED')
            return dict(status='VERIFIED_SERVICE',reason_code='NATIVE_SCM_SIGNED_IMAGE',resolved_path=before['path'])
        if ntpath.dirname(path)==canonical(roots['system32']):
            if cn[1] not in WINDOWS_PUBLISHERS:return blocked('SYSTEM_IMAGE_PUBLISHER_NOT_REVIEWED')
            return dict(status='VERIFIED_SYSTEM_IMAGE',reason_code='NATIVE_SIGNED_SYSTEM_IMAGE',resolved_path=before['path'])
        return blocked('UNREVIEWED_PROCESS_IMAGE')
    except (KeyError,TypeError,ValueError,AttributeError):
        return blocked('PROCESS_EVIDENCE_UNAVAILABLE')

PUBLIC_PROCESS_REASONS=frozenset('PROCESS_INVENTORY_SCHEMA_INVALID '.split()) | frozenset('CIM_CREATION_MISMATCH CIM_IMAGE_NAME_MISMATCH CIM_IMAGE_PATH_MISMATCH DUPLICATE_PROCESS_ID GRID_PROCESS_INDICATOR IMAGE_HASH_CHANGED IMAGE_HASH_UNAVAILABLE IMAGE_PATH_CHANGED IMAGE_PATH_INVALID IMAGE_PATH_UNAVAILABLE IMAGE_PUBLISHER_UNAVAILABLE IMAGE_REPARSE_UNVERIFIED IMAGE_SIGNATURE_UNVERIFIED KERNEL_EVIDENCE_CONFLICT KERNEL_IDENTITY_CONFLICT KERNEL_IDENTITY_UNAVAILABLE NATIVE_PROCESS_API_UNAVAILABLE NATIVE_PROCESS_EVIDENCE_CHANGED PROCESS_CREATION_CHANGED PROCESS_CREATION_UNAVAILABLE PROCESS_EVIDENCE_SCHEMA_INVALID PROCESS_EVIDENCE_UNAVAILABLE PROCESS_ID_CONFLICT PROCESS_INVENTORY_COVERAGE_MISMATCH PROCESS_NOT_ALIVE SERVICE_API_UNAVAILABLE SERVICE_CONFIGURATION_CHANGED SERVICE_CONFIG_IMAGE_MISMATCH SERVICE_CONFIG_PATH_INVALID SERVICE_DLL_CONFIGURATION_UNREVIEWED SERVICE_DLL_SIGNATURE_UNVERIFIED SERVICE_EVIDENCE_CHANGED SERVICE_HOST_CONFIGURATION_UNREVIEWED SERVICE_IDENTITY_UNAVAILABLE SERVICE_IMAGE_NOT_REVIEWED SERVICE_IMPLEMENTATION_CHANGED SERVICE_IMPLEMENTATION_NOT_LOADED SERVICE_IMPLEMENTATION_UNVERIFIED SERVICE_MEMBERSHIP_CHANGED SERVICE_MEMBERSHIP_UNAVAILABLE SERVICE_MODULES_CHANGED SERVICE_MODULES_UNAVAILABLE SERVICE_MODULE_LIFETIME_MISMATCH SERVICE_NOT_RUNNING SERVICE_PID_CHANGED SERVICE_PID_MISMATCH SERVICE_PUBLISHER_NOT_REVIEWED SERVICE_RULE_UNREVIEWED SERVICE_STATE_CHANGED SIGNATURE_IMAGE_PATH_MISMATCH SYSTEM_IMAGE_PUBLISHER_NOT_REVIEWED UNREVIEWED_PROCESS_IMAGE'.split())


def classify_missing(row,evidence,roots):
    try:
        from evidence_schema import json_value
        json_value(row);json_value(evidence);json_value(roots)
        result=_classify_missing(row,evidence,roots)
    except (KeyError,TypeError,ValueError,AttributeError,OverflowError,RecursionError):
        return dict(status='UNRESOLVED',reason_code='PROCESS_EVIDENCE_SCHEMA_INVALID')
    if result['status'].startswith('VERIFIED_'):
        try:
            from evidence_schema import validate_success
            validate_success(row,evidence,roots)
        except (KeyError,TypeError,ValueError,AttributeError,OverflowError):
            return dict(status='UNRESOLVED',reason_code='PROCESS_EVIDENCE_SCHEMA_INVALID')
    return result


def _assess_processes(rows,roots,expected_missing_pids):
    # Coverage equality must not alias JSON floats/bools to native integer PIDs.
    if (not isinstance(expected_missing_pids,list) or
            any(type(pid) is not int or not 0<=pid<=0x7fffffff for pid in expected_missing_pids)):
        raise ValueError('PROCESS_INVENTORY_EXPECTED_IDS_INVALID')
    results=[]
    seen=set()
    for item in rows:
        row=item['process'];pid=row.get('pid')
        result=classify_missing(row,item.get('evidence',{}),roots)
        if pid in seen:result=dict(status='UNRESOLVED',reason_code='DUPLICATE_PROCESS_ID')
        seen.add(pid)
        results.append(dict(process=row,assessment=result))
    unresolved=[r for r in results if r['assessment']['status']=='UNRESOLVED']
    reasons={}
    for r in unresolved:
        code=r['assessment']['reason_code'];reasons[code]=reasons.get(code,0)+1
    expected=list(expected_missing_pids)
    mismatch=len(rows)!=len(expected) or len(expected)!=len(set(expected)) or seen!=set(expected)
    if mismatch:reasons['PROCESS_INVENTORY_COVERAGE_MISMATCH']=1
    return dict(results=results,missing_process_paths=len(expected),verified_missing_process_paths=len(results)-len(unresolved),unknown_process_paths=len(unresolved)+int(mismatch),reason_counts=reasons)

def assess_processes(rows,roots,expected_missing_pids):
    try:
        if type(rows) is not list:raise ValueError('PROCESS_INVENTORY_SCHEMA_INVALID')
        return _assess_processes(rows,roots,expected_missing_pids)
    except (KeyError,TypeError,ValueError,AttributeError,OverflowError):
        return dict(results=[],missing_process_paths=0,verified_missing_process_paths=0,
                    unknown_process_paths=1,reason_counts={'PROCESS_INVENTORY_SCHEMA_INVALID':1})


def snapshot_refusal(row,evidence,native=None):
    """Check lifetime/topology only; no general kernel identity is established.

    Names and additional characteristics are never admission predicates. Require
    their stability, but do not infer identity from a label or an API failure.
    """
    snapshots=[evidence.get(key) for key in ('kernel_before','kernel_after')]
    for item in (row,*snapshots):
        if not isinstance(item,dict):return 'KERNEL_IDENTITY_UNAVAILABLE'
        if any(type(item.get(k)) is not int or not 0<=item[k]<=0x7fffffff
               for k in ('pid','parent_pid','session_id')):
            return 'KERNEL_IDENTITY_UNAVAILABLE'
        if type(item.get('created')) is not int or not 0<=item['created']<=0x7fffffffffffffff:
            return 'KERNEL_IDENTITY_UNAVAILABLE'
        if type(item.get('name')) is not str:return 'KERNEL_IDENTITY_UNAVAILABLE'
    first,last=snapshots
    if first!=last:return 'KERNEL_IDENTITY_CONFLICT'
    if any(first[k]!=row[k] for k in ('pid','parent_pid','session_id')):
        return 'KERNEL_IDENTITY_CONFLICT'
    if native is not None and (first['pid']!=native['pid'] or first['created']!=native['created']
                               or not same_creation(row['created'],first['created'])
                               or first['name'].casefold()!=row['name'].casefold()):
        return 'KERNEL_IDENTITY_CONFLICT'
    return None
