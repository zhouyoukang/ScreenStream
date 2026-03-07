
# ADB Path
$adb = "C:\Users\Administrator\AppData\Local\Android\Sdk\platform-tools\adb.exe"

# Get list of connected devices
$devices = & $adb devices -l | Select-String -Pattern "device " | ForEach-Object { $_.ToString().Split(" ")[0] }

# Attempt to find APK
$potentialPaths = @(
    "F:\github\AIOT\ScreenStream_v2\mjpeg\build\outputs\apk\playStore\debug\mjpeg-playStore-debug.apk",
    "F:\github\AIOT\ScreenStream_v2\app\build\outputs\apk\debug\app-debug.apk",
    "F:\github\AIOT\ScreenStream_v2\mjpeg\build\outputs\apk\debug\mjpeg-debug.apk"
)

$apkPath = $null
foreach ($path in $potentialPaths) {
    if (Test-Path $path) {
        $apkPath = $path
        break
    }
}

# If exact path fails, search recursively
if (-not $apkPath) {
    Write-Host "Searching for debug APK..."
    $apkPath = Get-ChildItem -Path "F:\github\AIOT\ScreenStream_v2" -Filter "*debug.apk" -Recurse -ErrorAction SilentlyContinue | 
    Sort-Object LastWriteTime -Descending | 
    Select-Object -First 1 -ExpandProperty FullName
}

if (-not $apkPath) {
    Write-Host "Critical: Could not find any debug APK." -ForegroundColor Red
    exit
}

Write-Host "Using APK: $apkPath" -ForegroundColor Cyan
$pkgName = "info.dvkr.screenstream.dev"

foreach ($device in $devices) {
    if ([string]::IsNullOrWhiteSpace($device)) { continue }
    
    Write-Host "Processing Device: $device" -ForegroundColor Cyan
    
    # install
    Write-Host "  Installing APK..." -NoNewline
    & $adb -s $device install -r -g $apkPath
    if ($LASTEXITCODE -eq 0) { Write-Host "Done" -ForegroundColor Green } else { Write-Host "Failed" -ForegroundColor Red; continue }

    # Grant permissions
    Write-Host "  Granting permissions..."
    & $adb -s $device shell pm grant $pkgName android.permission.POST_NOTIFICATIONS
    & $adb -s $device shell pm grant $pkgName android.permission.RECORD_AUDIO
    
    # Launch App
    Write-Host "  Launching App..."
    & $adb -s $device shell monkey -p $pkgName -c android.intent.category.LAUNCHER 1
    
    Write-Host "  Device $device ready." -ForegroundColor Green
}
