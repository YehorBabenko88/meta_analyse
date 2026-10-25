"""Pure commissioning evidence evaluator. No execution, enrollment or stage advancement."""
import math
import re

CHECKS={
    'G0':('source','host','process','scm','ci'),
    'G1':('isolation','cluster_identity','role_database','migrations','rollback_ownership'),
    'G2':('bybit','sequence','postgres_checkpoint','desktop','shutdown'),
    'G3':('continuity','resources','shutdown','checkpoint','privacy'),
    'G4':('continuity','resources','shutdown','checkpoint','privacy'),
    'G5':('continuity','resources','shutdown','checkpoint','privacy'),
}
DURATIONS=dict(G0=0,G1=0,G2=0,G3=1800,G4=7200,G5=86400)
MAX_SECONDS=dict(G0=300,G1=1800,G2=600,G3=1830,G4=7230,G5=86430)


def require(condition):
    if not condition:raise ValueError('INVALID_EVIDENCE')


def evaluate_stage(stage,sha,tree,evidence,*,operator_approved=False,previous=None):
    """PASS means submitted fields satisfy this checker, never physical permission."""
    def result(status,reason):
        return dict(status=status,reason=reason,authorization='NONE',next_stage_started=False,
                    scope='SUBMITTED_EVIDENCE_ONLY')
    try:
        require(type(stage) is str and stage in CHECKS)
        require(all(type(v) is str and re.fullmatch('[0-9a-f]{40}',v) for v in (sha,tree)))
        require(type(evidence) is dict and evidence['source']==dict(sha=sha,tree=tree))
        require(type(operator_approved) is bool)
        checks=evidence['checks'];metrics=evidence['metrics']
        require(type(checks) is dict and set(checks)<=set(CHECKS[stage]))
        require(all(type(v) is str and v in ('PASS','FAIL','BLOCKED') for v in checks.values()))
        if stage!='G0':
            if not operator_approved:return result('BLOCKED','OPERATOR_GATE_REQUIRED')
            require(type(previous) is dict)
            require(previous==dict(stage='G'+str(int(stage[1])-1),status='PASS',sha=sha,tree=tree))
        if 'FAIL' in checks.values():return result('FAIL','PRECONDITION_FAILED')
        if set(checks)!=set(CHECKS[stage]) or any(v!='PASS' for v in checks.values()):
            return result('BLOCKED','PRECONDITION_UNPROVEN')
        require(type(metrics) is dict)
        for key in ('cpu_peak_percent','memory_delta_mb','free_disk_mb','queue_depth','active_writes','ui_age_seconds','elapsed_seconds','unresolved_processes'):
            value=metrics[key]
            require(type(value) in (int,float) and math.isfinite(value) and value>=0)
        for key in ('queue_depth','active_writes','unresolved_processes'):require(type(metrics[key]) is int)
        if (metrics['cpu_peak_percent']>80 or metrics['memory_delta_mb']>1024 or metrics['free_disk_mb']<8192
                or metrics['elapsed_seconds']>MAX_SECONDS[stage]):
            return result('FAIL','RESOURCE_STOP_CONDITION')
        if metrics['elapsed_seconds']<DURATIONS[stage]:return result('BLOCKED','DURATION_UNPROVEN')
        if metrics['unresolved_processes']!=0:return result('FAIL','INVENTORY_UNRESOLVED')
        if stage in ('G2','G3','G4','G5') and (metrics['queue_depth']>1024 or metrics['active_writes']!=0 or metrics['ui_age_seconds']>5):
            return result('FAIL','RUNTIME_STOP_CONDITION')
        return result('PASS','EVIDENCE_CHECKS_SATISFIED')
    except (AssertionError,KeyError,TypeError,ValueError,OverflowError):
        return result('BLOCKED','EVIDENCE_INVALID_OR_SOURCE_MISMATCH')
