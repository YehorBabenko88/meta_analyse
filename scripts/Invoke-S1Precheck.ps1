# PowerShell 5.1, one approved Python worker; stdout only, no automatic retry.
param([string]$Repo, [string]$Python, [string]$Packet,
      [string]$PacketSha256, [switch]$OperatorApproved)
$ErrorActionPreference='Stop'
$watch=[Diagnostics.Stopwatch]::StartNew()
$child=$null
$workerPin='c9dbeb3ecb3a410d0feff59cc4844ff4baebd7334379920cba259744ed9bf98a'
function Public-Refusal([string]$Reason,[int]$Code=2) {
 $outcome='BLOCKED';if($Code -eq 1){$outcome='FAIL'}
 [ordered]@{schema=1;stage='S1_PRECHECK';contract_version=1
 source_sha='b00c66776b27e929016f7541329c29c9349dddfe';source_tree='0418dc7bea4bb2f40f6712b0f3c0c1a6c63b8288'
 source_bound=$false;source_continuity='NOT_EVALUATED';runtime_continuity='NOT_EVALUATED';output_readiness='NOT_EVALUATED'
 outcome=$outcome;reason=$Reason;elapsed_ms=[long]$watch.ElapsedMilliseconds;exit_code=$Code
 attempts=[int]($null -ne $child);s1_complete=$false;authorization='NONE';g0_status='FAIL_CLOSED'
 next_stage='BLOCKED';stop_required=$true}|ConvertTo-Json -Compress
}
function Need($Condition){if(-not $Condition){throw 'UNAVAILABLE'}}
function Local-Ordinary([string]$Path){
 Need ($Path -match '^[A-Za-z]:\\' -and $Path.Substring(2).IndexOf(':') -lt 0)
 $parts=$Path.Substring(3).Split('\');$at=$Path.Substring(0,3)
 foreach($part in @('')+$parts){
  if($part -ne ''){Need ($part -notin @('.','..') -and $part.TrimEnd([char[]]' .') -ceq $part);$at=Join-Path $at $part}
  $item=Get-Item -LiteralPath $at -Force
  Need (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0)
 }
 return $item
}
function Read-Bounded([string]$Path,[int]$Limit){
 $operationStart=$watch.ElapsedMilliseconds
 $before=Local-Ordinary $Path
 Need ($before -is [IO.FileInfo] -and $before.Length -le $Limit -and $watch.Elapsed.TotalSeconds -lt 30)
 $stream=$null
 try {
  $stream=[IO.File]::Open($Path,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
  Need ($stream.Length -eq $before.Length)
  $bytes=New-Object byte[] ([int]$stream.Length)
  $offset=0
  while($offset -lt $bytes.Length){
   $task=$stream.ReadAsync($bytes,$offset,$bytes.Length-$offset)
   Need ($task.Wait([int][Math]::Max(1,[Math]::Min(5000-($watch.ElapsedMilliseconds-$operationStart),30000-$watch.ElapsedMilliseconds))))
   Need ($task.Result -gt 0);$offset+=$task.Result
  }
  $after=Local-Ordinary $Path
  Need ($before.Length -eq $after.Length -and $before.LastWriteTimeUtc -eq $after.LastWriteTimeUtc -and $watch.Elapsed.TotalSeconds -lt 30 -and $watch.ElapsedMilliseconds-$operationStart -lt 5000)
  return ,$bytes
 } finally {if($null -ne $stream){$stream.Dispose()}}
}
function SHA256([byte[]]$Bytes){
 $hasher=[Security.Cryptography.SHA256]::Create()
 try{return ([BitConverter]::ToString($hasher.ComputeHash($Bytes))).Replace('-','').ToLowerInvariant()}
 finally{$hasher.Dispose()}
}
function Quote([string]$Value){
 # All values are local paths or lowercase hex; quoting cannot admit options/commands.
 Need (-not $Value.Contains('"') -and -not $Value.EndsWith('\') -and $Value -notmatch '[\r\n\x00]')
 return '"'+$Value+'"'
}
try {
 Need ($OperatorApproved.IsPresent -and $args.Count -eq 0 -and $PacketSha256 -cmatch '^[0-9a-f]{64}$')
 foreach($p in @($Repo,$Python,$Packet)){[void](Local-Ordinary $p)}
 Need ((Get-Item -LiteralPath $Repo) -is [IO.DirectoryInfo])
 Need ((Get-Item -LiteralPath $Python) -is [IO.FileInfo])
 $worker=Join-Path $PSScriptRoot 's1_precheck.py'
 [void](Local-Ordinary $worker)
 Need ((SHA256 (Read-Bounded $worker 1048576)) -ceq $workerPin)
 $shell=[Diagnostics.Process]::GetCurrentProcess().MainModule.FileName
 # Runtime is verified BEFORE executing Python. This packet is approved/pinned
 # outside ADMINIT; the switch and hash do not manufacture approval authority.
 $packetBytes=Read-Bounded $Packet 1048576
 Need ((SHA256 $packetBytes) -ceq $PacketSha256)
 $strictUtf8=New-Object Text.UTF8Encoding($false,$true)
 $privatePacket=$strictUtf8.GetString($packetBytes)|ConvertFrom-Json
 Need ($privatePacket.schema -is [int] -and $privatePacket.schema -eq 1)
 Need ($privatePacket.reference_kind -ceq 'EXTERNALLY_REVIEWED_CONTINUITY')
 $roles=@('python_exe','python312_dll','hashlib_pyd','ctypes_pyd','libcrypto','libffi','crt','bz2_pyd','lzma_pyd','git_exe','git_core','libiconv','libintl','pcre2','zlib','powershell_exe')
 $seen=@{}
 Need (@($privatePacket.files).Count -ge $roles.Count -and @($privatePacket.files).Count -le 17)
 foreach($entry in $privatePacket.files){
  Need ($entry.role -cin ($roles+@('crt_1')) -and -not $seen.ContainsKey($entry.role) -and $entry.sha256 -cmatch '^[0-9a-f]{64}$')
  $seen.Add($entry.role,$true)
  if($entry.role -ceq 'python_exe'){Need ($entry.path -ieq $Python)}
  if($entry.role -ceq 'powershell_exe'){Need ($entry.path -ieq $shell)}
  Need ((SHA256 (Read-Bounded $entry.path 16777216)) -ceq $entry.sha256)
 }
 foreach($role in $roles){Need ($seen.ContainsKey($role))}
 Need (@($privatePacket.absent).Count -ge 1 -and @($privatePacket.absent).Count -le 16)
 foreach($absent in $privatePacket.absent){
  Need ($absent -match '^[A-Za-z]:\\' -and $absent -notmatch '\\\.\.(?:\\|$)' -and -not (Test-Path -LiteralPath $absent))
  $ancestor=[IO.Path]::GetDirectoryName($absent)
  while(-not [IO.Directory]::Exists($ancestor)){$ancestor=[IO.Path]::GetDirectoryName($ancestor);Need ($null -ne $ancestor)}
  [void](Local-Ordinary $ancestor)
 }
 $environmentKeys=@('PATH','GIT_CONFIG_SYSTEM','GIT_CONFIG_GLOBAL','GIT_CONFIG_NOSYSTEM','PYTHONHOME','PYTHONPATH','PYTHONSTARTUP','PYTHONUSERBASE','__PYVENV_LAUNCHER__')
 Need (@($privatePacket.environment.PSObject.Properties).Count -eq $environmentKeys.Count)
 foreach($key in $environmentKeys){
  Need ($null -ne $privatePacket.environment.PSObject.Properties[$key])
  Need ([Environment]::GetEnvironmentVariable($key) -ceq $privatePacket.environment.$key)
 }
 $info=New-Object Diagnostics.ProcessStartInfo
 $info.FileName=$Python
 $info.Arguments='-I -S -B '+(Quote $worker)+' --repo '+(Quote $Repo)+' --packet '+(Quote $Packet)+' --packet-pin '+$PacketSha256+' --shell '+(Quote $shell)+' --operator-approved'
 $info.WorkingDirectory=$Repo;$info.UseShellExecute=$false;$info.CreateNoWindow=$true
 $info.RedirectStandardInput=$true;$info.RedirectStandardOutput=$true;$info.RedirectStandardError=$true
 $child=New-Object Diagnostics.Process;$child.StartInfo=$info
 Need ($watch.Elapsed.TotalSeconds -lt 30)
 Need ($child.Start())
 $child.StandardInput.WriteLine([string]$child.Id)
 $child.StandardInput.Flush()
 # Pin worker execution to one CPU already available to this process.
 [long]$mask=$child.ProcessorAffinity.ToInt64();[long]$bit=1
 while(($mask -band $bit) -eq 0 -and $bit -gt 0){$bit=$bit -shl 1}
 Need ($bit -gt 0);$child.ProcessorAffinity=[IntPtr]$bit
 $stdout=New-Object byte[] 4097;$stderr=New-Object byte[] 4097
 $outTask=$child.StandardOutput.BaseStream.ReadAsync($stdout,0,$stdout.Length)
 $errTask=$child.StandardError.BaseStream.ReadAsync($stderr,0,$stderr.Length)
 while(-not $child.HasExited){
  $child.Refresh()
  if($watch.Elapsed.TotalSeconds -ge 30 -or $child.PeakWorkingSet64 -gt 268435456 -or $child.PrivateMemorySize64 -gt 268435456){
   $child.Kill();[void]$child.WaitForExit(1000);Public-Refusal 'BUDGET_EXCEEDED' 1;exit 1
  }
  if(($outTask.IsCompleted -and $outTask.Result -ge 4096) -or ($errTask.IsCompleted -and $errTask.Result -gt 0)){
   $child.Kill();[void]$child.WaitForExit(1000);Public-Refusal 'OUTPUT_UNAVAILABLE' 1;exit 1
  }
  if($outTask.IsCompleted -and $outTask.Result -gt 0){break}
  Start-Sleep -Milliseconds 10
 }
 Need (-not $child.HasExited -and $outTask.Wait(500) -and $watch.Elapsed.TotalSeconds -lt 30)
 Need ($outTask.Result -gt 0 -and $outTask.Result -le 4096)
 # ReadAsync may complete with a partial pipe chunk. Collect only bounded remainder.
 $count=$outTask.Result
 while($count -le 4096 -and $stdout[$count-1] -ne 10){
  $child.Refresh()
  if($watch.Elapsed.TotalSeconds -ge 30 -or $child.PeakWorkingSet64 -gt 268435456 -or $child.PrivateMemorySize64 -gt 268435456){
   $child.Kill();[void]$child.WaitForExit(1000);Public-Refusal 'BUDGET_EXCEEDED' 1;exit 1
  }
  $more=$child.StandardOutput.BaseStream.ReadAsync($stdout,$count,$stdout.Length-$count)
  Need ($more.Wait(500))
  if($more.Result -eq 0){break};$count+=$more.Result
 }
 Need ($count -le 4096)
 $utf8=New-Object Text.UTF8Encoding($false,$true)
 $text=$utf8.GetString($stdout,0,$count)
 # The worker serializes only ASCII enum keys/values and primitives. Reject all
 # escapes rather than interpreting escaped duplicate/forged property names.
 Need (-not $text.Contains('\'))
 $r=$text|ConvertFrom-Json
 $keys=@('schema','stage','contract_version','source_sha','source_tree','source_bound','source_continuity','runtime_continuity','output_readiness','outcome','reason','elapsed_ms','exit_code','attempts','s1_complete','authorization','g0_status','next_stage','stop_required')
 Need ($r -is [pscustomobject] -and @($r.PSObject.Properties).Count -eq $keys.Count)
 foreach($key in $keys){Need ($null -ne $r.PSObject.Properties[$key])}
 foreach($key in @('stage','source_sha','source_tree','source_continuity','runtime_continuity','output_readiness','outcome','reason','authorization','g0_status','next_stage')){
  Need ($r.$key -is [string])
 }
 $jsonKeys=@([regex]::Matches($text,'"([A-Za-z_0-9]+)"\s*:')|ForEach-Object {$_.Groups[1].Value})
 Need ($jsonKeys.Count -eq $keys.Count -and @($jsonKeys|Sort-Object -Unique).Count -eq $keys.Count)
 Need ($r.schema -is [int] -and $r.schema -eq 1 -and $r.contract_version -is [int] -and $r.contract_version -eq 1)
 Need ($r.stage -ceq 'S1_PRECHECK' -and $r.source_sha -ceq 'b00c66776b27e929016f7541329c29c9349dddfe' -and $r.source_tree -ceq '0418dc7bea4bb2f40f6712b0f3c0c1a6c63b8288')
 Need ($r.authorization -ceq 'NONE' -and $r.g0_status -ceq 'FAIL_CLOSED' -and $r.next_stage -ceq 'BLOCKED')
 Need ($r.s1_complete -is [bool] -and -not $r.s1_complete -and $r.stop_required -is [bool] -and $r.stop_required)
 Need ($r.source_bound -is [bool] -and $r.attempts -is [int] -and $r.attempts -eq 1)
 Need (($r.elapsed_ms -is [int] -or $r.elapsed_ms -is [long]) -and $r.elapsed_ms -ge 0 -and $r.elapsed_ms -lt 30000)
 Need ($r.exit_code -is [int] -and $r.exit_code -in @(0,1,2))
 foreach($field in @('source_continuity','runtime_continuity','output_readiness')){Need ($r.$field -cin @('PASS','FAIL','BLOCKED','NOT_EVALUATED'))}
 Need ($r.reason -cin @('PRECONDITIONS_REQUIRED','SOURCE_UNAVAILABLE','SOURCE_CHANGED','RUNTIME_CONTINUITY_UNAVAILABLE','NAMESPACE_UNAVAILABLE','BUDGET_EXCEEDED','OUTPUT_UNAVAILABLE','PRECHECK_COMPLETE'))
 if($r.exit_code -eq 0){Need ($r.outcome -ceq 'PASS_PRECHECK_ONLY' -and $r.reason -ceq 'PRECHECK_COMPLETE' -and $r.source_bound -and $r.source_continuity -ceq 'PASS' -and $r.runtime_continuity -ceq 'PASS' -and $r.output_readiness -ceq 'PASS')}
 else {Need (-not $r.source_bound -and $r.outcome -ceq $(if($r.exit_code -eq 1){'FAIL'}else{'BLOCKED'}))}
 $child.Refresh()
 if($child.PeakWorkingSet64 -gt 268435456 -or $child.PrivateMemorySize64 -gt 268435456){
  $child.Kill();[void]$child.WaitForExit(1000);Public-Refusal 'BUDGET_EXCEEDED' 1;exit 1
 }
 # A successful write does not prove the peer read it. Require an exact
 # per-attempt response after the resource/liveness checkpoint.
 $random=New-Object byte[] 16
 $rng=[Security.Cryptography.RandomNumberGenerator]::Create()
 try{$rng.GetBytes($random)}finally{$rng.Dispose()}
 $nonce=([BitConverter]::ToString($random)).Replace('-','').ToLowerInvariant()
 $child.StandardInput.WriteLine($nonce);$child.StandardInput.Close()
 Need ($child.WaitForExit(500) -and $errTask.Wait(500) -and $errTask.Result -eq 0 -and $watch.Elapsed.TotalSeconds -lt 30)
 Need ($child.ExitCode -eq $r.exit_code)
 $tail=New-Object byte[] 64;$tailCount=0
 while($tailCount -lt $tail.Length){
  Need ($watch.Elapsed.TotalSeconds -lt 30)
  $tailRead=$child.StandardOutput.BaseStream.ReadAsync($tail,$tailCount,$tail.Length-$tailCount)
  Need ($tailRead.Wait([int][Math]::Max(1,[Math]::Min(500,30000-$watch.ElapsedMilliseconds))))
  if($tailRead.Result -eq 0){break};$tailCount+=$tailRead.Result
 }
 Need ($tailCount -lt $tail.Length)
 $ack=$utf8.GetString($tail,0,$tailCount)
 $expected='S1_ACK:'+$nonce
 Need ($ack -ceq ($expected+[char]10) -or $ack -ceq ($expected+[char]13+[char]10))
 $r.elapsed_ms=[long]$watch.ElapsedMilliseconds
 $r|ConvertTo-Json -Compress
 exit $r.exit_code
} catch {
 if($null -ne $child){try{if(-not $child.HasExited){$child.Kill();[void]$child.WaitForExit(1000)}}catch{}}
 Public-Refusal 'PRECONDITIONS_REQUIRED';exit 2
} finally {if($null -ne $child){$child.Dispose()}}
