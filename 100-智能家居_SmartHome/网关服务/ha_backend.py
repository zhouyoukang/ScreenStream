#!/usr/bin/env python3
"""
Home Assistant REST API 客户端
可选后端 — 提供场景/历史/模板渲染等高级功能

弊端修复 (2026-02-27):
- 加入状态缓存 (30s TTL)，避免每次 /devices 调用都 fetch 1416 实体
- 加入自动重连逻辑，HA 离线后自动恢复
- 加入连接状态跟踪
"""

import logging
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_CACHE_TTL = 30  # 状态缓存有效期(秒)


class HAClient:
    """Home Assistant REST API 客户端 (带缓存+自动重连)"""

    def __init__(self, url: str, token: str):
        self.url = url.rstrip("/")
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        self._client: Optional[httpx.AsyncClient] = None
        self.connected = False
        self._states_cache: list = []
        self._cache_time: float = 0

    async def init(self):
        self._client = httpx.AsyncClient(timeout=15.0)

    async def _ensure_client(self):
        """确保 httpx 客户端可用，断线自动重建"""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=15.0)

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
        self.connected = False

    @property
    def client(self) -> httpx.AsyncClient:
        assert self._client is not None
        return self._client

    async def check(self) -> dict:
        try:
            await self._ensure_client()
            resp = await self.client.get(f"{self.url}/api/", headers=self.headers)
            self.connected = resp.status_code == 200
            return {"connected": self.connected, "status": resp.status_code}
        except Exception as e:
            self.connected = False
            return {"connected": False, "error": str(e)}

    async def get_states(self, use_cache: bool = True) -> list:
        """获取所有实体状态，默认使用30s缓存"""
        now = time.monotonic()
        if use_cache and self._states_cache and (now - self._cache_time) < _CACHE_TTL:
            return self._states_cache
        try:
            await self._ensure_client()
            resp = await self.client.get(f"{self.url}/api/states", headers=self.headers)
            resp.raise_for_status()
            self._states_cache = resp.json()
            self._cache_time = now
            self.connected = True
            return self._states_cache
        except Exception as e:
            self.connected = False
            if self._states_cache:
                logger.warning("HA offline, returning cached states (%d entities)", len(self._states_cache))
                return self._states_cache
            raise

    async def get_state(self, entity_id: str) -> dict:
        await self._ensure_client()
        resp = await self.client.get(f"{self.url}/api/states/{entity_id}", headers=self.headers)
        resp.raise_for_status()
        return resp.json()

    async def call_service(self, domain: str, service: str, data: dict) -> list:
        await self._ensure_client()
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
