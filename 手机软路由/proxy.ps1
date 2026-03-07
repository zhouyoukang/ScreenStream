# OPPO Reno4 SE Proxy Toggle Script
# Usage: .\proxy.ps1 [on|off|status|test]
# Modes: on=enable system proxy, off=disable, status=show current, test=connectivity check

param(
    [Parameter(Position=0)]
    [ValidateSet("on", "off", "status", "test")]
    [string]$Action = "status",

    [string]$ProxyIP = "192.168.31.95",
    [int]$SocksPort = 10808,
    [int]$HttpPort = 10809,
    [ValidateSet("socks", "http")]
    [string]$Type = "socks"
)

$RegPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings"

function Get-ProxyStatus {
    $enabled = (Get-ItemProperty -Path $RegPath).ProxyEnable
    $server = (Get-ItemProperty -Path $RegPath).ProxyServer
    if ($enabled -eq 1) {
        Write-Host "[ON] System proxy: $server" -ForegroundColor Green
    } else {
        Write-Host "[OFF] System proxy disabled" -ForegroundColor Yellow
        if ($server) { Write-Host "  (Last used: $server)" -ForegroundColor DarkGray }
    }
}

function Set-ProxyOn {
    $port = if ($Type -eq "http") { $HttpPort } else { $SocksPort }
    $proxyStr = "socks=${ProxyIP}:${port}"
    if ($Type -eq "http") { $proxyStr = "${ProxyIP}:${port}" }

    Set-ItemProperty -Path $RegPath -Name ProxyEnable -Value 1
    Set-ItemProperty -Path $RegPath -Name ProxyServer -Value $proxyStr
    Set-ItemProperty -Path $RegPath -Name ProxyOverride -Value "localhost;127.*;192.168.*;<local>"
    Write-Host "[ON] Proxy enabled: $proxyStr" -ForegroundColor Green
    Write-Host "  Bypass: localhost, 127.*, 192.168.*, <local>" -ForegroundColor DarkGray
}

function Set-ProxyOff {
    Set-ItemProperty -Path $RegPath -Name ProxyEnable -Value 0
    Write-Host "[OFF] Proxy disabled" -ForegroundColor Yellow
}

function Test-Proxy {
    Write-Host "Testing SOCKS5 proxy ${ProxyIP}:${SocksPort}..." -ForegroundColor Cyan

    # Test 1: Google
    $code = & curl.exe -s -o NUL -w "%{http_code}" -x "socks5://${ProxyIP}:${SocksPort}" "https://www.google.com" -m 10 2>&1
    if ($code -eq "200") {
        Write-Host "  Google: OK (HTTP $code)" -ForegroundColor Green
    } else {
        Write-Host "  Google: FAIL ($code)" -ForegroundColor Red
    }

    # Test 2: GitHub
    $code2 = & curl.exe -s -o NUL -w "%{http_code}" -x "socks5://${ProxyIP}:${SocksPort}" "https://github.com" -m 10 2>&1
    if ($code2 -eq "200" -or $code2 -eq "301") {
        Write-Host "  GitHub: OK (HTTP $code2)" -ForegroundColor Green
    } else {
        Write-Host "  GitHub: FAIL ($code2)" -ForegroundColor Red
    }

    # Test 3: Exit IP
    $ip = & curl.exe -s -x "socks5://${ProxyIP}:${SocksPort}" "https://api.ipify.org" -m 10 2>&1
    if ($ip -match '^\d+\.\d+\.\d+\.\d+$') {
        Write-Host "  Exit IP: $ip" -ForegroundColor Green
    } else {
        Write-Host "  Exit IP: unknown" -ForegroundColor Yellow
    }
}

# Main
switch ($Action) {
    "on"     { Set-ProxyOn }
    "off"    { Set-ProxyOff }
    "status" { Get-ProxyStatus }
    "test"   { Test-Proxy }
}
