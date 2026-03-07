"""
多手机舰队管理器 (Phone Fleet Manager)
=======================================
协调多部手机+多SIM卡，为 Network Guardian 提供：
  1. 多手机并行探测 — 找到所有可用手机
  2. 网络质量评估 — 哪部手机信号最好/流量最便宜
  3. 智能选择 — 根据运营商/信号/电量自动选最优备份
  4. 手机互联网共享控制 — USB共享/WiFi热点
  5. 手机间互监 — 通过手机检测PC是否断网

与 phone_lib.Phone 兼容，与 network_guardian.Guardian 协作。

用法：
  from phone_fleet import PhoneFleet
  fleet = PhoneFleet()
  fleet.scan()            # 扫描所有可用手机
  fleet.best_backup()     # 选最优备份手机
  fleet.enable_tether()   # 启用最优手机的网络共享
  fleet.status()          # 所有手机状态总览

独立运行：
  python phone_fleet.py              # 扫描并显示所有手机
  python phone_fleet.py --monitor    # 持续监控模式
  python phone_fleet.py --tether     # 启用最优手机共享
"""

import json, time, os, sys, subprocess, threading, logging, re
from pathlib import Path
from datetime import datetime

log = logging.getLogger("fleet")
if not log.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s [Fleet] %(message)s", "%H:%M:%S"))
    log.addHandler(_h)
    log.setLevel(logging.INFO)

# ============================================================
# ADB工具（与network_guardian共享逻辑）
# ============================================================
import shutil

def _find_adb():
    candidates = [
        shutil.which("adb"),
        os.path.join(os.path.dirname(__file__), "android-sdk",
                     "platform-tools", "adb.exe"),
        os.environ.get("ADB_PATH", ""),
    ]
    for p in candidates:
        if p and os.path.isfile(p):
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

def _adb(*args, serial=None, timeout=10):
    adb = _find_adb()
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

def _http_probe(url, timeout=2):
    """HTTP探测，返回(ok, latency_ms, data)"""
    from urllib.request import Request, urlopen
    try:
        req = Request(url, method="GET")
        start = time.time()
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            latency = (time.time() - start) * 1000
            data = json.loads(raw)
            return True, latency, data
    except Exception:
        return False, -1, {}


# ============================================================
# 手机信息采集
# ============================================================

class PhoneInfo:
    """单部手机的完整信息"""

    def __init__(self, serial):
        self.serial = serial
        self.model = ""
        self.manufacturer = ""
        self.android_ver = ""
        self.carrier = ""           # 运营商
        self.sim_state = ""         # SIM状态
        self.network_type = ""      # WiFi/4G/5G
        self.signal_strength = -1   # 信号强度 dBm
        self.wifi_ip = ""           # WiFi IP
        self.wifi_ssid = ""         # WiFi SSID
        self.battery = -1           # 电量%
        self.charging = False       # 是否充电
        self.is_usb = False         # 是否USB连接
        self.ss_url = ""            # ScreenStream URL
        self.ss_alive = False       # ScreenStream是否存活
        self.ss_latency = -1        # SS响应延迟ms
        self.tether_active = False  # 网络共享是否开启
        self.data_enabled = True    # 移动数据是否开启
        self.score = 0              # 综合评分（备份优先级）
        self.last_update = 0

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}


def collect_phone_info(serial):
    """通过ADB采集手机完整信息"""
    info = PhoneInfo(serial)
    info.is_usb = ":" not in serial

    # 基本信息
    out, ok = _adb("shell", "getprop", "ro.product.model", serial=serial)
    if ok: info.model = out.strip()

    out, ok = _adb("shell", "getprop", "ro.product.manufacturer", serial=serial)
    if ok: info.manufacturer = out.strip()

    out, ok = _adb("shell", "getprop", "ro.build.version.release", serial=serial)
    if ok: info.android_ver = out.strip()

    # 运营商
    out, ok = _adb("shell", "getprop", "gsm.operator.alpha", serial=serial)
    if ok: info.carrier = out.strip()

    # SIM状态
    out, ok = _adb("shell", "getprop", "gsm.sim.state", serial=serial)
    if ok: info.sim_state = out.strip()

    # 网络类型
    out, ok = _adb("shell", "getprop", "gsm.network.type", serial=serial)
    if ok: info.network_type = out.strip()

    # WiFi IP
    out, ok = _adb("shell", "ip", "addr", "show", "wlan0", serial=serial)
    if ok:
        m = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", out)
        if m: info.wifi_ip = m.group(1)

    # WiFi SSID
    out, ok = _adb("shell", "dumpsys", "wifi", serial=serial, timeout=5)
    if ok:
        m = re.search(r'mWifiInfo.*?SSID:\s*"?([^",\n]+)', out)
        if m: info.wifi_ssid = m.group(1).strip()

    # 电量
    out, ok = _adb("shell", "dumpsys", "battery", serial=serial)
    if ok:
        m = re.search(r"level:\s*(\d+)", out)
        if m: info.battery = int(m.group(1))
        info.charging = "AC powered: true" in out or "USB powered: true" in out

    # 信号强度
    out, ok = _adb("shell", "dumpsys", "telephony.registry", serial=serial, timeout=5)
    if ok:
        # 搜索信号强度 (dBm)
        m = re.search(r"mSignalStrength.*?(-?\d+)\s*dBm", out)
        if m: info.signal_strength = int(m.group(1))

    # 移动数据状态
    out, ok = _adb("shell", "settings", "get", "global", "mobile_data", serial=serial)
    if ok: info.data_enabled = out.strip() == "1"

    # USB共享状态
    out, ok = _adb("shell", "dumpsys", "connectivity", serial=serial, timeout=5)
    if ok:
        info.tether_active = "Tethering" in out and "CONNECTED" in out

    # 探测ScreenStream
    ports_to_try = [8084, 8080, 8081]
    for port in ports_to_try:
        # 先尝试WiFi IP
        if info.wifi_ip:
            url = f"http://{info.wifi_ip}:{port}"
            alive, lat, data = _http_probe(url)
            if alive:
                info.ss_url = url
                info.ss_alive = True
                info.ss_latency = lat
                break

        # 再尝试localhost (ADB forward)
        if info.is_usb:
            url = f"http://127.0.0.1:{port}"
            alive, lat, data = _http_probe(url, timeout=1)
            if alive:
                info.ss_url = url
                info.ss_alive = True
                info.ss_latency = lat
                break

    # 综合评分（用于选最优备份）
    info.score = _calc_backup_score(info)
    info.last_update = time.time()
    return info


def _calc_backup_score(info):
    """计算手机作为网络备份的综合评分 (0-100, 越高越优)"""
    score = 50  # 基础分

    # 电量影响 (0-20分)
    if info.battery >= 0:
        if info.battery > 50: score += 20
        elif info.battery > 20: score += 10
        elif info.battery > 10: score += 5
        else: score -= 20  # 低电量扣分
    if info.charging: score += 5  # 充电中加分

    # 连接方式 (0-15分)
    if info.is_usb: score += 15   # USB连接最可靠
    elif info.wifi_ip: score += 10  # WiFi可达
    else: score -= 10

    # SIM状态 (0-10分)
    if "READY" in info.sim_state.upper(): score += 10
    elif info.sim_state: score += 5

    # 移动数据 (0-10分)
    if info.data_enabled: score += 10

    # 信号强度 (0-10分)
    if info.signal_strength != -1:
        if info.signal_strength > -70: score += 10    # 强信号
        elif info.signal_strength > -85: score += 7   # 中等
        elif info.signal_strength > -100: score += 3  # 弱
        else: score += 0  # 极弱

    # 网络类型加分
    net = info.network_type.upper()
    if "NR" in net or "5G" in net: score += 5     # 5G
    elif "LTE" in net or "4G" in net: score += 3  # 4G
    elif "HSPA" in net: score += 1                 # 3G+

    # ScreenStream存活加分
    if info.ss_alive: score += 5

    return min(100, max(0, score))


# ============================================================
# 舰队管理器
# ============================================================

class PhoneFleet:
    """多手机舰队管理"""

    def __init__(self):
        self.phones = {}  # serial → PhoneInfo
        self._lock = threading.Lock()

    def scan(self):
        """扫描所有ADB连接的手机"""
        out, ok = _adb("devices")
        if not ok:
            log.error("ADB不可用")
            return []

        serials = []
        for line in out.splitlines():
            if "\tdevice" in line:
                serial = line.split("\t")[0]
                serials.append(serial)

        if not serials:
            log.info("未发现ADB设备")
            return []

        log.info(f"发现 {len(serials)} 个设备，采集信息...")

        results = []
        threads = []
        for serial in serials:
            def collect(s=serial):
                info = collect_phone_info(s)
                with self._lock:
                    self.phones[s] = info
                results.append(info)
            t = threading.Thread(target=collect)
            t.start()
            threads.append(t)

        for t in threads:
            t.join(timeout=15)

        # 按评分排序
        results.sort(key=lambda x: x.score, reverse=True)
        return results

    def best_backup(self):
        """选最优备份手机"""
        if not self.phones:
            self.scan()

        with self._lock:
            candidates = sorted(self.phones.values(),
                                key=lambda p: p.score, reverse=True)

        for phone in candidates:
            if phone.battery > 10 and (phone.is_usb or phone.wifi_ip):
                return phone
        return candidates[0] if candidates else None

    def enable_tether(self, serial=None, method="usb"):
        """启用指定手机（或最优手机）的网络共享
        method: usb | hotspot"""
        if serial is None:
            best = self.best_backup()
            if not best:
                log.error("没有可用的手机")
                return False
            serial = best.serial
            log.info(f"自动选择: {best.model} ({best.serial}) [评分:{best.score}]")

        phone = self.phones.get(serial)
        name = phone.model if phone else serial

        if method == "usb":
            log.info(f"启用 {name} USB共享...")
            _adb("shell", "svc", "usb", "setFunctions", "rndis,adb", serial=serial)
            time.sleep(3)
            # 验证
            _adb("shell", "service", "call", "connectivity", "33",
                 "i32", "1", "s16", "com.android.shell", serial=serial)
            return True

        elif method == "hotspot":
            log.info(f"启用 {name} WiFi热点...")
            # Android 12+
            _adb("shell", "cmd", "wifi", "start-softap",
                 "Guardian_AP", "wpa2", "guardian12345", serial=serial)
            time.sleep(2)
            # 回退：打开设置
            _adb("shell", "am", "start", "-n",
                 "com.android.settings/.TetherSettings", serial=serial)
            return True

        return False

    def disable_tether(self, serial=None):
        """关闭网络共享"""
        targets = [serial] if serial else list(self.phones.keys())
        for s in targets:
            _adb("shell", "svc", "usb", "setFunctions", "mtp,adb", serial=s)
            _adb("shell", "cmd", "wifi", "stop-softap", serial=s)
        log.info("网络共享已关闭")

    def status(self):
        """所有手机状态总览"""
        if not self.phones:
            self.scan()

        summary = []
        for serial, info in sorted(self.phones.items(),
                                    key=lambda x: x[1].score, reverse=True):
            summary.append({
                "name": f"{info.manufacturer} {info.model}".strip(),
                "serial": serial,
                "carrier": info.carrier,
                "battery": f"{info.battery}%{'⚡' if info.charging else ''}",
                "network": info.network_type,
                "signal": f"{info.signal_strength}dBm" if info.signal_strength != -1 else "?",
                "wifi_ip": info.wifi_ip or "-",
                "usb": "✅" if info.is_usb else "❌",
                "ss": f"✅ {info.ss_latency:.0f}ms" if info.ss_alive else "❌",
                "data": "✅" if info.data_enabled else "❌",
                "sim": info.sim_state,
                "score": info.score,
            })
        return summary

    def print_status(self):
        """格式化打印"""
        statuses = self.status()
        if not statuses:
            print("未发现手机")
            return

        print(f"\n📱 手机舰队 — {len(statuses)}台设备")
        print("=" * 80)
        for i, s in enumerate(statuses, 1):
            star = "⭐" if i == 1 else "  "
            print(f"{star} #{i} {s['name']} [{s['carrier']}]")
            print(f"     序列号: {s['serial']}")
            print(f"     电量: {s['battery']}  网络: {s['network']}  "
                  f"信号: {s['signal']}  SIM: {s['sim']}")
            print(f"     WiFi: {s['wifi_ip']}  USB: {s['usb']}  "
                  f"SS: {s['ss']}  数据: {s['data']}")
            print(f"     备份评分: {s['score']}/100")
            print()

    def check_internet_via_phone(self, serial=None):
        """通过手机检测互联网是否通畅（手机视角）
        用于判断是手机网络问题还是PC网络问题"""
        if serial is None:
            best = self.best_backup()
            if not best:
                return None
            serial = best.serial

        # 让手机ping外网
        out, ok = _adb("shell", "ping", "-c", "3", "-W", "2", "8.8.8.8", serial=serial)
        if ok and "bytes from" in out:
            m = re.search(r"avg.*?/([\d.]+)/", out)
            latency = float(m.group(1)) if m else 0
            return {
                "internet_ok": True,
                "latency_ms": latency,
                "source": "phone_cell",
                "serial": serial
            }
        return {
            "internet_ok": False,
            "detail": out[:200] if out else "ping failed",
            "serial": serial
        }

    def diagnose_disconnect(self):
        """智能诊断断网原因：
        - PC宽带断 + 手机WiFi断 = 路由器/ISP问题
        - PC宽带断 + 手机4G通 = 仅PC宽带问题
        - PC通 + 手机断 = 手机问题
        - 全断 = ISP/区域性断网
        """
        results = {
            "time": datetime.now().isoformat(),
            "pc_internet": False,
            "phones": [],
            "diagnosis": "",
            "action": ""
        }

        # 1. PC直接检测
        from network_guardian import check_internet, DEFAULT_CONFIG
        pc_ok, passed, total, lat = check_internet(
            DEFAULT_CONFIG["ping_targets"],
            DEFAULT_CONFIG["ping_consensus"],
            DEFAULT_CONFIG["ping_timeout_ms"])
        results["pc_internet"] = pc_ok
        results["pc_detail"] = f"{passed}/{total}, {lat:.0f}ms"

        # 2. 每部手机检测
        phone_results = []
        for serial in self.phones:
            r = self.check_internet_via_phone(serial)
            if r:
                phone_results.append(r)
        results["phones"] = phone_results

        phone_ok_count = sum(1 for r in phone_results if r.get("internet_ok"))
        phone_total = len(phone_results)

        # 3. 诊断
        if pc_ok and phone_ok_count == phone_total:
            results["diagnosis"] = "✅ 一切正常"
            results["action"] = "无需操作"

        elif not pc_ok and phone_ok_count > 0:
            results["diagnosis"] = "🔶 PC宽带断连，手机4G/5G正常 → 仅PC/路由器问题"
            results["action"] = "建议：USB共享手机网络 或 重启路由器"

        elif not pc_ok and phone_ok_count == 0 and phone_total > 0:
            # 检查手机WiFi vs 4G
            wifi_phones = [s for s, info in self.phones.items() if info.wifi_ip]
            if wifi_phones:
                results["diagnosis"] = "🔴 PC和手机WiFi都断 → 路由器/ISP问题"
                results["action"] = "建议：1.重启路由器 2.手机切4G后USB共享 3.联系ISP"
            else:
                results["diagnosis"] = "🔴 全部断网 → 区域性网络故障或全部SIM欠费"
                results["action"] = "建议：1.检查SIM卡 2.等待ISP恢复 3.换个位置试试信号"

        elif pc_ok and phone_ok_count < phone_total:
            results["diagnosis"] = "🔶 PC正常，部分手机异常"
            results["action"] = "检查异常手机的WiFi/SIM状态"

        else:
            results["diagnosis"] = "❓ 状态不明"
            results["action"] = "手动检查各设备网络"

        return results


# ============================================================
# 持续监控模式
# ============================================================

def monitor_loop(fleet, interval=15):
    """持续监控所有手机状态"""
    print("📡 持续监控模式 (Ctrl+C退出)")
    print(f"   监控间隔: {interval}秒\n")

    try:
        while True:
            fleet.scan()
            os.system("cls" if os.name == "nt" else "clear")
            fleet.print_status()

            # 简要诊断
            diag = fleet.diagnose_disconnect()
            print(f"诊断: {diag['diagnosis']}")
            if diag["action"] != "无需操作":
                print(f"建议: {diag['action']}")
            print(f"\n下次刷新: {interval}秒后... (Ctrl+C退出)")

            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n监控已停止")


# ============================================================
# CLI
# ============================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="📱 Phone Fleet Manager — 多手机舰队管理")
    parser.add_argument("--monitor", action="store_true", help="持续监控模式")
    parser.add_argument("--tether", action="store_true", help="启用最优手机共享")
    parser.add_argument("--stop-tether", action="store_true", help="关闭所有手机共享")
    parser.add_argument("--diagnose", action="store_true", help="诊断断网原因")
    parser.add_argument("--json", action="store_true", help="JSON格式输出")
    parser.add_argument("--interval", type=int, default=15, help="监控间隔(秒)")
    args = parser.parse_args()

    fleet = PhoneFleet()

    if args.monitor:
        monitor_loop(fleet, args.interval)
        return

    if args.diagnose:
        fleet.scan()
        result = fleet.diagnose_disconnect()
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(f"\n🔍 断网诊断")
            print(f"   PC互联网: {'✅' if result['pc_internet'] else '❌'} ({result.get('pc_detail','')})")
            for pr in result["phones"]:
                status = "✅" if pr.get("internet_ok") else "❌"
                lat = f"{pr.get('latency_ms',0):.0f}ms" if pr.get("internet_ok") else ""
                print(f"   手机({pr['serial'][:12]}): {status} {lat}")
            print(f"\n   诊断: {result['diagnosis']}")
            print(f"   建议: {result['action']}")
        return

    if args.tether:
        fleet.scan()
        fleet.enable_tether()
        return

    if args.stop_tether:
        fleet.scan()
        fleet.disable_tether()
        return

    # 默认：扫描并显示
    fleet.scan()
    if args.json:
        print(json.dumps(fleet.status(), indent=2, ensure_ascii=False))
    else:
        fleet.print_status()


if __name__ == "__main__":
    main()
