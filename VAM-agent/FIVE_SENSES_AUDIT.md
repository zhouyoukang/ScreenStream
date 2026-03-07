# VAM-agent 五感代码审计报告

> 审计时间: 2026-06 | 审计范围: VAM-agent/ 全部Python模块
> 审计方法: 逐文件阅读 → 问题分类 → 严重度评级 → 修复建议

## 审计范围 (27个核心文件)

| 包 | 文件 | 行数 | 职责 |
|----|------|------|------|
| **顶层** | `__main__.py` | 167 | 主CLI入口 |
| **顶层** | `master.py` | 946 | MasterAgent全域编排器 |
| **vam/** | `__init__.py` | 30 | 包入口/六感架构声明 |
| **vam/** | `config.py` | 92 | VaM路径/常量 |
| **vam/** | `agent.py` | 602 | VaMAgent六感中枢 |
| **vam/** | `process.py` | 104 | VaM进程管理 |
| **vam/** | `scenes.py` | 331 | 场景CRUD+SceneBuilder |
| **vam/** | `resources.py` | 238 | 资源扫描/管理 |
| **vam/** | `plugins.py` | 156 | BepInEx/脚本管理 |
| **vam/** | `logs.py` | 124 | 日志监控+错误检测 |
| **vam/** | `gui.py` | 902 | GUI自动化(Win32+OCR) |
| **vam/** | `signalr.py` | 8 | 重导向到voxta/signalr |
| **vam/bridge/** | `__init__.py` | 55 | Bridge包入口 |
| **vam/bridge/** | `client.py` | 548 | VaMBridge HTTP客户端 |
| **voxta/** | `__init__.py` | 23 | 包入口/五感架构声明 |
| **voxta/** | `config.py` | 91 | Voxta路径/端口/模块分类 |
| **voxta/** | `agent.py` | 367 | VoxtaAgent五感中枢 |
| **voxta/** | `db.py` | 282 | SQLite DB直控 |
| **voxta/** | `signalr.py` | 412 | SignalR WebSocket客户端 |
| **voxta/** | `process.py` | 127 | 服务进程管理 |
| **voxta/** | `logs.py` | 21 | 日志读取(极简) |
| **voxta/** | `chat.py` | 583 | 聊天引擎(双模式) |
| **voxta/** | `hub.py` | 775 | 中枢控制(DB高级/诊断/修复) |
| **voxta/** | `__main__.py` | 249 | Voxta CLI入口 |
| **browser_bridge/** | `playwright_agent.py` | 583 | 桌面应用浏览器化Agent |

**总代码量**: ~7,000+ 行 Python

---

## 一、严重问题 (CRITICAL) — 必须修复

### C1. db.py 与 hub.py 大规模代码重复

**严重度**: 🔴 CRITICAL (架构腐蚀)

两个文件实现了几乎完全相同的DB操作，但使用不同模式：

| 功能 | `db.py` (函数式) | `hub.py` (VoxtaDB类) |
|------|-----------------|---------------------|
| 备份 | `backup_db()` | `VoxtaDB.backup()` |
| 角色列表 | `list_characters()` | `VoxtaDB.list_characters()` |
| 模块列表 | `list_modules()` | `VoxtaDB.list_modules()` |
| 启停模块 | `set_module_enabled()` | `VoxtaDB.set_module_enabled()` |
| 记忆书 | `list_memory_books()` | `VoxtaDB.list_memory_books()` |
| 预设 | `list_presets()` | `VoxtaDB.list_presets()` |
| 消息 | `recent_messages()` | `VoxtaDB.recent_messages()` |
| 统计 | `get_stats()` | `VoxtaDB.stats()` |
| 连接 | `_connect_db(readonly=True)` | `VoxtaDB._conn()`(无readonly) |
| 脱敏 | ✅ DPAPI掩码 | ❌ 无 |

**影响**: 
- `voxta/agent.py` 同时依赖两者，行为不一致
- `db.py` 有readonly保护 + DPAPI脱敏，`hub.py` 没有
- Bug修复只改一处，另一处继续有问题

**建议**: 统一为单一DB层，`hub.py` 的增强功能(CRUD/TavernCard/诊断)作为上层扩展。

### C2. DB连接泄露风险

**严重度**: 🔴 CRITICAL (资源泄露)

`db.py` 中多个函数使用 `conn = _connect_db()` 但无 `try/finally` 保护：

```python
# db.py 问题模式 (get_stats, list_characters, list_modules, list_memory_books, 
#                 list_presets, list_chats, recent_messages, list_scenarios)
def list_characters() -> list:
    conn = _connect_db()
    chars = []
    for r in conn.execute("SELECT * FROM Characters"):  # 若此处异常
        ...
    conn.close()  # 永远不会执行
    return chars
```

`hub.py` 的 `VoxtaDB` 同样存在此问题。

**建议**: 使用 `with` 上下文管理器或 `try/finally` 包裹所有DB操作。

### C3. SQL注入向量

**严重度**: 🔴 CRITICAL (安全)

多处使用f-string拼接SQL列名/表名：

| 文件:行 | 代码 | 风险 |
|---------|------|------|
| `db.py:89` | `f"UPDATE Characters SET [{field}]=?"` | 列名注入 |
| `hub.py:171` | `f"UPDATE Characters SET [{key}]=?"` | 列名注入 |
| `hub.py:363` | `f"UPDATE Characters SET {set_clause}"` | 列名注入 |
| `hub.py:448` | `f"SELECT COUNT(*) FROM [{table}]"` | 表名注入 |
| `db.py:46` | `f"SELECT COUNT(*) FROM [{table}]"` | 表名注入 |

虽然调用方通常可信，但应加白名单校验防御。

### C4. 凭据硬编码

**严重度**: 🔴 CRITICAL (安全)

| 位置 | 内容 | 问题 |
|------|------|------|
| `hub.py:613` | `'aLMmT1pWgy6Okyh2cauMYaYpsHUVzb1c'` | 火山引擎token明文写在诊断检查里 |
| `AGENTS.md:117` | `vam666` | VaM Box密码在tracked文件中明文 |
| `chat.py:32-33` | API URL硬编码 | 非凭据但应可配置 |

**建议**: 所有检查用的token/密码移入 `secrets.env`，代码中只引用键名。

### C5. 无依赖管理文件

**严重度**: 🔴 CRITICAL (可移植性)

整个项目**无 `requirements.txt`**。散落的依赖包括：

| 模块 | 依赖 | 类型 |
|------|------|------|
| `gui.py` | `pywin32`, `mss`, `rapidocr_onnxruntime` | Windows专用 |
| `signalr.py` | `websocket-client` | 核心功能 |
| `chat.py` | (标准库) | 无额外依赖 |
| `browser_bridge/` | `playwright`, `fastapi`, `uvicorn`, `mss`, `opencv-python` | 可选功能 |

**建议**: 创建 `requirements.txt` (核心) + `requirements-gui.txt` (GUI) + `requirements-bridge.txt` (Browser Bridge)。

---

## 二、警告级问题 (WARNING) — 应尽快修复

### W1. chat.py 与 hub.py LLM/TTS功能重复

`chat.py` 有完整的 `LLMClient` 和 `TTSClient` 类。
`hub.py` 有 `DirectAPI.edgetts_speak()` 和 `DirectAPI.dashscope_chat()`。

两套实现不同（chat.py更完善），应统一。

### W2. voxta/logs.py 功能极度单薄

仅21行，只能读最后N行日志。相比 `vam/logs.py`（124行，有错误模式检测、BepInEx日志、关键词搜索），Voxta日志模块几乎为空壳。

缺失功能：
- 错误模式检测
- 日志级别过滤
- 关键词搜索
- 日志大小监控

### W3. process.py 工具函数重复

`vam/process.py` 和 `voxta/process.py` 各自实现了 `check_port()` 和 `check_http()`，代码几乎相同。应提取到共享工具模块。

### W4. VaMAgent方法膨胀

`vam/agent.py` 声称"六感Agent"，但实际有 **60+方法**。其中 ~40个是 `VaMBridge` 的薄包装：

```python
def runtime_atoms(self) -> List[dict]:
    return self._bridge.list_atoms()  # 纯转发
```

AGENTS.md声称"22方法"，与实际严重不符。可考虑 `__getattr__` 委托或分组子对象。

### W5. hub.py 危险操作无备份保护

| 方法 | 风险 |
|------|------|
| `VoxtaDB.delete_character()` | 直接删除，无备份 |
| `VoxtaDB.clear_chat_history()` | 清空全部对话，无备份 |
| `VoxtaDB.update_character()` | 无备份直接写 |

对比 `db.py` 的 `update_character_field()` 会先调 `backup_db()`。

### W6. 错误吞没模式普遍

大量 `except Exception: pass` 或 `except Exception: return False`，隐藏了真实错误：

```python
# db.py:47 — 静默忽略表不存在
except Exception:
    pass

# hub.py:59 — 配置解析失败静默
except Exception:
    pass

# db.py:93 — 更新失败只返回False，不记录原因
except Exception:
    return False
```

**建议**: 至少添加 `logging.debug()` 记录被吞没的异常。

### W7. 硬编码驱动器路径

`resources.py:226` 和 `hub.py:618` 硬编码了 `["F:", "D:", "E:"]` 驱动器。应从config获取或动态检测。

### W8. chat.py API Key通过环境变量加载但未集成secrets.env

`LLMClient.chat_with_fallback()` 从 `os.environ.get(env_key)` 加载API Key。
项目的凭据协议要求从 `secrets.env` 加载，但 `chat.py` 未实现此集成。

---

## 三、信息级问题 (INFO) — 改善建议

### I1. 测试文件组织

- `vam/tests/` 有16个测试文件（GUI导航相关），全是实操测试
- `voxta/tools/` 有8个 `_test_*.py` 文件混在工具目录中
- 无单元测试，无mock测试，无CI可用的测试

### I2. browser_bridge 与主包耦合松散

`browser_bridge/` 独立性好，但与vam/voxta包无import关系。
`DesktopAgent` 可作为 `VaMAgent` 的 `hand` 感官的升级替代。

### I3. master.py status() 方法直接引用模块级变量

```python
# master.py:890
voxta_db.get_stats()  # 引用顶层import的模块
# master.py:895-896
vam_process.get_all_status()
voxta_process.get_all_status()
```

这些应通过 `self.vam` / `self.voxta` agent实例访问，而非直接调用底层模块。

### I4. signalr.py websocket-client检测

`VoxtaSignalR.connect()` 在运行时才检查 `import websocket`，无安装指引自动化。

### I5. CharacterLoader 在 chat.py 中重复了 db.py / hub.py 的角色加载

`chat.py` 的 `CharacterLoader` 又一次实现了角色从DB加载的逻辑，是db.py + hub.py之外的**第三份实现**。

### I6. AGENTS.md 文档与代码不一致

| 文档声明 | 实际代码 |
|---------|---------|
| VaMAgent 22方法 | 60+方法 |
| 缺少 `gui.py` 模块说明 | gui.py是最大模块(902行) |
| 缺少 `bridge/` 子包说明 | bridge是核心运行时通道 |
| 遗留工具"已迁入" | 工具文件仍存在于磁盘 |

---

## 四、架构评估

### 优点 ✅

1. **感官隔离清晰**: 六感(VaM) + 五感(Voxta) 架构，方法命名规范 (`see_/hear_/touch_/smell_/taste_/hand_`)
2. **通道优先级设计**: Bridge HTTP > DB > File > GUI 的非侵入降级链
3. **双模式聊天引擎**: standalone/voxta 两种模式灵活切换
4. **SignalR协议实现完整**: greeting处理、zombie chat恢复、action推理都有
5. **CLI入口完善**: 30+子命令覆盖查看/连接/操作/聊天/诊断全生命周期
6. **TavernCard导入**: 支持PNG和JSON两种V2格式
7. **MouseGuard设计**: GUI自动化时保护用户操作不被干扰
8. **SceneBuilder**: 编程式场景构建，支持Voxta角色注入

### 问题模式 ❌

| 模式 | 出现次数 | 根因 |
|------|---------|------|
| DB层三重实现 | 3 (db.py/hub.py/chat.py) | 功能迁移时未合并旧代码 |
| 连接未释放 | ~15处 | 未使用上下文管理器 |
| 异常静默吞没 | ~20处 | 防御式编程过度 |
| f-string SQL | 5处 | 快速开发习惯 |
| 硬编码路径/值 | ~10处 | 单机开发思维 |
| 工具函数重复 | 2处(check_port/check_http) | vam/voxta包独立开发 |

---

## 五、修复优先级矩阵

| 优先级 | 问题 | 预计工作量 | 影响面 |
|--------|------|-----------|--------|
| **P0** | C5 创建requirements.txt | 30min | 全项目可移植性 |
| **P0** | C4 凭据清理 | 1h | 安全 |
| **P1** | C2 DB连接try/finally | 2h | 数据安全 |
| **P1** | C1 DB层统一 | 4h | 架构整洁度 |
| **P1** | C3 SQL列名白名单 | 1h | 安全 |
| **P2** | W1 LLM/TTS统一 | 2h | 减少重复 |
| **P2** | W2 Voxta日志增强 | 1h | 监控能力 |
| **P2** | W3 共享工具提取 | 1h | 代码复用 |
| **P2** | W5 危险操作加备份 | 1h | 数据安全 |
| **P2** | W6 异常日志记录 | 2h | 可调试性 |
| **P3** | W4 Agent方法重构 | 3h | 可维护性 |
| **P3** | W8 secrets.env集成 | 1h | 凭据规范 |
| **P3** | I1-I6 文档/测试对齐 | 2h | 文档准确性 |

---

## 六、依赖图谱

```
__main__.py ──→ master.py ──→ VaMAgent (vam/agent.py)
                           ──→ VoxtaAgent (voxta/agent.py)
                           ──→ VoxtaDB, Diagnostics, AutoFix (voxta/hub.py)
                           ──→ voxta_db (voxta/db.py)  ← 与hub.py重复
                           ──→ vam/voxta process模块

VaMAgent ──→ config, process, scenes, resources, plugins, logs, gui
         ──→ VaMBridge (vam/bridge/client.py)

VoxtaAgent ──→ config, db, hub(lazy), chat(lazy), signalr, process, logs

ChatEngine ──→ CharacterLoader  ← 与db.py/hub.py重复
           ──→ ConversationHistory
           ──→ PromptBuilder
           ──→ LLMClient       ← 与hub.py DirectAPI重复
           ──→ TTSClient       ← 与hub.py DirectAPI重复
           ──→ VoxtaSignalR (voxta模式)

browser_bridge/ ──→ playwright (独立，与主包无耦合)
```

---

## 七、下一步行动

1. **P0 立即修复**: 创建 `requirements.txt` + 清理凭据硬编码
2. **P1 本周修复**: DB连接安全化 + DB层统一 + SQL注入防护
3. **P2 下周修复**: LLM/TTS统一 + 日志增强 + 共享工具提取
4. **P3 持续改善**: Agent方法重构 + secrets.env全面集成 + 文档对齐
