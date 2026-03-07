"""
网络自愈守护进程 (Network Guardian)
====================================
利用多手机+多SIM卡+单PC+多Agent，实现网络断连自动恢复。

架构：
  Layer 1: 互联网路径冗余 (PC→Internet)
    ├── Path A: 家庭宽带 (以太网/WiFi) — 主链路
    ├── Path B: 手机1 USB共享网络 — 备份1 (最低延迟)
    ├── Path C: 手机2 WiFi热点 — 备份2
    └── Path D: 手机3 WiFi热点 — 备份3 (不同运营商)

  Layer 2: 本地网络弹性 (PC↔手机)
    ├── USB连接 (最可靠，不依赖网络)
    ├── WiFi (同路由器)
    └── ADB over WiFi

  Layer 3: 公网隧道弹性 (Internet→服务)
    ├── Cloudflare Tunnel 自动重启
    └── 进程监控 + 自动恢复

  Layer 4: Agent互监心跳
    ├── PC agent 监控所有手机
    ├── 每部手机监控PC
    └── 故障检测→自动恢复

用法：
  python network_guardian.py                    # 交互式启动
  python network_guardian.py --daemon           # 后台守护模式
  python network_guardian.py --status           # 查看当前状态
  python network_guardian.py --failover usb     # 手动切换到USB共享
  python network_guardian.py --restore          # 恢复主链路

依赖：零外部依赖（纯标准库）
"""

import json, time, os, sys, subprocess, socket, threading, logging, argparse
import ctypes
from datetime import datetime, timedelta
from pathlib import Path
from collections import deque
from http.server import HTTPServer, BaseHTTPRequestHandler

# ============================================================
# 日志
# ============================================================
log = logging.getLogger("guardian")
if not log.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter(
        "%(asctime)s [Guardian] %(levelname)s %(message)s", "%H:%M:%S"))
    log.addHandler(_h)
    log.setLevel(logging.INFO)

# ============================================================
# 配置
# ============================================================
DEFAULT_CONFIG = {
    # 探测目标（多目标共识：>=2个通=网络正常）
    "ping_targets": ["8.8.8.8", "1.1.1.1", "223.5.5.5", "119.29.29.29"],
    "ping_consensus": 2,          # 至少N个目标通过才算网络正常
    "ping_timeout_ms": 2000,      # 单次ping超时
    "check_interval_sec": 5,      # 检测间隔
    "fail_threshold": 3,          # 连续N次失败才触发切换
    "recovery_check_sec": 30,     # 主链路恢复检测间隔
    "cooldown_sec": 60,           # 切换后冷却期（防抖动）

    # ADB路径
    "adb_path": "",  # 空=自动检测

    # 手机设备配置
    "phones": [
        {
            "name": "Samsung S23U",
            "serial": "",           # ADB序列号（空=自动检测首个USB设备）
            "wifi_ip": "",          # WiFi IP（空=自动获取）
            "ss_port": 8084,        # ScreenStream端口
            "tether_method": "usb", # usb | hotspot
            "carrier": "移动",      # 运营商标记
            "priority": 1,          # 越小越优先
            "enabled": True
        }
    ],

    # 网络适配器名称（Windows）
    "adapters": {
        "primary": "",      # 主适配器名（空=自动检测以太网/WiFi）
        "usb_tether": "",   # USB共享网络适配器名（空=自动检测RNDIS）
    },

    # Cloudflare Tunnel
    "tunnel": {
        "enabled": False,
        "command": "cloudflared tunnel --url http://localhost:8080",
        "restart_on_failover": True
    },

    # Agent心跳
    "heartbeat": {
        "enabled": True,
        "port": 9800,              # 心跳HTTP服务端口
        "interval_sec": 10,        # 心跳间隔
        "dead_threshold": 3        # N次无响应判定为死亡
    },

    # 通知
    "notify": {
        "toast": True,             # Windows Toast通知
        "sound": True,             # 系统提示音
        "log_file": "network_guardian.log"
    }
}

CONFIG_PATH = Path(__file__).parent / "network_guardian_config.json"

def load_config():
    """加载配置，不存在则创建默认"""
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                user_cfg = json.load(f)
            # 深度合并
            cfg = DEFAULT_CONFIG.copy()
            for k, v in user_cfg.items():
                if isinstance(v, dict) and k in cfg and isinstance(cfg[k], dict):
                    cfg[k].update(v)
                else:
                    cfg[k] = v
            return cfg
        except Exception as e:
            log.warning(f"配置加载失败，使用默认: {e}")
    return DEFAULT_CONFIG.copy()

def save_config(cfg):
    """保存配置"""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


# ============================================================
# ADB 工具
# ============================================================
_adb_path_cache = None

def _find_adb(cfg_path=""):
    global _adb_path_cache
    if _adb_path_cache:
        return _adb_path_cache

    import shutil
    candidates = [
        cfg_path,
        shutil.which("adb"),
        os.path.join(os.path.dirname(__file__), "android-sdk",
                     "platform-tools", "adb.exe"),
        os.environ.get("ADB_PATH", ""),
    ]
    for p in candidates:
        if p and os.path.isfile(p):
            _adb_path_cache = p
            return p
    return None

def _safe_decode(raw_bytes):
    """安全解码：UTF-8 → GBK → Latin1 回退链"""
    for enc in ("utf-8", "gbk", "cp936", "latin1"):
        try:
            return raw_bytes.decode(enc)
        except (UnicodeDecodeError, AttributeError):
            continue
    return raw_bytes.decode("utf-8", errors="replace")

def adb_run(*args, serial=None, timeout=10, adb_path=""):
    """执行ADB命令，返回(stdout, success)"""
    adb = _find_adb(adb_path)
    if not adb:
        return "", False
    cmd = [adb]
    if serial:
        cmd.extend(["-s", serial])
    cmd.extend(args)
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout,
                           creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        return _safe_decode(r.stdout).strip(), r.returncode == 0
    except Exception as e:
        return str(e), False


# ============================================================
# 网络探测
# ============================================================

def ping_host(host, timeout_ms=2000):
    """Ping单个主机，返回(reachable, latency_ms)"""
    try:
        if os.name == "nt":
            r = subprocess.run(
                ["ping", "-n", "1", "-w", str(timeout_ms), host],
                capture_output=True, timeout=timeout_ms/1000 + 2,
                creationflags=subprocess.CREATE_NO_WINDOW)
            stdout = _safe_decode(r.stdout)
            if r.returncode == 0 and ("TTL=" in stdout or "ttl=" in stdout):
                import re
                m = re.search(r"[=<](\d+)ms", stdout)
                latency = int(m.group(1)) if m else 0
                return True, latency
        else:
            r = subprocess.run(
                ["ping", "-c", "1", "-W", str(timeout_ms // 1000 or 1), host],
                capture_output=True, timeout=timeout_ms/1000 + 2)
            stdout = _safe_decode(r.stdout)
            if r.returncode == 0:
                import re
                m = re.search(r"time=(\d+\.?\d*)", stdout)
                latency = float(m.group(1)) if m else 0
                return True, latency
    except Exception:
        pass
    return False, -1

def tcp_probe(host, port=80, timeout=2):
    """TCP连接探测"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((host, port))
        s.close()
        return True
    except Exception:
        return False

def check_internet(targets, consensus=2, timeout_ms=2000):
    """多目标共识检测互联网连通性。
    返回 (connected: bool, passed: int, total: int, avg_latency_ms: float)"""
    results = []
    for host in targets:
        ok, lat = ping_host(host, timeout_ms)
        results.append((ok, lat))

    passed = sum(1 for ok, _ in results if ok)
    latencies = [lat for ok, lat in results if ok and lat >= 0]
    avg_lat = sum(latencies) / len(latencies) if latencies else -1
    return passed >= consensus, passed, len(targets), avg_lat


# ============================================================
# Windows 网络适配器管理
# ============================================================

def _ps_json(command):
    """执行PowerShell命令并返回JSON结果（处理编码）"""
    try:
        # 用 -OutputEncoding utf8 确保输出UTF-8
        full_cmd = f"[Console]::OutputEncoding=[Text.Encoding]::UTF8; {command}"
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", full_cmd],
            capture_output=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        stdout = _safe_decode(r.stdout)
        if r.returncode == 0 and stdout.strip():
            data = json.loads(stdout.strip())
            if isinstance(data, dict):
                data = [data]
            return data
    except Exception as e:
        log.error(f"PowerShell命令失败: {e}")
    return []

def get_adapters():
    """获取所有网络适配器信息"""
    return _ps_json(
        "Get-NetAdapter | Select-Object Name,InterfaceDescription,"
        "Status,LinkSpeed,ifIndex,MacAddress | ConvertTo-Json -Compress")

def get_adapter_metrics():
    """获取IPv4适配器优先级"""
    return _ps_json(
        "Get-NetIPInterface -AddressFamily IPv4 | "
        "Select-Object ifIndex,InterfaceAlias,InterfaceMetric,ConnectionState | "
        "ConvertTo-Json -Compress")

def find_primary_adapter():
    """自动检测主网络适配器（以太网优先，其次WiFi）"""
    adapters = get_adapters()
    up_adapters = [a for a in adapters if str(a.get("Status", "")).lower() == "up"]

    # 优先：有线以太网
    for a in up_adapters:
        desc = str(a.get("InterfaceDescription", "")).lower()
        name = str(a.get("Name", "")).lower()
        if ("ethernet" in desc or "以太网" in name or "ethernet" in name) \
                and "virtual" not in desc and "tap" not in desc \
                and "wireguard" not in desc:
            return a.get("Name", "")

    # 次选：WiFi/WLAN
    for a in up_adapters:
        desc = str(a.get("InterfaceDescription", "")).lower()
        name = str(a.get("Name", "")).lower()
        if any(kw in name for kw in ("wi-fi", "wifi", "wlan")) \
                or any(kw in desc for kw in ("wi-fi", "wifi", "wireless")):
            if "virtual" not in desc and "direct" not in desc:
                return a.get("Name", "")
    return None

def find_usb_tether_adapter():
    """自动检测USB共享网络适配器（RNDIS/NCM/Remote NDIS）"""
    adapters = get_adapters()
    tether_keywords = ["rndis", "remote ndis", "usb ethernet", "ncm",
                       "android", "基于远程", "共享"]
    for a in adapters:
        desc = str(a.get("InterfaceDescription", "")).lower()
        name = str(a.get("Name", "")).lower()
        combined = desc + " " + name
        if any(kw in combined for kw in tether_keywords):
            return a.get("Name", "")
    return None

def set_adapter_metric(adapter_name, metric):
    """设置适配器优先级（metric越低优先级越高）"""
    try:
        cmd = (f"[Console]::OutputEncoding=[Text.Encoding]::UTF8; "
               f"Set-NetIPInterface -InterfaceAlias '{adapter_name}' "
               f"-InterfaceMetric {metric}")
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        if r.returncode == 0:
            log.info(f"✅ 适配器 '{adapter_name}' metric 设为 {metric}")
            return True
        else:
            log.error(f"设置metric失败: {_safe_decode(r.stderr).strip()}")
    except Exception as e:
        log.error(f"设置metric异常: {e}")
    return False

def enable_adapter(adapter_name):
    """启用网络适配器"""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"Enable-NetAdapter -Name '{adapter_name}' -Confirm:$false"],
            capture_output=True, timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        return r.returncode == 0
    except Exception:
        return False

def disable_adapter(adapter_name):
    """禁用网络适配器"""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"Disable-NetAdapter -Name '{adapter_name}' -Confirm:$false"],
            capture_output=True, timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        return r.returncode == 0
    except Exception:
        return False


# ============================================================
# 手机USB共享网络控制
# ============================================================

def enable_usb_tethering(serial=None, adb_path=""):
    """通过ADB启用手机USB共享网络。
    多种方法尝试，适配不同品牌。"""

    methods = [
        # 方法1: 直接设置USB功能为RNDIS (Android 通用)
        ("shell", "svc", "usb", "setFunctions", "rndis,adb"),
        # 方法2: 通过service call (Android 6-12)
        ("shell", "service", "call", "connectivity", "33", "i32", "1", "s16", "com.android.shell"),
        # 方法3: 通过settings (部分厂商)
        ("shell", "settings", "put", "global", "tether_dun_required", "0"),
    ]

    for method in methods:
        out, ok = adb_run(*method, serial=serial, adb_path=adb_path)
        if ok:
            log.info(f"USB共享网络启用命令成功: {' '.join(method[:3])}")

    # 等待Windows识别新适配器
    time.sleep(5)

    # 验证适配器出现
    tether = find_usb_tether_adapter()
    if tether:
        log.info(f"✅ USB共享网络适配器已出现: {tether}")
        return True, tether
    else:
        # 回退：打开手机的网络共享设置界面
        adb_run("shell", "am", "start", "-n",
                "com.android.settings/.TetherSettings",
                serial=serial, adb_path=adb_path)
        log.warning("⚠️ USB共享适配器未出现，已打开手机共享设置，请手动开启")
        return False, ""

def disable_usb_tethering(serial=None, adb_path=""):
    """关闭USB共享网络"""
    adb_run("shell", "svc", "usb", "setFunctions", "mtp,adb",
            serial=serial, adb_path=adb_path)
    log.info("USB共享网络已关闭")

def enable_wifi_hotspot(serial=None, adb_path=""):
    """通过ADB启用WiFi热点"""
    methods = [
        # Android 12+ (cmd wifi)
        ("shell", "cmd", "wifi", "start-softap", "Guardian_AP", "wpa2", "guardian12345"),
        # 通用：打开热点设置
        ("shell", "am", "start", "-n",
         "com.android.settings/com.android.settings.TetherSettings"),
    ]
    for method in methods:
        out, ok = adb_run(*method, serial=serial, adb_path=adb_path)
        if ok:
            log.info(f"WiFi热点命令成功: {' '.join(method[:4])}")
            return True
    return False

def disable_wifi_hotspot(serial=None, adb_path=""):
    """关闭WiFi热点"""
    adb_run("shell", "cmd", "wifi", "stop-softap",
            serial=serial, adb_path=adb_path)


# ============================================================
# 隧道进程管理
# ============================================================

def is_tunnel_running():
    """检查cloudflared是否在运行"""
    try:
        r = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq cloudflared.exe"],
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW)
        return "cloudflared.exe" in r.stdout
    except Exception:
        return False

def start_tunnel(command):
    """启动隧道进程"""
    try:
        parts = command.split()
        subprocess.Popen(parts,
                         creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log.info(f"✅ 隧道已启动: {command}")
        return True
    except Exception as e:
        log.error(f"隧道启动失败: {e}")
        return False

def stop_tunnel():
    """停止隧道进程"""
    try:
        subprocess.run(["taskkill", "/F", "/IM", "cloudflared.exe"],
                       capture_output=True, timeout=5,
                       creationflags=subprocess.CREATE_NO_WINDOW)
        log.info("隧道已停止")
    except Exception:
        pass


# ============================================================
# Agent心跳服务
# ============================================================

class HeartbeatState:
    """心跳状态管理"""
    def __init__(self):
        self.agents = {}  # name → {last_seen, url, status, latency}
        self.lock = threading.Lock()

    def update(self, name, url, latency_ms=0):
        with self.lock:
            self.agents[name] = {
                "last_seen": time.time(),
                "url": url,
                "status": "alive",
                "latency_ms": latency_ms
            }

    def check_dead(self, threshold_sec=30):
        """检查超时的agent"""
        dead = []
        now = time.time()
        with self.lock:
            for name, info in self.agents.items():
                if now - info["last_seen"] > threshold_sec:
                    if info["status"] != "dead":
                        info["status"] = "dead"
                        dead.append(name)
        return dead

    def get_all(self):
        with self.lock:
            return dict(self.agents)

heartbeat_state = HeartbeatState()


def probe_agent(name, url, timeout=3):
    """探测一个agent是否存活"""
    try:
        from urllib.request import Request, urlopen
        req = Request(url, method="GET")
        start = time.time()
        with urlopen(req, timeout=timeout) as resp:
            latency = (time.time() - start) * 1000
            heartbeat_state.update(name, url, latency)
            return True, latency
    except Exception:
        return False, -1


class HeartbeatHTTPHandler(BaseHTTPRequestHandler):
    """心跳HTTP服务 — 提供状态查询接口"""

    def log_message(self, format, *args):
        pass  # 静默HTTP日志

    def do_GET(self):
        if self.path == "/heartbeat":
            self._json({"ok": True, "role": "pc_guardian",
                        "time": datetime.now().isoformat()})
        elif self.path == "/status":
            self._json(guardian_status())
        elif self.path == "/agents":
            self._json(heartbeat_state.get_all())
        else:
            self._json({"endpoints": ["/heartbeat", "/status", "/agents",
                                       "/failover", "/restore"]})

    def do_POST(self):
        if self.path == "/failover":
            body = self._read_body()
            method = body.get("method", "usb")
            ok = do_failover(method)
            self._json({"ok": ok, "method": method})
        elif self.path == "/restore":
            ok = do_restore()
            self._json({"ok": ok})
        elif self.path == "/heartbeat":
            body = self._read_body()
            name = body.get("name", "unknown")
            url = body.get("url", "")
            heartbeat_state.update(name, url)
            self._json({"ok": True})
        else:
            self._json({"error": "unknown endpoint"}, 404)

    def _json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > 0:
                return json.loads(self.rfile.read(length))
        except Exception:
            pass
        return {}


# ============================================================
# Windows 通知
# ============================================================

def notify(title, message, sound=True):
    """发送Windows通知（balloon tip + 声音）"""
    log.info(f"📢 {title}: {message}")
    if os.name != "nt":
        return

    # 方式: 系统托盘气泡通知（不阻塞，兼容性好）
    try:
        safe_title = title.replace("'", "''")
        safe_msg = message.replace("'", "''")
        ps = (
            f"Add-Type -AssemblyName System.Windows.Forms; "
            f"$n = New-Object System.Windows.Forms.NotifyIcon; "
            f"$n.Icon = [System.Drawing.SystemIcons]::Information; "
            f"$n.Visible = $true; "
            f"$n.ShowBalloonTip(5000, '{safe_title}', '{safe_msg}', "
            f"[System.Windows.Forms.ToolTipIcon]::Warning); "
            f"Start-Sleep -Seconds 6; $n.Dispose()"
        )
        subprocess.Popen(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps],
            creationflags=subprocess.CREATE_NO_WINDOW,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

    if sound:
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except Exception:
            pass


# ============================================================
# 核心状态机
# ============================================================

class GuardianState:
    NORMAL = "normal"             # 主链路正常
    DEGRADED = "degraded"         # 主链路不稳定（偶尔丢包）
    FAILOVER_USB = "failover_usb"   # 已切换到USB共享
    FAILOVER_HOTSPOT = "failover_hotspot"  # 已切换到WiFi热点
    RECOVERING = "recovering"     # 正在恢复主链路
    ERROR = "error"               # 故障状态

class Guardian:
    """网络守护核心"""

    def __init__(self, cfg):
        self.cfg = cfg
        self.state = GuardianState.NORMAL
        self.fail_count = 0
        self.last_failover = 0
        self.last_check = 0
        self.last_latency = 0
        self.active_backup = None  # 当前使用的备份链路信息
        self.history = deque(maxlen=100)  # 事件历史
        self.stats = {
            "total_checks": 0,
            "total_failures": 0,
            "total_failovers": 0,
            "total_recoveries": 0,
            "uptime_start": time.time(),
            "last_failover_time": None,
            "last_recovery_time": None,
        }
        self._stop = threading.Event()
        self._primary_adapter = None
        self._backup_adapter = None

        # 初始化适配器
        self._init_adapters()

    def _init_adapters(self):
        """检测并缓存适配器名称"""
        cfg_adapters = self.cfg.get("adapters", {})
        self._primary_adapter = cfg_adapters.get("primary") or find_primary_adapter()
        self._backup_adapter = cfg_adapters.get("usb_tether") or find_usb_tether_adapter()

        if self._primary_adapter:
            log.info(f"主适配器: {self._primary_adapter}")
        else:
            log.warning("未检测到主网络适配器")

        if self._backup_adapter:
            log.info(f"USB共享适配器: {self._backup_adapter}")
        else:
            log.info("USB共享适配器未就绪（断网时将自动启用）")

    def _log_event(self, event_type, detail=""):
        """记录事件"""
        entry = {
            "time": datetime.now().isoformat(),
            "type": event_type,
            "detail": detail,
            "state": self.state
        }
        self.history.append(entry)
        return entry

    def check_once(self):
        """执行一次网络检测"""
        self.stats["total_checks"] += 1
        targets = self.cfg["ping_targets"]
        consensus = self.cfg["ping_consensus"]
        timeout = self.cfg["ping_timeout_ms"]

        connected, passed, total, avg_lat = check_internet(targets, consensus, timeout)
        self.last_latency = avg_lat
        self.last_check = time.time()

        if connected:
            if self.fail_count > 0:
                log.info(f"网络恢复 ({passed}/{total}, {avg_lat:.0f}ms)")
            self.fail_count = 0
            return True
        else:
            self.fail_count += 1
            self.stats["total_failures"] += 1
            log.warning(f"网络异常 #{self.fail_count} ({passed}/{total} 通过)")
            return False

    def should_failover(self):
        """判断是否应该切换"""
        if self.fail_count < self.cfg["fail_threshold"]:
            return False
        # 冷却期检查
        if time.time() - self.last_failover < self.cfg["cooldown_sec"]:
            return False
        return True

    def do_failover(self, method="auto"):
        """执行链路切换"""
        self.stats["total_failovers"] += 1
        self.stats["last_failover_time"] = datetime.now().isoformat()
        self.last_failover = time.time()

        phones = [p for p in self.cfg.get("phones", []) if p.get("enabled")]
        phones.sort(key=lambda p: p.get("priority", 99))

        if method == "auto":
            # 自动选择：优先USB共享（延迟最低），其次WiFi热点
            for phone in phones:
                if phone.get("tether_method") == "usb":
                    method = "usb"
                    break
            else:
                method = "hotspot"

        if method == "usb":
            return self._failover_usb(phones)
        elif method == "hotspot":
            return self._failover_hotspot(phones)
        else:
            log.error(f"未知切换方法: {method}")
            return False

    def _failover_usb(self, phones):
        """切换到USB共享网络"""
        notify("🔄 网络切换", "主链路断连，切换到USB共享网络...", self.cfg["notify"]["sound"])
        self._log_event("failover_start", "usb")

        for phone in phones:
            serial = phone.get("serial") or None
            adb = self.cfg.get("adb_path", "")

            log.info(f"尝试 {phone['name']} USB共享...")
            ok, adapter_name = enable_usb_tethering(serial=serial, adb_path=adb)

            if ok or adapter_name:
                self._backup_adapter = adapter_name or find_usb_tether_adapter()
                if self._backup_adapter:
                    # 降低备份适配器metric（提高优先级）
                    set_adapter_metric(self._backup_adapter, 5)
                    # 提高主适配器metric（降低优先级）
                    if self._primary_adapter:
                        set_adapter_metric(self._primary_adapter, 9999)

                    # 等待路由生效
                    time.sleep(3)

                    # 验证新链路
                    net_ok, _, _, lat = check_internet(
                        self.cfg["ping_targets"], 1, self.cfg["ping_timeout_ms"])
                    if net_ok:
                        self.state = GuardianState.FAILOVER_USB
                        self.active_backup = {
                            "phone": phone["name"],
                            "adapter": self._backup_adapter,
                            "method": "usb",
                            "since": datetime.now().isoformat()
                        }
                        self._log_event("failover_success",
                                        f"USB via {phone['name']}, {lat:.0f}ms")
                        notify("✅ 网络已恢复",
                               f"通过 {phone['name']} USB共享 ({lat:.0f}ms)",
                               self.cfg["notify"]["sound"])

                        # 重启隧道（如果配置了）
                        if self.cfg.get("tunnel", {}).get("restart_on_failover"):
                            self._restart_tunnel()

                        return True

            log.warning(f"{phone['name']} USB共享失败，尝试下一个...")

        self._log_event("failover_failed", "所有USB共享尝试失败")
        notify("❌ 网络切换失败", "所有手机USB共享均失败", True)
        self.state = GuardianState.ERROR
        return False

    def _failover_hotspot(self, phones):
        """切换到WiFi热点"""
        notify("🔄 网络切换", "主链路断连，尝试连接手机热点...", self.cfg["notify"]["sound"])
        self._log_event("failover_start", "hotspot")

        for phone in phones:
            serial = phone.get("serial") or None
            adb = self.cfg.get("adb_path", "")

            log.info(f"尝试 {phone['name']} WiFi热点...")
            ok = enable_wifi_hotspot(serial=serial, adb_path=adb)

            if ok:
                # 热点需要更长时间启动
                time.sleep(8)
                # 此时Windows需要手动或自动连接热点WiFi
                # 检查网络是否恢复
                net_ok, _, _, lat = check_internet(
                    self.cfg["ping_targets"], 1, self.cfg["ping_timeout_ms"])
                if net_ok:
                    self.state = GuardianState.FAILOVER_HOTSPOT
                    self.active_backup = {
                        "phone": phone["name"],
                        "method": "hotspot",
                        "since": datetime.now().isoformat()
                    }
                    self._log_event("failover_success", f"Hotspot via {phone['name']}")
                    notify("✅ 网络已恢复",
                           f"通过 {phone['name']} 热点",
                           self.cfg["notify"]["sound"])
                    return True

        self.state = GuardianState.ERROR
        self._log_event("failover_failed", "所有热点尝试失败")
        return False

    def do_restore(self):
        """恢复主链路"""
        self._log_event("restore_start", "")

        # 恢复适配器优先级
        if self._primary_adapter:
            set_adapter_metric(self._primary_adapter, 25)  # 恢复正常优先级
        if self._backup_adapter:
            set_adapter_metric(self._backup_adapter, 9999)  # 降低备份优先级

        time.sleep(3)

        # 验证主链路
        net_ok, _, _, lat = check_internet(
            self.cfg["ping_targets"],
            self.cfg["ping_consensus"],
            self.cfg["ping_timeout_ms"])

        if net_ok:
            self.state = GuardianState.NORMAL
            self.active_backup = None
            self.fail_count = 0
            self.stats["total_recoveries"] += 1
            self.stats["last_recovery_time"] = datetime.now().isoformat()
            self._log_event("restore_success", f"主链路恢复, {lat:.0f}ms")
            notify("🔙 主链路恢复", f"已切回主网络 ({lat:.0f}ms)", self.cfg["notify"]["sound"])

            # 关闭备份链路
            phones = self.cfg.get("phones", [])
            for phone in phones:
                serial = phone.get("serial") or None
                adb = self.cfg.get("adb_path", "")
                if phone.get("tether_method") == "usb":
                    disable_usb_tethering(serial=serial, adb_path=adb)
                else:
                    disable_wifi_hotspot(serial=serial, adb_path=adb)

            # 重启隧道
            if self.cfg.get("tunnel", {}).get("restart_on_failover"):
                self._restart_tunnel()

            return True
        else:
            log.warning("主链路仍不可用，保持备份链路")
            # 恢复备份优先级
            if self._backup_adapter:
                set_adapter_metric(self._backup_adapter, 5)
            if self._primary_adapter:
                set_adapter_metric(self._primary_adapter, 9999)
            return False

    def _restart_tunnel(self):
        """重启隧道"""
        tunnel_cfg = self.cfg.get("tunnel", {})
        if not tunnel_cfg.get("enabled"):
            return
        stop_tunnel()
        time.sleep(2)
        start_tunnel(tunnel_cfg.get("command", ""))

    def check_primary_recovery(self):
        """在备份模式下，定期检查主链路是否恢复"""
        if self.state not in (GuardianState.FAILOVER_USB, GuardianState.FAILOVER_HOTSPOT):
            return

        # 临时切回主链路测试
        if self._primary_adapter and self._backup_adapter:
            # 短暂给主链路高优先级测试
            set_adapter_metric(self._primary_adapter, 5)
            set_adapter_metric(self._backup_adapter, 10)
            time.sleep(2)

            net_ok, passed, total, lat = check_internet(
                self.cfg["ping_targets"][:2], 1, 1500)

            if net_ok:
                log.info(f"主链路恢复信号 ({passed}/{total}, {lat:.0f}ms)")
                self.do_restore()
            else:
                # 切回备份
                set_adapter_metric(self._backup_adapter, 5)
                set_adapter_metric(self._primary_adapter, 9999)

    def get_status(self):
        """获取完整状态"""
        uptime = time.time() - self.stats["uptime_start"]
        return {
            "state": self.state,
            "fail_count": self.fail_count,
            "last_latency_ms": self.last_latency,
            "active_backup": self.active_backup,
            "primary_adapter": self._primary_adapter,
            "backup_adapter": self._backup_adapter,
            "uptime_sec": int(uptime),
            "uptime_human": str(timedelta(seconds=int(uptime))),
            "stats": self.stats,
            "agents": heartbeat_state.get_all(),
            "recent_events": list(self.history)[-10:],
        }

    def run(self):
        """主循环"""
        log.info("=" * 60)
        log.info("🛡️  Network Guardian 启动")
        log.info(f"  主适配器: {self._primary_adapter or '未检测'}")
        log.info(f"  USB共享:  {self._backup_adapter or '待激活'}")
        log.info(f"  手机数量: {len([p for p in self.cfg.get('phones', []) if p.get('enabled')])}")
        log.info(f"  检测间隔: {self.cfg['check_interval_sec']}秒")
        log.info(f"  探测目标: {', '.join(self.cfg['ping_targets'])}")
        log.info("=" * 60)

        # 启动心跳服务
        hb_cfg = self.cfg.get("heartbeat", {})
        if hb_cfg.get("enabled"):
            self._start_heartbeat_server(hb_cfg.get("port", 9800))
            self._start_agent_monitor()

        # 启动隧道监控
        tunnel_cfg = self.cfg.get("tunnel", {})
        if tunnel_cfg.get("enabled"):
            self._start_tunnel_monitor()

        check_interval = self.cfg["check_interval_sec"]
        recovery_interval = self.cfg["recovery_check_sec"]
        last_recovery_check = 0

        try:
            while not self._stop.is_set():
                # 正常/降级模式：检测互联网
                if self.state in (GuardianState.NORMAL, GuardianState.DEGRADED):
                    ok = self.check_once()
                    if not ok and self.should_failover():
                        self.do_failover("auto")

                # 备份模式：定期检查主链路恢复
                elif self.state in (GuardianState.FAILOVER_USB, GuardianState.FAILOVER_HOTSPOT):
                    # 继续监控备份链路是否正常
                    ok = self.check_once()
                    if not ok:
                        log.error("备份链路也断了！尝试切换其他备份...")
                        self.state = GuardianState.NORMAL
                        self.fail_count = self.cfg["fail_threshold"]  # 立即触发重新failover

                    # 定期检查主链路
                    if time.time() - last_recovery_check > recovery_interval:
                        self.check_primary_recovery()
                        last_recovery_check = time.time()

                elif self.state == GuardianState.ERROR:
                    # 错误状态：持续尝试恢复
                    ok = self.check_once()
                    if ok:
                        self.state = GuardianState.NORMAL
                        self.fail_count = 0
                        notify("🔙 网络自愈", "连接已恢复", True)

                self._stop.wait(check_interval)

        except KeyboardInterrupt:
            log.info("收到退出信号")
        finally:
            self._cleanup()

    def _cleanup(self):
        """清理退出"""
        log.info("🛡️  Guardian 正在退出...")
        # 如果在备份模式，恢复适配器
        if self.state in (GuardianState.FAILOVER_USB, GuardianState.FAILOVER_HOTSPOT):
            log.info("恢复网络适配器设置...")
            if self._primary_adapter:
                set_adapter_metric(self._primary_adapter, 25)
            if self._backup_adapter:
                set_adapter_metric(self._backup_adapter, 50)
        log.info("✅ Guardian 已退出")

    def stop(self):
        self._stop.set()

    def _start_heartbeat_server(self, port):
        """启动心跳HTTP服务"""
        def serve():
            try:
                server = HTTPServer(("0.0.0.0", port), HeartbeatHTTPHandler)
                server.timeout = 1
                log.info(f"心跳服务启动: http://0.0.0.0:{port}")
                while not self._stop.is_set():
                    server.handle_request()
            except Exception as e:
                log.error(f"心跳服务异常: {e}")

        t = threading.Thread(target=serve, daemon=True, name="heartbeat-server")
        t.start()

    def _start_agent_monitor(self):
        """启动Agent监控线程"""
        def monitor():
            hb_cfg = self.cfg.get("heartbeat", {})
            interval = hb_cfg.get("interval_sec", 10)
            threshold = hb_cfg.get("dead_threshold", 3) * interval

            while not self._stop.is_set():
                # 探测所有配置的手机
                for phone in self.cfg.get("phones", []):
                    if not phone.get("enabled"):
                        continue
                    name = phone.get("name", "unknown")
                    ip = phone.get("wifi_ip", "")
                    port = phone.get("ss_port", 8084)
                    found = False

                    # 尝试WiFi IP（如果有）
                    if ip:
                        for p in (port, 8080, 8081):
                            url = f"http://{ip}:{p}/status"
                            ok, lat = probe_agent(name, url)
                            if ok:
                                found = True
                                break

                    # WiFi IP 失败或为空 → 尝试 localhost（ADB forward）
                    if not found:
                        for p in (port, 8080, 8081):
                            url = f"http://127.0.0.1:{p}/status"
                            ok, lat = probe_agent(name, url)
                            if ok:
                                found = True
                                break

                # 检查死亡agent
                dead = heartbeat_state.check_dead(threshold)
                for name in dead:
                    log.warning(f"⚠️ Agent '{name}' 无响应")

                self._stop.wait(interval)

        t = threading.Thread(target=monitor, daemon=True, name="agent-monitor")
        t.start()

    def _start_tunnel_monitor(self):
        """启动隧道进程监控"""
        def monitor():
            tunnel_cfg = self.cfg.get("tunnel", {})
            command = tunnel_cfg.get("command", "")
            if not command:
                return

            while not self._stop.is_set():
                if not is_tunnel_running():
                    log.warning("隧道进程不存在，重启中...")
                    start_tunnel(command)
                self._stop.wait(30)

        t = threading.Thread(target=monitor, daemon=True, name="tunnel-monitor")
        t.start()


# ============================================================
# 全局访问器（供HTTP handler使用）
# ============================================================
_guardian_instance = None

def guardian_status():
    if _guardian_instance:
        return _guardian_instance.get_status()
    return {"error": "guardian not running"}

def do_failover(method="auto"):
    if _guardian_instance:
        return _guardian_instance.do_failover(method)
    return False

def do_restore():
    if _guardian_instance:
        return _guardian_instance.do_restore()
    return False


# ============================================================
# CLI
# ============================================================

def print_status():
    """打印当前状态"""
    import urllib.request
    try:
        with urllib.request.urlopen("http://127.0.0.1:9800/status", timeout=3) as resp:
            data = json.loads(resp.read().decode())
            print(json.dumps(data, indent=2, ensure_ascii=False, default=str))
    except Exception:
        print("Guardian 未运行或心跳端口不可达")
        # 直接检测
        connected, passed, total, lat = check_internet(
            DEFAULT_CONFIG["ping_targets"],
            DEFAULT_CONFIG["ping_consensus"],
            DEFAULT_CONFIG["ping_timeout_ms"])
        print(f"\n直接检测: {'✅ 正常' if connected else '❌ 异常'} "
              f"({passed}/{total} 通过, {lat:.0f}ms)")
        print(f"主适配器: {find_primary_adapter() or '未检测到'}")
        print(f"USB共享:  {find_usb_tether_adapter() or '未连接'}")

def detect_and_setup():
    """首次运行：自动检测环境并生成配置"""
    print("🔍 检测网络环境...")
    cfg = DEFAULT_CONFIG.copy()

    # 检测适配器
    primary = find_primary_adapter()
    usb = find_usb_tether_adapter()
    print(f"  主适配器: {primary or '未检测到'}")
    print(f"  USB共享:  {usb or '未连接'}")
    cfg["adapters"]["primary"] = primary or ""
    cfg["adapters"]["usb_tether"] = usb or ""

    # 检测ADB
    adb = _find_adb()
    if adb:
        print(f"  ADB: {adb}")
        cfg["adb_path"] = adb

        # 检测连接的手机
        out, ok = adb_run("devices", adb_path=adb)
        if ok:
            phones = []
            for line in out.splitlines():
                if "\tdevice" in line:
                    serial = line.split("\t")[0]
                    # 获取手机型号
                    model_out, _ = adb_run("shell", "getprop", "ro.product.model",
                                           serial=serial, adb_path=adb)
                    carrier_out, _ = adb_run("shell", "getprop", "gsm.operator.alpha",
                                             serial=serial, adb_path=adb)
                    phones.append({
                        "name": model_out.strip() or serial,
                        "serial": serial,
                        "wifi_ip": "",
                        "ss_port": 8084,
                        "tether_method": "usb" if ":" not in serial else "hotspot",
                        "carrier": carrier_out.strip() or "未知",
                        "priority": len(phones) + 1,
                        "enabled": True
                    })
                    print(f"  手机: {phones[-1]['name']} ({serial}) [{phones[-1]['carrier']}]")

            if phones:
                cfg["phones"] = phones
    else:
        print("  ADB: 未找到")

    # 检测网络
    connected, passed, total, lat = check_internet(
        cfg["ping_targets"], cfg["ping_consensus"], cfg["ping_timeout_ms"])
    print(f"\n  互联网: {'✅ 正常' if connected else '❌ 异常'} "
          f"({passed}/{total}, {lat:.0f}ms)")

    # 检测cloudflared
    try:
        r = subprocess.run(["cloudflared", "--version"],
                           capture_output=True, text=True, timeout=5,
                           creationflags=subprocess.CREATE_NO_WINDOW)
        if r.returncode == 0:
            print(f"  Cloudflared: {r.stdout.strip()[:50]}")
    except Exception:
        print("  Cloudflared: 未安装")

    # 保存配置
    save_config(cfg)
    print(f"\n✅ 配置已保存到: {CONFIG_PATH}")
    print("   编辑配置后运行 'python network_guardian.py' 启动守护")
    return cfg


def main():
    parser = argparse.ArgumentParser(description="🛡️ Network Guardian — 网络自愈守护进程")
    parser.add_argument("--daemon", action="store_true", help="后台守护模式")
    parser.add_argument("--status", action="store_true", help="查看当前状态")
    parser.add_argument("--setup", action="store_true", help="自动检测环境并生成配置")
    parser.add_argument("--failover", choices=["usb", "hotspot", "auto"],
                        help="手动触发链路切换")
    parser.add_argument("--restore", action="store_true", help="恢复主链路")
    parser.add_argument("--port", type=int, default=0, help="心跳服务端口 (覆盖配置)")
    args = parser.parse_args()

    if args.setup:
        detect_and_setup()
        return

    if args.status:
        print_status()
        return

    if args.failover:
        cfg = load_config()
        guardian = Guardian(cfg)
        guardian.do_failover(args.failover)
        return

    if args.restore:
        cfg = load_config()
        guardian = Guardian(cfg)
        guardian.do_restore()
        return

    # 正常启动
    if not CONFIG_PATH.exists():
        print("首次运行，自动检测环境...")
        cfg = detect_and_setup()
        print("\n" + "=" * 40)
        input("按回车启动守护进程...")
    else:
        cfg = load_config()

    if args.port:
        cfg.setdefault("heartbeat", {})["port"] = args.port

    global _guardian_instance
    _guardian_instance = Guardian(cfg)

    if args.daemon:
        log.info("后台守护模式")

    _guardian_instance.run()


if __name__ == "__main__":
    main()
