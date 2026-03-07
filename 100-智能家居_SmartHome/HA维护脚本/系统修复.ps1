# Home Assistant 系统修复
# 此脚本用于修复Home Assistant系统中的常见问题

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logFile = "repair_log_${timestamp}.log"

function Log-Message {
    param(
        [string]$message,
        [string]$color = "White"
    )
    
    Write-Host $message -ForegroundColor $color
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - $message" | Out-File $logFile -Append
}

function Create-Backup {
    param(
        [string]$component
    )
    
    $backupDir = "修复备份_${timestamp}"
    if (-not (Test-Path $backupDir)) {
        New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
    }
    
    $backupFile = "${component}_backup_${timestamp}.zip"
    $backupPath = Join-Path $backupDir $backupFile
    
    Log-Message "创建 $component 备份: $backupPath" "Cyan"
    
    return $backupPath
}

# 初始化日志文件
"Home Assistant 系统修复日志 - $(Get-Date)" | Out-File $logFile
"===========================================" | Out-File $logFile -Append
"" | Out-File $logFile -Append

Log-Message "开始Home Assistant系统修复..." "Magenta"
Log-Message "修复时间: $(Get-Date)" "Magenta"

# 获取token
$hasToken = $false
if (Test-Path "ha_token.txt") {
    try {
        $token = Get-Content "ha_token.txt" -Raw
        $token = $token.Trim()
        $hasToken = $true
        Log-Message "成功读取访问令牌" "Green"
    } catch {
        Log-Message "警告: 无法读取访问令牌: $_" "Yellow"
        Log-Message "部分修复功能将不可用" "Yellow"
    }
} else {
    Log-Message "警告: 找不到ha_token.txt文件" "Yellow"
    Log-Message "部分修复功能将不可用" "Yellow"
}

# 显示修复选项菜单
function Show-Menu {
    Log-Message "`n===========================================" "Cyan"
    Log-Message "      Home Assistant 系统修复工具      " "Cyan"
    Log-Message "===========================================" "Cyan"
    Log-Message "1. 修复配置文件问题" "White"
    Log-Message "2. 修复前端资源问题" "White"
    Log-Message "3. 修复HACS组件问题" "White"
    Log-Message "4. 修复数据库问题" "White"
    Log-Message "5. 修复Card-mod前端问题" "White"
    Log-Message "6. 修复实体引用问题" "White"
    Log-Message "7. 修复权限问题" "White"
    Log-Message "8. 清理缓存" "White"
    Log-Message "9. 执行全部修复" "Green"
    Log-Message "0. 退出" "Red"
    Log-Message "===========================================" "Cyan"
    Log-Message "请选择要执行的修复操作 (0-9): " "Yellow" -NoNewline
    
    $choice = Read-Host
    return $choice
}

# 修复配置文件问题
function Fix-ConfigurationFiles {
    Log-Message "`n开始修复配置文件问题..." "Cyan"
    
    # 检查configuration.yaml是否存在
    if (-not (Test-Path "configuration.yaml")) {
        Log-Message "错误: 找不到configuration.yaml文件" "Red"
        return
    }
    
    # 创建备份
    $backupPath = Create-Backup "config"
    Compress-Archive -Path "configuration.yaml" -DestinationPath $backupPath -Force
    
    Log-Message "检查配置文件格式..." "White"
    
    # 读取并检查文件内容
    $content = Get-Content "configuration.yaml" -Raw
    
    # 检查并修复常见格式问题
    $needsSave = $false
    
    # 检查缩进问题
    $lines = $content -split "`r?`n"
    $fixedLines = @()
    $hasIndentIssue = $false
    
    foreach ($line in $lines) {
        # 修复使用Tab的行
        if ($line -match "`t") {
            $hasIndentIssue = $true
            $fixedLine = $line -replace "`t", "  "
            $fixedLines += $fixedLine
        } else {
            $fixedLines += $line
        }
    }
    
    if ($hasIndentIssue) {
        Log-Message "  修复了配置文件中的Tab缩进问题" "Yellow"
        $content = $fixedLines -join "`n"
        $needsSave = $true
    }
    
    # 检查冒号后面的空格
    if ($content -match ':\S') {
        Log-Message "  修复了冒号后缺少空格的问题" "Yellow"
        $content = $content -replace '(:)([^\s\n])', '$1 $2'
        $needsSave = $true
    }
    
    # 保存修复后的文件
    if ($needsSave) {
        $content | Out-File "configuration.yaml" -Encoding utf8
        Log-Message "配置文件格式问题已修复" "Green"
    } else {
        Log-Message "配置文件格式正常" "Green"
    }
    
    # 如果有token，验证配置文件语法
    if ($hasToken) {
        Log-Message "验证配置文件语法..." "White"
        
        $headers = @{
            "Authorization" = "Bearer $token"
            "Content-Type" = "application/json"
        }
        
        try {
            Invoke-RestMethod -Uri "http://localhost:8123/api/services/homeassistant/check_config" -Method Post -Headers $headers -Body "{}" | Out-Null
            Start-Sleep -Seconds 2
            $checkResult = Invoke-RestMethod -Uri "http://localhost:8123/api/config/core/check_config" -Method Get -Headers $headers
            
            if ($checkResult.result -eq "valid") {
                Log-Message "  配置文件语法验证通过" "Green"
            } else {
                Log-Message "  配置文件语法验证失败" "Red"
                
                if ($checkResult.errors) {
                    foreach ($error in $checkResult.errors) {
                        Log-Message "    - $error" "Red"
                    }
                }
            }
        } catch {
            Log-Message "  无法验证配置文件语法: $_" "Yellow"
        }
    }
    
    Log-Message "配置文件修复完成" "Green"
}

# 修复前端资源问题
function Fix-FrontendResources {
    Log-Message "`n开始修复前端资源问题..." "Cyan"
    
    # 检查resources目录
    $resourcesDir = "config\www"
    if (-not (Test-Path $resourcesDir)) {
        Log-Message "创建资源目录: $resourcesDir" "Yellow"
        New-Item -ItemType Directory -Path $resourcesDir -Force | Out-Null
    }
    
    # 创建备份
    $backupPath = Create-Backup "frontend"
    if (Test-Path $resourcesDir) {
        Compress-Archive -Path $resourcesDir -DestinationPath $backupPath -Force
    }
    
    # 检查重复资源
    Log-Message "检查重复资源..." "White"
    
    $communityDir = "config\www\community"
    $hacsfilesDir = "config\www\hacsfiles"
    $customUiDir = "config\www\custom_ui"
    
    $duplicates = @()
    
    if ((Test-Path $communityDir) -and (Test-Path $hacsfilesDir)) {
        Log-Message "  发现可能的重复目录: community 和 hacsfiles" "Yellow"
        
        $communityItems = Get-ChildItem $communityDir -Directory | Select-Object -ExpandProperty Name
        $hacsfilesItems = Get-ChildItem $hacsfilesDir -Directory | Select-Object -ExpandProperty Name
        
        $duplicateItems = $communityItems | Where-Object { $hacsfilesItems -contains $_ }
        
        if ($duplicateItems.Count -gt 0) {
            Log-Message "  发现 $($duplicateItems.Count) 个重复资源:" "Yellow"
            foreach ($item in $duplicateItems) {
                Log-Message "    - $item" "Yellow"
                $duplicates += $item
            }
            
            $removeDuplicates = Read-Host "  是否移除重复资源? (Y/N)"
            if ($removeDuplicates -eq "Y" -or $removeDuplicates -eq "y") {
                foreach ($item in $duplicates) {
                    $hacsPath = Join-Path $hacsfilesDir $item
                    if (Test-Path $hacsPath) {
                        Log-Message "    移除重复资源: $hacsPath" "Yellow"
                        Remove-Item $hacsPath -Recurse -Force
                    }
                }
                Log-Message "  重复资源已移除" "Green"
            }
        } else {
            Log-Message "  未发现重复资源" "Green"
        }
    }
    
    # 修复常见的前端资源问题
    Log-Message "修复常见前端资源问题..." "White"
    
    # 检查card-mod资源
    $cardModPaths = @(
        "config\www\community\lovelace-card-mod\card-mod.js",
        "config\www\hacsfiles\lovelace-card-mod\card-mod.js",
        "config\www\custom_ui\lovelace-card-mod\card-mod.js",
        "config\www\lovelace-card-mod\card-mod.js"
    )
    
    $cardModExists = $false
    foreach ($path in $cardModPaths) {
        if (Test-Path $path) {
            $cardModExists = $true
            Log-Message "  找到card-mod资源: $path" "Green"
            break
        }
    }
    
    if (-not $cardModExists) {
        Log-Message "  未找到card-mod资源，这可能会导致界面问题" "Yellow"
    }
    
    Log-Message "前端资源修复完成" "Green"
}

# 修复HACS组件问题
function Fix-HacsIssues {
    Log-Message "`n开始修复HACS组件问题..." "Cyan"
    
    # 检查HACS组件
    $hacsDir = "config\custom_components\hacs"
    if (-not (Test-Path $hacsDir)) {
        Log-Message "错误: HACS组件未安装" "Red"
        Log-Message "请先安装HACS组件: https://hacs.xyz/docs/installation/manual" "Yellow"
        return
    }
    
    # 创建备份
    $backupPath = Create-Backup "hacs"
    Compress-Archive -Path $hacsDir -DestinationPath $backupPath -Force
    
    # 检查HACS数据目录
    Log-Message "检查HACS数据目录..." "White"
    
    $hacsDataDir = "config\.storage\hacs"
    if (-not (Test-Path $hacsDataDir)) {
        Log-Message "  HACS数据目录不存在，这可能是首次安装" "Yellow"
    } else {
        # 检查HACS数据文件
        $hacsDataFile = "config\.storage\hacs.data"
        if (Test-Path $hacsDataFile) {
            try {
                $hacsData = Get-Content $hacsDataFile -Raw | ConvertFrom-Json
                Log-Message "  HACS数据文件正常" "Green"
            } catch {
                Log-Message "  HACS数据文件可能已损坏: $_" "Red"
                $backupHacsData = "${hacsDataFile}.bak_${timestamp}"
                Copy-Item $hacsDataFile $backupHacsData -Force
                Log-Message "  已备份损坏的HACS数据文件到: $backupHacsData" "Yellow"
            }
        }
    }
    
    # 检查HACS前端资源目录
    Log-Message "检查HACS前端资源目录..." "White"
    
    $hacsFrontendDirs = @(
        "config\www\community",
        "config\www\hacsfiles"
    )
    
    $hasFrontendDir = $false
    foreach ($dir in $hacsFrontendDirs) {
        if (Test-Path $dir) {
            $hasFrontendDir = $true
            $resources = (Get-ChildItem $dir -Directory).Count
            Log-Message "  发现HACS前端资源目录: $dir (包含 $resources 个资源)" "Green"
        }
    }
    
    if (-not $hasFrontendDir) {
        Log-Message "  未找到HACS前端资源目录，创建默认目录..." "Yellow"
        New-Item -ItemType Directory -Path "config\www\community" -Force | Out-Null
        Log-Message "  已创建HACS前端资源目录: config\www\community" "Green"
    }
    
    Log-Message "HACS组件修复完成" "Green"
}

# 修复数据库问题
function Fix-DatabaseIssues {
    Log-Message "`n开始修复数据库问题..." "Cyan"
    
    # 创建备份
    $backupPath = Create-Backup "database"
    Compress-Archive -Path "config\.storage" -DestinationPath $backupPath -Force
    
    # 检查核心数据库文件
    Log-Message "检查核心数据库文件..." "White"
    
    $coreDbFile = "config\.storage\core.restore_state"
    if (Test-Path $coreDbFile) {
        $dbInfo = Get-Item $coreDbFile
        $dbSize = [math]::Round($dbInfo.Length / 1MB, 2)
        
        if ($dbSize -gt 50) {
            Log-Message "  数据库文件较大 ($dbSize MB)，可能需要清理" "Yellow"
            $cleanDb = Read-Host "  是否清理数据库文件? (Y/N)"
            
            if ($cleanDb -eq "Y" -or $cleanDb -eq "y") {
                $backupDbFile = "${coreDbFile}.bak_${timestamp}"
                Copy-Item $coreDbFile $backupDbFile -Force
                Log-Message "  已备份数据库文件到: $backupDbFile" "Green"
                
                # 如果有token，尝试通过API清理
                if ($hasToken) {
                    Log-Message "  尝试通过API清理数据库..." "White"
                    
                    $headers = @{
                        "Authorization" = "Bearer $token"
                        "Content-Type" = "application/json"
                    }
                    
                    try {
                        Invoke-RestMethod -Uri "http://localhost:8123/api/services/recorder/purge" -Method Post -Headers $headers -Body "{}" | Out-Null
                        Log-Message "  已发送数据库清理命令" "Green"
                    } catch {
                        Log-Message "  通过API清理数据库失败: $_" "Red"
                    }
                } else {
                    Log-Message "  由于没有访问令牌，无法通过API清理数据库" "Yellow"
                    Log-Message "  建议手动重启Home Assistant以清理数据库" "Yellow"
                }
            }
        } else {
            Log-Message "  数据库文件大小正常 ($dbSize MB)" "Green"
        }
    } else {
        Log-Message "  未找到核心数据库文件，这可能是首次安装" "Yellow"
    }
    
    Log-Message "数据库修复完成" "Green"
}

# 修复Card-mod前端问题
function Fix-CardModIssues {
    Log-Message "`n开始修复Card-mod前端问题..." "Cyan"
    
    # 检查Card-mod资源
    Log-Message "检查Card-mod资源..." "White"
    
    $cardModPaths = @(
        "config\www\community\lovelace-card-mod\card-mod.js",
        "config\www\hacsfiles\lovelace-card-mod\card-mod.js",
        "config\www\custom_ui\lovelace-card-mod\card-mod.js",
        "config\www\lovelace-card-mod\card-mod.js"
    )
    
    $validCardModPath = $null
    foreach ($path in $cardModPaths) {
        if (Test-Path $path) {
            $validCardModPath = $path
            Log-Message "  找到Card-mod资源: $path" "Green"
            break
        }
    }
    
    if ($null -eq $validCardModPath) {
        Log-Message "  未找到Card-mod资源，尝试从备份恢复..." "Yellow"
        
        # 查找备份中的Card-mod资源
        $backupDirs = Get-ChildItem -Path "." -Filter "修复备份_*" -Directory | Sort-Object LastWriteTime -Descending
        $foundInBackup = $false
        
        foreach ($backupDir in $backupDirs) {
            $backupFiles = Get-ChildItem -Path $backupDir.FullName -Filter "frontend_backup_*.zip"
            
            foreach ($backupFile in $backupFiles) {
                Log-Message "  检查备份: $($backupFile.FullName)" "White"
                
                # 解压缩备份以检查Card-mod资源
                $tempDir = "temp_extract_${timestamp}"
                New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
                
                try {
                    Expand-Archive -Path $backupFile.FullName -DestinationPath $tempDir -Force
                    
                    # 查找Card-mod资源
                    $cardModFiles = Get-ChildItem -Path $tempDir -Recurse -Filter "card-mod.js"
                    
                    if ($cardModFiles.Count -gt 0) {
                        $sourceCardMod = $cardModFiles[0].FullName
                        Log-Message "  在备份中找到Card-mod资源: $sourceCardMod" "Green"
                        
                        # 创建目标目录
                        $targetDir = "config\www\community\lovelace-card-mod"
                        if (-not (Test-Path $targetDir)) {
                            New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
                        }
                        
                        # 复制Card-mod资源
                        $targetPath = Join-Path $targetDir "card-mod.js"
                        Copy-Item $sourceCardMod $targetPath -Force
                        Log-Message "  已恢复Card-mod资源到: $targetPath" "Green"
                        
                        $foundInBackup = $true
                        $validCardModPath = $targetPath
                        break
                    }
                } catch {
                    Log-Message "  解压缩备份失败: $_" "Red"
                } finally {
                    # 清理临时目录
                    if (Test-Path $tempDir) {
                        Remove-Item $tempDir -Recurse -Force
                    }
                }
                
                if ($foundInBackup) {
                    break
                }
            }
            
            if ($foundInBackup) {
                break
            }
        }
        
        if (-not $foundInBackup) {
            Log-Message "  未在备份中找到Card-mod资源，需要手动安装" "Red"
            Log-Message "  建议通过HACS安装Card-mod: https://github.com/thomasloven/lovelace-card-mod" "Yellow"
        }
    }
    
    # 验证Card-mod资源
    if ($null -ne $validCardModPath) {
        Log-Message "验证Card-mod资源..." "White"
        
        try {
            $cardModContent = Get-Content $validCardModPath -Raw
            
            if ($cardModContent -match "cardMod") {
                Log-Message "  Card-mod资源验证通过" "Green"
            } else {
                Log-Message "  Card-mod资源可能已损坏" "Red"
            }
        } catch {
            Log-Message "  读取Card-mod资源失败: $_" "Red"
        }
    }
    
    Log-Message "Card-mod前端问题修复完成" "Green"
}

# 修复实体引用问题
function Fix-EntityReferences {
    Log-Message "`n开始修复实体引用问题..." "Cyan"
    
    if (-not $hasToken) {
        Log-Message "无法修复实体引用问题: 缺少访问令牌" "Red"
        return
    }
    
    # 获取实体列表
    Log-Message "获取实体列表..." "White"
    
    $headers = @{
        "Authorization" = "Bearer $token"
        "Content-Type" = "application/json"
    }
    
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:8123/api/states" -Method Get -Headers $headers
        $entityCount = $response.Count
        Log-Message "  找到 $entityCount 个实体" "Green"
        
        # 保存实体列表到文件
        $entitiesFile = "entities_list.json"
        $response | ConvertTo-Json -Depth 10 | Out-File $entitiesFile -Encoding utf8
        Log-Message "  已保存实体列表到: $entitiesFile" "Green"
        
        # 检查仪表板配置
        Log-Message "检查仪表板配置..." "White"
        
        $dashboardFile = "config\lovelace\ui-lovelace.yaml"
        if (Test-Path $dashboardFile) {
            Log-Message "  找到仪表板配置文件: $dashboardFile" "Green"
            
            # 备份仪表板配置
            $backupDashboard = "${dashboardFile}.bak_${timestamp}"
            Copy-Item $dashboardFile $backupDashboard -Force
            Log-Message "  已备份仪表板配置到: $backupDashboard" "Green"
            
            # 读取仪表板配置
            $dashboardContent = Get-Content $dashboardFile -Raw
            
            # 获取实体ID列表
            $entityIds = $response | ForEach-Object { $_.entity_id }
            
            # 检查无效实体引用
            $invalidEntities = @()
            $matches = [regex]::Matches($dashboardContent, "entity_id: ([a-z0-9_\.]+)")
            foreach ($match in $matches) {
                $entityId = $match.Groups[1].Value
                if ($entityIds -notcontains $entityId) {
                    $invalidEntities += $entityId
                }
            }
            
            # 检查无效实体引用
            $matches = [regex]::Matches($dashboardContent, "entity: ([a-z0-9_\.]+)")
            foreach ($match in $matches) {
                $entityId = $match.Groups[1].Value
                if ($entityIds -notcontains $entityId) {
                    $invalidEntities += $entityId
                }
            }
            
            if ($invalidEntities.Count -gt 0) {
                Log-Message "  发现 $($invalidEntities.Count) 个无效实体引用:" "Yellow"
                $uniqueInvalidEntities = $invalidEntities | Select-Object -Unique
                foreach ($entity in $uniqueInvalidEntities) {
                    Log-Message "    - $entity" "Yellow"
                }
                
                $fixEntities = Read-Host "  是否尝试自动修复无效实体引用? (Y/N)"
                if ($fixEntities -eq "Y" -or $fixEntities -eq "y") {
                    Log-Message "  尝试自动修复无效实体引用..." "White"
                    
                    # 自动修复的逻辑可以根据需要扩展
                    Log-Message "  自动修复功能需要根据具体情况定制" "Yellow"
                    Log-Message "  建议手动检查和修复无效实体引用" "Yellow"
                }
            } else {
                Log-Message "  未发现无效实体引用" "Green"
            }
        } else {
            Log-Message "  未找到仪表板配置文件" "Yellow"
        }
    } catch {
        Log-Message "  获取实体列表失败: $_" "Red"
    }
    
    Log-Message "实体引用问题修复完成" "Green"
}

# 修复权限问题
function Fix-PermissionIssues {
    Log-Message "`n开始修复权限问题..." "Cyan"
    
    # 检查关键目录
    Log-Message "检查关键目录权限..." "White"
    
    $keyDirs = @(
        "config",
        "config\custom_components",
        "config\www",
        "config\.storage"
    )
    
    foreach ($dir in $keyDirs) {
        if (Test-Path $dir) {
            Log-Message "  检查目录: $dir" "White"
            
            try {
                # 获取当前权限
                $acl = Get-Acl $dir
                
                # 添加完全控制权限
                $currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
                $accessRule = New-Object System.Security.AccessControl.FileSystemAccessRule(
                    $currentUser,
                    "FullControl",
                    "ContainerInherit,ObjectInherit",
                    "None",
                    "Allow"
                )
                
                $acl.AddAccessRule($accessRule)
                Set-Acl $dir $acl
                
                Log-Message "  已修复目录权限: $dir" "Green"
            } catch {
                Log-Message "  修复目录权限失败: $dir - $_" "Red"
            }
        }
    }
    
    Log-Message "权限问题修复完成" "Green"
}

# 清理缓存
function Clear-Cache {
    Log-Message "`n开始清理缓存..." "Cyan"
    
    # 检查缓存目录
    $cacheDirs = @(
        "config\.storage\.cache",
        "config\.cache"
    )
    
    foreach ($dir in $cacheDirs) {
        if (Test-Path $dir) {
            Log-Message "  清理缓存目录: $dir" "White"
            
            try {
                # 备份缓存目录
                $backupDir = "${dir}.bak_${timestamp}"
                Copy-Item $dir $backupDir -Recurse -Force
                Log-Message "  已备份缓存目录到: $backupDir" "Green"
                
                # 清理缓存目录
                Remove-Item $dir -Recurse -Force
                Log-Message "  已清理缓存目录: $dir" "Green"
            } catch {
                Log-Message "  清理缓存目录失败: $dir - $_" "Red"
            }
        }
    }
    
    # 清理临时文件
    $tempDirs = @(
        "config\www\.ha-temp"
    )
    
    foreach ($dir in $tempDirs) {
        if (Test-Path $dir) {
            Log-Message "  清理临时目录: $dir" "White"
            
            try {
                Remove-Item $dir -Recurse -Force
                Log-Message "  已清理临时目录: $dir" "Green"
            } catch {
                Log-Message "  清理临时目录失败: $dir - $_" "Red"
            }
        }
    }
    
    Log-Message "缓存清理完成" "Green"
}

# 执行全部修复
function Fix-All {
    Log-Message "`n开始执行全部修复..." "Magenta"
    
    Fix-ConfigurationFiles
    Fix-FrontendResources
    Fix-HacsIssues
    Fix-DatabaseIssues
    Fix-CardModIssues
    Fix-EntityReferences
    Fix-PermissionIssues
    Clear-Cache
    
    Log-Message "`n全部修复完成!" "Magenta"
    Log-Message "建议重启Home Assistant以应用所有修复" "Yellow"
}

# 主程序
$exitRequested = $false

while (-not $exitRequested) {
    $choice = Show-Menu
    
    switch ($choice) {
        "1" { Fix-ConfigurationFiles }
        "2" { Fix-FrontendResources }
        "3" { Fix-HacsIssues }
        "4" { Fix-DatabaseIssues }
        "5" { Fix-CardModIssues }
        "6" { Fix-EntityReferences }
        "7" { Fix-PermissionIssues }
        "8" { Clear-Cache }
        "9" { Fix-All }
        "0" { $exitRequested = $true }
        default { Log-Message "无效的选择，请重试" "Red" }
    }
    
    if (-not $exitRequested) {
        Log-Message "`n按任意键继续..." "Cyan"
        $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    }
}

Log-Message "`n修复操作已完成！日志已保存到: $logFile" "Magenta"
Log-Message "如有需要，可以使用'脚本\系统维护\重启HA.ps1'脚本重启Home Assistant" "Yellow" 