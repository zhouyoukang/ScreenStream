<#
  SSH Agent 一键修复脚本
  解决问题：SSH passphrase 交互式prompt 阻塞 AI Agent 终端
  根因：id_ed25519 有密码保护，每次 git push/ssh 都弹 passphrase 输入
  方案：启动 Windows OpenSSH Agent 服务 + 缓存密钥（只需输入一次密码）
#>

Write-Host "=== SSH Agent 修复 ===" -ForegroundColor Cyan

# Step 1: 检查 ssh-agent 服务状态
$svc = Get-Service ssh-agent -ErrorAction SilentlyContinue
if (-not $svc) {
    Write-Host "[!] ssh-agent 服务不存在，尝试安装 OpenSSH..." -ForegroundColor Yellow
    Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0
    $svc = Get-Service ssh-agent -ErrorAction SilentlyContinue
}

if ($svc) {
    # Step 2: 设置自动启动 + 启动服务
    if ($svc.StartType -ne 'Automatic') {
        Write-Host "[*] 设置 ssh-agent 为自动启动..." -ForegroundColor Yellow
        Set-Service ssh-agent -StartupType Automatic
    }
    if ($svc.Status -ne 'Running') {
        Write-Host "[*] 启动 ssh-agent..." -ForegroundColor Yellow
        Start-Service ssh-agent
    }
    Write-Host "[OK] ssh-agent 已运行" -ForegroundColor Green

    # Step 3: 添加密钥到 agent（这一步需要输入一次密码）
    $keyPath = "$env:USERPROFILE\.ssh\id_ed25519"
    if (Test-Path $keyPath) {
        Write-Host ""
        Write-Host ">>> 即将添加密钥，请输入一次密码（之后永不再问）<<<" -ForegroundColor Yellow
        Write-Host ""
        ssh-add $keyPath

        # Step 4: 验证
        Write-Host ""
        $keys = ssh-add -l 2>&1
        if ($keys -match "ed25519") {
            Write-Host "[OK] 密钥已缓存，后续 git push/ssh 不再需要密码" -ForegroundColor Green
        }
        else {
            Write-Host "[!] 密钥添加可能失败，请手动运行: ssh-add $keyPath" -ForegroundColor Red
        }
    }
    else {
        Write-Host "[!] 未找到密钥: $keyPath" -ForegroundColor Red
    }
}
else {
    Write-Host "[!] 无法获取 ssh-agent 服务" -ForegroundColor Red
}

# Step 5: 验证 GitHub 连接
Write-Host ""
Write-Host "=== 验证 GitHub 连接 ===" -ForegroundColor Cyan
$result = ssh -T git@github.com 2>&1
Write-Host $result
if ($result -match "successfully authenticated") {
    Write-Host "[OK] GitHub SSH 连接正常" -ForegroundColor Green
}
else {
    Write-Host "[!] 连接可能有问题，但如果看到 'Hi xxx' 就是正常的" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== 可选：彻底消灭 C1 根因 ===" -ForegroundColor Magenta
Write-Host "如果你想永久去除密钥密码保护（推荐个人开发机）："
Write-Host "  ssh-keygen -p -f $env:USERPROFILE\.ssh\id_ed25519" -ForegroundColor Yellow
Write-Host "  → 输入旧密码 → 新密码留空按回车 → 确认留空按回车"
Write-Host "  → 之后SSH永远不需要密码，即使ssh-agent未运行"
Write-Host ""
Write-Host "=== 完成 ===" -ForegroundColor Green
Write-Host "现在可以正常 git push 了（不会再弹密码输入）"
