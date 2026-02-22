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

import asyncio
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
    "大灯": "筒灯",
    "主灯": "筒灯",
    "床底灯": "床底灯",
    "台灯": "床底灯",
    # 风扇 (实际设备名: 米家智能直流变频循环落地扇)
    "风扇": "落地扇",
    "电风扇": "落地扇",
    "电扇": "落地扇",
    "落地扇": "循环落地扇",
    # 音箱
    "音箱": "音箱",
    "小爱": "小爱",
    # 开关(编号 + 数字)
    "一号": "一号", "1号": "一号",
    "二号": "二号", "2号": "二号",
    "三号": "三号", "3号": "三号",
    # 家电
    "电饭煲": "电饭煲",
    "电热毯": "电热毯",
    "晾衣机": "晾衣机",
    "充电器": "充电器",
    # 摄像头
    "摄像头": "摄像机",
    "摄像机": "摄像机",
}

# 场景宏别名 (精确 + 自然语言表达)
SCENE_ALIASES = {
    "回家": "home", "回家模式": "home", "到家": "home",
    "我回来了": "home", "到家了": "home", "回来了": "home",
    "离家": "away", "离家模式": "away", "出门": "away",
    "我出门了": "away", "走了": "away", "出发": "away",
    "睡觉": "sleep", "睡眠": "sleep", "睡眠模式": "sleep", "晚安": "sleep",
    "困了": "sleep", "睡了": "sleep", "休息": "sleep",
    "看电影": "movie", "观影": "movie", "观影模式": "movie", "电影模式": "movie",
    "工作": "work", "工作模式": "work", "学习": "work", "学习模式": "work",
}

# 舒适意图: 人的体感 → (动作, 设备关键词, 成功回复)
COMFORT_INTENTS = {
    "太冷了": ("turn_on", "电热毯", "🌡️ 已开启电热毯"),
    "好冷": ("turn_on", "电热毯", "🌡️ 已开启电热毯"),
    "冷死了": ("turn_on", "电热毯", "🌡️ 已开启电热毯"),
    "暖和点": ("turn_on", "电热毯", "🌡️ 已开启电热毯"),
    "太热了": ("turn_on", "落地扇", "🌀 已开启风扇"),
    "好热": ("turn_on", "落地扇", "🌀 已开启风扇"),
    "热死了": ("turn_on", "落地扇", "🌀 已开启风扇"),
    "凉快点": ("turn_on", "落地扇", "🌀 已开启风扇"),
    "太暗了": ("turn_on", "筒灯", "💡 已开灯"),
    "好暗": ("turn_on", "筒灯", "💡 已开灯"),
    "太亮了": ("turn_off", "筒灯", "💡 已关灯"),
    "好亮": ("turn_off", "筒灯", "💡 已关灯"),
    "有点冷": ("turn_on", "电热毯", "🌡️ 已开启电热毯"),
    "有点热": ("turn_on", "落地扇", "🌀 已开启风扇"),
    "看不清": ("turn_on", "筒灯", "💡 已开灯"),
    "看不见": ("turn_on", "筒灯", "💡 已开灯"),
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
        text = text.strip().rstrip("。！？!?.，,~～…")
        if not text:
            return "发送指令控制智能家居，输入「帮助」查看命令列表"

        # 1. 帮助
        if text in ("帮助", "help", "?", "？", "命令"):
            return self._help()

        # 2. 设备状态查询
        if text in ("状态", "设备", "设备列表", "所有设备"):
            return await self._device_status()

        # 3. 场景宏 (精确 + 模糊匹配)
        scene_key = self._match_scene(text)
        if scene_key:
            return await self._execute_scene(scene_key)

        # 3.5 舒适意图: "太冷了" → 开电热毯 (精确+模糊)
        comfort = self._match_comfort(text)
        if comfort:
            action, keyword, msg = comfort
            result = await self._control_device(keyword, action)
            return msg if "已" in result else result

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
        return """🏠 智能家居控制
📱 设备: 打开灯带 / 关闭风扇
🎬 场景: 回家 / 睡觉 / 离家 / 工作 / 观影
⚡ 快捷: 全关 / 全开 / 关灯 / 开灯
🌡️ 舒适: 太冷了 / 太热了 / 太暗了
🔊 播报: 说 你好世界
📊 状态: 状态
🤖 其他: 直接说，转给小爱"""

    def _match_comfort(self, text: str) -> Optional[tuple]:
        """匹配舒适意图: 精确 → 关键词包含(如'好冷啊'包含'好冷')"""
        c = COMFORT_INTENTS.get(text)
        if c:
            return c
        for key in sorted(COMFORT_INTENTS, key=len, reverse=True):
            if len(key) >= 2 and key in text:
                return COMFORT_INTENTS[key]
        return None

    def _match_scene(self, text: str) -> Optional[str]:
        """匹配场景: 精确别名 → 关键词包含(如'我要睡觉了'包含'睡觉')"""
        key = SCENE_ALIASES.get(text)
        if key:
            return key
        for alias in sorted(SCENE_ALIASES, key=len, reverse=True):
            if len(alias) >= 2 and alias in text:
                return SCENE_ALIASES[alias]
        return None

    async def _device_status(self) -> str:
        """查询设备状态 — 按类型分组精简显示"""
        micloud = self.gw.get("micloud")
        ewelink = self.gw.get("ewelink")
        devices = []
        if micloud:
            devices.extend(micloud.get_devices())
        if ewelink and ewelink.at:
            devices.extend(ewelink.get_devices())
        if not devices:
            return "📊 暂无设备连接"
        cat_map = {
            "light": "💡灯", "switch": "🔌开关", "media_player": "🔊音箱",
            "fan": "🌀风扇", "cover": "🏠家电", "climate": "🌡️温控",
        }
        groups = {}
        online = 0
        for d in devices:
            cat = cat_map.get(d.get("domain", ""), "")
            if not cat:
                continue
            name = d.get("name", "?").replace("米家智能", "").replace("小米", "")
            if d.get("isOnline"):
                online += 1
                name += "✅"
            groups.setdefault(cat, []).append(name)
        lines = [f"📊 {len(devices)}台设备 | {online}台在线"]
        for cat, items in groups.items():
            lines.append(f"{cat}: {' / '.join(items)}")
        return "\n".join(lines)

    async def _execute_scene(self, scene_key: str) -> str:
        """执行场景宏 — 立即返回确认，后台异步执行（避免微信5秒超时）"""
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

        # 场景宏含多个命令+sleep，总耗时可能>5秒 → 后台执行
        async def _run_scene():
            did = str(target["did"])
            for cmd in scene["commands"]:
                try:
                    micloud.control_device(did, "execute_command", cmd, {"silent": True})
                except Exception as e:
                    logger.error("Scene command '%s' failed: %s", cmd, e)
                await asyncio.sleep(2)

        asyncio.create_task(_run_scene())
        steps = " → ".join(scene["commands"])
        return f"🎬 {scene['name']} 执行中...\n{steps}"

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
        """执行快捷操作 — 后台异步执行（避免微信5秒超时）"""
        micloud = self.gw.get("micloud")
        if not micloud:
            return f"⚡ {action}: 后端不可用"

        action_names = {
            "all_off": "全部关闭", "all_on": "全部打开",
            "lights_off": "关灯", "lights_on": "开灯",
            "fans_off": "关闭风扇",
        }

        async def _run():
            try:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, micloud.quick_action, action)
            except Exception as e:
                logger.error("Quick action '%s' failed: %s", action, e)

        asyncio.create_task(_run())
        return f"⚡ {action_names.get(action, action)} 执行中..."

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
        """解析设备控制命令: '打开灯带' / '灯带打开' / '把灯打开' → {name_keyword, action, value}"""
        action = None
        remaining = text

        # 正序: 动作+设备 ("打开灯带")
        for kw in sorted(ON_KEYWORDS, key=len, reverse=True):
            if text.startswith(kw):
                action = "turn_on"
                remaining = text[len(kw):].strip()
                break
        if not action:
            for kw in sorted(OFF_KEYWORDS, key=len, reverse=True):
                if text.startswith(kw):
                    action = "turn_off"
                    remaining = text[len(kw):].strip()
                    break
        if not action:
            for kw in sorted(TOGGLE_KEYWORDS, key=len, reverse=True):
                if text.startswith(kw):
                    action = "toggle"
                    remaining = text[len(kw):].strip()
                    break

        # "把X打开/关了/关掉" 句式 (优先于反序，避免"把灯"误匹配)
        if not action:
            m = re.match(r'把(.+?)(打开|开启|关闭|关掉|关了|开|关)', text)
            if m:
                remaining = m.group(1).strip()
                action = "turn_on" if m.group(2) in ("打开", "开启", "开") else "turn_off"

        # 反序: 设备+动作 ("灯带打开" / "灯带开")
        if not action:
            for kw in sorted(ON_KEYWORDS, key=len, reverse=True):
                if text.endswith(kw):
                    action = "turn_on"
                    remaining = text[:-len(kw)].strip()
                    break
        if not action:
            for kw in sorted(OFF_KEYWORDS, key=len, reverse=True):
                if text.endswith(kw):
                    action = "turn_off"
                    remaining = text[:-len(kw)].strip()
                    break

        if not action or not remaining:
            return None

        # 去口语虚词
        for filler in ("一下", "一个", "那个", "这个"):
            remaining = remaining.replace(filler, "")
        remaining = remaining.strip()
        if not remaining:
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
            for dev in micloud.get_devices():
                name = dev.get("name", "")
                eid = str(dev.get("id", dev.get("did", "")))
                if keyword in name or name in keyword:
                    return ("micloud", eid, dev)

        if ewelink and ewelink.at:
            for dev in ewelink.get_devices():
                name = dev.get("name", "")
                eid = str(dev.get("id", dev.get("deviceid", "")))
                if keyword in name or name in keyword:
                    return ("ewelink", eid, dev)

        return None

    async def _control_device(self, name_keyword: str, action: str, value=None) -> str:
        """通过名称关键词匹配并控制设备"""
        found = self._find_device_by_name(name_keyword)
        if not found:
            names = '/'.join(sorted(DEVICE_ALIASES.keys())[:12])
            return f"未找到'{name_keyword}'\n💡 可用: {names}"

        backend, eid, dev = found
        name = dev.get("name", eid).replace("米家智能", "").replace("小米", "")

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
        return f"❌ {name}: {self._humanize_error(result.get('error', '控制失败'))}"

    @staticmethod
    def _humanize_error(error: str) -> str:
        """原始错误代码 → 人话"""
        if "device_offline" in error or "-704042011" in error:
            return "设备离线(未通电或WiFi断开)"
        if "-704220043" in error:
            return "登录过期，请发送'刷新'"
        if "-704010000" in error:
            return "未授权"
        if "not found" in error.lower():
            return "设备不存在"
        return error

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
