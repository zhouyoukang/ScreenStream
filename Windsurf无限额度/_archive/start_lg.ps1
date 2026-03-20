# start_lg.ps1 — 启动 windsurf-LG 的完整脚本（以管理员运行）
# 1. 预写 hosts 条目（绕过 DNS Client 文件锁）
# 2. 启动 windsurf-LG

$ErrorActionPreference = 'SilentlyContinue'
$hostsPath = 'C:\WINDOWS\System32\drivers\etc\hosts'
$lgExe = 'D:\浏览器下载\windsurf-LG_1.0.0.11.p.exe'

# === Step 1: 确保 hosts 含 windsurf/codeium 条目 ===
$requiredEntries = @(
    '127.0.0.1 server.self-serve.windsurf.com',
    '127.0.0.1 server.codeium.com'
)

try {
    # 用 FileShare.Read,Write,Delete 绕过 DNS Client 的文件锁
    $fs = [IO.FileStream]::new($hostsPath, 'Open', 'Read', 'Read,Write,Delete')
    $sr = [IO.StreamReader]::new($fs)
    $currentContent = $sr.ReadToEnd()
    $sr.Close()
    $fs.Close()
} catch {
    $currentContent = ''
}

$needsWrite = $false
foreach ($entry in $requiredEntries) {
    $domain = ($entry -split '\s+')[1]
    if ($currentContent -notmatch [regex]::Escape($domain)) {
        $needsWrite = $true
        break
    }
}

if ($needsWrite) {
    try {
        $newContent = "# hosts - managed by windsurf-LG startup script`r`n"
        $newContent += "127.0.0.1 localhost`r`n"
        foreach ($entry in $requiredEntries) {
            $newContent += "$entry`r`n"
        }
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($newContent)
        $fs = [IO.FileStream]::new($hostsPath, 'Open', 'Write', 'Read,Write,Delete')
        $fs.SetLength(0)
        $fs.Write($bytes, 0, $bytes.Length)
        $fs.Flush()
        $fs.Close()
        Write-Host "[OK] hosts entries written ($($bytes.Length) bytes)"
    } catch {
        Write-Host "[WARN] hosts write failed: $_"
    }
} else {
    Write-Host "[OK] hosts entries already present"
}

# === Step 2: 启动 windsurf-LG ===
$existing = Get-Process -Name 'windsurf-LG*' -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "[OK] windsurf-LG already running (PID $($existing.Id))"
} else {
    if (Test-Path $lgExe) {
        Start-Process $lgExe
        Write-Host "[OK] windsurf-LG started"
    } else {
        Write-Host "[ERROR] windsurf-LG not found at: $lgExe"
    }
}

# === Step 3: 等待 443 端口 ===
$waited = 0
while ($waited -lt 15) {
    $listener = netstat -ano 2>$null | Select-String '127.0.0.1:443.*LISTENING'
    if ($listener) {
        Write-Host "[OK] 443 port listening"
        break
    }
    Start-Sleep -Seconds 1
    $waited++
}
if ($waited -ge 15) {
    Write-Host "[WARN] 443 not listening after 15s - check Wind client GUI"
}
