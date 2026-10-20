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
GRID=re.compile(r'grid|^(?:coordinator|worker|collector)(?:\.exe)?$',re.I)

def canonical(path):
    if not isinstance(path,str) or not ntpath.isabs(path) or path.startswith(('\\\\','\\??\\')):
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

def classify_missing(row,evidence,roots):
    def blocked(code):return dict(status='UNRESOLVED',reason_code=code)
    try:
        if evidence.get('collection_error'):return blocked('PROCESS_EVIDENCE_UNAVAILABLE')
        if GRID.search(str(row.get('name',''))) or any(GRID.search(str(n.get('path',''))) for n in (evidence.get('native_before',{}),evidence.get('native_after',{}))):
            return blocked('GRID_PROCESS_INDICATOR')
        pid=row['pid']
        if type(pid) is not int or pid<0:return blocked('PROCESS_ID_CONFLICT')
        if pid in (0,4):
            before=evidence.get('kernel_before',{});after=evidence.get('kernel_after',{})
            if not before or before!=after or before.get('pid')!=pid or before.get('parent_pid')!=0 or before.get('session_id')!=0 or row.get('parent_pid')!=0 or row.get('session_id')!=0:
                return blocked('KERNEL_IDENTITY_UNAVAILABLE')
            if pid==0:
                valid=before.get('name') in ('','Idle') and row.get('name')=='System Idle Process' and (same_creation(row.get('created'),before.get('created')) or (type(row.get('created')) is int and row['created']==before.get('created')==0))
            else:
                valid=before.get('name')=='System' and row.get('name')=='System' and same_creation(row.get('created'),before.get('created'))
            return dict(status='VERIFIED_KERNEL',reason_code='KERNEL_SNAPSHOT_IDENTITY') if valid else blocked('KERNEL_IDENTITY_CONFLICT')
        before=evidence.get('native_before',{});after=evidence.get('native_after',{})
        if any(n.get('pid')!=pid or n.get('alive') is not True or not same_creation(row.get('created'),n.get('created')) for n in (before,after)):
            return blocked('PROCESS_LIFETIME_UNAVAILABLE_OR_CHANGED')
        if before['created']!=after['created']:return blocked('PROCESS_LIFETIME_UNAVAILABLE_OR_CHANGED')
        path=canonical(before.get('path'))
        if not path or path!=canonical(after.get('path')) or ntpath.basename(path)!=str(row.get('name','')).casefold():
            return blocked('PROCESS_IMAGE_CONFLICT')
        sig=evidence.get('signature',{})
        cn=re.search(r'(?:^|,\s*)CN=([^,]+)(?:,|$)',sig.get('subject',''))
        if sig.get('status')!='Valid' or canonical(sig.get('path'))!=path or not cn or sig.get('reparse_point') is not False or not re.fullmatch('[0-9a-f]{64}',sig.get('sha256','')) or sig['sha256']!=sig.get('sha256_after'):
            return blocked('IMAGE_SIGNATURE_OR_FILE_IDENTITY_UNVERIFIED')
        # Services must satisfy the reviewed service rule even for System32.
        if evidence.get('services_before_complete') is not True or evidence.get('services_after_complete') is not True or 'services_before' not in evidence or 'services_after' not in evidence:
            return blocked('SERVICE_MEMBERSHIP_UNAVAILABLE')
        services=evidence['services_before'];after_services=evidence['services_after']
        if not isinstance(services,list) or not isinstance(after_services,list):return blocked('SERVICE_IDENTITY_UNAVAILABLE')
        known_service_image=any(path==canonical(ntpath.join(roots[root],relative)) for root,relative,_ in SERVICE_RULES.values())
        if known_service_image and not services:return blocked('SERVICE_IDENTITY_UNAVAILABLE')
        if services or after_services:
            if sorted(services,key=lambda s:s['name'])!=sorted(after_services,key=lambda s:s['name']):return blocked('SERVICE_IDENTITY_CHANGED')
            for svc in services:
                rule=SERVICE_RULES.get(svc.get('name'))
                if not rule or svc.get('pid')!=pid or svc.get('state')!=4 or command_executable(svc.get('binary_path'))!=path:
                    return blocked('SERVICE_IDENTITY_CONFLICT')
                root,relative,publishers=rule
                if path!=canonical(ntpath.join(roots[root],relative)) or cn[1] not in publishers:
                    return blocked('SERVICE_IMAGE_NOT_REVIEWED')
            return dict(status='VERIFIED_SERVICE',reason_code='NATIVE_SCM_SIGNED_IMAGE',resolved_path=before['path'])
        if ntpath.dirname(path)==canonical(roots['system32']) and cn[1] in WINDOWS_PUBLISHERS:
            return dict(status='VERIFIED_SYSTEM_IMAGE',reason_code='NATIVE_SIGNED_SYSTEM_IMAGE',resolved_path=before['path'])
        return blocked('UNREVIEWED_PROCESS_IMAGE')
    except (KeyError,TypeError,ValueError,AttributeError):
        return blocked('PROCESS_EVIDENCE_UNAVAILABLE')

def assess_processes(rows,roots,expected_missing_pids):
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
