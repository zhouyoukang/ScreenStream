# 三界隔离 — 保存地界凭据 (仅需运行一次)
# 保存后, 双击 地界.rdp 或 .\enter.ps1 均免密直连
# Usage: .\save-cred.ps1

Write-Host ""
Write-Host "  保存地界RDP凭据 (一次性)" -ForegroundColor Cyan
Write-Host "  保存后双击 地界.rdp 免密直连" -ForegroundColor DarkGray
Write-Host ""

$pass = Read-Host "  输入 windsurf-test 密码" -AsSecureString
$bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($pass)
$plain = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
[System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)

# Save to Windows Credential Manager
cmdkey /generic:TERMSRV/127.0.0.1 /user:.\windsurf-test /pass:$plain
$plain = $null

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "  凭据已保存到 Windows Credential Manager" -ForegroundColor Green
    Write-Host "  现在可以免密连接地界:" -ForegroundColor Green
    Write-Host "    双击 地界.rdp" -ForegroundColor DarkGray
    Write-Host "    或 .\enter.ps1" -ForegroundColor DarkGray
} else {
    Write-Host ""
    Write-Host "  保存失败, 请手动在RDP对话框中勾选'记住凭据'" -ForegroundColor Red
}
