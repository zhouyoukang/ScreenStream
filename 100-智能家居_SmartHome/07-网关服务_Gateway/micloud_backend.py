"""
MiCloud Direct Backend — 直接调用小米云 API，不依赖 Home Assistant
使用 HA 缓存的 session token 绕过 2FA 登录

核心能力:
  - 设备列表 (get_devices)
  - 属性读取 (get_properties)
  - 属性设置 (set_property) — 控制设备
  - 动作执行 (execute_action) — TTS/播放等
  - MIoT spec 自动加载 — 从 HA 缓存或在线获取
"""

import json
import glob
import os
import logging
import time
from typing import Optional, Any
from micloud import MiCloud

logger = logging.getLogger(__name__)

# MiCloud RPC 错误码映射
MICLOUD_ERROR_CODES = {
    -704042011: "device_offline",
    -704040002: "device_unreachable",
    -704030013: "property_not_writable",
    -704030023: "property_read_only",
    -704020000: "invalid_params",
    -704010000: "unauthorized",
    -704000000: "unknown_error",
    -704220043: "token_expired",
}

def micloud_error_msg(code: int) -> str:
    """MiCloud 错误码 → 可读消息"""
    label = MICLOUD_ERROR_CODES.get(code, f"unknown({code})")
    return f"{label} (code={code})"


# ============================================================
# MIoT Spec 管理
# ============================================================
class MiotSpec:
    """MIoT 设备规格 — 描述设备的服务/属性/动作"""

    def __init__(self, model: str, spec_data: dict):
        self.model = model
        self.type = spec_data.get("type", "")
        self.description = spec_data.get("description", "")
        self.services = {}  # {siid: ServiceSpec}
        for svc in spec_data.get("services", []):
            ss = ServiceSpec(svc)
            self.services[ss.siid] = ss

    def get_main_switch(self) -> Optional[tuple]:
        """找到主开关属性 (siid, piid) — 通常是 siid=2, piid=1"""
        for siid in [2, 3]:
            svc = self.services.get(siid)
            if not svc:
                continue
            for piid, prop in svc.properties.items():
                if prop.name == "on" and prop.format == "bool" and prop.writable:
                    return (siid, piid)
        return None

    def get_writable_props(self) -> list:
        """获取所有可写属性"""
        result = []
        for siid, svc in self.services.items():
            for piid, prop in svc.properties.items():
                if prop.writable:
                    result.append({
                        "siid": siid, "piid": piid,
                        "service": svc.name, "name": prop.name,
                        "format": prop.format,
                        "value_range": prop.value_range,
                        "value_list": prop.value_list,
                    })
        return result

    def get_readable_props(self) -> list:
        """获取所有可读属性"""
        result = []
        for siid, svc in self.services.items():
            for piid, prop in svc.properties.items():
                if prop.readable:
                    result.append({
                        "siid": siid, "piid": piid,
                        "service": svc.name, "name": prop.name,
                        "format": prop.format,
                    })
        return result

    def get_actions(self) -> list:
        """获取所有可执行动作"""
        result = []
        for siid, svc in self.services.items():
            for aiid, action in svc.actions.items():
                result.append({
                    "siid": siid, "aiid": aiid,
                    "service": svc.name, "name": action.name,
                    "in_params": action.in_params,
                })
        return result


class ServiceSpec:
    def __init__(self, data: dict):
        self.siid = data["iid"]
        self.type = data.get("type", "")
        self.name = self.type.split(":")[3] if ":" in self.type else self.type
        self.properties = {}
        for p in data.get("properties", []):
            ps = PropertySpec(p)
            self.properties[ps.piid] = ps
        self.actions = {}
        for a in data.get("actions", []):
            acs = ActionSpec(a)
            self.actions[acs.aiid] = acs


class PropertySpec:
    def __init__(self, data: dict):
        self.piid = data["iid"]
        self.type = data.get("type", "")
        self.name = self.type.split(":")[3] if ":" in self.type else self.type
        self.format = data.get("format", "unknown")
        access = data.get("access", [])
        self.readable = "read" in access
        self.writable = "write" in access
        self.value_range = data.get("value-range")
        self.value_list = data.get("value-list")


class ActionSpec:
    def __init__(self, data: dict):
        self.aiid = data["iid"]
        self.type = data.get("type", "")
        self.name = self.type.split(":")[3] if ":" in self.type else self.type
        self.in_params = data.get("in", [])


# ============================================================
# 设备分类 & 归一化
# ============================================================
# 音箱动作回退表 — 无 spec 文件时使用（数据来源: MIGPT-Easy + MIoT spec）
# 格式: hardware_model -> {action_name: (siid, aiid/piid)}
SPEAKER_ACTION_FALLBACK = {
    # execute-text-directive: 让音箱执行语音指令
    # play-text: TTS 播报
    # volume: 音量属性 (siid, piid, "prop")
    "LX06": {"execute-text-directive": (5, 1), "play-text": (5, 3), "volume": (2, 1, "prop")},
    "L05B": {"execute-text-directive": (5, 3), "play-text": (5, 1), "volume": (2, 1, "prop")},
    "S12A": {"execute-text-directive": (5, 1), "play-text": (5, 3), "volume": (2, 1, "prop")},
    "LX01": {"execute-text-directive": (5, 1), "play-text": (5, 3), "volume": (2, 1, "prop")},
    "L06A": {"execute-text-directive": (5, 1), "play-text": (5, 3), "volume": (2, 1, "prop")},
    "LX04": {"execute-text-directive": (5, 1), "play-text": (5, 3), "volume": (2, 1, "prop")},
    "L05C": {"execute-text-directive": (5, 3), "play-text": (5, 1), "volume": (2, 1, "prop")},
    "L17A": {"execute-text-directive": (7, 3), "play-text": (7, 1), "volume": (2, 1, "prop")},
    "X08E": {"execute-text-directive": (7, 3), "play-text": (7, 1), "volume": (4, 1, "prop")},
    "LX05A": {"execute-text-directive": (5, 1), "play-text": (5, 3), "volume": (2, 1, "prop")},
    "L16A": {"execute-text-directive": (7, 3), "play-text": (7, 1), "volume": (4, 1, "prop")},
}

# 通用回退 — 大多数小爱音箱使用 SIID=5
_SPEAKER_DEFAULT = {"execute-text-directive": (5, 1), "play-text": (5, 3), "volume": (2, 1, "prop")}


def _get_hardware(model: str) -> str:
    """从 model 提取硬件型号: xiaomi.wifispeaker.lx06 -> LX06"""
    return model.split(".")[-1].upper() if "." in model else model.upper()


DEVICE_TYPE_MAP = {
    "switch": "switch", "outlet": "switch", "plug": "switch",
    "light": "light", "strip": "light",
    "fan": "fan",
    "speaker": "media_player", "wifispeaker": "media_player",
    "camera": "camera",
    "sensor_ht": "sensor", "sensor_occupy": "sensor",
    "temperature-humidity-sensor": "sensor",
    "occupancy-sensor": "sensor",
    "router": "sensor",
    "airer": "cover",
    "cooker": "sensor",
    "blanket": "climate",
    "pillow": "sensor",
    "gateway": "sensor",
    "watch": "sensor",
}


def classify_device(model: str, spec_type: str = "") -> str:
    """根据 model 和 spec type 推断设备域"""
    model_lower = model.lower()
    for key, domain in DEVICE_TYPE_MAP.items():
        if key in model_lower:
            return domain
    # 从 spec type 推断
    if spec_type:
        type_part = spec_type.split(":")[4] if ":" in spec_type and len(spec_type.split(":")) > 4 else ""
        for key, domain in DEVICE_TYPE_MAP.items():
            if key in type_part.lower():
                return domain
    return "sensor"


# ============================================================
# MiCloud Direct Client
# ============================================================
class MiCloudDirect:
    """直接调用小米云 API 的客户端"""

    MIOT_API_BASE = "https://api.io.mi.com/app"

    def __init__(self, credentials: dict, spec_dir: Optional[str] = None):
        """
        credentials: {
            "username": "...",
            "password": "...",
            "user_id": "...",
            "service_token": "...",
            "ssecurity": "...",
            "server_country": "cn"
        }
        spec_dir: HA 缓存的 MIoT spec 目录 (可选)
        """
        self.credentials = credentials
        self.spec_dir = spec_dir
        self.mc: Optional[MiCloud] = None
        self._devices: list = []
        self._device_map: dict = {}  # did -> device info
        self._specs: dict = {}  # model -> MiotSpec
        self._last_refresh = 0

    def init(self):
        """初始化 micloud 客户端 — 优先直接登录，回退到 HA 缓存 session"""
        username = self.credentials.get("username", "")
        password = self.credentials.get("password", "")

        if username and password:
            # 直接登录（推荐，不依赖 HA 缓存）
            ok = self._login_direct(username, password)
            if not ok:
                logger.warning("Direct login failed, falling back to HA session cache")
                self._restore_session()
        else:
            # 从 HA 缓存恢复 session
            self._restore_session()

        self._load_specs()
        self.refresh_devices()

    def _login_direct(self, username: str, password: str) -> bool:
        """用户名密码直接登录 MiCloud"""
        try:
            # 绕过系统代理（Windows代理可能阻断 account.xiaomi.com 登录）
            old_no_proxy = os.environ.get("NO_PROXY", "")
            os.environ["NO_PROXY"] = "account.xiaomi.com,api.io.mi.com," + old_no_proxy
            try:
                mc = MiCloud(username, password)
                mc.default_server = self.credentials.get("server_country", "cn")
                if mc.login():
                    self.mc = mc
                    logger.info("MiCloud direct login success, user_id=%s", mc.user_id)
                    return True
                logger.error("MiCloud direct login failed (wrong credentials?)")
            finally:
                if old_no_proxy:
                    os.environ["NO_PROXY"] = old_no_proxy
                else:
                    os.environ.pop("NO_PROXY", None)
        except Exception as e:
            logger.error("MiCloud direct login error: %s", e)
        return False

    def _restore_session(self):
        """从 HA 缓存恢复 session token"""
        mc = MiCloud(
            self.credentials.get("username", ""),
            self.credentials.get("password", "")
        )
        mc.user_id = self.credentials.get("user_id", "")
        mc.service_token = self.credentials.get("service_token", "")
        mc.ssecurity = self.credentials.get("ssecurity", "")
        mc.default_server = self.credentials.get("server_country", "cn")
        self.mc = mc
        logger.info("MiCloud session restored for user %s", mc.user_id)

    def relogin(self) -> dict:
        """重新登录 MiCloud（用于 session 过期时）"""
        username = self.credentials.get("username", "")
        password = self.credentials.get("password", "")
        if not username or not password:
            return {"ok": False, "error": "No username/password configured. Set in config.json micloud section."}
        ok = self._login_direct(username, password)
        if ok:
            self.refresh_devices()
            return {"ok": True, "devices": len(self._devices), "user_id": self.mc.user_id}
        return {"ok": False, "error": "Login failed. Check credentials."}

    def diagnose(self) -> dict:
        """诊断 MiCloud 连接状态"""
        result = {
            "cloud_reachable": False,
            "session_valid": False,
            "devices_total": len(self._devices),
            "devices_online": 0,
            "login_mode": "direct" if self.credentials.get("username") and self.credentials.get("password") else "ha_cache",
            "user_id": self.mc.user_id if self.mc else None,
        }
        if not self.mc:
            result["error"] = "MiCloud client not initialized"
            return result

        # 测试云端可达性 — 获取设备列表（轻量操作）
        try:
            country = self.credentials.get("server_country", "cn")
            devices = self.mc.get_devices(country=country)
            result["cloud_reachable"] = True
            result["session_valid"] = devices is not None
            if devices:
                result["devices_total"] = len(devices)
        except Exception as e:
            result["error"] = f"Cloud test failed: {e}"
            return result

        # 测试设备在线性 — 使用 isOnline 字段（云端推送连接状态，比 GET code=0 更准确）
        online_count = 0
        probe_results = []
        for d in self._devices:
            did = str(d["did"])
            name = d.get("name", "")
            is_online = d.get("isOnline", False)
            if is_online:
                online_count += 1
            probe_results.append({
                "did": did, "name": name,
                "isOnline": is_online,
                "model": d.get("model", ""),
            })

        result["devices_online"] = online_count
        result["devices_offline"] = len(self._devices) - online_count
        result["online_devices"] = [p for p in probe_results if p["isOnline"]]
        result["note"] = "isOnline=True 表示设备保持云端推送连接，可控制。GET code=0 可能是缓存值。"
        return result

    def _load_specs(self):
        """从 HA 缓存加载 MIoT spec"""
        if not self.spec_dir or not os.path.isdir(self.spec_dir):
            logger.warning("No spec dir, will use basic fallbacks")
            return
        for f in glob.glob(os.path.join(self.spec_dir, "urn_miot-spec-v2_device_*.json")):
            try:
                with open(f, encoding="utf-8") as fh:
                    raw = json.load(fh)
                data = raw.get("data", raw)
                spec_type = data.get("type", "")
                # 从 spec type 提取 model hint
                # type = "urn:miot-spec-v2:device:fan:0000A005:dmaker-p221:1"
                parts = spec_type.split(":")
                if len(parts) >= 6:
                    model_hint = parts[5].replace("-", ".")
                    spec = MiotSpec(model_hint, data)
                    self._specs[model_hint] = spec
                    logger.debug("Loaded spec for %s (%d services)", model_hint, len(spec.services))
            except Exception as e:
                logger.warning("Failed to load spec %s: %s", os.path.basename(f), e)
        logger.info("Loaded %d MIoT specs", len(self._specs))

    def _find_spec(self, model: str) -> Optional[MiotSpec]:
        """查找设备的 MIoT spec
        model 格式: brand.category.variant (如 chuangmi.camera.021a04)
        spec key 格式: brand.variant (如 chuangmi.021a04)
        """
        if model in self._specs:
            return self._specs[model]
        # 三段model → 两段spec key: brand.variant
        parts = model.split(".")
        if len(parts) >= 3:
            key2 = f"{parts[0]}.{parts[2]}"
            if key2 in self._specs:
                return self._specs[key2]
        # 模糊匹配: spec key 包含 model 的最后一段
        if len(parts) >= 2:
            variant = parts[-1]
            for key, spec in self._specs.items():
                if variant in key:
                    return spec
        return None

    def refresh_devices(self):
        """从小米云刷新设备列表"""
        if not self.mc:
            return
        country = self.credentials.get("server_country", "cn")
        try:
            devices = self.mc.get_devices(country=country) or []
            self._devices = devices
            self._device_map = {str(d["did"]): d for d in devices}
            self._last_refresh = time.time()
            logger.info("Refreshed %d devices from MiCloud", len(devices))
        except Exception as e:
            logger.error("Failed to refresh devices: %s", e)

    # ==================== 设备列表 ====================

    def get_devices(self, domain: Optional[str] = None) -> list:
        """获取归一化设备列表"""
        result = []
        for d in self._devices:
            model = d.get("model", "")
            spec = self._find_spec(model)
            dev_domain = classify_device(model, spec.type if spec else "")
            if domain and dev_domain != domain:
                continue

            device = {
                "id": str(d["did"]),
                "domain": dev_domain,
                "name": d.get("name", model),
                "model": model,
                "state": "unknown",  # 需要 RPC 查询
                "ip": d.get("localip", ""),
                "icon": "",
                "last_changed": "",
                "capabilities": [],
            }

            # 加载能力
            if spec:
                main_switch = spec.get_main_switch()
                if main_switch:
                    device["capabilities"].append("on_off")
                writable = spec.get_writable_props()
                for w in writable:
                    if w["name"] == "brightness":
                        device["capabilities"].append("brightness")
                    elif w["name"] == "color":
                        device["capabilities"].append("color")
                    elif w["name"] in ("fan_level", "fan-level"):
                        device["capabilities"].append("fan_speed")
                    elif w["name"] == "volume":
                        device["capabilities"].append("volume")
                actions = spec.get_actions()
                for a in actions:
                    if a["name"] == "play-text":
                        device["capabilities"].append("tts")
                    elif a["name"] in ("play", "pause") and "media_control" not in device["capabilities"]:
                        device["capabilities"].append("media_control")

            result.append(device)
        return result

    def get_device(self, did: str) -> Optional[dict]:
        """获取单个设备详情（含实时状态）"""
        d = self._device_map.get(did)
        if not d:
            return None

        model = d.get("model", "")
        spec = self._find_spec(model)
        dev_domain = classify_device(model, spec.type if spec else "")

        device = {
            "id": did,
            "domain": dev_domain,
            "name": d.get("name", model),
            "model": model,
            "ip": d.get("localip", ""),
            "icon": "",
            "capabilities": [],
            "properties": {},
            "actions": [],
        }

        if spec:
            # 读取所有可读属性
            readable = spec.get_readable_props()
            if readable:
                props_to_read = [{"did": did, "siid": p["siid"], "piid": p["piid"]} for p in readable[:20]]
                values = self._rpc_get_properties(props_to_read)
                for v in values:
                    key = f"s{v.get('siid', 0)}_p{v.get('piid', 0)}"
                    # 找到属性名
                    for p in readable:
                        if p["siid"] == v.get("siid") and p["piid"] == v.get("piid"):
                            key = f"{p['service']}.{p['name']}"
                            break
                    device["properties"][key] = v.get("value")

            # 推断 state
            main_switch = spec.get_main_switch()
            if main_switch:
                siid, piid = main_switch
                for p in readable:
                    if p["siid"] == siid and p["piid"] == piid:
                        key = f"{p['service']}.{p['name']}"
                        val = device["properties"].get(key)
                        device["state"] = "on" if val else "off"
                        break

            device["capabilities"] = [c for c in self._build_capabilities(spec)]
            device["actions"] = spec.get_actions()

        return device

    def _build_capabilities(self, spec: MiotSpec) -> list:
        caps = []
        if spec.get_main_switch():
            caps.append("on_off")
        for w in spec.get_writable_props():
            if w["name"] == "brightness":
                caps.append("brightness")
            elif w["name"] == "color":
                caps.append("color")
            elif "fan" in w["name"] and "level" in w["name"]:
                caps.append("fan_speed")
            elif w["name"] == "volume":
                caps.append("volume")
        for a in spec.get_actions():
            if a["name"] == "play-text":
                caps.append("tts")
            elif a["name"] in ("play", "pause"):
                caps.append("media_control")
        return list(set(caps))

    # ==================== RPC 操作 ====================

    def _rpc_get_properties(self, params: list) -> list:
        """MIoT Cloud RPC: 批量读取属性"""
        if not self.mc:
            return []
        url = f"{self.MIOT_API_BASE}/miotspec/prop/get"
        data = {"data": json.dumps({"params": params})}
        try:
            resp = self.mc.request(url, data)
            result = json.loads(resp)
            if result.get("code") == 0:
                return result.get("result", [])
            logger.warning("RPC get_properties failed: %s", result)
        except Exception as e:
            logger.error("RPC get_properties error: %s", e)
        return []

    def _rpc_set_property(self, did: str, siid: int, piid: int, value: Any) -> dict:
        """MIoT Cloud RPC: 设置单个属性。返回 {ok, error?, raw?}"""
        if not self.mc:
            return {"ok": False, "error": "MiCloud not connected"}
        url = f"{self.MIOT_API_BASE}/miotspec/prop/set"
        data = {"data": json.dumps({"params": [{"did": did, "siid": siid, "piid": piid, "value": value}]})}
        try:
            resp = self.mc.request(url, data)
            result = json.loads(resp)
            if result.get("code") == 0:
                items = result.get("result", [])
                failed = [i for i in items if i.get("code") != 0]
                if not failed:
                    return {"ok": True}
                err_code = failed[0].get('code', 0)
                msg = micloud_error_msg(err_code)
                logger.warning("RPC set_property item failed: %s -> %s", failed, msg)
                return {"ok": False, "error": msg, "raw": failed}
            err_code = result.get('code', 0)
            msg = micloud_error_msg(err_code)
            logger.warning("RPC set_property failed: %s -> %s", result, msg)
            return {"ok": False, "error": msg, "raw": result}
        except Exception as e:
            logger.error("RPC set_property error: %s", e)
            return {"ok": False, "error": str(e)}

    def _rpc_execute_action(self, did: str, siid: int, aiid: int, params: list = None) -> dict:
        """MIoT Cloud RPC: 执行动作。返回 {ok, error?, raw}"""
        if not self.mc:
            return {"ok": False, "error": "MiCloud not connected"}
        url = f"{self.MIOT_API_BASE}/miotspec/action"
        action_data = {"did": did, "siid": siid, "aiid": aiid}
        if params:
            action_data["in"] = params
        data = {"data": json.dumps({"params": action_data})}
        try:
            resp = self.mc.request(url, data)
            raw = json.loads(resp)
            # 检查外层 code
            if raw.get("code") != 0:
                msg = micloud_error_msg(raw.get("code", -1))
                logger.warning("RPC action failed (outer): %s", msg)
                return {"ok": False, "error": msg, "raw": raw}
            # 检查内层 result.code (设备实际执行结果)
            inner = raw.get("result", {})
            inner_code = inner.get("code", 0) if isinstance(inner, dict) else 0
            if inner_code != 0:
                msg = micloud_error_msg(inner_code)
                logger.warning("RPC action failed (device): %s", msg)
                return {"ok": False, "error": msg, "raw": raw}
            return {"ok": True, "raw": raw}
        except Exception as e:
            logger.error("RPC execute_action error: %s", e)
            return {"ok": False, "error": str(e)}

    # ==================== 音箱回退（无 spec 时） ====================

    def _speaker_fallback(self, did: str, action: str, value: Any, extra: dict, fb: dict) -> dict:
        """使用硬编码 SIID/AIID 回退表控制音箱，不依赖 spec 文件"""
        if action == "execute_command":
            mapping = fb.get("execute-text-directive")
            if mapping:
                cmd = str(value) if value else ""
                silent = (extra or {}).get("silent", False)
                result = self._rpc_execute_action(did, mapping[0], mapping[1], [cmd, silent])
                return {**result, "action": "execute_command", "fallback": True}
        elif action in ("play_text", "tts"):
            mapping = fb.get("play-text")
            if mapping:
                text = str(value) if value else ""
                result = self._rpc_execute_action(did, mapping[0], mapping[1], [text])
                return {**result, "action": "play_text", "fallback": True}
        elif action == "set_volume":
            mapping = fb.get("volume")
            if mapping and len(mapping) >= 3 and mapping[2] == "prop":
                result = self._rpc_set_property(did, mapping[0], mapping[1], int(value))
                return {**result, "action": "set_volume", "fallback": True}
        return {"ok": False, "error": f"No fallback for action {action}"}

    # ==================== 高级控制 ====================

    def control_device(self, did: str, action: str, value: Any = None, extra: dict = None) -> dict:
        """统一设备控制接口"""
        d = self._device_map.get(did)
        if not d:
            return {"ok": False, "error": f"Device {did} not found"}

        model = d.get("model", "")
        spec = self._find_spec(model)

        # 无 spec 时尝试音箱回退表（去 HA 依赖核心）
        if not spec and action in ("execute_command", "play_text", "tts", "set_volume"):
            hw = _get_hardware(model)
            fb = SPEAKER_ACTION_FALLBACK.get(hw, _SPEAKER_DEFAULT if "speaker" in model else None)
            if fb:
                return self._speaker_fallback(did, action, value, extra, fb)
        if not spec:
            return {"ok": False, "error": f"No spec for model {model}"}

        if action == "turn_on":
            sw = spec.get_main_switch()
            if sw:
                result = self._rpc_set_property(did, sw[0], sw[1], True)
                return {**result, "action": "turn_on"}
        elif action == "turn_off":
            sw = spec.get_main_switch()
            if sw:
                result = self._rpc_set_property(did, sw[0], sw[1], False)
                return {**result, "action": "turn_off"}
        elif action == "toggle":
            sw = spec.get_main_switch()
            if sw:
                # 读当前值再反转
                vals = self._rpc_get_properties([{"did": did, "siid": sw[0], "piid": sw[1]}])
                current = vals[0].get("value", False) if vals else False
                result = self._rpc_set_property(did, sw[0], sw[1], not current)
                return {**result, "action": "toggle", "new_state": not current}
        elif action == "set_brightness":
            # 找 brightness 属性
            for siid, svc in spec.services.items():
                for piid, prop in svc.properties.items():
                    if prop.name == "brightness" and prop.writable:
                        result = self._rpc_set_property(did, siid, piid, int(value))
                        return {**result, "action": "set_brightness"}
        elif action == "set_color":
            for siid, svc in spec.services.items():
                for piid, prop in svc.properties.items():
                    if prop.name == "color" and prop.writable:
                        result = self._rpc_set_property(did, siid, piid, int(value))
                        return {**result, "action": "set_color"}
        elif action == "set_fan_speed" or action == "set_percentage":
            for siid, svc in spec.services.items():
                for piid, prop in svc.properties.items():
                    if "fan" in prop.name and "level" in prop.name and prop.writable:
                        result = self._rpc_set_property(did, siid, piid, int(value))
                        return {**result, "action": "set_fan_speed"}
        elif action == "set_volume":
            for siid, svc in spec.services.items():
                for piid, prop in svc.properties.items():
                    if prop.name == "volume" and prop.writable:
                        result = self._rpc_set_property(did, siid, piid, int(value))
                        return {**result, "action": "set_volume"}
        elif action == "play_text" or action == "tts":
            # 找 intelligent-speaker 的 play-text action
            for siid, svc in spec.services.items():
                for aiid, act in svc.actions.items():
                    if act.name == "play-text":
                        text = str(value) if value else ""
                        result = self._rpc_execute_action(did, siid, aiid, [text])
                        return {**result, "action": "play_text"}
        elif action == "execute_command":
            # 找 intelligent-speaker 的 execute-text-directive
            for siid, svc in spec.services.items():
                for aiid, act in svc.actions.items():
                    if act.name == "execute-text-directive":
                        cmd = str(value) if value else ""
                        silent = (extra or {}).get("silent", False)
                        result = self._rpc_execute_action(did, siid, aiid, [cmd, silent])
                        return {**result, "action": "execute_command"}
        elif action == "set_property":
            # 直接设置属性 (高级模式)
            siid = (extra or {}).get("siid", 2)
            piid = (extra or {}).get("piid", 1)
            result = self._rpc_set_property(did, siid, piid, value)
            return {**result, "action": "set_property", "siid": siid, "piid": piid}
        elif action in ("play", "pause", "next", "previous", "stop"):
            # 找对应的 action
            for siid, svc in spec.services.items():
                for aiid, act in svc.actions.items():
                    if act.name == action:
                        result = self._rpc_execute_action(did, siid, aiid)
                        return {**result, "action": action}

        return {"ok": False, "error": f"Unsupported action '{action}' for model {model}"}

    def get_device_status(self, did: str) -> dict:
        """快速获取设备开关状态"""
        d = self._device_map.get(did)
        if not d:
            return {"state": "unknown"}
        model = d.get("model", "")
        spec = self._find_spec(model)
        if not spec:
            return {"state": "unknown"}
        sw = spec.get_main_switch()
        if not sw:
            return {"state": "unknown"}
        vals = self._rpc_get_properties([{"did": did, "siid": sw[0], "piid": sw[1]}])
        if vals and vals[0].get("code") == 0:
            return {"state": "on" if vals[0].get("value") else "off"}
        return {"state": "unavailable"}

    # ==================== 批量操作 ====================

    def batch_get_status(self, dids: list = None) -> dict:
        """批量获取多设备状态"""
        if dids is None:
            dids = list(self._device_map.keys())
        results = {}
        for did in dids:
            results[did] = self.get_device_status(did)
        return results

    def quick_action(self, action: str) -> dict:
        """快捷操作: all_off, lights_off, fans_off 等"""
        affected = []
        for d in self._devices:
            model = d.get("model", "")
            domain = classify_device(model)
            did = str(d["did"])
            if action == "all_off" and domain in ("switch", "light", "fan"):
                result = self.control_device(did, "turn_off")
                affected.append({"did": did, "name": d.get("name", ""), **result})
            elif action == "lights_off" and domain == "light":
                result = self.control_device(did, "turn_off")
                affected.append({"did": did, "name": d.get("name", ""), **result})
            elif action == "fans_off" and domain == "fan":
                result = self.control_device(did, "turn_off")
                affected.append({"did": did, "name": d.get("name", ""), **result})
        return {"action": action, "affected": len(affected), "results": affected}


# ============================================================
# 凭据加载 — 三级链: config直填 → 自缓存 → HA回退
# ============================================================
GATEWAY_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_CACHE_FILE = os.path.join(GATEWAY_DIR, ".xiaomi_token_cache.json")


def save_credentials_cache(creds: dict):
    """保存凭据到自管理缓存（不依赖HA）"""
    try:
        cache = {k: creds[k] for k in ("user_id", "service_token", "ssecurity", "server_country")
                 if k in creds}
        cache["_ts"] = int(time.time())
        with open(TOKEN_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
        logger.info("Saved credentials cache to %s", TOKEN_CACHE_FILE)
    except Exception as e:
        logger.warning("Failed to save credentials cache: %s", e)


def load_credentials_standalone(mi_cfg: dict) -> Optional[dict]:
    """三级凭据链，按优先级尝试:
    L1: config.json 中直接填写的 token (user_id + service_token + ssecurity)
    L2: 自管理缓存文件 (.xiaomi_token_cache.json)
    L3: HA 配置回退 (ha_config_path)
    """
    # --- L1: config.json 直填 token ---
    if mi_cfg.get("user_id") and mi_cfg.get("service_token"):
        logger.info("[L1] Using credentials from config.json (user_id=%s)", mi_cfg["user_id"])
        creds = {
            "user_id": mi_cfg["user_id"],
            "service_token": mi_cfg["service_token"],
            "ssecurity": mi_cfg.get("ssecurity", ""),
            "server_country": mi_cfg.get("server", "cn"),
            "username": mi_cfg.get("username", ""),
            "password": mi_cfg.get("password", ""),
        }
        save_credentials_cache(creds)
        return creds

    # --- L2: 自管理缓存文件 ---
    if os.path.exists(TOKEN_CACHE_FILE):
        try:
            with open(TOKEN_CACHE_FILE, encoding="utf-8") as f:
                cache = json.load(f)
            if cache.get("user_id") and cache.get("service_token"):
                age_hours = (time.time() - cache.get("_ts", 0)) / 3600
                logger.info("[L2] Using cached credentials (age=%.1fh, user_id=%s)",
                           age_hours, cache["user_id"])
                cache["username"] = mi_cfg.get("username", "")
                cache["password"] = mi_cfg.get("password", "")
                return cache
        except Exception as e:
            logger.warning("[L2] Failed to load cache: %s", e)

    # --- L3: HA 配置回退 ---
    ha_path = mi_cfg.get("ha_config_path", "")
    if ha_path:
        creds = load_credentials_from_ha(ha_path)
        if creds:
            logger.info("[L3] Using credentials from HA config")
            creds["username"] = mi_cfg.get("username", creds.get("username", ""))
            creds["password"] = mi_cfg.get("password", creds.get("password", ""))
            save_credentials_cache(creds)
            return creds

    logger.warning("No credentials found from any source (config/cache/HA)")
    return None


def load_credentials_from_ha(ha_config_path: str = r"E:\HassWP\config") -> Optional[dict]:
    """从 HA 的 .storage/core.config_entries 提取小米云凭据（L3回退）"""
    entries_file = os.path.join(ha_config_path, ".storage", "core.config_entries")
    if not os.path.exists(entries_file):
        logger.warning("HA config entries not found: %s", entries_file)
        return None
    try:
        with open(entries_file, encoding="utf-8") as f:
            data = json.load(f)
        for entry in data.get("data", {}).get("entries", []):
            if entry.get("domain") == "xiaomi_miot":
                creds = entry.get("data", {})
                logger.info("Found xiaomi_miot credentials for user %s", creds.get("user_id"))
                return creds
    except Exception as e:
        logger.error("Failed to load HA config: %s", e)
    return None
