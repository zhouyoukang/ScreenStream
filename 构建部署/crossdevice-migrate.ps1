<#
.SYNOPSIS
    CrossDevice C->E 迁移脚本 (73.7GB Samsung照片)
.DESCRIPTION
    将 C:\Users\zhouyoukang\CrossDevice 迁移到 E:\CrossDevice
    使用 robocopy /MOVE，完成后创建 Junction 保持路径兼容
.NOTES
    运行前建议: 关闭不必要的浏览器标签降低内存到85%以下
    预计耗时: 10-30分钟(取决于磁盘速度)
#>

$src = "C:\Users\zhouyoukang\CrossDevice"
$dst = "E:\CrossDevice"

# Pre-flight check
$os = Get-CimInstance Win32_OperatingSystem
$memPct = [math]::Round(($os.TotalVisibleMemorySize - $os.FreePhysicalMemory) / $os.TotalVisibleMemorySize * 100, 0)
$eFree = [math]::Round((Get-Volume E).SizeRemaining/1GB, 1)

Write-Host "=== CrossDevice Migration Pre-flight ===" -ForegroundColor Cyan
Write-Host "Memory: ${memPct}%"
Write-Host "E: free: ${eFree}GB"
Write-Host "Source: $src"

if($memPct -gt 95) {
    Write-Host "BLOCKED: Memory ${memPct}% > 95%. Close apps first." -ForegroundColor Red
    exit 1
}
if($eFree -lt 80) {
    Write-Host "BLOCKED: E: only ${eFree}GB free, need 80GB+" -ForegroundColor Red
    exit 1
}

# Check source is real directory (not already a junction)
$item = Get-Item $src -Force -EA SilentlyContinue
if(!$item) {
    Write-Host "Source not found: $src" -ForegroundColor Red
    exit 1
}
if($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
    Write-Host "Source is already a junction. Migration already done." -ForegroundColor Green
    exit 0
}

$srcSize = (Get-ChildItem $src -Recurse -File -Force -EA SilentlyContinue | Measure-Object Length -Sum).Sum
Write-Host "Source size: $([math]::Round($srcSize/1GB,1))GB"
Write-Host ""
Write-Host "Starting migration in 5 seconds... (Ctrl+C to cancel)" -ForegroundColor Yellow
Start-Sleep 5

# Create destination
if(!(Test-Path $dst)) { New-Item -ItemType Directory -Path $dst -Force | Out-Null }

# Robocopy MOVE
Write-Host "Running robocopy /MOVE ..." -ForegroundColor Cyan
$logFile = "$env:TEMP\crossdevice_migrate_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"
$proc = Start-Process robocopy -ArgumentList "`"$src`" `"$dst`" /E /MOVE /R:1 /W:1 /MT:4 /LOG:`"$logFile`"" -Wait -PassThru -NoNewWindow

if($proc.ExitCode -le 3) {
    Write-Host "Robocopy completed successfully (exit code $($proc.ExitCode))" -ForegroundColor Green
    
    # Remove empty source directory
    if(Test-Path $src) {
        Remove-Item $src -Recurse -Force -EA SilentlyContinue
    }
    
    # Create junction for path compatibility
    cmd /c "mklink /J `"$src`" `"$dst`""
    
    Write-Host ""
    Write-Host "=== Migration Complete ===" -ForegroundColor Green
    Write-Host "Data: $dst"
    Write-Host "Junction: $src -> $dst"
    
    $cFree = [math]::Round((Get-Volume C).SizeRemaining/1GB, 1)
    Write-Host "C: now ${cFree}GB free"
} else {
    Write-Host "Robocopy error (exit code $($proc.ExitCode)). Check log: $logFile" -ForegroundColor Red
}
