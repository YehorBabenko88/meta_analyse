param([Parameter(Mandatory=$true)][string]$ExpectedComputer,[Parameter(Mandatory=$true)][string]$MetaScalpExe,[Parameter(Mandatory=$true)][string]$Output)
$ErrorActionPreference='Stop'
if ($env:COMPUTERNAME -ne $ExpectedComputer -or ($env:COMPUTERNAME -replace '-','') -in @('LS5','LS7')) { throw 'Wrong or protected machine' }
$os=Get-CimInstance Win32_OperatingSystem
$system=Get-CimInstance Win32_ComputerSystem
$cpu=Get-CimInstance Win32_Processor
$file=Get-Item -LiteralPath $MetaScalpExe
[ordered]@{utc=[datetime]::UtcNow.ToString('o');computer=$env:COMPUTERNAME;os=$os.Caption;build=$os.BuildNumber;cpu=@($cpu.Name);ram_bytes=$system.TotalPhysicalMemory;disks=@(Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | Select-Object DeviceID,Size,FreeSpace);metascalp_version=$file.VersionInfo.FileVersion;metascalp_sha256=(Get-FileHash -LiteralPath $MetaScalpExe -Algorithm SHA256).Hash} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $Output -Encoding utf8
