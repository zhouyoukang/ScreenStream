# AGI — 智能体系管理中心

## 核心职责
Windsurf全部AI配置的统一观管入口。三层架构（Zone 0全局 → Zone 1项目 → Zone 2目录）的可视化管理。

## 关键文件
- `dashboard-server.py` — Web仪表盘服务器(:9090)，内嵌HTML前端
- `README.md` — 用户入口指南

## 启动
```powershell
python AGI/dashboard-server.py
# → http://localhost:9090
```

## 关键约束
- **不动源配置**：`.windsurf/`是Windsurf引擎读取的配置源，AGI/仅提供管理视图层
- **只读为主**：仪表盘默认只读查看，不自动修改配置文件
- **端口9090**：不与其他服务冲突（SS 8080-8084 / 智能家居 8900 / remote_agent 9903）

## 对话结束选项
- **打开仪表盘** — 启动dashboard-server.py在浏览器中查看
- **体检一下** — 运行/health-check验证全部配置完整性
- **进化升级** — 运行/evolve发现改进点
- **收工提交** — git commit变更
