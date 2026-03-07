#!/usr/bin/env python3
"""
Agent主动感知引擎 — ProactiveAgent v1.0
=========================================
从高维度审视用户与智能家居的完整状态，主动带入用户之感。

架构:
  PhoneSensor       — 30s轮询手机五感 (battery/notifications/screen/foreground_app)
  HomeSensor        — 60s轮询家居状态 (temp/presence/lights/fans/devices)
  ContextInference  — 融合手机+家居 → 推断用户活动场景
  RulesEngine       — 规则触发: TTS播报 / 场景切换 / 设备联动
  ProactiveDaemon   — 后台编排 + 共享状态 + API端点集成

运行方式:
  python proactive_agent.py                     # 独立守护进程
  python proactive_agent.py --once              # 单次采集调试
  from proactive_agent import ProactiveDaemon   # 嵌入网关

用户状态推断层次 (从低到高):
  L0 体感  — 温度/光线 → 自动调节设备
  L1 转场  — 回家/离家/睡觉/晨起 → 执行场景宏
  L2 感知  — 家里状态一览 → 主动播报/推送
  L3 预判  — 根据行为模式预测需求
  L4 托管  — 全自动无感运行
"""

import json
import time
import threading
import logging
import os
from datetime import datetime
from typing import Optional, List, Dict, Any
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from dataclasses import dataclass, field, asdict
from collections import deque

logger = logging.getLogger(__name__)


# ============================================================
# 数据模型
# ============================================================

@dataclass
class PhoneState:
    """手机五感状态快照"""
    timestamp: float = 0.0
    battery: int = -1
    charging: bool = False
    network: str = "?"
    net_ok: bool = False
    screen_off: bool = False
    foreground_app: str = ""
    notification_count: int = 0
    notifications: List[dict] = field(default_factory=list)
    wifi_ssid: str = ""
    storage_free_gb: float = 0.0
    input_enabled: bool = True
    reachable: bool = False
    error: str = ""

    @property
    def age_sec(self) -> float:
        return time.time() - self.timestamp if self.timestamp else 999

    @property
    def battery_ok(self) -> bool:
        return self.battery > 20

    @property
    def battery_low(self) -> bool:
        return 0 < self.battery <= 20

    @property
    def battery_critical(self) -> bool:
        return 0 < self.battery <= 8


@dataclass
class HomeState:
    """家居环境状态快照"""
    timestamp: float = 0.0
    temperature: float = -1.0
    humidity: float = -1.0
    presence: bool = False
    lights_on: List[str] = field(default_factory=list)
    lights_off: List[str] = field(default_factory=list)
    fans_on: List[str] = field(default_factory=list)
    switches_on: List[str] = field(default_factory=list)
    speaker_online: bool = False
    device_count: int = 0
    reachable: bool = False
    error: str = ""

    @property
    def any_light_on(self) -> bool:
        return bool(self.lights_on)

    @property
    def any_fan_on(self) -> bool:
        return bool(self.fans_on)

    @property
    def age_sec(self) -> float:
        return time.time() - self.timestamp if self.timestamp else 999

    @property
    def temp_ok(self) -> bool:
        return 16 <= self.temperature <= 26

    @property
    def temp_hot(self) -> bool:
        return self.temperature > 28

    @property
    def temp_cold(self) -> bool:
        return 0 < self.temperature < 14


@dataclass
class UserContext:
    """高维用户状态模型 — 融合手机+家居"""
    timestamp: float = 0.0
    inferred_activity: str = "unknown"  # sleeping/working/away/home/morning/evening
    at_home: bool = True
    likely_sleeping: bool = False
    likely_working: bool = False
    likely_morning: bool = False
    alerts: List[str] = field(default_factory=list)
    phone: PhoneState = field(default_factory=PhoneState)
    home: HomeState = field(default_factory=HomeState)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["_human_time"] = (
            datetime.fromtimestamp(self.timestamp).strftime("%H:%M:%S")
            if self.timestamp else "-"
        )
        d["_phone_age_sec"] = round(self.phone.age_sec)
        d["_home_age_sec"] = round(self.home.age_sec)
        return d

    def summary(self) -> str:
        """人类可读摘要"""
        parts = [f"活动={self.inferred_activity}"]
        if self.phone.reachable:
            bat = f"{self.phone.battery}%{'⚡' if self.phone.charging else ''}"
            parts.append(f"手机电量={bat}")
        if self.home.reachable:
            if self.home.temperature > 0:
                parts.append(f"室温={self.home.temperature:.1f}°C")
            if self.home.lights_on:
                parts.append(f"亮灯={len(self.home.lights_on)}盏")
        if self.alerts:
            parts.append(f"⚠️{' '.join(self.alerts)}")
        return " | ".join(parts)


@dataclass
class ProactiveEvent:
    """主动动作事件记录"""
    timestamp: float
    rule_id: str
    trigger_desc: str
    action_desc: str
    success: bool
    detail: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["_human_time"] = datetime.fromtimestamp(self.timestamp).strftime("%Y-%m-%d %H:%M:%S")
        return d


# ============================================================
# HTTP工具 (零外部依赖)
# ============================================================

def _http_get(url: str, timeout: int = 5) -> Optional[dict]:
    """HTTP GET → JSON，失败返回None"""
    try:
        req = Request(url, headers={"Accept": "application/json", "User-Agent": "ProactiveAgent/1.0"})
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        logger.debug(f"GET {url} → {e}")
        return None


def _http_post(url: str, data: dict = None, timeout: int = 8) -> Optional[dict]:
    """HTTP POST JSON → JSON，失败返回None"""
    try:
        body = json.dumps(data or {}).encode()
        req = Request(url, data=body, headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "ProactiveAgent/1.0",
        })
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        logger.debug(f"POST {url} → {e}")
        return None


# ============================================================
# 传感器层
# ============================================================

class PhoneSensor:
    """手机五感传感器 — ScreenStream HTTP API"""

    def __init__(self, phone_url: str = "http://127.0.0.1:8084"):
        self.base = phone_url.rstrip("/")
        self._state = PhoneState()
        self._lock = threading.Lock()

    def poll(self) -> PhoneState:
        """采集手机完整状态（并发GET加速）"""
        state = PhoneState(timestamp=time.time())
        try:
            import concurrent.futures
            urls = {
                "status": f"{self.base}/status",
                "devinfo": f"{self.base}/deviceinfo",
                "notifs": f"{self.base}/notifications/read?limit=10",
                "screen": f"{self.base}/screen/text",
            }
            results = {}
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                futures = {pool.submit(_http_get, url, 4): key for key, url in urls.items()}
                for future in concurrent.futures.as_completed(futures, timeout=6):
                    key = futures[future]
                    try:
                        results[key] = future.result()
                    except Exception:
                        results[key] = None

            status = results.get("status") or {}
            devinfo = results.get("devinfo") or {}
            notifs = results.get("notifs") or {}
            screen = results.get("screen") or {}

            if not status and not devinfo:
                state.reachable = False
                state.error = "手机API无响应"
                with self._lock:
                    self._state = state
                return state

            state.reachable = True
            state.screen_off = status.get("screenOffMode", False)
            state.input_enabled = status.get("inputEnabled", True)
            state.battery = devinfo.get("batteryLevel", -1)
            state.charging = devinfo.get("isCharging", False)
            state.network = devinfo.get("networkType", "?")
            state.net_ok = devinfo.get("networkConnected", False)
            state.wifi_ssid = devinfo.get("wifiSSID", "")
            state.storage_free_gb = round(devinfo.get("storageAvailableMB", 0) / 1024, 1)
            state.notification_count = notifs.get("total", 0)
            state.notifications = notifs.get("notifications", [])[:10]
            state.foreground_app = screen.get("package", "")

        except Exception as e:
            state.reachable = False
            state.error = str(e)

        with self._lock:
            self._state = state
        return state

    @property
    def last(self) -> PhoneState:
        with self._lock:
            return self._state


class HomeSensor:
    """家居状态传感器 — 智能家居网关REST API"""

    def __init__(self, gateway_url: str = "http://127.0.0.1:8900"):
        self.base = gateway_url.rstrip("/")
        self._state = HomeState()
        self._lock = threading.Lock()

    def poll(self) -> HomeState:
        """采集家居完整状态"""
        state = HomeState(timestamp=time.time())
        try:
            devices_resp = _http_get(f"{self.base}/devices", timeout=8)
            if not devices_resp:
                state.reachable = False
                state.error = "智能家居网关无响应"
                with self._lock:
                    self._state = state
                return state

            state.reachable = True
            state.device_count = devices_resp.get("count", 0)

            for dev in devices_resp.get("devices", []):
                dev_state_str = str(dev.get("state", "")).lower()
                dev_name = dev.get("name", dev.get("id", ""))
                dev_id = str(dev.get("id", ""))
                domain = dev.get("domain", "") or (dev_id.split(".")[0] if "." in dev_id else "")
                is_on = dev_state_str in ("on", "true", "1", "open", "heat", "cool", "auto")

                if domain == "light":
                    (state.lights_on if is_on else state.lights_off).append(dev_name)
                elif domain == "fan":
                    if is_on:
                        state.fans_on.append(dev_name)
                elif domain == "switch":
                    if is_on:
                        state.switches_on.append(dev_name)
                elif domain == "sensor":
                    lower_name = dev_name.lower() + dev_id.lower()
                    try:
                        val = float(dev_state_str)
                        if any(k in lower_name for k in ["温度", "temperature", "temp"]):
                            if -20 < val < 60:
                                state.temperature = val
                        elif any(k in lower_name for k in ["湿度", "humidity", "humi"]):
                            if 0 < val < 100:
                                state.humidity = val
                    except (ValueError, TypeError):
                        pass
                    if any(k in lower_name for k in ["人在", "presence", "occupancy", "motion"]):
                        state.presence = is_on

            # 音箱在线状态
            speakers_resp = _http_get(f"{self.base}/speakers", timeout=4)
            if speakers_resp:
                state.speaker_online = speakers_resp.get("online", 0) > 0

        except Exception as e:
            state.reachable = False
            state.error = str(e)

        with self._lock:
            self._state = state
        return state

    @property
    def last(self) -> HomeState:
        with self._lock:
            return self._state


# ============================================================
# 上下文推断引擎
# ============================================================

class ContextInferenceEngine:
    """从手机+家居状态推断用户活动场景"""

    # 家庭WiFi SSID关键词（可通过config覆盖）
    HOME_SSID_KEYWORDS: List[str] = []

    @classmethod
    def infer(cls, phone: PhoneState, home: HomeState) -> UserContext:
        ctx = UserContext(timestamp=time.time(), phone=phone, home=home)
        hour = datetime.now().hour
        alerts = []

        # ── 是否在家推断 ──
        if phone.reachable:
            # 手机可直连 = 在家（USB转发 or 同WiFi）
            at_home = True
            # 如果配置了家庭SSID，用SSID精确判断
            if cls.HOME_SSID_KEYWORDS and phone.wifi_ssid:
                ssid = phone.wifi_ssid.lower()
                at_home = any(k.lower() in ssid for k in cls.HOME_SSID_KEYWORDS)
        else:
            at_home = False  # 不可达 = 可能外出
        ctx.at_home = at_home

        # ── 睡眠状态推断 ──
        # 深夜/凌晨 + 屏幕关闭 + 灯已关
        sleeping = (
            phone.screen_off
            and (hour >= 23 or hour <= 6)
            and not home.any_light_on
            and at_home
        )
        ctx.likely_sleeping = sleeping

        # ── 晨起状态推断 ──
        morning = (
            6 <= hour <= 9
            and not phone.screen_off
            and phone.reachable
            and at_home
        )
        ctx.likely_morning = morning

        # ── 工作状态推断 ──
        working = (
            not phone.screen_off
            and 9 <= hour <= 18
            and home.any_light_on
            and at_home
        )
        ctx.likely_working = working

        # ── 综合活动场景 ──
        if not at_home:
            ctx.inferred_activity = "away"
        elif sleeping:
            ctx.inferred_activity = "sleeping"
        elif morning:
            ctx.inferred_activity = "morning"
        elif working:
            ctx.inferred_activity = "working"
        elif 19 <= hour <= 23:
            ctx.inferred_activity = "evening"
        else:
            ctx.inferred_activity = "home"

        # ── 警报生成 ──
        if phone.reachable and not phone.charging:
            if phone.battery_critical:
                alerts.append(f"⚠️手机危急电量{phone.battery}%")
            elif phone.battery_low:
                alerts.append(f"手机低电量{phone.battery}%")

        if home.temp_hot and not home.any_fan_on:
            alerts.append(f"室温{home.temperature:.1f}°C偏高")
        elif home.temp_cold:
            alerts.append(f"室温{home.temperature:.1f}°C偏低")

        ctx.alerts = alerts
        return ctx


# ============================================================
# 规则引擎
# ============================================================

class Rule:
    """单条主动规则基类"""

    def __init__(self, rule_id: str, name: str, enabled: bool = True, cooldown_sec: int = 300):
        self.id = rule_id
        self.name = name
        self.enabled = enabled
        self._cooldown_sec = cooldown_sec
        self._last_triggered: float = 0.0

    def can_trigger(self) -> bool:
        return time.time() - self._last_triggered > self._cooldown_sec

    def check(self, ctx: UserContext) -> Optional[str]:
        """检查是否触发。返回动作规格字符串，None则不触发。
        动作规格格式: "type:param|type2:param2"
        type: tts / scene / fan_on / fan_off / light_on / light_off / log
        """
        raise NotImplementedError

    def mark_triggered(self):
        self._last_triggered = time.time()


class BatteryLowRule(Rule):
    def __init__(self):
        super().__init__("battery_low", "手机低电量提醒", enabled=True, cooldown_sec=600)

    def check(self, ctx: UserContext) -> Optional[str]:
        p = ctx.phone
        if not p.reachable or p.charging or p.battery <= 0:
            return None
        if p.battery_low and not p.battery_critical:
            return f"tts:主人，手机电量只剩{p.battery}%了，请及时充电"
        return None


class BatteryCriticalRule(Rule):
    def __init__(self):
        super().__init__("battery_critical", "手机危急电量警报", enabled=True, cooldown_sec=180)

    def check(self, ctx: UserContext) -> Optional[str]:
        p = ctx.phone
        if not p.reachable or p.charging or p.battery <= 0:
            return None
        if p.battery_critical:
            return f"tts:警告！手机电量仅剩{p.battery}%，请立即充电！"
        return None


class HighTempFanRule(Rule):
    def __init__(self):
        super().__init__("high_temp_fan", "高温自动开风扇", enabled=True, cooldown_sec=1800)

    def check(self, ctx: UserContext) -> Optional[str]:
        h = ctx.home
        if not h.reachable or h.temperature <= 0:
            return None
        if h.temp_hot and not h.any_fan_on and ctx.at_home:
            return f"fan_on:落地扇|tts:室温{h.temperature:.1f}度偏高，已为您开启风扇"
        return None


class LowTempAlert(Rule):
    def __init__(self):
        super().__init__("low_temp_alert", "低温提醒", enabled=True, cooldown_sec=3600)

    def check(self, ctx: UserContext) -> Optional[str]:
        h = ctx.home
        if not h.reachable or h.temperature <= 0:
            return None
        if h.temp_cold and ctx.at_home and not ctx.likely_sleeping:
            return f"tts:室温{h.temperature:.1f}度，注意保暖"
        return None


class MorningGreetingRule(Rule):
    def __init__(self):
        super().__init__("morning_greeting", "早晨问候", enabled=True, cooldown_sec=43200)

    def check(self, ctx: UserContext) -> Optional[str]:
        if not ctx.likely_morning or not ctx.phone.reachable:
            return None
        hour = datetime.now().hour
        if hour <= 7:
            greet = "早安！今天也要元气满满哦"
        elif hour <= 8:
            greet = "早上好！新的一天开始了，记得喝水"
        else:
            greet = "上午好！记得吃早饭"
        return f"tts:{greet}"


class SleepAutoOffRule(Rule):
    def __init__(self):
        super().__init__("sleep_auto_off", "睡眠自动关灯", enabled=True, cooldown_sec=28800)

    def check(self, ctx: UserContext) -> Optional[str]:
        hour = datetime.now().hour
        p = ctx.phone
        h = ctx.home
        if (p.screen_off and hour >= 23 and h.any_light_on and ctx.at_home and h.reachable):
            return "scene:sleep|tts:检测到您准备休息，已为您关闭灯光，晚安"
        return None


class WelcomeHomeRule(Rule):
    """用户回家欢迎（基于手机可达性检测）"""

    def __init__(self):
        super().__init__("welcome_home", "回家欢迎", enabled=True, cooldown_sec=1800)
        self._was_away: bool = False

    def check(self, ctx: UserContext) -> Optional[str]:
        if not ctx.phone.reachable:
            self._was_away = True
            return None
        if self._was_away and ctx.at_home:
            self._was_away = False
            hour = datetime.now().hour
            if 6 <= hour <= 23:
                return "scene:home|tts:欢迎回家！已为您开灯"
        return None


class NotificationSpikeRule(Rule):
    def __init__(self):
        super().__init__("notification_spike", "重要新消息播报", enabled=False, cooldown_sec=120)
        self._prev_count: int = -1

    def check(self, ctx: UserContext) -> Optional[str]:
        p = ctx.phone
        if not p.reachable:
            return None
        if self._prev_count < 0:
            self._prev_count = p.notification_count
            return None
        new_count = p.notification_count - self._prev_count
        if new_count >= 3:
            self._prev_count = p.notification_count
            social = [n for n in p.notifications[:3]
                      if any(k in str(n.get("package", "")).lower()
                             for k in ["weixin", "tencent", "qq", "wx"])]
            if social:
                title = social[0].get("title", "")
                suffix = f"，{title}" if title else ""
                return f"tts:您有{new_count}条新消息{suffix}"
        else:
            self._prev_count = p.notification_count
        return None


class EveningRelaxRule(Rule):
    """傍晚情境：自动调暖灯"""

    def __init__(self):
        super().__init__("evening_relax", "傍晚暖灯提醒", enabled=True, cooldown_sec=86400)

    def check(self, ctx: UserContext) -> Optional[str]:
        hour = datetime.now().hour
        if (ctx.inferred_activity == "evening"
                and ctx.at_home
                and ctx.home.reachable
                and not ctx.home.any_light_on):
            return "tts:傍晚到了，要不要开个灯放松一下？"
        return None


# ============================================================
# 动作执行器
# ============================================================

class ActionExecutor:
    """执行规则引擎触发的动作"""

    def __init__(self, gateway_url: str, phone_url: str):
        self.gateway = gateway_url.rstrip("/")
        self.phone = phone_url.rstrip("/")

    def execute(self, action_spec: str, ctx: UserContext) -> tuple:
        """
        解析并执行动作规格
        格式: "type:param|type2:param2"
        类型:
          tts:文字        — 小爱音箱播报
          scene:name      — 执行场景宏
          fan_on:关键词   — 开风扇
          fan_off:关键词  — 关风扇
          light_on        — 开全部灯
          light_off       — 关全部灯
          log:文字        — 仅记录日志
        """
        results = []
        overall_ok = True

        for part in action_spec.split("|"):
            part = part.strip()
            if ":" not in part and part not in ("light_on", "light_off"):
                continue
            if ":" in part:
                action_type, param = part.split(":", 1)
            else:
                action_type, param = part, ""
            action_type = action_type.strip()
            param = param.strip()

            try:
                if action_type == "tts":
                    ok = self._tts(param, ctx)
                    results.append(f"TTS({'✅' if ok else '❌'}): {param[:20]}")
                    overall_ok = overall_ok and ok
                elif action_type == "scene":
                    ok = self._scene(param)
                    results.append(f"场景[{param}]({'✅' if ok else '❌'})")
                    overall_ok = overall_ok and ok
                elif action_type == "fan_on":
                    ok = self._voice_control(f"打开{param or '风扇'}")
                    results.append(f"开风扇({'✅' if ok else '❌'})")
                elif action_type == "fan_off":
                    ok = self._voice_control(f"关闭{param or '风扇'}")
                    results.append(f"关风扇({'✅' if ok else '❌'})")
                elif action_type == "light_on":
                    ok = bool(_http_post(f"{self.gateway}/quick/lights_on"))
                    results.append(f"开灯({'✅' if ok else '❌'})")
                elif action_type == "light_off":
                    ok = bool(_http_post(f"{self.gateway}/quick/lights_off"))
                    results.append(f"关灯({'✅' if ok else '❌'})")
                elif action_type == "log":
                    logger.info(f"[Agent] {param}")
                    results.append(f"日志: {param}")
                else:
                    results.append(f"未知动作: {action_type}")
            except Exception as e:
                results.append(f"错误[{action_type}]: {e}")
                overall_ok = False

        return overall_ok, " | ".join(results)

    def _tts(self, text: str, ctx: UserContext) -> bool:
        """TTS播报 — 优先Mina API，回退proxy/voice"""
        # 尝试Mina TTS
        r = _http_post(f"{self.gateway}/mina/tts", {"text": text}, timeout=10)
        if r and r.get("ok"):
            return True
        # 回退proxy/voice
        r = _http_post(f"{self.gateway}/proxy/voice",
                       {"command": f"说{text}", "silent": False}, timeout=10)
        return bool(r and r.get("ok"))

    def _scene(self, scene_name: str) -> bool:
        r = _http_post(f"{self.gateway}/scenes/macros/{scene_name}", timeout=15)
        return bool(r and r.get("ok"))

    def _voice_control(self, command: str) -> bool:
        """通过音箱代理执行语音命令"""
        r = _http_post(f"{self.gateway}/proxy/voice",
                       {"command": command, "silent": True}, timeout=10)
        return bool(r and r.get("ok"))


# ============================================================
# ProactiveDaemon — 主动感知守护进程
# ============================================================

class ProactiveDaemon:
    """
    Agent主动感知守护进程

    启动后维护三条后台线程:
      PA-Phone  — 轮询手机五感
      PA-Home   — 轮询家居设备
      PA-Rules  — 规则引擎 + 上下文推断

    对外暴露:
      get_context()     → 当前用户上下文快照
      get_history()     → 最近主动事件历史
      get_rules_status() → 所有规则状态
      toggle_rule()     → 开关规则
      force_check()     → 强制立即检查（调试）
      get_health()      → 守护进程健康状态
    """

    VERSION = "1.0.0"

    def __init__(self, config: dict = None):
        cfg = config or {}
        phone_url = cfg.get("phone_url", "http://127.0.0.1:8084")
        gateway_url = cfg.get("gateway_url", "http://127.0.0.1:8900")

        self.phone_interval = cfg.get("phone_interval_sec", 30)
        self.home_interval = cfg.get("home_interval_sec", 60)
        self.rules_interval = cfg.get("rules_interval_sec", 15)
        self.enabled = cfg.get("enabled", True)

        # 家庭SSID配置
        home_ssids = cfg.get("home_ssid_keywords", [])
        if home_ssids:
            ContextInferenceEngine.HOME_SSID_KEYWORDS = home_ssids

        self.phone_sensor = PhoneSensor(phone_url)
        self.home_sensor = HomeSensor(gateway_url)
        self.executor = ActionExecutor(gateway_url, phone_url)

        # 规则列表（可动态开关）
        self.rules: List[Rule] = [
            BatteryLowRule(),
            BatteryCriticalRule(),
            HighTempFanRule(),
            LowTempAlert(),
            MorningGreetingRule(),
            SleepAutoOffRule(),
            WelcomeHomeRule(),
            NotificationSpikeRule(),
            EveningRelaxRule(),
        ]

        # 从config覆盖规则开关
        rules_cfg = cfg.get("rules", {})
        for rule in self.rules:
            if rule.id in rules_cfg:
                rc = rules_cfg[rule.id]
                rule.enabled = bool(rc.get("enabled", rule.enabled))
                if "cooldown_sec" in rc:
                    rule._cooldown_sec = int(rc["cooldown_sec"])

        self._context = UserContext()
        self._history: deque = deque(maxlen=200)
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._threads: List[threading.Thread] = []
        self._start_time = time.time()
        self._poll_count = {"phone": 0, "home": 0, "rules": 0}

        logger.info(f"ProactiveDaemon v{self.VERSION} 初始化: {len(self.rules)}条规则")

    def start(self):
        """启动所有后台感知线程"""
        if not self.enabled:
            logger.info("ProactiveDaemon: 未启用 (enabled=false)")
            return

        t_phone = threading.Thread(target=self._phone_loop, daemon=True, name="PA-Phone")
        t_home = threading.Thread(target=self._home_loop, daemon=True, name="PA-Home")
        t_rules = threading.Thread(target=self._rules_loop, daemon=True, name="PA-Rules")

        for t in [t_phone, t_home, t_rules]:
            t.start()
            self._threads.append(t)

        logger.info(
            f"ProactiveDaemon 已启动 — "
            f"手机:{self.phone_interval}s, 家居:{self.home_interval}s, 规则:{self.rules_interval}s"
        )

    def stop(self):
        """停止所有后台线程"""
        self._stop.set()
        for t in self._threads:
            t.join(timeout=5)
        logger.info("ProactiveDaemon 已停止")

    # ── 后台线程 ──

    def _phone_loop(self):
        while not self._stop.is_set():
            try:
                state = self.phone_sensor.poll()
                self._poll_count["phone"] += 1
                icon = "📱" if state.reachable else "📵"
                bat_str = f"bat={state.battery}%" if state.battery >= 0 else "bat=?"
                logger.debug(f"{icon} Phone #{self._poll_count['phone']}: "
                             f"{bat_str} screen_off={state.screen_off} "
                             f"notif={state.notification_count}")
            except Exception as e:
                logger.error(f"[PA-Phone] 轮询错误: {e}")
            self._stop.wait(self.phone_interval)

    def _home_loop(self):
        while not self._stop.is_set():
            try:
                state = self.home_sensor.poll()
                self._poll_count["home"] += 1
                icon = "🏠" if state.reachable else "🔌"
                temp_str = f"temp={state.temperature:.1f}°C" if state.temperature > 0 else "temp=?"
                logger.debug(f"{icon} Home #{self._poll_count['home']}: "
                             f"lights={len(state.lights_on)} fans={len(state.fans_on)} {temp_str}")
            except Exception as e:
                logger.error(f"[PA-Home] 轮询错误: {e}")
            self._stop.wait(self.home_interval)

    def _rules_loop(self):
        """规则引擎主循环 — 每N秒跑一次"""
        # 首次等待几秒让传感器预热
        self._stop.wait(5)

        while not self._stop.is_set():
            try:
                phone = self.phone_sensor.last
                home = self.home_sensor.last
                ctx = ContextInferenceEngine.infer(phone, home)

                with self._lock:
                    self._context = ctx

                self._poll_count["rules"] += 1

                for rule in self.rules:
                    if not rule.enabled or not rule.can_trigger():
                        continue
                    try:
                        action = rule.check(ctx)
                        if action:
                            rule.mark_triggered()
                            logger.info(f"🎯 [Rule:{rule.id}] 触发 → {action}")
                            ok, detail = self.executor.execute(action, ctx)
                            event = ProactiveEvent(
                                timestamp=time.time(),
                                rule_id=rule.id,
                                trigger_desc=rule.name,
                                action_desc=action,
                                success=ok,
                                detail=detail,
                            )
                            with self._lock:
                                self._history.append(event)
                            logger.info(f"{'✅' if ok else '❌'} [Rule:{rule.id}] {detail}")
                    except Exception as e:
                        logger.error(f"[Rule:{rule.id}] 执行错误: {e}")

            except Exception as e:
                logger.error(f"[PA-Rules] 规则循环错误: {e}")

            self._stop.wait(self.rules_interval)

    # ── 公开API ──

    def get_context(self) -> dict:
        """获取当前用户上下文快照"""
        with self._lock:
            return self._context.to_dict()

    def get_summary(self) -> str:
        """获取人类可读摘要"""
        with self._lock:
            return self._context.summary()

    def get_history(self, limit: int = 20) -> List[dict]:
        """获取最近主动事件历史"""
        with self._lock:
            events = list(self._history)
        return [e.to_dict() for e in events[-limit:]]

    def get_rules_status(self) -> List[dict]:
        """获取所有规则状态"""
        now = time.time()
        return [
            {
                "id": r.id,
                "name": r.name,
                "enabled": r.enabled,
                "cooldown_sec": r._cooldown_sec,
                "last_triggered": (
                    datetime.fromtimestamp(r._last_triggered).strftime("%H:%M:%S")
                    if r._last_triggered else "从未"
                ),
                "can_trigger": r.can_trigger(),
                "next_trigger_in_sec": max(0, round(r._cooldown_sec - (now - r._last_triggered)))
                    if r._last_triggered else 0,
            }
            for r in self.rules
        ]

    def toggle_rule(self, rule_id: str, enabled: bool) -> bool:
        """开关规则，返回是否找到"""
        for r in self.rules:
            if r.id == rule_id:
                r.enabled = enabled
                logger.info(f"规则 {rule_id} → {'启用' if enabled else '禁用'}")
                return True
        return False

    def get_health(self) -> dict:
        """守护进程健康状态"""
        return {
            "version": self.VERSION,
            "enabled": self.enabled,
            "running": not self._stop.is_set(),
            "uptime_sec": round(time.time() - self._start_time),
            "phone_reachable": self.phone_sensor.last.reachable,
            "phone_poll_count": self._poll_count["phone"],
            "home_reachable": self.home_sensor.last.reachable,
            "home_poll_count": self._poll_count["home"],
            "rules_cycles": self._poll_count["rules"],
            "active_rules": sum(1 for r in self.rules if r.enabled),
            "total_rules": len(self.rules),
            "events_fired": len(self._history),
        }

    def force_check(self, rule_id: Optional[str] = None) -> dict:
        """强制立即执行规则检查（忽略冷却，用于调试/手动触发）"""
        logger.info(f"强制检查: rule_id={rule_id or '全部'}")
        phone = self.phone_sensor.poll()
        home = self.home_sensor.poll()
        ctx = ContextInferenceEngine.infer(phone, home)

        with self._lock:
            self._context = ctx

        results = []
        target_rules = [r for r in self.rules if not rule_id or r.id == rule_id]

        for rule in target_rules:
            if not rule.enabled:
                results.append({"rule": rule.id, "skipped": "disabled"})
                continue
            action = rule.check(ctx)
            if action:
                rule.mark_triggered()
                ok, detail = self.executor.execute(action, ctx)
                event = ProactiveEvent(
                    timestamp=time.time(),
                    rule_id=rule.id,
                    trigger_desc=rule.name,
                    action_desc=action,
                    success=ok,
                    detail=detail,
                )
                with self._lock:
                    self._history.append(event)
                results.append({
                    "rule": rule.id,
                    "action": action,
                    "ok": ok,
                    "detail": detail,
                })
            else:
                results.append({"rule": rule.id, "no_trigger": True})

        return {
            "context": ctx.to_dict(),
            "context_summary": ctx.summary(),
            "rule_checks": results,
        }

    def poll_phone_now(self) -> dict:
        """立即采集手机状态"""
        state = self.phone_sensor.poll()
        return asdict(state)

    def poll_home_now(self) -> dict:
        """立即采集家居状态"""
        state = self.home_sensor.poll()
        return asdict(state)


# ============================================================
# 独立运行入口
# ============================================================

if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Agent主动感知守护进程")
    parser.add_argument("--phone", default="http://127.0.0.1:8084", help="手机API地址")
    parser.add_argument("--gateway", default="http://127.0.0.1:8900", help="智能家居网关地址")
    parser.add_argument("--phone-interval", type=int, default=30)
    parser.add_argument("--home-interval", type=int, default=60)
    parser.add_argument("--rules-interval", type=int, default=15)
    parser.add_argument("--once", action="store_true", help="单次采集（调试）")
    parser.add_argument("--rule", default=None, help="--once时只测试指定规则")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    cfg = {
        "phone_url": args.phone,
        "gateway_url": args.gateway,
        "phone_interval_sec": args.phone_interval,
        "home_interval_sec": args.home_interval,
        "rules_interval_sec": args.rules_interval,
        "enabled": True,
    }

    daemon = ProactiveDaemon(cfg)

    if args.once:
        print("\n=== Agent主动感知 — 单次检查 ===\n")
        result = daemon.force_check(args.rule)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    else:
        daemon.start()
        print(f"\n🤖 ProactiveDaemon v{ProactiveDaemon.VERSION} 运行中...")
        print(f"   手机: {args.phone} (每{args.phone_interval}s)")
        print(f"   家居: {args.gateway} (每{args.home_interval}s)")
        print(f"   规则: {len(daemon.rules)}条 (每{args.rules_interval}s检查)")
        print("   Ctrl+C 停止\n")
        try:
            while True:
                time.sleep(30)
                ctx = daemon.get_context()
                health = daemon.get_health()
                print(
                    f"[{datetime.now().strftime('%H:%M:%S')}] "
                    f"{ctx.get('inferred_activity', '?')} | "
                    f"{daemon.get_summary()} | "
                    f"事件:{health['events_fired']}"
                )
        except KeyboardInterrupt:
            daemon.stop()
            print("\n已停止")
