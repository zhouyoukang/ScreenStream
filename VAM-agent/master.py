"""
MasterAgent — VaM + Voxta 全域统一编排器

顶层开发者思维:
  1. 自动发现(Auto-Discovery) — 零配置感知所有可操作空间
  2. 工作流编排(Workflows) — 一键完成复杂多步操作
  3. 非侵入保证(Non-Invasive) — 所有操作不干扰用户前台
  4. 通道优先级 — Bridge HTTP > DB直控 > 文件系统 > GUI(最后手段)

使用:
    from master import MasterAgent
    m = MasterAgent()
    m.discover()           # 自动发现所有可操作空间
    m.capabilities()       # 列出能力矩阵
    m.workflow_startup()   # 一键全栈启动
    m.workflow_scene()     # 一键场景搭建
    m.workflow_chat()      # 一键开始对话
    m.full_health()        # 全域健康检查
"""
import json
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from vam import VaMAgent
from vam.config import VAM_CONFIG
from vam.bridge import VaMBridgeError
from vam import scenes, resources, plugins, process as vam_process

from voxta import VoxtaAgent
from voxta.config import VOXTA_CONFIG
from voxta import signalr
from voxta.hub import VoxtaDB, Diagnostics, AutoFix
from voxta import db as voxta_db
from voxta import process as voxta_process


# ═══════════════════════════════════════════════════════
# 通道优先级定义
# ═══════════════════════════════════════════════════════

CHANNEL_PRIORITY = {
    "bridge_http":  {"level": 1, "invasive": False, "desc": "AgentBridge HTTP API (:8285)"},
    "signalr_ws":   {"level": 2, "invasive": False, "desc": "Voxta SignalR WebSocket (:5384)"},
    "db_direct":    {"level": 3, "invasive": False, "desc": "Voxta SQLite DB直控"},
    "file_system":  {"level": 4, "invasive": False, "desc": "文件系统读写"},
    "process_mgmt": {"level": 5, "invasive": False, "desc": "进程管理(启停)"},
    "gui_auto":     {"level": 6, "invasive": True,  "desc": "GUI自动化(OCR+点击) — 最后手段"},
}


class MasterAgent:
    """VaM + Voxta 全域统一编排器 — 零配置·非侵入·全自动"""

    def __init__(self, bridge_port: int = 8285, bridge_key: str = None):
        self.vam = VaMAgent(bridge_port=bridge_port, bridge_key=bridge_key)
        self.voxta = VoxtaAgent()
        self._log = logging.getLogger("MasterAgent")
        self._state = {}
        self._discovered = False

    # ═══════════════════════════════════════════════════════
    # 自动发现 (Auto-Discovery) — 零配置感知所有可操作空间
    # ═══════════════════════════════════════════════════════

    def discover(self) -> dict:
        """自动发现所有可操作空间 — 零配置"""
        state = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "channels": {},
            "vam": {},
            "voxta": {},
            "capabilities": {},
        }

        # 通道探测
        state["channels"] = self._discover_channels()

        # VaM 可操作空间
        state["vam"] = self._discover_vam()

        # Voxta 可操作空间
        state["voxta"] = self._discover_voxta()

        # 能力矩阵
        state["capabilities"] = self._build_capability_matrix(state)

        self._state = state
        self._discovered = True
        return state

    def _discover_channels(self) -> dict:
        """探测所有控制通道状态"""
        channels = {}

        # Bridge HTTP
        try:
            alive = self.vam.runtime_alive()
            channels["bridge_http"] = {
                "online": alive, "port": 8285,
                "desc": CHANNEL_PRIORITY["bridge_http"]["desc"],
            }
            if alive:
                status = self.vam.runtime_status()
                channels["bridge_http"]["version"] = status.get("version", "?")
                channels["bridge_http"]["atom_count"] = status.get("atomCount", 0)
        except Exception:
            channels["bridge_http"] = {"online": False, "port": 8285}

        # SignalR
        try:
            sr = self.voxta.hear_signalr()
            channels["signalr_ws"] = {
                "online": sr.get("connected", False), "port": 5384,
                "version": sr.get("version", "?"),
            }
        except Exception:
            channels["signalr_ws"] = {"online": False, "port": 5384}

        # DB
        try:
            stats = voxta_db.get_stats()
            channels["db_direct"] = {
                "online": True, "path": str(VOXTA_CONFIG.VOXTA_DB),
                "tables": stats,
            }
        except Exception:
            channels["db_direct"] = {"online": False}

        # File System
        channels["file_system"] = {
            "online": True,
            "vam_root": str(VAM_CONFIG.VAM_ROOT),
            "vam_root_exists": VAM_CONFIG.VAM_ROOT.exists(),
        }

        # Process Management
        channels["process_mgmt"] = {
            "online": True,
            "vam_services": vam_process.get_all_status(),
            "voxta_services": voxta_process.get_all_status(),
        }

        # GUI (always available but invasive)
        channels["gui_auto"] = {
            "online": True,
            "invasive": True,
            "note": "仅当所有非侵入通道失败时使用",
        }

        return channels

    def _discover_vam(self) -> dict:
        """发现VaM所有可操作空间"""
        vam_state = {
            "paths": self.vam.see_critical_paths(),
            "scenes": [],
            "scripts": [],
            "plugins": {},
            "var_packages": {},
            "runtime": {},
        }

        # 文件系统层
        try:
            vam_state["scenes"] = self.vam.see_scenes()
        except Exception as e:
            vam_state["scenes_error"] = str(e)

        try:
            vam_state["scripts"] = self.vam.see_scripts()
        except Exception as e:
            vam_state["scripts_error"] = str(e)

        try:
            vam_state["plugins"] = self.vam.see_plugins()
        except Exception as e:
            vam_state["plugins_error"] = str(e)

        try:
            vam_state["var_packages"] = self.vam.see_var_packages(0)
        except Exception as e:
            vam_state["var_packages_error"] = str(e)

        # 运行时层 (仅Bridge在线时)
        try:
            if self.vam.runtime_alive():
                vam_state["runtime"]["alive"] = True
                vam_state["runtime"]["status"] = self.vam.runtime_status()
                vam_state["runtime"]["atoms"] = self.vam.runtime_atoms()
                vam_state["runtime"]["scene_info"] = self.vam.runtime_scene_info()
                try:
                    vam_state["runtime"]["atom_types"] = self.vam.runtime_atom_types()
                except Exception:
                    pass
                try:
                    vam_state["runtime"]["prefs"] = self.vam.runtime_get_prefs()
                except Exception:
                    pass

                # 深度发现: 每个Atom的storables
                atoms = vam_state["runtime"].get("atoms", [])
                atom_details = []
                for atom in atoms[:10]:
                    atom_id = atom.get("id") or atom.get("uid", "")
                    if not atom_id:
                        continue
                    detail = {"id": atom_id, "type": atom.get("type", "")}
                    try:
                        detail["storables"] = self.vam.runtime_storables(atom_id)
                        detail["storable_count"] = len(detail["storables"])
                    except Exception:
                        pass
                    try:
                        detail["controllers"] = self.vam.runtime_controllers(atom_id)
                    except Exception:
                        pass
                    atom_details.append(detail)
                vam_state["runtime"]["atom_details"] = atom_details
            else:
                vam_state["runtime"]["alive"] = False
        except Exception as e:
            vam_state["runtime"]["alive"] = False
            vam_state["runtime"]["error"] = str(e)

        return vam_state

    def _discover_voxta(self) -> dict:
        """发现Voxta所有可操作空间"""
        voxta_state = {
            "paths": self.voxta.see_critical_paths(),
            "characters": [],
            "modules": [],
            "scenarios": [],
            "presets": [],
            "memory_books": [],
            "stats": {},
        }

        try:
            voxta_state["characters"] = self.voxta.see_characters()
        except Exception as e:
            voxta_state["characters_error"] = str(e)

        try:
            voxta_state["modules"] = self.voxta.smell_modules()
        except Exception as e:
            voxta_state["modules_error"] = str(e)

        try:
            voxta_state["scenarios"] = self.voxta.see_scenarios()
        except Exception as e:
            voxta_state["scenarios_error"] = str(e)

        try:
            voxta_state["presets"] = self.voxta.see_hub_presets()
        except Exception as e:
            voxta_state["presets_error"] = str(e)

        try:
            voxta_state["memory_books"] = self.voxta.see_hub_memory_books()
        except Exception as e:
            voxta_state["memory_books_error"] = str(e)

        try:
            voxta_state["stats"] = self.voxta.see_stats()
        except Exception as e:
            voxta_state["stats_error"] = str(e)

        try:
            voxta_state["appsettings"] = self.voxta.see_appsettings()
        except Exception as e:
            voxta_state["appsettings_error"] = str(e)

        return voxta_state

    def _build_capability_matrix(self, state: dict) -> dict:
        """构建完整能力矩阵 — 列出所有可操作空间"""
        bridge_alive = (state.get("channels", {})
                        .get("bridge_http", {}).get("online", False))
        signalr_alive = (state.get("channels", {})
                         .get("signalr_ws", {}).get("online", False))
        db_alive = (state.get("channels", {})
                    .get("db_direct", {}).get("online", False))

        matrix = {
            "vam_file_ops": {
                "available": True,
                "channel": "file_system",
                "ops": [
                    "场景CRUD (list/create/read/delete)",
                    "脚本部署 (deploy C# scripts)",
                    "VAR包扫描 (list/search/info)",
                    "外观管理 (appearances)",
                    "服装管理 (clothing)",
                    "发型管理 (hair)",
                    "插件管理 (BepInEx/Custom/PluginData)",
                    "日志监控 (read/search/errors)",
                    "磁盘管理 (usage/warnings)",
                ],
            },
            "vam_runtime_ops": {
                "available": bridge_alive,
                "channel": "bridge_http",
                "ops": [
                    "Atom CRUD (create/read/update/delete)",
                    "Storable参数控制 (float/bool/string/chooser)",
                    "Action调用 (discover & invoke)",
                    "Controller位置/旋转",
                    "Morph操控 (10000+ morphs, filter/batch)",
                    "表情控制 (smile/sad/angry/surprised/wink/neutral)",
                    "手部/头部运动控制",
                    "场景加载/保存/清空/浏览",
                    "动画冻结/解冻",
                    "Timeline控制 (play/stop/scrub/speed)",
                    "截图捕获",
                    "VaM偏好设置 (read/write prefs)",
                    "全局动作 (play/stop/reset/undo/redo)",
                    "批量命令执行",
                    "Voxta插件控制 (send/state/action/new_chat)",
                    "摄像机导航",
                    "运行时插件列表",
                    "运行时日志",
                ],
            },
            "vam_gui_ops": {
                "available": True,
                "channel": "gui_auto",
                "invasive": True,
                "ops": [
                    "OCR文字扫描",
                    "文字点击/坐标点击/相对点击",
                    "键盘按键/快捷键",
                    "文本输入/剪贴板操作",
                    "拖拽/滚轮",
                    "截图",
                    "菜单导航",
                    "场景浏览器操作",
                    "等待/验证界面状态",
                    "MouseGuard用户活跃检测",
                ],
            },
            "voxta_db_ops": {
                "available": db_alive,
                "channel": "db_direct",
                "ops": [
                    "角色CRUD (create/read/update/delete)",
                    "TavernCard导入 (PNG/JSON)",
                    "模块管理 (enable/disable/config)",
                    "记忆书管理 (list)",
                    "预设管理 (list)",
                    "对话历史 (read/clear)",
                    "场景管理 (list)",
                    "数据库统计/备份",
                    "全链路诊断",
                    "自动修复 (重复角色/死链模块/Vosk忽略词)",
                ],
            },
            "voxta_signalr_ops": {
                "available": signalr_alive,
                "channel": "signalr_ws",
                "ops": [
                    "实时对话 (SignalR双向通信)",
                    "开始/结束聊天会话",
                    "发送/接收消息",
                    "动作推理 (action extraction)",
                ],
            },
            "voxta_chat_ops": {
                "available": True,
                "channel": "db_direct + llm_api",
                "ops": [
                    "独立模式聊天 (脱离Voxta, 直调LLM)",
                    "LLM多后端降级 (DashScope/DeepSeek/Local)",
                    "TTS直调 (EdgeTTS)",
                    "Prompt构建 (人格注入)",
                    "动作推理 (emote/action extraction)",
                ],
            },
            "process_ops": {
                "available": True,
                "channel": "process_mgmt",
                "ops": [
                    "VaM启停",
                    "Voxta全栈启停",
                    "EdgeTTS启停",
                    "TextGen启停",
                    "端口探测",
                    "服务状态监控",
                ],
            },
        }

        # 统计
        total_ops = sum(len(v["ops"]) for v in matrix.values())
        available_ops = sum(
            len(v["ops"]) for v in matrix.values() if v["available"]
        )
        non_invasive_ops = sum(
            len(v["ops"]) for v in matrix.values()
            if v["available"] and not v.get("invasive", False)
        )

        matrix["_summary"] = {
            "total_ops": total_ops,
            "available_ops": available_ops,
            "non_invasive_ops": non_invasive_ops,
            "coverage": f"{available_ops}/{total_ops}",
            "non_invasive_rate": (f"{non_invasive_ops}/{available_ops}"
                                  if available_ops else "0/0"),
        }

        return matrix

    def capabilities(self) -> dict:
        """列出完整能力矩阵"""
        if not self._discovered:
            self.discover()
        return self._state.get("capabilities", {})

    # ═══════════════════════════════════════════════════════
    # 工作流编排 (Workflows) — 一键完成复杂多步操作
    # ═══════════════════════════════════════════════════════

    def workflow_startup(self, include_textgen: bool = False) -> dict:
        """一键全栈启动: VaM → Voxta → EdgeTTS → (TextGen)

        通道: process_mgmt (非侵入)
        """
        results = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "steps": [],
        }

        # Step 1: VaM进程
        vam_status = vam_process.get_all_status()
        vam_running = vam_status.get("vam", {}).get("running", False)
        if not vam_running:
            ok, msg = vam_process.start_service("vam")
            results["steps"].append({
                "step": "start_vam", "ok": ok, "msg": msg,
            })
        else:
            results["steps"].append({
                "step": "start_vam", "ok": True, "msg": "Already running",
            })

        # Step 2: Voxta全栈
        voxta_results = self.voxta.touch_start_all(include_textgen=include_textgen)
        results["steps"].append({
            "step": "start_voxta_stack",
            "results": voxta_results,
        })

        # Step 3: 等待Bridge上线
        bridge_ok = False
        for attempt in range(10):
            try:
                if self.vam.runtime_alive():
                    bridge_ok = True
                    break
            except Exception:
                pass
            time.sleep(2)
        results["steps"].append({
            "step": "wait_bridge", "ok": bridge_ok,
            "attempts": attempt + 1,
        })

        # Step 4: 验证全部通道
        results["channels"] = self._discover_channels()
        online = sum(1 for c in results["channels"].values()
                     if c.get("online", False))
        results["summary"] = {
            "channels_online": f"{online}/{len(results['channels'])}",
            "ready": bridge_ok,
        }

        return results

    def workflow_scene(self, scene_name: str = None,
                       character_name: str = None,
                       load_existing: str = None) -> dict:
        """一键场景搭建

        通道: bridge_http (非侵入) + file_system
        优先级: 加载已有场景 > 创建新场景
        """
        results = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "steps": [],
        }

        # 确保Bridge在线
        if not self.vam.runtime_alive():
            results["error"] = "Bridge offline — 请先运行 workflow_startup()"
            return results

        # Step 1: 加载或创建场景
        if load_existing:
            try:
                r = self.vam.runtime_load_scene(load_existing)
                results["steps"].append({
                    "step": "load_scene", "ok": True, "path": load_existing,
                })
            except VaMBridgeError as e:
                results["steps"].append({
                    "step": "load_scene", "ok": False, "error": str(e),
                })
                return results
        else:
            path = self.vam.touch_create_scene(name=scene_name)
            results["steps"].append({
                "step": "create_scene", "ok": True, "path": path,
            })
            try:
                self.vam.runtime_load_scene(path)
                results["steps"].append({
                    "step": "load_created_scene", "ok": True,
                })
            except VaMBridgeError as e:
                results["steps"].append({
                    "step": "load_created_scene", "ok": False, "error": str(e),
                })

        # Step 2: 如果指定角色, 查找Voxta角色ID
        if character_name:
            chars = self.voxta.see_characters()
            char_match = None
            for c in chars:
                if (c.get("name", "").lower() == character_name.lower() or
                        character_name.lower() in c.get("name", "").lower()):
                    char_match = c
                    break

            if char_match:
                results["steps"].append({
                    "step": "find_character", "ok": True,
                    "character": char_match.get("name"),
                    "id": char_match.get("id"),
                })
            else:
                results["steps"].append({
                    "step": "find_character", "ok": False,
                    "error": f"Character not found: {character_name}",
                    "available": [c.get("name") for c in chars],
                })

        # Step 3: 获取场景信息
        try:
            scene_info = self.vam.runtime_scene_info()
            results["scene_info"] = scene_info
        except Exception:
            pass

        # Step 4: 获取当前Atoms
        try:
            atoms = self.vam.runtime_atoms()
            results["atoms"] = atoms
        except Exception:
            pass

        return results

    def workflow_chat(self, character_name: str = None,
                      message: str = None,
                      mode: str = "standalone") -> dict:
        """一键开始对话

        通道: db_direct + llm_api (非侵入)
        mode: 'standalone' (直调LLM) 或 'voxta' (SignalR)
        """
        results = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "steps": [],
        }

        # Step 1: 查找角色
        if not character_name:
            chars = self.voxta.see_characters()
            if chars:
                character_name = chars[0].get("name", "")
                results["steps"].append({
                    "step": "auto_select_character", "name": character_name,
                })
            else:
                results["error"] = "No characters found in Voxta DB"
                return results

        # Step 2: 加载角色并发送消息
        if mode == "standalone":
            if message:
                reply = self.voxta.touch_chat_standalone(character_name, message)
                results["steps"].append({
                    "step": "chat_standalone", "ok": "error" not in reply,
                    "reply": reply,
                })
            else:
                results["steps"].append({
                    "step": "chat_ready", "mode": "standalone",
                    "character": character_name,
                    "usage": "m.voxta.touch_chat_standalone('角色名', '消息')",
                })
        elif mode == "voxta":
            chars = self.voxta.see_characters()
            char_id = None
            for c in chars:
                if c.get("name", "").lower() == character_name.lower():
                    char_id = c.get("id")
                    break

            if not char_id:
                results["error"] = f"Character not found: {character_name}"
                return results

            if message:
                reply = self.voxta.touch_chat(char_id, message)
                results["steps"].append({
                    "step": "chat_voxta", "ok": "error" not in reply,
                    "reply": reply,
                })
            else:
                results["steps"].append({
                    "step": "chat_ready", "mode": "voxta",
                    "character": character_name,
                    "character_id": char_id,
                    "usage": f"m.voxta.touch_chat('{char_id}', '消息')",
                })

        return results

    def workflow_demo(self, character_name: str = None) -> dict:
        """完整演示流程: 发现 → 启动 → 场景 → 对话

        通道: 全通道 (优先非侵入)
        """
        results = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "phases": [],
        }

        # Phase 1: 发现
        state = self.discover()
        results["phases"].append({
            "phase": "discover",
            "channels_found": len(state.get("channels", {})),
            "scenes": len(state.get("vam", {}).get("scenes", [])),
            "characters": len(state.get("voxta", {}).get("characters", [])),
        })

        # Phase 2: 确保服务在线
        bridge_alive = (state.get("channels", {})
                        .get("bridge_http", {}).get("online", False))
        if not bridge_alive:
            startup = self.workflow_startup()
            results["phases"].append({
                "phase": "startup",
                "result": startup.get("summary", {}),
            })

        # Phase 3: 自动选择角色
        if not character_name:
            chars = state.get("voxta", {}).get("characters", [])
            if chars:
                character_name = chars[0].get("name", "Unknown")

        results["phases"].append({
            "phase": "character_selected",
            "name": character_name,
        })

        # Phase 4: 场景 (如果Bridge在线)
        if self.vam.runtime_alive():
            scene_result = self.workflow_scene(character_name=character_name)
            results["phases"].append({
                "phase": "scene",
                "steps": len(scene_result.get("steps", [])),
            })

        # Phase 5: 对话就绪
        chat_result = self.workflow_chat(
            character_name=character_name, mode="standalone"
        )
        results["phases"].append({
            "phase": "chat_ready",
            "result": chat_result,
        })

        results["ready"] = True
        results["character"] = character_name
        return results

    # ═══════════════════════════════════════════════════════
    # 非侵入操作层 (Non-Invasive Layer)
    # ═══════════════════════════════════════════════════════

    def safe_execute(self, operation: str, **kwargs) -> dict:
        """非侵入式执行 — 按通道优先级自动选择最佳通道

        通道优先级: Bridge HTTP > DB > File System > GUI
        只有在所有非侵入通道都失败时才降级到GUI
        """
        OPERATIONS = {
            "list_atoms": self._safe_list_atoms,
            "load_scene": self._safe_load_scene,
            "get_character": self._safe_get_character,
            "create_character": self._safe_create_character,
            "set_module": self._safe_set_module,
            "health_check": self._safe_health_check,
        }

        handler = OPERATIONS.get(operation)
        if not handler:
            return {
                "error": f"Unknown operation: {operation}",
                "available": list(OPERATIONS.keys()),
            }

        return handler(**kwargs)

    def _safe_list_atoms(self, **kwargs) -> dict:
        """安全列出Atoms — Bridge > 场景文件解析"""
        try:
            return {"channel": "bridge_http", "data": self.vam.runtime_atoms()}
        except Exception:
            pass
        try:
            scenes_list = self.vam.see_scenes()
            return {"channel": "file_system", "data": scenes_list,
                    "note": "Bridge offline, showing scene files instead"}
        except Exception as e:
            return {"channel": "none", "error": str(e)}

    def _safe_load_scene(self, path: str = "", **kwargs) -> dict:
        """安全加载场景 — Bridge > GUI"""
        try:
            return {"channel": "bridge_http",
                    "data": self.vam.runtime_load_scene(path)}
        except Exception:
            pass
        return {"channel": "none",
                "error": "Bridge offline. Use workflow_startup() first."}

    def _safe_get_character(self, name_or_id: str = "", **kwargs) -> dict:
        """安全获取角色 — DB直控"""
        try:
            detail = self.voxta.see_character_detail(name_or_id)
            if detail:
                return {"channel": "db_direct", "data": detail}
            chars = self.voxta.see_characters()
            for c in chars:
                if name_or_id.lower() in c.get("name", "").lower():
                    return {"channel": "db_direct", "data": c}
            return {"channel": "db_direct", "error": "Not found",
                    "available": [c.get("name") for c in chars]}
        except Exception as e:
            return {"channel": "none", "error": str(e)}

    def _safe_create_character(self, name: str = "", profile: str = "",
                               personality: str = "", **kwargs) -> dict:
        """安全创建角色 — DB直控"""
        try:
            char_id = self.voxta.touch_create_character(
                name, profile, personality, **kwargs
            )
            return {"channel": "db_direct", "data": {"id": char_id, "name": name}}
        except Exception as e:
            return {"channel": "none", "error": str(e)}

    def _safe_set_module(self, module_id: str = "",
                         enabled: bool = True, **kwargs) -> dict:
        """安全设置模块 — DB直控"""
        try:
            ok = self.voxta.touch_set_module(module_id, enabled)
            return {"channel": "db_direct",
                    "data": {"module_id": module_id, "enabled": enabled, "ok": ok}}
        except Exception as e:
            return {"channel": "none", "error": str(e)}

    def _safe_health_check(self, **kwargs) -> dict:
        """安全健康检查 — 全通道"""
        return self.full_health()

    # ═══════════════════════════════════════════════════════
    # 全域健康 (Full Health)
    # ═══════════════════════════════════════════════════════

    def full_health(self) -> dict:
        """全域健康检查 — VaM + Voxta 统一评估"""
        report = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "vam_health": {},
            "voxta_health": {},
            "channels": {},
            "issues": [],
            "auto_fix_available": [],
        }

        # VaM健康
        try:
            report["vam_health"] = self.vam.taste_health()
        except Exception as e:
            report["vam_health"] = {"error": str(e)}

        # Voxta健康
        try:
            report["voxta_health"] = self.voxta.taste_health()
        except Exception as e:
            report["voxta_health"] = {"error": str(e)}

        # 通道状态
        report["channels"] = self._discover_channels()

        # Voxta诊断
        try:
            issues = Diagnostics.full_scan()
            report["issues"] = [
                {"level": l, "component": c, "msg": m}
                for l, c, m in issues
            ]
        except Exception as e:
            report["issues_error"] = str(e)

        # 自动修复预览
        try:
            fixes = AutoFix.run_all(dry_run=True)
            report["auto_fix_available"] = fixes
        except Exception as e:
            report["auto_fix_error"] = str(e)

        # 综合评分
        vam_score = report.get("vam_health", {}).get("health_score", 0)
        voxta_score = report.get("voxta_health", {}).get("health_score", 0)
        channel_count = sum(
            1 for c in report["channels"].values() if c.get("online", False)
        )
        issue_count = len(report.get("issues", []))

        # 加权评分: VaM 30% + Voxta 30% + 通道 20% + 问题 20%
        channel_score = min(100, channel_count * 20)
        issue_penalty = min(50, issue_count * 5)
        total = int(vam_score * 0.3 + voxta_score * 0.3 +
                    channel_score * 0.2 + max(0, 100 - issue_penalty) * 0.2)
        report["total_health_score"] = max(0, min(100, total))

        return report

    def auto_fix(self, dry_run: bool = True) -> dict:
        """全域自动修复"""
        results = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "fixes": [],
        }

        if not dry_run:
            self.voxta.touch_backup()

        try:
            fixes = AutoFix.run_all(dry_run=dry_run)
            results["fixes"] = fixes
        except Exception as e:
            results["error"] = str(e)

        results["dry_run"] = dry_run
        return results

    # ═══════════════════════════════════════════════════════
    # 便捷方法
    # ═══════════════════════════════════════════════════════

    def status(self) -> dict:
        """快速状态概览"""
        bridge = False
        try:
            bridge = self.vam.runtime_alive()
        except Exception:
            pass

        signalr_ok = False
        try:
            sr = self.voxta.hear_signalr()
            signalr_ok = sr.get("connected", False)
        except Exception:
            pass

        db_ok = False
        try:
            voxta_db.get_stats()
            db_ok = True
        except Exception:
            pass

        vam_svc = vam_process.get_all_status()
        voxta_svc = voxta_process.get_all_status()

        return {
            "bridge": bridge,
            "signalr": signalr_ok,
            "database": db_ok,
            "vam_process": vam_svc.get("vam", {}).get("running", False),
            "voxta_process": voxta_svc.get("voxta", {}).get("running", False),
            "edgetts": voxta_svc.get("edgetts", {}).get("running", False),
        }

    def quick_report(self) -> str:
        """快速文本报告"""
        st = self.status()
        lines = [
            f"MasterAgent 状态报告 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "通道状态:",
            f"  Bridge HTTP :8285  {'ON' if st['bridge'] else 'OFF'}",
            f"  SignalR WS  :5384  {'ON' if st['signalr'] else 'OFF'}",
            f"  SQLite DB          {'ON' if st['database'] else 'OFF'}",
            "",
            "服务状态:",
            f"  VaM进程             {'ON' if st['vam_process'] else 'OFF'}",
            f"  Voxta引擎           {'ON' if st['voxta_process'] else 'OFF'}",
            f"  EdgeTTS             {'ON' if st['edgetts'] else 'OFF'}",
        ]

        # 角色计数
        try:
            chars = self.voxta.see_characters()
            lines.append(f"\n角色: {len(chars)}个")
            for c in chars[:5]:
                lines.append(f"  - {c.get('name', '?')}")
        except Exception:
            pass

        # 场景计数
        try:
            scene_list = self.vam.see_scenes()
            lines.append(f"\n场景: {len(scene_list)}个")
        except Exception:
            pass

        return "\n".join(lines)

    def __repr__(self):
        st = self.status()
        online = sum(1 for v in st.values() if v)
        return f"MasterAgent({online}/{len(st)} online)"
