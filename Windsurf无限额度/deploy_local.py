"""
Windsurf 无限畅享 — 一键部署 v1.0
==================================
零花费 · 零精力 · 全自动

用法 (需管理员):
  python deploy_local.py              # 完整部署
  python deploy_local.py --check      # 仅检查状态
  python deploy_local.py --remote IP  # 远程部署到指定机器
"""

import sys
import os
import subprocess
import shutil
import socket
import json
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
DOMAINS = ["server.self-serve.windsurf.com", "server.codeium.com"]


def run(cmd, **kw):
    r = subprocess.run(cmd, shell=True, capture_output=True,
                       encoding="utf-8", errors="ignore", timeout=30, **kw)
    return r.returncode == 0, r.stdout.strip()


def step(n, total, msg):
    print(f"\n  [{n}/{total}] {msg}")


def main():
    check_only = "--check" in sys.argv

    print()
    print("  ╔══════════════════════════════════════════════╗")
    print("  ║  Windsurf 无限畅享 一键部署 v1.0              ║")
    print("  ║  零花费 · 零精力 · 全自动                     ║")
    print("  ╚══════════════════════════════════════════════╝")
    print()

    total = 7
    issues = []

    # 1. 证书
    step(1, total, "TLS证书...")
    cert_pem = SCRIPT_DIR / "windsurf_proxy_ca.pem"
    cert_key = SCRIPT_DIR / "windsurf_proxy_ca.key"
    cert_cer = SCRIPT_DIR / "windsurf_proxy_ca.cer"

    if cert_pem.exists() and cert_key.exists():
        print("        ✅ 证书已存在")
    elif not check_only:
        ok, out = run(f'"{sys.executable}" "{SCRIPT_DIR / "windsurf_proxy.py"}" --gen-cert')
        if ok:
            print("        ✅ 证书已生成")
        else:
            issues.append("证书生成失败")
            print(f"        ❌ 失败: {out}")
    else:
        issues.append("证书不存在")
        print("        ❌ 缺失")

    # 2. 系统证书信任
    step(2, total, "系统证书信任...")
    if cert_cer.exists():
        if not check_only:
            run(f'certutil -addstore Root "{cert_cer}"')
        print("        ✅ 已安装到受信任根")
    else:
        print("        ⚠ CER文件不存在")

    # 3. SSL_CERT_FILE
    step(3, total, "SSL_CERT_FILE环境变量...")
    sys_cert = os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "windsurf_proxy_ca.pem")
    if not check_only and cert_pem.exists():
        shutil.copy2(str(cert_pem), sys_cert)
        run(f'setx SSL_CERT_FILE "{sys_cert}" /M')
    if os.path.isfile(sys_cert):
        print(f"        ✅ {sys_cert}")
    else:
        issues.append("SSL_CERT_FILE未配置")
        print("        ❌ 缺失")

    # 4. hosts
    step(4, total, "hosts文件...")
    hosts_path = r"C:\Windows\System32\drivers\etc\hosts"
    try:
        with open(hosts_path, "r") as f:
            hosts = f.read()
        missing = [d for d in DOMAINS if d not in hosts]
        if missing and not check_only:
            with open(hosts_path, "a") as f:
                for d in missing:
                    f.write(f"\n127.0.0.1 {d}")
            print(f"        ✅ 添加了 {len(missing)} 条")
        elif not missing:
            print("        ✅ 全部已配置")
        else:
            issues.append(f"hosts缺少: {', '.join(missing)}")
            print(f"        ❌ 缺少: {', '.join(missing)}")
    except PermissionError:
        issues.append("hosts无权限(需管理员)")
        print("        ❌ 无权限")

    # 5. Windsurf settings.json
    step(5, total, "Windsurf settings.json...")
    settings_path = os.path.expandvars(r"%APPDATA%\Windsurf\User\settings.json")
    if os.path.isfile(settings_path):
        with open(settings_path, "r", encoding="utf-8") as f:
            settings = json.load(f)
        changed = False
        if settings.get("http.proxyStrictSSL") != False:
            settings["http.proxyStrictSSL"] = False
            changed = True
        if settings.get("http.proxySupport") != "off":
            settings["http.proxySupport"] = "off"
            changed = True
        if changed and not check_only:
            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=4, ensure_ascii=False)
            print("        ✅ 已更新")
        elif not changed:
            print("        ✅ 已正确")
        else:
            issues.append("settings需更新")
    else:
        print("        ⚠ Windsurf未安装或未初始化")

    # 6. Patch
    step(6, total, "JS补丁...")
    patch_script = SCRIPT_DIR / "patch_windsurf.py"
    if patch_script.exists():
        if not check_only:
            ok, out = run(f'"{sys.executable}" "{patch_script}"')
            patched = "[=] No new" in out or "[✓]" in out
            if patched:
                print("        ✅ 补丁已应用")
            else:
                issues.append("补丁应用失败")
                print(f"        ❌ {out[:100]}")
        else:
            ok, out = run(f'"{sys.executable}" "{patch_script}" --verify')
            if "All patches active" in out:
                print("        ✅ 补丁已生效")
            else:
                issues.append("补丁未生效")
                print("        ❌ 部分未生效")
    else:
        issues.append("patch脚本缺失")

    # 7. Guardian
    step(7, total, "Guardian守护...")
    guardian = SCRIPT_DIR / "windsurf_guardian.py"
    if guardian.exists():
        if not check_only:
            run(f'"{sys.executable}" "{guardian}" --install')
        print("        ✅ 计划任务已注册")
    else:
        issues.append("guardian脚本缺失")

    # Summary
    print("\n" + "=" * 50)
    if not issues:
        print("  🎉 部署完成! 所有组件就绪!")
    else:
        print(f"  ⚠ {len(issues)}个问题:")
        for i in issues:
            print(f"    ❌ {i}")
    print("=" * 50)
    return len(issues) == 0


if __name__ == "__main__":
    main()
