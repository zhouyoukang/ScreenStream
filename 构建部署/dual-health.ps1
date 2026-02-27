<#
.SYNOPSIS
    Dual-PC health check (one-liner friendly)
.EXAMPLE
    .\构建部署\dual-health.ps1
#>
$ErrorActionPreference = 'Continue'
$pass = 0; $fail = 0
function T($n, $t) { try { if (& $t) { Write-Host "  [OK] $n" -ForegroundColor Green; $script:pass++ }else { Write-Host "  [!!] $n" -ForegroundColor Red; $script:fail++ } }catch { Write-Host "  [!!] $n" -ForegroundColor Red; $script:fail++ } }
# 从 secrets.env 加载凭据
$envFile = Join-Path $PSScriptRoot '..\secrets.env'
if (Test-Path $envFile) { Get-Content $envFile | ForEach-Object { if ($_ -match '^\s*([^#=]+?)\s*=\s*(.+)$') { Set-Item "env:$($Matches[1])" $Matches[2] } } }
$cred = New-Object PSCredential($env:DESKTOP_USER, (ConvertTo-SecureString $env:DESKTOP_PASSWORD -AsPlainText -Force))

Write-Host "===== Dual-PC Health =====" -ForegroundColor Cyan
Write-Host "[Laptop -> Desktop]"
T "Ping" { Test-Connection 192.168.31.141 -Count 1 -Quiet }
T "WinRM" { (Invoke-Command 192.168.31.141 -Credential $cred -ScriptBlock { hostname } -EA Stop) -eq ([char]21608 + [char]22823 + [char]24072 + [char]30340 + [char]21488 + [char]24335 + [char]26426 -join '') }
T "SMB(4)" { (Test-Path X:\Windows) -and (Test-Path W:\) -and (Test-Path V:\) -and (Test-Path U:\) }
T "remote_agent" { (Invoke-RestMethod http://192.168.31.141:9903/health -TimeoutSec 3).hostname }
T "FRP" { try { Invoke-RestMethod http://60.205.171.100:19903/health -TimeoutSec 5; $true }catch { $false } }

Write-Host "[Desktop -> Laptop]"
T "remote_agent" { (Invoke-RestMethod http://192.168.31.179:9903/health -TimeoutSec 3).hostname }

Write-Host "[Windsurf]"
T "Desktop WS" { (@(Invoke-Command 192.168.31.141 -Credential $cred -ScriptBlock { Get-Process Windsurf -EA 0 }).Count) -gt 0 }
T "Git sync" { (git log -1 --format="%h") -eq (git -C "W:\道\道生一\一生二" log -1 --format="%h") }

$m1 = [math]::Round((Get-CimInstance Win32_OperatingSystem | % { ($_.TotalVisibleMemorySize - $_.FreePhysicalMemory) / $_.TotalVisibleMemorySize * 100 }), 0)
$c1 = [math]::Round((Get-Volume C -EA 0).SizeRemaining / 1GB, 1)
$r = Invoke-Command 192.168.31.141 -Credential $cred -ScriptBlock {
  $m = [math]::Round((Get-CimInstance Win32_OperatingSystem | % { ($_.TotalVisibleMemorySize - $_.FreePhysicalMemory) / $_.TotalVisibleMemorySize * 100 }), 0)
  $c = [math]::Round((Get-Volume C).SizeRemaining / 1GB, 1)
  "$m%|${c}GB"
}
Write-Host "`n[Resources] Laptop: MEM=${m1}% C:${c1}GB | Desktop: $r" -ForegroundColor Gray
Write-Host "`n===== $pass OK / $fail FAIL =====" -ForegroundColor $(if ($fail -eq 0) { 'Green' }else { 'Yellow' })
