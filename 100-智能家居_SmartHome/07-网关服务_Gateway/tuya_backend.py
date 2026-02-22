#!/usr/bin/env python3
"""
涂鸦 Cloud API 客户端
可选后端 — 直连涂鸦云控制 IoT 设备
"""

import time
import hmac
import hashlib
from typing import Optional

import httpx


TUYA_BASE_URLS = {
    "cn": "https://openapi.tuyacn.com",
    "us": "https://openapi.tuyaus.com",
    "eu": "https://openapi.tuyaeu.com",
    "in": "https://openapi.tuyain.com",
}


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
