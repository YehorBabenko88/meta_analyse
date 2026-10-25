"""Fixed aggregate observations only. No host access, identifiers or persistence."""

STATES={'NOT_EVALUATED','COMPLETE','INCOMPLETE','MALFORMED','VALIDATED','INVALID',
        'RESOLVED','UNRESOLVED','NOT_APPLICABLE','MATCHED_OBSERVATION_ONLY'}
CODES={'ELEVATED_TOKEN_REQUIRED','COLLECTOR_SOURCE_UNVERIFIED','COLLECTOR_SOURCE_CHANGED',
       'PROCESS_INVENTORY_SNAPSHOT_INVALID','PROCESS_SNAPSHOT_BINDING_INVALID',
       'COLLECTOR_CHILD_BLOCKED','AGGREGATE_DIAGNOSTIC_UNAVAILABLE',
       'AGGREGATE_OUTPUT_UNAVAILABLE','AGGREGATE_ARGUMENTS_INVALID'}
FIELDS=('snapshot_status','source_snapshot_status','inventory_error_count','process_status',
        'unresolved_count','scm_status','incomplete_scm_snapshots',
        'incomplete_module_snapshots','scm_refusal_count','module_refusal_count','http_sys_status')


class AggregateDiagnostics:
    def __init__(self):
        self.values={k:'NOT_EVALUATED' if k.endswith('_status') else None for k in FIELDS}
        self.codes=set()

    def failure(self,code):
        self.codes.add(code if type(code) is str and code in CODES else 'AGGREGATE_DIAGNOSTIC_UNAVAILABLE')
        if code in ('COLLECTOR_SOURCE_CHANGED','COLLECTOR_SOURCE_UNVERIFIED'):
            self.codes={code}
            self.values={k:'NOT_EVALUATED' if k.endswith('_status') else None for k in FIELDS}
        if code in ('PROCESS_INVENTORY_SNAPSHOT_INVALID','PROCESS_SNAPSHOT_BINDING_INVALID'):
            self.values['source_snapshot_status']='INVALID'

    def observe_raw(self,facts):
        # Never retain the raw object, names, reason keys, per-process rows or exceptions.
        v=self.values
        try:
            if type(facts) is not dict:raise ValueError
            grid=facts['grid'];private=facts['private_inventory']
            if type(grid) is not dict or type(private) is not dict:raise ValueError
            errors=grid['errors'];rows=private['processes'];visible=grid['visible_processes']
            if (type(errors) is not list or type(rows) is not list or type(visible) is not int
                    or not 0<=visible<=1000000 or type(grid.get('coverage_complete')) is not bool):raise ValueError
            v['inventory_error_count']=len(errors)
            valid=all(type(r) is dict and type(r.get('ProcessId')) is int and 0<=r['ProcessId']<=0x7fffffff for r in rows)
            v['snapshot_status']='COMPLETE' if (valid and rows and len(rows)==visible
                and len({r['ProcessId'] for r in rows})==len(rows) and not errors and grid['coverage_complete']) else 'INCOMPLETE'
            if not valid:v['snapshot_status']='MALFORMED'
        except (KeyError,TypeError,ValueError,AttributeError):
            v['snapshot_status']='MALFORMED'
        try:
            rows=facts['process_evidence']
            if type(rows) is not list:raise ValueError
            incomplete=modules=applicable=0
            for item in rows:
                if type(item) is not dict or type(item.get('process')) is not dict or type(item.get('evidence')) is not dict:raise ValueError
                proof=item['evidence'];pid=item['process'].get('pid')
                if type(pid) is not int:raise ValueError
                # Only SCM applicability, never an exclusion from process classification.
                if pid in (0,4):continue
                applicable+=1
                for phase in ('before','after'):
                    incomplete+=int(proof.get('services_'+phase+'_complete') is not True)
                    key='modules_'+phase
                    required=bool(proof.get('implementation_'+phase)) or key in proof
                    if required:modules+=int(type(proof.get(key)) is not dict or proof[key].get('complete') is not True)
            v['incomplete_scm_snapshots']=incomplete
            v['incomplete_module_snapshots']=modules
            v['scm_status']='INCOMPLETE' if incomplete or modules else 'COMPLETE' if applicable else 'NOT_APPLICABLE'
        except (KeyError,TypeError,ValueError,AttributeError):
            v['scm_status']='MALFORMED'
        return v['snapshot_status']!='MALFORMED'

    def validated(self):
        self.values['source_snapshot_status']='VALIDATED'

    def assessed(self,assessment):
        count=assessment.get('unknown_process_paths')
        if type(count) is not int or not 0<=count<=1000000:
            self.values['process_status']='MALFORMED'
            return
        self.values['unresolved_count']=count
        self.values['process_status']='UNRESOLVED' if count else 'RESOLVED'
        reasons=assessment.get('reason_counts')
        if type(reasons) is not dict or any(type(k) is not str or type(n) is not int or not 0<=n<=1000000 for k,n in reasons.items()):
            self.values['process_status']='MALFORMED'
            return
        self.values['module_refusal_count']=sum(n for k,n in reasons.items() if k.startswith('SERVICE_MODULE'))
        self.values['scm_refusal_count']=sum(n for k,n in reasons.items() if k.startswith('SERVICE_') and not k.startswith('SERVICE_MODULE'))
        if self.values['module_refusal_count'] or self.values['scm_refusal_count']:self.values['scm_status']='UNRESOLVED'

    def http_observed(self,matched):
        self.values['http_sys_status']='MATCHED_OBSERVATION_ONLY' if matched is True else 'UNRESOLVED'

    def report(self):
        aggregate={}
        for key in FIELDS:
            value=self.values[key]
            aggregate[key]=(value if type(value) is str and value in STATES else 'MALFORMED') if key.endswith('_status') else (value if type(value) is int and 0<=value<=1000000 else None)
        codes=set(self.codes)
        if aggregate['snapshot_status'] in ('INCOMPLETE','MALFORMED'):codes.add('INCOMPLETE_INVENTORY')
        if aggregate['process_status']=='UNRESOLVED':codes.add('UNRESOLVED_PROCESS_IDENTITIES')
        if aggregate['incomplete_scm_snapshots']:codes.add('SCM_EVIDENCE_INCOMPLETE')
        if aggregate['incomplete_module_snapshots']:codes.add('MODULE_EVIDENCE_INCOMPLETE')
        if aggregate['scm_refusal_count'] or aggregate['module_refusal_count']:codes.add('SCM_EVIDENCE_UNRESOLVED')
        if aggregate['http_sys_status']=='UNRESOLVED':codes.add('HTTP_SYS_OWNERSHIP_UNRESOLVED')
        return dict(schema=1,status='FAIL_CLOSED',diagnostic_status='AGGREGATE_ONLY_NOT_AUTHORIZATION',
                    authorization='NONE',reason_codes=sorted(codes) or ['AGGREGATE_ONLY'],aggregate=aggregate)
