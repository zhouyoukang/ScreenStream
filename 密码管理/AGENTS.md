# AGENTS.md — 密码管理目录

## 目录用途
凭据安全的统一治理中枢。包含审计报告、自动化工具、Agent操作指令。

## Agent操作规则

### 读取凭据
```
1. read_file("凭据中心.md")           → 了解键名和结构
2. run_command("Get-Content secrets.env") → 获取实际值
3. 使用后不存入Memory                  → 防散落
```

### 禁止
- Memory中存储实际密码/Token值
- git tracked文件中写入明文凭据
- 在多处维护同一凭据的实际值

### 新增凭据流程
1. 在 `secrets.env` 添加 `KEY=value`
2. 在 `凭据中心.md` 对应section添加键名+描述
3. 代码中用 `os.environ` / `dotenv` / `Select-String` 引用

### 审计
- 运行 `python audit.py` 检测泄露
- 运行 `python sync_check.py` 检查双机同步

### 端口服务管理中枢
- 运行 `python service_hub.py` 启动中枢 (端口:9999)
- Dashboard: http://127.0.0.1:9999/dashboard
- API: `/api/status` `/api/ports` `/api/zones` `/api/terminals` `/api/conflicts` `/api/resources` `/api/health?port=N` `/api/scan` `/api/events`
- POST: `/api/cleanup` (清理僵尸终端) `/api/refresh` (刷新缓存)
- 42个端口已注册，6个Zone分区(A-F)
- 零PowerShell依赖，纯CMD+ctypes，启动<1s，API响应<500ms
