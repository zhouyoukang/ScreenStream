"""
VaM 统一Agent — VaM 3D引擎六感控制中枢

六感架构(VaM视角):
  视(Vision)  — 场景/脚本/插件/资源/日志状态感知
  听(Audio)   — VaM进程状态/端口探测
  触(Touch)   — 进程启停/场景创建/脚本部署/文件写入
  嗅(Scent)   — 风险预判/错误检测/磁盘预警
  味(Taste)   — 资源扫描/健康检查
  手(Hand)    — VaM GUI直接操控(OCR+坐标点击+快捷键,模拟用户操作VaM软件本身)

Voxta相关功能已迁移至 voxta/agent.py (VoxtaAgent)。
"""
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict

from .config import VAM_CONFIG
from . import process, scenes, resources, plugins, logs, gui
from .bridge import VaMBridge, VaMBridgeError
from . import characters, animations, environments, plugin_gen, packaging, pipeline
from . import discovery


class VaMAgent:
    """VaM 3D引擎六感 Agent + 运行时直控"""

    def __init__(self, bridge_port: int = 8285, bridge_key: str = None):
        self.config = VAM_CONFIG
        self._bridge = VaMBridge(port=bridge_port, auth_key=bridge_key)
        self._log = logging.getLogger("VaMAgent")

    # ══════════════════════════════════════════════
    # 视 · Vision — 状态感知
    # ══════════════════════════════════════════════

    def see_critical_paths(self) -> dict:
        """视·文件完整性"""
        return self.config.get_all_critical_paths()

    def see_scenes(self, directory: str = None) -> list:
        """视·场景列表"""
        return scenes.list_scenes(directory)

    def see_scene_detail(self, path: str) -> dict:
        """视·场景详情"""
        return scenes.get_scene_info(path)

    def see_scripts(self) -> list:
        """视·脚本列表"""
        return resources.list_scripts()

    def see_var_packages(self, top_n: int = 20) -> dict:
        """视·VAR包概览"""
        return resources.list_var_packages(top_n)

    def see_var_detail(self, var_path: str) -> dict:
        """视·VAR包深度分析(元数据/依赖/文件类型/校验和)"""
        return resources.get_var_detail(var_path)

    def see_var_dependencies(self, var_path: str, recursive: bool = False) -> dict:
        """视·VAR包依赖分析"""
        if recursive:
            return resources.resolve_dependencies(var_path)
        return {"dependencies": resources.get_var_dependencies(var_path)}

    def see_scene_references(self, scene_path: str) -> dict:
        """视·场景资源引用扫描"""
        return resources.scan_scene_references(scene_path)

    def see_plugins(self) -> dict:
        """视·插件概览"""
        return plugins.plugin_dashboard()

    def see_log(self, tail: int = 100) -> list:
        """视·VaM日志"""
        return logs.read_log(tail)

    # ══════════════════════════════════════════════
    # 听 · Audio — VaM进程状态监控
    # ══════════════════════════════════════════════

    def hear_services(self) -> dict:
        """听·VaM服务状态"""
        return process.get_all_status()

    def hear_port(self, port: int) -> bool:
        """听·端口探测"""
        return process.check_port(port)

    def hear_service(self, key: str) -> dict:
        """听·单个服务状态"""
        status = process.get_all_status()
        return status.get(key, {"error": f"Unknown service: {key}"})

    # ══════════════════════════════════════════════
    # 触 · Touch — 主动操作
    # ══════════════════════════════════════════════

    def touch_start_service(self, key: str) -> tuple:
        """触·启动VaM服务"""
        return process.start_service(key)

    def touch_stop(self, process_name: str) -> tuple:
        """触·停止进程"""
        return process.stop_process(process_name)

    def touch_create_scene(self, name: str = None) -> str:
        """触·创建基础场景"""
        scene = scenes.SceneBuilder()
        scene.add_camera(position=(0, 1.5, 3.0), fov=50)
        scene.add_three_point_lighting()
        path = scene.save(name=name)
        return path

    def touch_deploy_script(self, name: str, code: str,
                              subdir: str = "Agent") -> str:
        """触·部署C#脚本到VaM"""
        return plugins.deploy_script(name, code, subdir)

    def touch_delete_scene(self, path: str) -> bool:
        """触·删除场景"""
        return scenes.delete_scene(path)

    # ══════════════════════════════════════════════
    # 嗅 · Scent — 风险预判与错误检测
    # ══════════════════════════════════════════════

    def smell_errors(self, tail: int = 500) -> list:
        """嗅·日志错误检测"""
        return logs.detect_errors(tail)

    def smell_error_summary(self, tail: int = 1000) -> dict:
        """嗅·错误摘要"""
        return logs.error_summary(tail)

    def smell_disk(self) -> dict:
        """嗅·磁盘空间预警"""
        usage = resources.disk_usage()
        warnings = {}
        for drive, info in usage.items():
            if info.get("used_pct", 0) > 85:
                warnings[drive] = f"磁盘空间紧张: {info['used_pct']}% ({info['free_gb']}GB剩余)"
        return {"usage": usage, "warnings": warnings}

    def smell_bepinex(self) -> dict:
        """嗅·BepInEx配置检查"""
        return plugins.check_bepinex_config()

    def smell_log_search(self, keyword: str) -> list:
        """嗅·日志关键词搜索"""
        return logs.search_log(keyword)

    # ══════════════════════════════════════════════
    # 味 · Taste — 全局质量评估
    # ══════════════════════════════════════════════

    def taste_health(self) -> dict:
        """味·VaM健康检查"""
        report = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "vision": {},
            "audio": {},
            "scent": {},
        }

        # 视·文件完整性
        paths = self.see_critical_paths()
        missing = [n for n, p in paths.items() if not p["exists"]]
        report["vision"]["critical_paths"] = {
            "total": len(paths),
            "ok": len(paths) - len(missing),
            "missing": missing,
        }

        # 听·服务状态
        status = self.hear_services()
        online = [k for k, v in status.items() if v.get("running")]
        offline = [k for k, v in status.items() if not v.get("running")]
        report["audio"]["services"] = {
            "online": online,
            "offline": offline,
        }

        # 嗅·错误检测
        error_sum = self.smell_error_summary(500)
        report["scent"]["errors"] = {
            "total": error_sum["total"],
            "by_level": error_sum.get("by_level", {}),
        }

        # 嗅·磁盘
        disk = self.smell_disk()
        report["scent"]["disk_warnings"] = disk.get("warnings", {})

        # 运行时·Bridge状态
        try:
            bridge_alive = self._bridge.is_alive()
        except Exception:
            bridge_alive = False
        report["runtime"] = {"bridge_alive": bridge_alive}

        # 综合评分
        score = 100
        score -= len(missing) * 10
        score -= len(offline) * 5
        score -= min(error_sum["total"], 10) * 2
        score -= len(disk.get("warnings", {})) * 5
        if not bridge_alive:
            score -= 5
        report["health_score"] = max(0, min(100, score))

        return report

    def taste_full_scan(self) -> dict:
        """味·完整资源扫描"""
        return resources.full_scan()

    def taste_var_health(self, top_n: int = 10) -> dict:
        """味·VAR包健康报告(命名/meta/损坏/依赖统计)"""
        return resources.var_health_report(top_n)

    def taste_scene_integrity(self, scene_path: str) -> dict:
        """味·场景完整性检查(引用验证)"""
        return resources.check_scene_integrity(scene_path)

    def taste_dependency_graph(self) -> dict:
        """味·构建并分析VAR包依赖图(孤儿/关键包/重复/缺失)"""
        graph = resources.VarDependencyGraph()
        graph.build()
        summary = graph.summary()
        summary["critical"] = graph.get_critical(min_dependents=3)[:10]
        summary["duplicates"] = graph.get_duplicates()[:10]
        summary["missing"] = graph.get_missing()[:20]
        return summary

    def see_var_deep_scan(self, var_path: str) -> dict:
        """视·VAR包深度扫描(元数据+内容分类+依赖+CRC32)"""
        return resources.var_deep_scan(var_path)

    def see_var_dependents(self, var_name: str) -> dict:
        """视·查看谁依赖此VAR包(反向依赖)"""
        graph = resources.VarDependencyGraph()
        graph.build()
        dependents = graph.get_dependents(var_name)
        return {"package": var_name, "dependent_count": len(dependents),
                "dependents": dependents}

    # ══════════════════════════════════════════════
    # 手 · Hand — VaM GUI直接操控（模拟用户操作VaM软件本身）
    # ══════════════════════════════════════════════

    def hand_state(self) -> dict:
        """手·获取VaM GUI当前状态（窗口/界面文字/页面检测）"""
        return gui.get_vam_state()

    def hand_scan(self, full_screen: bool = False) -> dict:
        """手·OCR扫描VaM界面所有可见文字及坐标"""
        return gui.scan(full_screen=full_screen)

    def hand_find(self, text: str, exact: bool = False) -> dict:
        """手·在VaM界面中查找指定文字"""
        return gui.find_text(text, exact=exact)

    def hand_click_text(self, text: str, button: str = "left",
                        index: int = 0) -> dict:
        """手·点击VaM界面中的指定文字"""
        return gui.click_text(text, button=button, index=index)

    def hand_click_at(self, x: int, y: int, button: str = "left") -> dict:
        """手·点击VaM窗口中的指定坐标"""
        return gui.click_at(x, y, button=button)

    def hand_click_relative(self, rx: float, ry: float,
                            button: str = "left") -> dict:
        """手·点击VaM窗口的相对位置(0.0~1.0)"""
        return gui.click_relative(rx, ry, button=button)

    def hand_key(self, key: str) -> dict:
        """手·在VaM中按键（如'f9', 'ctrl+s'）"""
        return gui.press_key(key)

    def hand_hotkey(self, action: str) -> dict:
        """手·执行VaM快捷键操作（如'save', 'toggle_ui', 'screenshot'）"""
        return gui.vam_hotkey(action)

    def hand_type(self, text: str) -> dict:
        """手·在VaM中输入文本"""
        return gui.type_text(text)

    def hand_drag(self, x1: int, y1: int, x2: int, y2: int,
                  duration: float = 0.5) -> dict:
        """手·在VaM中拖拽（滑块/3D旋转）"""
        return gui.drag(x1, y1, x2, y2, duration=duration)

    def hand_scroll(self, clicks: int = 3, x: int = None,
                    y: int = None) -> dict:
        """手·在VaM中滚轮（列表/缩放）"""
        return gui.scroll(clicks, x=x, y=y)

    def hand_screenshot(self, path: str = None) -> str:
        """手·截取VaM窗口图片"""
        return gui.save_screenshot(path)

    def hand_navigate(self, target: str) -> dict:
        """手·导航VaM主菜单(hub/scene_browser/create/teaser/creator)"""
        return gui.navigate_main_menu(target)

    def hand_wait_for(self, text: str, timeout: float = 30.0) -> dict:
        """手·等待VaM界面出现指定文字"""
        return gui.wait_for_text(text, timeout=timeout)

    def hand_verify(self, expected_texts: list) -> dict:
        """手·验证VaM界面是否包含预期文字"""
        return gui.verify_screen(expected_texts)

    def hand_open_scene(self, scene_name: str = None) -> dict:
        """手·打开场景浏览器并搜索场景"""
        return gui.open_scene(scene_name)

    def hand_create_scene(self) -> dict:
        """手·通过GUI创建新场景"""
        return gui.create_new_scene()

    def hand_save_scene(self) -> dict:
        """手·保存当前场景"""
        return gui.save_current_scene()

    def hand_toggle_ui(self) -> dict:
        """手·显示/隐藏VaM UI"""
        return gui.toggle_ui()

    def hand_paste(self, text: str) -> dict:
        """手·通过剪贴板粘贴文本到VaM（支持中文/Unicode）"""
        return gui.paste_text(text)

    def hand_clipboard_get(self) -> dict:
        """手·读取剪贴板内容"""
        return gui.get_clipboard()

    def hand_clipboard_set(self, text: str) -> dict:
        """手·设置剪贴板内容"""
        return gui.set_clipboard(text)

    def hand_guard_status(self) -> dict:
        """手·获取MouseGuard状态（用户活跃检测）"""
        return gui.get_guard().status()

    def hand_guard_pause(self):
        """手·暂停MouseGuard（允许所有自动化操作）"""
        gui.get_guard().pause()

    def hand_guard_resume(self):
        """手·恢复MouseGuard保护"""
        gui.get_guard().resume()

    # ══════════════════════════════════════════════
    # 运行时 · Runtime — BepInEx HTTP Bridge 直控
    # ══════════════════════════════════════════════

    @property
    def bridge(self) -> VaMBridge:
        """直接访问 VaMBridge 实例（高级用法）"""
        return self._bridge

    def runtime_alive(self) -> bool:
        """运行时·Bridge是否可达"""
        return self._bridge.is_alive()

    def runtime_status(self) -> dict:
        """运行时·VaM完整运行时状态"""
        return self._bridge.status()

    def runtime_atoms(self) -> List[dict]:
        """运行时·列出所有Atom"""
        return self._bridge.list_atoms()

    def runtime_get_atom(self, atom_id: str) -> dict:
        """运行时·获取Atom详情"""
        return self._bridge.get_atom(atom_id)

    def runtime_create_atom(self, atom_type: str, atom_id: str = None) -> dict:
        """运行时·创建Atom"""
        return self._bridge.create_atom(atom_type, atom_id)

    def runtime_remove_atom(self, atom_id: str) -> dict:
        """运行时·删除Atom"""
        return self._bridge.remove_atom(atom_id)

    def runtime_set_float(self, atom: str, storable: str,
                          name: str, value: float) -> dict:
        """运行时·设置Float参数"""
        return self._bridge.set_float(atom, storable, name, value)

    def runtime_set_bool(self, atom: str, storable: str,
                         name: str, value: bool) -> dict:
        """运行时·设置Bool参数"""
        return self._bridge.set_bool(atom, storable, name, value)

    def runtime_set_string(self, atom: str, storable: str,
                           name: str, value: str) -> dict:
        """运行时·设置String参数"""
        return self._bridge.set_string(atom, storable, name, value)

    def runtime_set_chooser(self, atom: str, storable: str,
                            name: str, value: str) -> dict:
        """运行时·设置StringChooser参数"""
        return self._bridge.set_chooser(atom, storable, name, value)

    def runtime_call_action(self, atom: str, storable: str,
                            action: str) -> dict:
        """运行时·调用Action"""
        return self._bridge.call_action(atom, storable, action)

    def runtime_set_morph(self, atom: str, name: str,
                          value: float) -> dict:
        """运行时·设置Morph值"""
        return self._bridge.set_morph(atom, name, value)

    def runtime_list_morphs(self, atom: str, filter: str = None,
                            modified_only: bool = False) -> List[dict]:
        """运行时·列出Morph（支持过滤）"""
        return self._bridge.list_morphs(atom, filter=filter,
                                        modified_only=modified_only)

    def runtime_set_controller(self, atom: str, controller: str,
                               position: tuple = None,
                               rotation: tuple = None) -> dict:
        """运行时·设置控制器位置/旋转"""
        return self._bridge.set_controller(atom, controller,
                                           position=position,
                                           rotation=rotation)

    def runtime_load_scene(self, path: str) -> dict:
        """运行时·加载场景"""
        return self._bridge.load_scene(path)

    def runtime_save_scene(self, path: str) -> dict:
        """运行时·保存场景"""
        return self._bridge.save_scene(path)

    def runtime_voxta_send(self, atom: str, message: str) -> dict:
        """运行时·Voxta发送消息"""
        return self._bridge.voxta_send_message(atom, message)

    def runtime_voxta_state(self, atom: str) -> dict:
        """运行时·Voxta获取状态"""
        return self._bridge.voxta_state(atom)

    def runtime_voxta_new_chat(self, atom: str) -> dict:
        """运行时·Voxta新建对话"""
        return self._bridge.voxta_new_chat(atom)

    def runtime_timeline_play(self, atom: str,
                              animation: str = None) -> dict:
        """运行时·Timeline播放"""
        return self._bridge.timeline_play(atom, animation=animation)

    def runtime_timeline_stop(self, atom: str) -> dict:
        """运行时·Timeline停止"""
        return self._bridge.timeline_stop(atom)

    def runtime_batch(self, commands: List[dict]) -> dict:
        """运行时·批量命令执行"""
        return self._bridge.batch(commands)

    def runtime_global_action(self, action: str) -> dict:
        """运行时·全局动作(play/stop/reset/undo/redo)"""
        return self._bridge.global_action(action)

    def runtime_log(self) -> List[dict]:
        """运行时·获取VaM运行时日志"""
        return self._bridge.get_log()

    # ── 运行时·Discovery (自动发现可操作空间) ──

    def runtime_atom_types(self) -> List[str]:
        """运行时·列出所有可创建的Atom类型"""
        return self._bridge.list_atom_types()

    def runtime_storables(self, atom_id: str) -> List[str]:
        """运行时·列出Atom上的所有Storable ID"""
        return self._bridge.list_storables(atom_id)

    def runtime_params(self, atom_id: str, storable_id: str) -> dict:
        """运行时·获取Storable的所有参数(float/bool/string)"""
        return self._bridge.get_params(atom_id, storable_id)

    def runtime_choosers(self, atom_id: str, storable_id: str) -> List[dict]:
        """运行时·获取Storable的所有StringChooser及选项"""
        return self._bridge.get_choosers(atom_id, storable_id)

    def runtime_actions(self, atom_id: str, storable_id: str) -> List[str]:
        """运行时·列出Storable的所有可用Action"""
        return self._bridge.get_actions(atom_id, storable_id)

    def runtime_controllers(self, atom_id: str) -> List[dict]:
        """运行时·列出Atom的所有Controller及位置"""
        return self._bridge.get_controllers(atom_id)

    # ── 运行时·Scene (场景高级控制) ──

    def runtime_clear_scene(self) -> dict:
        """运行时·清空当前场景所有Atom"""
        return self._bridge.clear_scene()

    def runtime_scene_info(self) -> dict:
        """运行时·获取当前场景信息"""
        return self._bridge.scene_info()

    def runtime_browse_scenes(self) -> List[dict]:
        """运行时·浏览可用场景文件"""
        return self._bridge.list_scenes()

    # ── 运行时·Control (全局控制) ──

    def runtime_freeze(self, enabled: bool = True) -> dict:
        """运行时·冻结/解冻动画"""
        return self._bridge.freeze(enabled)

    def runtime_navigate(self, atom_id: str) -> dict:
        """运行时·导航摄像机到指定Atom"""
        return self._bridge.navigate_to(atom_id)

    def runtime_screenshot(self, path: str = None) -> dict:
        """运行时·截图"""
        return self._bridge.screenshot(path)

    def runtime_plugins(self, atom_id: str) -> List[dict]:
        """运行时·列出Atom上的插件"""
        return self._bridge.list_plugins(atom_id)

    def runtime_undo(self) -> dict:
        """运行时·撤销"""
        return self._bridge.undo()

    def runtime_redo(self) -> dict:
        """运行时·重做"""
        return self._bridge.redo()

    # ── 运行时·Preferences (VaM偏好设置) ──

    def runtime_get_prefs(self) -> dict:
        """运行时·读取VaM偏好设置"""
        return self._bridge.get_prefs()

    def runtime_set_prefs(self, **kwargs) -> dict:
        """运行时·修改VaM偏好设置"""
        return self._bridge.set_prefs(**kwargs)

    # ── 运行时·Character (角色高级控制) ──

    def runtime_expression(self, atom_id: str, expression: str,
                           intensity: float = 1.0) -> List[dict]:
        """运行时·设置表情(smile/sad/angry/surprised/wink/neutral)"""
        return self._bridge.set_expression(atom_id, expression, intensity)

    def runtime_move_hand(self, atom_id: str, hand: str = "right",
                          position: tuple = None,
                          rotation: tuple = None) -> dict:
        """运行时·移动角色手部"""
        return self._bridge.move_hand(atom_id, hand, position, rotation)

    def runtime_move_head(self, atom_id: str,
                          position: tuple = None,
                          rotation: tuple = None) -> dict:
        """运行时·移动角色头部"""
        return self._bridge.move_head(atom_id, position, rotation)

    def runtime_set_morphs(self, atom_id: str,
                           morphs: Dict[str, float]) -> List[dict]:
        """运行时·批量设置Morph值"""
        return self._bridge.set_morphs(atom_id, morphs)

    # ── 运行时·Voxta Plugin (VaM内Voxta插件控制) ──

    def runtime_voxta_reply(self, atom_id: str) -> str:
        """运行时·获取Voxta最后回复"""
        return self._bridge.voxta_get_reply(atom_id)

    def runtime_voxta_action(self, atom_id: str, action: str) -> dict:
        """运行时·执行Voxta插件动作(startNewChat/deleteCurrentChat/etc)"""
        return self._bridge.voxta_action(atom_id, action)

    # ── 运行时·Timeline (动画高级控制) ──

    def runtime_timeline_scrub(self, atom_id: str, time: float) -> dict:
        """运行时·Timeline跳转到指定时间"""
        return self._bridge.timeline_scrub(atom_id, time)

    def runtime_timeline_speed(self, atom_id: str, speed: float) -> dict:
        """运行时·Timeline设置播放速度"""
        return self._bridge.timeline_speed(atom_id, speed)

    # ── 运行时·Diagnostics ──

    def runtime_health_report(self) -> dict:
        """运行时·Bridge综合健康报告"""
        return self._bridge.health_report()

    # ══════════════════════════════════════════════
    # 综合能力
    # ══════════════════════════════════════════════

    def dashboard(self) -> dict:
        """VaM综合仪表盘"""
        return {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "services": self.hear_services(),
            "critical_paths": self.see_critical_paths(),
            "scene_count": len(self.see_scenes()),
            "var_count": self.see_var_packages(0).get("count", 0),
            "health_score": self.taste_health().get("health_score", 0),
        }

    def quick_report(self) -> str:
        """快速文本报告"""
        health = self.taste_health()
        lines = [
            f"VaM Agent 健康报告 | {health['timestamp']}",
            f"健康评分: {health['health_score']}/100",
            "",
            "服务状态:",
        ]
        status = self.hear_services()
        for k, v in status.items():
            icon = "ON" if v.get("running") else "OFF"
            lines.append(f"  [{icon}] {v.get('name', k)}")

        missing = health["vision"]["critical_paths"].get("missing", [])
        if missing:
            lines.append(f"\n缺失文件: {', '.join(missing)}")

        errors = health["scent"]["errors"]
        if errors["total"] > 0:
            lines.append(f"\n日志错误: {errors['total']}个")
            for level, count in errors.get("by_level", {}).items():
                lines.append(f"  {level}: {count}")

        warnings = health["scent"].get("disk_warnings", {})
        if warnings:
            lines.append("\n磁盘警告:")
            for drive, msg in warnings.items():
                lines.append(f"  {drive}: {msg}")

        return "\n".join(lines)

    # ══════════════════════════════════════════════
    # 造 · Create — 场景/角色/动画/环境开发
    # ══════════════════════════════════════════════

    # ── 角色构建 ──

    def create_character(self, name: str, gender: str = "female",
                         morph_template: str = "",
                         expression: str = "neutral",
                         position: tuple = (0, 0, 0)) -> dict:
        """造·快速创建角色atom"""
        builder = characters.CharacterBuilder(name, gender)
        if morph_template:
            builder.morphs.from_template(morph_template)
        if expression:
            builder.expression.set_expression(expression)
        builder.set_position(*position)
        return builder.build()

    def create_character_builder(self, name: str,
                                 gender: str = "female") -> characters.CharacterBuilder:
        """造·获取角色构建器实例 (高级用法)"""
        return characters.CharacterBuilder(name, gender)

    def see_character_assets(self) -> dict:
        """视·列出所有角色相关资产 (外观/服装/发型/模板)"""
        return characters.list_all_character_assets()

    def see_morph_templates(self) -> list:
        """视·列出可用形态模板"""
        return list(characters.MorphPreset.TEMPLATES.keys())

    def see_expression_presets(self) -> list:
        """视·列出可用表情预设"""
        return list(characters.ExpressionManager.EXPRESSION_PRESETS.keys())

    # ── 动画构建 ──

    def create_pose(self, preset_name: str) -> list:
        """造·从预设创建姿态 (返回storable列表)"""
        pose = animations.PoseLibrary.get_pose(preset_name)
        return pose.build()

    def create_breathing_anim(self, controller: str = "chestControl",
                              amplitude: float = 0.01) -> dict:
        """造·创建呼吸动画"""
        anim = animations.create_breathing_animation(controller, amplitude)
        return anim.build()

    def create_idle_anim(self, controller: str = "hipControl",
                         amplitude: float = 0.02) -> dict:
        """造·创建空闲摇摆动画"""
        anim = animations.create_idle_sway(controller, amplitude)
        return anim.build()

    def create_timeline(self, name: str, duration: float = 5.0,
                        loop: bool = True) -> animations.TimelineBuilder:
        """造·获取时间线构建器实例 (高级用法)"""
        return animations.TimelineBuilder(name, duration, loop)

    def see_pose_presets(self) -> list:
        """视·列出可用姿态预设"""
        return animations.PoseLibrary.list_poses()

    # ── 环境构建 ──

    def create_environment(self, lighting: str = "three_point",
                           camera: str = "portrait") -> list:
        """造·快速创建环境atoms (灯光+相机)"""
        env = environments.EnvironmentBuilder()
        env.lighting.from_preset(lighting)
        env.cameras.from_preset(camera)
        return env.build_atoms()

    def create_environment_builder(self) -> environments.EnvironmentBuilder:
        """造·获取环境构建器实例 (高级用法)"""
        return environments.EnvironmentBuilder()

    def see_lighting_presets(self) -> list:
        """视·列出可用灯光预设"""
        return environments.LightingRig.list_presets()

    def see_camera_presets(self) -> list:
        """视·列出可用相机预设"""
        return environments.CameraRig.list_presets()

    def see_environment_assets(self) -> list:
        """视·列出可用环境资产"""
        env = environments.EnvironmentBuilder()
        return env.list_available_assets()

    def see_sounds(self) -> list:
        """视·列出可用音频"""
        env = environments.EnvironmentBuilder()
        return env.list_available_sounds()

    # ── 插件生成 ──

    def create_plugin(self, class_name: str,
                      description: str = "") -> plugin_gen.PluginGenerator:
        """造·获取C#插件生成器实例"""
        return plugin_gen.PluginGenerator(class_name, description)

    def create_scripter_script(self, name: str,
                               atom_id: str = "Person") -> plugin_gen.ScripterGenerator:
        """造·获取Scripter脚本生成器实例"""
        return plugin_gen.ScripterGenerator(name, atom_id)

    def touch_deploy_plugin(self, class_name: str,
                            description: str = "",
                            storables: list = None) -> str:
        """触·生成并部署C#插件到VaM"""
        gen = plugin_gen.PluginGenerator(class_name, description)
        if storables:
            for s in storables:
                st = s.get("type", "bool")
                if st == "bool":
                    gen.add_bool(s["name"], s.get("display", ""),
                                s.get("default", False))
                elif st == "float":
                    gen.add_float(s["name"], s.get("display", ""),
                                 s.get("default", 0.0),
                                 s.get("min", 0.0), s.get("max", 1.0))
                elif st == "string":
                    gen.add_string(s["name"], s.get("display", ""),
                                  s.get("default", ""))
                elif st == "action":
                    gen.add_action(s["name"], s.get("display", ""),
                                  s.get("body", ""))
        return gen.deploy()

    # ── VAR包管理 ──

    def create_var(self, creator: str, package_name: str,
                   scene_data: dict, version: int = 1,
                   description: str = "") -> str:
        """造·快速创建VAR包 (场景→.var)"""
        return packaging.quick_var(creator, package_name,
                                   scene_data, version, description)

    def create_var_builder(self, creator: str, package_name: str,
                           version: int = 1) -> packaging.VarBuilder:
        """造·获取VAR包构建器实例 (高级用法)"""
        return packaging.VarBuilder(creator, package_name, version)

    def see_var_info(self, var_path: str) -> dict:
        """视·检查VAR包详细信息 (元数据/依赖/内容)"""
        return packaging.inspect_var(var_path)

    def smell_missing_deps(self) -> list:
        """嗅·检查所有VAR包中的缺失依赖"""
        resolver = packaging.DependencyResolver()
        return resolver.check_missing()

    # ── 场景开发管线 ──

    def create_scene_recipe(self, name: str,
                            description: str = "") -> pipeline.SceneRecipe:
        """造·创建场景配方 (声明式场景定义)"""
        return pipeline.SceneRecipe(name, description)

    def create_scene_from_template(self, template_name: str,
                                   save: bool = True) -> dict:
        """造·从预定义模板创建完整场景"""
        return pipeline.quick_scene(template_name, save)

    def create_scene_pipeline(self,
                              recipe: pipeline.SceneRecipe) -> pipeline.SceneDevPipeline:
        """造·获取场景开发管线实例 (高级用法)"""
        return pipeline.SceneDevPipeline(recipe)

    def see_scene_templates(self) -> list:
        """视·列出可用场景模板"""
        return pipeline.list_templates()

    # ── 资源发现 ──

    def discover_resources(self, force_rescan: bool = False) -> dict:
        """味·扫描并索引VaM安装中的所有真实资源"""
        index = discovery.get_index(force_rescan)
        return index.summary()

    def search_resources(self, category: str = "", name: str = "",
                         creator: str = "", limit: int = 20) -> list:
        """视·搜索VaM资源 (外观/服装/发型/场景/插件/morph)"""
        return discovery.quick_search(category, name, creator, limit)

    def see_resource_creators(self) -> list:
        """视·列出所有资源创作者及其资源数"""
        index = discovery.get_index()
        return index.creators()[:30]

    def see_appearances(self, creator: str = "",
                        limit: int = 20) -> list:
        """视·列出可用外观预设"""
        index = discovery.get_index()
        return [e.to_dict() for e in index.appearances(creator, limit)]

    def see_discovered_clothing(self, creator: str = "",
                                limit: int = 20) -> list:
        """视·列出发现的服装资源"""
        index = discovery.get_index()
        return [e.to_dict() for e in index.clothing(creator, limit)]

    def see_discovered_hair(self, creator: str = "",
                            limit: int = 20) -> list:
        """视·列出发现的发型资源"""
        index = discovery.get_index()
        return [e.to_dict() for e in index.hair(creator, limit)]

    def see_discovered_scenes(self, creator: str = "",
                              limit: int = 20) -> list:
        """视·列出发现的场景"""
        index = discovery.get_index()
        return [e.to_dict() for e in index.scenes(creator, limit)]

    def see_discovered_plugins(self, creator: str = "",
                               limit: int = 20) -> list:
        """视·列出发现的插件"""
        index = discovery.get_index()
        return [e.to_dict() for e in index.plugins(creator, limit)]

    def see_local_assets(self) -> dict:
        """视·扫描本地非VAR资源 (直接文件)"""
        return discovery.LocalAssetScanner.full_scan()

    # ── 综合开发仪表板 ──

    def dev_dashboard(self) -> dict:
        """造·场景开发综合仪表板"""
        return {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "morph_templates": self.see_morph_templates(),
            "expression_presets": self.see_expression_presets(),
            "pose_presets": self.see_pose_presets(),
            "lighting_presets": [p["name"] for p in self.see_lighting_presets()],
            "camera_presets": [p["name"] for p in self.see_camera_presets()],
            "scene_templates": [t["name"] for t in self.see_scene_templates()],
            "character_assets": self.see_character_assets(),
        }
