# Mandatory Windows CI check of the real read-only native API boundary.
param([Parameter(Mandatory=$true)][string]$Output)
$ErrorActionPreference='Stop'
$script:probeStage='LOAD_NATIVE_PROBE'
function Assert-Probe([bool]$Condition,[string]$Code) { $script:probeStage=$Code;if (!$Condition) { throw $Code } }
try {
 . (Join-Path $PSScriptRoot 'process-evidence.ps1')
 $cim=Get-CimInstance Win32_Process -Filter "ProcessId=$PID"
 $first=[MetaCommissionInventory.Probe]::ReadProcess($PID)
 $last=[MetaCommissionInventory.Probe]::ReadProcess($PID)
 Assert-Probe ($first -and $last -and $first.alive -and $last.alive -and $first.pid -eq $PID -and $first.created -eq $last.created -and $first.path -eq $last.path -and [IO.Path]::IsPathRooted($first.path)) 'NATIVE_PROCESS_BOUNDARY'
 Assert-Probe ($cim.CreationDate -and [Math]::Abs($first.created-$cim.CreationDate.ToUniversalTime().ToFileTimeUtc()) -lt 10) 'NATIVE_CIM_CREATION_BINDING'
 Assert-Probe ($null -eq [MetaCommissionInventory.Probe]::ReadProcess(-1)) 'INVALID_PROCESS_NOT_REJECTED'
 Assert-Probe ($null -eq [MetaCommissionInventory.Probe]::ReadService('__meta_commission_inventory_missing_service__')) 'UNKNOWN_SERVICE_NOT_REJECTED'
 $membership=[MetaCommissionInventory.Probe]::ReadBindings($PID)
 Assert-Probe ($membership.services.Count -eq 0 -and ($membership.complete -or $membership.reason_code -in @('SERVICE_COVERAGE_UNAVAILABLE','SERVICE_STATUS_UNAVAILABLE'))) 'NATIVE_EMPTY_OR_FAIL_CLOSED_SERVICE_MEMBERSHIP'
 $service=Get-CimInstance Win32_Service -Filter "Name='EventLog'"
 $scm=[MetaCommissionInventory.Probe]::ReadService('EventLog')
 $members=[MetaCommissionInventory.Probe]::ReadBindings($service.ProcessId)
 Assert-Probe ($scm -and $scm.state -eq 4 -and $scm.pid -eq $service.ProcessId -and $scm.binary_path -eq $service.PathName) 'SCM_STATUS_CONFIG_BOUNDARY'
 Assert-Probe (($members.complete -and @($members.services | Where-Object { $_.name -eq 'EventLog' -and $_.pid -eq $service.ProcessId }).Count -eq 1) -or (!$members.complete -and $members.services.Count -eq 0)) 'SCM_COMPLETE_OR_FAIL_CLOSED_MEMBERSHIP_BOUNDARY'
 foreach($kernelIdValue in @(0,4)) {
  $before=[MetaCommissionInventory.Probe]::ReadKernel($kernelIdValue)
  $after=[MetaCommissionInventory.Probe]::ReadKernel($kernelIdValue)
  Assert-Probe ($before -and $after -and $before.pid -eq $kernelIdValue -and $before.parent_pid -eq 0 -and $before.session_id -eq 0 -and (($before | ConvertTo-Json -Compress) -eq ($after | ConvertTo-Json -Compress))) 'NATIVE_KERNEL_SNAPSHOT_BOUNDARY'
 }
 [ordered]@{status='PASS';native_process='PASS';creation_binding='PASS';unknown_process_service='REJECTED';scm_native_status_config='PASS';scm_membership=if($membership.complete -and $members.complete){'COMPLETE'}else{'FAIL_CLOSED_UNAVAILABLE'};scm_coverage_reason=$membership.reason_code;kernel_snapshot='PASS';access='READ_ONLY_QUERY';services_changed=$false;private_values_published=$false;host_admission='NOT_TESTED'} | ConvertTo-Json | Set-Content -LiteralPath $Output -Encoding UTF8
} catch {
 [ordered]@{status='FAIL_CLOSED';stage=$script:probeStage;error_type=$_.Exception.GetType().Name;detail='Native read-only identity boundary failed; private values suppressed'} | ConvertTo-Json | Set-Content -LiteralPath $Output -Encoding UTF8
 exit 1
}
