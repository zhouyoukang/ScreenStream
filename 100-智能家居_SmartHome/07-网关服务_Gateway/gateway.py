#!/usr/bin/env python3
"""
Smart Home Gateway — 统一智能家居 API 网关
支持双模式:
  - direct: 直连小米云 API (MiCloud)，不依赖 HA
  - ha: 以 Home Assistant 为中枢
端口: 8900

API 概览:
  GET  /                     — 网关状态
  GET  /devices              — 所有设备列表
  GET  /devices/{id}         — 单个设备详情
  POST /devices/{id}/control — 控制设备
  GET  /scenes               — 场景列表
  POST /scenes/{id}/activate — 触发场景
  GET  /rooms                — 房间/区域列表
  POST /batch                — 批量控制
  GET  /history/{entity_id}  — 历史记录 (HA mode only)
  POST /template             — HA模板渲染 (HA mode only)
  POST /quick/{action}       — 快捷操作: all_off, lights_off, etc.

  # MiCloud 直连 (direct mode)
  GET  /micloud/status        — MiCloud 连接状态
  POST /micloud/rpc           — 原始 MIoT RPC 调用
  POST /micloud/tts           — 小爱音箱 TTS

  # 涂鸦直连 (可选)
  GET  /tuya/devices          — 涂鸦设备列表
  POST /tuya/devices/{id}/cmd — 涂鸦设备控制
"""

import os
import sys
import time
import hmac
import hashlib
import json
import asyncio
from typing import Optional, Any
from contextlib import asynccontextmanager

import logging
import argparse

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from micloud_backend import MiCloudDirect, load_credentials_from_ha

load_dotenv()
logger = logging.getLogger(__name__)

# ============================================================
# Configuration
# ============================================================
HA_URL = os.getenv("HA_URL", "http://192.168.31.228:8123")
HA_TOKEN = os.getenv("HA_TOKEN", "")

TUYA_CLIENT_ID = os.getenv("TUYA_CLIENT_ID", "")
TUYA_SECRET = os.getenv("TUYA_SECRET", "")
TUYA_REGION = os.getenv("TUYA_REGION", "cn")
TUYA_BASE_URLS = {
    "cn": "https://openapi.tuyacn.com",
    "us": "https://openapi.tuyaus.com",
    "eu": "https://openapi.tuyaeu.com",
    "in": "https://openapi.tuyain.com",
}

GATEWAY_HOST = os.getenv("GATEWAY_HOST", "0.0.0.0")
GATEWAY_PORT = int(os.getenv("GATEWAY_PORT", "8900"))

# Mode: "direct" (MiCloud direct) or "ha" (Home Assistant proxy)
GATEWAY_MODE = os.getenv("GATEWAY_MODE", "direct")

# MiCloud config
HA_CONFIG_PATH = os.getenv("HA_CONFIG_PATH", r"E:\HassWP\config")
MIOT_SPEC_DIR = os.path.join(HA_CONFIG_PATH, ".storage", "xiaomi_miot")


# ============================================================
# Home Assistant Client
# ============================================================
class HAClient:
    """Home Assistant REST API 客户端"""

    def __init__(self, url: str, token: str):
        self.url = url.rstrip("/")
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        self._client: Optional[httpx.AsyncClient] = None

    async def init(self):
        self._client = httpx.AsyncClient(timeout=15.0)

    async def close(self):
        if self._client:
            await self._client.aclose()

    @property
    def client(self) -> httpx.AsyncClient:
        assert self._client is not None
        return self._client

    async def check(self) -> dict:
        try:
            resp = await self.client.get(f"{self.url}/api/", headers=self.headers)
            return {"connected": resp.status_code == 200, "status": resp.status_code}
        except Exception as e:
            return {"connected": False, "error": str(e)}

    async def get_states(self) -> list:
        resp = await self.client.get(f"{self.url}/api/states", headers=self.headers)
        resp.raise_for_status()
        return resp.json()

    async def get_state(self, entity_id: str) -> dict:
        resp = await self.client.get(f"{self.url}/api/states/{entity_id}", headers=self.headers)
        resp.raise_for_status()
        return resp.json()

    async def call_service(self, domain: str, service: str, data: dict) -> list:
        resp = await self.client.post(
            f"{self.url}/api/services/{domain}/{service}",
            headers=self.headers,
            json=data,
        )
        resp.raise_for_status()
        return resp.json()

    async def get_services(self) -> list:
        resp = await self.client.get(f"{self.url}/api/services", headers=self.headers)
        resp.raise_for_status()
        return resp.json()

    async def get_config(self) -> dict:
        resp = await self.client.get(f"{self.url}/api/config", headers=self.headers)
        resp.raise_for_status()
        return resp.json()

    async def render_template(self, template: str) -> str:
        resp = await self.client.post(
            f"{self.url}/api/template",
            headers=self.headers,
            json={"template": template},
        )
        resp.raise_for_status()
        return resp.text

    async def get_history(self, entity_id: str, hours: int = 24) -> list:
        from datetime import datetime, timedelta, timezone
        start = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        resp = await self.client.get(
            f"{self.url}/api/history/period/{start}",
            headers=self.headers,
            params={"filter_entity_id": entity_id, "minimal_response": ""},
        )
        resp.raise_for_status()
        return resp.json()

    async def fire_event(self, event_type: str, data: dict) -> dict:
        resp = await self.client.post(
            f"{self.url}/api/events/{event_type}",
            headers=self.headers,
            json=data,
        )
        resp.raise_for_status()
        return resp.json()


# ============================================================
# Tuya Cloud Client (可选)
# ============================================================
class TuyaClient:
    """涂鸦 Cloud API 客户端"""

    def __init__(self, client_id: str, secret: str, region: str = "cn"):
        self.client_id = client_id
        self.secret = secret
        self.base_url = TUYA_BASE_URLS.get(region, TUYA_BASE_URLS["cn"])
        self.access_token = ""
        self.token_expire = 0
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def enabled(self) -> bool:
        return bool(self.client_id and self.secret)

    async def init(self):
        self._client = httpx.AsyncClient(timeout=15.0)
        if self.enabled:
            await self._refresh_token()

    async def close(self):
        if self._client:
            await self._client.aclose()

    @property
    def client(self) -> httpx.AsyncClient:
        assert self._client is not None
        return self._client

    def _sign(self, payload: str) -> tuple:
        t = str(int(time.time() * 1000))
        sign_str = self.client_id + payload + t
        sign = hmac.new(
            self.secret.encode(), sign_str.encode(), hashlib.sha256
        ).hexdigest().upper()
        return sign, t

    async def _refresh_token(self):
        sign, t = self._sign("")
        headers = {
            "client_id": self.client_id,
            "sign": sign,
            "t": t,
            "sign_method": "HMAC-SHA256",
        }
        resp = await self.client.get(
            f"{self.base_url}/v1.0/token?grant_type=1", headers=headers
        )
        data = resp.json()
        if data.get("success"):
            self.access_token = data["result"]["access_token"]
            self.token_expire = time.time() + data["result"]["expire_time"] - 60
        else:
            raise Exception(f"Tuya token error: {data}")

    async def _ensure_token(self):
        if time.time() > self.token_expire:
            await self._refresh_token()

    async def _request(self, method: str, path: str, body: dict = None) -> dict:
        await self._ensure_token()
        sign, t = self._sign(self.access_token)
        headers = {
            "client_id": self.client_id,
            "access_token": self.access_token,
            "sign": sign,
            "t": t,
            "sign_method": "HMAC-SHA256",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}{path}"
        if method == "GET":
            resp = await self.client.get(url, headers=headers)
        else:
            resp = await self.client.post(url, headers=headers, json=body or {})
        return resp.json()

    async def get_devices(self) -> dict:
        return await self._request("GET", "/v1.0/iot-01/associated-users/devices")

    async def get_device_status(self, device_id: str) -> dict:
        return await self._request("GET", f"/v1.0/devices/{device_id}/status")

    async def send_commands(self, device_id: str, commands: list) -> dict:
        return await self._request(
            "POST",
            f"/v1.0/devices/{device_id}/commands",
            {"commands": commands},
        )

    async def get_device_functions(self, device_id: str) -> dict:
        return await self._request("GET", f"/v1.0/devices/{device_id}/functions")


# ============================================================
# Pydantic Models
# ============================================================
class ControlRequest(BaseModel):
    action: str  # turn_on, turn_off, toggle, set_brightness, set_temperature, etc.
    value: Optional[Any] = None
    extra: Optional[dict] = None

class BatchControlRequest(BaseModel):
    commands: list[dict]  # [{"entity_id": "...", "action": "turn_on", "value": ...}, ...]

class TuyaCommandRequest(BaseModel):
    commands: list[dict]  # [{"code": "switch_1", "value": true}, ...]

class TemplateRequest(BaseModel):
    template: str


# ============================================================
# Device normalization
# ============================================================
DEVICE_DOMAINS = {"switch", "light", "fan", "climate", "cover", "media_player",
                  "vacuum", "lock", "sensor", "binary_sensor", "automation", "scene",
                  "script", "input_boolean", "humidifier", "water_heater"}

def normalize_device(state: dict) -> dict:
    """将 HA 实体转换为统一设备格式"""
    eid = state["entity_id"]
    domain = eid.split(".")[0]
    attrs = state.get("attributes", {})

    device = {
        "id": eid,
        "domain": domain,
        "name": attrs.get("friendly_name", eid),
        "state": state["state"],
        "icon": attrs.get("icon", ""),
        "last_changed": state.get("last_changed", ""),
    }

    # 域特定属性
    if domain == "light":
        device["brightness"] = attrs.get("brightness")
        device["color_temp"] = attrs.get("color_temp")
        device["rgb_color"] = attrs.get("rgb_color")
        device["supported_color_modes"] = attrs.get("supported_color_modes", [])
    elif domain == "fan":
        device["percentage"] = attrs.get("percentage")
        device["preset_mode"] = attrs.get("preset_mode")
    elif domain == "climate":
        device["temperature"] = attrs.get("temperature")
        device["current_temperature"] = attrs.get("current_temperature")
        device["hvac_modes"] = attrs.get("hvac_modes", [])
        device["hvac_action"] = attrs.get("hvac_action")
    elif domain == "cover":
        device["current_position"] = attrs.get("current_position")
    elif domain == "sensor":
        device["unit"] = attrs.get("unit_of_measurement", "")
        device["device_class"] = attrs.get("device_class", "")
    elif domain == "media_player":
        device["media_title"] = attrs.get("media_title")
        device["volume_level"] = attrs.get("volume_level")

    return device


def build_service_call(entity_id: str, req: ControlRequest) -> tuple:
    """将统一控制请求转换为 HA 服务调用"""
    domain = entity_id.split(".")[0]
    action = req.action
    data = {"entity_id": entity_id}

    if action in ("turn_on", "turn_off", "toggle"):
        service = action
        if req.extra:
            data.update(req.extra)
        # 灯光亮度快捷方式
        if domain == "light" and action == "turn_on" and req.value is not None:
            data["brightness"] = int(req.value)
    elif action == "set_brightness":
        service = "turn_on"
        data["brightness"] = int(req.value)
    elif action == "set_color_temp":
        service = "turn_on"
        data["color_temp"] = int(req.value)
    elif action == "set_rgb":
        service = "turn_on"
        data["rgb_color"] = req.value  # [r, g, b]
    elif action == "set_percentage":
        service = "set_percentage"
        data["percentage"] = int(req.value)
    elif action == "set_temperature":
        service = "set_temperature"
        data["temperature"] = float(req.value)
    elif action == "set_hvac_mode":
        service = "set_hvac_mode"
        data["hvac_mode"] = req.value
    elif action == "set_position":
        service = "set_cover_position"
        data["position"] = int(req.value)
    elif action == "open":
        service = "open_cover"
    elif action == "close":
        service = "close_cover"
    elif action == "stop":
        service = "stop_cover"
    elif action == "lock":
        service = "lock"
    elif action == "unlock":
        service = "unlock"
    elif action == "trigger":
        service = "trigger"
    elif action == "activate":
        service = "turn_on"
    else:
        # 直接传递
        service = action
        if req.value is not None:
            data["value"] = req.value
        if req.extra:
            data.update(req.extra)

    return domain, service, data


# ============================================================
# FastAPI App
# ============================================================
ha = HAClient(HA_URL, HA_TOKEN)
tuya = TuyaClient(TUYA_CLIENT_ID, TUYA_SECRET, TUYA_REGION)
micloud: Optional[MiCloudDirect] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global micloud
    if GATEWAY_MODE == "direct":
        creds = load_credentials_from_ha(HA_CONFIG_PATH)
        if creds:
            micloud = MiCloudDirect(creds, spec_dir=MIOT_SPEC_DIR)
            micloud.init()
            logger.info("MiCloud direct mode: %d devices loaded", len(micloud._devices))
        else:
            logger.warning("No MiCloud credentials found, falling back to HA mode")
    if GATEWAY_MODE == "ha" or not micloud:
        await ha.init()
    if tuya.enabled:
        try:
            await tuya.init()
        except Exception as e:
            logger.warning("Tuya init failed: %s", e)
    yield
    await ha.close()
    await tuya.close()

app = FastAPI(
    title="Smart Home Gateway",
    version="2.0.0",
    description="统一智能家居 API 网关 — MiCloud 直连 + HA 代理双模式",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== 核心路由 ====================

@app.get("/")
async def gateway_status():
    result = {
        "gateway": "Smart Home Gateway",
        "version": "2.0.0",
        "mode": GATEWAY_MODE,
        "tuya": {"enabled": tuya.enabled},
    }
    if micloud:
        result["micloud"] = {
            "connected": True,
            "devices": len(micloud._devices),
            "specs": len(micloud._specs),
            "user_id": micloud.credentials.get("user_id", ""),
        }
    if GATEWAY_MODE == "ha" or not micloud:
        result["ha"] = await ha.check()
    return result


@app.get("/devices")
async def list_devices(
    domain: Optional[str] = Query(None, description="Filter by domain: switch, light, fan, etc."),
    room: Optional[str] = Query(None, description="Filter by area/room name"),
):
    """获取所有设备列表"""
    if micloud:
        devices = micloud.get_devices(domain=domain)
        return {"count": len(devices), "devices": devices, "mode": "direct"}
    # HA fallback
    try:
        states = await ha.get_states()
    except Exception:
        return {"count": 0, "devices": [], "ha_offline": True}
    devices = []
    for s in states:
        d = s["entity_id"].split(".")[0]
        if d not in DEVICE_DOMAINS:
            continue
        if domain and d != domain:
            continue
        dev = normalize_device(s)
        if room:
            area = s.get("attributes", {}).get("area", "")
            if room.lower() not in (area or "").lower():
                continue
        devices.append(dev)
    return {"count": len(devices), "devices": devices, "mode": "ha"}


@app.get("/devices/{entity_id}")
async def get_device(entity_id: str):
    """获取单个设备详情"""
    if micloud:
        device = micloud.get_device(entity_id)
        if device:
            return device
        raise HTTPException(status_code=404, detail=f"Device not found: {entity_id}")
    try:
        state = await ha.get_state(entity_id)
        return normalize_device(state)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"Entity not found: {entity_id}")


@app.post("/devices/{entity_id}/control")
async def control_device(entity_id: str, req: ControlRequest):
    """控制设备"""
    if micloud:
        result = micloud.control_device(entity_id, req.action, req.value, req.extra)
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result.get("error", "Control failed"))
        return {"ok": True, "entity_id": entity_id, "action": req.action, "mode": "direct", **result}
    # HA fallback
    domain, service, data = build_service_call(entity_id, req)
    try:
        result = await ha.call_service(domain, service, data)
        return {"ok": True, "entity_id": entity_id, "action": req.action, "result": result}
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))


@app.get("/scenes")
async def list_scenes():
    """获取场景列表"""
    try:
        states = await ha.get_states()
    except Exception:
        return {"count": 0, "scenes": [], "ha_offline": True}
    scenes = [
        {
            "id": s["entity_id"],
            "name": s.get("attributes", {}).get("friendly_name", s["entity_id"]),
            "icon": s.get("attributes", {}).get("icon", ""),
        }
        for s in states
        if s["entity_id"].startswith("scene.")
    ]
    return {"count": len(scenes), "scenes": scenes}


@app.post("/scenes/{scene_id}/activate")
async def activate_scene(scene_id: str):
    """触发场景"""
    if not scene_id.startswith("scene."):
        scene_id = f"scene.{scene_id}"
    result = await ha.call_service("scene", "turn_on", {"entity_id": scene_id})
    return {"ok": True, "scene": scene_id, "result": result}


@app.get("/automations")
async def list_automations():
    """获取自动化列表"""
    try:
        states = await ha.get_states()
    except Exception:
        return {"count": 0, "automations": [], "ha_offline": True}
    autos = [
        {
            "id": s["entity_id"],
            "name": s.get("attributes", {}).get("friendly_name", s["entity_id"]),
            "state": s["state"],
        }
        for s in states
        if s["entity_id"].startswith("automation.")
    ]
    return {"count": len(autos), "automations": autos}


@app.post("/automations/{auto_id}/trigger")
async def trigger_automation(auto_id: str):
    """触发自动化"""
    if not auto_id.startswith("automation."):
        auto_id = f"automation.{auto_id}"
    result = await ha.call_service("automation", "trigger", {"entity_id": auto_id})
    return {"ok": True, "automation": auto_id}


@app.get("/rooms")
async def list_rooms():
    """获取区域/房间列表（从设备属性推断）"""
    try:
        states = await ha.get_states()
    except Exception:
        return {"rooms": [], "ha_offline": True}
    rooms = {}
    for s in states:
        d = s["entity_id"].split(".")[0]
        if d not in DEVICE_DOMAINS:
            continue
        area = s.get("attributes", {}).get("area", "未分类")
        if area not in rooms:
            rooms[area] = []
        rooms[area].append(s["entity_id"])
    return {"rooms": [{"name": k, "device_count": len(v), "devices": v} for k, v in rooms.items()]}


@app.post("/batch")
async def batch_control(req: BatchControlRequest):
    """批量控制设备"""
    results = []
    for cmd in req.commands:
        entity_id = cmd.get("entity_id", "")
        action = cmd.get("action", "toggle")
        value = cmd.get("value")
        extra = cmd.get("extra")
        try:
            ctrl = ControlRequest(action=action, value=value, extra=extra)
            domain, service, data = build_service_call(entity_id, ctrl)
            await ha.call_service(domain, service, data)
            results.append({"entity_id": entity_id, "ok": True})
        except Exception as e:
            results.append({"entity_id": entity_id, "ok": False, "error": str(e)})
    return {"results": results, "total": len(results), "success": sum(1 for r in results if r["ok"])}


@app.get("/history/{entity_id}")
async def get_history(entity_id: str, hours: int = Query(24, ge=1, le=168)):
    """获取设备历史记录"""
    data = await ha.get_history(entity_id, hours)
    return {"entity_id": entity_id, "hours": hours, "data": data}


@app.post("/template")
async def render_template(req: TemplateRequest):
    """渲染 HA 模板"""
    result = await ha.render_template(req.template)
    return {"result": result}


@app.get("/services")
async def list_services():
    """获取所有可用服务"""
    try:
        return await ha.get_services()
    except Exception:
        return {"services": [], "ha_offline": True}


@app.get("/config")
async def get_config():
    """获取 HA 配置"""
    try:
        return await ha.get_config()
    except Exception:
        return {"ha_offline": True, "error": "Home Assistant is not reachable"}


# ==================== 涂鸦直连路由 ====================

@app.get("/tuya/devices")
async def tuya_devices():
    """获取涂鸦设备列表"""
    if not tuya.enabled:
        raise HTTPException(status_code=503, detail="Tuya not configured")
    return await tuya.get_devices()


@app.get("/tuya/devices/{device_id}/status")
async def tuya_device_status(device_id: str):
    """获取涂鸦设备状态"""
    if not tuya.enabled:
        raise HTTPException(status_code=503, detail="Tuya not configured")
    return await tuya.get_device_status(device_id)


@app.get("/tuya/devices/{device_id}/functions")
async def tuya_device_functions(device_id: str):
    """获取涂鸦设备可用功能"""
    if not tuya.enabled:
        raise HTTPException(status_code=503, detail="Tuya not configured")
    return await tuya.get_device_functions(device_id)


@app.post("/tuya/devices/{device_id}/cmd")
async def tuya_send_command(device_id: str, req: TuyaCommandRequest):
    """发送涂鸦设备控制指令"""
    if not tuya.enabled:
        raise HTTPException(status_code=503, detail="Tuya not configured")
    return await tuya.send_commands(device_id, req.commands)


# ==================== 便捷快捷路由 ====================

@app.post("/quick/{action}")
async def quick_action(action: str, entities: Optional[str] = Query(None)):
    """快捷操作: /quick/all_off, /quick/all_on, /quick/lights_off, etc."""
    if micloud:
        return micloud.quick_action(action)
    # HA fallback
    try:
        states = await ha.get_states()
    except Exception:
        return {"action": action, "affected": 0, "results": [], "ha_offline": True}

    if action == "all_off":
        targets = [s["entity_id"] for s in states
                   if s["entity_id"].split(".")[0] in ("switch", "light", "fan") and s["state"] == "on"]
    elif action == "all_on":
        targets = [s["entity_id"] for s in states
                   if s["entity_id"].split(".")[0] in ("switch", "light") and s["state"] == "off"]
    elif action == "lights_off":
        targets = [s["entity_id"] for s in states
                   if s["entity_id"].startswith("light.") and s["state"] == "on"]
    elif action == "lights_on":
        targets = [s["entity_id"] for s in states
                   if s["entity_id"].startswith("light.") and s["state"] == "off"]
    elif action == "fans_off":
        targets = [s["entity_id"] for s in states
                   if s["entity_id"].startswith("fan.") and s["state"] == "on"]
    else:
        raise HTTPException(status_code=400, detail=f"Unknown quick action: {action}")

    results = []
    for eid in targets:
        domain = eid.split(".")[0]
        service = "turn_off" if "off" in action else "turn_on"
        try:
            await ha.call_service(domain, service, {"entity_id": eid})
            results.append({"entity_id": eid, "ok": True})
        except Exception as e:
            results.append({"entity_id": eid, "ok": False, "error": str(e)})

    return {"action": action, "affected": len(results), "results": results}


# ==================== MiCloud 直连路由 ====================

class RpcRequest(BaseModel):
    did: str
    siid: int
    piid: Optional[int] = None
    aiid: Optional[int] = None
    value: Optional[Any] = None
    params: Optional[list] = None

class TtsRequest(BaseModel):
    text: str
    speaker: Optional[str] = None  # did of speaker, or auto-select


@app.get("/micloud/status")
async def micloud_status():
    """MiCloud 连接状态"""
    if not micloud:
        return {"connected": False, "mode": GATEWAY_MODE}
    return {
        "connected": True,
        "user_id": micloud.credentials.get("user_id", ""),
        "devices": len(micloud._devices),
        "specs": len(micloud._specs),
        "last_refresh": micloud._last_refresh,
    }


@app.post("/micloud/rpc")
async def micloud_rpc(req: RpcRequest):
    """原始 MIoT RPC 调用"""
    if not micloud:
        raise HTTPException(status_code=503, detail="MiCloud not available")
    if req.aiid is not None:
        result = micloud._rpc_execute_action(req.did, req.siid, req.aiid, req.params)
        return {"ok": result.get("code") == 0, "result": result}
    elif req.value is not None and req.piid is not None:
        ok = micloud._rpc_set_property(req.did, req.siid, req.piid, req.value)
        return {"ok": ok}
    elif req.piid is not None:
        vals = micloud._rpc_get_properties([{"did": req.did, "siid": req.siid, "piid": req.piid}])
        return {"ok": True, "result": vals}
    else:
        raise HTTPException(status_code=400, detail="Must provide piid (get/set) or aiid (action)")


@app.post("/micloud/tts")
async def micloud_tts(req: TtsRequest):
    """小爱音箱 TTS"""
    if not micloud:
        raise HTTPException(status_code=503, detail="MiCloud not available")
    # 找音箱设备
    speakers = [d for d in micloud._devices if "speaker" in d.get("model", "").lower()]
    if req.speaker:
        target = next((d for d in speakers if str(d["did"]) == req.speaker), None)
    else:
        target = speakers[0] if speakers else None
    if not target:
        raise HTTPException(status_code=404, detail="No speaker found")
    did = str(target["did"])
    result = micloud.control_device(did, "play_text", req.text)
    return {"ok": result.get("ok", False), "speaker": target.get("name", ""), "did": did, **result}


@app.post("/micloud/refresh")
async def micloud_refresh():
    """刷新设备列表"""
    if not micloud:
        raise HTTPException(status_code=503, detail="MiCloud not available")
    micloud.refresh_devices()
    return {"ok": True, "devices": len(micloud._devices)}


# ============================================================
# Entry point
# ============================================================
if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Smart Home Gateway")
    parser.add_argument("--mode", choices=["direct", "ha"], default=GATEWAY_MODE,
                        help="Backend mode: direct (MiCloud) or ha (Home Assistant)")
    parser.add_argument("--port", type=int, default=GATEWAY_PORT)
    parser.add_argument("--host", default=GATEWAY_HOST)
    args = parser.parse_args()

    GATEWAY_MODE = args.mode
    GATEWAY_PORT = args.port
    GATEWAY_HOST = args.host

    print(f"Smart Home Gateway v2.0.0")
    print(f"  Mode: {GATEWAY_MODE}")
    print(f"  Listen: {GATEWAY_HOST}:{GATEWAY_PORT}")
    if GATEWAY_MODE == "direct":
        print(f"  MiCloud: credentials from {HA_CONFIG_PATH}")
        print(f"  MIoT specs: {MIOT_SPEC_DIR}")
    else:
        print(f"  HA: {HA_URL}")
    print(f"  Tuya: {'enabled' if tuya.enabled else 'disabled'}")
    uvicorn.run(app, host=GATEWAY_HOST, port=GATEWAY_PORT)
