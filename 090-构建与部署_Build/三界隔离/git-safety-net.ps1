# Git Safety Net — auto-snapshot before risky operations
# Usage: .\git-safety-net.ps1 -Action snapshot|rollback|status
# Called automatically by Agent before heavy modifications
param(
    [ValidateSet('snapshot','rollback','status','list')]
    [string]$Action = 'status',
    [string]$Message = ''
)

$root = 'E:\道\道生一\一生二'

switch ($Action) {
    'snapshot' {
        $tag = "safety/$(Get-Date -Format 'yyyyMMdd-HHmmss')"
        $msg = if ($Message) { $Message } else { "Auto-snapshot before Agent operation" }
        git -C $root stash push -m "SAFETY: $msg" --include-untracked 2>$null
        $stashed = $LASTEXITCODE -eq 0
        if ($stashed) {
            git -C $root stash pop 2>$null
        }
        # Create lightweight tag as bookmark
        git -C $root tag $tag -m $msg 2>$null
        Write-Host "Snapshot: $tag" -ForegroundColor Green
    }
    'rollback' {
        $tags = git -C $root tag -l 'safety/*' --sort=-creatordate 2>$null
        if ($tags) {
            $latest = ($tags -split "`n")[0]
            Write-Host "Rolling back to: $latest" -ForegroundColor Yellow
            git -C $root checkout $latest -- . 2>$null
            Write-Host "Rolled back. Use 'git diff' to review changes." -ForegroundColor Green
        } else {
            Write-Host "No safety snapshots found" -ForegroundColor Red
        }
    }
    'list' {
        Write-Host "Safety snapshots:" -ForegroundColor Cyan
        git -C $root tag -l 'safety/*' --sort=-creatordate -n1 2>$null | Select-Object -First 10
    }
    'status' {
        $tags = (git -C $root tag -l 'safety/*' 2>$null | Measure-Object).Count
        $branch = git -C $root branch --show-current 2>$null
        $dirty = (git -C $root status --porcelain 2>$null | Measure-Object).Count
        Write-Host "Branch: $branch | Snapshots: $tags | Uncommitted: $dirty"
    }
}
