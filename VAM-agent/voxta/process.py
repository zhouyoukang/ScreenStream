"""
Voxta 服务进程管理 — Voxta/EdgeTTS/TextGen 启动/停止/状态检测
"""
import socket
import subprocess
import sys
import time
import urllib.request

from .config import VOXTA_CONFIG


# ── 通用工具 ──

def check_port(port: int, host: str = "127.0.0.1", timeout: float = 2) -> bool:
    """检查端口是否开放"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            return s.connect_ex((host, port)) == 0
    except Exception:
        return False


def check_http(url: str, timeout: float = 5) -> tuple:
    """检查HTTP端点, 返回 (是否成功, 响应内容)"""
    try:
        req = urllib.request.urlopen(url, timeout=timeout)
        return True, req.read()[:500].decode("utf-8", errors="ignore")
    except Exception as e:
        return False, str(e)


# ── 服务状态 ──

def get_all_status() -> dict:
    """获取所有Voxta相关服务状态"""
    status = {}
    for key, svc in VOXTA_CONFIG.SERVICES.items():
        port_ok = check_port(svc["port"])
        http_ok = False
        if port_ok:
            http_ok, _ = check_http(f"http://localhost:{svc['port']}{svc['health']}")
        status[key] = {
            "name": svc["name"],
            "port": svc["port"],
            "running": port_ok,
            "http_ok": http_ok,
            "type": "service",
        }
    return status


# ── 服务启动 ──

def start_service(service_key: str, wait: bool = True) -> tuple:
    """启动指定Voxta相关服务, 返回 (成功, 消息)"""
    if service_key == "voxta":
        exe = str(VOXTA_CONFIG.VOXTA_EXE)
        cwd = str(VOXTA_CONFIG.VOXTA_EXE.parent)
        if not VOXTA_CONFIG.VOXTA_EXE.exists():
            return False, f"Voxta not found: {exe}"
        subprocess.Popen([exe], cwd=cwd, creationflags=subprocess.CREATE_NEW_CONSOLE)

    elif service_key == "edgetts":
        path = str(VOXTA_CONFIG.EDGETTS_SCRIPT)
        if not VOXTA_CONFIG.EDGETTS_SCRIPT.exists():
            return False, f"EdgeTTS script not found: {path}"
        subprocess.Popen(
            [sys.executable, path],
            cwd=str(VOXTA_CONFIG.EDGETTS_DIR),
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )

    elif service_key == "textgen":
        bat = str(VOXTA_CONFIG.TEXTGEN_BAT)
        if not VOXTA_CONFIG.TEXTGEN_BAT.exists():
            return False, f"TextGen script not found: {bat}"
        subprocess.Popen(
            ["cmd", "/c", bat],
            cwd=str(VOXTA_CONFIG.TEXTGEN_DIR),
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )

    else:
        return False, f"Unknown Voxta service: {service_key}"

    if wait:
        time.sleep(3)

    svc_info = VOXTA_CONFIG.SERVICES.get(service_key, {})
    port = svc_info.get("port", "N/A")
    return True, f"{service_key} starting (port: {port})"


def start_full_stack(include_textgen: bool = False) -> list:
    """启动完整Voxta服务栈: EdgeTTS → Voxta → (TextGen)"""
    results = []

    for svc in ["edgetts", "voxta"]:
        ok, msg = start_service(svc, wait=True)
        results.append({"service": svc, "ok": ok, "msg": msg})
        time.sleep(3)

    if include_textgen:
        ok, msg = start_service("textgen", wait=True)
        results.append({"service": "textgen", "ok": ok, "msg": msg})
        time.sleep(5)

    return results


def wait_for_service(service_key: str, timeout: int = 30) -> bool:
    """等待Voxta相关服务就绪"""
    svc = VOXTA_CONFIG.SERVICES.get(service_key)
    if not svc:
        return False

    start = time.time()
    while time.time() - start < timeout:
        if check_port(svc["port"]):
            ok, _ = check_http(f"http://localhost:{svc['port']}{svc['health']}")
            if ok:
                return True
        time.sleep(1)
    return False
