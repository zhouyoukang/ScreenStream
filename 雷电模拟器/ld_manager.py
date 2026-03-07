#!/usr/bin/env python3
"""
雷电模拟器统一管理中枢 (LDPlayer Manager Hub)
==============================================
统一管理所有虚拟机，为工作区13个手机相关项目提供全自动化测试/开发/部署/验证。

用法:
    python ld_manager.py                    # 全景状态
    python ld_manager.py --status           # 详细状态
    python ld_manager.py --setup            # 初始化: 重命名VM+升级配置+端口映射
    python ld_manager.py --test <project>   # 运行项目测试配方
    python ld_manager.py --test all         # 运行所有项目测试
    python ld_manager.py --ports            # 显示/设置端口映射
    python ld_manager.py --install-ss       # 安装ScreenStream到所有VM
    python ld_manager.py --start-ss <idx>   # 启动ScreenStream
    python ld_manager.py --health           # 全链路健康检查
    python ld_manager.py --e2e              # 端到端验证
"""

import subprocess
import json
import sys
import os
import time
import argparse
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

# ═══════════════════════════════════════════════════════════════
# 常量
# ═══════════════════════════════════════════════════════════════

LDPLAYER_DIR = r"D:\leidian\LDPlayer9"
DNCONSOLE = os.path.join(LDPLAYER_DIR, "dnconsole.exe")
ADB = os.path.join(LDPLAYER_DIR, "adb.exe")
WORKSPACE = r"d:\道\道生一\一生二"

# VM规划: index → (目标名称, 用途, 项目列表)
VM_PLAN = {
    0: ("雷电模拟器",     "通用主控",       ["ScreenStream构建验证"]),
    3: ("SS-投屏主控",    "投屏+Input+Root", ["ScreenStream", "手机操控库", "公网投屏", "亲情远程", "手机软路由"]),
    4: ("PWA-Web测试",   "PWA+浏览器+Viewer", ["二手书手机端", "电脑公网投屏手机", "智能家居", "微信公众号"]),
    5: ("采集-自动化",    "ADB自动化+采集",   ["手机购物订单", "ORS6-VAM抖音同步", "agent-phone-control"]),
}

# 项目 → 测试配置
PROJECT_CONFIG = {
    "ScreenStream": {
        "vm_index": 3,
        "needs_ss": True,
        "needs_root": True,
        "apk": "info.dvkr.screenstream.dev",
        "ports": {"gateway": 8080, "input": 8084},
        "test_urls": ["/api/status"],
        "description": "核心投屏+反向控制",
    },
    "手机操控库": {
        "vm_index": 3,
        "needs_ss": True,
        "apk": "info.dvkr.screenstream.dev",
        "ports": {"input": 8084},
        "test_urls": ["/status", "/senses"],
        "description": "PhoneLib API封装测试",
    },
    "公网投屏": {
        "vm_index": 3,
        "needs_ss": True,
        "ports": {"gateway": 8080, "mjpeg": 8081},
        "test_urls": ["/api/status"],
        "description": "ScreenStream公网投屏验证",
    },
    "亲情远程": {
        "vm_index": 3,
        "needs_ss": True,
        "ports": {"gateway": 8080, "webrtc": 8083, "input": 8084},
        "test_urls": ["/api/status"],
        "description": "WebRTC P2P远程控制",
    },
    "手机软路由": {
        "vm_index": 3,
        "needs_ss": False,
        "apk": "com.v2ray.ang",
        "ports": {"socks5": 10808},
        "description": "V2rayNG SOCKS5代理",
    },
    "二手书手机端": {
        "vm_index": 4,
        "needs_ss": False,
        "browser_url": "http://127.0.0.1:8088",
        "description": "PWA手机端UI测试",
    },
    "电脑公网投屏手机": {
        "vm_index": 4,
        "needs_ss": False,
        "ports": {"viewer": 9803},
        "browser_url": "http://127.0.0.1:9803",
        "description": "桌面投屏Viewer端测试",
    },
    "智能家居": {
        "vm_index": 4,
        "needs_ss": False,
        "browser_url": "http://127.0.0.1:8900/wx/web",
        "description": "智能家居Web控制面板",
    },
    "微信公众号": {
        "vm_index": 4,
        "needs_ss": False,
        "browser_url": "https://aiotvr.xyz/wx/web",
        "description": "微信公众号Web面板",
    },
    "手机购物订单": {
        "vm_index": 5,
        "needs_ss": True,
        "ports": {"input": 8084},
        "description": "ADB UI自动化采集淘宝订单",
    },
    "ORS6-VAM抖音同步": {
        "vm_index": 5,
        "needs_ss": False,
        "browser_url": "https://www.douyin.com",
        "description": "抖音视频同步+节拍检测",
    },
    "agent-phone-control": {
        "vm_index": 5,
        "needs_ss": True,
        "ports": {"input": 8084},
        "description": "Agent远程操控手机",
    },
}

# 端口映射方案: vm_index → {本机端口: 模拟器内端口}
PORT_MAP = {
    0: {},  # 主控暂无固定映射
    3: {18080: 8080, 18084: 8084, 18081: 8081, 18083: 8083},
    4: {28080: 8080, 28084: 8084},
    5: {38080: 8080, 38084: 8084},
}


# ═══════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════

def run(cmd, timeout=30):
    """运行命令，返回(returncode, stdout)"""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           encoding='utf-8', errors='replace')
        return r.returncode, r.stdout.strip()
    except subprocess.TimeoutExpired:
        return -1, "TIMEOUT"
    except Exception as e:
        return -1, str(e)

def dnc(*args):
    """调用dnconsole"""
    return run([DNCONSOLE] + list(args))

def adb_cmd(serial, *args):
    """调用adb"""
    return run([ADB, "-s", serial] + list(args))

def adb_shell(serial, cmd):
    """adb shell"""
    return adb_cmd(serial, "shell", cmd)

def http_get(url, timeout=5):
    """简单HTTP GET"""
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode('utf-8', errors='replace')
    except urllib.error.HTTPError as e:
        return e.code, str(e)
    except Exception as e:
        return 0, str(e)


# ═══════════════════════════════════════════════════════════════
# 核心功能
# ═══════════════════════════════════════════════════════════════

def get_vm_list():
    """获取所有VM列表"""
    code, out = dnc("list2")
    if code != 0:
        return []
    vms = []
    for line in out.strip().split('\n'):
        parts = line.strip().split(',')
        if len(parts) >= 10:
            vms.append({
                "index": int(parts[0]),
                "name": parts[1],
                "top_hwnd": parts[2],
                "bind_hwnd": parts[3],
                "running": parts[4] == '1',
                "pid": int(parts[5]) if parts[5] != '-1' else -1,
                "vbox_pid": int(parts[6]) if parts[6] != '-1' else -1,
                "width": int(parts[7]),
                "height": int(parts[8]),
                "dpi": int(parts[9]),
            })
    return vms

def get_running_list():
    """获取运行中的VM名称列表"""
    code, out = dnc("runninglist")
    if code != 0:
        return []
    return [n.strip() for n in out.strip().split('\n') if n.strip()]

def get_adb_devices():
    """获取ADB设备列表"""
    code, out = run([ADB, "devices"])
    if code != 0:
        return {}
    devices = {}
    for line in out.strip().split('\n')[1:]:
        parts = line.strip().split('\t')
        if len(parts) == 2 and parts[1] == 'device':
            devices[parts[0]] = 'device'
    return devices

def get_vm_config(index):
    """读取VM配置文件"""
    cfg_path = os.path.join(LDPLAYER_DIR, "vms", "config", f"leidian{index}.config")
    if not os.path.exists(cfg_path):
        return {}
    try:
        with open(cfg_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def get_vm_adb_serial(index):
    """根据VM index推算ADB serial"""
    # LDPlayer ADB端口规则: 5554 + index*2 (但实际可能不同)
    # 通过dnconsole adb获取更准确
    base_ports = {0: 5554, 3: 5560, 4: 5562, 5: 5564}
    port = base_ports.get(index)
    if port:
        return f"emulator-{port}"
    return None

def get_vm_detail(vm, config):
    """获取VM详细信息"""
    detail = {
        **vm,
        "model": config.get("propertySettings.phoneModel", "?"),
        "manufacturer": config.get("propertySettings.phoneManufacturer", "?"),
        "root": config.get("basicSettings.rootMode", False),
        "cpu": config.get("advancedSettings.cpuCount", "?"),
        "memory": config.get("advancedSettings.memorySize", "?"),
        "adb_debug": config.get("basicSettings.adbDebug", 0),
    }
    res = config.get("advancedSettings.resolution", {})
    if res:
        detail["res_w"] = res.get("width", vm["width"])
        detail["res_h"] = res.get("height", vm["height"])
    return detail

def get_emulator_packages(serial):
    """获取模拟器内已安装的第三方应用"""
    code, out = adb_shell(serial, "pm list packages -3 2>/dev/null")
    if code != 0:
        return []
    return [l.replace("package:", "").strip() for l in out.split('\n') if l.startswith("package:")]

def get_emulator_ss_status(serial):
    """检查ScreenStream状态"""
    # 先检查SS是否在运行
    code, out = adb_shell(serial, "dumpsys activity services info.dvkr.screenstream.dev 2>/dev/null | head -5")
    ss_running = "ServiceRecord" in out if code == 0 else False
    
    # 检查端口
    code, out = adb_shell(serial, "netstat -tlnp 2>/dev/null | grep -E '8080|8084'")
    ports = []
    if code == 0:
        for line in out.split('\n'):
            if '8080' in line and 'LISTEN' in line:
                ports.append(8080)
            if '8084' in line and 'LISTEN' in line:
                ports.append(8084)
    
    return {"running": ss_running, "ports": ports}


# ═══════════════════════════════════════════════════════════════
# 命令: 状态
# ═══════════════════════════════════════════════════════════════

def cmd_status(detailed=False):
    """显示全景状态"""
    print("=" * 70)
    print("  雷电模拟器统一管理中枢 · 全景状态")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    # 主机信息
    print(f"\n📍 安装路径: {LDPLAYER_DIR}")
    print(f"📍 ADB路径:  {ADB}")
    
    # VM列表
    vms = get_vm_list()
    running = get_running_list()
    devices = get_adb_devices()
    
    print(f"\n{'─' * 70}")
    print(f"  虚拟机列表 ({len(vms)} 台, {len(running)} 运行中)")
    print(f"{'─' * 70}")
    
    for vm in vms:
        idx = vm["index"]
        config = get_vm_config(idx)
        detail = get_vm_detail(vm, config)
        
        status = "🟢运行" if vm["running"] else "⚪停止"
        plan = VM_PLAN.get(idx, (None, "未规划", []))
        
        serial = get_vm_adb_serial(idx)
        adb_ok = serial in devices if serial else False
        
        print(f"\n  [{idx}] {vm['name']}  {status}")
        print(f"      型号: {detail['model']} ({detail['manufacturer']})")
        print(f"      分辨率: {detail.get('res_w', vm['width'])}×{detail.get('res_h', vm['height'])}@{vm['dpi']}dpi")
        print(f"      CPU: {detail['cpu']}核 | RAM: {detail['memory']}MB | Root: {'✅' if detail['root'] else '❌'}")
        print(f"      ADB: {serial or 'N/A'} {'✅' if adb_ok else '❌'}")
        print(f"      规划: {plan[1]} → {', '.join(plan[2]) if plan[2] else 'N/A'}")
        
        if detailed and vm["running"] and adb_ok:
            # 已安装的第三方应用
            pkgs = get_emulator_packages(serial)
            if pkgs:
                print(f"      应用({len(pkgs)}): {', '.join(pkgs[:5])}{'...' if len(pkgs)>5 else ''}")
            
            # ScreenStream状态
            ss = get_emulator_ss_status(serial)
            ss_icon = "🟢" if ss["running"] else "🔴"
            print(f"      SS: {ss_icon} 端口: {ss['ports'] or 'none'}")
    
    # 项目映射
    print(f"\n{'─' * 70}")
    print(f"  项目 → 虚拟机映射 ({len(PROJECT_CONFIG)} 个项目)")
    print(f"{'─' * 70}")
    
    for proj, cfg in PROJECT_CONFIG.items():
        vm_idx = cfg["vm_index"]
        vm_name = VM_PLAN.get(vm_idx, (None, "?"))[0]
        ss_icon = "📡" if cfg.get("needs_ss") else "🌐"
        print(f"  {ss_icon} {proj:20s} → VM[{vm_idx}] {vm_name}")
    
    # 端口映射
    print(f"\n{'─' * 70}")
    print(f"  端口映射方案")
    print(f"{'─' * 70}")
    for idx, ports in PORT_MAP.items():
        if ports:
            vm_name = VM_PLAN.get(idx, (f"VM{idx}", "?"))[0]
            for local, remote in ports.items():
                print(f"  VM[{idx}] {vm_name}: localhost:{local} → emulator:{remote}")
    
    # 八卦辩证
    print(f"\n{'─' * 70}")
    print(f"  伏羲八卦 · 问题检测")
    print(f"{'─' * 70}")
    problems = detect_problems(vms, devices)
    for p in problems:
        print(f"  {p}")
    
    if not problems:
        print("  ✅ 涅槃 · 无问题")
    
    return vms, devices


def detect_problems(vms, devices):
    """八卦辩证: 检测所有问题"""
    problems = []
    
    for vm in vms:
        idx = vm["index"]
        config = get_vm_config(idx)
        
        # ☰乾: 认知卸载 — VM名称是否有意义
        if idx in (1, 2) and vm["name"] not in VM_PLAN:
            pass  # 归档VM不报问题
        
        # ☷坤: 信息熵减 — 配置是否合理
        cpu = config.get("advancedSettings.cpuCount", 1)
        mem = config.get("advancedSettings.memorySize", 1536)
        if vm["running"] and idx in VM_PLAN:
            if cpu < 2:
                problems.append(f"☷坤 VM[{idx}] {vm['name']}: CPU={cpu}核过低，建议≥2核")
            if mem < 2048:
                problems.append(f"☷坤 VM[{idx}] {vm['name']}: RAM={mem}MB过低，建议≥2048MB")
        
        # ☵坎: 上善若水 — ADB连通性
        if vm["running"] and idx in VM_PLAN:
            serial = get_vm_adb_serial(idx)
            if serial and serial not in devices:
                problems.append(f"☵坎 VM[{idx}] {vm['name']}: ADB {serial} 不可达")
        
        # ☲离: 结构先于行动 — 分辨率
        res = config.get("advancedSettings.resolution", {})
        w = res.get("width", vm["width"])
        h = res.get("height", vm["height"])
        if vm["running"] and idx in VM_PLAN and w < 720:
            problems.append(f"☲离 VM[{idx}] {vm['name']}: 分辨率{w}×{h}过低，投屏测试建议≥720p")
        
        # ☳震: 一次推到底 — ScreenStream是否运行
        if vm["running"] and idx in VM_PLAN:
            serial = get_vm_adb_serial(idx)
            if serial and serial in devices:
                pkgs = get_emulator_packages(serial)
                plan_projs = VM_PLAN.get(idx, (None, None, []))[2]
                needs_ss = any(PROJECT_CONFIG.get(p, {}).get("needs_ss") for p in plan_projs
                              if p in PROJECT_CONFIG)
                if needs_ss and "info.dvkr.screenstream.dev" not in pkgs:
                    problems.append(f"☳震 VM[{idx}] {vm['name']}: 需要ScreenStream但未安装")
        
        # ☶艮: 知止 — Root状态
        root = config.get("basicSettings.rootMode", False)
        if idx == 3 and not root:
            problems.append(f"☶艮 VM[{idx}] {vm['name']}: 投屏主控应启用Root")
    
    # ☴巽: 渐进渗透 — 全局检查
    emulator_count = sum(1 for vm in vms if vm["running"])
    if emulator_count > 4:
        problems.append(f"☴巽 运行{emulator_count}台VM，建议≤4台以节省资源")
    
    # ☱兑: 集群涌现 — 端口冲突检测
    all_local_ports = []
    for idx, ports in PORT_MAP.items():
        for lp in ports.keys():
            if lp in all_local_ports:
                problems.append(f"☱兑 本机端口{lp}冲突!")
            all_local_ports.append(lp)
    
    return problems


# ═══════════════════════════════════════════════════════════════
# 命令: Setup (初始化配置)
# ═══════════════════════════════════════════════════════════════

def cmd_setup():
    """初始化: 重命名VM + 升级配置"""
    print("🔧 初始化雷电模拟器虚拟机配置...\n")
    
    vms = get_vm_list()
    running_names = get_running_list()
    
    for idx, (target_name, role, projects) in VM_PLAN.items():
        vm = next((v for v in vms if v["index"] == idx), None)
        if not vm:
            print(f"  ⚠️  VM[{idx}] 不存在，跳过")
            continue
        
        current_name = vm["name"]
        is_running = current_name in running_names
        
        print(f"  📋 VM[{idx}] '{current_name}' → '{target_name}' ({role})")
        
        # 重命名 (需要先停止)
        if current_name != target_name:
            if is_running:
                print(f"     ⚠️  VM运行中，重命名需先停止。跳过重命名。")
                print(f"     💡 手动: dnconsole quit --index {idx}")
                print(f"            dnconsole rename --index {idx} --title \"{target_name}\"")
            else:
                code, out = dnc("rename", "--index", str(idx), "--title", target_name)
                print(f"     {'✅' if code == 0 else '❌'} 重命名: {out}")
        
        # 升级配置 (CPU/RAM) — 也需要停止
        config = get_vm_config(idx)
        cpu = config.get("advancedSettings.cpuCount", 1)
        mem = config.get("advancedSettings.memorySize", 1536)
        
        target_cpu = 2
        target_mem = 2048
        if idx == 0:
            target_cpu = 4
            target_mem = 4096
        
        needs_modify = cpu < target_cpu or mem < target_mem
        if needs_modify:
            if is_running:
                print(f"     ⚠️  配置升级需停止VM: CPU {cpu}→{target_cpu}, RAM {mem}→{target_mem}")
                print(f"     💡 手动: dnconsole quit --index {idx}")
                print(f"            dnconsole modify --index {idx} --cpu {target_cpu} --memory {target_mem}")
            else:
                code, out = dnc("modify", "--index", str(idx),
                               "--cpu", str(target_cpu), "--memory", str(target_mem))
                print(f"     {'✅' if code == 0 else '❌'} 配置: CPU→{target_cpu}, RAM→{target_mem}: {out}")
    
    print("\n✅ Setup完成")


# ═══════════════════════════════════════════════════════════════
# 命令: 端口映射
# ═══════════════════════════════════════════════════════════════

def cmd_ports(action="show"):
    """管理端口映射"""
    devices = get_adb_devices()
    
    print("🔌 端口映射管理\n")
    
    for idx, ports in PORT_MAP.items():
        if not ports:
            continue
        serial = get_vm_adb_serial(idx)
        vm_name = VM_PLAN.get(idx, (f"VM{idx}",))[0]
        
        if serial not in devices:
            print(f"  VM[{idx}] {vm_name}: ❌ ADB不可达 ({serial})")
            continue
        
        print(f"  VM[{idx}] {vm_name} ({serial}):")
        
        for local_port, remote_port in ports.items():
            if action == "setup":
                # adb forward
                code, out = adb_cmd(serial, "forward", f"tcp:{local_port}", f"tcp:{remote_port}")
                status = "✅" if code == 0 else "❌"
                print(f"    {status} forward tcp:{local_port} → tcp:{remote_port}")
            else:
                # 检查是否可达
                try:
                    status_code, _ = http_get(f"http://127.0.0.1:{local_port}/", timeout=2)
                    reachable = status_code > 0
                except:
                    reachable = False
                icon = "🟢" if reachable else "⚪"
                print(f"    {icon} localhost:{local_port} → emulator:{remote_port}")
        print()


# ═══════════════════════════════════════════════════════════════
# 命令: ScreenStream管理
# ═══════════════════════════════════════════════════════════════

def cmd_install_ss():
    """安装ScreenStream到需要的VM"""
    print("📦 安装ScreenStream...\n")
    
    # 寻找APK
    apk_candidates = [
        os.path.join(WORKSPACE, "构建部署", "app-dev-debug.apk"),
        os.path.join(WORKSPACE, "build", "outputs", "apk", "dev", "debug", "app-dev-debug.apk"),
    ]
    
    # 搜索构建目录
    for root_dir in [os.path.join(WORKSPACE, "app"), os.path.join(WORKSPACE, "build")]:
        if os.path.isdir(root_dir):
            for dirpath, dirnames, filenames in os.walk(root_dir):
                for f in filenames:
                    if f.endswith('.apk'):
                        apk_candidates.append(os.path.join(dirpath, f))
    
    apk_path = None
    for c in apk_candidates:
        if os.path.exists(c):
            apk_path = c
            break
    
    if not apk_path:
        print("  ❌ 未找到ScreenStream APK")
        print("  💡 请先构建: ./gradlew :app:assembleDevDebug")
        print("  💡 或指定APK路径")
        return
    
    print(f"  📦 APK: {apk_path}")
    
    devices = get_adb_devices()
    for idx in [3, 4, 5]:
        serial = get_vm_adb_serial(idx)
        if serial not in devices:
            print(f"  VM[{idx}]: ❌ 不在线")
            continue
        
        # 检查是否已安装
        pkgs = get_emulator_packages(serial)
        if "info.dvkr.screenstream.dev" in pkgs:
            print(f"  VM[{idx}]: ✅ 已安装")
            continue
        
        # 安装
        code, out = adb_cmd(serial, "install", "-r", "-t", apk_path)
        print(f"  VM[{idx}]: {'✅' if code == 0 else '❌'} {out[:80]}")


def cmd_start_ss(index):
    """启动指定VM的ScreenStream"""
    serial = get_vm_adb_serial(index)
    if not serial:
        print(f"❌ VM[{index}] 无ADB映射")
        return
    
    print(f"🚀 启动 VM[{index}] ScreenStream...")
    
    # 启动SS Activity
    code, out = adb_shell(serial,
        "am start -n info.dvkr.screenstream.dev/info.dvkr.screenstream.ui.activity.AppActivity")
    print(f"  Activity: {'✅' if code == 0 else '❌'}")
    
    time.sleep(2)
    
    # 检查状态
    ss = get_emulator_ss_status(serial)
    print(f"  状态: {'🟢运行' if ss['running'] else '🔴未运行'}")
    print(f"  端口: {ss['ports'] or 'none'}")


# ═══════════════════════════════════════════════════════════════
# 命令: 项目测试
# ═══════════════════════════════════════════════════════════════

def cmd_test(project_name):
    """运行项目测试配方"""
    if project_name == "all":
        results = {}
        for name in PROJECT_CONFIG:
            results[name] = run_project_test(name)
        
        print(f"\n{'═' * 50}")
        print(f"  测试汇总: {sum(results.values())}/{len(results)} PASS")
        print(f"{'═' * 50}")
        for name, passed in results.items():
            print(f"  {'✅' if passed else '❌'} {name}")
        return
    
    if project_name not in PROJECT_CONFIG:
        print(f"❌ 未知项目: {project_name}")
        print(f"可用项目: {', '.join(PROJECT_CONFIG.keys())}")
        return
    
    run_project_test(project_name)


def run_project_test(project_name):
    """运行单个项目的测试配方"""
    cfg = PROJECT_CONFIG[project_name]
    idx = cfg["vm_index"]
    serial = get_vm_adb_serial(idx)
    
    print(f"\n{'─' * 50}")
    print(f"  🧪 测试: {project_name}")
    print(f"  📝 {cfg['description']}")
    print(f"  🖥️  VM[{idx}] ({serial})")
    print(f"{'─' * 50}")
    
    passed = True
    devices = get_adb_devices()
    
    # T1: ADB连通
    adb_ok = serial in devices if serial else False
    print(f"  T1 ADB连通: {'✅' if adb_ok else '❌'}")
    if not adb_ok:
        return False
    
    # T2: 应用安装检查
    if cfg.get("apk"):
        pkgs = get_emulator_packages(serial)
        installed = cfg["apk"] in pkgs
        print(f"  T2 {cfg['apk']}: {'✅已安装' if installed else '❌未安装'}")
        if not installed:
            passed = False
    
    # T3: ScreenStream状态
    if cfg.get("needs_ss"):
        ss = get_emulator_ss_status(serial)
        print(f"  T3 ScreenStream: {'✅' if ss['running'] else '⚠️未运行'} 端口:{ss['ports']}")
        if not ss["running"]:
            passed = False
    
    # T4: 端口映射检查
    if cfg.get("ports"):
        for name, port in cfg["ports"].items():
            code, out = adb_shell(serial, f"netstat -tlnp 2>/dev/null | grep {port}")
            listening = 'LISTEN' in out if code == 0 else False
            print(f"  T4 端口 {name}({port}): {'✅' if listening else '⚪未监听'}")
    
    # T5: API端点测试 (通过adb forward)
    if cfg.get("test_urls") and cfg.get("ports"):
        first_port = list(cfg["ports"].values())[0]
        for url in cfg["test_urls"]:
            full_url = f"http://127.0.0.1:{first_port}{url}"
            # 通过adb shell curl测试
            code, out = adb_shell(serial, f"curl -s http://127.0.0.1:{first_port}{url} 2>/dev/null | head -c 200")
            has_response = len(out) > 0 if code == 0 else False
            print(f"  T5 {url}: {'✅' if has_response else '⚪无响应'}")
    
    # T6: 浏览器URL可达性
    if cfg.get("browser_url"):
        print(f"  T6 Browser URL: {cfg['browser_url']} (需手动验证)")
    
    result = "✅ PASS" if passed else "⚠️ PARTIAL"
    print(f"\n  结果: {result}")
    return passed


# ═══════════════════════════════════════════════════════════════
# 命令: 健康检查
# ═══════════════════════════════════════════════════════════════

def cmd_health():
    """全链路健康检查"""
    print("🏥 全链路健康检查\n")
    
    checks = []
    
    # H1: LDPlayer安装
    h1 = os.path.exists(DNCONSOLE)
    checks.append(("H1 LDPlayer安装", h1))
    print(f"  {'✅' if h1 else '❌'} H1 LDPlayer安装: {LDPLAYER_DIR}")
    
    # H2: dnconsole可用
    code, out = dnc("list")
    h2 = code == 0
    checks.append(("H2 dnconsole", h2))
    print(f"  {'✅' if h2 else '❌'} H2 dnconsole命令")
    
    # H3: ADB可用
    code, out = run([ADB, "version"])
    h3 = code == 0
    checks.append(("H3 ADB", h3))
    print(f"  {'✅' if h3 else '❌'} H3 ADB: {out.split(chr(10))[0] if h3 else 'N/A'}")
    
    # H4: VM运行状态
    running = get_running_list()
    h4 = len(running) > 0
    checks.append(("H4 VM运行", h4))
    print(f"  {'✅' if h4 else '❌'} H4 运行中VM: {len(running)} ({', '.join(running)})")
    
    # H5: ADB设备
    devices = get_adb_devices()
    emulators = {k: v for k, v in devices.items() if k.startswith("emulator")}
    h5 = len(emulators) > 0
    checks.append(("H5 ADB设备", h5))
    print(f"  {'✅' if h5 else '❌'} H5 ADB模拟器设备: {len(emulators)}")
    
    # H6: ScreenStream安装
    ss_count = 0
    for idx in [3, 4, 5]:
        serial = get_vm_adb_serial(idx)
        if serial in devices:
            pkgs = get_emulator_packages(serial)
            if "info.dvkr.screenstream.dev" in pkgs:
                ss_count += 1
    h6 = ss_count > 0
    checks.append(("H6 ScreenStream", h6))
    print(f"  {'✅' if h6 else '⚠️'} H6 ScreenStream已安装: {ss_count}/3 VM")
    
    # H7: 工作区可达
    h7 = os.path.isdir(WORKSPACE)
    checks.append(("H7 工作区", h7))
    print(f"  {'✅' if h7 else '❌'} H7 工作区: {WORKSPACE}")
    
    passed = sum(1 for _, ok in checks if ok)
    total = len(checks)
    print(f"\n  结果: {passed}/{total} {'✅ HEALTHY' if passed == total else '⚠️ ISSUES'}")


# ═══════════════════════════════════════════════════════════════
# 命令: E2E验证
# ═══════════════════════════════════════════════════════════════

def cmd_e2e():
    """端到端全流程验证"""
    print("🔬 端到端验证\n")
    
    results = []
    
    # E1: 列出所有VM
    vms = get_vm_list()
    results.append(("E1 VM列表", len(vms) >= 4))
    print(f"  {'✅' if len(vms) >= 4 else '❌'} E1 VM数量: {len(vms)}")
    
    # E2: 运行中的VM
    running = get_running_list()
    results.append(("E2 运行VM", len(running) >= 3))
    print(f"  {'✅' if len(running) >= 3 else '❌'} E2 运行中: {len(running)}")
    
    # E3: ADB设备匹配
    devices = get_adb_devices()
    emulators = [k for k in devices if k.startswith("emulator")]
    results.append(("E3 ADB设备", len(emulators) >= 3))
    print(f"  {'✅' if len(emulators) >= 3 else '❌'} E3 ADB模拟器: {len(emulators)}")
    
    # E4-E6: 每个关键VM的ADB shell
    for idx, name in [(3, "SS-投屏主控"), (4, "PWA-Web测试"), (5, "采集-自动化")]:
        serial = get_vm_adb_serial(idx)
        if serial in devices:
            code, out = adb_shell(serial, "getprop ro.product.model")
            ok = code == 0 and len(out) > 0
            results.append((f"E{idx+1} VM[{idx}] ADB Shell", ok))
            print(f"  {'✅' if ok else '❌'} E{idx+1} VM[{idx}] {name}: model={out}")
        else:
            results.append((f"E{idx+1} VM[{idx}] ADB Shell", False))
            print(f"  ❌ E{idx+1} VM[{idx}] {name}: ADB不可达")
    
    # E7: ScreenStream安装检查
    ss_installed = 0
    for idx in [3, 4, 5]:
        serial = get_vm_adb_serial(idx)
        if serial in devices:
            pkgs = get_emulator_packages(serial)
            if "info.dvkr.screenstream.dev" in pkgs:
                ss_installed += 1
    results.append(("E7 SS安装", ss_installed >= 2))
    print(f"  {'✅' if ss_installed >= 2 else '⚠️'} E7 ScreenStream安装: {ss_installed}/3")
    
    # E8: 端口映射测试
    port_ok = 0
    for idx in [3, 4, 5]:
        serial = get_vm_adb_serial(idx)
        if serial in devices:
            code, out = adb_shell(serial, "netstat -tlnp 2>/dev/null | grep LISTEN | wc -l")
            if code == 0:
                try:
                    count = int(out.strip())
                    if count > 0:
                        port_ok += 1
                except:
                    pass
    results.append(("E8 端口监听", port_ok >= 2))
    print(f"  {'✅' if port_ok >= 2 else '⚠️'} E8 模拟器端口监听: {port_ok}/3")
    
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"\n  {'═' * 40}")
    print(f"  E2E结果: {passed}/{total} {'✅ PASS' if passed >= total - 1 else '⚠️ ISSUES'}")


# ═══════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="雷电模拟器统一管理中枢")
    parser.add_argument("--status", action="store_true", help="详细状态")
    parser.add_argument("--setup", action="store_true", help="初始化VM配置")
    parser.add_argument("--test", type=str, help="运行项目测试 (项目名 或 all)")
    parser.add_argument("--ports", choices=["show", "setup"], default=None, help="端口映射")
    parser.add_argument("--install-ss", action="store_true", help="安装ScreenStream")
    parser.add_argument("--start-ss", type=int, help="启动SS (VM index)")
    parser.add_argument("--health", action="store_true", help="健康检查")
    parser.add_argument("--e2e", action="store_true", help="E2E验证")
    
    args = parser.parse_args()
    
    if args.setup:
        cmd_setup()
    elif args.test:
        cmd_test(args.test)
    elif args.ports:
        cmd_ports(args.ports)
    elif args.install_ss:
        cmd_install_ss()
    elif args.start_ss is not None:
        cmd_start_ss(args.start_ss)
    elif args.health:
        cmd_health()
    elif args.e2e:
        cmd_e2e()
    elif args.status:
        cmd_status(detailed=True)
    else:
        cmd_status(detailed=False)


if __name__ == "__main__":
    main()
