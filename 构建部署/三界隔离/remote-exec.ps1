# Three Realms Isolation - Remote Execution in Agent Realm
# Run commands in windsurf-test context from zhouyoukang session
# Usage: .\remote-exec.ps1 -Command "whoami"
#        .\remote-exec.ps1 -Command "git -C 'E:\道\道生一\一生二' status"
#        .\remote-exec.ps1 -ScriptFile "E:\道\道生一\一生二\构建部署\三界隔离\init-agent.ps1"
param(
    [string]$Command,
    [string]$ScriptFile,
    [string]$User = 'windsurf-test'
)

if (-not $Command -and -not $ScriptFile) {
    Write-Host "Usage:" -ForegroundColor Cyan
    Write-Host "  .\remote-exec.ps1 -Command 'whoami'"
    Write-Host "  .\remote-exec.ps1 -ScriptFile 'path\to\script.ps1'"
    return
}

# Build credential (uses saved credential from cmdkey, or prompts)
$savedCred = cmdkey /list:TERMSRV/127.0.0.1 2>$null
if ($savedCred -match $User) {
    Write-Host "  [+] Using saved credentials for $User" -ForegroundColor Green
} else {
    Write-Host "  [!] No saved credentials. Run save-cred.ps1 first, or enter password:" -ForegroundColor Yellow
}

$cred = Get-Credential -UserName ".\$User" -Message "Agent Realm ($User) password"
if (-not $cred) {
    Write-Host "  Cancelled." -ForegroundColor Red
    return
}

try {
    if ($Command) {
        Write-Host "  >> Executing in Agent Realm: $Command" -ForegroundColor Cyan
        $sb = [scriptblock]::Create($Command)
        Invoke-Command -ComputerName localhost -Credential $cred -ScriptBlock $sb
    }
    elseif ($ScriptFile) {
        if (-not (Test-Path $ScriptFile)) {
            Write-Host "  Script not found: $ScriptFile" -ForegroundColor Red
            return
        }
        Write-Host "  >> Executing script in Agent Realm: $ScriptFile" -ForegroundColor Cyan
        Invoke-Command -ComputerName localhost -Credential $cred -FilePath $ScriptFile
    }
    Write-Host "`n  >> Done." -ForegroundColor Green
}
catch {
    Write-Host "  >> Error: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.Exception.Message -match 'Access is denied|WinRM') {
        Write-Host "  Hint: windsurf-test is in Remote Management Users group." -ForegroundColor Yellow
        Write-Host "  Try: Enable-PSRemoting -Force (as admin)" -ForegroundColor Yellow
    }
}
