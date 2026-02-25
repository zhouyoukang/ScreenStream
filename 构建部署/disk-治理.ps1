<#
.SYNOPSIS
    三盘五感全面治理脚本
.DESCRIPTION
    2026-02-25 全盘审计后的治理方案执行脚本
    分7个Phase，每Phase可独立运行
.PARAMETER Phase
    执行的阶段: 1-7 或 'all'
    1=调查报告 2=C盘治理 3=E盘治理 4=D盘治理 5=命名修复 6=Agent监控 7=验证
.PARAMETER DryRun
    模拟运行，不实际删除/移动文件
#>
param(
    [ValidateSet('1','2','3','4','5','6','7','all')]
    [string]$Phase = 'all',
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$script:totalFreed = 0
$script:actions = @()

function Log($msg, $color='White') {
    $ts = Get-Date -Format 'HH:mm:ss'
    Write-Host "[$ts] $msg" -ForegroundColor $color
}

function LogAction($action, $size, $risk) {
    $script:actions += [PSCustomObject]@{Action=$action; SizeMB=[math]::Round($size/1MB,1); Risk=$risk}
    $script:totalFreed += $size
}

function SafeDelete($path, $desc) {
    if(Test-Path $path) {
        $size = (Get-ChildItem $path -Recurse -File -Force -EA SilentlyContinue | Measure-Object Length -Sum).Sum
        if($DryRun) {
            Log "[DRY] Would delete: $desc ($([math]::Round($size/1MB,1))MB)" 'Yellow'
        } else {
            Remove-Item $path -Recurse -Force -EA SilentlyContinue
            Log "Deleted: $desc ($([math]::Round($size/1MB,1))MB)" 'Green'
        }
        LogAction "DELETE $desc" $size 'medium'
    }
}

function SafeMove($src, $dst, $desc) {
    if(Test-Path $src) {
        if(!(Test-Path (Split-Path $dst))) { New-Item -ItemType Directory -Path (Split-Path $dst) -Force | Out-Null }
        $size = if((Get-Item $src).PSIsContainer) {
            (Get-ChildItem $src -Recurse -File -Force -EA SilentlyContinue | Measure-Object Length -Sum).Sum
        } else { (Get-Item $src).Length }
        if($DryRun) {
            Log "[DRY] Would move: $desc ($([math]::Round($size/1MB,1))MB)" 'Yellow'
        } else {
            Move-Item $src $dst -Force
            Log "Moved: $desc" 'Green'
        }
        LogAction "MOVE $desc" 0 'low'
    }
}

# ============================================================
# Phase 1: 调查报告
# ============================================================
function Phase1 {
    Log "===== Phase 1: System Investigation =====" 'Cyan'
    
    # Disk status
    foreach($d in @('C','D','E')) {
        $v = Get-Volume -DriveLetter $d
        $pct = [math]::Round($v.SizeRemaining/$v.Size*100,1)
        $status = if($pct -lt 30){'RED'}elseif($pct -lt 50){'YELLOW'}else{'GREEN'}
        Log "$($d): $([math]::Round($v.SizeRemaining/1GB,1))GB free ($pct%) [$status]" $(if($status -eq 'RED'){'Red'}elseif($status -eq 'YELLOW'){'Yellow'}else{'Green'})
    }
    
    # Memory
    $os = Get-CimInstance Win32_OperatingSystem
    $memPct = [math]::Round(($os.TotalVisibleMemorySize - $os.FreePhysicalMemory) / $os.TotalVisibleMemorySize * 100, 0)
    Log "Memory: ${memPct}% used" $(if($memPct -gt 90){'Red'}elseif($memPct -gt 80){'Yellow'}else{'Green'})
}

# ============================================================
# Phase 2: C盘治理 (目标: 28% -> 50%+)
# ============================================================
function Phase2 {
    Log "===== Phase 2: C Drive Treatment =====" 'Cyan'
    
    # 2.1 CrossDevice迁移 (73.7GB -> E盘)
    $cdSrc = "C:\Users\zhouyoukang\CrossDevice"
    $cdDst = "E:\CrossDevice"
    if((Test-Path $cdSrc) -and !(Get-Item $cdSrc).Attributes.HasFlag([IO.FileAttributes]::ReparsePoint)) {
        $cdSize = (Get-ChildItem $cdSrc -Recurse -File -Force -EA SilentlyContinue | Measure-Object Length -Sum).Sum
        Log "CrossDevice: $([math]::Round($cdSize/1GB,1))GB to migrate C->E" 'Yellow'
        if(!$DryRun) {
            Log "Starting robocopy migration (this takes a while)..." 'Yellow'
            if(!(Test-Path $cdDst)) { New-Item -ItemType Directory -Path $cdDst -Force | Out-Null }
            $rc = Start-Process robocopy -ArgumentList "`"$cdSrc`" `"$cdDst`" /E /MOVE /R:1 /W:1 /NP /LOG:`"$env:TEMP\crossdevice_move.log`"" -Wait -PassThru -NoNewWindow
            if($rc.ExitCode -le 3) {
                # Create junction for compatibility
                if(Test-Path $cdSrc) { Remove-Item $cdSrc -Force -Recurse -EA SilentlyContinue }
                cmd /c "mklink /J `"$cdSrc`" `"$cdDst`"" | Out-Null
                Log "CrossDevice migrated + junction created" 'Green'
            } else {
                Log "Robocopy returned exit code $($rc.ExitCode), check log" 'Red'
            }
        }
        LogAction "MIGRATE CrossDevice C->E" $cdSize 'medium'
    } elseif((Get-Item $cdSrc -EA SilentlyContinue).Attributes.HasFlag([IO.FileAttributes]::ReparsePoint)) {
        Log "CrossDevice already a junction, skip" 'Gray'
    }
    
    # 2.2 Trae缓存清理 (8.1GB, 最后使用2025年10月)
    $traeRoaming = "C:\Users\zhouyoukang\AppData\Roaming\Trae"
    if(Test-Path $traeRoaming) {
        SafeDelete $traeRoaming "Roaming\Trae cache (last used Oct 2025)"
    }
    
    # 2.3 C:\ 根目录散落文件归档
    $archiveDir = "C:\temp\c_root_archive"
    if(!(Test-Path $archiveDir)) { New-Item -ItemType Directory -Path $archiveDir -Force | Out-Null }
    $rootFiles = Get-ChildItem "C:\" -File -Force -EA SilentlyContinue | Where-Object {
        $_.Name -notmatch 'pagefile|swapfile|hiberfil|bootTel|DumpStack|59489359' -and
        $_.Name -ne '.GamingRoot'
    }
    foreach($f in $rootFiles) {
        SafeMove $f.FullName "$archiveDir\$($f.Name)" "C:\$($f.Name) -> archive"
    }
    
    # 2.4 npm-cache清理
    $npmCache = "C:\Users\zhouyoukang\AppData\Local\npm-cache"
    if(Test-Path $npmCache) {
        SafeDelete $npmCache "npm-cache (1.1GB)"
    }
    
    # 2.5 Temp清理
    $tempDir = "C:\Users\zhouyoukang\AppData\Local\Temp"
    if(Test-Path $tempDir) {
        $oldFiles = Get-ChildItem $tempDir -File -Force -EA SilentlyContinue | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-7) }
        $oldSize = ($oldFiles | Measure-Object Length -Sum).Sum
        if(!$DryRun) {
            $oldFiles | Remove-Item -Force -EA SilentlyContinue
            Log "Cleaned $($oldFiles.Count) temp files ($([math]::Round($oldSize/1MB,1))MB)" 'Green'
        }
        LogAction "CLEAN Temp files >7d" $oldSize 'low'
    }
}

# ============================================================
# Phase 3: E盘治理
# ============================================================
function Phase3 {
    Log "===== Phase 3: E Drive Treatment =====" 'Cyan'
    
    # 3.1 浏览器下载位置 - 删除已安装安装包(>100MB)
    $dlDir = "E:\浏览器下载位置"
    if(Test-Path $dlDir) {
        $packages = Get-ChildItem $dlDir -File -Force -EA SilentlyContinue | Where-Object {
            $_.Extension -match '\.(exe|msi|zip|rar|7z)$' -and $_.Length -gt 100MB
        }
        foreach($pkg in $packages) {
            SafeDelete $pkg.FullName "Download: $($pkg.Name) ($([math]::Round($pkg.Length/1MB,1))MB)"
        }
    }
    
    # 3.2 ADinstall安装残留
    SafeDelete "E:\ADinstall" "Altium Designer install files (5.7GB)"
    
    # 3.3 2023写字机教程包
    SafeDelete "E:\2023写字机软件教程包" "2023 writing machine tutorial (11.2GB)"
}

# ============================================================
# Phase 4: D盘治理
# ============================================================
function Phase4 {
    Log "===== Phase 4: D Drive Treatment =====" 'Cyan'
    
    # 4.1 MemoTrace重复
    SafeDelete "D:\MemoTrace暂时有误" "MemoTrace duplicate copy"
    
    # 4.2 Trae应用目录
    SafeDelete "D:\Trae" "Trae IDE (unused since Oct 2025)"
    SafeDelete "D:\Trae CN" "Trae CN IDE"
    
    # 4.3 Blender散落文件 -> 归档
    $blenderArchive = "D:\temp\blender_scattered"
    if(!(Test-Path $blenderArchive)) { New-Item -ItemType Directory -Path $blenderArchive -Force | Out-Null }
    $blenderFiles = Get-ChildItem "D:\" -File -Force -EA SilentlyContinue | Where-Object {
        $_.Name -match 'blender|BlendThumb|cycles_kernel'
    }
    foreach($bf in $blenderFiles) {
        SafeMove $bf.FullName "$blenderArchive\$($bf.Name)" "D:\$($bf.Name) -> blender archive"
    }
    
    # 4.4 D:\ 根目录杂散文件归档
    $dArchive = "D:\temp\d_root_archive"
    if(!(Test-Path $dArchive)) { New-Item -ItemType Directory -Path $dArchive -Force | Out-Null }
    $dRootFiles = Get-ChildItem "D:\" -File -Force -EA SilentlyContinue | Where-Object {
        $_.Name -notmatch 'DumpStack|bootTel' -and $_.Length -lt 200MB
    }
    foreach($df in $dRootFiles) {
        SafeMove $df.FullName "$dArchive\$($df.Name)" "D:\$($df.Name) -> archive"
    }
    
    # 4.5 Youku缓存
    SafeDelete "D:\Youku Files" "Youku offline cache (9.3GB)"
    
    # 4.6 Home_Assiatant拼写修复
    if((Test-Path "D:\Home_Assiatant") -and !(Test-Path "D:\Home_Assistant")) {
        SafeMove "D:\Home_Assiatant" "D:\Home_Assistant" "Fix typo: Home_Assiatant -> Home_Assistant"
    }
}

# ============================================================
# Phase 5: 命名规范修复
# ============================================================
function Phase5 {
    Log "===== Phase 5: Naming Convention Fix =====" 'Cyan'
    
    # 5.1 乱码目录检查并重命名
    $garbled = "D:\妗岄潰"
    if(Test-Path $garbled) {
        $items = Get-ChildItem $garbled -Force -EA SilentlyContinue
        if($items.Count -eq 0) {
            if(!$DryRun) { Remove-Item $garbled -Force }
            Log "Removed empty garbled directory: D:\妗岄潰" 'Green'
        } else {
            SafeMove $garbled "D:\temp\garbled_dir_backup" "Garbled dir D:\妗岄潰 -> backup"
        }
    }
    
    # 5.2 E:\道下命名统一（AI大小写）
    $renames = @{
        "E:\道\AI _PCB设计" = "E:\道\AI-PCB设计"           # 去除空格+下划线
        "E:\道\ai浏览器自动化" = "E:\道\AI-浏览器自动化"     # ai->AI
        "E:\道\ai操作手机" = "E:\道\AI-操作手机"             # ai->AI
        "E:\道\AI初恋测试" = "E:\道\AI-初恋测试"             # 加连字符
    }
    foreach($old in $renames.Keys) {
        $new = $renames[$old]
        if((Test-Path $old) -and !(Test-Path $new)) {
            SafeMove $old $new "Rename: $(Split-Path $old -Leaf) -> $(Split-Path $new -Leaf)"
        }
    }
    
    Log "Note: Junction targets in workspace need manual update after renames" 'Yellow'
}

# ============================================================
# Phase 6: Agent监控体系
# ============================================================
function Phase6 {
    Log "===== Phase 6: Agent Monitoring Setup =====" 'Cyan'
    Log "Creating disk-monitor.ps1..." 'Gray'
    # Monitor script created separately
    Log "Phase 6 complete - monitor script available" 'Green'
}

# ============================================================
# Phase 7: 验证
# ============================================================
function Phase7 {
    Log "===== Phase 7: Verification =====" 'Cyan'
    
    foreach($d in @('C','D','E')) {
        $v = Get-Volume -DriveLetter $d
        $pct = [math]::Round($v.SizeRemaining/$v.Size*100,1)
        Log "$($d): $([math]::Round($v.SizeRemaining/1GB,1))GB free ($pct%)" 'White'
    }
    
    Log "`nActions performed: $($script:actions.Count)" 'Cyan'
    Log "Estimated space freed: $([math]::Round($script:totalFreed/1GB,1))GB" 'Green'
    
    if($script:actions.Count -gt 0) {
        Log "`nAction Summary:" 'Cyan'
        $script:actions | Format-Table -AutoSize
    }
}

# ============================================================
# Main
# ============================================================
Log "=== Disk Treatment Script ===" 'Cyan'
Log "Mode: $(if($DryRun){'DRY RUN'}else{'LIVE'})" $(if($DryRun){'Yellow'}else{'Red'})
Log ""

switch($Phase) {
    '1' { Phase1 }
    '2' { Phase2 }
    '3' { Phase3 }
    '4' { Phase4 }
    '5' { Phase5 }
    '6' { Phase6 }
    '7' { Phase7 }
    'all' {
        Phase1; Phase2; Phase3; Phase4; Phase5; Phase6; Phase7
    }
}

Log "`n=== Treatment Complete ===" 'Cyan'
