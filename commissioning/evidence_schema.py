"""Pure schema and cross-stage consistency checks; no OS access or persistence.

The classifier still decides trust. This gate rejects impossible/partial inputs
before any otherwise successful classification can be consumed.
"""
from datetime import datetime, timezone
import ntpath
import re
import math
import json

PID_MAX=0x7fffffff
TIME_MAX=0x7fffffffffffffff
DWORD_MAX=0xffffffff


def need(condition):
    if not condition: raise ValueError('PROCESS_EVIDENCE_SCHEMA_INVALID')


def integer(value, maximum=PID_MAX, minimum=0):
    need(type(value) is int and minimum<=value<=maximum)


def text(value, empty=True):
    need(type(value) is str and (empty or bool(value)) and not any(c in value for c in ('\x00','\r','\n')))


def record(value, fields):
    need(type(value) is dict and set(fields)<=set(value))


def json_value(value, depth=0):
    need(depth<=40)
    if value is None or type(value) in (str,bool,int):return
    if type(value) is float:need(math.isfinite(value));return
    if type(value) is list:
        for item in value:json_value(item,depth+1)
        return
    need(type(value) is dict and all(type(key) is str for key in value))
    for item in value.values():json_value(item,depth+1)


def strict_loads(payload):
    def unique(pairs):
        result={}
        for key,value in pairs:need(key not in result);result[key]=value
        return result
    value=json.loads(payload,object_pairs_hook=unique)
    json_value(value)
    return value


def row(value):
    record(value,('pid','name','created','parent_pid','session_id'))
    for key in ('pid','parent_pid','session_id'): integer(value[key])
    integer(value['created'],TIME_MAX,0 if value['pid']==0 else 1)
    text(value['name'],False)
    need(value.get('cim_path') is None or type(value['cim_path']) is str)


def expanded(raw,roots):
    text(raw)
    values={'systemroot':ntpath.dirname(roots['system32']), 'windir':ntpath.dirname(roots['system32']),
            'systemdrive':ntpath.splitdrive(roots['system32'])[0], 'programfiles':roots['program_files']}
    def replace(match):
        need(match[1].casefold() in values)
        return values[match[1].casefold()]
    value=re.sub(r'%([^%]+)%',replace,raw)
    need('%' not in value)
    return value


def signature(value):
    record(value,('path','status','subject','sha256','sha256_after','reparse_point'))
    for key in ('path','status','subject'): text(value[key],False)
    need(type(value['reparse_point']) is bool)
    for key in ('sha256','sha256_after'):need(type(value[key]) is str and re.fullmatch('[0-9a-f]{64}',value[key]) is not None)
    need(value['sha256']==value['sha256_after'])
    need(set(value)=={'path','status','subject','sha256','sha256_after','reparse_point'})


def validate_success(process,evidence,roots):
    import process_identity as p
    json_value(process);json_value(evidence);json_value(roots);row(process)
    record(roots,('system32','program_files'))
    need(set(roots)=={'system32','program_files'})
    for value in roots.values():need(type(value) is str and bool(p.canonical(value)))
    need(type(evidence) is dict)
    need(set(process)<={'pid','name','created','parent_pid','session_id','cim_path'})
    fields={'collection_error','signature','native_before','native_after','kernel_before','kernel_after',
            'implementation_signatures'}
    for suffix in ('before','after'):
        fields.update({'services_'+suffix,'services_'+suffix+'_complete','services_'+suffix+'_reason',
                       'services_'+suffix+'_diagnostics','modules_'+suffix,'implementation_'+suffix})
    need(set(evidence)<=fields)
    for suffix in ('before','after'):
        if 'kernel_'+suffix in evidence:
            need(set(evidence['kernel_'+suffix])=={'pid','name','created','parent_pid','session_id'})
    if 'collection_error' in evidence:need(evidence['collection_error']=='')
    if process['pid'] in (0,4):return
    for suffix in ('before','after'):
        native=evidence['native_'+suffix]
        record(native,('pid','path','created','alive','image_query_succeeded','error_stage','win32_error'))
        need(set(native)<={'pid','path','created','alive','image_query_succeeded','error_stage','win32_error',
                           'native_format_path','native_format_query_succeeded','native_format_win32_error'})
        integer(native['pid']);integer(native['created'],TIME_MAX,1);integer(native['win32_error'],DWORD_MAX)
        text(native['path'],False);text(native['error_stage'])
        need(type(native['alive']) is bool and type(native['image_query_succeeded']) is bool)
        fields={'native_format_path','native_format_query_succeeded','native_format_win32_error'}
        if fields&set(native):
            record(native,fields)
            text(native['native_format_path']);need(type(native['native_format_query_succeeded']) is bool)
            integer(native['native_format_win32_error'],DWORD_MAX)
            # ReadProcess queries diagnostic native-format only after image-query failure.
            need(native['native_format_path']=='' and native['native_format_query_succeeded'] is False and native['native_format_win32_error']==0)
        need(native['pid']==process['pid'] and native['created']//10==process['created']//10)
        # Full Unicode casefold can expand distinct filenames (e.g. ß -> ss).
        # Match the same lower-based convention used by canonical paths.
        need(ntpath.basename(p.canonical(native['path']))==process['name'].lower())
    need(evidence['native_before']==evidence['native_after'])
    signature(evidence['signature'])
    reviewed={item['name'] for item in evidence['services_before'] if item['name'] in p.WINDOWS_SERVICE_CONTRACTS}
    implementation_fields={'modules_before','modules_after','implementation_before','implementation_after','implementation_signatures'}
    if not reviewed:need(not (implementation_fields&set(evidence)))
    else:
        need(implementation_fields<=set(evidence))
        for key in ('implementation_before','implementation_after','implementation_signatures'):
            need(type(evidence[key]) is dict and set(evidence[key])==reviewed)
    for suffix in ('before','after'):
        services=evidence['services_'+suffix];need(type(services) is list)
        reason='services_'+suffix+'_reason';diagnostic='services_'+suffix+'_diagnostics'
        if reason in evidence or diagnostic in evidence:
            need(evidence.get(reason)=='COMPLETE_REGISTRY_SCM_COVERAGE')
            d=evidence.get(diagnostic);record(d,('stage','win32_error','failed_service'))
            need(set(d)=={'stage','win32_error','failed_service'})
            need(d['stage']=='' and d['failed_service']=='');integer(d['win32_error'],DWORD_MAX);need(d['win32_error']==0)
        for service in services:
            record(service,('name','pid','state','binary_path','error_stage','win32_error'))
            for key in ('name','binary_path'):text(service[key],False)
            need(set(service)<={'name','pid','state','binary_path','error_stage','win32_error','service_type','start_name'})
            integer(service['pid']);integer(service['state'],7,1);integer(service['win32_error'],DWORD_MAX)
            need(service['error_stage']=='')
            if 'service_type' in service:integer(service['service_type'],DWORD_MAX)
            if 'start_name' in service:text(service['start_name'],False)
            name=service['name']
            if name not in p.WINDOWS_SERVICE_CONTRACTS:continue
            record(service,('service_type','start_name'))
            config=evidence['implementation_'+suffix][name]
            fields=('complete','name','error_stage','image_path','expanded_image_path','service_type','account',
                    'dll_present','dll_path','expanded_dll_path','dll_source')
            record(config,fields)
            need(set(config)==set(fields))
            need(config['complete'] is True and type(config['dll_present']) is bool)
            integer(config['service_type'],DWORD_MAX)
            for key in fields:
                if key not in ('complete','dll_present','service_type'):text(config[key])
            raw_image=expanded(config['image_path'],roots)
            need(config['account'].isascii() and service['start_name'].isascii())
            need(p.command_argument_text(config['expanded_image_path']).isascii())
            need(p.command_argument_text(service['binary_path']).isascii())
            need(p.command_argument_text(raw_image).isascii())
            need(p.command_executable(raw_image)==p.command_executable(config['expanded_image_path']) and
                 p.command_arguments(raw_image)==p.command_arguments(config['expanded_image_path']))
            if config['dll_present']:
                need(p.canonical(expanded(config['dll_path'],roots))==p.canonical(config['expanded_dll_path']))
            else:need(config['dll_path']==config['expanded_dll_path']=='')
            modules=evidence['modules_'+suffix]
            record(modules,('pid','created','alive','complete','paths','error_stage','win32_error'))
            need(set(modules)=={'pid','created','alive','complete','paths','error_stage','win32_error'})
            integer(modules['pid']);integer(modules['created'],TIME_MAX,1);integer(modules['win32_error'],DWORD_MAX)
            need(type(modules['alive']) is bool and type(modules['complete']) is bool and modules['error_stage']=='')
            need(type(modules['paths']) is list and all(type(v) is str and bool(p.canonical(v)) for v in modules['paths']))
            signature(evidence['implementation_signatures'][name])


def validate_source_snapshot(original,records,roots,system_directory):
    import process_identity as p
    need(type(original) is list and bool(original) and type(records) is list)
    record(roots,('system32','program_files'))
    need(set(roots)=={'system32','program_files'})
    need(all(type(v) is str and bool(p.canonical(v)) for v in roots.values()))
    need(p.canonical(roots['system32'])==p.canonical(str(system_directory)))
    by_pid={}
    for item in original:
        record(item,('ProcessId','Name','ParentProcessId','SessionId','ExecutablePath','CreationFileTime','CreationDate'))
        need(set(item)=={'ProcessId','Name','ParentProcessId','SessionId','ExecutablePath','CreationFileTime','CreationDate'})
        for key in ('ProcessId','ParentProcessId','SessionId'):integer(item[key])
        need(item['ProcessId'] not in by_pid);by_pid[item['ProcessId']]=item
        text(item['Name'],False);integer(item['CreationFileTime'],TIME_MAX,0 if item['ProcessId']==0 else 1)
        need(item['ExecutablePath'] is None or type(item['ExecutablePath']) is str)
        if item['ExecutablePath']:need(bool(p.canonical(item['ExecutablePath'])))
        if item['CreationDate'] is None:need(item['ProcessId']==0 and item['CreationFileTime']==0)
        else:
            text(item['CreationDate'],False)
            date=datetime.fromisoformat(item['CreationDate'].replace('Z','+00:00'))
            need(date.tzinfo is not None)
            delta=date.astimezone(timezone.utc)-datetime(1601,1,1,tzinfo=timezone.utc)
            ticks=(delta.days*86400+delta.seconds)*10000000+delta.microseconds*10
            need(ticks//10==item['CreationFileTime']//10)
    for item in records:
        record(item,('process','evidence'));process=item['process'];row(process)
        source=by_pid.get(process['pid']);need(source is not None and not source['ExecutablePath'])
        need(process['name']==source['Name'] and process['parent_pid']==source['ParentProcessId'] and
             process['session_id']==source['SessionId'] and process['created']==source['CreationFileTime'] and
             process.get('cim_path')==source['ExecutablePath'])


def validate_public(facts):
    json_value(facts)
    record(facts,('grid','os'))
    grid=facts['grid'];os=facts['os'];record(os,('system','edition','build'))
    need(os['system']=='Windows')
    need(type(os['edition']) is str and os['edition'] in {'Professional','ProfessionalN','ProfessionalEducation','ProfessionalEducationN',
        'ProfessionalWorkstation','ProfessionalWorkstationN','ProfessionalSingleLanguage','ProfessionalCountrySpecific'})
    integer(os['build'],PID_MAX,22000)
    record(grid,('coverage_complete','errors','findings'))
    need(type(grid['coverage_complete']) is bool)
    for key in ('errors','findings'):
        need(type(grid[key]) is list and all(type(value) is str for value in grid[key]))
    for key in ('visible_services','visible_tasks','visible_processes','missing_process_paths',
                'verified_missing_process_paths','unknown_process_paths'):
        if key in grid:integer(grid[key])
    counts={'missing_process_paths','verified_missing_process_paths','unknown_process_paths'}
    if counts&set(grid):
        need(counts<=set(grid))
        need(grid['verified_missing_process_paths']<=grid['missing_process_paths'])
        need(grid['verified_missing_process_paths']+grid['unknown_process_paths']>=grid['missing_process_paths'])
    if 'reason_counts' in grid:
        from process_identity import PUBLIC_PROCESS_REASONS
        need(type(grid['reason_counts']) is dict)
        for key,value in grid['reason_counts'].items():need(key in PUBLIC_PROCESS_REASONS);integer(value,PID_MAX,1)
        if grid.get('unknown_process_paths')==0:need(not grid['reason_counts'])
    for key in ('credential_names','production_dsn_names'):
        if key in facts:need(type(facts[key]) is list and all(type(v) is str for v in facts[key]))
    if 'identity' in facts:
        record(facts['identity'],('hostname','username','sid','machine_guid','install_id','hardware_uuid'))
        for value in facts['identity'].values():text(value,False)
    need(type(facts.get('postgres_listeners',[])) is list)
    need(type(facts.get('api_listeners',[])) is list)
    for item in facts.get('postgres_listeners',[]):
        record(item,('port','address'));integer(item['port'],65535,1)
        need(item['address'] in ('127.0.0.1','::1','0.0.0.0','::'))
