# Home Assistant重启与MiGPT修复脚本
Write-Host "Home Assistant重启与MiGPT修复工具" -ForegroundColor Cyan
Write-Host "=============================" -ForegroundColor Cyan
Write-Host ""

# 获取认证令牌
$token = $null

if (Test-Path "ha_token.txt") {
    $token = Get-Content "ha_token.txt" -Raw
    $token = $token.Trim()  # 移除多余的空白字符
    Write-Host "从ha_token.txt读取到了访问令牌" -ForegroundColor Green
} else {
    $token = Read-Host "请输入Home Assistant长期访问令牌"
    # 保存token到文件
    $token | Out-File "ha_token.txt" -Encoding utf8
    Write-Host "已保存访问令牌到ha_token.txt" -ForegroundColor Green
}

# 检查Home Assistant连接
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8123/api/config" -Headers @{Authorization=("Bearer " + $token)} -UseBasicParsing
    Write-Host "成功连接到Home Assistant" -ForegroundColor Green
} catch {
    Write-Host "无法连接到Home Assistant，请检查令牌是否有效。" -ForegroundColor Red
    Write-Host "错误信息: $_"
    
    $newToken = Read-Host "请输入有效的Home Assistant长期访问令牌"
    $newToken | Out-File "ha_token.txt" -Encoding utf8
    $token = $newToken
    
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8123/api/config" -Headers @{Authorization=("Bearer " + $token)} -UseBasicParsing
        Write-Host "成功连接到Home Assistant" -ForegroundColor Green
    } catch {
        Write-Host "仍然无法连接，请手动检查令牌和Home Assistant是否正常运行。" -ForegroundColor Red
        exit 1
    }
}

# 1. 重启Home Assistant
Write-Host "`n正在重启Home Assistant..." -ForegroundColor Yellow
try {
    Invoke-WebRequest -Method POST -Uri "http://localhost:8123/api/services/homeassistant/restart" `
                     -Headers @{Authorization=("Bearer " + $token); "Content-Type"="application/json"} `
                     -Body "{}" -UseBasicParsing | Out-Null
    
    Write-Host "已发送重启命令，等待Home Assistant重启..." -ForegroundColor Yellow
    
    # 等待Home Assistant重启
    $retryCount = 0
    $maxRetry = 30
    $success = $false
    
    while ($retryCount -lt $maxRetry) {
        Start-Sleep -Seconds 5
        try {
            $statusResponse = Invoke-WebRequest -Uri "http://localhost:8123/api/config" `
                                               -Headers @{Authorization=("Bearer " + $token)} `
                                               -UseBasicParsing -ErrorAction SilentlyContinue
            if ($statusResponse.StatusCode -eq 200) {
                Write-Host "Home Assistant已成功重启！" -ForegroundColor Green
                $success = $true
                break
            }
        } catch {
            Write-Host "等待Home Assistant重启中... ($($retryCount+1)/$maxRetry)" -ForegroundColor Yellow
        }
        $retryCount++
    }
    
    if (-not $success) {
        Write-Host "等待Home Assistant重启超时，继续尝试修复..." -ForegroundColor Red
    }
} catch {
    Write-Host "发送重启命令时出错: $_" -ForegroundColor Red
}

# 2. 确保python_scripts目录存在
$pythonScriptsDir = "config/python_scripts"
if (!(Test-Path $pythonScriptsDir)) {
    Write-Host "创建python_scripts目录..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $pythonScriptsDir -Force | Out-Null
    Write-Host "已创建目录: $pythonScriptsDir" -ForegroundColor Green
}

# 3. 复制修复脚本
$fixScriptSource = "工具库/修复脚本/migpt_enhanced_fix.py"
$fixScriptDest = "config/python_scripts/migpt_enhanced_fix.py"

if (Test-Path $fixScriptSource) {
    Copy-Item -Path $fixScriptSource -Destination $fixScriptDest -Force
    Write-Host "已复制修复脚本: $fixScriptSource -> $fixScriptDest" -ForegroundColor Green
} else {
    Write-Host "修复脚本不存在: $fixScriptSource" -ForegroundColor Red
    
    # 如果目标文件已存在，就使用它
    if (Test-Path $fixScriptDest) {
        Write-Host "但目标文件已存在，将继续使用。" -ForegroundColor Yellow
    } else {
        Write-Host "目标文件也不存在，无法继续。" -ForegroundColor Red
        exit 1
    }
}

# 4. 等待10秒确保Home Assistant完全加载
Write-Host "`n等待Home Assistant完全加载..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# 5. 运行修复脚本
Write-Host "`n正在运行MiGPT修复脚本..." -ForegroundColor Yellow
try {
    # 调用python_script.turn_on服务来运行脚本
    $fix_response = Invoke-WebRequest -Method POST `
                                    -Uri "http://localhost:8123/api/services/python_script/turn_on" `
                                    -Headers @{Authorization=("Bearer " + $token); "Content-Type"="application/json"} `
                                    -Body "{`"entity_id`":`"python_script.migpt_enhanced_fix`"}" `
                                    -UseBasicParsing
    
    if ($fix_response.StatusCode -eq 200) {
        Write-Host "修复脚本已成功运行！" -ForegroundColor Green
        
        # 给修复一些时间生效
        Start-Sleep -Seconds 5
        
        # 检查MiGPT实体
        $entityResponse = Invoke-WebRequest -Uri "http://localhost:8123/api/states" `
                                          -Headers @{Authorization=("Bearer " + $token); "Content-Type"="application/json"} `
                                          -UseBasicParsing
        
        $entities = $entityResponse.Content | ConvertFrom-Json
        $migptEntities = $entities | Where-Object { $_.entity_id -like "media_player.migpt*" -or $_.entity_id -like "sensor.migpt*" }
        
        if ($migptEntities.Count -gt 0) {
            Write-Host "`n发现 $($migptEntities.Count) 个MiGPT相关实体:" -ForegroundColor Green
            $migptEntities | ForEach-Object {
                Write-Host " - $($_.entity_id): $($_.state)" -ForegroundColor Cyan
            }
            Write-Host "`n修复成功！请刷新Home Assistant界面查看新添加的实体。" -ForegroundColor Green
        } else {
            Write-Host "`n未发现任何MiGPT实体，修复可能未成功。请检查Home Assistant日志获取详细信息。" -ForegroundColor Red
        }
    } else {
        Write-Host "运行修复脚本返回了非200状态码: $($fix_response.StatusCode)" -ForegroundColor Red
    }
} catch {
    Write-Host "运行修复脚本时出错: $_" -ForegroundColor Red
    Write-Host "请检查Home Assistant日志获取详细信息。" -ForegroundColor Yellow
}

# 6. 额外尝试重新加载MiGPT集成
Write-Host "`n尝试重新加载MiGPT集成..." -ForegroundColor Yellow
try {
    # 获取MiGPT集成的entry_id
    $entries_response = Invoke-WebRequest -Uri "http://localhost:8123/api/config/config_entries/entry" `
                                         -Headers @{Authorization=("Bearer " + $token); "Content-Type"="application/json"} `
                                         -UseBasicParsing
    
    $entries = $entries_response.Content | ConvertFrom-Json
    $migpt_entry = $entries | Where-Object { $_.domain -eq "migpt" } | Select-Object -First 1
    
    if ($migpt_entry) {
        $entry_id = $migpt_entry.entry_id
        Write-Host "找到MiGPT集成ID: $entry_id" -ForegroundColor Green
        
        # 重新加载集成
        $reload_response = Invoke-WebRequest -Method POST `
                                           -Uri "http://localhost:8123/api/config/config_entries/entry/$entry_id/reload" `
                                           -Headers @{Authorization=("Bearer " + $token); "Content-Type"="application/json"} `
                                           -Body "{}" `
                                           -UseBasicParsing
        
        if ($reload_response.StatusCode -eq 200) {
            Write-Host "MiGPT集成已成功重新加载!" -ForegroundColor Green
        } else {
            Write-Host "重新加载MiGPT集成返回非200状态码: $($reload_response.StatusCode)" -ForegroundColor Red
        }
    } else {
        Write-Host "未找到MiGPT集成配置项" -ForegroundColor Red
    }
} catch {
    Write-Host "获取或重新加载集成时出错: $_" -ForegroundColor Red
}

Write-Host "`n修复过程已完成。" -ForegroundColor Green
Write-Host "如果问题仍然存在，您可以尝试以下步骤:" -ForegroundColor Yellow
Write-Host "1. 在Home Assistant集成页面删除并重新添加MiGPT集成" -ForegroundColor Yellow
Write-Host "2. 检查Home Assistant日志获取更详细的错误信息" -ForegroundColor Yellow
Write-Host "3. 尝试运行其他修复脚本: 工具库/修复脚本/fix_migpt_complete.ps1" -ForegroundColor Yellow

Write-Host "`n按任意键退出..." -ForegroundColor Cyan
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown") 