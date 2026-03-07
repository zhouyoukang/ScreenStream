#!/usr/bin/env python3
"""
微信公众号 API 客户端 — access_token管理 + 自定义菜单 + 模板消息 + 用户管理 + 二维码

架构: gateway.py → 本模块 → WeChat API (api.weixin.qq.com)

依赖: httpx (已在 requirements.txt)
"""

import time
import json
import logging
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

WECHAT_API_BASE = "https://api.weixin.qq.com"
TOKEN_CACHE_FILE = Path(__file__).parent / ".wechat_token_cache.json"


class WeChatAPI:
    """微信公众号 API 封装 — 零外部SDK依赖"""

    def __init__(self, appid: str, appsecret: str):
        self.appid = appid
        self.appsecret = appsecret
        self._access_token = ""
        self._token_expires_at = 0
        self._load_cached_token()

    # ============================================================
    # Access Token 管理（自动刷新 + 文件缓存）
    # ============================================================

    def _load_cached_token(self):
        """从文件加载缓存的 access_token"""
        try:
            if TOKEN_CACHE_FILE.exists():
                data = json.loads(TOKEN_CACHE_FILE.read_text(encoding="utf-8"))
                if data.get("appid") == self.appid and data.get("expires_at", 0) > time.time() + 60:
                    self._access_token = data["access_token"]
                    self._token_expires_at = data["expires_at"]
                    logger.info("Loaded cached access_token (expires in %ds)", int(self._token_expires_at - time.time()))
        except Exception as e:
            logger.warning("Failed to load token cache: %s", e)

    def _save_token_cache(self):
        """将 access_token 缓存到文件"""
        try:
            TOKEN_CACHE_FILE.write_text(json.dumps({
                "appid": self.appid,
                "access_token": self._access_token,
                "expires_at": self._token_expires_at,
            }, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.warning("Failed to save token cache: %s", e)

    def get_access_token(self) -> str:
        """获取 access_token（自动刷新，提前60秒过期）"""
        if self._access_token and time.time() < self._token_expires_at - 60:
            return self._access_token
        return self._refresh_access_token()

    def _refresh_access_token(self) -> str:
        """从微信服务器刷新 access_token"""
        url = f"{WECHAT_API_BASE}/cgi-bin/token"
        params = {
            "grant_type": "client_credential",
            "appid": self.appid,
            "secret": self.appsecret,
        }
        try:
            resp = httpx.get(url, params=params, timeout=10)
            data = resp.json()
            if "access_token" in data:
                self._access_token = data["access_token"]
                self._token_expires_at = time.time() + data.get("expires_in", 7200)
                self._save_token_cache()
                logger.info("Refreshed access_token (expires_in=%d)", data.get("expires_in", 0))
                return self._access_token
            else:
                logger.error("Failed to get access_token: %s", data)
                return ""
        except Exception as e:
            logger.error("access_token request failed: %s", e)
            return ""

    def _api_get(self, path: str, params: dict = None, _retried: bool = False) -> dict:
        """通用 GET 请求（40001自动重试）"""
        token = self.get_access_token()
        if not token:
            return {"errcode": -1, "errmsg": "no access_token"}
        url = f"{WECHAT_API_BASE}{path}"
        p = {"access_token": token}
        if params:
            p.update(params)
        try:
            resp = httpx.get(url, params=p, timeout=15)
            result = resp.json()
            if result.get("errcode") in (40001, 42001) and not _retried:
                logger.warning("Token expired in GET %s, refreshing...", path)
                self._access_token = ""
                self._token_expires_at = 0
                return self._api_get(path, params, _retried=True)
            return result
        except Exception as e:
            return {"errcode": -1, "errmsg": str(e)}

    def _api_post(self, path: str, data: dict, _retried: bool = False) -> dict:
        """通用 POST 请求（40001自动重试）"""
        token = self.get_access_token()
        if not token:
            return {"errcode": -1, "errmsg": "no access_token"}
        url = f"{WECHAT_API_BASE}{path}?access_token={token}"
        try:
            resp = httpx.post(url, json=data, timeout=15)
            result = resp.json()
            if result.get("errcode") in (40001, 42001) and not _retried:
                logger.warning("Token expired in POST %s, refreshing...", path)
                self._access_token = ""
                self._token_expires_at = 0
                return self._api_post(path, data, _retried=True)
            return result
        except Exception as e:
            return {"errcode": -1, "errmsg": str(e)}

    # ============================================================
    # 自定义菜单
    # ============================================================

    def create_menu(self, menu: dict) -> dict:
        """创建自定义菜单"""
        result = self._api_post("/cgi-bin/menu/create", menu)
        if result.get("errcode", -1) == 0:
            logger.info("Menu created successfully")
        else:
            logger.error("Menu creation failed: %s", result)
        return result

    def get_menu(self) -> dict:
        """查询当前菜单"""
        return self._api_get("/cgi-bin/get_current_selfmenu_info")

    def delete_menu(self) -> dict:
        """删除菜单"""
        return self._api_get("/cgi-bin/menu/delete")

    # ============================================================
    # 用户管理
    # ============================================================

    def get_user_list(self, next_openid: str = "") -> dict:
        """获取关注者列表"""
        params = {}
        if next_openid:
            params["next_openid"] = next_openid
        return self._api_get("/cgi-bin/user/get", params)

    def get_user_info(self, openid: str) -> dict:
        """获取用户基本信息"""
        return self._api_get("/cgi-bin/user/info", {"openid": openid, "lang": "zh_CN"})

    def batch_get_user_info(self, openid_list: list) -> dict:
        """批量获取用户信息"""
        data = {"user_list": [{"openid": oid, "lang": "zh_CN"} for oid in openid_list]}
        return self._api_post("/cgi-bin/user/info/batchget", data)

    # ============================================================
    # 客服消息（48小时内互动的用户可主动推送）
    # ============================================================

    def send_text_message(self, openid: str, content: str) -> dict:
        """发送文本客服消息"""
        return self._api_post("/cgi-bin/message/custom/send", {
            "touser": openid,
            "msgtype": "text",
            "text": {"content": content},
        })

    def send_news_message(self, openid: str, articles: list) -> dict:
        """发送图文客服消息 (articles: [{title, description, picurl, url}])"""
        return self._api_post("/cgi-bin/message/custom/send", {
            "touser": openid,
            "msgtype": "news",
            "news": {"articles": articles},
        })

    # ============================================================
    # 模板消息
    # ============================================================

    def get_template_list(self) -> dict:
        """获取已添加的模板列表"""
        return self._api_get("/cgi-bin/template/get_all_private_template")

    def send_template_message(self, openid: str, template_id: str,
                              data: dict, url: str = "", miniprogram: dict = None) -> dict:
        """发送模板消息
        data 格式: {"key1": {"value": "xxx", "color": "#173177"}, ...}
        """
        msg = {
            "touser": openid,
            "template_id": template_id,
            "data": data,
        }
        if url:
            msg["url"] = url
        if miniprogram:
            msg["miniprogram"] = miniprogram
        return self._api_post("/cgi-bin/message/template/send", msg)

    # ============================================================
    # 二维码（临时/永久）
    # ============================================================

    def create_qrcode(self, scene: str, expire_seconds: int = 2592000, permanent: bool = False) -> dict:
        """创建带参数的二维码
        scene: 场景值（字符串）
        expire_seconds: 临时码有效期，最长30天(2592000)
        permanent: 永久码(无过期，数量有限10万)
        """
        if permanent:
            data = {
                "action_name": "QR_LIMIT_STR_SCENE",
                "action_info": {"scene": {"scene_str": scene}},
            }
        else:
            data = {
                "expire_seconds": expire_seconds,
                "action_name": "QR_STR_SCENE",
                "action_info": {"scene": {"scene_str": scene}},
            }
        result = self._api_post("/cgi-bin/qrcode/create", data)
        if "ticket" in result:
            result["qrcode_url"] = f"https://mp.weixin.qq.com/cgi-bin/showqrcode?ticket={result['ticket']}"
        return result

    # ============================================================
    # 公众号信息
    # ============================================================

    def get_api_quota(self, cgi_path: str) -> dict:
        """查询 API 调用额度"""
        return self._api_post("/cgi-bin/openapi/quota/get", {"cgi_path": cgi_path})

    def status(self) -> dict:
        """返回当前状态概览"""
        token = self.get_access_token()
        return {
            "appid": self.appid[:8] + "..." if self.appid else "",
            "has_token": bool(token),
            "token_expires_in": max(0, int(self._token_expires_at - time.time())) if token else 0,
        }


# ============================================================
# 智能家居专用菜单预设
# ============================================================

SMART_HOME_MENU = {
    "button": [
        {
            "name": "💡 控制",
            "sub_button": [
                {"type": "click", "name": "全部关闭", "key": "ALL_OFF"},
                {"type": "click", "name": "开灯", "key": "LIGHTS_ON"},
                {"type": "click", "name": "关灯", "key": "LIGHTS_OFF"},
                {"type": "click", "name": "开风扇", "key": "FAN_ON"},
                {"type": "click", "name": "关风扇", "key": "FAN_OFF"},
            ]
        },
        {
            "name": "🎬 场景",
            "sub_button": [
                {"type": "click", "name": "回家模式", "key": "SCENE_HOME"},
                {"type": "click", "name": "睡眠模式", "key": "SCENE_SLEEP"},
                {"type": "click", "name": "离家模式", "key": "SCENE_AWAY"},
                {"type": "click", "name": "工作模式", "key": "SCENE_WORK"},
                {"type": "click", "name": "观影模式", "key": "SCENE_MOVIE"},
            ]
        },
        {
            "name": "📊 更多",
            "sub_button": [
                {"type": "click", "name": "设备状态", "key": "STATUS"},
                {"type": "click", "name": "帮助", "key": "HELP"},
                {"type": "view", "name": "控制面板",
                 "url": "https://aiotvr.xyz/wx/web"},
            ]
        },
    ]
}
