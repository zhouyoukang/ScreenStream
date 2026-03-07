<#
.SYNOPSIS
  GitHub API Fallback — 当GitHub MCP不可用时的降级方案
  
.DESCRIPTION
  通过Invoke-WebRequest + Clash代理直接调用GitHub REST API
  覆盖最常用操作: search/get/create/list
  
.EXAMPLE
  # 搜索仓库
  .\github-fallback.ps1 search-repos "windsurf mcp"
  
  # 获取文件内容
  .\github-fallback.ps1 get-file zhouyoukang/mcp-test-repo README.md
  
  # 列出Issues
  .\github-fallback.ps1 list-issues zhouyoukang/mcp-test-repo
  
  # 列出Commits
  .\github-fallback.ps1 list-commits zhouyoukang/mcp-test-repo -n 5
  
  # 创建Issue
  .\github-fallback.ps1 create-issue zhouyoukang/mcp-test-repo "Bug Title" "Bug body"
  
  # 获取PR
  .\github-fallback.ps1 get-pr zhouyoukang/mcp-test-repo 1
  
  # 健康检查
  .\github-fallback.ps1 health
#>

param(
    [Parameter(Position=0)]
    [string]$Command,
    
    [Parameter(Position=1)]
    [string]$Arg1,
    
    [Parameter(Position=2)]
    [string]$Arg2,
    
    [Parameter(Position=3)]
    [string]$Arg3,
    
    [int]$n = 10
)

$ErrorActionPreference = "Stop"

# --- Config ---
$PROXY = "http://127.0.0.1:7890"
$TOKEN = [System.Environment]::GetEnvironmentVariable("GITHUB_PERSONAL_ACCESS_TOKEN", "User")
if (-not $TOKEN) { $TOKEN = $env:GITHUB_PERSONAL_ACCESS_TOKEN }
$API = "https://api.github.com"

function Invoke-GH {
    param([string]$Uri, [string]$Method = "GET", $Body = $null)
    
    $curlArgs = @("-s", "-m", "15", "-H", "Accept: application/vnd.github+json", "-H", "User-Agent: MCP-Fallback/1.0", "-H", "X-GitHub-Api-Version: 2022-11-28")
    if ($TOKEN) { $curlArgs += @("-H", "Authorization: Bearer $TOKEN") }
    if ($Method -ne "GET") { $curlArgs += @("-X", $Method) }
    if ($Body) { $curlArgs += @("-H", "Content-Type: application/json", "-d", ($Body | ConvertTo-Json -Depth 10 -Compress)) }
    
    # Try with proxy first (required in China)
    $proxyOk = Test-NetConnection -ComputerName 127.0.0.1 -Port 7890 -WarningAction SilentlyContinue -InformationLevel Quiet
    if ($proxyOk) { $curlArgs += @("-x", $PROXY) }
    
    $curlArgs += $Uri
    $result = & curl.exe @curlArgs 2>$null
    if ($LASTEXITCODE -ne 0) { Write-Error "curl failed (exit=$LASTEXITCODE)"; return $null }
    $json = ($result -join "`n")
    if (-not $json) { Write-Error "Empty response from GitHub API"; return $null }
    return ($json | ConvertFrom-Json)
}

switch ($Command) {
    "health" {
        Write-Host "=== GitHub Fallback Health ==="
        Write-Host "Token: $(if($TOKEN){'SET ('+$TOKEN.Length+'chars)'}else{'NOT SET'})"
        Write-Host "Proxy: $PROXY"
        $proxyOk = Test-NetConnection -ComputerName 127.0.0.1 -Port 7890 -WarningAction SilentlyContinue -InformationLevel Quiet
        Write-Host "Proxy status: $(if($proxyOk){'ONLINE'}else{'OFFLINE'})"
        try {
            $r = Invoke-GH "$API/rate_limit"
            $core = $r.resources.core
            Write-Host "API: OK (remaining=$($core.remaining)/$($core.limit))"
        } catch {
            Write-Host "API: FAIL - $($_.Exception.Message)"
        }
    }
    
    "search-repos" {
        $q = [System.Uri]::EscapeDataString($Arg1)
        $r = Invoke-GH "$API/search/repositories?q=$q&per_page=$n"
        $r.items | ForEach-Object {
            Write-Host "$($_.full_name) [$($_.stargazers_count)★] — $($_.description)"
        }
        Write-Host "`nTotal: $($r.total_count) results"
    }
    
    "search-code" {
        $q = [System.Uri]::EscapeDataString($Arg1)
        $r = Invoke-GH "$API/search/code?q=$q&per_page=$n"
        $r.items | ForEach-Object {
            Write-Host "$($_.repository.full_name)/$($_.path)"
        }
        Write-Host "`nTotal: $($r.total_count) results"
    }
    
    "get-file" {
        # Arg1 = owner/repo, Arg2 = path
        $r = Invoke-GH "$API/repos/$Arg1/contents/$Arg2"
        if ($r.encoding -eq "base64") {
            $content = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($r.content))
            Write-Host $content
        } else {
            $r | ConvertTo-Json -Depth 5
        }
    }
    
    "list-issues" {
        $r = Invoke-GH "$API/repos/$Arg1/issues?state=all&per_page=$n"
        $r | ForEach-Object {
            $type = if($_.pull_request){"PR"}else{"Issue"}
            Write-Host "#$($_.number) [$($_.state)] ($type) $($_.title)"
        }
    }
    
    "get-issue" {
        $r = Invoke-GH "$API/repos/$Arg1/issues/$Arg2"
        Write-Host "#$($r.number) [$($r.state)] $($r.title)"
        Write-Host "By: $($r.user.login) | Created: $($r.created_at)"
        Write-Host "---"
        Write-Host $r.body
    }
    
    "create-issue" {
        # Arg1 = owner/repo, Arg2 = title, Arg3 = body
        $body = @{ title = $Arg2; body = $Arg3 }
        $r = Invoke-GH "$API/repos/$Arg1/issues" -Method POST -Body $body
        Write-Host "Created: #$($r.number) $($r.title)"
        Write-Host "URL: $($r.html_url)"
    }
    
    "list-commits" {
        $r = Invoke-GH "$API/repos/$Arg1/commits?per_page=$n"
        $r | ForEach-Object {
            $date = $_.commit.committer.date
            $msg = $_.commit.message.Split("`n")[0]
            Write-Host "$($_.sha.Substring(0,7)) $date $msg"
        }
    }
    
    "get-pr" {
        $r = Invoke-GH "$API/repos/$Arg1/pulls/$Arg2"
        Write-Host "#$($r.number) [$($r.state)] $($r.title)"
        Write-Host "By: $($r.user.login) | $($r.head.ref) → $($r.base.ref)"
        Write-Host "Changed: $($r.changed_files) files, +$($r.additions)/-$($r.deletions)"
        Write-Host "---"
        Write-Host $r.body
    }
    
    "list-prs" {
        $r = Invoke-GH "$API/repos/$Arg1/pulls?state=all&per_page=$n"
        $r | ForEach-Object {
            Write-Host "#$($_.number) [$($_.state)] $($_.title) ($($_.head.ref)→$($_.base.ref))"
        }
    }
    
    "rate-limit" {
        $r = Invoke-GH "$API/rate_limit"
        $r.resources | Get-Member -MemberType NoteProperty | ForEach-Object {
            $res = $r.resources.($_.Name)
            Write-Host "$($_.Name): $($res.remaining)/$($res.limit)"
        }
    }
    
    default {
        Write-Host @"
GitHub API Fallback — MCP降级方案

Commands:
  health                              健康检查
  search-repos <query>                搜索仓库
  search-code <query>                 搜索代码
  get-file <owner/repo> <path>        获取文件内容
  list-issues <owner/repo>            列出Issues
  get-issue <owner/repo> <number>     获取Issue详情
  create-issue <owner/repo> <title> <body>  创建Issue
  list-commits <owner/repo>           列出Commits
  get-pr <owner/repo> <number>        获取PR详情
  list-prs <owner/repo>               列出PRs
  rate-limit                          API配额

Options:
  -n <count>                          结果数量(默认10)
"@
    }
}
