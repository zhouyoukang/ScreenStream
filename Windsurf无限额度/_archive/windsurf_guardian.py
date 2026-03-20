"""
Windsurf Guardian v1.0 — 全自动守护
====================================
功能:
1. 监控 workbench.desktop.main.js 文件变化 → 自动重新patch
2. 监控代理进程存活 → 自动重启/failover
3. 开机自启注册(schtask)
4. 健康检查报告

用法:
  python windsurf_guardian.py              # 前台运行守护
  python windsurf_guardian.py --check      # 一次性健康检查
  python windsurf_guardian.py --install    # 注册开机自启计划任务
  python windsurf_guardian.py --uninstall  # 移除计划任务
"""

import sys
import os
import time
import hashlib
import subprocess
import socket
import json
import logging
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent
PATCH_SCRIPT = SCRIPT_DIR / "patch_windsurf.py"
PROXY_SCRIPT = SCRIPT_DIR / "windsurf_proxy.py"
CERT_PEM = SCRIPT_DIR / "windsurf_proxy_ca.pem"
STATE_FILE = SCRIPT_DIR / ".guardian_state.json"
LOG_FILE = SCRIPT_DIR / "guardian.log"

TASK_NAME = "WindsurfGuardian"
CHECK_INTERVAL = 30  # seconds
BOOT_GRACE_PERIOD = 180  # seconds — 开机后3分钟内不自动启动fallback proxy
CFW_PROCESS_NAMES = ["CodeFreeWindsurf", "CFW"]  # CFW可能的进程名前缀

# Windsurf JS 候选路径
JS_CANDIDATES = [
    r"D:\Windsurf\resources\app\out\vs\workbench\workbench.desktop.main.js",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Windsurf\resources\app\out\vs\workbench\workbench.desktop.main.js"),
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ]
)
log = logging.getLogger("guardian")


def find_js():
    for p in JS_CANDIDATES:
        if os.path.isfile(p):
            return p
    return None


def file_hash(path):
    if not os.path.isfile(path):
        return None
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def is_patched(js_path):
    """快速检查补丁状态(不导入patch_windsurf)"""
    try:
        with open(js_path, "r", encoding="utf-8") as f:
            content = f.read()
        markers = [
            "U5e=Z=>!0,W5e=",
            "if(!1)return",
            'planName:"Pro Ultimate"',
            "this.isEnterprise=!0,this.hasPaidFeatures=!0",
            'this.impersonateTier="ENTERPRISE_SAAS"',
        ]
        return all(m in content for m in markers)
    except Exception:
        return False


def apply_patch(js_path):
    """调用 patch_windsurf.py 应用补丁"""
    log.info(f"Applying patches to {js_path}")
    try:
        result = subprocess.run(
            [sys.executable, str(PATCH_SCRIPT), js_path],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            log.info("Patch applied successfully")
            for line in result.stdout.strip().split("\n"):
                if line.startswith("[✓]") or line.startswith("[=]"):
                    log.info(f"  {line}")
            return True
        else:
            log.error(f"Patch failed: {result.stderr}")
            return False
    except Exception as e:
        log.error(f"Patch error: {e}")
        return False


def check_port(host, port):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        r = s.connect_ex((host, port))
        s.close()
        return r == 0
    except Exception:
        return False


def is_cfw_running():
    """检测CFW进程是否在运行(不依赖端口)"""
    try:
        result = subprocess.run(
            ["tasklist", "/fo", "csv", "/nh"],
            capture_output=True, timeout=10, encoding="utf-8", errors="ignore"
        )
        for line in result.stdout.split("\n"):
            for name in CFW_PROCESS_NAMES:
                if name.lower() in line.lower():
                    return True
    except Exception:
        pass
    return False


def kill_port_occupant(port=443):
    """杀死占用指定端口的进程(仅杀自建代理,不杀CFW)"""
    try:
        result = subprocess.run(
            ["netstat", "-ano", "-p", "TCP"],
            capture_output=True, timeout=10, encoding="utf-8", errors="ignore"
        )
        for line in result.stdout.split("\n"):
            if f"127.0.0.1:{port}" in line and "LISTEN" in line:
                parts = line.split()
                pid = int(parts[-1])
                # 检查是不是CFW — 不杀CFW
                try:
                    proc = subprocess.run(
                        ["tasklist", "/fi", f"PID eq {pid}", "/fo", "csv", "/nh"],
                        capture_output=True, timeout=5, encoding="utf-8", errors="ignore"
                    )
                    pname = proc.stdout.strip()
                    if any(n.lower() in pname.lower() for n in CFW_PROCESS_NAMES):
                        log.info(f"Port {port} occupied by CFW (PID {pid}), not killing")
                        return False
                except Exception:
                    pass
                log.warning(f"Killing port {port} occupant PID {pid}")
                subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, timeout=10)
                time.sleep(1)
                return True
    except Exception as e:
        log.error(f"kill_port_occupant error: {e}")
    return False


def get_proxy_info():
    """检测代理状态: 返回 (type, pid, port)"""
    info = {"type": None, "pid": None, "port": None}
    try:
        result = subprocess.run(
            ["netstat", "-ano", "-p", "TCP"],
            capture_output=True, timeout=10, encoding="utf-8", errors="ignore"
        )
        for line in result.stdout.split("\n"):
            if "127.0.0.1:443" in line and "LISTEN" in line:
                parts = line.split()
                pid = int(parts[-1])
                info["port"] = 443
                info["pid"] = pid
                # 识别进程类型
                try:
                    proc = subprocess.run(
                        ["tasklist", "/fi", f"PID eq {pid}", "/fo", "csv", "/nh"],
                        capture_output=True, timeout=5, encoding="utf-8", errors="ignore"
                    )
                    name = proc.stdout.strip().strip('"').split('"')[0]
                    if "CodeFreeWindsurf" in name:
                        info["type"] = "CFW"
                    elif "python" in name.lower():
                        info["type"] = "self-built"
                    else:
                        info["type"] = name
                except Exception:
                    info["type"] = "unknown"
                break
    except Exception:
        pass
    return info


def detect_version(js_path):
    product_json = os.path.normpath(os.path.join(os.path.dirname(js_path), "..", "..", "..", "product.json"))
    if os.path.isfile(product_json):
        try:
            with open(product_json, "r", encoding="utf-8") as f:
                return json.load(f).get("version", "unknown")
        except Exception:
            pass
    return "unknown"


def health_check():
    """全面健康检查"""
    issues = []
    ok_items = []

    # 1. JS文件 & Patch
    js_path = find_js()
    if js_path:
        ver = detect_version(js_path)
        if is_patched(js_path):
            ok_items.append(f"Patch: v{ver} 已生效")
        else:
            issues.append(f"Patch: v{ver} 未生效!")
    else:
        issues.append("JS文件: 未找到workbench.desktop.main.js")

    # 2. 代理
    proxy = get_proxy_info()
    if proxy["type"]:
        ok_items.append(f"Proxy: {proxy['type']} (PID {proxy['pid']}) on :{proxy['port']}")
    elif check_port("127.0.0.1", 443):
        ok_items.append("Proxy: :443 listening (process unknown)")
    else:
        issues.append("Proxy: 443端口无监听!")

    # 3. 证书
    if CERT_PEM.exists():
        ok_items.append(f"Cert: {CERT_PEM.name} exists")
    else:
        issues.append(f"Cert: {CERT_PEM.name} missing!")

    ssl_cert = os.environ.get("SSL_CERT_FILE", "")
    if ssl_cert and os.path.isfile(ssl_cert):
        ok_items.append(f"SSL_CERT_FILE: {ssl_cert}")
    else:
        issues.append(f"SSL_CERT_FILE: not set or file missing")

    # 4. hosts
    hosts_path = r"C:\Windows\System32\drivers\etc\hosts"
    try:
        with open(hosts_path, "r") as f:
            hosts = f.read()
        domains = ["server.self-serve.windsurf.com", "server.codeium.com"]
        for d in domains:
            if d in hosts:
                ok_items.append(f"Hosts: {d} ✓")
            else:
                issues.append(f"Hosts: {d} missing!")
    except Exception as e:
        issues.append(f"Hosts: read error: {e}")

    # 5. settings.json
    settings_path = os.path.expandvars(r"%APPDATA%\Windsurf\User\settings.json")
    if os.path.isfile(settings_path):
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                s = json.load(f)
            if s.get("http.proxyStrictSSL") == False:
                ok_items.append("Settings: proxyStrictSSL=false")
            else:
                issues.append("Settings: proxyStrictSSL != false")
        except Exception:
            issues.append("Settings: parse error")
    else:
        issues.append("Settings: not found")

    # Report
    print("\n" + "=" * 50)
    print("  Windsurf Guardian Health Check")
    print("  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 50)
    for item in ok_items:
        print(f"  ✅ {item}")
    for issue in issues:
        print(f"  ❌ {issue}")
    print(f"\n  Score: {len(ok_items)}/{len(ok_items)+len(issues)}")
    if not issues:
        print("  🎉 All systems nominal!")
    print("=" * 50)
    return len(issues) == 0


def install_task():
    """注册Windows计划任务(开机自启)"""
    python = sys.executable
    script = str(Path(__file__).resolve())
    cmd = f'schtasks /create /tn "{TASK_NAME}" /tr "\"{python}\" \"{script}\"" /sc onlogon /rl highest /f'
    log.info(f"Installing scheduled task: {TASK_NAME}")
    result = subprocess.run(cmd, shell=True, capture_output=True, encoding="gbk", errors="ignore")
    if result.returncode == 0:
        log.info(f"✅ Task '{TASK_NAME}' installed (runs at logon)")
        print(f"✅ 计划任务 '{TASK_NAME}' 已注册 (用户登录时自动启动)")
    else:
        log.error(f"Failed: {result.stderr}")
        print(f"❌ 注册失败 (需管理员权限): {result.stderr}")


def uninstall_task():
    """移除计划任务"""
    cmd = f'schtasks /delete /tn "{TASK_NAME}" /f'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"✅ 计划任务 '{TASK_NAME}' 已移除")
    else:
        print(f"❌ 移除失败: {result.stderr}")


def guardian_loop():
    """主守护循环"""
    log.info("=" * 50)
    log.info("Windsurf Guardian v2.0 started")
    log.info("=" * 50)

    state = load_state()
    js_path = find_js()

    if not js_path:
        log.error("workbench.desktop.main.js not found, exiting")
        return

    # 初始状态
    current_hash = file_hash(js_path)
    state["last_hash"] = state.get("last_hash", current_hash)
    state["last_check"] = datetime.now().isoformat()

    if not is_patched(js_path):
        log.warning("Patches not applied, applying now...")
        apply_patch(js_path)
        current_hash = file_hash(js_path)
        state["last_hash"] = current_hash
        state["last_patch"] = datetime.now().isoformat()

    save_state(state)
    log.info(f"Monitoring: {js_path}")
    log.info(f"Hash: {current_hash}")
    log.info(f"Check interval: {CHECK_INTERVAL}s")

    consecutive_errors = 0
    boot_time = time.time()
    cfw_was_seen = False  # CFW是否曾经在线过

    while True:
        try:
            time.sleep(CHECK_INTERVAL)
            uptime = time.time() - boot_time

            # 1. 检查JS文件是否变化(Windsurf更新)
            new_hash = file_hash(js_path)
            if new_hash and new_hash != state.get("last_hash"):
                ver = detect_version(js_path)
                log.warning(f"⚡ JS file changed! Windsurf updated to v{ver}")
                log.warning(f"  Old hash: {state.get('last_hash')}")
                log.warning(f"  New hash: {new_hash}")

                # 等待Windsurf完成写入
                time.sleep(5)
                new_hash = file_hash(js_path)

                if not is_patched(js_path):
                    log.info("Reapplying patches...")
                    if apply_patch(js_path):
                        state["last_patch"] = datetime.now().isoformat()
                        state["last_version"] = ver
                        log.info(f"✅ Patches reapplied for v{ver}")
                    else:
                        log.error("❌ Patch reapply failed!")
                else:
                    log.info("Patches still intact after update")

                state["last_hash"] = file_hash(js_path)
                state["last_check"] = datetime.now().isoformat()
                save_state(state)

            # 2. 检查代理存活 — 智能决策
            port_open = check_port("127.0.0.1", 443)
            cfw_alive = is_cfw_running()

            if cfw_alive:
                cfw_was_seen = True

            if port_open:
                state.pop("proxy_down_since", None)
            elif not port_open:
                state["proxy_down_since"] = state.get("proxy_down_since", datetime.now().isoformat())

                # 决策：是否启动fallback proxy
                if uptime < BOOT_GRACE_PERIOD and not cfw_was_seen:
                    # 开机静默期：CFW还没启动过，不抢占443
                    if int(uptime) % 60 < CHECK_INTERVAL:  # 每分钟只提醒一次
                        log.info(f"⏳ Boot grace period ({int(BOOT_GRACE_PERIOD - uptime)}s remaining), waiting for CFW...")
                elif cfw_was_seen and not cfw_alive:
                    # CFW曾经在线但现在崩溃了 → 启动fallback
                    log.warning("⚠ CFW was running but crashed! Starting fallback proxy...")
                    if PROXY_SCRIPT.exists() and CERT_PEM.exists():
                        subprocess.Popen(
                            [sys.executable, str(PROXY_SCRIPT)],
                            cwd=str(SCRIPT_DIR),
                            creationflags=subprocess.CREATE_NO_WINDOW
                        )
                        time.sleep(3)
                        if check_port("127.0.0.1", 443):
                            log.info("✅ Fallback proxy started on :443")
                            state.pop("proxy_down_since", None)
                        else:
                            log.error("❌ Fallback proxy failed to start")
                else:
                    # 静默期过了但CFW从未出现 → 记录但不抢占
                    log.warning("⚠ Port 443 not listening, CFW not detected. Start CFW manually.")

            consecutive_errors = 0

        except KeyboardInterrupt:
            log.info("Guardian stopped by user")
            break
        except Exception as e:
            consecutive_errors += 1
            log.error(f"Error in guardian loop: {e}")
            if consecutive_errors > 10:
                log.error("Too many consecutive errors, exiting")
                break
            time.sleep(10)

    save_state(state)


def main():
    if "--check" in sys.argv:
        health_check()
    elif "--install" in sys.argv:
        install_task()
    elif "--uninstall" in sys.argv:
        uninstall_task()
    elif "--patch-now" in sys.argv:
        js_path = find_js()
        if js_path:
            if not is_patched(js_path):
                apply_patch(js_path)
            else:
                print("✅ Already patched")
        else:
            print("❌ JS file not found")
    else:
        guardian_loop()


if __name__ == "__main__":
    main()
