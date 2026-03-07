"""
Agent操作电脑 · 统一探测脚本
扫描所有agent系统的运行状态、端口、API健康度
用法: python probe.py [--fix] [--verbose]
"""
import json, socket, subprocess, sys, os, time, ssl
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

WORKSPACE = Path(__file__).parent.parent
VERBOSE = '--verbose' in sys.argv or '-v' in sys.argv
FIX_MODE = '--fix' in sys.argv

# ═══════════════════════════════════════════════════════════════
# 系统注册表 — 所有agent操作电脑的系统
# ═══════════════════════════════════════════════════════════════
SYSTEMS = [
    {
        "name": "笔记本Agent(LAN)",
        "dir": "远程桌面",
        "desc": "55+端点全能控制(截屏/键鼠/Shell/文件/UIA/Guardian)",
        "port": 9903,
        "host": "192.168.31.179",
        "health": "/health",
        "local_only": False,
        "public_url": "http://60.205.171.100:19903/health",
        "key_files": [],
    },
    {
        "name": "远程桌面Agent(台式机)",
        "dir": "远程桌面",
        "desc": "Python HTTP全能控制(截屏/键鼠/Shell/进程/文件/Guardian)",
        "port": 9903,
        "host": "127.0.0.1",
        "health": "/health",
        "local_only": False,
        "expected_stopped": True,  # 运行于笔记本，台式机不启动
        "start_cmd": "start_agent.bat",
        "key_files": ["remote_agent.py", "remote_desktop.html", "rdp_agent.py"],
    },
    {
        "name": "远程中枢(Node.js)",
        "dir": "远程桌面/remote-hub",
        "desc": "WebSocket三体架构(Sense↔Brain↔Agent), 17步自动诊断",
        "port": 3002,
        "host": "0.0.0.0",
        "health": "/health",
        "local_only": False,
        "public_url": "https://aiotvr.xyz/agent/",
        "start_cmd": "start_all.bat",
        "key_files": ["server.js", "page.js", "brain.js"],
    },
    {
        "name": "AGI仪表盘",
        "dir": "AGI",
        "desc": "系统健康/凭据/Skills/Observatory统一仪表盘",
        "port": 9090,
        "host": "127.0.0.1",
        "health": "/",
        "local_only": True,
        "start_cmd": "start.bat",
        "key_files": ["dashboard-server.py"],
    },
    {
        "name": "Clash VPN管理",
        "dir": "clash-agent",
        "desc": "代理引擎+Web UI(6分类应用路由/实时连接/节点管理)",
        "port": 9098,
        "host": "127.0.0.1",
        "health": "/api/status",
        "local_only": True,
        "alt_port": 7890,
        "alt_check": "proxy_port",
        "start_cmd": "start.bat",
        "key_files": ["vpn-manager.py", "clash-meta.exe"],
        "runtime_dir": "D:\\VPN",
    },
    {
        "name": "智能家居网关",
        "dir": "智能家居/网关服务",
        "desc": "HA代理+涂鸦+eWeLink+微信(proactive_agent主动推送)",
        "port": 8900,
        "host": "127.0.0.1",
        "health": "/",
        "local_only": False,
        "expected_stopped": True,  # 按需启动
        "start_cmd": "start.bat",
        "key_files": ["gateway.py", "proactive_agent.py", "dashboard.html"],
    },
    {
        "name": "认知代理",
        "dir": "认知代理",
        "desc": "五维感知(文件/输入/窗口/剪贴板/网络)+意图提炼+工作流引擎",
        "port": 9070,
        "host": "127.0.0.1",
        "health": "/health",
        "local_only": True,
        "expected_stopped": True,  # 按需启动
        "key_files": ["server.py", "mcp_server.py"],
    },
    {
        "name": "二手书系统",
        "dir": None,
        "desc": "ModularSystem 190路由 (运行于E盘)",
        "port": 8088,
        "host": "127.0.0.1",
        "health": "/",
        "local_only": False,
        "key_files": [],
    },
    {
        "name": "手机操控库",
        "dir": "手机操控库",
        "desc": "phone_lib.py(ADB/五感/循环采集/远程协助)",
        "port": None,
        "health": None,
        "local_only": True,
        "key_files": ["phone_lib.py", "five_senses.py", "phone_loop.py", "remote_assist.py"],
    },
    {
        "name": "公网投屏控制台",
        "dir": "公网投屏/cast",
        "desc": "ADB Bridge+配置中心+直连手机(setup.html)",
        "port": None,
        "health": None,
        "local_only": False,
        "public_url": "https://aiotvr.xyz/cast/setup.html",
        "key_files": ["adb-bridge.py", "setup.html", "index.html"],
    },
    # AI视频剪辑 — 已移除（目录从未创建，为计划项目）
    {
        "name": "跨账号控制(三界隔离)",
        "dir": "构建部署/三界隔离",
        "desc": "Administrator↔ai↔zhou 跨Windows账号操作",
        "port": None,
        "health": None,
        "local_only": True,
        "key_files": ["enter.ps1", "remote-exec.ps1", "status.ps1"],
    },
    {
        "name": "桌面守护(Guardian)",
        "dir": "远程桌面",
        "desc": "防误操作/自动恢复/RDP保护",
        "port": None,
        "health": None,
        "local_only": True,
        "key_files": ["desktop_guardian.ps1"],
    },
    {
        "name": "双电脑互联",
        "dir": "远程桌面/rdp",
        "desc": "RDP连接配置(已迁移自双电脑互联/)",
        "port": None,
        "health": None,
        "local_only": True,
        "key_files": ["台式机.rdp"],
    },
    {
        "name": "Voxta AI对话",
        "dir": "VAM-agent/voxta",
        "desc": "SignalR协议/角色管理/聊天引擎",
        "port": 5384,
        "host": "127.0.0.1",
        "health": None,
        "local_only": True,
        "expected_stopped": True,
        "key_files": ["agent.py", "chat.py", "hub.py"],
    },
]

# 公网端点
PUBLIC_ENDPOINTS = [
    ("aiotvr.xyz 健康检查", "https://aiotvr.xyz/api/health"),
    ("aiotvr.xyz 投屏", "https://aiotvr.xyz/cast/"),
    ("aiotvr.xyz 配置中心", "https://aiotvr.xyz/cast/setup.html"),
    ("aiotvr.xyz 远程中枢", "https://aiotvr.xyz/agent/"),
]

# 外部重复位置（应该被清理的）
EXTERNAL_DUPLICATES = [
    {
        "path": r"E:\道\AI之电脑\agent",
        "duplicate_of": "管理/00-归档/old-agent-scripts",
        "verdict": "完全重复(43文件), 可删除",
    },
    {
        "path": r"E:\道\AI之电脑\双机互联",
        "duplicate_of": "远程桌面/rdp/",
        "verdict": "完全重复, 可删除",
    },
    {
        "path": r"E:\道\AI之电脑\rdp连接配置",
        "duplicate_of": "远程桌面/rdp/ (7个RDP文件)",
        "verdict": "完全重复, 可删除",
    },
    {
        "path": r"E:\道\AI之电脑\远程桌面文档",
        "duplicate_of": "远程桌面/ + 文档/",
        "verdict": "9文档, 5已在文档/, 4在远程桌面/, 可删除",
    },
    {
        "path": r"E:\道\AI之手机",
        "duplicate_of": "手机操控库/ + 文档/",
        "verdict": "已清理 | 核心.py已迁移, 剩余为旧文档/APK/日志, 可归档",
    },
    {
        "path": r"E:\道\电脑管理",
        "duplicate_of": "无对应(POC实验)",
        "verdict": "已清理 | Agent-S/Windows-MCP/MCP-Tools均为POC垃圾(20410项), 无迁移价值",
    },
]

# ═══════════════════════════════════════════════════════════════
# 探测函数
# ═══════════════════════════════════════════════════════════════

def check_port(host, port, timeout=2):
    """检查端口是否可达"""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False

def check_http(url, timeout=5):
    """检查HTTP端点"""
    try:
        req = Request(url, headers={'User-Agent': 'AgentProbe/1.0'})
        ctx = _SSL_CTX if url.startswith('https') else None
        resp = urlopen(req, timeout=timeout, context=ctx)
        body = resp.read(2048).decode('utf-8', errors='replace')
        return resp.status, body
    except URLError as e:
        return 0, str(e)
    except Exception as e:
        return -1, str(e)

def check_files(sys_info):
    """检查关键文件是否存在"""
    missing = []
    d = sys_info.get("dir")
    if not d:
        return missing
    runtime = sys_info.get("runtime_dir")
    base = Path(runtime) if runtime and Path(runtime).exists() else WORKSPACE / d
    for f in sys_info.get("key_files", []):
        if not (base / f).exists():
            missing.append(str(base / f))
    return missing

def check_external_duplicates():
    """检查外部重复位置"""
    results = []
    for dup in EXTERNAL_DUPLICATES:
        p = Path(dup["path"])
        exists = p.exists()
        count = len(list(p.rglob("*"))) if exists else 0
        results.append({
            "path": dup["path"],
            "exists": exists,
            "file_count": count,
            "duplicate_of": dup["duplicate_of"],
            "verdict": dup["verdict"],
        })
    return results

def probe_system(sys_info):
    """探测单个系统"""
    result = {
        "name": sys_info["name"],
        "desc": sys_info["desc"],
        "dir": sys_info.get("dir", "N/A"),
        "status": "unknown",
        "issues": [],
    }
    
    # 0. 目录存在性检查
    d = sys_info.get("dir")
    if d:
        base = WORKSPACE / d
        if not base.exists():
            result["issues"].append(f"目录不存在: {d}")
            result["dir_exists"] = False
        else:
            result["dir_exists"] = True

    # 1. 文件检查
    missing = check_files(sys_info)
    if missing:
        result["issues"].append(f"缺失文件: {', '.join(missing)}")
    
    # 2. 端口检查
    port = sys_info.get("port")
    if port:
        host = sys_info.get("host", "127.0.0.1")
        if check_port(host if host != "0.0.0.0" else "127.0.0.1", port):
            result["port_status"] = f":{port} ✅"
            result["status"] = "running"
        else:
            expected = sys_info.get("expected_stopped", False)
            result["port_status"] = f":{port} ⏸️" if expected else f":{port} ❌"
            result["status"] = "expected_stopped" if expected else "stopped"
            if not expected:
                result["issues"].append(f"端口 {port} 未监听")
    
    # 3. HTTP健康检查
    health = sys_info.get("health")
    if health and port and result["status"] == "running":
        host = sys_info.get("host", "127.0.0.1")
        if host == "0.0.0.0":
            host = "127.0.0.1"
        url = f"http://{host}:{port}{health}"
        code, body = check_http(url)
        if code >= 200 and code < 400:
            result["http_status"] = f"HTTP {code} ✅"
            if VERBOSE and body:
                result["response_preview"] = body[:200]
        else:
            result["http_status"] = f"HTTP {code} ❌"
            result["issues"].append(f"健康检查失败: HTTP {code}")
    
    # 4. 公网检查
    pub_url = sys_info.get("public_url")
    if pub_url:
        code, _ = check_http(pub_url)
        if code >= 200 and code < 400:
            result["public_status"] = f"公网 ✅"
        elif code == 401:
            result["public_status"] = f"公网 ✅ (需认证)"
        else:
            result["public_status"] = f"公网 ❌ (HTTP {code})"
            result["issues"].append(f"公网不可达: {pub_url}")
    
    # 5. 备用端口检查
    alt_port = sys_info.get("alt_port")
    if alt_port:
        if check_port("127.0.0.1", alt_port):
            result["alt_port_status"] = f":{alt_port} ✅ ({sys_info.get('alt_check', 'alt')})"
        else:
            result["alt_port_status"] = f":{alt_port} ❌"
    
    # 6. 无端口系统 — 检查文件完整性即可
    if not port and not missing and result.get("dir_exists", True):
        result["status"] = "files_ok"
    elif not port and (missing or not result.get("dir_exists", True)):
        result["status"] = "broken"
    
    return result

# ═══════════════════════════════════════════════════════════════
# 主函数
# ═══════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("  Agent操作电脑 · 统一探测")
    print(f"  时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  工作区: {WORKSPACE}")
    print("=" * 60)
    
    all_issues = []
    results = []
    
    # --- 探测所有系统 ---
    print(f"\n{'━' * 60}")
    print(f"  § 1. 系统探测 ({len(SYSTEMS)}个Agent系统)")
    print(f"{'━' * 60}")
    
    running = 0
    stopped = 0
    files_ok = 0
    
    for sys_info in SYSTEMS:
        r = probe_system(sys_info)
        results.append(r)
        
        icon = {"running": "🟢", "stopped": "🔴", "expected_stopped": "⏸️", "files_ok": "📁", "broken": "💀", "unknown": "⚪"}.get(r["status"], "⚪")
        port_info = r.get("port_status", "")
        http_info = r.get("http_status", "")
        pub_info = r.get("public_status", "")
        alt_info = r.get("alt_port_status", "")
        
        status_parts = [x for x in [port_info, http_info, pub_info, alt_info] if x]
        status_str = " | ".join(status_parts) if status_parts else r["status"]
        
        print(f"  {icon} {r['name']:20s} {status_str}")
        
        if r["status"] == "running":
            running += 1
        elif r["status"] == "stopped":
            stopped += 1
        elif r["status"] == "expected_stopped":
            running += 1  # 预期停止不算问题
        elif r["status"] == "broken":
            stopped += 1  # broken counts as stopped
        else:
            files_ok += 1
        
        if r["issues"]:
            all_issues.extend([(r["name"], i) for i in r["issues"]])
    
    # --- 公网端点 ---
    print(f"\n{'━' * 60}")
    print("  § 2. 公网端点")
    print(f"{'━' * 60}")
    
    for name, url in PUBLIC_ENDPOINTS:
        code, _ = check_http(url, timeout=10)
        if code >= 200 and code < 400:
            print(f"  ✅ {name:30s} → {code}")
        elif code == 401:
            print(f"  🔒 {name:30s} → {code} (需认证)")
        else:
            print(f"  ❌ {name:30s} → {code}")
            all_issues.append(("公网", f"{name} 不可达 (HTTP {code})"))
    
    # --- 外部重复检查 ---
    print(f"\n{'━' * 60}")
    print("  § 3. 外部重复资源")
    print(f"{'━' * 60}")
    
    dups = check_external_duplicates()
    for d in dups:
        icon = "⚠️" if d["exists"] else "✅"
        status = f"存在({d['file_count']}项)" if d["exists"] else "已清理"
        print(f"  {icon} {d['path']}")
        print(f"     重复于: {d['duplicate_of']}")
        print(f"     状态: {status} | {d['verdict']}")
        if d["exists"]:
            all_issues.append(("重复", f"{d['path']} 仍存在 ({d['file_count']}项)"))
    
    # --- 汇总 ---
    print(f"\n{'━' * 60}")
    print("  § 4. 汇总")
    print(f"{'━' * 60}")
    print(f"  🟢 运行/正常: {running}  🔴 异常停止: {stopped}  📁 仅文件: {files_ok}")
    print(f"  ⚠️  问题数: {len(all_issues)}")
    
    if all_issues:
        print(f"\n{'━' * 60}")
        print("  § 5. 所有问题")
        print(f"{'━' * 60}")
        for idx, (sys_name, issue) in enumerate(all_issues, 1):
            print(f"  {idx:2d}. [{sys_name}] {issue}")
    
    # --- 输出JSON报告 ---
    report = {
        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
        "summary": {
            "running": running,
            "stopped": stopped,
            "files_ok": files_ok,
            "total_issues": len(all_issues),
        },
        "systems": results,
        "external_duplicates": dups,
        "issues": [{"system": s, "issue": i} for s, i in all_issues],
    }
    
    report_path = Path(__file__).parent / "probe_report.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n  📄 报告已保存: {report_path}")
    
    # 评分
    score = 10.0
    score -= stopped * 0.5  # 每个停止的服务扣0.5
    score -= len([d for d in dups if d["exists"]]) * 0.3  # 每个重复扣0.3
    score -= len([i for _, i in all_issues if "缺失" in i]) * 0.5  # 缺失文件扣0.5
    score = max(0, min(10, score))
    print(f"  🏆 健康评分: {score:.1f}/10")
    
    print(f"\n{'=' * 60}")
    return len(all_issues)

if __name__ == "__main__":
    sys.exit(0 if main() == 0 else 1)
