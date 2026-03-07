<#
.SYNOPSIS
    ScreenStream 公网远控隧道部署脚本
.DESCRIPTION
    一键配置 Cloudflare Tunnel 或 FRP，将手机 ScreenStream 服务暴露到公网。
    支持三种模式：Cloudflare Quick Tunnel（免注册）、Cloudflare Named Tunnel、FRP。
.EXAMPLE
    .\remote-tunnel-setup.ps1 -Mode quick -LocalPort 8081
    .\remote-tunnel-setup.ps1 -Mode cloudflare -Domain myphone.example.com -LocalPort 8081
    .\remote-tunnel-setup.ps1 -Mode frp -FrpServer frp.example.com -RemotePort 7000 -LocalPort 8081
#>

param(
    [ValidateSet('quick', 'cloudflare', 'frp')]
    [string]$Mode = 'quick',
    [int]$LocalPort = 8080,
    [string]$Domain = '',
    [string]$FrpServer = '',
    [int]$RemotePort = 7000,
    [switch]$GenerateToken
)

$ErrorActionPreference = 'Stop'

function Write-Step($msg) { Write-Host "`n[*] $msg" -ForegroundColor Cyan }
function Write-Ok($msg) { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "  [!] $msg" -ForegroundColor Yellow }

# Step 0: Generate auth token if requested
if ($GenerateToken) {
    Write-Step "Generating auth token via API..."
    try {
        $resp = Invoke-RestMethod -Uri "http://localhost:$LocalPort/auth/generate" -Method POST -ContentType 'application/json' -Body '{}'
        if ($resp.ok) {
            Write-Ok "Auth token generated: $($resp.token)"
            Write-Host "`n  Share this URL with remote users:" -ForegroundColor White
            Write-Host "  https://<your-tunnel-domain>/?auth=$($resp.token)" -ForegroundColor Yellow
        }
    }
    catch {
        Write-Warn "Could not generate token. Is ScreenStream running on port $LocalPort?"
    }
}

switch ($Mode) {
    'quick' {
        Write-Step "Mode: Cloudflare Quick Tunnel (free, no account needed)"
        Write-Step "Checking cloudflared..."

        $cf = Get-Command cloudflared -ErrorAction SilentlyContinue
        if (-not $cf) {
            Write-Warn "cloudflared not found. Installing via winget..."
            winget install Cloudflare.cloudflared --accept-package-agreements --accept-source-agreements
            $cf = Get-Command cloudflared -ErrorAction SilentlyContinue
            if (-not $cf) {
                Write-Host "  Please install cloudflared manually: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/" -ForegroundColor Red
                exit 1
            }
        }
        Write-Ok "cloudflared found: $($cf.Source)"

        Write-Step "Starting Quick Tunnel -> localhost:$LocalPort"
        Write-Host "  The tunnel URL will appear below. Share it with remote users." -ForegroundColor White
        Write-Host "  Press Ctrl+C to stop the tunnel.`n" -ForegroundColor Gray

        & cloudflared tunnel --url "http://localhost:$LocalPort"
    }

    'cloudflare' {
        if (-not $Domain) {
            Write-Host "Error: -Domain is required for named tunnel mode" -ForegroundColor Red
            Write-Host "Example: .\remote-tunnel-setup.ps1 -Mode cloudflare -Domain myphone.example.com" -ForegroundColor Gray
            exit 1
        }

        Write-Step "Mode: Cloudflare Named Tunnel -> $Domain"
        Write-Step "Checking cloudflared..."

        $cf = Get-Command cloudflared -ErrorAction SilentlyContinue
        if (-not $cf) {
            Write-Warn "cloudflared not found. Please install: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/"
            exit 1
        }

        Write-Step "Login to Cloudflare (browser will open)..."
        & cloudflared tunnel login

        $tunnelName = "screenstream-remote"
        Write-Step "Creating tunnel: $tunnelName"
        & cloudflared tunnel create $tunnelName

        Write-Step "Routing DNS: $Domain -> $tunnelName"
        & cloudflared tunnel route dns $tunnelName $Domain

        Write-Step "Starting tunnel..."
        & cloudflared tunnel run --url "http://localhost:$LocalPort" $tunnelName
    }

    'frp' {
        if (-not $FrpServer) {
            Write-Host "Error: -FrpServer is required for FRP mode" -ForegroundColor Red
            exit 1
        }

        Write-Step "Mode: FRP Client -> $FrpServer"

        # FRP v0.52+ 仅支持 TOML 格式，INI 已废弃
        $frpConfig = @"
serverAddr = "$FrpServer"
serverPort = $RemotePort
loginFailExit = false

[[proxies]]
name = "screenstream"
type = "tcp"
localIP = "127.0.0.1"
localPort = $LocalPort
remotePort = $($LocalPort + 10000)
"@

        # 如果有域名，添加 HTTPS 代理
        if ($Domain) {
            $frpConfig += @"

[[proxies]]
name = "screenstream-https"
type = "https"
localIP = "127.0.0.1"
localPort = $LocalPort
customDomains = ["$Domain"]
"@
        }

        $configPath = Join-Path $PSScriptRoot "frpc-screenstream.toml"
        $frpConfig | Set-Content $configPath -Encoding UTF8
        Write-Ok "FRP config written to: $configPath"

        $frpc = Get-Command frpc -ErrorAction SilentlyContinue
        if ($frpc) {
            Write-Step "Starting FRP client..."
            & frpc -c $configPath
        }
        else {
            Write-Warn "frpc not found. Please download from https://github.com/fatedier/frp/releases"
            Write-Host "  Then run: frpc -c `"$configPath`"" -ForegroundColor Gray
        }
    }
}
