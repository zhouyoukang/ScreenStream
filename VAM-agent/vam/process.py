"""
VaM 服务进程管理 — VaM进程启动/停止/状态检测

Voxta服务管理已迁移至 voxta/process.py
"""
import socket
import subprocess
import time
import urllib.request

from .config import VAM_CONFIG


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


def check_process(name: str) -> bool:
    """检查进程是否运行中"""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {name}"],
            capture_output=True, timeout=10
        )
        stdout = result.stdout.decode("gbk", errors="ignore")
        return name.lower() in stdout.lower()
    except Exception:
        return False


def get_all_status() -> dict:
    """获取VaM服务状态"""
    status = {}

    # VaM进程
    vam_running = check_process("VaM.exe")
    status["vam"] = {
        "name": "VaM",
        "running": vam_running,
        "type": "process",
    }

    return status


def start_service(service_key: str, wait: bool = True) -> tuple:
    """启动VaM服务, 返回 (成功, 消息)"""
    if service_key == "vam":
        exe = str(VAM_CONFIG.VAM_EXE)
        if not VAM_CONFIG.VAM_EXE.exists():
            return False, f"VaM not found: {exe}"
        subprocess.Popen([exe], cwd=str(VAM_CONFIG.VAM_EXE.parent))
    elif service_key == "vambox":
        exe = str(VAM_CONFIG.VAMBOX_EXE)
        if not VAM_CONFIG.VAMBOX_EXE.exists():
            return False, f"VaM Box not found: {exe}"
        subprocess.Popen(
            [exe], cwd=str(VAM_CONFIG.VAMBOX_EXE.parent),
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
    else:
        return False, f"Unknown VaM service: {service_key} (Voxta服务请用 voxta.process)"

    if wait:
        time.sleep(3)
    return True, f"{service_key} starting"


def stop_process(name: str) -> tuple:
    """停止进程"""
    try:
        result = subprocess.run(
            ["taskkill", "/IM", name, "/F"],
            capture_output=True, timeout=10
        )
        return result.returncode == 0, result.stdout.decode("gbk", errors="ignore").strip()
    except Exception as e:
        return False, str(e)


def wait_for_vam(timeout: int = 60) -> bool:
    """等待VaM进程启动"""
    start = time.time()
    while time.time() - start < timeout:
        if check_process("VaM.exe"):
            return True
        time.sleep(2)
    return False
