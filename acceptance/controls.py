"""Independent source-test mutation sensitivity and additional acceptance probes."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import xml.etree.ElementTree as ET

import run as harness


def main():
    harness.verify()
    sys.path[:0] = [str(Path.cwd()/'tests'), str(Path.cwd()/'commissioning')]
    import process_identity as p
    import test_windows_service_contracts as service
    import test_kernel_identity_evidence as kernel
    source = Path('commissioning/process_identity.py').read_text()
    controls = [
        ('empty-scm', "if known_service_image and not services:", 'if False:', lambda: service.test_service_host_cannot_fall_back_to_system_image_with_empty_membership('DoSvc')),
        ('duplicate-scm', 'if len(names)!=len({name.casefold() for name in names}):', 'if False:', lambda: service.test_duplicate_service_membership_is_not_complete_evidence('both')),
        ('implementation', 'if refusal:return blocked(refusal)', 'if False:return blocked(refusal)', lambda: service.test_unproved_or_spoofed_service_implementation_stays_unresolved('missing-proof', 'DoSvc')),
        ('kernel-snapshot-stability', "if first!=last:return 'KERNEL_IDENTITY_CONFLICT'", "if False:return 'KERNEL_IDENTITY_CONFLICT'", lambda: kernel.test_changed_snapshot_rejected('name')),
        ('native-record-stability', "if before!=after:return blocked('NATIVE_PROCESS_EVIDENCE_CHANGED')", "if False:return blocked('NATIVE_PROCESS_EVIDENCE_CHANGED')", kernel.test_native_snapshot_change_rejected_even_with_stable_kernel_records),
        ('pid-reuse', "if before['created']!=after['created']:", 'if False:', kernel.test_native_pid_reuse_rejected),
        ('no-image-no-kernel-admission', "return blocked('IMAGE_PATH_UNAVAILABLE')", "return dict(status='VERIFIED_KERNEL',reason_code='MUTANT')", lambda: kernel.test_labels_errors_and_subsystem_never_authorize_arbitrary_pid('Secure System', 31)),
        ('native-types', "or type(n.get('pid')) is not int or type(n.get('win32_error')) is not int", 'or False', lambda: kernel.test_native_wrong_types_rejected('pid', 123.0)),
        ('scm-success-status', "if svc.get('error_stage') or type(svc.get('win32_error')) is not int or svc['win32_error']!=0:", 'if False:', lambda: service.test_scm_requires_explicit_success_error_code('DoSvc', 5)),
    ]
    result=[]
    for name, old, new, check in controls:
        assert old in source, name
        mutant=types.ModuleType('mutant');exec(compile(source.replace(old,new), '<mutant>', 'exec'), mutant.__dict__)
        service.p=kernel.p=mutant
        try:
            check()
        except AssertionError: detected=True
        else: detected=False
        finally: service.p=kernel.p=p
        result.append(dict(control=name, detected=detected))
    probes=[]
    for fault in ('changed-parent', 'changed-creation', 'missing-after', 'null-before', 'invalid-session'):
        row,e=service.evidence()
        k={key:row[key] for key in ('pid','created','parent_pid','session_id','name')}
        e.update(kernel_before=k,kernel_after=copy.deepcopy(k))
        if fault=='changed-parent':e['kernel_after']['parent_pid']+=1
        if fault=='changed-creation':e['kernel_after']['created']+=10
        if fault=='missing-after':e.pop('kernel_after')
        if fault=='null-before':e['kernel_before']=None
        if fault=='invalid-session':e['kernel_after']['session_id']=False
        assessment=p.classify_missing(row,e,service.ROOTS)
        probes.append(dict(probe='available-image-kernel-'+fault, expected='UNRESOLVED', actual=assessment['status'], passed=assessment['status']=='UNRESOLVED'))
    # Probe privacy using synthetic values only. Never echo the payload or paths.
    with tempfile.TemporaryDirectory() as directory:
        for name,payload in [('scm','{"services_before":[]}'),('hostname','{"hostname":"synthetic"}'),('path','C:\\Users\\synthetic\\private'),('junit-host','<testsuite tests="0" hostname="synthetic"/>')]:
            artifact=Path(directory)/'public.json';artifact.write_text(payload)
            check=subprocess.run([sys.executable,'scripts/check_public_diagnostic_artifacts.py',str(artifact)],capture_output=True)
            probes.append(dict(probe='privacy-'+name, expected='REJECTED', actual='ACCEPTED' if check.returncode==0 else 'REJECTED', passed=check.returncode!=0))
    out=Path('controls-public');out.mkdir(exist_ok=True)
    summary=dict(candidate_sha=harness.TARGET,candidate_tree=harness.TREE,harness_sha=harness.git('rev-parse','HEAD',cwd=harness.HERE),
                 mutations=result,probes=probes,candidate_source_modified=False,native_execution=False)
    (out/'controls.json').write_text(json.dumps(summary,indent=2)+'\n')
    suite=ET.Element('testsuite', tests=str(len(result)+len(probes)),failures=str(sum(not x['passed'] for x in probes)+sum(not x['detected'] for x in result)),errors='0',skipped='0')
    for item in result+probes:
        case=ET.SubElement(suite,'testcase',classname='independent.acceptance',name=item.get('control',item.get('probe')))
        if not item.get('detected',item.get('passed')):ET.SubElement(case,'failure',message='Independent contract failed; synthetic reproduction only')
    ET.ElementTree(suite).write(out/'junit.xml',encoding='utf-8',xml_declaration=True)
    for path in out.iterdir():harness.safe(path)
    harness.verify()
    print('Mutation controls detected:',sum(x['detected'] for x in result),'/',len(result))
    print('Independent contract failures:',sum(not x['passed'] for x in probes),'/',len(probes))
    return 0 if all(x['detected'] for x in result) and all(x['passed'] for x in probes) else 1


if __name__=='__main__':raise SystemExit(main())
