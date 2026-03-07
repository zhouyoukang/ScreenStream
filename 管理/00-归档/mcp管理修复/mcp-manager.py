#!/usr/bin/env python3
"""
MCP Manager — Windsurf MCP服务器无感热管理器
在Windsurf运行过程中完成MCP服务添加/删除/修复，零中断、零Reload

架构发现 (逆向workbench.desktop.main.js):
  - 权威配置: ~/.codeium/windsurf/mcp_config.json
    → windsurf.refreshMcpServers gRPC Unary 只读此文件
  - 次要配置: %APPDATA%/Windsurf/User/mcp.json (windsurf --add-mcp 写入)
    → 仅启动时读取，运行时刷新不读此文件
  - 刷新机制: keybinding(Ctrl+Alt+Shift+M) → windsurf.refreshMcpServers
    → 通过Windows API SendKeys无感触发，用户完全无感

Usage:
  python mcp-manager.py list                     # 列出所有MCP服务器
  python mcp-manager.py add <name> [--template]  # 添加服务器
  python mcp-manager.py remove <name>            # 删除服务器
  python mcp-manager.py enable <name>            # 启用服务器
  python mcp-manager.py disable <name>           # 禁用服务器
  python mcp-manager.py test [name]              # 测试连通性
  python mcp-manager.py fix                      # 八祸自动修复
  python mcp-manager.py catalog                  # 显示可用模板
  python mcp-manager.py backup                   # 备份配置
  python mcp-manager.py restore [file]           # 恢复配置
  python mcp-manager.py status                   # 全面健康检查
  python mcp-manager.py refresh                  # 触发Windsurf刷新
"""

import json
import os
import sys
import subprocess
import shutil
import time
import socket
import ctypes
import ctypes.wintypes
from pathlib import Path
from datetime import datetime

# ============================================================
# 配置路径
# ============================================================
HOME = Path(os.environ.get("USERPROFILE", os.path.expanduser("~")))
APPDATA = Path(os.environ.get("APPDATA", HOME / "AppData" / "Roaming"))

CONFIG_LEGACY = HOME / ".codeium" / "windsurf" / "mcp_config.json"
CONFIG_NEW = APPDATA / "Windsurf" / "User" / "mcp.json"
BACKUP_DIR = HOME / ".codeium" / "windsurf" / "backups"

KEYBINDINGS_PATH = APPDATA / "Windsurf" / "User" / "keybindings.json"
SENDKEYS_SCRIPT = Path(__file__).parent / "_send_mcp_refresh.ps1"

# ============================================================
# MCP服务器模板库 (含八祸防护)
# ============================================================
CATALOG = {
    "chrome-devtools": {
        "desc": "Chrome DevTools Protocol — 浏览器DOM/网络/性能分析",
        "config": {
            "command": "cmd.exe",
            "args": ["/c", "C:\\temp\\chrome-devtools-mcp.cmd"],
            "disabled": False,
        },
        "notes": "v4: cmd.exe wrapper绕过npx超时(九祸#9)，--isolated在wrapper中设置",
    },
    "context7": {
        "desc": "Context7 — 库文档实时查询(resolve→query)",
        "config": {
            "command": "cmd.exe",
            "args": ["/c", "C:\\temp\\context7-mcp.cmd"],
            "disabled": False,
        },
        "notes": "v4: cmd.exe wrapper绕过npx超时(九祸#9)，无需env段",
    },
    "playwright": {
        "desc": "Playwright — 无头浏览器自动化(截图/填表/导航)",
        "config": {
            "command": "cmd.exe",
            "args": ["/c", "C:\\temp\\playwright-mcp.cmd"],
            "disabled": False,
        },
        "notes": "v4.1: --config声明式配置(超时/视口/Chromium优化)，禁止env段(八祸#8)",
        "install_cmd": "npx.cmd -y playwright install chromium",
        "install_env": {"HTTPS_PROXY": "http://127.0.0.1:7890"},
    },
    "github": {
        "desc": "GitHub — 仓库/Issue/PR/搜索(需Token+代理)",
        "config": {
            "command": "cmd.exe",
            "args": ["/c", "C:\\temp\\github-mcp.cmd"],
            "disabled": False,
        },
        "notes": "v4: cmd.exe wrapper绕过npx(八祸#6/#9)，代理+Token在wrapper中设置，禁止env段",
        "requires": ["GITHUB_PERSONAL_ACCESS_TOKEN"],
        "wrapper": True,
    },
    "fetch": {
        "desc": "Fetch MCP — HTTP请求(已被IWR替代，建议禁用)",
        "config": {
            "command": "npx.cmd",
            "args": ["-y", "fetch-mcp"],
            "disabled": True,
        },
        "notes": "弹窗无法关闭(二进制硬编码)，用IWR替代",
    },
    "filesystem": {
        "desc": "Filesystem — 文件系统操作(读写/搜索/目录)",
        "config": {
            "command": "npx.cmd",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "C:/"],
            "disabled": False,
        },
        "notes": "最后一个参数是允许访问的根目录",
    },
    "memory": {
        "desc": "Memory — 知识图谱持久化记忆",
        "config": {
            "command": "npx.cmd",
            "args": ["-y", "@modelcontextprotocol/server-memory"],
            "disabled": False,
        },
        "notes": "数据存储在~/.mcp-memory/",
    },
    "sequential-thinking": {
        "desc": "Sequential Thinking — 分步推理/复杂问题分解",
        "config": {
            "command": "npx.cmd",
            "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"],
            "disabled": False,
        },
        "notes": "适合复杂推理任务",
    },
    "puppeteer": {
        "desc": "Puppeteer — Chrome自动化(截图/PDF/爬取)",
        "config": {
            "command": "npx.cmd",
            "args": ["-y", "@modelcontextprotocol/server-puppeteer"],
            "disabled": False,
        },
        "notes": "与playwright功能重叠，二选一",
    },
    "brave-search": {
        "desc": "Brave Search — 网页搜索(需API Key)",
        "config": {
            "command": "npx.cmd",
            "args": ["-y", "@modelcontextprotocol/server-brave-search"],
            "disabled": False,
        },
        "notes": "需BRAVE_API_KEY环境变量",
        "requires": ["BRAVE_API_KEY"],
    },
    "sqlite": {
        "desc": "SQLite — 数据库查询/分析",
        "config": {
            "command": "npx.cmd",
            "args": ["-y", "@modelcontextprotocol/server-sqlite", "C:/temp/data.db"],
            "disabled": False,
        },
        "notes": "最后参数是数据库路径",
    },
    "everything": {
        "desc": "Everything — Windows极速文件搜索(需Everything运行)",
        "config": {
            "command": "npx.cmd",
            "args": ["-y", "@modelcontextprotocol/server-everything"],
            "disabled": False,
        },
        "notes": "需要Everything搜索引擎运行",
    },
}

# ============================================================
# 八祸知识库
# ============================================================
NINE_DISASTERS = [
    {"id": 1, "name": "BOM",        "symptom": "0 MCPs全消失",       "check": "check_bom",    "fix": "fix_bom"},
    {"id": 2, "name": "npx",        "symptom": "新窗口0 MCPs",       "check": "check_npx",    "fix": "fix_npx"},
    {"id": 3, "name": "${env:}",    "symptom": "pipe closed",        "check": "check_envvar", "fix": "fix_envvar"},
    {"id": 4, "name": "fetch代理",   "symptom": "fetch failed",       "check": "check_proxy",  "fix": None},
    {"id": 5, "name": "Playwright", "symptom": "icu_util崩溃",       "check": "check_pw",     "fix": "fix_pw"},
    {"id": 6, "name": "env感染",    "symptom": "GitHub黄点",         "check": "check_env_infection", "fix": "fix_env_infection"},
    {"id": 7, "name": "gzip腐败",   "symptom": "API返回乱码",        "check": "check_gzip",   "fix": None},
    {"id": 8, "name": "代理干扰CDP", "symptom": "Playwright黄点",     "check": "check_cdp",    "fix": "fix_cdp"},
    {"id": 9, "name": "npx超时",    "symptom": "3/4红灯deadline",    "check": "check_npx_timeout", "fix": None},
]

# ============================================================
# 核心函数
# ============================================================

def read_config(path):
    """读取配置文件，返回dict"""
    if not path.exists():
        return {}
    try:
        text = path.read_text(encoding="utf-8-sig")  # 容忍BOM
        data = json.loads(text)
        return data
    except Exception as e:
        print(f"  ⚠ 读取 {path.name} 失败: {e}")
        return {}

def write_config(path, data):
    """写入配置文件，UTF-8无BOM"""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2, ensure_ascii=False)
    path.write_bytes(text.encode("utf-8"))  # 无BOM
    return True

def get_all_servers():
    """合并两个配置文件的服务器列表"""
    legacy = read_config(CONFIG_LEGACY)
    new = read_config(CONFIG_NEW)
    
    servers = {}
    
    # 旧配置
    legacy_servers = legacy.get("mcpServers", {})
    for name, cfg in legacy_servers.items():
        servers[name] = {"config": cfg, "source": "legacy", "path": CONFIG_LEGACY}
    
    # 新配置(覆盖旧配置同名服务器)
    new_servers = new.get("servers", {})
    for name, cfg in new_servers.items():
        if name in servers:
            servers[name] = {"config": cfg, "source": "both", "path": CONFIG_NEW}
        else:
            servers[name] = {"config": cfg, "source": "new", "path": CONFIG_NEW}
    
    return servers

def ensure_keybinding():
    """确保keybindings.json中有refreshMcpServers快捷键"""
    target_binding = {"key": "ctrl+alt+shift+m", "command": "windsurf.refreshMcpServers"}
    
    if KEYBINDINGS_PATH.exists():
        try:
            text = KEYBINDINGS_PATH.read_text(encoding="utf-8-sig")
            bindings = json.loads(text)
            for b in bindings:
                if b.get("command") == "windsurf.refreshMcpServers":
                    return True  # 已存在
            bindings.append(target_binding)
        except:
            bindings = [target_binding]
    else:
        bindings = [target_binding]
    
    KEYBINDINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    KEYBINDINGS_PATH.write_bytes(json.dumps(bindings, indent=2).encode("utf-8"))
    return True

def trigger_refresh():
    """无感触发Windsurf MCP刷新
    
    机制: keybinding(Ctrl+Alt+Shift+M) → windsurf.refreshMcpServers → gRPC RefreshMcpServers
    通过Windows API SendKeys发送快捷键，用户完全无感
    """
    ensure_keybinding()
    
    # 方法1: 直接用ctypes调用Windows API
    try:
        user32 = ctypes.windll.user32
        
        # 找Windsurf窗口
        hwnd = None
        result = subprocess.run(
            ["powershell", "-c", "(Get-Process Windsurf -EA SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1).MainWindowHandle"],
            capture_output=True, text=True, timeout=5
        )
        hwnd_val = result.stdout.strip()
        if hwnd_val and hwnd_val != "0":
            hwnd = int(hwnd_val)
        
        if not hwnd:
            print("  ⚠ Windsurf窗口未找到，请手动 Ctrl+Alt+Shift+M")
            return False
        
        # 保存当前前台窗口
        orig_fg = user32.GetForegroundWindow()
        
        # 切到Windsurf、发按键、切回
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.2)
        
        VK_CONTROL, VK_ALT, VK_SHIFT, VK_M = 0x11, 0x12, 0x10, 0x4D
        KEYEVENTF_KEYUP = 0x0002
        
        user32.keybd_event(VK_CONTROL, 0, 0, 0)
        user32.keybd_event(VK_ALT, 0, 0, 0)
        user32.keybd_event(VK_SHIFT, 0, 0, 0)
        user32.keybd_event(VK_M, 0, 0, 0)
        time.sleep(0.05)
        user32.keybd_event(VK_M, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_SHIFT, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_ALT, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
        
        time.sleep(0.2)
        user32.SetForegroundWindow(orig_fg)
        return True
        
    except Exception as e:
        print(f"  ⚠ SendKeys失败: {e}")
        print("  👉 请手动按 Ctrl+Alt+Shift+M 刷新MCP")
        return False

def backup_config():
    """备份两个配置文件"""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backed = []
    for src in [CONFIG_LEGACY, CONFIG_NEW]:
        if src.exists():
            dst = BACKUP_DIR / f"{src.stem}_{ts}{src.suffix}"
            shutil.copy2(src, dst)
            backed.append(str(dst))
    return backed

def check_port(port, host="127.0.0.1", timeout=2):
    """检查端口是否监听"""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except:
        return False

# ============================================================
# 八祸检查函数
# ============================================================

def check_bom():
    """检查BOM"""
    for cfg_path in [CONFIG_LEGACY, CONFIG_NEW]:
        if cfg_path.exists():
            raw = cfg_path.read_bytes()
            if raw[:3] == b"\xef\xbb\xbf":
                return False, f"{cfg_path.name} 有BOM"
    return True, "无BOM"

def fix_bom():
    for cfg_path in [CONFIG_LEGACY, CONFIG_NEW]:
        if cfg_path.exists():
            raw = cfg_path.read_bytes()
            if raw[:3] == b"\xef\xbb\xbf":
                cfg_path.write_bytes(raw[3:])
    return True

def check_npx():
    """检查command是否用npx.cmd"""
    servers = get_all_servers()
    for name, info in servers.items():
        cmd = info["config"].get("command", "")
        if cmd == "npx":
            return False, f"{name} 用了 'npx' 而非 'npx.cmd'"
    return True, "全部正确"

def fix_npx():
    for cfg_path in [CONFIG_LEGACY, CONFIG_NEW]:
        data = read_config(cfg_path)
        key = "mcpServers" if cfg_path == CONFIG_LEGACY else "servers"
        servers = data.get(key, {})
        changed = False
        for name, cfg in servers.items():
            if cfg.get("command") == "npx":
                cfg["command"] = "npx.cmd"
                changed = True
        if changed:
            write_config(cfg_path, data)
    return True

def check_envvar():
    """检查${env:}插值"""
    for cfg_path in [CONFIG_LEGACY, CONFIG_NEW]:
        if cfg_path.exists():
            text = cfg_path.read_text(encoding="utf-8")
            if "${env:" in text or "$env:" in text:
                return False, f"{cfg_path.name} 含PS变量插值"
    return True, "无插值"

def fix_envvar():
    for cfg_path in [CONFIG_LEGACY, CONFIG_NEW]:
        if cfg_path.exists():
            text = cfg_path.read_text(encoding="utf-8")
            if "${env:" in text or "$env:" in text:
                # 只能报告，不能自动修复(需要知道实际值)
                print(f"  ⚠ {cfg_path.name} 含变量插值，需手动替换为实际值")
    return False

def check_proxy():
    """检查Clash代理可用(7890为当前端口，7897为旧端口)"""
    if check_port(7890):
        return True, "Clash:7890 在线"
    if check_port(7897):
        return True, "Clash:7897 在线(旧端口)"
    return False, "Clash:7890/7897 均离线"

def check_pw():
    """检查Playwright浏览器已安装"""
    pw_dir = Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"
    chromium_dirs = list(pw_dir.glob("chromium-*")) if pw_dir.exists() else []
    if chromium_dirs:
        return True, f"Chromium已安装: {chromium_dirs[-1].name}"
    return False, "Chromium未安装"

def fix_pw():
    env = os.environ.copy()
    env["HTTPS_PROXY"] = "http://127.0.0.1:7890"
    print("  安装Playwright Chromium (需代理)...")
    result = subprocess.run(
        ["npx.cmd", "-y", "playwright", "install", "chromium"],
        env=env, capture_output=True, text=True, timeout=120
    )
    return result.returncode == 0

def check_env_infection():
    """检查env段中的NODE_OPTIONS"""
    for cfg_path in [CONFIG_LEGACY, CONFIG_NEW]:
        data = read_config(cfg_path)
        key = "mcpServers" if cfg_path == CONFIG_LEGACY else "servers"
        for name, cfg in data.get(key, {}).items():
            env = cfg.get("env", {})
            if "NODE_OPTIONS" in env:
                return False, f"{name} 的env段有NODE_OPTIONS(会感染子进程)"
    return True, "无NODE_OPTIONS感染"

def fix_env_infection():
    for cfg_path in [CONFIG_LEGACY, CONFIG_NEW]:
        data = read_config(cfg_path)
        key = "mcpServers" if cfg_path == CONFIG_LEGACY else "servers"
        changed = False
        for name, cfg in data.get(key, {}).items():
            env = cfg.get("env", {})
            if "NODE_OPTIONS" in env:
                del env["NODE_OPTIONS"]
                if not env:
                    del cfg["env"]
                changed = True
        if changed:
            write_config(cfg_path, data)
    return True

def check_gzip():
    """检查bootstrap.js代理配置完整性"""
    bs_path = Path("C:/temp/github-proxy-bootstrap.js")
    if bs_path.exists():
        text = bs_path.read_text(encoding="utf-8")
        # v3 uses undici ProxyAgent (handles encoding internally, no need for Accept-Encoding:identity)
        if "ProxyAgent" in text and "setGlobalDispatcher" in text:
            return True, "bootstrap.js v3 (undici ProxyAgent)"
        # v2 raw socket approach needs Accept-Encoding:identity
        if "Accept-Encoding" in text and "identity" in text:
            return True, "bootstrap.js v2 (raw socket + identity)"
        return False, "bootstrap.js代理配置不完整"
    return False, "bootstrap.js不存在(GitHub MCP需要)"

def check_npx_timeout():
    """检查是否使用全局安装+wrapper绕过npx超时"""
    for cfg_path in [CONFIG_LEGACY]:
        data = read_config(cfg_path)
        for name, cfg in data.get("mcpServers", {}).items():
            cmd = cfg.get("command", "")
            args = cfg.get("args", [])
            if cmd in ("npx", "npx.cmd"):
                return False, f"{name} 仍用npx(首次~105秒超时风险)"
    return True, "全部使用cmd.exe+wrapper"

def check_cdp():
    """检查Playwright是否有多余的env段"""
    for cfg_path in [CONFIG_LEGACY, CONFIG_NEW]:
        data = read_config(cfg_path)
        key = "mcpServers" if cfg_path == CONFIG_LEGACY else "servers"
        for name, cfg in data.get(key, {}).items():
            if "playwright" in name.lower():
                if "env" in cfg and ("HTTPS_PROXY" in cfg.get("env", {}) or "HTTP_PROXY" in cfg.get("env", {})):
                    return False, f"{name} 的env段有代理(干扰CDP)"
    return True, "Playwright无代理干扰"

def fix_cdp():
    for cfg_path in [CONFIG_LEGACY, CONFIG_NEW]:
        data = read_config(cfg_path)
        key = "mcpServers" if cfg_path == CONFIG_LEGACY else "servers"
        changed = False
        for name, cfg in data.get(key, {}).items():
            if "playwright" in name.lower() and "env" in cfg:
                del cfg["env"]
                changed = True
        if changed:
            write_config(cfg_path, data)
    return True

# ============================================================
# 命令实现
# ============================================================

def cmd_list():
    """列出所有MCP服务器"""
    servers = get_all_servers()
    if not servers:
        print("  无MCP服务器")
        return
    
    print(f"  {'名称':<22} {'状态':<6} {'来源':<8} {'命令'}")
    print(f"  {'─'*22} {'─'*6} {'─'*8} {'─'*40}")
    for name, info in sorted(servers.items()):
        cfg = info["config"]
        disabled = cfg.get("disabled", False)
        status = "🔴禁用" if disabled else "🟢启用"
        source = {"legacy": "旧配置", "new": "新配置", "both": "双配置"}[info["source"]]
        cmd = cfg.get("command", "?")
        args = " ".join(cfg.get("args", [])[:3])
        print(f"  {name:<22} {status:<6} {source:<8} {cmd} {args}")

def cmd_add(name, template=None, custom_json=None):
    """添加MCP服务器(写入mcp_config.json + 无感刷新)"""
    if template and template in CATALOG:
        config = CATALOG[template]["config"].copy()
        print(f"  使用模板: {template}")
        print(f"  描述: {CATALOG[template]['desc']}")
        
        requires = CATALOG[template].get("requires", [])
        for env_var in requires:
            if not os.environ.get(env_var):
                print(f"  ⚠ 需要环境变量: {env_var}")
                return False
    elif custom_json:
        config = json.loads(custom_json)
    else:
        print(f"  错误: 需要 --template 或 --json 参数")
        print(f"  可用模板: {', '.join(CATALOG.keys())}")
        return False
    
    backup_config()
    
    # 直接写入权威配置(mcp_config.json)
    data = read_config(CONFIG_LEGACY)
    if "mcpServers" not in data:
        data["mcpServers"] = {}
    data["mcpServers"][name] = config
    write_config(CONFIG_LEGACY, data)
    print(f"  📝 已写入 mcp_config.json")
    
    # 无感触发刷新
    if trigger_refresh():
        print(f"  ✅ {name} 已添加并无感生效")
    else:
        print(f"  ⚠ 自动刷新失败，请手动按 Ctrl+Alt+Shift+M")
    
    return True

def cmd_remove(name):
    """删除MCP服务器"""
    backup_config()
    removed = False
    
    # 从旧配置删除
    data = read_config(CONFIG_LEGACY)
    if name in data.get("mcpServers", {}):
        del data["mcpServers"][name]
        write_config(CONFIG_LEGACY, data)
        removed = True
        print(f"  ✅ 从 mcp_config.json 删除 {name}")
    
    # 从新配置删除
    data = read_config(CONFIG_NEW)
    if name in data.get("servers", {}):
        del data["servers"][name]
        write_config(CONFIG_NEW, data)
        removed = True
        print(f"  ✅ 从 mcp.json 删除 {name}")
    
    if removed:
        if trigger_refresh():
            print(f"  ✅ {name} 已删除并无感生效")
        else:
            print(f"  ⚠ 自动刷新失败，请手动按 Ctrl+Alt+Shift+M")
    else:
        print(f"  ⚠ 未找到服务器: {name}")
    
    return removed

def cmd_enable(name):
    """启用MCP服务器"""
    return _set_disabled(name, False)

def cmd_disable(name):
    """禁用MCP服务器"""
    return _set_disabled(name, True)

def _set_disabled(name, disabled):
    """设置服务器disabled状态"""
    backup_config()
    found = False
    
    for cfg_path in [CONFIG_LEGACY, CONFIG_NEW]:
        data = read_config(cfg_path)
        key = "mcpServers" if cfg_path == CONFIG_LEGACY else "servers"
        if name in data.get(key, {}):
            data[key][name]["disabled"] = disabled
            write_config(cfg_path, data)
            found = True
            action = "禁用" if disabled else "启用"
            print(f"  ✅ {name} 已{action} ({cfg_path.name})")
    
    if found:
        if trigger_refresh():
            action = "禁用" if disabled else "启用"
            print(f"  ✅ {name} 已{action}并无感生效")
        else:
            print(f"  ⚠ 自动刷新失败，请手动按 Ctrl+Alt+Shift+M")
    else:
        print(f"  ⚠ 未找到服务器: {name}")
    
    return found

def cmd_test(name=None):
    """测试MCP服务器连通性"""
    servers = get_all_servers()
    targets = {name: servers[name]} if name and name in servers else servers
    
    for sname, info in targets.items():
        cfg = info["config"]
        if cfg.get("disabled", False):
            print(f"  ⏸ {sname}: 已禁用(跳过)")
            continue
        
        cmd = cfg.get("command", "")
        args = cfg.get("args", [])
        
        # 检查命令可执行
        exe = shutil.which(cmd) or shutil.which(cmd.replace(".cmd", ""))
        if not exe and cmd != "cmd.exe":
            print(f"  ❌ {sname}: 命令不存在 '{cmd}'")
            continue
        
        # 检查环境依赖
        env_issues = []
        env_cfg = cfg.get("env", {})
        for key in env_cfg:
            if key == "NODE_OPTIONS":
                env_issues.append("NODE_OPTIONS感染风险")
            if key in ("HTTPS_PROXY", "HTTP_PROXY"):
                if "playwright" in sname.lower():
                    env_issues.append("代理干扰CDP")
        
        if env_issues:
            print(f"  ⚠ {sname}: {', '.join(env_issues)}")
        else:
            print(f"  ✅ {sname}: 配置健康")

def cmd_fix():
    """九祸自动修复"""
    print("  九祸自动检查:")
    issues = 0
    fixed = 0
    
    for disaster in NINE_DISASTERS:
        check_fn = globals().get(disaster["check"])
        if not check_fn:
            continue
        
        ok, msg = check_fn()
        status = "✅" if ok else "❌"
        print(f"  {status} #{disaster['id']} {disaster['name']}: {msg}")
        
        if not ok:
            issues += 1
            fix_fn_name = disaster.get("fix")
            if fix_fn_name:
                fix_fn = globals().get(fix_fn_name)
                if fix_fn:
                    if fix_fn():
                        fixed += 1
                        print(f"     → 已自动修复")
                    else:
                        print(f"     → 自动修复失败，需手动处理")
    
    print(f"\n  总计: {issues}个问题, {fixed}个已修复")
    if fixed > 0:
        if trigger_refresh():
            print(f"  ✅ 已无感刷新MCP")
        else:
            print(f"  ⚠ 请手动按 Ctrl+Alt+Shift+M 刷新")

def cmd_catalog():
    """显示可用模板"""
    print(f"  {'模板名':<24} {'描述'}")
    print(f"  {'─'*24} {'─'*50}")
    for name, info in sorted(CATALOG.items()):
        disabled = info["config"].get("disabled", False)
        tag = " [默认禁用]" if disabled else ""
        print(f"  {name:<24} {info['desc']}{tag}")
        if info.get("requires"):
            print(f"  {'':24} 需要: {', '.join(info['requires'])}")

def cmd_backup():
    """备份配置"""
    files = backup_config()
    for f in files:
        print(f"  📦 {f}")
    print(f"  共备份 {len(files)} 个文件")

def cmd_restore(backup_file=None):
    """恢复配置"""
    if backup_file:
        target = Path(backup_file)
        if not target.exists():
            print(f"  ⚠ 文件不存在: {backup_file}")
            return False
        # 根据文件名判断恢复到哪个配置
        if "mcp_config" in target.name:
            shutil.copy2(target, CONFIG_LEGACY)
            print(f"  ✅ 已恢复到 mcp_config.json")
        elif "mcp" in target.name:
            shutil.copy2(target, CONFIG_NEW)
            print(f"  ✅ 已恢复到 mcp.json")
        trigger_refresh()
        return True
    
    # 列出可用备份
    if BACKUP_DIR.exists():
        backups = sorted(BACKUP_DIR.glob("mcp*"), key=lambda p: p.stat().st_mtime, reverse=True)
        if backups:
            print("  可用备份:")
            for b in backups[:10]:
                print(f"    {b.name} ({b.stat().st_size}B, {datetime.fromtimestamp(b.stat().st_mtime).strftime('%Y-%m-%d %H:%M')})")
            return True
    print("  无可用备份")
    return False

def cmd_status():
    """全面健康检查"""
    print("═" * 60)
    print("  MCP Manager 健康检查")
    print("═" * 60)
    
    # 配置文件
    print("\n📁 配置文件:")
    for path, label in [(CONFIG_LEGACY, "旧配置"), (CONFIG_NEW, "新配置")]:
        if path.exists():
            size = path.stat().st_size
            mtime = datetime.fromtimestamp(path.stat().st_mtime).strftime("%H:%M:%S")
            print(f"  ✅ {label}: {path} ({size}B, {mtime})")
        else:
            print(f"  ⚠ {label}: {path} (不存在)")
    
    # 服务器列表
    print("\n🖥 MCP服务器:")
    cmd_list()
    
    # 九祸检查
    print("\n🔍 九祸检查:")
    for disaster in NINE_DISASTERS:
        check_fn = globals().get(disaster["check"])
        if check_fn:
            ok, msg = check_fn()
            print(f"  {'✅' if ok else '❌'} #{disaster['id']} {disaster['name']}: {msg}")
    
    # 进程检查
    print("\n⚙ Node.js进程:")
    try:
        result = subprocess.run(
            ["powershell", "-c", "(Get-Process node -EA SilentlyContinue).Count"],
            capture_output=True, text=True, timeout=5
        )
        count = result.stdout.strip() or "0"
        print(f"  Node进程数: {count}")
    except:
        print(f"  Node进程数: 未知")
    
    # Clash代理
    print("\n🌐 网络:")
    clash_ok, clash_msg = check_proxy()
    print(f"  {clash_msg} {'✅' if clash_ok else '❌'}")
    
    # Token
    token = os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN", "")
    print(f"  GitHub Token: {'✅ 已设置' if token else '❌ 未设置'}")

def cmd_refresh():
    """触发Windsurf MCP无感刷新"""
    if trigger_refresh():
        print("  ✅ 已无感触发Windsurf MCP刷新 (SendKeys → Ctrl+Alt+Shift+M)")
    else:
        print("  ⚠ 自动刷新失败，请手动按 Ctrl+Alt+Shift+M")

# ============================================================
# CLI入口
# ============================================================

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    
    command = sys.argv[1].lower()
    args = sys.argv[2:]
    
    print(f"\n🔧 MCP Manager — {command}")
    print("─" * 40)
    
    if command == "list":
        cmd_list()
    elif command == "add":
        if not args:
            print("  用法: add <name> --template <template>")
            print("  或:   add <name> --json '{...}'")
            return
        name = args[0]
        template = None
        custom_json = None
        for i, a in enumerate(args[1:], 1):
            if a == "--template" and i + 1 < len(args):
                template = args[i + 1]
            elif a == "--json" and i + 1 < len(args):
                custom_json = args[i + 1]
        if not template and not custom_json:
            template = name  # 名称即模板
        cmd_add(name, template=template, custom_json=custom_json)
    elif command == "remove":
        if args:
            cmd_remove(args[0])
        else:
            print("  用法: remove <name>")
    elif command == "enable":
        if args:
            cmd_enable(args[0])
        else:
            print("  用法: enable <name>")
    elif command == "disable":
        if args:
            cmd_disable(args[0])
        else:
            print("  用法: disable <name>")
    elif command == "test":
        cmd_test(args[0] if args else None)
    elif command == "fix":
        cmd_fix()
    elif command == "catalog":
        cmd_catalog()
    elif command == "backup":
        cmd_backup()
    elif command == "restore":
        cmd_restore(args[0] if args else None)
    elif command == "status":
        cmd_status()
    elif command == "refresh":
        cmd_refresh()
    else:
        print(f"  未知命令: {command}")
        print("  可用: list add remove enable disable test fix catalog backup restore status refresh")

if __name__ == "__main__":
    main()
