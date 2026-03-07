"""
Voxta 统一Agent — Voxta AI对话引擎控制中枢

五感架构(Voxta视角):
  视(Vision)  — Voxta仪表板/角色/模块/日志/角色详情
  听(Audio)   — Voxta服务状态/SignalR连接/端口探测
  触(Touch)   — 服务启停/备份/模块开关/对话/角色CRUD/TavernCard导入/自动修复
  嗅(Scent)   — 模块配置评估/全链路诊断/安全扫描
  味(Taste)   — 健康评估/综合评分/文本报告/JSON报告
"""
from datetime import datetime
from typing import Optional

from .config import VOXTA_CONFIG
from . import db, signalr, logs, process


class VoxtaAgent:
    """Voxta五感Agent — 统一控制中枢"""

    def __init__(self):
        self.config = VOXTA_CONFIG
        self._hub = None
        self._chat_engine = None

    @property
    def hub(self):
        """懒加载hub模块"""
        if self._hub is None:
            from .hub import VoxtaDB
            self._hub = VoxtaDB()
        return self._hub

    @property
    def chat_engine(self):
        """懒加载chat模块"""
        if self._chat_engine is None:
            from .chat import ChatEngine
            self._chat_engine = ChatEngine()
        return self._chat_engine

    # ══════════════════════════════════════════════
    # 视 · Vision — Voxta状态感知
    # ══════════════════════════════════════════════

    def see_critical_paths(self) -> dict:
        """视·Voxta文件完整性"""
        return self.config.get_all_critical_paths()

    def see_dashboard(self) -> dict:
        """视·Voxta仪表板"""
        return db.dashboard()

    def see_characters(self) -> list:
        """视·角色列表"""
        return db.list_characters()

    def see_character_detail(self, char_id: str) -> Optional[dict]:
        """视·角色完整详情"""
        return self.hub.get_character_detail(char_id)

    def see_modules(self) -> list:
        """视·模块列表"""
        return db.list_modules()

    def see_scenarios(self) -> list:
        """视·场景列表"""
        return db.list_scenarios()

    def see_presets(self) -> list:
        """视·预设列表"""
        return db.list_presets()

    def see_hub_presets(self) -> list:
        """视·预设详情(含参数)"""
        return self.hub.list_presets()

    def see_memory_books(self) -> list:
        """视·记忆书"""
        return db.list_memory_books()

    def see_hub_memory_books(self) -> list:
        """视·记忆书详情(含条目)"""
        return self.hub.list_memory_books()

    def see_log(self, tail: int = 50) -> list:
        """视·Voxta日志"""
        return logs.read_voxta_log(tail)

    def see_chats(self, limit: int = 20) -> list:
        """视·最近对话"""
        return db.list_chats(limit)

    def see_messages(self, limit: int = 20) -> list:
        """视·最近消息"""
        return db.recent_messages(limit)

    def see_hub_messages(self, limit: int = 20) -> list:
        """视·最近消息(完整字段)"""
        return self.hub.recent_messages(limit)

    def see_stats(self) -> dict:
        """视·数据库统计"""
        return db.get_stats()

    def see_all_tables(self) -> dict:
        """视·所有表及行数"""
        return self.hub.get_all_tables()

    def see_appsettings(self) -> dict:
        """视·Voxta appsettings.json"""
        return db.read_appsettings()

    # ══════════════════════════════════════════════
    # 听 · Audio — Voxta服务状态监控
    # ══════════════════════════════════════════════

    def hear_services(self) -> dict:
        """听·所有Voxta服务状态"""
        return process.get_all_status()

    def hear_port(self, port: int) -> bool:
        """听·端口探测"""
        return process.check_port(port)

    def hear_signalr(self) -> dict:
        """听·Voxta SignalR连接状态"""
        return signalr.check_signalr()

    def hear_edgetts(self) -> Optional[dict]:
        """听·EdgeTTS健康状态"""
        from .hub import DirectAPI
        return DirectAPI.edgetts_health()

    def hear_edgetts_voices(self) -> Optional[list]:
        """听·EdgeTTS可用声音列表"""
        from .hub import DirectAPI
        return DirectAPI.edgetts_voices()

    # ══════════════════════════════════════════════
    # 触 · Touch — 主动操作
    # ══════════════════════════════════════════════

    def touch_start_service(self, key: str) -> tuple:
        """触·启动Voxta服务"""
        return process.start_service(key)

    def touch_start_all(self, include_textgen: bool = False) -> list:
        """触·启动完整Voxta服务栈"""
        return process.start_full_stack(include_textgen)

    def touch_backup(self) -> str:
        """触·备份Voxta数据库"""
        return self.hub.backup()

    def touch_set_module(self, module_id: str, enabled: bool) -> bool:
        """触·启用/禁用Voxta模块"""
        return db.set_module_enabled(module_id, enabled)

    def touch_update_module_config(self, module_id: str,
                                   config_updates: dict) -> bool:
        """触·更新模块配置"""
        return self.hub.update_module_config(module_id, config_updates)

    def touch_chat(self, character_id: str, text: str,
                    scenario_id: str = None) -> dict:
        """触·通过SignalR与角色对话"""
        return signalr.quick_chat(character_id, text, scenario_id)

    def touch_chat_standalone(self, name_or_id: str, text: str,
                              speak: bool = False) -> dict:
        """触·独立模式聊天(直调LLM,脱离Voxta)"""
        engine = self.chat_engine
        if not engine.current_char or engine.current_char.get('name') != name_or_id:
            char = engine.load_character(name_or_id)
            if not char:
                return {'error': f'Character not found: {name_or_id}'}
        return engine.chat(text, speak=speak)

    def touch_update_character(self, char_id: str, field: str, value) -> bool:
        """触·更新角色单字段"""
        return db.update_character_field(char_id, field, value)

    def touch_update_character_multi(self, char_id: str,
                                     updates: dict) -> bool:
        """触·更新角色多字段"""
        return self.hub.update_character(char_id, updates)

    def touch_create_character(self, name: str, profile: str,
                               personality: str, **kwargs) -> str:
        """触·创建新角色"""
        self.hub.backup()
        return self.hub.create_character(name, profile, personality, **kwargs)

    def touch_delete_character(self, char_id: str) -> bool:
        """触·删除角色"""
        self.hub.backup()
        return self.hub.delete_character(char_id)

    def touch_import_tavern_card(self, png_path: str,
                                 culture: str = 'zh-CN') -> dict:
        """触·从TavernCard PNG导入角色"""
        self.hub.backup()
        return self.hub.import_tavern_card(png_path, culture)

    def touch_import_tavern_json(self, json_path: str,
                                 culture: str = 'zh-CN') -> dict:
        """触·从TavernCard JSON导入角色"""
        self.hub.backup()
        return self.hub.import_tavern_json(json_path, culture)

    def touch_clear_history(self) -> bool:
        """触·清空所有对话历史"""
        self.hub.backup()
        return self.hub.clear_chat_history()

    def touch_tts(self, text: str,
                  voice: str = 'zh-CN-XiaoxiaoNeural') -> tuple:
        """触·直接合成语音(EdgeTTS)"""
        from .hub import DirectAPI
        return DirectAPI.edgetts_speak(text, voice)

    def touch_llm(self, message: str, api_key: str = None) -> tuple:
        """触·直接调用LLM(DashScope)"""
        from .hub import DirectAPI
        return DirectAPI.dashscope_chat(message, api_key)

    def touch_auto_fix(self, dry_run: bool = True) -> list:
        """触·运行自动修复"""
        from .hub import AutoFix
        if not dry_run:
            self.hub.backup()
        return AutoFix.run_all(dry_run)

    # ══════════════════════════════════════════════
    # 嗅 · Scent — Voxta配置评估
    # ══════════════════════════════════════════════

    def smell_modules(self) -> dict:
        """嗅·Voxta模块配置评估"""
        enabled = db.get_enabled_by_category()
        missing_critical = []
        if "LLM" not in enabled:
            missing_critical.append("LLM (无大语言模型)")
        if "TTS" not in enabled:
            missing_critical.append("TTS (无语音合成)")
        if "STT" not in enabled:
            missing_critical.append("STT (无语音识别)")

        high_value = []
        for m in db.list_modules():
            if not m["enabled"] and m["service"] in ["ChromaDb", "Florence2", "BuiltIn.ChainOfThought"]:
                high_value.append(f"{m['service']} ({m['label'] or '未配置'})")

        return {
            "enabled_by_category": enabled,
            "missing_critical": missing_critical,
            "high_value_disabled": high_value,
        }

    def smell_diagnose(self) -> list:
        """嗅·全链路诊断(文件/服务/DB/模块/安全/磁盘)"""
        from .hub import Diagnostics
        return Diagnostics.full_scan()

    def smell_diagnose_text(self) -> str:
        """嗅·全链路诊断文本报告"""
        from .hub import Diagnostics
        return Diagnostics.text_report()

    def smell_diagnose_json(self) -> dict:
        """嗅·全链路诊断JSON报告"""
        from .hub import Diagnostics
        return Diagnostics.json_report()

    # ══════════════════════════════════════════════
    # 味 · Taste — Voxta健康评估
    # ══════════════════════════════════════════════

    def taste_health(self) -> dict:
        """味·Voxta健康检查"""
        report = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "paths": {},
            "services": {},
            "signalr": {},
            "modules": {},
        }

        # 文件完整性
        paths = self.see_critical_paths()
        missing = [n for n, p in paths.items() if not p["exists"]]
        report["paths"] = {
            "total": len(paths),
            "ok": len(paths) - len(missing),
            "missing": missing,
        }

        # 服务状态
        status = self.hear_services()
        online = [k for k, v in status.items() if v.get("running")]
        offline = [k for k, v in status.items() if not v.get("running")]
        report["services"] = {"online": online, "offline": offline}

        # SignalR
        report["signalr"] = self.hear_signalr()

        # 模块评估
        report["modules"] = self.smell_modules()

        # 综合评分
        score = 100
        score -= len(missing) * 10
        score -= len(offline) * 5
        if report["signalr"].get("connected"):
            score += 5
        if report["modules"].get("missing_critical"):
            score -= len(report["modules"]["missing_critical"]) * 10
        report["health_score"] = max(0, min(100, score))

        return report

    # ══════════════════════════════════════════════
    # 综合能力
    # ══════════════════════════════════════════════

    def dashboard(self) -> dict:
        """综合仪表板"""
        return {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "services": self.hear_services(),
            "critical_paths": self.see_critical_paths(),
            "stats": db.get_stats(),
            "signalr": self.hear_signalr(),
            "health_score": self.taste_health().get("health_score", 0),
        }

    def quick_report(self) -> str:
        """快速文本报告"""
        health = self.taste_health()
        lines = [
            f"Voxta Agent 健康报告 | {health['timestamp']}",
            f"健康评分: {health['health_score']}/100",
            "",
            "服务状态:",
        ]
        status = self.hear_services()
        for k, v in status.items():
            icon = "ON" if v.get("running") else "OFF"
            lines.append(f"  [{icon}] {v.get('name', k)}")

        sr = health.get("signalr", {})
        if sr.get("connected"):
            lines.append(f"\nSignalR: 已连接 (Voxta {sr.get('version', '?')})")
        else:
            lines.append(f"\nSignalR: 未连接")

        missing = health["paths"].get("missing", [])
        if missing:
            lines.append(f"\n缺失文件: {', '.join(missing)}")

        modules = health.get("modules", {})
        if modules.get("missing_critical"):
            lines.append(f"\n缺失关键模块: {', '.join(modules['missing_critical'])}")

        return "\n".join(lines)
