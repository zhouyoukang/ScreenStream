# ═══════════════════════════════════════════════════════════
# 台式机141 · 一键启动所有Hub服务
# 道生一(注册表) → 一生二(Hub) → 二生三(Dashboard) → 三生万物
#
# 用法: .\start_all_hubs.ps1 [-All] [-Category <name>] [-List] [-Stop]
# ═══════════════════════════════════════════════════════════

param(
    [switch]$All,
    [switch]$List,
    [switch]$Stop,
    [string]$Category = ""
)

$ROOT = "D:\道\道生一\一生二"

# ── Hub 注册表 ──
$HUBS = @(
    # 核心中枢
    @{Name="资源注册表";     Port=9000;  Cmd="python resource_registry.py";                Dir="三电脑服务器";              Cat="核心"}
    @{Name="AGI仪表盘";      Port=9090;  Cmd="python dashboard-server.py";                 Dir="AGI";                       Cat="核心"}

    # 凭据与数据
    @{Name="密码中枢";        Port=9877;  Cmd="python password_hub.py";                     Dir="密码管理";                  Cat="凭据"}
    @{Name="手机数据中枢";    Port=9878;  Cmd="python phone_hub.py";                        Dir="密码管理";                  Cat="凭据"}

    # 设备Hub
    @{Name="拓竹3D打印";      Port=8870;  Cmd="python bambu_hub.py";                        Dir="拓竹AI 3D打印机";           Cat="设备"}
    @{Name="EcoFlow电源";     Port=8871;  Cmd="python ecoflow_hub.py";                      Dir="正浩德2户外电源";           Cat="设备"}
    @{Name="Insta360相机";    Port=8860;  Cmd="python insta360_hub.py";                     Dir="影石360 x3";                Cat="设备"}
    @{Name="ORS6设备";        Port=41927; Cmd="python ors6_hub.py --no-browser";            Dir="ORS6-VAM饮料摇匀器";        Cat="设备"}
    @{Name="Go1机器狗";       Port=8087;  Cmd="python go1_hub.py --port 8087";              Dir="机器狗开发";                Cat="设备"}

    # 智能家居
    @{Name="米家中枢";        Port=8873;  Cmd="python mijia_hub.py";                        Dir="米家系统全整合";            Cat="智能家居"}
    @{Name="米家摄像头";      Port=8874;  Cmd="python camera_hub.py";                       Dir="米家系统全整合";            Cat="智能家居"}

    # 投屏/远程
    @{Name="电脑投屏";        Port=9802;  Cmd="python desktop.py";                          Dir="电脑公网投屏手机";          Cat="投屏"}
    @{Name="远程Agent";       Port=9903;  Cmd="python remote_agent.py";                     Dir="远程桌面";                  Cat="远程"}

    # 万物
    @{Name="万物中枢";        Port=8808;  Cmd="python wan_wu_server.py";                    Dir="雷鸟v3开发";                Cat="中枢"}
    @{Name="RayNeo管理";      Port=8800;  Cmd="python rayneo_dashboard.py";                 Dir="雷鸟v3开发";                Cat="AR"}
)

function Show-List {
    Write-Host "`n三电脑服务器 · Hub服务清单" -ForegroundColor Cyan
    Write-Host ("=" * 60)
    $cats = $HUBS | Group-Object Cat
    foreach ($g in $cats) {
        Write-Host "`n[$($g.Name)]" -ForegroundColor Yellow
        foreach ($h in $g.Group) {
            $listening = (Get-NetTCPConnection -LocalPort $h.Port -ErrorAction SilentlyContinue | Where-Object State -eq "Listen")
            $status = if ($listening) { "[ON]" } else { "[OFF]" }
            $color = if ($listening) { "Green" } else { "DarkGray" }
            Write-Host ("  {0,-5} {1,-20} :{2,-6} {3}" -f $status, $h.Name, $h.Port, $h.Dir) -ForegroundColor $color
        }
    }
    Write-Host ""
}

function Start-Hub($hub) {
    $dir = Join-Path $ROOT $hub.Dir
    if (-not (Test-Path $dir)) {
        Write-Host "  [SKIP] $($hub.Name) - 目录不存在: $($hub.Dir)" -ForegroundColor DarkGray
        return
    }
    $listening = (Get-NetTCPConnection -LocalPort $hub.Port -ErrorAction SilentlyContinue | Where-Object State -eq "Listen")
    if ($listening) {
        Write-Host "  [SKIP] $($hub.Name) :$($hub.Port) 已在运行" -ForegroundColor DarkGray
        return
    }
    Write-Host "  [START] $($hub.Name) :$($hub.Port) ..." -ForegroundColor Green -NoNewline
    Start-Process -FilePath "python" -ArgumentList ($hub.Cmd -replace "python ", "") -WorkingDirectory $dir -WindowStyle Minimized
    Start-Sleep -Milliseconds 500
    Write-Host " OK" -ForegroundColor Green
}

function Stop-AllHubs {
    Write-Host "`n停止所有Hub服务..." -ForegroundColor Yellow
    foreach ($h in $HUBS) {
        $conns = Get-NetTCPConnection -LocalPort $h.Port -ErrorAction SilentlyContinue | Where-Object State -eq "Listen"
        foreach ($c in $conns) {
            $proc = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue
            if ($proc -and $proc.ProcessName -eq "python") {
                Stop-Process -Id $proc.Id -Force
                Write-Host "  [STOP] $($h.Name) :$($h.Port) PID=$($proc.Id)" -ForegroundColor Red
            }
        }
    }
}

# ── Main ──
if ($List) { Show-List; return }
if ($Stop) { Stop-AllHubs; return }

Write-Host "`n三电脑服务器 · 启动Hub服务" -ForegroundColor Cyan
Write-Host ("=" * 60)

$targets = $HUBS
if ($Category) {
    $targets = $HUBS | Where-Object { $_.Cat -eq $Category }
    Write-Host "分类: $Category ($($targets.Count)个)" -ForegroundColor Yellow
} elseif (-not $All) {
    # Default: start core + credentials only
    $targets = $HUBS | Where-Object { $_.Cat -in @("核心", "凭据") }
    Write-Host "默认模式: 仅启动核心+凭据 ($($targets.Count)个)" -ForegroundColor Yellow
    Write-Host "使用 -All 启动全部, -Category <name> 按分类启动" -ForegroundColor DarkGray
}

foreach ($h in $targets) { Start-Hub $h }

Write-Host "`n启动完成。" -ForegroundColor Cyan
Show-List
