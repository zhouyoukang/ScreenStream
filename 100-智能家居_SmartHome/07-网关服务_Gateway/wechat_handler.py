#!/usr/bin/env python3
"""
微信公众号消息处理模块 — 智能家居语音/文字控制入口

架构: 微信服务器 → POST /wx (XML) → 本模块解析 → Gateway API 内部调用 → XML回复

支持的命令:
  设备控制: "打开灯带" "关闭风扇" "开灯" "关灯"
  设备状态: "状态" "设备列表"
  场景宏:   "回家模式" "睡眠模式" "离家模式" "工作模式" "观影模式"
  音箱TTS:  "说 你好" "播报 欢迎回家"
  快捷操作: "全部关闭" "全部打开" "关闭所有灯"
  帮助:     "帮助" "help" "?"
"""

import hashlib
import time
import re
import logging
from typing import Optional
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)


# ============================================================
# XML 解析与生成
# ============================================================

def parse_xml(xml_bytes: bytes) -> dict:
    """解析微信推送的 XML 消息"""
    root = ET.fromstring(xml_bytes)
    msg = {}
    for child in root:
        msg[child.tag] = child.text or ""
    return msg


def text_reply(from_user: str, to_user: str, content: str) -> str:
    """生成文本回复 XML"""
    return f"""<xml>
<ToUserName><![CDATA[{from_user}]]></ToUserName>
<FromUserName><![CDATA[{to_user}]]></FromUserName>
<CreateTime>{int(time.time())}</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[{content}]]></Content>
</xml>"""


def verify_signature(token: str, signature: str, timestamp: str, nonce: str) -> bool:
    """验证微信服务器签名"""
    tmp = sorted([token, timestamp, nonce])
    tmp_str = "".join(tmp)
    computed = hashlib.sha1(tmp_str.encode("utf-8")).hexdigest()
    return computed == signature


# ============================================================
# 命令解析引擎
# ============================================================

# 设备名称别名映射 → 用户输入关键词 : 设备名称中的匹配关键词
# MiCloud 设备用数字 DID (如 531616941)，匹配靠设备名称
DEVICE_ALIASES = {
    # 灯
    "灯带": "灯带",
    "飞利浦灯带": "灯带",
    "rgb灯": "灯带",
    "筒灯": "筒灯",
    "床底灯": "床底灯",
    # 风扇
    "风扇": "风扇",
    "电风扇": "风扇",
    "落地扇": "循环落地扇",
    # 音箱
    "音箱": "音箱",
    "小爱": "小爱",
    # 开关(编号)
    "一号": "一号",
    "二号": "二号",
    "三号": "三号",
    # 家电
    "电饭煲": "电饭煲",
    "电热毯": "电热毯",
    "晾衣机": "晾衣机",
    "充电器": "充电器",
    # 摄像头
    "摄像头": "摄像机",
    "摄像机": "摄像机",
}

# 场景宏别名
SCENE_ALIASES = {
    "回家": "home", "回家模式": "home", "到家": "home",
    "离家": "away", "离家模式": "away", "出门": "away",
    "睡觉": "sleep", "睡眠": "sleep", "睡眠模式": "sleep", "晚安": "sleep",
    "看电影": "movie", "观影": "movie", "观影模式": "movie",
    "工作": "work", "工作模式": "work", "学习": "work",
}

# 动作关键词
ON_KEYWORDS = {"打开", "开", "开启", "启动", "on", "开灯"}
OFF_KEYWORDS = {"关闭", "关", "关掉", "停止", "off", "关灯"}
TOGGLE_KEYWORDS = {"切换", "toggle"}


class WeChatCommandRouter:
    """将微信文本消息路由到 Gateway 内部函数调用"""

    def __init__(self, gateway_ref):
        """
        gateway_ref: dict containing references to gateway internals:
            - micloud: MiCloudDirect instance
            - ewelink: EWeLinkClient instance
            - mina: MinaClient instance
            - scene_macros: dict of scene macros
            - find_speaker: callable returning best speaker
        """
        self.gw = gateway_ref

    async def handle_text(self, text: str) -> str:
        """处理文本命令，返回回复文本"""
        text = text.strip()
        if not text:
            return "发送指令控制智能家居，输入「帮助」查看命令列表"

        # 1. 帮助
        if text in ("帮助", "help", "?", "？", "命令"):
            return self._help()

        # 2. 设备状态查询
        if text in ("状态", "设备", "设备列表", "所有设备"):
            return await self._device_status()

        # 3. 场景宏
        scene_key = SCENE_ALIASES.get(text)
        if scene_key:
            return await self._execute_scene(scene_key)

        # 4. 快捷操作
        quick = self._parse_quick_action(text)
        if quick:
            return await self._quick_action(quick)

        # 5. TTS 播报
        tts_text = self._parse_tts(text)
        if tts_text:
            return await self._tts(tts_text)

        # 6. 设备控制（打开/关闭 + 设备名）
        ctrl = self._parse_device_control(text)
        if ctrl:
            return await self._control_device(ctrl["name_keyword"], ctrl["action"], ctrl["value"])

        # 7. 音箱语音代理（直接转发自然语言给小爱）
        if text.startswith("小爱") or text.startswith("语音"):
            cmd = text.lstrip("小爱").lstrip("语音").strip()
            if cmd:
                return await self._voice_proxy(cmd)

        # 8. 未识别 → 尝试音箱代理
        return await self._voice_proxy(text)

    def _help(self) -> str:
        return """🏠 智能家居控制 — 命令列表

📱 设备控制:
  打开灯带 / 关闭风扇
  打开四号开关 / 关闭床插头

📊 状态查询:
  状态 / 设备列表

🎬 场景模式:
  回家模式 / 睡眠模式 / 离家模式
  工作模式 / 观影模式

⚡ 快捷操作:
  全部关闭 / 全部打开
  关灯 / 开灯

🔊 音箱播报:
  说 你好世界
  播报 欢迎回家

🤖 自然语言(转小爱):
  直接输入任意指令，自动转发给小爱音箱"""

    async def _device_status(self) -> str:
        """查询所有设备状态"""
        lines = ["📊 设备状态\n"]
        micloud = self.gw.get("micloud")
        ewelink = self.gw.get("ewelink")

        if micloud:
            devices = micloud.get_devices()
            for d in devices:
                icon = "🟢" if d.get("state") == "on" else "⚪"
                name = d.get("name", d.get("id", "?"))
                state = d.get("state", "unknown")
                lines.append(f"{icon} {name}: {state}")

        if ewelink and ewelink.at:
            devices = ewelink.get_devices()
            for d in devices:
                icon = "🟢" if d.get("state") == "on" else "⚪"
                name = d.get("name", d.get("id", "?"))
                state = d.get("state", "unknown")
                lines.append(f"{icon} {name}: {state}")

        if len(lines) == 1:
            lines.append("暂无设备连接")

        return "\n".join(lines)

    async def _execute_scene(self, scene_key: str) -> str:
        """执行场景宏"""
        macros = self.gw.get("scene_macros", {})
        scene = macros.get(scene_key)
        if not scene:
            return f"未知场景: {scene_key}"

        micloud = self.gw.get("micloud")
        find_speaker = self.gw.get("find_speaker")
        if not micloud or not find_speaker:
            return "音箱代理不可用，无法执行场景"

        target = find_speaker()
        if not target:
            return "没有在线音箱，无法执行场景"

        did = str(target["did"])
        results = []
        import asyncio
        for cmd in scene["commands"]:
            result = micloud.control_device(did, "execute_command", cmd, {"silent": True})
            ok = result.get("ok", False)
            results.append(f"  {'✅' if ok else '❌'} {cmd}")
            await asyncio.sleep(2)

        ok_count = sum(1 for r in results if "✅" in r)
        header = f"🎬 {scene['name']} ({ok_count}/{len(results)})\n"
        return header + "\n".join(results)

    def _parse_quick_action(self, text: str) -> Optional[str]:
        """解析快捷操作"""
        mapping = {
            "全部关闭": "all_off", "全关": "all_off", "全部关": "all_off",
            "全部打开": "all_on", "全开": "all_on",
            "关灯": "lights_off", "关闭所有灯": "lights_off",
            "开灯": "lights_on", "打开所有灯": "lights_on",
            "关闭风扇": "fans_off", "关扇": "fans_off",
        }
        return mapping.get(text)

    async def _quick_action(self, action: str) -> str:
        """执行快捷操作"""
        micloud = self.gw.get("micloud")
        if micloud:
            result = micloud.quick_action(action)
            affected = result.get("affected", 0)
            return f"⚡ {action}: 已操作 {affected} 个设备"
        return f"⚡ {action}: 后端不可用"

    def _parse_tts(self, text: str) -> Optional[str]:
        """解析TTS命令"""
        for prefix in ("说 ", "说:", "说：", "播报 ", "播报:", "播报：", "tts "):
            if text.lower().startswith(prefix):
                return text[len(prefix):].strip()
        return None

    async def _tts(self, text: str) -> str:
        """发送TTS到音箱"""
        micloud = self.gw.get("micloud")
        find_speaker = self.gw.get("find_speaker")
        if not micloud or not find_speaker:
            # 尝试 Mina
            mina = self.gw.get("mina")
            if mina and mina.token:
                result = await mina.tts(text)
                if result.get("ok"):
                    return f"🔊 已播报: {text}"
            return "音箱不可用"

        target = find_speaker()
        if not target:
            return "没有在线音箱"

        did = str(target["did"])
        result = micloud.control_device(did, "play_text", text)
        if result.get("ok"):
            return f"🔊 已播报: {text}"
        return f"播报失败: {result.get('error', '未知错误')}"

    def _parse_device_control(self, text: str) -> Optional[dict]:
        """解析设备控制命令: '打开灯带' → {name_keyword, action, value}"""
        action = None
        remaining = text

        for kw in ON_KEYWORDS:
            if text.startswith(kw):
                action = "turn_on"
                remaining = text[len(kw):].strip()
                break
        if not action:
            for kw in OFF_KEYWORDS:
                if text.startswith(kw):
                    action = "turn_off"
                    remaining = text[len(kw):].strip()
                    break
        if not action:
            for kw in TOGGLE_KEYWORDS:
                if text.startswith(kw):
                    action = "toggle"
                    remaining = text[len(kw):].strip()
                    break

        if not action or not remaining:
            return None

        # 匹配设备别名 → 设备名称关键词
        name_keyword = DEVICE_ALIASES.get(remaining.lower()) or DEVICE_ALIASES.get(remaining)
        if name_keyword:
            return {"name_keyword": name_keyword, "action": action, "value": None}

        # 没有别名也直接尝试用原文匹配设备名
        return {"name_keyword": remaining, "action": action, "value": None}

    def _find_device_by_name(self, keyword: str) -> Optional[tuple]:
        """按名称关键词在所有后端中查找设备，返回 (backend_name, device_id, device_info)"""
        micloud = self.gw.get("micloud")
        ewelink = self.gw.get("ewelink")

        if micloud:
            for eid, dev in micloud._device_map.items():
                name = dev.get("name", "")
                if keyword in name or name in keyword:
                    return ("micloud", eid, dev)

        if ewelink and ewelink.at:
            for eid, dev in ewelink._device_map.items():
                name = dev.get("name", "")
                if keyword in name or name in keyword:
                    return ("ewelink", eid, dev)

        return None

    async def _control_device(self, name_keyword: str, action: str, value=None) -> str:
        """通过名称关键词匹配并控制设备"""
        found = self._find_device_by_name(name_keyword)
        if not found:
            return f"未找到匹配'{name_keyword}'的设备"

        backend, eid, dev = found
        name = dev.get("name", eid)

        if backend == "micloud":
            micloud = self.gw.get("micloud")
            result = micloud.control_device(eid, action, value)
        elif backend == "ewelink":
            ewelink = self.gw.get("ewelink")
            result = await ewelink.control_device(eid, action, value)
        else:
            return f"未知后端: {backend}"

        if result.get("ok"):
            emoji = "🟢" if action == "turn_on" else "⚪" if action == "turn_off" else "🔄"
            action_text = "已打开" if action == "turn_on" else "已关闭" if action == "turn_off" else "已切换"
            return f"{emoji} {name}: {action_text}"
        return f"❌ {name}: {result.get('error', '控制失败')}"

    async def _voice_proxy(self, command: str) -> str:
        """通过音箱代理执行自然语言命令"""
        micloud = self.gw.get("micloud")
        find_speaker = self.gw.get("find_speaker")
        if not micloud or not find_speaker:
            return f"音箱代理不可用。你说的是: {command}"

        target = find_speaker()
        if not target:
            return "没有在线音箱，无法执行语音代理"

        did = str(target["did"])
        result = micloud.control_device(did, "execute_command", command, {"silent": True})
        if result.get("ok"):
            return f"🤖 已发送给小爱: {command}"
        return f"❌ 语音代理失败: {result.get('error', '?')}"

    async def handle_event(self, event_type: str, event_key: str = "") -> str:
        """处理事件消息（关注/取关/菜单点击）"""
        if event_type == "subscribe":
            return """🏠 欢迎使用智能家居控制!

发送文字指令即可控制家中设备:
  打开灯带 / 关闭风扇
  回家模式 / 睡眠模式
  状态 / 帮助

更多命令输入「帮助」查看"""

        if event_type == "unsubscribe":
            return ""

        if event_type == "CLICK":
            # 自定义菜单点击
            action_map = {
                "STATUS": "状态",
                "ALL_OFF": "全部关闭",
                "SCENE_HOME": "回家模式",
                "SCENE_SLEEP": "睡眠模式",
                "HELP": "帮助",
            }
            cmd = action_map.get(event_key, "")
            if cmd:
                return await self.handle_text(cmd)

        return ""
