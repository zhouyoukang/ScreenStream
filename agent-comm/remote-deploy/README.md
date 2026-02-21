# Agent-Comm Remote Agent Deploy

将此文件夹复制到远程 Windows 机器，运行 `setup.bat` 即可连接到中央 Dashboard。

## 前置条件
- Python 3.8+ 已安装并在 PATH 中
- 网络可达 Dashboard 主机（默认 192.168.10.219:9901）

## 部署步骤
1. 复制整个 `remote-deploy/` 目录到远程机器（如 `C:\agent-comm\`）
2. 编辑 `config.json`，确认 `connect_host` 指向 Dashboard 主机 IP
3. 双击 `setup.bat`
4. 重启 Windsurf IDE

## 文件说明
```
remote-deploy/
├── README.md           ← 本文件
├── config.json         ← 远程配置（指向Dashboard主机IP）
├── bridge_agent.py     ← 通信客户端
├── bridge.bat          ← 入口脚本
└── setup.bat           ← 一键部署规则到当前账号
```
