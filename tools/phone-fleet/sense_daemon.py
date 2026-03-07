"""
sense_daemon.py — 无感守护（五感之外）
=======================================
道 · 无感而知，无为而治

设计哲学:
  五感 (五感采集) = 主动询问，你问它才答
  无感 (此守护)  = 被动守望，它默默盯着你，异常才开口
  反之有反       = 不只感知→控制，还能 机器→人类 反向告警（写剪贴板/发手机通知）

功能:
  · 后台循环监控所有 agent（手机 + 台式机 + 笔记本）
  · 检测异常：手机无障碍断/RAM>90%/磁盘<5GB/agent离线
  · 异常时：写日志 + 写剪贴板告警 + (可选)发手机通知
  · 安静运行，无异常不输出任何内容

用法:
  python sense_daemon.py                # 前台运行（30s/次，Ctrl+C停止）
  python sense_daemon.py --interval 60  # 60秒一次
  python sense_daemon.py --once         # 仅检查一次后退出
  python sense_daemon.py --verbose      # 每轮打印状态（调试用）
  python sense_daemon.py --alert-phone  # 异常时通过手机API推送通知
  python sense_daemon.py --log E:\\logs\\sense.log  # 自定义日志路径
"""

import argparse
import json
import logging
import os
import sys
import time
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.request import Request, urlopen
from urllib.error import URLError

# ── 路径设置 ────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

try:
    from phone_lib import Phone, NegativeState
    _PHONE_LIB_OK = True
except ImportError:
    _PHONE_LIB_OK = False

DEFAULT_LOG = os.path.join(_HERE, "sense_daemon.log")

# ── 阈值配置 ────────────────────────────────────────────────
ALERT_THRESHOLDS = {
    "ram_pct_max":    90,   # RAM使用率超过此值告警
    "disk_free_min":   5,   # 磁盘剩余低于此GB告警
    "battery_min":    15,   # 手机电量低于此%告警（未充电时）
    "agent_timeout":   5,   # agent探测超时秒数
}


# ── HTTP 工具 ────────────────────────────────────────────────
def _get(url: str, path: str, timeout: float = 5):
    try:
        with urlopen(url + path, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"_error": str(e)[:80]}


# ── 各域健康检查 ─────────────────────────────────────────────
def _check_windows_agent(name: str, url: str) -> list:
    """检查 Windows agent，返回告警列表 []"""
    alerts = []
    h  = _get(url, "/health")
    si = _get(url, "/sysinfo")

    if "_error" in h:
        alerts.append(f"[{name}] 离线: {h['_error'][:60]}")
        return alerts

    ram = si.get("ram_percent", 0)
    disk = si.get("disk_free_gb", 999)
    locked = si.get("is_locked", False)

    if ram > ALERT_THRESHOLDS["ram_pct_max"]:
        alerts.append(f"[{name}] RAM告警: {ram}% > {ALERT_THRESHOLDS['ram_pct_max']}%")
    if isinstance(disk, (int, float)) and disk < ALERT_THRESHOLDS["disk_free_min"]:
        alerts.append(f"[{name}] 磁盘告警: 剩余 {disk}GB < {ALERT_THRESHOLDS['disk_free_min']}GB")
    if locked:
        alerts.append(f"[{name}] 锁屏中")

    return alerts


def _check_phone(url: str) -> list:
    """检查手机状态，返回告警列表"""
    alerts = []
    try:
        s = _get(url, "/status")
        d = _get(url, "/deviceinfo")

        if "_error" in s:
            alerts.append(f"[手机] 离线: {s['_error'][:60]}")
            return alerts

        if not s.get("inputEnabled", True):
            alerts.append("[手机] 无障碍服务断开! (AccessibilityService stopped)")

        if s.get("screenOffMode", False):
            alerts.append("[手机] 屏幕息屏")

        bat = d.get("batteryLevel", 100)
        charging = d.get("isCharging", True)
        if bat < ALERT_THRESHOLDS["battery_min"] and not charging:
            alerts.append(f"[手机] 电量低: {bat}% (未充电)")

    except Exception as e:
        alerts.append(f"[手机] 检查异常: {e}")

    return alerts


# ── 反向告警 ─────────────────────────────────────────────────
def _push_to_clipboard(text: str):
    """将告警写入台式机剪贴板 (通过台式机 admin agent)"""
    try:
        body = json.dumps({"text": text}).encode()
        req = Request("http://localhost:9904/clipboard", data=body,
                      headers={"Content-Type": "application/json"}, method="POST")
        urlopen(req, timeout=3)
    except Exception:
        pass


def _push_to_phone(phone_url: str, title: str, message: str):
    """通过 ScreenStream API 将告警推送到手机 (写剪贴板+振动)"""
    try:
        # 写剪贴板
        body = json.dumps({"text": f"⚠️ {title}: {message}"}).encode()
        req = Request(phone_url + "/clipboard", data=body,
                      headers={"Content-Type": "application/json"}, method="POST")
        urlopen(req, timeout=3)
        # 振动提醒
        body2 = json.dumps({"duration": 800}).encode()
        req2 = Request(phone_url + "/vibrate", data=body2,
                       headers={"Content-Type": "application/json"}, method="POST")
        urlopen(req2, timeout=3)
    except Exception:
        pass


# ── 主守护循环 ────────────────────────────────────────────────
class SenseDaemon:
    """
    无感守护 — 五感之外的被动监控层

    守护哲学:
      有感 → 主动感知 (sense_all.py 调用时才工作)
      无感 → 被动守望 (此类，永远在后台盯着)
      反之 → 机器告警人类 (写剪贴板/振动手机 = 机器反向控制人类注意力)
    """

    DOMAINS = {
        "台式机-Admin":  ("windows", "http://localhost:9904"),
        "台式机-ai":     ("windows", "http://localhost:9905"),
        "笔记本":        ("windows", "http://192.168.31.179:9903"),
        "手机":          ("phone",   "http://127.0.0.1:8084"),
    }

    def __init__(self, interval=30, log_path=DEFAULT_LOG,
                 verbose=False, alert_phone=False):
        self.interval   = interval
        self.log_path   = log_path
        self.verbose    = verbose
        self.alert_phone = alert_phone
        self._stop_evt  = threading.Event()
        self._round     = 0

        logging.basicConfig(
            filename=log_path,
            level=logging.INFO,
            format="%(asctime)s [感] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            encoding="utf-8",
        )
        self._log = logging.getLogger("sense_daemon")

    def _one_round(self) -> list:
        """一轮检查，返回所有告警列表"""
        all_alerts = []

        tasks = []
        for name, (dtype, url) in self.DOMAINS.items():
            if dtype == "windows":
                tasks.append((name, lambda n=name, u=url: _check_windows_agent(n, u)))
            else:
                tasks.append((name, lambda u=url: _check_phone(u)))

        with ThreadPoolExecutor(max_workers=len(tasks)) as ex:
            futs = {ex.submit(fn): name for name, fn in tasks}
            for fut in as_completed(futs, timeout=20):
                try:
                    result = fut.result()
                    all_alerts.extend(result)
                except Exception as e:
                    all_alerts.append(f"[{futs[fut]}] 检查异常: {e}")

        return all_alerts

    def tick(self):
        """执行一次检测周期"""
        self._round += 1
        ts = datetime.now().strftime("%H:%M:%S")

        alerts = self._one_round()

        if alerts:
            msg = f"第{self._round}轮 [{ts}] {len(alerts)}个告警"
            self._log.warning(msg)
            for a in alerts:
                self._log.warning(f"  ⚠ {a}")
            if self.verbose or True:  # 有告警时总是打印
                print(f"\n⚠️  {msg}")
                for a in alerts:
                    print(f"   {a}")
            # 反向告警: 写剪贴板
            alert_text = f"[无感守护 {ts}] {'; '.join(alerts)}"
            _push_to_clipboard(alert_text)
            # 反向告警: 手机振动+剪贴板
            if self.alert_phone:
                _push_to_phone("http://127.0.0.1:8084",
                               "无感守护", "; ".join(alerts[:2]))
        else:
            msg = f"第{self._round}轮 [{ts}] 全域正常"
            self._log.info(msg)
            if self.verbose:
                print(f"✅ {msg}")

    def run_once(self):
        """仅执行一次检测并输出结果"""
        alerts = self._one_round()
        if alerts:
            print(f"⚠️  检测到 {len(alerts)} 个异常:")
            for a in alerts:
                print(f"   {a}")
        else:
            print("✅ 全域健康，无告警")
        return alerts

    def run_forever(self):
        """持续守护循环（Ctrl+C 停止）"""
        print(f"🌙 无感守护启动  间隔={self.interval}s  日志={self.log_path}")
        print(f"   监控域: {list(self.DOMAINS.keys())}")
        print(f"   Ctrl+C 停止\n")
        self._log.info(f"守护启动 interval={self.interval}s")
        try:
            while not self._stop_evt.is_set():
                self.tick()
                self._stop_evt.wait(self.interval)
        except KeyboardInterrupt:
            pass
        self._log.info("守护停止")
        print("\n🌙 无感守护已停止")

    def stop(self):
        self._stop_evt.set()


# ── CLI ──────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="无感守护 — 五感之外的被动监控\n道·无感而知，无为而治",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--interval",    type=int, default=30,
                        help="检测间隔秒数 (默认30)")
    parser.add_argument("--once",        action="store_true",
                        help="只检测一次后退出")
    parser.add_argument("--verbose",     action="store_true",
                        help="每轮打印状态(包括正常状态)")
    parser.add_argument("--alert-phone", action="store_true",
                        help="异常时通过ScreenStream API振动手机")
    parser.add_argument("--log",         default=DEFAULT_LOG,
                        help=f"日志路径 (默认: {DEFAULT_LOG})")
    parser.add_argument("--thresholds",  action="store_true",
                        help="打印当前阈值配置")
    args = parser.parse_args()

    if args.thresholds:
        print("当前告警阈值:")
        for k, v in ALERT_THRESHOLDS.items():
            print(f"  {k} = {v}")
        sys.exit(0)

    daemon = SenseDaemon(
        interval=args.interval,
        log_path=args.log,
        verbose=args.verbose,
        alert_phone=args.alert_phone,
    )

    if args.once:
        sys.exit(0 if not daemon.run_once() else 1)
    else:
        daemon.run_forever()
