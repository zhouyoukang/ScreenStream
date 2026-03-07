# P2P Direct Mode auto-restart wrapper
# Restarts desktop.py automatically on crash (mss DXGI native crash workaround)
$script = Join-Path $PSScriptRoot "desktop.py"
$pyArgs = "--direct","--port","9803","--fps","10","--quality","60","--scale","50"
$restartDelay = 3

Write-Host "[WRAPPER] P2P auto-restart wrapper started" -ForegroundColor Cyan
$crashCount = 0

while ($true) {
    $crashCount++
    Write-Host "[WRAPPER] Starting desktop.py (run #$crashCount)..." -ForegroundColor Green
    $proc = Start-Process python -ArgumentList (@("-u", $script) + $pyArgs) -NoNewWindow -PassThru -Wait
    $code = $proc.ExitCode
    Write-Host "[WRAPPER] desktop.py exited with code $code (run #$crashCount)" -ForegroundColor Yellow
    
    if ($code -eq 0) {
        Write-Host "[WRAPPER] Clean exit, stopping wrapper" -ForegroundColor Green
        break
    }
    
    Write-Host "[WRAPPER] Restarting in ${restartDelay}s..." -ForegroundColor Yellow
    Start-Sleep $restartDelay
}
