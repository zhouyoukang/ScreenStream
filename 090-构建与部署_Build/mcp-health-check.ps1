<#
.SYNOPSIS
    MCP Server Health Check + Diagnostics + Optimization
.EXAMPLE
    powershell -File mcp-health-check.ps1
#>

param(
    [switch]$Fix  # 加 -Fix 自动清理多余Node进程
)

Write-Host "`n=== MCP Health Check ===" -ForegroundColor Cyan
Write-Host "Time: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')`n"

# 1. System resources
$os = Get-CimInstance Win32_OperatingSystem
$memPct = [math]::Round(($os.TotalVisibleMemorySize - $os.FreePhysicalMemory) / $os.TotalVisibleMemorySize * 100, 0)
$cFree = [math]::Round((Get-Volume C).SizeRemaining / 1GB, 0)
$memColor = if ($memPct -gt 90) { 'Red' } elseif ($memPct -gt 85) { 'Yellow' } else { 'Green' }
$cColor = if ($cFree -lt 10) { 'Red' } elseif ($cFree -lt 20) { 'Yellow' } else { 'Green' }
Write-Host '[SYS] MEM: ' -NoNewline; Write-Host "${memPct}%" -ForegroundColor $memColor -NoNewline
Write-Host '  C: ' -NoNewline; Write-Host "${cFree}GB" -ForegroundColor $cColor

# 2. Node processes (MCP Servers are Node processes)
$nodeProcs = Get-Process -Name node -ErrorAction SilentlyContinue
$nodeCount = ($nodeProcs | Measure-Object).Count
$nodeMem = ($nodeProcs | Measure-Object -Property WorkingSet64 -Sum).Sum / 1MB
$nodeColor = if ($nodeCount -gt 15) { 'Red' } elseif ($nodeCount -gt 10) { 'Yellow' } else { 'Green' }
Write-Host '[Node] count: ' -NoNewline; Write-Host "$nodeCount" -ForegroundColor $nodeColor -NoNewline
Write-Host "  mem: $([math]::Round($nodeMem, 0))MB"

# 3. MCP process identification
Write-Host "`n--- MCP Processes ---" -ForegroundColor DarkGray
$mcpKeywords = @('playwright', 'chrome-devtools', 'context7', 'fetch-mcp', 'server-github', 'mcp')
$mcpProcs = @()
foreach ($proc in $nodeProcs) {
    try {
        $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId=$($proc.Id)").CommandLine
        $isMcp = $false
        foreach ($kw in $mcpKeywords) {
            if ($cmdLine -match $kw) { $isMcp = $true; break }
        }
        if ($isMcp) {
            $memMB = [math]::Round($proc.WorkingSet64 / 1MB, 0)
            $mcpProcs += [PSCustomObject]@{
                PID    = $proc.Id
                Mem    = "${memMB}MB"
                Server = if ($cmdLine -match 'playwright') { 'playwright' }
                elseif ($cmdLine -match 'chrome-devtools') { 'chrome-devtools' }
                elseif ($cmdLine -match 'context7') { 'context7' }
                elseif ($cmdLine -match 'fetch') { 'fetch ⚠️' }
                elseif ($cmdLine -match 'github') { 'github' }
                else { 'unknown-mcp' }
            }
        }
    }
    catch {}
}

if ($mcpProcs.Count -gt 0) {
    $mcpProcs | Format-Table -AutoSize | Out-String | Write-Host
    $mcpTotalMem = ($mcpProcs | ForEach-Object { [int]($_.Mem -replace 'MB', '') } | Measure-Object -Sum).Sum
    Write-Host "MCP total: ${mcpTotalMem}MB ($($mcpProcs.Count) procs)"
}
else {
    Write-Host '  (No active MCP procs - normal, MCP lazy-loads)' -ForegroundColor DarkGray
}

# 4. Chromium/Chrome processes (Playwright instances)
$chromiumProcs = Get-Process -Name chromium, chrome -ErrorAction SilentlyContinue
$chromiumCount = ($chromiumProcs | Measure-Object).Count
$chromiumMem = [math]::Round(($chromiumProcs | Measure-Object -Property WorkingSet64 -Sum).Sum / 1MB, 0)
if ($chromiumCount -gt 0) {
    Write-Host "`n[Browser] Chromium/Chrome: $chromiumCount procs, mem: ${chromiumMem}MB"
    if ($chromiumMem -gt 1000) {
        Write-Host '  WARN: Browser >1GB, consider browser_close' -ForegroundColor Yellow
    }
}

# 5. Context tax estimation
Write-Host "`n--- Context Tax ---" -ForegroundColor DarkGray
$servers = @(
    @{Name = 'playwright'; Tools = 22; Status = 'core' }
    @{Name = 'chrome-devtools'; Tools = 15; Status = 'core' }
    @{Name = 'context7'; Tools = 2; Status = 'useful' }
    @{Name = 'github'; Tools = 12; Status = 'useful' }
    @{Name = 'fetch'; Tools = 3; Status = 'DISABLE(IWR replaced)' }
)
$totalTools = ($servers | ForEach-Object { $_.Tools } | Measure-Object -Sum).Sum
Write-Host "  Servers: $($servers.Count), Tool defs: $totalTools"
Write-Host '  Est. context tax: 12-15 pct'
Write-Host '  After removing fetch: 11-14 pct' -ForegroundColor Green

# 6. Optimization suggestions
Write-Host "`n=== Suggestions ===" -ForegroundColor Cyan
$suggestions = @()

$fetchProc = $mcpProcs | Where-Object { $_.Server -match 'fetch' }
if ($fetchProc) {
    $suggestions += "WARN: fetch MCP running (PID:$($fetchProc.PID)), disable in IDE settings"
}
$suggestions += 'TIP: Disable fetch in IDE Settings > MCP Servers'

if ($memPct -gt 85) {
    $suggestions += "BLOCK: MEM ${memPct}pct > 85pct, no new Playwright (R5)"
    if ($chromiumMem -gt 500) {
        $suggestions += "BLOCK: Close Playwright via browser_close (${chromiumMem}MB)"
    }
}

if ($nodeCount -gt 15) {
    $suggestions += 'BLOCK: Node procs > 15, review and kill extras'
}

if ($cFree -lt 20) {
    $suggestions += 'BLOCK: C drive < 20GB, no writes to C'
}

foreach ($s in $suggestions) {
    Write-Host "  $s"
}

# 7. Quick fix commands
Write-Host "`n--- Quick Fixes ---" -ForegroundColor DarkGray
Write-Host '  Disable fetch: IDE Settings > MCP Servers > fetch > Disable'
Write-Host '  Export cookie: node mcp-auth-export.js https://site.com auth.json'
Write-Host '  Load cookie:   Playwright MCP args + --storage-state auth.json'
Write-Host '  Free browser:  Call browser_close in conversation'
Write-Host ''
