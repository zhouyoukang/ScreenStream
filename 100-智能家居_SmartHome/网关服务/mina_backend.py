#!/usr/bin/env python3
"""
Mina API Client — 小米音箱桥梁 (TTS + 对话历史)
用于 AI↔用户 双向通信: 读取音箱对话历史 + 发送 TTS 播报
"""

import os
import json
import time
import random
import string
from typing import Optional

import httpx


class MinaClient:
    """Lightweight Mina API client — speaker bridge for AI-user interaction"""
    MINA_API = "https://api2.mina.mi.com"
    CONV_API = "https://userprofile.mina.mi.com/device_profile/v2/conversation"
    UA = "MiHome/6.0.103 (com.xiaomi.mihome; build:6.0.103.1; iOS 14.4.0) Alamofire/6.0.103 MICO/iOSApp/appStore/6.0.103"

    def __init__(self, token_file: str = ""):
        self.token = None
        self.devices = []
        self._client = httpx.AsyncClient(timeout=15)
        self._token_file = token_file or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "mina_token.json"
        )

    def load_token(self) -> bool:
        if not os.path.exists(self._token_file):
            return False
        with open(self._token_file, encoding="utf-8") as f:
            self.token = json.load(f)
        return bool(self.token.get("serviceToken"))

    def _cookies(self, device_id: str = "") -> dict:
        return {
            "userId": str(self.token["userId"]),
            "serviceToken": self.token["serviceToken"],
            "deviceId": device_id or self.token.get("deviceId", ""),
        }

    def _rid(self):
        return "app_ios_" + ''.join(random.choices(string.ascii_lowercase + string.digits, k=30))

    async def fetch_devices(self) -> list:
        url = f"{self.MINA_API}/admin/v2/device_list?master=0&requestId={self._rid()}"
        resp = await self._client.get(url, cookies=self._cookies(), headers={"User-Agent": self.UA})
        if resp.status_code != 200:
            return self.devices
        try:
            data = resp.json()
        except Exception:
            return self.devices
        if data.get("code") == 0:
            self.devices = data.get("data", [])
        return self.devices

    def get_online_speaker(self) -> Optional[dict]:
        return next((d for d in self.devices if d.get("presence") == "online"), None)

    async def get_conversation(self, device_id: str = None, hardware: str = "LX06", limit: int = 5) -> list:
        """Get recent voice conversations from speaker (user→AI bridge)"""
        if not device_id:
            dev = self.get_online_speaker()
            if not dev:
                return []
            device_id = dev["deviceID"]
            hardware = dev.get("hardware", hardware)
        url = f"{self.CONV_API}?source=dialogu&hardware={hardware}&timestamp={int(time.time()*1000)}&limit={limit}"
        resp = await self._client.get(url, cookies=self._cookies(device_id), headers={"User-Agent": self.UA})
        try:
            result = resp.json()
        except Exception:
            return []
        if result.get("code") != 0:
            return []
        raw = result.get("data", "")
        obj = json.loads(raw) if isinstance(raw, str) else raw
        return obj.get("records", []) if obj else []

    async def tts(self, text: str, device_id: str = None) -> dict:
        """Send TTS via Mina ubus (AI→user bridge)"""
        if not device_id:
            dev = self.get_online_speaker()
            if not dev:
                return {"ok": False, "error": "No online speaker"}
            device_id = dev["deviceID"]
        msg = json.dumps({"text": text})
        url = f"{self.MINA_API}/remote/ubus"
        data = {"deviceId": device_id, "message": msg, "method": "text_to_speech", "path": "mibrain", "requestId": self._rid()}
        resp = await self._client.post(url, data=data, cookies=self._cookies(device_id), headers={"User-Agent": self.UA})
        try:
            r = resp.json()
            return {"ok": r.get("code") == 0, "raw": r}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    async def close(self):
        await self._client.aclose()
