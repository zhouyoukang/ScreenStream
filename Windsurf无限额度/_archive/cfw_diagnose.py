"""
CFW 伏羲八卦全景诊断 v1.0
=============================
八卦解构CodeFreeWindsurf所有数据和端口，一键定位问题。

用法:
  python cfw_diagnose.py           # 全景诊断
  python cfw_diagnose.py --fix     # 诊断+自动修复
  python cfw_diagnose.py --kill443 # 仅清理443端口占用
"""

import subprocess, socket, os, sys, json, time, re
from pathlib import Path
from datetime import datetime

# ═══════════════════════════════════════════════════
# 常量
# ═══════════════════════════════════════════════════
CFW_NAMES = ["CodeFreeWindsurf", "CFW"]
HOSTS_PATH = r"C:\Windows\System32\drivers\etc\hosts"
HOSTS_ENTRIES = [
    "127.0.0.1 server.self-serve.windsurf.com",
    "127.0.0.1 server.codeium.com",
]
JS_CANDIDATES = [
    r"D:\Windsurf\resources\app\out\vs\workbench\workbench.desktop.main.js",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Windsurf\resources\app\out\vs\workbench\workbench.desktop.main.js"),
]
CERT_THUMBPRINT = "EE8978E69E0CFE3FBD6FFD7E511BE6337A2FC4F7"
CRITICAL_PORTS = {
    443: "CFW MITM Proxy",
    7890: "Clash混合代理",
    18443: "CFW Relay (LAN共享)",
    9097: "Clash API",
}
PORT_443_COMPETITORS = [
    # (服务名/进程名, 描述, 冲突根因)
    ("frpmgr", "FRP管理器服务", "frpmgr服务Auto启动可能抢占443或干扰"),
    ("windsurf_proxy", "Guardian自建代理", "Guardian在CFW未启动时自动启动fallback proxy占据443"),
    ("python", "Python进程", "cfw_relay.py或windsurf_proxy.py"),
    ("pythonw", "Python后台进程", "cfw_relay.py后台运行"),
    ("httpd", "Apache HTTP", "IIS/Apache占用443"),
    ("nginx", "Nginx", "Nginx占用443"),
]
SCHTASK_NAMES = [
    "CFW_Relay", "FRP Client", "FRP Client Laptop",
    "WindsurfGuardian", "ClipboardGuardian", "DaoRemoteAgent",
    "WindsurfPortProxy", "DesktopCast",
]


def run(cmd, timeout=15):
    """执行命令并返回stdout"""
    try:
        r = subprocess.run(
            cmd, capture_output=True, timeout=timeout,
            encoding="utf-8", errors="ignore", shell=isinstance(cmd, str)
        )
        return r.stdout.strip()
    except Exception as e:
        return f"[ERROR] {e}"


def check_port(host, port):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        r = s.connect_ex((host, port))
        s.close()
        return r == 0
    except Exception:
        return False


def get_port_pid(port):
    """获取监听指定端口的PID"""
    out = run("netstat -ano -p TCP")
    for line in out.split("\n"):
        if f"127.0.0.1:{port}" in line and "LISTEN" in line:
            parts = line.split()
            return int(parts[-1])
        if f"0.0.0.0:{port}" in line and "LISTEN" in line:
            parts = line.split()
            return int(parts[-1])
    return None


def get_process_name(pid):
    """通过PID获取进程名"""
    if not pid:
        return None
    out = run(f'tasklist /fi "PID eq {pid}" /fo csv /nh')
    if out and '"' in out:
        return out.strip('"').split('"')[0]
    return None


def is_cfw_process(pname):
    if not pname:
        return False
    return any(n.lower() in pname.lower() for n in CFW_NAMES)


# ═══════════════════════════════════════════════════
# 八卦诊断
# ═══════════════════════════════════════════════════

def diag_qian():
    """☰乾·架构: CFW二进制+版本"""
    results = []
    # 查找所有CFW可执行文件
    search_dirs = [
        r"D:\Desktop", r"D:\浏览器下载",
        os.path.expanduser("~\\Desktop"),
    ]
    found = []
    for d in search_dirs:
        if os.path.isdir(d):
            for f in os.listdir(d):
                if "CodeFreeWindsurf" in f and f.endswith(".exe"):
                    fp = os.path.join(d, f)
                    sz = os.path.getsize(fp) / 1024 / 1024
                    mt = datetime.fromtimestamp(os.path.getmtime(fp)).strftime("%Y-%m-%d %H:%M")
                    found.append((fp, sz, mt))
        # 递归搜索浏览器下载
        if d == r"D:\浏览器下载" and os.path.isdir(d):
            for root, dirs, files in os.walk(d):
                for f in files:
                    if "CodeFreeWindsurf" in f and f.endswith(".exe"):
                        fp = os.path.join(root, f)
                        if fp not in [x[0] for x in found]:
                            sz = os.path.getsize(fp) / 1024 / 1024
                            mt = datetime.fromtimestamp(os.path.getmtime(fp)).strftime("%Y-%m-%d %H:%M")
                            found.append((fp, sz, mt))
                if len(found) > 10:
                    break

    if found:
        for fp, sz, mt in found:
            results.append(("✅", f"CFW: {os.path.basename(fp)} ({sz:.1f}MB, {mt})", fp))
    else:
        results.append(("❌", "未找到CodeFreeWindsurf可执行文件!", None))

    # 检查正在运行的CFW进程
    pid = get_port_pid(443)
    pname = get_process_name(pid)
    if pid and is_cfw_process(pname):
        results.append(("✅", f"CFW运行中: {pname} (PID {pid}) on :443", None))
    elif pid:
        results.append(("⚠️", f"443端口被占用: {pname} (PID {pid}) — 非CFW!", None))
    else:
        results.append(("❌", "443端口无监听 — CFW未运行!", None))

    return "☰乾·架构", results


def diag_kun():
    """☷坤·端口: 所有关键端口扫描"""
    results = []
    for port, desc in CRITICAL_PORTS.items():
        pid = get_port_pid(port)
        if pid:
            pname = get_process_name(pid)
            results.append(("✅", f":{port} {desc} → {pname} (PID {pid})", None))
        else:
            if port == 443:
                results.append(("❌", f":{port} {desc} — 未监听!", None))
            else:
                results.append(("⚪", f":{port} {desc} — 未监听", None))
    return "☷坤·端口", results


def diag_li():
    """☲离·视觉: hosts/证书/settings"""
    results = []

    # hosts
    try:
        with open(HOSTS_PATH, "r") as f:
            hosts = f.read()
        for entry in HOSTS_ENTRIES:
            domain = entry.split()[-1]
            if domain in hosts:
                results.append(("✅", f"hosts: {domain} → 127.0.0.1", None))
            else:
                results.append(("❌", f"hosts: {domain} 缺失!", None))
    except Exception as e:
        results.append(("❌", f"hosts读取失败: {e}", None))

    # 证书
    out = run(f"certutil -verifystore Root {CERT_THUMBPRINT}")
    if "成功" in out or "Succeeded" in out.lower() or "CertUtil" in out:
        results.append(("✅", f"TLS证书已信任 (Thumbprint: {CERT_THUMBPRINT[:16]}...)", None))
    else:
        results.append(("⚠️", "TLS证书状态不确定", None))

    # SSL_CERT_FILE
    ssl_cert = os.environ.get("SSL_CERT_FILE", "")
    if ssl_cert and os.path.isfile(ssl_cert):
        results.append(("✅", f"SSL_CERT_FILE: {ssl_cert}", None))
    elif ssl_cert:
        results.append(("⚠️", f"SSL_CERT_FILE设置但文件不存在: {ssl_cert}", None))
    else:
        results.append(("⚪", "SSL_CERT_FILE: 未设置", None))

    # settings.json
    settings_path = os.path.expandvars(r"%APPDATA%\Windsurf\User\settings.json")
    if os.path.isfile(settings_path):
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                s = json.load(f)
            if s.get("http.proxyStrictSSL") == False:
                results.append(("✅", "settings: proxyStrictSSL=false", None))
            else:
                results.append(("❌", "settings: proxyStrictSSL未关闭!", None))
        except Exception:
            results.append(("⚠️", "settings.json解析错误", None))
    else:
        results.append(("⚠️", "settings.json未找到", None))

    return "☲离·视觉", results


def diag_zhen():
    """☳震·补丁: JS补丁状态"""
    results = []
    js_path = None
    for p in JS_CANDIDATES:
        if os.path.isfile(p):
            js_path = p
            break

    if not js_path:
        results.append(("❌", "workbench.desktop.main.js 未找到!", None))
        return "☳震·补丁", results

    sz = os.path.getsize(js_path) / 1024 / 1024
    results.append(("✅", f"JS文件: {js_path} ({sz:.1f}MB)", None))

    try:
        with open(js_path, "r", encoding="utf-8") as f:
            content = f.read()
        markers = {
            "Pro Ultimate": 'planName:"Pro Ultimate"',
            "Enterprise": 'impersonateTier="ENTERPRISE_SAAS"',
            "isEnterprise": "this.isEnterprise=!0",
            "hasCapacity": "U5e=Z=>!0",
            "browserEnabled": "browserEnabled:!0",
        }
        all_ok = True
        for name, marker in markers.items():
            if marker in content:
                results.append(("✅", f"补丁{name}: 已生效", None))
            else:
                results.append(("❌", f"补丁{name}: 未生效!", None))
                all_ok = False
        if not all_ok:
            results.append(("💡", "运行: python patch_windsurf.py 修复补丁", None))
    except Exception as e:
        results.append(("❌", f"JS文件读取失败: {e}", None))

    return "☳震·补丁", results


def diag_xun():
    """☴巽·网络: portproxy/FRP/连通性"""
    results = []

    # portproxy
    out = run("netsh interface portproxy show v4tov4")
    if out.strip():
        for line in out.strip().split("\n"):
            if line.strip() and not line.startswith("-") and "Listen" not in line:
                results.append(("✅", f"portproxy: {line.strip()}", None))
    else:
        results.append(("⚪", "portproxy: 无规则 (本机模式,不对外共享)", None))

    # FRP
    frpc_pids = []
    out = run('tasklist /fi "IMAGENAME eq frpc.exe" /fo csv /nh')
    for line in out.split("\n"):
        if "frpc" in line.lower():
            frpc_pids.append(line.strip())
    if frpc_pids:
        results.append(("✅", f"FRP客户端: {len(frpc_pids)}个frpc进程运行中", None))
    else:
        results.append(("⚪", "FRP客户端: 未运行", None))

    # 连通性: CFW后端
    if check_port("127.0.0.1", 443):
        results.append(("✅", "CFW代理: 127.0.0.1:443 可达", None))
    else:
        results.append(("❌", "CFW代理: 127.0.0.1:443 不可达!", None))

    return "☴巽·网络", results


def diag_kan():
    """☵坎·冲突: 443端口竞争者分析"""
    results = []
    pid443 = get_port_pid(443)

    if not pid443:
        results.append(("❌", "443无监听 — CFW未启动", None))
    else:
        pname = get_process_name(pid443)
        if is_cfw_process(pname):
            results.append(("✅", f"443被CFW正确占用: {pname} (PID {pid443})", None))
        else:
            results.append(("🔴", f"443被非CFW进程占用: {pname} (PID {pid443}) — 这是端口冲突根因!", None))

    # 扫描所有可能的443竞争者
    results.append(("📋", "=== 443端口潜在竞争者扫描 ===", None))

    # frpmgr服务
    out = run('sc query frpmgr_6caf8add47e1dfc1862ab4e86162dc1e')
    if "RUNNING" in out:
        results.append(("🔴", "frpmgr服务: 运行中! 可能竞争443", None))
    elif "STOPPED" in out:
        # 检查启动类型
        out2 = run('sc qc frpmgr_6caf8add47e1dfc1862ab4e86162dc1e')
        if "AUTO_START" in out2:
            results.append(("⚠️", "frpmgr服务: 已停止但Auto启动 — 重启后可能抢占!", None))
        else:
            results.append(("✅", "frpmgr服务: 已停止, Manual启动", None))
    else:
        results.append(("✅", "frpmgr服务: 不存在或已禁用", None))

    # Guardian fallback proxy
    out = run("tasklist /fo csv /nh")
    python_procs = [l for l in out.split("\n") if "python" in l.lower()]
    if python_procs:
        results.append(("⚪", f"Python进程: {len(python_procs)}个运行中 (含Guardian/Relay等)", None))

    # 计划任务
    results.append(("📋", "=== 开机计划任务 ===", None))
    for tn in SCHTASK_NAMES:
        out = run(f'schtasks /Query /TN "\\{tn}" /FO LIST /V 2>nul')
        if "ERROR" in out or not out.strip():
            continue
        status = "未知"
        trigger = "未知"
        action = "未知"
        for line in out.split("\n"):
            if "状态:" in line or "Status:" in line:
                status = line.split(":")[-1].strip()
            if "触发器:" in line or "Trigger:" in line:
                trigger = line.split(":", 1)[-1].strip()
        is_boot = "系统启动" in out or "Boot" in out
        is_logon = "登陆" in out or "Logon" in out or "登录" in out
        ttype = "BOOT" if is_boot else ("LOGON" if is_logon else "OTHER")
        results.append(("📌", f"{tn}: {status} [{ttype}]", None))

    return "☵坎·冲突", results


def diag_gen():
    """☶艮·Guardian: 守护进程状态"""
    results = []

    guardian_log = Path(__file__).parent / "guardian.log"
    if guardian_log.exists():
        sz = guardian_log.stat().st_size / 1024
        results.append(("✅", f"Guardian日志: {sz:.0f}KB", None))

        # 读取最后20行分析
        with open(guardian_log, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()[-20:]

        proxy_started = False
        port_warnings = 0
        for line in lines:
            if "Self-built proxy started" in line or "Fallback proxy started" in line:
                proxy_started = True
            if "Port 443 not listening" in line:
                port_warnings += 1

        if proxy_started:
            results.append(("⚠️", "Guardian最近启动了fallback proxy — 这是443冲突根因!", None))
        if port_warnings > 0:
            results.append(("⚠️", f"Guardian最近{port_warnings}次检测到443无监听", None))

        # 检查Guardian版本
        for line in lines:
            if "Guardian v" in line:
                ver = line.split("Guardian")[1].split("started")[0].strip()
                results.append(("📌", f"Guardian版本: {ver}", None))
                break
    else:
        results.append(("⚪", "Guardian日志不存在", None))

    # Guardian进程
    out = run("tasklist /fo csv /nh")
    guardian_running = "windsurf_guardian" in out.lower()
    results.append(("✅" if guardian_running else "⚪",
                     f"Guardian进程: {'运行中' if guardian_running else '未运行'}", None))

    return "☶艮·Guardian", results


def diag_dui():
    """☱兑·数据: CFW运行时数据"""
    results = []

    pid443 = get_port_pid(443)
    pname = get_process_name(pid443)

    if pid443 and is_cfw_process(pname):
        # CFW内存
        out = run(f'tasklist /fi "PID eq {pid443}" /fo csv /nh')
        if out:
            parts = out.split(",")
            if len(parts) >= 5:
                mem = parts[4].strip().strip('"').replace(" K", "").replace(",", "")
                try:
                    mem_mb = int(mem) / 1024
                    results.append(("✅", f"CFW内存: {mem_mb:.0f}MB", None))
                except Exception:
                    pass

        # 网络连接数
        out = run(f'netstat -ano | findstr "{pid443}"')
        conns = len([l for l in out.split("\n") if "ESTABLISHED" in l])
        listens = len([l for l in out.split("\n") if "LISTENING" in l])
        results.append(("✅", f"CFW网络: {listens}个监听 + {conns}个活跃连接", None))
    else:
        results.append(("❌", "CFW未运行,无法采集运行时数据", None))

    # Windsurf路径和版本
    for p in JS_CANDIDATES:
        pj = os.path.normpath(os.path.join(os.path.dirname(p), "..", "..", "..", "product.json"))
        if os.path.isfile(pj):
            try:
                with open(pj, "r", encoding="utf-8") as f:
                    d = json.load(f)
                ver = d.get("version", "?")
                name = d.get("nameShort", "?")
                results.append(("✅", f"Windsurf: {name} v{ver}", None))
            except Exception:
                pass
            break

    return "☱兑·数据", results


# ═══════════════════════════════════════════════════
# 修复函数
# ═══════════════════════════════════════════════════

def fix_kill_443():
    """清理443端口非CFW占用者"""
    pid = get_port_pid(443)
    if not pid:
        print("  443端口无占用,无需清理")
        return True
    pname = get_process_name(pid)
    if is_cfw_process(pname):
        print(f"  443被CFW占用({pname} PID {pid}),无需清理")
        return True
    print(f"  杀死443占用者: {pname} (PID {pid})")
    run(f"taskkill /F /PID {pid}")
    time.sleep(1)
    if not get_port_pid(443):
        print("  ✅ 443端口已释放")
        return True
    else:
        print("  ❌ 443端口仍被占用")
        return False


def fix_frpmgr_manual():
    """确保frpmgr服务为Manual"""
    out = run('sc qc frpmgr_6caf8add47e1dfc1862ab4e86162dc1e')
    if "AUTO_START" in out:
        print("  修复frpmgr服务启动类型: Auto → Manual")
        run('sc config frpmgr_6caf8add47e1dfc1862ab4e86162dc1e start= demand')
        print("  ✅ frpmgr已设为Manual")
    else:
        print("  frpmgr已是Manual/Disabled,无需修改")


# ═══════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════

def main():
    do_fix = "--fix" in sys.argv
    kill_only = "--kill443" in sys.argv

    if kill_only:
        print("=== 清理443端口 ===")
        fix_kill_443()
        return

    print()
    print("╔" + "═" * 56 + "╗")
    print("║  CodeFreeWindsurf 伏羲八卦全景诊断 v1.0              ║")
    print("║  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " " * 37 + "║")
    print("╚" + "═" * 56 + "╝")
    print()

    diagnosers = [
        diag_qian, diag_kun, diag_li, diag_zhen,
        diag_xun, diag_kan, diag_gen, diag_dui,
    ]

    total_ok = 0
    total_warn = 0
    total_err = 0

    for diag in diagnosers:
        name, results = diag()
        print(f"━━━ {name} ━━━")
        for status, msg, detail in results:
            print(f"  {status} {msg}")
            if status == "✅":
                total_ok += 1
            elif status in ("⚠️", "⚪"):
                total_warn += 1
            elif status in ("❌", "🔴"):
                total_err += 1
        print()

    # 评分
    total = total_ok + total_warn + total_err
    score = total_ok / max(total, 1) * 100
    print("━━━ 总评 ━━━")
    print(f"  ✅ {total_ok}项正常  ⚠️ {total_warn}项警告  ❌ {total_err}项异常")
    print(f"  健康度: {score:.0f}%")

    if total_err == 0:
        print("  🎉 系统完全正常!")
    else:
        print(f"  💡 发现{total_err}个问题" + ("，使用 --fix 自动修复" if not do_fix else ""))

    # 自动修复
    if do_fix and total_err > 0:
        print()
        print("━━━ 自动修复 ━━━")
        fix_kill_443()
        fix_frpmgr_manual()
        print()
        print("  修复完成！请运行 →启动CFW.cmd 启动CFW")

    print()


if __name__ == "__main__":
    main()
