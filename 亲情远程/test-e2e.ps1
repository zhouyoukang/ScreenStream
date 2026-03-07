# Family Remote E2E Test
$ADB = "D:\platform-tools\adb.exe"
$SIGNAL = "http://localhost:9100"
$ErrorActionPreference = "Continue"

Write-Host "`n=== Family Remote E2E Test ===" -ForegroundColor Cyan

# 1. ADB
Write-Host "[1/6] ADB" -ForegroundColor Yellow
$dev = & $ADB devices | Select-String "device$"
if (-not $dev) { Write-Host "  FAIL: no device" -ForegroundColor Red; exit 1 }
Write-Host "  OK: $($dev.Line.Trim())" -ForegroundColor Green

# 2. Port forward
Write-Host "[2/6] Port forward" -ForegroundColor Yellow
& $ADB forward tcp:8080 tcp:8080 2>$null
& $ADB forward tcp:8081 tcp:8081 2>$null
& $ADB forward tcp:8084 tcp:8084 2>$null
Write-Host "  OK: 8080/8081/8084" -ForegroundColor Green

# 3. API
Write-Host "[3/6] API health" -ForegroundColor Yellow
$status = curl.exe -s -m 3 http://127.0.0.1:8084/status 2>$null
Write-Host "  /status: $status"
$gw = curl.exe -s -m 3 -o NUL -w '%{http_code}' http://127.0.0.1:8080/ 2>$null
Write-Host "  Gateway: HTTP $gw"

# 4. Stream
Write-Host "[4/6] Stream" -ForegroundColor Yellow
$ports = & $ADB shell "netstat -tlnp 2>/dev/null" 2>$null
if ($ports -match '8081') { Write-Host "  MJPEG :8081 online" -ForegroundColor Green }
else { Write-Host "  MJPEG :8081 not listening (stream not started or WebRTC mode)" -ForegroundColor Yellow }

# 5. Control
Write-Host "[5/6] Control" -ForegroundColor Yellow
$r1 = curl.exe -s -m 3 -X POST http://127.0.0.1:8084/home 2>$null
Write-Host "  /home: $r1"
Start-Sleep -Milliseconds 500
$r2 = curl.exe -s -m 3 -X POST http://127.0.0.1:8084/back 2>$null
Write-Host "  /back: $r2"
$r3 = curl.exe -s -m 3 http://127.0.0.1:8084/foreground 2>$null
Write-Host "  /foreground: $r3"

# 6. Signaling
Write-Host "[6/6] Signaling" -ForegroundColor Yellow
$sp = curl.exe -s -m 3 -o NUL -w '%{http_code}' "${SIGNAL}/app/ping" 2>$null
Write-Host "  /app/ping: HTTP $sp"
$vp = curl.exe -s -m 3 -o NUL -w '%{http_code}' "${SIGNAL}/cast/" 2>$null
Write-Host "  /cast/: HTTP $vp"

# Summary
Write-Host "`n=== URLs ===" -ForegroundColor Yellow
Write-Host "  ScreenStream UI: http://127.0.0.1:8080"
$viewerUrl = "${SIGNAL}/cast/"
Write-Host "  Family Viewer:   ${viewerUrl}"
Write-Host ""
