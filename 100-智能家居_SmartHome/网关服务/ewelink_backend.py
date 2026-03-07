"""
eWeLink Direct Backend — 直接调用 CoolKit v2 API 控制 Sonoff/eWeLink 设备
不依赖 Home Assistant，只需 eWeLink 开发者凭据 + 用户账号

注册地址: https://dev.ewelink.cc
免费支持品牌: SONOFF, sonoff, 嵩诺, coolkit

API 基础:
  - 登录: POST /v2/user/login
  - 设备列表: GET /v2/device/thing
  - 设备状态: GET /v2/device/thing/status
  - 控制设备: POST /v2/device/thing/status
  - 刷新Token: POST /v2/user/refresh
"""

import hmac
import hashlib
import json
import time
import string
import random
import logging
from typing import Optional, Any

import httpx

logger = logging.getLogger(__name__)

REGION_URLS = {
    "cn": "https://cn-apia.coolkit.cn",
    "as": "https://as-apia.coolkit.cc",
    "us": "https://us-apia.coolkit.cc",
    "eu": "https://eu-apia.coolkit.cc",
}


class EWeLinkClient:
    """eWeLink CoolKit v2 API 客户端"""

    def __init__(self, app_id: str, app_secret: str, region: str = "cn"):
        self.app_id = app_id
        self.app_secret = app_secret
        self.base_url = REGION_URLS.get(region, REGION_URLS["cn"])
        self.region = region
        self.at = ""  # access token
        self.rt = ""  # refresh token
        self.user_api_key = ""
        self.token_expire = 0
        self._client: Optional[httpx.AsyncClient] = None
        self._devices: list = []
        self._device_map: dict = {}  # deviceid -> device info

    @property
    def enabled(self) -> bool:
        return bool(self.app_id and self.app_secret)

    async def init(self):
        self._client = httpx.AsyncClient(timeout=15.0)

    async def close(self):
        if self._client:
            await self._client.aclose()

    @property
    def client(self) -> httpx.AsyncClient:
        assert self._client is not None
        return self._client

    @staticmethod
    def _nonce(length: int = 8) -> str:
        return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))

    def _sign(self, payload: str) -> str:
        return hmac.new(
            self.app_secret.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()

    def _base_headers(self) -> dict:
        return {
            "X-CK-Appid": self.app_id,
            "X-CK-Nonce": self._nonce(),
            "Content-Type": "application/json",
        }

    # ==================== 认证 ====================

    async def login(self, email: str = "", password: str = "",
                    phone: str = "", country_code: str = "+86") -> bool:
        """登录 eWeLink 账号"""
        body = {"countryCode": country_code, "password": password}
        if email:
            body["email"] = email
        elif phone:
            body["phoneNumber"] = phone
        else:
            logger.error("Must provide email or phone")
            return False

        body_str = json.dumps(body, separators=(",", ":"))
        headers = self._base_headers()
        headers["Authorization"] = f"Sign {self._sign(body_str)}"

        try:
            resp = await self.client.post(
                f"{self.base_url}/v2/user/login",
                content=body_str,
                headers=headers,
            )
            data = resp.json()
            if data.get("error") == 0:
                self.at = data["data"]["at"]
                self.rt = data["data"]["rt"]
                self.user_api_key = data["data"]["user"]["apikey"]
                self.token_expire = time.time() + 86400 * 29  # ~30 days
                logger.info("eWeLink login success, user: %s", data["data"]["user"].get("email", ""))
                return True
            else:
                logger.error("eWeLink login failed: error=%s, msg=%s",
                             data.get("error"), data.get("msg", data.get("message", "")))
                return False
        except Exception as e:
            logger.error("eWeLink login error: %s", e)
            return False

    async def refresh_token(self) -> bool:
        """刷新 access token"""
        if not self.rt:
            return False
        headers = self._base_headers()
        headers["Authorization"] = f"Bearer {self.at}"
        try:
            resp = await self.client.post(
                f"{self.base_url}/v2/user/refresh",
                json={"rt": self.rt},
                headers=headers,
            )
            data = resp.json()
            if data.get("error") == 0:
                self.at = data["data"]["at"]
                self.rt = data["data"]["rt"]
                self.token_expire = time.time() + 86400 * 29
                logger.info("eWeLink token refreshed")
                return True
        except Exception as e:
            logger.error("eWeLink refresh error: %s", e)
        return False

    async def _ensure_token(self):
        if time.time() > self.token_expire and self.rt:
            await self.refresh_token()

    def _auth_headers(self) -> dict:
        headers = self._base_headers()
        headers["Authorization"] = f"Bearer {self.at}"
        return headers

    # ==================== 设备管理 ====================

    async def fetch_devices(self) -> list:
        """获取设备列表"""
        await self._ensure_token()
        try:
            resp = await self.client.get(
                f"{self.base_url}/v2/device/thing",
                headers=self._auth_headers(),
            )
            data = resp.json()
            if data.get("error") == 0:
                things = data.get("data", {}).get("thingList", [])
                devices = []
                for thing in things:
                    item = thing.get("itemData", {})
                    if item:
                        devices.append(item)
                self._devices = devices
                self._device_map = {d["deviceid"]: d for d in devices}
                logger.info("eWeLink: fetched %d devices", len(devices))
                return devices
            else:
                logger.error("eWeLink fetch devices failed: %s", data.get("msg", ""))
        except Exception as e:
            logger.error("eWeLink fetch devices error: %s", e)
        return []

    def get_devices(self, domain: Optional[str] = None) -> list:
        """获取归一化设备列表"""
        result = []
        for d in self._devices:
            dev = self._normalize(d)
            if domain and dev["domain"] != domain:
                continue
            result.append(dev)
        return result

    def get_device(self, device_id: str) -> Optional[dict]:
        """获取单个设备详情"""
        d = self._device_map.get(device_id)
        if not d:
            return None
        return self._normalize(d)

    def _normalize(self, d: dict) -> dict:
        """将 eWeLink 设备转换为统一格式"""
        params = d.get("params", {})
        device_id = d["deviceid"]
        name = d.get("name", device_id)
        brand = d.get("brandName", "")
        model = d.get("productModel", "")

        # 判断设备类型
        uiid = d.get("extra", {}).get("uiid", 0)
        channels = self._get_channel_count(uiid, params)

        # 状态
        if channels == 1:
            state = params.get("switch", "unknown")
        else:
            switches = params.get("switches", [])
            on_count = sum(1 for s in switches if s.get("switch") == "on")
            state = "on" if on_count > 0 else "off"

        device = {
            "id": device_id,
            "domain": "switch",
            "name": name,
            "model": f"{brand} {model}".strip(),
            "state": state,
            "icon": "",
            "last_changed": d.get("params", {}).get("staMac", ""),
            "source": "ewelink",
            "capabilities": ["on_off"],
        }

        if channels > 1:
            device["channels"] = channels
            device["switches"] = [
                {"outlet": s.get("outlet", i), "switch": s.get("switch", "off")}
                for i, s in enumerate(params.get("switches", [])[:channels])
            ]

        # 功率监控
        if "power" in params:
            device["power"] = params.get("power")
            device["capabilities"].append("power_monitor")
        if "voltage" in params:
            device["voltage"] = params.get("voltage")
        if "current" in params:
            device["current"] = params.get("current")

        return device

    @staticmethod
    def _get_channel_count(uiid: int, params: dict) -> int:
        """根据 UIID 判断通道数"""
        # 常见 UIID: 1=单通道, 2=双通道, 3=三通道, 4=四通道, 6=单通道(功率), 77=单通道(功率v2)
        multi_channel_uiids = {2: 2, 3: 3, 4: 4, 7: 2, 8: 3, 9: 4}
        if uiid in multi_channel_uiids:
            return multi_channel_uiids[uiid]
        if "switches" in params and len(params["switches"]) > 1:
            return len(params["switches"])
        return 1

    # ==================== 设备控制 ====================

    async def control_device(self, device_id: str, action: str,
                             value: Any = None, extra: dict = None) -> dict:
        """统一设备控制接口"""
        d = self._device_map.get(device_id)
        if not d:
            return {"ok": False, "error": f"Device {device_id} not found"}

        params = {}
        uiid = d.get("extra", {}).get("uiid", 0)
        channels = self._get_channel_count(uiid, d.get("params", {}))

        if action == "turn_on":
            if channels == 1:
                params = {"switch": "on"}
            else:
                outlet = (extra or {}).get("outlet", 0)
                params = self._build_switch_params(d, outlet, "on")
        elif action == "turn_off":
            if channels == 1:
                params = {"switch": "off"}
            else:
                outlet = (extra or {}).get("outlet", 0)
                params = self._build_switch_params(d, outlet, "off")
        elif action == "toggle":
            if channels == 1:
                current = d.get("params", {}).get("switch", "off")
                params = {"switch": "off" if current == "on" else "on"}
            else:
                outlet = (extra or {}).get("outlet", 0)
                switches = d.get("params", {}).get("switches", [])
                for s in switches:
                    if s.get("outlet") == outlet:
                        new_state = "off" if s.get("switch") == "on" else "on"
                        params = self._build_switch_params(d, outlet, new_state)
                        break
        elif action == "all_on":
            if channels > 1:
                params = {"switches": [{"switch": "on", "outlet": i} for i in range(channels)]}
            else:
                params = {"switch": "on"}
        elif action == "all_off":
            if channels > 1:
                params = {"switches": [{"switch": "off", "outlet": i} for i in range(channels)]}
            else:
                params = {"switch": "off"}
        else:
            return {"ok": False, "error": f"Unsupported action: {action}"}

        if not params:
            return {"ok": False, "error": "Failed to build control params"}

        return await self._send_control(device_id, params)

    def _build_switch_params(self, device: dict, outlet: int, state: str) -> dict:
        """构建多通道开关参数"""
        switches = list(device.get("params", {}).get("switches", []))
        updated = False
        for s in switches:
            if s.get("outlet") == outlet:
                s["switch"] = state
                updated = True
                break
        if not updated:
            switches.append({"switch": state, "outlet": outlet})
        return {"switches": switches}

    async def _send_control(self, device_id: str, params: dict) -> dict:
        """发送控制命令到 eWeLink API"""
        await self._ensure_token()
        body = {
            "type": 1,
            "id": device_id,
            "params": params,
        }
        try:
            resp = await self.client.post(
                f"{self.base_url}/v2/device/thing/status",
                json=body,
                headers=self._auth_headers(),
            )
            data = resp.json()
            if data.get("error") == 0:
                # 更新本地缓存
                if device_id in self._device_map:
                    self._device_map[device_id].setdefault("params", {}).update(params)
                return {"ok": True, "action": "control", "params": params}
            else:
                return {"ok": False, "error": data.get("msg", f"error {data.get('error')}")}
        except Exception as e:
            logger.error("eWeLink control error: %s", e)
            return {"ok": False, "error": str(e)}

    # ==================== 批量操作 ====================

    def quick_action(self, action: str) -> dict:
        """快捷操作(同步标记,异步执行需外部await)"""
        targets = []
        for d in self._devices:
            dev = self._normalize(d)
            if action == "all_off" and dev["state"] == "on":
                targets.append(d["deviceid"])
            elif action == "all_on" and dev["state"] == "off":
                targets.append(d["deviceid"])
        return {"action": action, "targets": targets}

    async def execute_quick_action(self, action: str) -> dict:
        """执行快捷操作"""
        info = self.quick_action(action)
        results = []
        ctrl_action = "turn_off" if "off" in action else "turn_on"
        for did in info["targets"]:
            result = await self.control_device(did, ctrl_action)
            results.append({"device_id": did, **result})
        return {"action": action, "affected": len(results), "results": results}
