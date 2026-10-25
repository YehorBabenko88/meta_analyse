"""R0-R5 one-shot diagnostics. Always FAIL_CLOSED; never authorization."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import subprocess
import sys

import evidence_schema as schema
import host_identity as host
import process_identity as identity

ROOT=Path(__file__).resolve().parents[1]
STAGES=frozenset(('OPEN_PROCESS GET_PROCESS_TIMES GET_EXIT_CODE QUERY_IMAGE OPEN_PROCESS_MODULES '
    'MODULE_PROCESS_TIMES MODULE_EXIT_CODE ENUM_MODULES MODULE_COUNT_INVALID MODULE_PATH '
    'MODULE_PATH_TRUNCATED ENUM_MODULES_AFTER MODULE_LIST_CHANGED').split())
EARLY=frozenset('OPEN_PROCESS GET_PROCESS_TIMES GET_EXIT_CODE OPEN_PROCESS_MODULES MODULE_PROCESS_TIMES MODULE_EXIT_CODE'.split())
ERRORS={0:'NONE',5:'ACCESS_DENIED',31:'GEN_FAILURE',87:'INVALID_PARAMETER',122:'INSUFFICIENT_BUFFER',299:'PARTIAL_COPY'}
CHECKS=('CONFIG_MEMBER_MATCH','REGISTRY_TYPE_REVIEWED','SCM_TYPE_REVIEWED','REGISTRY_ACCOUNT_MATCH',
        'SCM_ACCOUNT_MATCH','REGISTRY_IMAGE_MATCH','REGISTRY_ARGS_MATCH','SCM_ARGS_MATCH')
COOCCURRENCE=('BOTH_FAILED','REGISTRY_ONLY_FAILED','SCM_ONLY_FAILED','NEITHER_FAILED','NOT_EVALUATED')
SAFE_ERRORS=frozenset(('SOURCE_BINDING_INVALID EVIDENCE_INVALID LIFETIME_BINDING_INVALID ARGUMENTS_INVALID '
    'OUTPUT_UNAVAILABLE COLLECTOR_UNAVAILABLE ELEVATED_TOKEN_REQUIRED COLLECTOR_CHILD_BLOCKED '
    'PROCESS_INVENTORY_SNAPSHOT_INVALID PROCESS_SNAPSHOT_BINDING_INVALID').split())


class AdapterError(ValueError):
    def __init__(self,code='EVIDENCE_INVALID'):
        self.code=code if type(code) is str and code in SAFE_ERRORS else 'EVIDENCE_INVALID'
        super().__init__(self.code)


def require(ok,code='EVIDENCE_INVALID'):
    if not ok:raise AdapterError(code)


def source_binding(sha,tree):
    try:
        require(type(sha) is str and re.fullmatch('[0-9a-f]{40}',sha) is not None)
        require(type(tree) is str and re.fullmatch('[0-9a-f]{40}',tree) is not None)
        def git(*args):
            return subprocess.check_output(['git','-C',str(ROOT),*args],stderr=subprocess.DEVNULL,timeout=10).decode().strip()
        require(git('rev-parse','HEAD')==sha and git('rev-parse','HEAD^{tree}')==tree)
        collector=host.collector_identity(sha,root=ROOT)
        return dict(sha=sha,tree=tree,collector=collector)
    except BaseException:
        raise AdapterError('SOURCE_BINDING_INVALID') from None


def endpoint(proof,key,row,native_times,kind,applicable=True):
    if not applicable:return ('NOT_APPLICABLE',None,'NOT_OBSERVED','NOT_OBSERVED')
    if key not in proof:return ('NOT_OBSERVED',None,'NOT_OBSERVED','NOT_OBSERVED')
    item=proof[key];require(type(item) is dict)
    schema.record(item,('pid','created','alive','error_stage','win32_error'))
    schema.integer(item['pid']);schema.integer(item['created'],schema.TIME_MAX)
    schema.integer(item['win32_error'],schema.DWORD_MAX)
    require(type(item['alive']) is bool and type(item['error_stage']) is str)
    require(item['pid']==row['pid'],'LIFETIME_BINDING_INVALID')
    if item['created']:
        require(identity.same_creation(item['created'],row['created']),'LIFETIME_BINDING_INVALID')
        if native_times:require(item['created']==native_times[0],'LIFETIME_BINDING_INVALID')
        lifetime='MATCHED'
    else:
        require(item['error_stage'] in EARLY,'LIFETIME_BINDING_INVALID');lifetime='NOT_OBSERVED'
    if kind=='native':
        require(type(item.get('path')) is str and type(item.get('image_query_succeeded')) is bool)
        stage='REPORTED_SUCCESS' if item['image_query_succeeded'] and item['path'] else 'EMPTY_IMAGE'
    else:
        require(type(item.get('complete')) is bool and type(item.get('paths')) is list)
        require(len(item['paths'])<=65536 and all(type(path) is str and bool(identity.canonical(path)) for path in item['paths']))
        if item['complete']:require(item['created']>0 and bool(item['paths']))
        stage='REPORTED_COMPLETE' if item['complete'] else 'INCOMPLETE_WITHOUT_STAGE'
    if item['error_stage']:stage=item['error_stage'] if item['error_stage'] in STAGES else 'OTHER'
    # Early failures precede the producer's assignment of alive; false is a default, not an observation.
    alive='NOT_OBSERVED' if item['error_stage'] in EARLY else 'ALIVE' if item['alive'] else 'NOT_ALIVE'
    return stage,ERRORS.get(item['win32_error'],'OTHER'),lifetime,alive


def add_endpoint(target,value):
    stage,error,lifetime,alive=value
    target['stage_counts'][stage]+=1
    if error is not None:target['error_counts'][error]+=1
    target['lifetime_counts'][lifetime]+=1
    target['alive_counts'][alive]+=1


def configuration_counts():
    return dict(member_checks=0,checks={key:dict(PASS=0,FAIL=0,NOT_EVALUATED=0) for key in CHECKS},
                type_cooccurrence={key:0 for key in COOCCURRENCE})


def paired_configuration(proof):
    # No per-member join leaves this boundary. Order is irrelevant, membership/config drift is not.
    reviewed=set()
    for phase in ('before','after'):
        services=proof.get('services_'+phase,[])
        require(type(services) is list and len(services)<=65536)
        for service in services:
            require(type(service) is dict and type(service.get('name')) is str)
            if service['name'] in identity.WINDOWS_SERVICE_CONTRACTS:reviewed.add(service['name'])
    if not reviewed:return
    members=[];configs=[];coverage=[]
    for phase in ('before','after'):
        services=proof.get('services_'+phase);require(type(services) is list)
        by_name={service['name']:service for service in services}
        require(len(by_name)==len(services))
        complete=proof.get('services_'+phase+'_complete');require(type(complete) is bool)
        config=proof.get('implementation_'+phase,{})
        require(type(config) is dict and set(config)<=reviewed)
        members.append(by_name);configs.append(config);coverage.append(complete)
    require(members[0]==members[1] and configs[0]==configs[1] and coverage[0]==coverage[1])


def config_checks(proof,phase,roots,row,target):
    key='services_'+phase
    if key not in proof:return
    services=proof[key];require(type(services) is list and len(services)<=65536)
    configs=proof.get('implementation_'+phase,{})
    require(type(configs) is dict)
    seen=set()
    for service in services:
        schema.record(service,('name','pid','state','binary_path','error_stage','win32_error'))
        name=service['name'];require(type(name) is str and bool(name) and name.casefold() not in seen)
        seen.add(name.casefold());schema.integer(service['pid']);schema.integer(service['state'],7,1)
        schema.integer(service['win32_error'],schema.DWORD_MAX)
        require(service['pid']==row['pid'],'LIFETIME_BINDING_INVALID')
        require(type(service['binary_path']) is str and type(service['error_stage']) is str)
        if name not in identity.WINDOWS_SERVICE_CONTRACTS:continue
        schema.integer(service['service_type'],schema.DWORD_MAX);require(type(service['start_name']) is str)
        target['member_checks']+=1
        checks=None
        if name in configs:
            c=configs[name];require(type(c) is dict and type(c.get('complete')) is bool and type(c.get('error_stage')) is str)
            schema.integer(c['service_type'],schema.DWORD_MAX)
            for field in ('name','account','expanded_image_path','image_path'):require(type(c.get(field)) is str)
            if c['complete'] and c['error_stage']=='':checks=identity.service_host_configuration_checks(service,c,roots)
        if checks is not None:
            require(type(checks) is dict and set(checks)==set(CHECKS) and all(type(value) is bool for value in checks.values()))
        category='NOT_EVALUATED'
        if checks is not None and proof['services_'+phase+'_complete'] and service['error_stage']=='' and service['win32_error']==0:
            registry_failed=not checks['REGISTRY_TYPE_REVIEWED'];scm_failed=not checks['SCM_TYPE_REVIEWED']
            category='BOTH_FAILED' if registry_failed and scm_failed else 'REGISTRY_ONLY_FAILED' if registry_failed else 'SCM_ONLY_FAILED' if scm_failed else 'NEITHER_FAILED'
        target['type_cooccurrence'][category]+=1
        for field in CHECKS:
            target['checks'][field]['NOT_EVALUATED' if checks is None else 'PASS' if checks[field] else 'FAIL']+=1


def _project(facts):
    # Reuse existing schema/aggregate validation, never classify or assess again.
    summary=host.inventory_refusal_projection(facts,'INCOMPLETE_INVENTORY')
    private=facts['private_inventory'];original=private['processes'];records=private['process_evidence'];roots=private['process_roots']
    require(type(records) is list and len(records)<=65536 and type(original) is list and len(original)<=65536)
    schema.validate_source_snapshot(original,records,roots,roots['system32'])
    expected={r['ProcessId'] for r in original if not r['ExecutablePath']}
    by_id={}
    for item in records:
        row=item['process'];schema.row(row)
        require(row['pid'] not in by_id);by_id[row['pid']]=item
    require(set(by_id)==expected)
    results=facts['process_inventory']['results'];require(type(results) is list and len(results)==len(records))
    observed=set();reasons=Counter();unresolved=[]
    valid={'VERIFIED_KERNEL':'KERNEL_SNAPSHOT_IDENTITY','VERIFIED_SERVICE':'NATIVE_SCM_SIGNED_IMAGE','VERIFIED_SYSTEM_IMAGE':'NATIVE_SIGNED_SYSTEM_IMAGE'}
    output=dict(process_count=0,reason_counts={},protection='NOT_COLLECTED',architecture='NOT_COLLECTED',
                inventory_state={key:summary[key] for key in ('process_snapshot','identity_evidence','scm_evidence','http_sys_ownership')},
                count_units=dict(reason_counts='PROCESS_FIRST_REFUSAL',native='SNAPSHOT_ENDPOINT',modules='SNAPSHOT_ENDPOINT',configuration='SERVICE_MEMBER_CHECK'),
                native={},modules={},configuration={},pair_stability={key:Counter() for key in ('native','modules','configuration')},
                later_implementation_checks='NOT_EVALUATED_BY_ADAPTER')
    for phase in ('before','after'):
        for group in ('native','modules'):
            output[group][phase]=dict(stage_counts=Counter(),error_counts=Counter(),lifetime_counts=Counter(),alive_counts=Counter())
        output['configuration'][phase]=configuration_counts()
    for result in results:
        schema.record(result,('process','assessment'));row=result['process'];schema.row(row)
        require(row['pid'] in by_id and row['pid'] not in observed)
        observed.add(row['pid']);require(row==by_id[row['pid']]['process'])
        proof=by_id[row['pid']]['evidence'];require(type(proof) is dict)
        assessment=result['assessment'];require(type(assessment) is dict)
        status=assessment.get('status');reason=assessment.get('reason_code')
        if status=='UNRESOLVED':
            require(type(reason) is str and reason in identity.PUBLIC_PROCESS_REASONS)
            reasons[reason]+=1;unresolved.append(result)
        else:require(type(status) is str and status in valid and reason==valid[status])
        paired_configuration(proof)
        times=[]
        for group in ('native','kernel','modules'):
            for phase in ('before','after'):
                item=proof.get(group+'_'+phase)
                if type(item) is dict:
                    schema.integer(item.get('created'),schema.TIME_MAX)
                    if item['created']:times.append(item['created'])
        if times:require(all(t==times[0] for t in times),'LIFETIME_BINDING_INVALID')
        kernel_times=[]
        for phase in ('before','after'):
            kernel=proof.get('kernel_'+phase)
            if kernel is not None:
                schema.record(kernel,('pid','name','created','parent_pid','session_id'))
                for field in ('pid','parent_pid','session_id'):schema.integer(kernel[field])
                schema.integer(kernel['created'],schema.TIME_MAX,0 if row['pid']==0 else 1)
                schema.text(kernel['name'],empty=row['pid']==0)
                require(all(kernel[field]==row[field] for field in ('pid','parent_pid','session_id')),'LIFETIME_BINDING_INVALID')
                require((kernel['created']==row['created']==0 and row['pid']==0) or identity.same_creation(kernel['created'],row['created']),'LIFETIME_BINDING_INVALID')
                kernel_times.append(kernel['created'])
            native=endpoint(proof,'native_'+phase,row,times,'native',row['pid'] not in (0,4))
            services=proof.get('services_'+phase,[])
            require(type(services) is list)
            applicable=any(type(s) is dict and s.get('name') in identity.WINDOWS_SERVICE_CONTRACTS for s in services) or 'modules_'+phase in proof
            modules=endpoint(proof,'modules_'+phase,row,times,'modules',applicable)
            # Validate every binding, but publish only unresolved diagnostics.
            cfg=output['configuration'][phase] if status=='UNRESOLVED' else configuration_counts()
            config_checks(proof,phase,roots,row,cfg)
            if status=='UNRESOLVED':
                add_endpoint(output['native'][phase],native);add_endpoint(output['modules'][phase],modules)
        require(not kernel_times or all(t==kernel_times[0] for t in kernel_times),'LIFETIME_BINDING_INVALID')
        if status=='UNRESOLVED':
            for group in ('native','modules','configuration'):
                prefix='implementation' if group=='configuration' else group
                first=proof.get(prefix+'_before');last=proof.get(prefix+'_after')
                same=None
                if type(first) is dict and type(last) is dict:
                    if group=='modules':
                        if first.get('complete') is True and last.get('complete') is True:
                            same={identity.canonical(v) for v in first['paths']}=={identity.canonical(v) for v in last['paths']}
                    else:same=first==last
                output['pair_stability'][group]['NOT_OBSERVED' if same is None else 'MATCH' if same else 'DIFFERENT']+=1
    require(dict(reasons)==facts['process_inventory']['reason_counts'])
    require(len(unresolved)==facts['process_inventory']['unknown_process_paths'])
    output.update(process_count=len(unresolved),reason_counts=dict(sorted(reasons.items())))
    return output


def project(facts):
    try:return _project(facts)
    except AdapterError:raise
    except (KeyError,TypeError,ValueError,AttributeError,OverflowError,RecursionError):
        raise AdapterError('EVIDENCE_INVALID') from None


def main(argv=None):
    class SafeParser(argparse.ArgumentParser):
        def error(self,message):raise AdapterError('ARGUMENTS_INVALID')
    output=None;binding=None;diagnostics=None;code='DIAGNOSTIC_ONLY'
    try:
        parser=SafeParser(add_help=False)
        for name in ('output','expected-sha','expected-tree'):parser.add_argument('--'+name,required=True)
        args=parser.parse_args(argv)
        try:output=host.NewOutput(args.output)
        except BaseException:raise AdapterError('OUTPUT_UNAVAILABLE') from None
        if not host.is_elevated():raise AdapterError('ELEVATED_TOKEN_REQUIRED')
        binding=source_binding(args.expected_sha,args.expected_tree)
        try:diagnostics=project(host.collect_facts())
        finally:
            try:after=source_binding(args.expected_sha,args.expected_tree)
            except BaseException:raise AdapterError('SOURCE_BINDING_INVALID') from None
            require(after==binding,'SOURCE_BINDING_INVALID')
    except BaseException as exc:
        diagnostics=None;binding=None
        code=exc.code if isinstance(exc,(AdapterError,host.DiagnosticError)) and type(exc.code) is str and exc.code in SAFE_ERRORS else 'COLLECTOR_UNAVAILABLE'
    def report():
        return dict(schema=1,status='FAIL_CLOSED',authorization='NONE',diagnostic_status='READ_ONLY_R0_R5',
                    projection_status='AVAILABLE' if diagnostics is not None else 'UNAVAILABLE',reason_codes=[code],
                    source={k:binding[k] for k in ('sha','tree')} if binding is not None else None,diagnostics=diagnostics)
    if output is not None:
        try:output.write(json.dumps(report(),allow_nan=False,sort_keys=True).encode('utf-8'))
        except BaseException:diagnostics=None;code='OUTPUT_UNAVAILABLE'
        finally:
            try:output.close()
            except BaseException:diagnostics=None;code='OUTPUT_UNAVAILABLE'
    try:print(json.dumps(report(),allow_nan=False,sort_keys=True))
    except (OSError,ValueError):pass
    return 1


if __name__=='__main__':raise SystemExit(main())
