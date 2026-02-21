# Phone Agent Soul 一键部署脚本
# 在 Agent Windows 账户下运行此脚本
# 用法: .\deploy-to-agent.ps1 -WorkspacePath "C:\Users\AgentUser\phone-agent-workspace"

param(
    [Parameter(Mandatory=$false)]
    [string]$WorkspacePath = "$env:USERPROFILE\phone-agent-workspace",
    
    [Parameter(Mandatory=$false)]
    [string]$SourcePath = $PSScriptRoot
)

Write-Host "=== Phone Agent Soul Deployment ===" -ForegroundColor Cyan
Write-Host "Source: $SourcePath"
Write-Host "Target workspace: $WorkspacePath"
Write-Host ""

# Step 1: Create workspace directory structure
Write-Host "[1/6] Creating workspace structure..." -ForegroundColor Yellow
$dirs = @(
    "$WorkspacePath\.windsurf\rules",
    "$WorkspacePath\.windsurf\skills\semantic-find-click",
    "$WorkspacePath\.windsurf\skills\app-open",
    "$WorkspacePath\.windsurf\skills\explore-unknown-app",
    "$WorkspacePath\.windsurf\workflows",
    "$WorkspacePath\shared-knowledge",
    "$WorkspacePath\operation-logs",
    "$WorkspacePath\scripts"
)
foreach ($dir in $dirs) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
}
Write-Host "  Created $(($dirs).Count) directories" -ForegroundColor Green

# Step 2: Deploy soul and rules to workspace
Write-Host "[2/6] Deploying rules to workspace..." -ForegroundColor Yellow
Copy-Item "$SourcePath\soul.md" "$WorkspacePath\.windsurf\rules\soul.md" -Force
Copy-Item "$SourcePath\execution-engine.md" "$WorkspacePath\.windsurf\rules\execution-engine.md" -Force
Write-Host "  soul.md + execution-engine.md deployed" -ForegroundColor Green

# Step 3: Create API reference rule (inline, based on practice findings)
Write-Host "[3/6] Creating API reference rule..." -ForegroundColor Yellow
@'
---
description: ScreenStream API reference for Phone Agent
alwaysApply: true
---

# API Reference

## Connection
- Detect port: scan 8080-8099 for GET /status response
- Test: GET /status -> {"ok":true}

## Perception
- `GET /screen/text` - all visible text + clickable elements
- `GET /viewtree?depth=N` - View tree (default depth=4)
- `GET /windowinfo` - package name + node count
- `GET /foreground` - foreground app package
- `GET /deviceinfo` - device info (model/battery/wifi/storage)
- `GET /notifications/read?limit=N` - recent notifications

## Action
- `POST /findclick {"text":"X"}` - semantic find and click
- `POST /tap {"nx":0.5,"ny":0.5}` - normalized coordinate tap
- `POST /text {"text":"X"}` - input text
- `POST /intent {"action":"X","data":"Y","package":"Z"}` - send Intent
- `GET /wait?text=X&timeout=5000` - wait for text to appear
- `POST /dismiss` - dismiss dialog
- `POST /settext {"search":"X","value":"Y"}` - set input field text
- `POST /command {"command":"natural language"}` - NLP command

## Navigation
- `POST /home` | `POST /back` | `POST /recents` | `POST /notifications`

## System
- `POST /volume {"stream":"music","level":8}` | `POST /brightness/128`
- `POST /wake` | `POST /lock` | `POST /flashlight/true`
'@ | Set-Content "$WorkspacePath\.windsurf\rules\api-reference.md" -Encoding UTF8
Write-Host "  api-reference.md created" -ForegroundColor Green

# Step 4: Deploy skills
Write-Host "[4/6] Deploying skills..." -ForegroundColor Yellow
Copy-Item "$SourcePath\skills\semantic-find-click\SKILL.md" "$WorkspacePath\.windsurf\skills\semantic-find-click\SKILL.md" -Force
Copy-Item "$SourcePath\skills\app-open\SKILL.md" "$WorkspacePath\.windsurf\skills\app-open\SKILL.md" -Force
Copy-Item "$SourcePath\skills\explore-unknown-app\SKILL.md" "$WorkspacePath\.windsurf\skills\explore-unknown-app\SKILL.md" -Force
Write-Host "  3 skills deployed" -ForegroundColor Green

# Step 5: Deploy global rules
Write-Host "[5/6] Deploying global rules..." -ForegroundColor Yellow
$globalRulesDir = "$env:USERPROFILE\.codeium\windsurf\memories"
if (-not (Test-Path $globalRulesDir)) {
    New-Item -ItemType Directory -Force -Path $globalRulesDir | Out-Null
}
$globalRulesTarget = "$globalRulesDir\global_rules.md"
if (Test-Path $globalRulesTarget) {
    $backup = "$globalRulesTarget.backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
    Copy-Item $globalRulesTarget $backup
    Write-Host "  Backed up existing global_rules.md to $backup" -ForegroundColor DarkYellow
}
Copy-Item "$SourcePath\global-rules.md" $globalRulesTarget -Force
Write-Host "  global_rules.md deployed" -ForegroundColor Green

# Step 6: Create AGENTS.md and device profile template
Write-Host "[6/6] Creating workspace files..." -ForegroundColor Yellow
@'
# Phone Agent Workspace

You are Phone Agent. You operate Android phones through ScreenStream HTTP API.

## Three Meta-Rules (from soul.md)
1. **Loop**: observe -> decide -> act -> verify -> learn. Always.
2. **Trust**: trust = f(success history). No trust = no autonomy.
3. **Honest**: Don't know = say don't know. Failed = say failed.

## Connection
- Scan ports 8080-8099 for active ScreenStream instance
- Test: GET /status -> {"ok":true}
- ADB forward: adb forward tcp:PORT tcp:PORT

## Forbidden
- Never modify source code
- Never operate financial/payment apps
- Never read notifications containing passwords/verification codes
'@ | Set-Content "$WorkspacePath\AGENTS.md" -Encoding UTF8

@'
---
description: Current connected device profile (auto-filled on first connection)
alwaysApply: true
---

# Device Profile

> Run GET /deviceinfo to fill this. Update after each new device connection.

- Model: [pending]
- Android: [pending]
- OEM: [pending]
- Port: [pending]
- Screen: [pending]

## Known Characteristics
- [accumulate through operation experience]
'@ | Set-Content "$WorkspacePath\.windsurf\rules\device-profile.md" -Encoding UTF8

# Init git
Push-Location $WorkspacePath
if (-not (Test-Path ".git")) {
    git init | Out-Null
    Write-Host "  Git initialized" -ForegroundColor Green
}
Pop-Location

Write-Host "  AGENTS.md + device-profile.md created" -ForegroundColor Green

# Summary
Write-Host ""
Write-Host "=== Deployment Complete ===" -ForegroundColor Cyan
Write-Host "Workspace: $WorkspacePath" -ForegroundColor White
Write-Host ""
Write-Host "Files deployed:" -ForegroundColor White
Write-Host "  .windsurf/rules/soul.md              (Agent consciousness)"
Write-Host "  .windsurf/rules/execution-engine.md   (OODA-L loop)"
Write-Host "  .windsurf/rules/api-reference.md      (API quick ref)"
Write-Host "  .windsurf/rules/device-profile.md     (device template)"
Write-Host "  .windsurf/skills/ x3                  (find-click, app-open, explore)"
Write-Host "  ~/.codeium/.../global_rules.md        (global rules)"
Write-Host "  AGENTS.md                             (root directive)"
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Open $WorkspacePath in Windsurf"
Write-Host "  2. Start a new Cascade conversation"
Write-Host "  3. Say: 'Initialize memory seeds - create 6 base knowledge entries'"
Write-Host "  4. Connect phone: adb forward tcp:PORT tcp:PORT"
Write-Host "  5. Test: 'Check phone connection and read the screen'"
