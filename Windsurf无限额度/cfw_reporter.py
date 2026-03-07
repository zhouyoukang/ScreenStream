#!/usr/bin/env python3
"""
CFW 状态上报器 v1.0
===================
运行于台式机，定期提取 CodeFreeWindsurf 运行时状态并推送到阿里云授权中枢。

功能:
  1. 从 CFW 进程内存提取运行时状态 (proxy_mode/tokens/requests/cost等)
  2. 每60秒推送到阿里云中枢 POST /hub/api/cfw-state
  3. 检查 CFW 进程存活状态
  4. 支持 --once 单次执行模式

部署: 
  - 作为 schtask 运行: schtasks /create /tn "CFW_Reporter" /tr "python cfw_reporter.py" /sc onlogon /ru SYSTEM
  - 或与 windsurf_guardian.py 集成

依赖: Python 3.8+ (stdlib only, Windows)
"""

import ctypes
import ctypes.wintypes as wt
import json
import subprocess
import time
import sys
import os
import urllib.request
import ssl
from datetime import datetime, timezone

# ==================== 配置 ====================

HUB_URL = os.environ.get("HUB_URL", "https://aiotvr.xyz/hub/api/cfw-state")
REPORT_INTERVAL = int(os.environ.get("REPORT_INTERVAL", "60"))  # 秒
VERBOSE = "--verbose" in sys.argv or "-v" in sys.argv

# ==================== Windows API ====================

k32 = ctypes.WinDLL("kernel32", use_last_error=True)

class MBI(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_ulonglong),
        ("AllocationBase", ctypes.c_ulonglong),
        ("AllocationProtect", wt.DWORD),
        ("_pad1", wt.DWORD),
        ("RegionSize", ctypes.c_ulonglong),
        ("State", wt.DWORD),
        ("Protect", wt.DWORD),
        ("Type", wt.DWORD),
        ("_pad2", wt.DWORD),
    ]

PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400
MEM_COMMIT = 0x1000
READABLE = {0x02, 0x04, 0x08, 0x20, 0x40, 0x80}


# ==================== CFW 进程发现 ====================

def find_cfw_pid():
    """查找 CodeFreeWindsurf 进程 PID"""
    try:
        r = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq CodeFreeWindsurf*", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=10
        )
        for line in r.stdout.strip().split("\n"):
            if "CodeFree" in line:
                parts = line.strip('"').split('","')
                return int(parts[1])
    except Exception:
        pass
    return None


def check_cfw_port():
    """检查 CFW 是否在 443 端口监听"""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        result = s.connect_ex(("127.0.0.1", 443))
        s.close()
        return result == 0
    except Exception:
        return False


# ==================== 内存提取 ====================

def extract_cfw_state(pid):
    """从 CFW 进程内存提取运行时状态 JSON"""
    h = k32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
    if not h:
        err = ctypes.get_last_error()
        if VERBOSE:
            print(f"  OpenProcess failed: error {err}")
        # 尝试 PROCESS_ALL_ACCESS
        h = k32.OpenProcess(0x1F0FFF, False, pid)
        if not h:
            return None

    mbi = MBI()
    addr = 0
    found_objects = []

    search_keys = [b'"proxy_mode"', b'"active_mappings"', b'"email"']

    while k32.VirtualQueryEx(h, ctypes.c_ulonglong(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
        if (mbi.State == MEM_COMMIT and
            (mbi.Protect & 0xFF) in READABLE and
            0 < mbi.RegionSize < 64 * 1024 * 1024):

            buf = (ctypes.c_char * mbi.RegionSize)()
            nread = ctypes.c_ulonglong(0)

            if k32.ReadProcessMemory(h, ctypes.c_ulonglong(mbi.BaseAddress),
                                     buf, mbi.RegionSize, ctypes.byref(nread)):
                data = bytes(buf[:nread.value])

                for key in search_keys:
                    idx = data.find(key)
                    if idx >= 0:
                        # 向前找 { 开始
                        bstart = data.rfind(b"{", max(0, idx - 1000), idx)
                        if bstart >= 0:
                            depth = 0
                            for i in range(bstart, min(len(data), bstart + 5000)):
                                if data[i:i+1] == b"{":
                                    depth += 1
                                elif data[i:i+1] == b"}":
                                    depth -= 1
                                if depth == 0:
                                    raw = data[bstart:i+1].replace(b"\x00", b"")
                                    try:
                                        obj = json.loads(raw)
                                        if isinstance(obj, dict) and len(obj) > 5:
                                            found_objects.append(obj)
                                    except (json.JSONDecodeError, UnicodeDecodeError):
                                        pass
                                    break

                if found_objects:
                    break  # 找到就停

        next_addr = mbi.BaseAddress + mbi.RegionSize
        if next_addr <= addr or next_addr > 0x7FFFFFFFFFFF:
            break
        addr = next_addr

    k32.CloseHandle(h)

    # 返回字段最多的对象
    if found_objects:
        return max(found_objects, key=lambda x: len(x))
    return None


# ==================== 上报 ====================

def report_state(state):
    """推送 CFW 状态到阿里云中枢"""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    data = json.dumps(state, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        HUB_URL,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            result = json.loads(resp.read())
            return result.get("ok", False)
    except Exception as e:
        if VERBOSE:
            print(f"  Report failed: {e}")
        return False


# ==================== 主循环 ====================

def run_once():
    """单次执行: 提取 + 上报"""
    pid = find_cfw_pid()
    port_ok = check_cfw_port()

    if not pid:
        state = {
            "running": False,
            "proxy_mode": "offline",
            "port_443": port_ok,
        }
        if VERBOSE:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] CFW not running")
        report_state(state)
        return state

    if VERBOSE:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] CFW PID={pid}, port:443={'OK' if port_ok else 'FAIL'}")

    # 提取内存状态
    mem_state = extract_cfw_state(pid)

    if mem_state:
        mem_state["running"] = True
        mem_state["pid"] = pid
        mem_state["port_443"] = port_ok
        if VERBOSE:
            mode = mem_state.get("proxy_mode", "?")
            reqs = mem_state.get("request_count", 0)
            cost = mem_state.get("session_cost", 0)
            print(f"  mode={mode}, requests={reqs}, cost=${cost:.0f}")
    else:
        mem_state = {
            "running": True,
            "pid": pid,
            "proxy_mode": "unknown",
            "port_443": port_ok,
        }
        if VERBOSE:
            print("  Memory extraction failed, reporting basic state")

    ok = report_state(mem_state)
    if VERBOSE:
        print(f"  Reported to hub: {'OK' if ok else 'FAIL'}")

    return mem_state


def main():
    once = "--once" in sys.argv

    print(f"""
  ╔═══════════════════════════════════════╗
  ║  CFW 状态上报器 v1.0                  ║
  ║  台式机 → 阿里云授权中枢              ║
  ╚═══════════════════════════════════════╝

  中枢: {HUB_URL}
  间隔: {REPORT_INTERVAL}s
  模式: {'单次' if once else '持续循环'}
""")

    if once:
        state = run_once()
        print(json.dumps(state, indent=2, ensure_ascii=False))
        return

    # 持续循环
    while True:
        try:
            run_once()
        except Exception as e:
            if VERBOSE:
                print(f"  Error: {e}")
        time.sleep(REPORT_INTERVAL)


if __name__ == "__main__":
    main()
