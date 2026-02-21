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
        """初始化 micloud 客户端"""
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
        self._load_specs()
        self.refresh_devices()

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
                    elif a["name"] in ("play", "pause"):
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

    def _rpc_set_property(self, did: str, siid: int, piid: int, value: Any) -> bool:
        """MIoT Cloud RPC: 设置单个属性"""
        if not self.mc:
            return False
        url = f"{self.MIOT_API_BASE}/miotspec/prop/set"
        data = {"data": json.dumps({"params": [{"did": did, "siid": siid, "piid": piid, "value": value}]})}
        try:
            resp = self.mc.request(url, data)
            result = json.loads(resp)
            if result.get("code") == 0:
                items = result.get("result", [])
                return all(i.get("code") == 0 for i in items)
            logger.warning("RPC set_property failed: %s", result)
        except Exception as e:
            logger.error("RPC set_property error: %s", e)
        return False

    def _rpc_execute_action(self, did: str, siid: int, aiid: int, params: list = None) -> dict:
        """MIoT Cloud RPC: 执行动作"""
        if not self.mc:
            return {"code": -1, "message": "not connected"}
        url = f"{self.MIOT_API_BASE}/miotspec/action"
        action_data = {"did": did, "siid": siid, "aiid": aiid}
        if params:
            action_data["in"] = params
        data = {"data": json.dumps({"params": action_data})}
        try:
            resp = self.mc.request(url, data)
            return json.loads(resp)
        except Exception as e:
            logger.error("RPC execute_action error: %s", e)
            return {"code": -1, "message": str(e)}

    # ==================== 高级控制 ====================

    def control_device(self, did: str, action: str, value: Any = None, extra: dict = None) -> dict:
        """统一设备控制接口"""
        d = self._device_map.get(did)
        if not d:
            return {"ok": False, "error": f"Device {did} not found"}

        model = d.get("model", "")
        spec = self._find_spec(model)
        if not spec:
            return {"ok": False, "error": f"No spec for model {model}"}

        if action == "turn_on":
            sw = spec.get_main_switch()
            if sw:
                ok = self._rpc_set_property(did, sw[0], sw[1], True)
                return {"ok": ok, "action": "turn_on"}
        elif action == "turn_off":
            sw = spec.get_main_switch()
            if sw:
                ok = self._rpc_set_property(did, sw[0], sw[1], False)
                return {"ok": ok, "action": "turn_off"}
        elif action == "toggle":
            sw = spec.get_main_switch()
            if sw:
                # 读当前值再反转
                vals = self._rpc_get_properties([{"did": did, "siid": sw[0], "piid": sw[1]}])
                current = vals[0].get("value", False) if vals else False
                ok = self._rpc_set_property(did, sw[0], sw[1], not current)
                return {"ok": ok, "action": "toggle", "new_state": not current}
        elif action == "set_brightness":
            # 找 brightness 属性
            for siid, svc in spec.services.items():
                for piid, prop in svc.properties.items():
                    if prop.name == "brightness" and prop.writable:
                        ok = self._rpc_set_property(did, siid, piid, int(value))
                        return {"ok": ok, "action": "set_brightness"}
        elif action == "set_color":
            for siid, svc in spec.services.items():
                for piid, prop in svc.properties.items():
                    if prop.name == "color" and prop.writable:
                        ok = self._rpc_set_property(did, siid, piid, int(value))
                        return {"ok": ok, "action": "set_color"}
        elif action == "set_fan_speed" or action == "set_percentage":
            for siid, svc in spec.services.items():
                for piid, prop in svc.properties.items():
                    if "fan" in prop.name and "level" in prop.name and prop.writable:
                        ok = self._rpc_set_property(did, siid, piid, int(value))
                        return {"ok": ok, "action": "set_fan_speed"}
        elif action == "set_volume":
            for siid, svc in spec.services.items():
                for piid, prop in svc.properties.items():
                    if prop.name == "volume" and prop.writable:
                        ok = self._rpc_set_property(did, siid, piid, int(value))
                        return {"ok": ok, "action": "set_volume"}
        elif action == "play_text" or action == "tts":
            # 找 intelligent-speaker 的 play-text action
            for siid, svc in spec.services.items():
                for aiid, act in svc.actions.items():
                    if act.name == "play-text":
                        text = str(value) if value else ""
                        result = self._rpc_execute_action(did, siid, aiid, [text])
                        return {"ok": result.get("code") == 0, "action": "play_text", "result": result}
        elif action == "execute_command":
            # 找 intelligent-speaker 的 execute-text-directive
            for siid, svc in spec.services.items():
                for aiid, act in svc.actions.items():
                    if act.name == "execute-text-directive":
                        cmd = str(value) if value else ""
                        silent = (extra or {}).get("silent", False)
                        result = self._rpc_execute_action(did, siid, aiid, [cmd, silent])
                        return {"ok": result.get("code") == 0, "action": "execute_command", "result": result}
        elif action == "set_property":
            # 直接设置属性 (高级模式)
            siid = (extra or {}).get("siid", 2)
            piid = (extra or {}).get("piid", 1)
            ok = self._rpc_set_property(did, siid, piid, value)
            return {"ok": ok, "action": "set_property", "siid": siid, "piid": piid}
        elif action in ("play", "pause", "next", "previous", "stop"):
            # 找对应的 action
            for siid, svc in spec.services.items():
                for aiid, act in svc.actions.items():
                    if act.name == action:
                        result = self._rpc_execute_action(did, siid, aiid)
                        return {"ok": result.get("code") == 0, "action": action, "result": result}

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
# 从 HA 配置加载凭据
# ============================================================
def load_credentials_from_ha(ha_config_path: str = r"E:\HassWP\config") -> Optional[dict]:
    """从 HA 的 .storage/core.config_entries 提取小米云凭据"""
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
