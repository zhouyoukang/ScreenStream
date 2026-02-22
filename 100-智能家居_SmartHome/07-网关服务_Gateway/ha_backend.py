#!/usr/bin/env python3
"""
Home Assistant REST API 客户端
可选后端 — 提供场景/历史/模板渲染等高级功能
"""

from typing import Optional

import httpx


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
