"""Execute only isolated pure PowerShell projections with synthetic providers.

Never dot-source the collector. No Add-Type, CIM, registry, signatures, DPAPI,
native probes, environment identity or database calls are executed.
"""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'commissioning'),str(ROOT/'tests')]
from test_process_identity_acceptance import fixture,ROOTS,CONTRACTS,add_topology
from test_process_inventory_identity import sample
from evidence_schema import strict_loads,validate_source_snapshot
from process_identity import classify_missing

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--shell',default='powershell');args=parser.parse_args()
    source=(ROOT/'commissioning/process-evidence.ps1').read_text(encoding='utf-8-sig')
    function=source[source.index('function Get-MissingProcessEvidence {'):]
    for method in ('Kernel','Process','Bindings','Modules'):
        old='[MetaCommissionInventory.Probe]::Read'+method+'($idValue)'
        assert old in function
        function=function.replace(old,'(Get-Synthetic'+method+')')
    function=function.replace('[Environment]::SystemDirectory','$synthetic.roots.system32')
    # Signature existence check is replaced by an in-script pure boolean provider.
    assert not any(token in function for token in ('MetaCommissionInventory','Add-Type','Registry','Get-CimInstance','[Environment]'))
    line=next(line.strip() for line in (ROOT/'commissioning/host-facts.ps1').read_text().splitlines() if line.strip().startswith('processes=@($processes | Select-Object'))
    projection=line[len('processes=@('):-1]
    cases=[]
    for name in CONTRACTS:
        row,e=fixture(name);add_topology(row,e);cases.append((name,row,e))
    row,e=sample();add_topology(row,e);cases.append(('ordinary',row,e))
    # Native 100ns detail may differ within the CIM microsecond.
    row,e=fixture();add_topology(row,e)
    for key in ('native_before','native_after','kernel_before','kernel_after','modules_before','modules_after'):e[key]['created']+=7
    cases.append(('native-100ns',row,e))
    cases.append(('idle',dict(pid=0,name='System Idle Process',parent_pid=0,session_id=0,created=0,cim_path=None),
        dict(kernel_before=dict(pid=0,name='',parent_pid=0,session_id=0,created=0),kernel_after=dict(pid=0,name='',parent_pid=0,session_id=0,created=0))))
    wrapper=r'''
param($Fixture)
$ErrorActionPreference='Stop'
$synthetic=Get-Content -LiteralPath $Fixture -Raw | ConvertFrom-Json
function Get-SyntheticKernel { $synthetic.evidence.kernel_before }
function Get-SyntheticProcess { $synthetic.evidence.native_before }
function Get-SyntheticModules { $synthetic.evidence.modules_before }
function Get-SyntheticBindings {
 [pscustomobject]@{complete=$true;reason_code='COMPLETE_REGISTRY_SCM_COVERAGE';error_stage='';win32_error=[int]0;failed_service='';services=@($synthetic.evidence.services_before)}
}
function Get-ServiceImplementationConfig { param($Name) $synthetic.evidence.implementation_before.$Name }
function Get-PrivateFileProof { param($Path)
 if ($Path -ieq $synthetic.evidence.native_before.path) {return $synthetic.evidence.signature}
 foreach($property in $synthetic.evidence.implementation_signatures.PSObject.Properties) {if($property.Value.path -ieq $Path){return $property.Value}}
 throw 'SYNTHETIC_FIXTURE_MISSING'
}
function Test-Path { param($LiteralPath,$PathType) $true }
__FUNCTION__
$row=$synthetic.process
$date=if($row.pid -eq 0){$null}else{[DateTime]::FromFileTimeUtc([long]$row.created)}
$processes=@([pscustomobject]@{Name=[string]$row.name;ProcessId=[uint32]$row.pid;ParentProcessId=[uint32]$row.parent_pid;SessionId=[uint32]$row.session_id;ExecutablePath=$row.cim_path;CreationDate=$date})
$original=@(__PROJECTION__)
[ordered]@{original=$original;records=@(Get-MissingProcessEvidence -ProcessRecord $processes[0])} | ConvertTo-Json -Depth 8 -Compress
'''.replace('__FUNCTION__',function).replace('__PROJECTION__',projection)
    with tempfile.TemporaryDirectory(prefix='synthetic-ps-contract-') as tmp:
        directory=Path(tmp);script=directory/'projection.ps1';script.write_text(wrapper,encoding='utf-8-sig')
        for name,row,e in cases:
            e=copy.deepcopy(e)
            for key in ('native_before','native_after'):
                if key in e:e[key].update(native_format_path='',native_format_query_succeeded=False,native_format_win32_error=0)
            file=directory/'fixture.json';file.write_text(json.dumps(dict(process=row,evidence=e,roots=ROOTS)),encoding='utf-8')
            # Inline pure code avoids changing any execution-policy setting.
            command='& {'+wrapper+"} -Fixture '"+str(file).replace("'","''")+"'"
            result=subprocess.run([args.shell,'-NoProfile','-NonInteractive','-Command',command],capture_output=True,timeout=20)
            if result.returncode:raise ValueError('SYNTHETIC_POWERSHELL_PROJECTION_FAILED')
            value=strict_loads(result.stdout.decode('utf-8-sig'))
            validate_source_snapshot(value['original'],value['records'],ROOTS,ROOTS['system32'])
            item=value['records'][0];assessment=classify_missing(item['process'],item['evidence'],ROOTS)
            assert assessment['status'].startswith('VERIFIED_'),name+':'+assessment['reason_code']
    print('Pure PowerShell JSON producer/schema contract PASS: 8 synthetic cases, native calls substituted; no collector execution')

if __name__=='__main__':main()
