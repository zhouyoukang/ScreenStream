# 三界隔离 — 进入地界
# Usage: .\enter.ps1 [-Mode rdp|switch|auto]
# rdp    = 打开RDP窗口(天界不受影响,可并行)
# switch = 快速用户切换(天界断开但保留,切回即恢复)
# auto   = 智能选择(有断开会话→switch, 否则→rdp)
param(
    [ValidateSet('rdp','switch','auto')]
    [string]$Mode = 'auto'
)

$AgentUser = 'windsurf-test'
$RdpFile = Join-Path $PSScriptRoot '地界.rdp'

# --- 探测会话 ---
$raw = query session 2>$null
$agentLine = $raw | Where-Object { $_ -match $AgentUser }
$agentId = $null
$agentState = 'none'
if ($agentLine -and $agentLine -match '\s+(\d+)\s+') {
    $agentId = $matches[1]
    if ($agentLine -match '断开|Disc') { $agentState = 'disconnected' }
    elseif ($agentLine -match '运行中|Active') { $agentState = 'active' }
}

# --- 状态显示 ---
Write-Host ""
Write-Host "  道 之 隔 离" -ForegroundColor Cyan
Write-Host "  天界 (zhouyoukang) : console, 运行中" -ForegroundColor Green
$icon = switch($agentState) { 'active'{'运行中','Green'} 'disconnected'{'断开(可恢复)','Yellow'} default{'未启动','DarkGray'} }
Write-Host "  地界 ($AgentUser)  : $($icon[0])" -ForegroundColor $icon[1]
Write-Host ""

# --- 自动模式决策 ---
if ($Mode -eq 'auto') {
    $Mode = if ($agentState -eq 'disconnected') { 'switch' } else { 'rdp' }
}

# --- 执行 ---
switch ($Mode) {
    'rdp' {
        Write-Host "  >> 打开RDP窗口到地界 (天界保持不变)" -ForegroundColor Green
        if (Test-Path $RdpFile) {
            Start-Process mstsc.exe -ArgumentList "`"$RdpFile`""
        } else {
            Start-Process mstsc.exe -ArgumentList '/v:127.0.0.1'
        }
        Write-Host "  >> 首次需输入 windsurf-test 密码, 勾选'记住凭据'后免密" -ForegroundColor DarkGray
    }
    'switch' {
        if ($agentId) {
            Write-Host "  >> 快速切换到地界 (Session $agentId)" -ForegroundColor Yellow
            Write-Host "  >> 天界会断开但程序继续运行, Ctrl+Alt+Del可切回" -ForegroundColor Yellow
            tscon $agentId /dest:console
        } else {
            Write-Host "  >> 地界无活跃会话, 改用RDP启动..." -ForegroundColor Yellow
            if (Test-Path $RdpFile) {
                Start-Process mstsc.exe -ArgumentList "`"$RdpFile`""
            } else {
                Start-Process mstsc.exe -ArgumentList '/v:127.0.0.1'
            }
        }
    }
}
