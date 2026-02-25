#!/usr/bin/env python3
"""
Smart Home Gateway v3.0 — 统一智能家居 API 网关
多后端聚合，HA 可选:
  - ewelink: 直连 Sonoff/eWeLink 设备 (CoolKit v2 API)
  - micloud: 直连小米云 API (MIoT RPC)
  - tuya: 直连涂鸦云 API
  - ha: Home Assistant 代理 (可选，提供场景/历史等高级功能)
端口: 8900 | 配置: config.json

API 概览:
  GET  /                     — 网关状态(所有后端连接情况)
  GET  /devices              — 所有设备列表(聚合全部后端)
  GET  /devices/{id}         — 单个设备详情
  POST /devices/{id}/control — 控制设备(自动路由到正确后端)
  GET  /scenes               — 场景列表 (HA only)
  POST /scenes/{id}/activate — 触发场景 (HA only)
  POST /quick/{action}       — 快捷操作: all_off, lights_off, etc.
  POST /batch                — 批量控制

  # eWeLink 直连
  GET  /ewelink/devices      — eWeLink 设备列表
  POST /ewelink/refresh      — 刷新设备列表

  # MiCloud 直连
  GET  /micloud/status       — MiCloud 连接状态
  POST /micloud/rpc          — 原始 MIoT RPC 调用
  POST /micloud/tts          — 小爱音箱 TTS

  # 涂鸦直连 (可选)
  GET  /tuya/devices          — 涂鸦设备列表
  POST /tuya/devices/{id}/cmd — 涂鸦设备控制

  # HA (可选)
  GET  /history/{entity_id}  — 历史记录
  POST /template             — HA模板渲染
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
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, HTMLResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from micloud_backend import MiCloudDirect, load_credentials_standalone, load_credentials_from_ha
from ewelink_backend import EWeLinkClient
from ha_backend import HAClient
from mina_backend import MinaClient
from tuya_backend import TuyaClient
from wechat_handler import WeChatCommandRouter, parse_xml, text_reply, verify_signature
import random, string

load_dotenv()
logger = logging.getLogger(__name__)

# ============================================================
# Configuration — from config.json (fallback to env vars)
# ============================================================
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
CONFIG_EXAMPLE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.example.json")
CFG = {}
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, encoding="utf-8") as _f:
        CFG = json.load(_f)
    logger.info("Loaded config from %s", CONFIG_FILE)
elif os.path.exists(CONFIG_EXAMPLE):
    import shutil
    shutil.copy2(CONFIG_EXAMPLE, CONFIG_FILE)
    with open(CONFIG_FILE, encoding="utf-8") as _f:
        CFG = json.load(_f)
    logger.info("Created config.json from template. Edit it to add credentials.")

_gw = CFG.get("gateway", {})
_ha = CFG.get("ha", {})
_mi = CFG.get("micloud", {})
_ew = CFG.get("ewelink", {})
_ty = CFG.get("tuya", {})

GATEWAY_HOST = _gw.get("host", os.getenv("GATEWAY_HOST", "0.0.0.0"))
GATEWAY_PORT = int(_gw.get("port", os.getenv("GATEWAY_PORT", "8900")))
GATEWAY_MODE = _gw.get("mode", os.getenv("GATEWAY_MODE", "direct"))

HA_ENABLED = _ha.get("enabled", False)
HA_URL = _ha.get("url", os.getenv("HA_URL", "http://192.168.31.141:8123"))
HA_TOKEN = _ha.get("token", os.getenv("HA_TOKEN", ""))

TUYA_CLIENT_ID = _ty.get("client_id", os.getenv("TUYA_CLIENT_ID", ""))
TUYA_SECRET = _ty.get("secret", os.getenv("TUYA_SECRET", ""))
TUYA_REGION = _ty.get("region", os.getenv("TUYA_REGION", "cn"))
TUYA_ENABLED = _ty.get("enabled", bool(TUYA_CLIENT_ID))

EWELINK_ENABLED = _ew.get("enabled", False)
EWELINK_APP_ID = _ew.get("app_id", "")
EWELINK_APP_SECRET = _ew.get("app_secret", "")
EWELINK_EMAIL = _ew.get("email", "")
EWELINK_PASSWORD = _ew.get("password", "")
EWELINK_REGION = _ew.get("region", "cn")
EWELINK_COUNTRY_CODE = _ew.get("country_code", "+86")

_wx = CFG.get("wechat", {})
WECHAT_ENABLED = _wx.get("enabled", False)
WECHAT_TOKEN = _wx.get("token", "")
WECHAT_APPID = _wx.get("appid", "")
WECHAT_APPSECRET = _wx.get("appsecret", "")

MICLOUD_ENABLED = _mi.get("enabled", True)
MICLOUD_USERNAME = _mi.get("username", "")
MICLOUD_PASSWORD = _mi.get("password", "")
MICLOUD_SERVER = _mi.get("server", "cn")


mina = MinaClient()

# Device source tracking — maps device_id to backend name
_device_source: dict = {}  # device_id -> "ewelink" | "micloud" | "tuya" | "ha"


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
# FastAPI App — Multi-backend, HA optional
# ============================================================
ha = HAClient(HA_URL, HA_TOKEN)
tuya = TuyaClient(TUYA_CLIENT_ID, TUYA_SECRET, TUYA_REGION)
ewelink = EWeLinkClient(EWELINK_APP_ID, EWELINK_APP_SECRET, EWELINK_REGION)
micloud: Optional[MiCloudDirect] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global micloud, _device_source
    backends_ok = []

    # 1. eWeLink (Sonoff devices)
    if EWELINK_ENABLED and ewelink.enabled and EWELINK_EMAIL:
        await ewelink.init()
        ok = await ewelink.login(email=EWELINK_EMAIL, password=EWELINK_PASSWORD,
                                 country_code=EWELINK_COUNTRY_CODE)
        if ok:
            devices = await ewelink.fetch_devices()
            for d in devices:
                _device_source[d["deviceid"]] = "ewelink"
            backends_ok.append(f"eWeLink({len(devices)} devices)")
        else:
            logger.warning("eWeLink login failed")

    # 2. MiCloud (Xiaomi devices) — 三级凭据链: config → 自缓存 → HA回退
    if MICLOUD_ENABLED:
        creds = load_credentials_standalone(_mi)
        if creds:
            spec_dir = None
            ha_path = _mi.get("ha_config_path", "")
            if ha_path:
                candidate = os.path.join(ha_path, ".storage", "xiaomi_miot")
                if os.path.isdir(candidate):
                    spec_dir = candidate
            micloud = MiCloudDirect(creds, spec_dir=spec_dir)
            micloud.init()
            for d in micloud._devices:
                _device_source[str(d["did"])] = "micloud"
            backends_ok.append(f"MiCloud({len(micloud._devices)} devices)")
        else:
            logger.warning("No MiCloud credentials found (tried config/cache/HA)")

    # 3. Tuya
    if TUYA_ENABLED and tuya.enabled:
        try:
            await tuya.init()
            backends_ok.append("Tuya")
        except Exception as e:
            logger.warning("Tuya init failed: %s", e)

    # 4. HA (optional, for scenes/history/extra devices)
    if HA_ENABLED and HA_TOKEN:
        await ha.init()
        check = await ha.check()
        if check.get("connected"):
            backends_ok.append("HA")
        else:
            logger.warning("HA not reachable: %s", check)

    # 5. Mina API (speaker bridge)
    if mina.load_token():
        devs = await mina.fetch_devices()
        online = [d for d in devs if d.get("presence") == "online"]
        backends_ok.append(f"Mina({len(devs)} speakers, {len(online)} online)")
    else:
        logger.warning("Mina token not found (mina_token.json)")

    # 6. WeChat Official Account
    if WECHAT_ENABLED and WECHAT_TOKEN:
        wechat_router = WeChatCommandRouter({
            "micloud": micloud,
            "ewelink": ewelink,
            "mina": mina,
            "ha": ha if HA_ENABLED and HA_TOKEN else None,
            "scene_macros": SCENE_MACROS,
            "find_speaker": _find_best_speaker,
        })
        app.state.wechat_router = wechat_router
        backends_ok.append("WeChat")
    else:
        app.state.wechat_router = None

    logger.info("Gateway ready: %s", " + ".join(backends_ok) if backends_ok else "no backends")
    yield
    if HA_ENABLED:
        await ha.close()
    if TUYA_ENABLED:
        await tuya.close()
    if EWELINK_ENABLED:
        await ewelink.close()
    if mina.token:
        await mina.close()

app = FastAPI(
    title="Smart Home Gateway",
    version="3.0.0",
    description="统一智能家居 API 网关 — 多后端聚合, HA 可选",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== 仪表盘 ====================

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """智能家居可视化仪表盘"""
    html_path = Path(__file__).parent / "dashboard.html"
    return html_path.read_text(encoding="utf-8")


# ==================== 核心路由 ====================

@app.get("/")
async def gateway_status():
    result = {
        "gateway": "Smart Home Gateway",
        "version": "3.0.0",
        "backends": {},
        "total_devices": 0,
    }
    total = 0
    if EWELINK_ENABLED and ewelink.at:
        n = len(ewelink._devices)
        result["backends"]["ewelink"] = {"connected": True, "devices": n}
        total += n
    if micloud:
        n = len(micloud._devices)
        result["backends"]["micloud"] = {
            "connected": True, "devices": n, "specs": len(micloud._specs),
        }
        total += n
    if TUYA_ENABLED and tuya.enabled:
        result["backends"]["tuya"] = {"enabled": True}
    if HA_ENABLED and HA_TOKEN:
        result["backends"]["ha"] = await ha.check()
    result["total_devices"] = total
    return result


@app.get("/devices")
async def list_devices(
    domain: Optional[str] = Query(None, description="Filter by domain: switch, light, fan, etc."),
    source: Optional[str] = Query(None, description="Filter by source: ewelink, micloud, tuya, ha"),
):
    """获取所有设备列表（聚合全部后端）"""
    devices = []
    sources_used = []

    # 1. eWeLink devices
    if (not source or source == "ewelink") and EWELINK_ENABLED and ewelink.at:
        ew_devs = ewelink.get_devices(domain=domain)
        for d in ew_devs:
            d["source"] = "ewelink"
        devices.extend(ew_devs)
        if ew_devs:
            sources_used.append("ewelink")

    # 2. MiCloud devices
    if (not source or source == "micloud") and micloud:
        mi_devs = micloud.get_devices(domain=domain)
        for d in mi_devs:
            d["source"] = "micloud"
        devices.extend(mi_devs)
        if mi_devs:
            sources_used.append("micloud")

    # 3. HA devices (if enabled, for devices not covered by direct backends)
    if (not source or source == "ha") and HA_ENABLED and HA_TOKEN:
        try:
            states = await ha.get_states()
            for s in states:
                d = s["entity_id"].split(".")[0]
                if d not in DEVICE_DOMAINS:
                    continue
                if domain and d != domain:
                    continue
                dev = normalize_device(s)
                dev["source"] = "ha"
                devices.append(dev)
            sources_used.append("ha")
        except Exception:
            pass

    return {"count": len(devices), "devices": devices, "sources": sources_used}


@app.get("/devices/{entity_id}")
async def get_device(entity_id: str):
    """获取单个设备详情（自动查找正确后端）"""
    # Check eWeLink
    if EWELINK_ENABLED and ewelink.at:
        dev = ewelink.get_device(entity_id)
        if dev:
            dev["source"] = "ewelink"
            return dev
    # Check MiCloud
    if micloud:
        dev = micloud.get_device(entity_id)
        if dev:
            dev["source"] = "micloud"
            return dev
    # Check HA
    if HA_ENABLED and HA_TOKEN:
        try:
            state = await ha.get_state(entity_id)
            dev = normalize_device(state)
            dev["source"] = "ha"
            return dev
        except Exception:
            pass
    raise HTTPException(status_code=404, detail=f"Device not found: {entity_id}")


@app.post("/devices/{entity_id}/control")
async def control_device(entity_id: str, req: ControlRequest):
    """控制设备（自动路由到正确后端: MiCloud → eWeLink → HA）"""
    # 1. MiCloud
    if micloud and micloud._device_map.get(entity_id):
        result = micloud.control_device(entity_id, req.action, req.value, req.extra)
        if not result.get("ok"):
            error_detail = result.get("error", "Control failed")
            raw = result.get("raw")
            detail = {"error": error_detail}
            if raw:
                detail["raw"] = raw
            raise HTTPException(status_code=400, detail=detail)
        return {"ok": True, "entity_id": entity_id, "action": req.action, "source": "micloud", **result}
    # 2. eWeLink
    if EWELINK_ENABLED and ewelink.at and ewelink._device_map.get(entity_id):
        result = await ewelink.control_device(entity_id, req.action, req.value, req.extra)
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result.get("error", "Control failed"))
        return {"ok": True, "entity_id": entity_id, "action": req.action, "source": "ewelink", **result}
    # 3. HA fallback (only if HA is configured)
    if HA_ENABLED:
        domain, service, data = build_service_call(entity_id, req)
        try:
            result = await ha.call_service(domain, service, data)
            return {"ok": True, "entity_id": entity_id, "action": req.action, "source": "ha", "result": result}
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"HA error: {e}")
    # No backend found for this device
    raise HTTPException(status_code=404, detail=f"Device not found in any backend: {entity_id}")


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
    """批量控制设备（自动路由到正确后端）"""
    results = []
    for cmd in req.commands:
        entity_id = cmd.get("entity_id", "")
        action = cmd.get("action", "toggle")
        value = cmd.get("value")
        extra = cmd.get("extra")
        try:
            # 优先 MiCloud
            if micloud and micloud._device_map.get(entity_id):
                result = micloud.control_device(entity_id, action, value, extra)
                results.append({"entity_id": entity_id, "ok": result.get("ok", False),
                                "error": result.get("error"), "source": "micloud"})
                continue
            # 然后 eWeLink
            if EWELINK_ENABLED and ewelink.at and ewelink._device_map.get(entity_id):
                result = await ewelink.control_device(entity_id, action, value, extra)
                results.append({"entity_id": entity_id, "ok": result.get("ok", False),
                                "error": result.get("error"), "source": "ewelink"})
                continue
            # 最后 HA
            ctrl = ControlRequest(action=action, value=value, extra=extra)
            domain, service, data = build_service_call(entity_id, ctrl)
            await ha.call_service(domain, service, data)
            results.append({"entity_id": entity_id, "ok": True, "source": "ha"})
        except Exception as e:
            results.append({"entity_id": entity_id, "ok": False, "error": str(e)})
    return {"results": results, "total": len(results), "success": sum(1 for r in results if r["ok"])}


@app.get("/history/{entity_id}")
async def get_history(entity_id: str, hours: int = Query(24, ge=1, le=168)):
    """获取设备历史记录"""
    try:
        data = await ha.get_history(entity_id, hours)
        return {"entity_id": entity_id, "hours": hours, "data": data}
    except Exception:
        return {"entity_id": entity_id, "hours": hours, "data": [], "ha_offline": True}


@app.post("/template")
async def render_template(req: TemplateRequest):
    """渲染 HA 模板"""
    try:
        result = await ha.render_template(req.template)
        return {"result": result}
    except Exception:
        return {"result": None, "ha_offline": True}


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


# ==================== eWeLink 直连路由 ====================

@app.get("/ewelink/devices")
async def ewelink_devices():
    """获取 eWeLink 设备列表"""
    if not EWELINK_ENABLED or not ewelink.at:
        raise HTTPException(status_code=503, detail="eWeLink not connected")
    return {"count": len(ewelink._devices), "devices": ewelink.get_devices()}


@app.post("/ewelink/refresh")
async def ewelink_refresh():
    """刷新 eWeLink 设备列表"""
    if not EWELINK_ENABLED or not ewelink.at:
        raise HTTPException(status_code=503, detail="eWeLink not connected")
    devices = await ewelink.fetch_devices()
    return {"ok": True, "devices": len(devices)}


@app.post("/ewelink/devices/{device_id}/control")
async def ewelink_control(device_id: str, req: ControlRequest):
    """控制 eWeLink 设备"""
    if not EWELINK_ENABLED or not ewelink.at:
        raise HTTPException(status_code=503, detail="eWeLink not connected")
    result = await ewelink.control_device(device_id, req.action, req.value, req.extra)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Control failed"))
    return {"ok": True, "device_id": device_id, "action": req.action, **result}


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
    valid_actions = {"all_off", "all_on", "lights_off", "lights_on", "fans_off"}
    if action not in valid_actions:
        raise HTTPException(status_code=400, detail=f"Unknown quick action: {action}. Valid: {', '.join(sorted(valid_actions))}")
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
        return result
    elif req.value is not None and req.piid is not None:
        result = micloud._rpc_set_property(req.did, req.siid, req.piid, req.value)
        return result
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


@app.get("/micloud/diagnose")
async def micloud_diagnose():
    """深度诊断 MiCloud 连接 — 区分云端不可达 vs 设备离线"""
    if not micloud:
        return {"error": "MiCloud not initialized", "solution": "Check config.json micloud section"}
    return micloud.diagnose()


@app.post("/micloud/relogin")
async def micloud_relogin():
    """重新登录 MiCloud（用于 session 过期或切换账号）"""
    if not micloud:
        raise HTTPException(status_code=503, detail="MiCloud not available")
    return micloud.relogin()


# ============================================================
# Mina API 路由 (音箱桥梁: AI↔用户双向通信)
# ============================================================

@app.get("/mina/devices")
async def mina_devices():
    """Mina 音箱列表（含在线状态）"""
    if not mina.token:
        raise HTTPException(status_code=503, detail="Mina not configured (missing mina_token.json)")
    devs = await mina.fetch_devices()
    result = []
    for d in devs:
        result.append({
            "deviceID": d.get("deviceID", ""),
            "name": d.get("name", ""),
            "hardware": d.get("hardware", ""),
            "online": d.get("presence") == "online",
        })
    best = mina.get_online_speaker()
    return {
        "count": len(result),
        "online": sum(1 for d in result if d["online"]),
        "best": best.get("deviceID") if best else None,
        "devices": result,
    }


@app.get("/mina/history")
async def mina_history(limit: int = Query(5, ge=1, le=30), device_id: Optional[str] = Query(None)):
    """读取音箱对话历史（用户→AI桥梁）— 用户对音箱说的话"""
    if not mina.token:
        raise HTTPException(status_code=503, detail="Mina not configured")
    records = await mina.get_conversation(device_id=device_id, limit=limit)
    parsed = []
    for r in records:
        answers = r.get("answers", [])
        answer_text = ""
        if answers:
            tts = answers[0].get("tts", {})
            answer_text = tts.get("text", "") if isinstance(tts, dict) else str(tts)
        parsed.append({
            "query": r.get("query", ""),
            "answer": answer_text,
            "time": r.get("time", 0),
        })
    return {"count": len(parsed), "records": parsed}


class MinaTtsRequest(BaseModel):
    text: str
    device_id: Optional[str] = None


@app.post("/mina/tts")
async def mina_tts(req: MinaTtsRequest):
    """通过 Mina API 发送 TTS（AI→用户桥梁）"""
    if not mina.token:
        raise HTTPException(status_code=503, detail="Mina not configured")
    result = await mina.tts(req.text, device_id=req.device_id)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "TTS failed"))
    return {"ok": True, "text": req.text, **result}


@app.post("/mina/refresh")
async def mina_refresh():
    """刷新 Mina 设备列表"""
    if not mina.token:
        raise HTTPException(status_code=503, detail="Mina not configured")
    devs = await mina.fetch_devices()
    online = [d for d in devs if d.get("presence") == "online"]
    return {"ok": True, "total": len(devs), "online": len(online)}


# ============================================================
# 音箱代理 + 场景宏 + TTS快捷
# ============================================================

def _find_best_speaker() -> Optional[dict]:
    """自动选择最佳在线音箱（优先 isOnline=True 的）"""
    if not micloud:
        return None
    speakers = [d for d in micloud._devices if "speaker" in d.get("model", "").lower()]
    # 优先 isOnline=True
    online = [s for s in speakers if s.get("isOnline")]
    if online:
        return online[0]
    # 回退到第一个音箱
    return speakers[0] if speakers else None


class VoiceProxyRequest(BaseModel):
    command: str
    speaker: Optional[str] = None  # did, auto-select if empty
    silent: bool = True


@app.post("/proxy/voice")
async def proxy_voice(req: VoiceProxyRequest):
    """音箱语音代理 — 通过在线音箱执行语音指令控制其他设备"""
    if not micloud:
        raise HTTPException(status_code=503, detail="MiCloud not available")

    if req.speaker:
        target = next((d for d in micloud._devices if str(d["did"]) == req.speaker), None)
    else:
        target = _find_best_speaker()

    if not target:
        raise HTTPException(status_code=404, detail="No speaker available")

    did = str(target["did"])
    result = micloud.control_device(did, "execute_command", req.command, {"silent": req.silent})
    return {
        "ok": result.get("ok", False),
        "speaker": target.get("name", ""),
        "did": did,
        "command": req.command,
        **result,
    }


@app.get("/tts/{text}")
async def tts_quick(text: str, speaker: Optional[str] = Query(None)):
    """TTS 快捷 GET — 浏览器地址栏即可播报"""
    if not micloud:
        raise HTTPException(status_code=503, detail="MiCloud not available")

    if speaker:
        target = next((d for d in micloud._devices if str(d["did"]) == speaker), None)
    else:
        target = _find_best_speaker()

    if not target:
        raise HTTPException(status_code=404, detail="No speaker available")

    did = str(target["did"])
    result = micloud.control_device(did, "play_text", text)
    return {"ok": result.get("ok", False), "speaker": target.get("name", ""), "text": text, **result}


# 场景宏定义
# commands: 音箱代理指令(兜底); direct: 直接RPC控制(优先,更快)
# direct 格式: [{"keyword": "设备名关键词", "action": "turn_on/turn_off"}]
SCENE_MACROS = {
    "home": {
        "name": "回家模式",
        "commands": ["打开筒灯", "打开灯带"],
        "direct": [
            {"keyword": "筒灯", "action": "turn_on"},
            {"keyword": "灯带", "action": "turn_on"},
        ],
    },
    "away": {
        "name": "离家模式",
        "commands": ["关灯", "关闭风扇"],
        "direct": [
            {"keyword": "灯带", "action": "turn_off"},
            {"keyword": "筒灯", "action": "turn_off"},
            {"keyword": "落地扇", "action": "turn_off"},
        ],
    },
    "sleep": {
        "name": "睡眠模式",
        "commands": ["关灯"],
        "direct": [
            {"keyword": "灯带", "action": "turn_off"},
            {"keyword": "筒灯", "action": "turn_off"},
        ],
    },
    "movie": {
        "name": "观影模式",
        "commands": ["关闭筒灯", "把灯带调成暖色"],
        "direct": [
            {"keyword": "筒灯", "action": "turn_off"},
        ],
    },
    "work": {
        "name": "工作模式",
        "commands": ["打开筒灯", "打开灯带", "灯带调成白色"],
        "direct": [
            {"keyword": "筒灯", "action": "turn_on"},
            {"keyword": "灯带", "action": "turn_on"},
        ],
    },
}


@app.get("/scenes/macros")
async def list_scene_macros():
    """列出预定义场景宏"""
    return {"scenes": {k: {"name": v["name"], "steps": len(v["commands"])} for k, v in SCENE_MACROS.items()}}


@app.post("/scenes/macros/{scene_name}")
async def execute_scene_macro(scene_name: str, silent: bool = Query(True)):
    """执行场景宏 — 通过音箱代理执行一组语音指令"""
    if scene_name not in SCENE_MACROS:
        valid = ", ".join(SCENE_MACROS.keys())
        raise HTTPException(status_code=400, detail=f"Unknown scene: {scene_name}. Valid: {valid}")

    if not micloud:
        raise HTTPException(status_code=503, detail="MiCloud not available")

    target = _find_best_speaker()
    if not target:
        raise HTTPException(status_code=404, detail="No online speaker for proxy control")

    scene = SCENE_MACROS[scene_name]
    did = str(target["did"])
    results = []
    for cmd in scene["commands"]:
        result = micloud.control_device(did, "execute_command", cmd, {"silent": silent})
        results.append({"command": cmd, "ok": result.get("ok", False)})
        await asyncio.sleep(2)  # 间隔等待音箱处理

    ok_count = sum(1 for r in results if r["ok"])
    return {
        "ok": ok_count == len(results),
        "scene": scene_name,
        "name": scene["name"],
        "speaker": target.get("name", ""),
        "steps": results,
        "success": ok_count,
        "total": len(results),
    }


@app.get("/speakers")
async def list_speakers():
    """列出所有音箱及在线状态"""
    if not micloud:
        return {"speakers": [], "count": 0}
    speakers = [d for d in micloud._devices if "speaker" in d.get("model", "").lower()]
    result = []
    for s in speakers:
        did = str(s["did"])
        result.append({
            "did": did,
            "name": s.get("name", ""),
            "model": s.get("model", ""),
            "isOnline": s.get("isOnline", False),
        })
    best = _find_best_speaker()
    return {
        "speakers": result,
        "count": len(result),
        "online": sum(1 for s in result if s["isOnline"]),
        "best": str(best["did"]) if best else None,
    }


# ==================== 微信公众号路由 ====================


@app.get("/wx")
async def wechat_verify(
    signature: str = Query(""),
    timestamp: str = Query(""),
    nonce: str = Query(""),
    echostr: str = Query(""),
):
    """微信服务器 Token 验证 (GET)"""
    if not WECHAT_ENABLED:
        raise HTTPException(status_code=503, detail="WeChat not enabled")
    if verify_signature(WECHAT_TOKEN, signature, timestamp, nonce):
        return PlainTextResponse(echostr)
    raise HTTPException(status_code=403, detail="Signature verification failed")


@app.post("/wx")
async def wechat_message(request: Request):
    """微信消息接收与回复 (POST XML)"""
    if not WECHAT_ENABLED:
        raise HTTPException(status_code=503, detail="WeChat not enabled")

    body = await request.body()
    try:
        msg = parse_xml(body)
    except Exception as e:
        logger.error("WeChat XML parse error: %s", e)
        return PlainTextResponse("success")

    msg_type = msg.get("MsgType", "")
    from_user = msg.get("FromUserName", "")
    to_user = msg.get("ToUserName", "")

    router: Optional[WeChatCommandRouter] = getattr(app.state, "wechat_router", None)
    if not router:
        reply = "智能家居网关未就绪，请稍后再试"
        return PlainTextResponse(text_reply(from_user, to_user, reply), media_type="application/xml")

    reply = ""
    if msg_type == "text":
        content = msg.get("Content", "").strip()
        reply = await router.handle_text(content)
    elif msg_type == "voice":
        # 语音消息(开启语音识别后微信自动转文字)
        recognition = msg.get("Recognition", "").strip().rstrip("。.")
        if recognition:
            reply = await router.handle_text(recognition)
        else:
            reply = "未识别到语音内容，请重试或发送文字"
    elif msg_type == "event":
        event_type = msg.get("Event", "")
        event_key = msg.get("EventKey", "")
        reply = await router.handle_event(event_type, event_key)
    else:
        reply = "暂不支持该消息类型，请发送文字或语音指令"

    if not reply:
        return PlainTextResponse("success")

    return PlainTextResponse(text_reply(from_user, to_user, reply), media_type="application/xml")


@app.get("/wx/status")
async def wechat_status():
    """微信公众号模块状态"""
    return {
        "enabled": WECHAT_ENABLED,
        "token_set": bool(WECHAT_TOKEN),
        "appid": WECHAT_APPID[:8] + "..." if WECHAT_APPID else "",
        "router_ready": getattr(app.state, "wechat_router", None) is not None,
    }


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

    print(f"Smart Home Gateway v3.0.0")
    print(f"  Mode: {GATEWAY_MODE}")
    print(f"  Listen: {GATEWAY_HOST}:{GATEWAY_PORT}")
    if GATEWAY_MODE == "direct":
        ha_path = _mi.get("ha_config_path", "")
        print(f"  MiCloud: 3-level chain (config → cache → {'HA:' + ha_path if ha_path else 'no HA'})")
    else:
        print(f"  HA: {HA_URL}")
    print(f"  Tuya: {'enabled' if tuya.enabled else 'disabled'}")
    uvicorn.run(app, host=GATEWAY_HOST, port=GATEWAY_PORT)
