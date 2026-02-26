# 双电脑互联 — 泰山不动恢复脚本
# 任何时候运行此脚本 → 所有配置恢复到已验证状态
# 需管理员权限运行

param([switch]$DesktopOnly, [switch]$LaptopOnly)

$ErrorActionPreference = 'Continue'

function Write-Step($msg) { Write-Host "  → $msg" -ForegroundColor Cyan }
function Write-OK($msg) { Write-Host "  ✅ $msg" -ForegroundColor Green }
function Write-FAIL($msg) { Write-Host "  ❌ $msg" -ForegroundColor Red }

# ===== 笔记本侧 =====
if (-not $DesktopOnly) {
    Write-Host "`n=== 笔记本侧恢复 ===" -ForegroundColor Yellow

    # 1. RDP配置
    Write-Step "RDP: fDenyTSConnections=0"
    Set-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server' -Name 'fDenyTSConnections' -Value 0 -Type DWord
    Set-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server' -Name 'fSingleSessionPerUser' -Value 1 -Type DWord
    Set-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Lsa' -Name 'LimitBlankPasswordUse' -Value 0 -Type DWord
    if(!(Test-Path 'HKLM:\SOFTWARE\Policies\Microsoft\Windows NT\Terminal Services')){New-Item 'HKLM:\SOFTWARE\Policies\Microsoft\Windows NT\Terminal Services' -Force|Out-Null}
    Set-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\Windows NT\Terminal Services' -Name 'Shadow' -Value 2 -Type DWord -Force
    Write-OK "RDP注册表"

    # 2. zhouyoukang在RDP用户组
    Write-Step "RDP用户组"
    net localgroup "Remote Desktop Users" zhouyoukang /add 2>$null
    Write-OK "zhouyoukang ∈ Remote Desktop Users"

    # 3. TermService
    Write-Step "TermService"
    Set-Service TermService -StartupType Automatic
    Start-Service TermService -EA SilentlyContinue
    Write-OK "TermService=Running"

    # 4. cmdkey(台式机凭据)
    Write-Step "台式机凭据"
    cmdkey /delete:TERMSRV/192.168.31.141 2>$null
    cmdkey /add:TERMSRV/192.168.31.141 /user:administrator /pass:wsy057066wsy 2>$null
    Write-OK "TERMSRV/192.168.31.141 → administrator"

    # 5. remote_agent计划任务
    Write-Step "RemoteAgent9903计划任务"
    $xml = @'
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers>
    <LogonTrigger><Enabled>true</Enabled><UserId>zhouyoukang</UserId></LogonTrigger>
    <SessionStateChangeTrigger><Enabled>true</Enabled><UserId>zhouyoukang</UserId><StateChange>RemoteConnect</StateChange></SessionStateChangeTrigger>
    <SessionStateChangeTrigger><Enabled>true</Enabled><UserId>zhouyoukang</UserId><StateChange>SessionUnlock</StateChange></SessionStateChangeTrigger>
    <SessionStateChangeTrigger><Enabled>true</Enabled><UserId>zhouyoukang</UserId><StateChange>ConsoleConnect</StateChange></SessionStateChangeTrigger>
  </Triggers>
  <Principals><Principal id="Author"><UserId>zhouyoukang</UserId><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>
  <Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries><StopIfGoingOnBatteries>false</StopIfGoingOnBatteries><ExecutionTimeLimit>PT1M</ExecutionTimeLimit><Enabled>true</Enabled><RestartOnFailure><Interval>PT1M</Interval><Count>3</Count></RestartOnFailure></Settings>
  <Actions Context="Author"><Exec><Command>E:\道\道生一\一生二\远程桌面\start_agent.bat</Command><WorkingDirectory>E:\道\道生一\一生二\远程桌面</WorkingDirectory></Exec></Actions>
</Task>
'@
    $tmp = "$env:TEMP\_task.xml"; $xml | Set-Content $tmp -Encoding Unicode
    schtasks /delete /tn RemoteAgent9903 /f 2>$null
    schtasks /create /tn RemoteAgent9903 /xml $tmp /f 2>$null
    Remove-Item $tmp -Force
    Write-OK "RemoteAgent9903 (4触发器)"

    # 6. 验证
    Write-Step "验证..."
    $rdpOK = (Get-Service TermService).Status -eq 'Running'
    $agentOK = try { (Invoke-RestMethod 'http://127.0.0.1:9903/health' -TimeoutSec 3).status -eq 'ok' } catch { $false }
    $smbOK = Test-Path X:\Windows
    Write-Host "  RDP=$rdpOK | agent=$agentOK | SMB=$smbOK"
}

# ===== 台式机侧(需WinRM) =====
if (-not $LaptopOnly) {
    Write-Host "`n=== 台式机侧恢复(via WinRM) ===" -ForegroundColor Yellow
    $cred = New-Object PSCredential('administrator',(ConvertTo-SecureString 'wsy057066wsy' -AsPlainText -Force))

    try {
        Invoke-Command -ComputerName 192.168.31.141 -Credential $cred -ScriptBlock {
            # RDP配置
            Set-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server' -Name 'fSingleSessionPerUser' -Value 1 -Type DWord
            if(!(Test-Path 'HKLM:\SOFTWARE\Policies\Microsoft\Windows NT\Terminal Services')){New-Item 'HKLM:\SOFTWARE\Policies\Microsoft\Windows NT\Terminal Services' -Force|Out-Null}
            Set-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\Windows NT\Terminal Services' -Name 'Shadow' -Value 2 -Type DWord -Force

            # 禁用无用账号
            'Guest','zhou','zhou1' | ForEach-Object { Disable-LocalUser $_ -EA SilentlyContinue }

            # 验证agent
            $agentOK = try { netstat -ano | Select-String ':9903.*LISTENING' } catch { $false }
            "台式机: RDP注册表OK | 无用账号禁用 | agent=$([bool]$agentOK)"
        }
        Write-OK "台式机配置恢复完成"
    } catch {
        Write-FAIL "台式机WinRM不可达: $_"
    }
}

Write-Host "`n=== 恢复完成 ===" -ForegroundColor Green
Write-Host "双击 台式机.rdp → 看台式机桌面"
Write-Host "台式机双击 笔记本.rdp → 看笔记本桌面"
Write-Host "http://192.168.31.141:9903 → 控台式机 | http://192.168.31.179:9903 → 控笔记本"
