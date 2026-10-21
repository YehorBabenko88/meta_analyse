# Read-only native probes. Dot-source only from the manifested collector.
$probeIdentity=[Security.Principal.WindowsIdentity]::GetCurrent()
if (-not ([Security.Principal.WindowsPrincipal]::new($probeIdentity)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
 throw 'ELEVATED_TOKEN_REQUIRED'
}
if (-not ('MetaCommissionInventory.Probe' -as [type])) {
Add-Type -TypeDefinition @'
using System;
using System.Text;
using System.Collections.Generic;
using Microsoft.Win32;
using System.Runtime.InteropServices;
namespace MetaCommissionInventory {
 public sealed class ProcessRow { public int pid; public string path=""; public long created; public bool alive,image_query_succeeded; public string error_stage=""; public int win32_error; }
 public sealed class ServiceRow { public string name; public int pid; public int state; public string binary_path; public string error_stage=""; public int win32_error; }
 public sealed class KernelRow { public int pid; public string name; public long created; public int parent_pid; public int session_id; }
  public sealed class ServiceSet { public bool complete; public string reason_code="SERVICE_COVERAGE_UNAVAILABLE",error_stage="",failed_service=""; public int win32_error; public ServiceRow[] services=new ServiceRow[0]; }
 public static class Probe {
  [DllImport("kernel32.dll",SetLastError=true)] static extern IntPtr OpenProcess(uint access,bool inherit,int pid);
  [DllImport("kernel32.dll",SetLastError=true)] static extern bool GetProcessTimes(IntPtr h,out long created,out long exited,out long kernel,out long user);
  [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern bool QueryFullProcessImageName(IntPtr h,uint flags,StringBuilder path,ref int length);
  [DllImport("kernel32.dll",SetLastError=true)] static extern bool GetExitCodeProcess(IntPtr h,out uint code);
  [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr h);
  [DllImport("advapi32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern IntPtr OpenSCManager(string machine,string database,uint access);
  [DllImport("advapi32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern IntPtr OpenService(IntPtr manager,string name,uint access);
  [DllImport("advapi32.dll",SetLastError=true)] static extern bool QueryServiceStatusEx(IntPtr service,int level,ref ServiceStatus status,int size,out int required);
  [DllImport("advapi32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern bool QueryServiceConfig(IntPtr service,IntPtr config,int size,out int required);
  [DllImport("advapi32.dll")] static extern bool CloseServiceHandle(IntPtr h);
  [DllImport("ntdll.dll")] static extern int NtQuerySystemInformation(int info,IntPtr buffer,int size,out int required);
  [StructLayout(LayoutKind.Sequential)] struct ServiceStatus { public uint type,state,accepted,win32exit,serviceexit,checkpoint,waitHint,pid,flags; }
  [StructLayout(LayoutKind.Sequential)] struct ServiceConfig { public uint type,start,error; public IntPtr binary,group; public uint tag; public IntPtr dependencies,startName,displayName; }
  public static ServiceSet ReadBindings(int pid) {
   // EnumServicesStatusEx silently omits services lacking QUERY_STATUS access.
   // Enumerate the independent registry namespace and explicitly query EVERY
   // Win32 service status. Any unreadable key/status means incomplete coverage.
   ServiceSet result=new ServiceSet();IntPtr manager=OpenSCManager(null,null,1);
   if(manager==IntPtr.Zero){result.win32_error=Marshal.GetLastWin32Error();result.error_stage="OPEN_SCM";return result;}
   try {
    using(RegistryKey root=Registry.LocalMachine.OpenSubKey(@"SYSTEM\CurrentControlSet\Services",false)) {
     if(root==null)return result;
     string[] names=root.GetSubKeyNames();if(names.Length==0||names.Length>65536)return result;
     Array.Sort(names,StringComparer.OrdinalIgnoreCase);
     List<ServiceRow> rows=new List<ServiceRow>();
     foreach(string name in names) {
      using(RegistryKey key=root.OpenSubKey(name,false)) {
       if(key==null)return result;
       // Query native status for every registered name, including keys without
       // Type metadata. Only SCM ERROR_SERVICE_DOES_NOT_EXIST proves an orphan
       // registry key is not a running service; AccessDenied is never absence.
       IntPtr service=OpenService(manager,name,4);
       if(service==IntPtr.Zero) {
        int error=Marshal.GetLastWin32Error();if(error==1060)continue;
        result.win32_error=error;result.error_stage="OPEN_SERVICE_STATUS";result.failed_service=name;
        result.reason_code="SERVICE_STATUS_UNAVAILABLE";return result;
       }
       try {
        ServiceStatus status=new ServiceStatus();int required;
        if(!QueryServiceStatusEx(service,0,ref status,Marshal.SizeOf(typeof(ServiceStatus)),out required)) {result.win32_error=Marshal.GetLastWin32Error();result.error_stage="QUERY_SERVICE_STATUS";result.failed_service=name;result.reason_code="SERVICE_STATUS_UNAVAILABLE";return result;}
        if((status.type&0x30)==0)continue;
        if(status.pid!=(uint)pid)continue;
        ServiceRow row=ReadService(name);
        if(row.error_stage!=""){result.error_stage=row.error_stage;result.win32_error=row.win32_error;result.failed_service=name;return result;}
        if(row.pid!=pid||row.state!=(int)status.state){result.error_stage="SERVICE_STATUS_CHANGED";result.failed_service=name;return result;}
        rows.Add(row);
       } finally {CloseServiceHandle(service);}
      }
     }
     string[] finalNames=root.GetSubKeyNames();Array.Sort(finalNames,StringComparer.OrdinalIgnoreCase);
     if(names.Length!=finalNames.Length)return result;
     for(int i=0;i<names.Length;i++)if(!StringComparer.OrdinalIgnoreCase.Equals(names[i],finalNames[i]))return result;
     result.services=rows.ToArray();result.complete=true;result.reason_code="COMPLETE_REGISTRY_SCM_COVERAGE";return result;
    }
   } catch {return result;} finally {CloseServiceHandle(manager);}
  }
  public static ProcessRow ReadProcess(int pid) {
   ProcessRow row=new ProcessRow {pid=pid};
   IntPtr h=OpenProcess(0x1000,false,pid); // PROCESS_QUERY_LIMITED_INFORMATION only.
   if(h==IntPtr.Zero){row.win32_error=Marshal.GetLastWin32Error();row.error_stage="OPEN_PROCESS";return row;}
   try {
    long created,exited,kernel,user;uint exit;
    if(!GetProcessTimes(h,out created,out exited,out kernel,out user)){row.win32_error=Marshal.GetLastWin32Error();row.error_stage="GET_PROCESS_TIMES";return row;}
    if(!GetExitCodeProcess(h,out exit)){row.win32_error=Marshal.GetLastWin32Error();row.error_stage="GET_EXIT_CODE";return row;}
    row.created=created;row.alive=exit==259 && exited==0;
    StringBuilder path=new StringBuilder(32768);int length=path.Capacity;
    bool found=QueryFullProcessImageName(h,0,path,ref length);
    if(!found){row.win32_error=Marshal.GetLastWin32Error();row.error_stage="QUERY_IMAGE";}
    row.image_query_succeeded=found;row.path=found?path.ToString():"";return row;
   } finally {CloseHandle(h);}
  }
  public static ServiceRow ReadService(string name) {
   ServiceRow row=new ServiceRow {name=name};
   IntPtr manager=OpenSCManager(null,null,1);if(manager==IntPtr.Zero){row.win32_error=Marshal.GetLastWin32Error();row.error_stage="OPEN_SCM";return row;}
   try {
    IntPtr service=OpenService(manager,name,5); // QUERY_CONFIG | QUERY_STATUS only.
    if(service==IntPtr.Zero){row.win32_error=Marshal.GetLastWin32Error();row.error_stage="OPEN_SERVICE_CONFIG";return row;}
    try {
     ServiceStatus status=new ServiceStatus();int size;
     if(!QueryServiceStatusEx(service,0,ref status,Marshal.SizeOf(typeof(ServiceStatus)),out size)){row.win32_error=Marshal.GetLastWin32Error();row.error_stage="QUERY_SERVICE_STATUS";return row;}
     QueryServiceConfig(service,IntPtr.Zero,0,out size);
     int configError=Marshal.GetLastWin32Error();
     if(size<=0||size>65536){row.win32_error=configError;row.error_stage="QUERY_SERVICE_CONFIG_SIZE";return row;}
     IntPtr buffer=Marshal.AllocHGlobal(size);
     try {
      if(!QueryServiceConfig(service,buffer,size,out size)){row.win32_error=Marshal.GetLastWin32Error();row.error_stage="QUERY_SERVICE_CONFIG";return row;}
      ServiceConfig config=(ServiceConfig)Marshal.PtrToStructure(buffer,typeof(ServiceConfig));
      row.pid=(int)status.pid;row.state=(int)status.state;row.binary_path=Marshal.PtrToStringUni(config.binary);return row;
     } finally {Marshal.FreeHGlobal(buffer);}
    } finally {CloseServiceHandle(service);}
   } finally {CloseServiceHandle(manager);}
  }
  public static KernelRow ReadKernel(int wanted) {
   // Windows x64 SYSTEM_PROCESS_INFORMATION prefix. Reject unknown ABI/layout;
   // independently compare the collector's native creation time before using it.
   if(IntPtr.Size!=8)return null;
   for(int capacity=262144;capacity<=33554432;capacity*=2) {
    IntPtr buffer=Marshal.AllocHGlobal(capacity);
    try {
     int required;int status=NtQuerySystemInformation(5,buffer,capacity,out required);
     if(status==unchecked((int)0xC0000004))continue;
     if(status!=0||required<104||required>capacity)return null;
     int offset=0;KernelRow result=null;bool selfChecked=false;
     ProcessRow self=ReadProcess(System.Diagnostics.Process.GetCurrentProcess().Id);
     if(self==null||!self.alive)return null;
     for(int count=0;count<65536;count++) {
      if(offset<0||offset>required-104)return null;
      IntPtr entry=IntPtr.Add(buffer,offset);
      int next=Marshal.ReadInt32(entry,0);
      long id=Marshal.ReadIntPtr(entry,80).ToInt64();long parent=Marshal.ReadIntPtr(entry,88).ToInt64();
      long created=Marshal.ReadInt64(entry,32);
      if(id==self.pid && created==self.created)selfChecked=true;
      if(id==wanted) {
       int length=(ushort)Marshal.ReadInt16(entry,56);IntPtr name=Marshal.ReadIntPtr(entry,64);
       long relative=name.ToInt64()-buffer.ToInt64();
       if(length%2!=0||length>1024||(length>0&&(relative<0||relative+length>required))||parent<0||parent>int.MaxValue)return null;
       result=new KernelRow {pid=wanted,name=length==0?"":Marshal.PtrToStringUni(name,length/2),created=created,parent_pid=(int)parent,session_id=Marshal.ReadInt32(entry,100)};
      }
      if(next==0)return selfChecked?result:null;
      if(next<104||next%8!=0||next>required-offset-104)return null;
      offset+=next;
     }
     return null;
    } finally {Marshal.FreeHGlobal(buffer);}
   }
   return null;
  }
 }
}
'@
}

function Get-MissingProcessEvidence {
 param([Parameter(Mandatory=$true)]$ProcessRecord)
 $idValue=[int]$ProcessRecord.ProcessId
 $row=[ordered]@{pid=$idValue;name=$ProcessRecord.Name;parent_pid=$ProcessRecord.ParentProcessId;session_id=$ProcessRecord.SessionId;created=$null;cim_path=$ProcessRecord.ExecutablePath}
 if ($ProcessRecord.CreationDate) { $row.created=$ProcessRecord.CreationDate.ToUniversalTime().ToFileTimeUtc() }
 $proof=[ordered]@{}
 try {
  if ($idValue -in @(0,4)) {
   $proof.kernel_before=[MetaCommissionInventory.Probe]::ReadKernel($idValue)
   $proof.kernel_after=[MetaCommissionInventory.Probe]::ReadKernel($idValue)
  } else {
   $proof.native_before=[MetaCommissionInventory.Probe]::ReadProcess($idValue)
   $beforeSet=[MetaCommissionInventory.Probe]::ReadBindings($idValue)
   $proof.services_before_complete=$beforeSet.complete
   $proof.services_before_reason=$beforeSet.reason_code
   $proof.services_before_diagnostics=[ordered]@{stage=$beforeSet.error_stage;win32_error=$beforeSet.win32_error;failed_service=$beforeSet.failed_service}
   $proof.services_before=@($beforeSet.services)
   $path=$proof.native_before.path
   if ($path -and [IO.Path]::IsPathRooted($path) -and (Test-Path -LiteralPath $path -PathType Leaf)) {
    $reparse=$false;$ancestor=Get-Item -LiteralPath $path -Force
    while ($ancestor) { if ($ancestor.Attributes -band [IO.FileAttributes]::ReparsePoint) {$reparse=$true};if($ancestor -is [IO.FileInfo]){$ancestor=$ancestor.Directory}else{$ancestor=$ancestor.Parent} }
    $hash=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    $signature=Get-AuthenticodeSignature -LiteralPath $path
    $proof.signature=[ordered]@{path=$path;status=$signature.Status.ToString();subject=$signature.SignerCertificate.Subject;sha256=$hash;sha256_after=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant();reparse_point=$reparse}
   }
   $afterSet=[MetaCommissionInventory.Probe]::ReadBindings($idValue)
   $proof.services_after_complete=$afterSet.complete
   $proof.services_after_reason=$afterSet.reason_code
   $proof.services_after_diagnostics=[ordered]@{stage=$afterSet.error_stage;win32_error=$afterSet.win32_error;failed_service=$afterSet.failed_service}
   $proof.services_after=@($afterSet.services)
   $proof.native_after=[MetaCommissionInventory.Probe]::ReadProcess($idValue)
  }
 } catch { $proof.collection_error='PROCESS_EVIDENCE_UNAVAILABLE' }
 [ordered]@{process=$row;evidence=$proof}
}
