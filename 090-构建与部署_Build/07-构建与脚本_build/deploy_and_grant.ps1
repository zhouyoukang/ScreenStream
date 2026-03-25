
# ADB Path
$adb = "D:\platform-tools\adb.exe"
if (-not (Test-Path $adb)) { $adb = "C:\Users\Administrator\AppData\Local\Android\Sdk\platform-tools\adb.exe" }

# Get list of connected devices
$devices = & $adb devices -l | Select-String -Pattern "device " | ForEach-Object { $_.ToString().Split(" ")[0] }

# Attempt to find APK (current repo structure)
$repoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$potentialPaths = @(
    "$repoRoot\010-用户界面与交互_UI\build\outputs\apk\FDroid\debug\app-FDroid-debug.apk",
    "$repoRoot\010-用户界面与交互_UI\build\outputs\apk\debug\app-debug.apk"
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
    Write-Host "Searching for debug APK in repo..."
    $apkPath = Get-ChildItem -Path $repoRoot -Filter "*debug.apk" -Recurse -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -match "010-用户界面" } |
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
    Start-Sleep -Milliseconds 2000

    # Agent: start streaming module
    Write-Host "  Starting streaming module via Agent..."
    & $adb -s $device shell am broadcast -a com.screenstream.DEV_CONTROL --es command start_module -n "${pkgName}/${pkgName}.DevControlReceiver"
    Start-Sleep -Milliseconds 1500

    # Agent: launch AgentProjectionActivity for MediaProjection grant (user taps "Start now" once)
    Write-Host "  Launching AgentProjectionActivity for MediaProjection grant..."
    & $adb -s $device shell am start -n "${pkgName}/${pkgName}.AgentProjectionActivity"

    Write-Host "  Device $device ready. Tap 'Start now' in the dialog." -ForegroundColor Green
    Write-Host "  After grant, start stream: adb shell am broadcast -a com.screenstream.DEV_CONTROL --es command start_stream -n `"${pkgName}/${pkgName}.DevControlReceiver`"" -ForegroundColor Yellow
}
