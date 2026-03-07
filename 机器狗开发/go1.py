#!/usr/bin/env python3
"""
Go1 统一CLI入口 — 一个命令控制所有模块

用法:
  python go1.py sim [args]        MuJoCo仿真 (go1_sim.py)
  python go1.py brain [args]      AI大脑 (go1_brain.py)
  python go1.py rl [args]         RL训练/推理 (go1_rl.py)
  python go1.py control [args]    真机MQTT控制 (go1_control.py)
  python go1.py test [args]       全功能诊断 (go1_test.py)
  python go1.py status            系统总览 (所有模块状态)

示例:
  python go1.py sim --gui trot             # GUI仿真小跑
  python go1.py brain -b patrol -d 30      # AI巡逻30秒
  python go1.py brain --api -d 300         # 启动HTTP API
  python go1.py rl --test                  # RL全链路测试
  python go1.py rl --train --steps 100K    # 训练PPO策略
  python go1.py control -i                 # 真机交互控制
  python go1.py test --skip-motor          # 诊断(跳过电机)
  python go1.py status                     # 系统总览
"""

import sys
import os
import json
import importlib
import subprocess
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
VERSION = "3.0"

# ── 模块映射 ──
MODULES = {
    "sim":     {"file": "go1_sim.py",     "desc": "MuJoCo仿真 (7步态+IMU+Gym+地形)"},
    "brain":   {"file": "go1_brain.py",   "desc": "AI大脑 (五感+情感+12行为+HTTP API)"},
    "rl":      {"file": "go1_rl.py",      "desc": "RL集成 (Gymnasium+PPO训练+策略推理)"},
    "control": {"file": "go1_control.py", "desc": "真机MQTT控制 (12动作+LED+交互)"},
    "test":    {"file": "go1_test.py",    "desc": "全功能诊断 (T1-T7: 网络/MQTT/电机)"},
}


def print_help():
    """打印帮助信息"""
    print(f"\n{'='*55}")
    print(f"  Go1 统一开发系统 v{VERSION}")
    print(f"  宇树Go1四足机器人 · 仿真/AI/RL/控制/诊断")
    print(f"{'='*55}\n")
    print("模块:")
    for name, info in MODULES.items():
        print(f"  {name:<10} {info['desc']}")
    print(f"  {'status':<10} 系统总览 (所有模块状态)")
    print(f"\n用法: python go1.py <模块> [参数...]")
    print(f"  例: python go1.py sim --gui trot")
    print(f"  例: python go1.py brain -b patrol -d 30")
    print(f"  例: python go1.py rl --test")
    print(f"\n每个模块的详细帮助: python go1.py <模块> --help")


def system_status():
    """系统总览 — 检查所有模块和依赖状态"""
    print(f"\n{'='*55}")
    print(f"  Go1 系统总览 v{VERSION}")
    print(f"{'='*55}\n")

    # 1. 依赖检查
    print("── 依赖状态 ──")
    deps = {
        "numpy": "核心",
        "mujoco": "仿真",
        "gymnasium": "RL",
        "stable_baselines3": "RL训练",
        "torch": "RL训练",
        "paho.mqtt.client": "真机控制",
        "cv2": "视觉",
        "serial": "RS485电机",
    }
    dep_ok, dep_fail = 0, 0
    for mod, usage in deps.items():
        try:
            importlib.import_module(mod.split(".")[0] if "." in mod else mod)
            dep_ok += 1
            print(f"  ✅ {mod:<25} ({usage})")
        except ImportError:
            dep_fail += 1
            print(f"  ❌ {mod:<25} ({usage})")
    print(f"  总计: {dep_ok} 可用 / {dep_fail} 缺失")

    # 2. 模块文件检查
    print("\n── 模块文件 ──")
    for name, info in MODULES.items():
        path = _SCRIPT_DIR / info["file"]
        if path.exists():
            size_kb = path.stat().st_size / 1024
            print(f"  ✅ {info['file']:<22} ({size_kb:.0f}KB)")
        else:
            print(f"  ❌ {info['file']:<22} 缺失!")

    # 3. MuJoCo模型检查
    print("\n── MuJoCo模型 ──")
    scene_xml = _SCRIPT_DIR / "refs" / "mujoco-menagerie" / "unitree_go1" / "scene.xml"
    go1_xml = _SCRIPT_DIR / "refs" / "mujoco-menagerie" / "unitree_go1" / "go1.xml"
    for f, desc in [(scene_xml, "scene.xml"), (go1_xml, "go1.xml")]:
        if f.exists():
            print(f"  ✅ {desc}")
        else:
            print(f"  ❌ {desc} 缺失!")

    # 4. RL预训练模型
    print("\n── RL资源 ──")
    refs_dir = _SCRIPT_DIR / "refs"
    if refs_dir.exists():
        ref_projects = [d.name for d in refs_dir.iterdir()
                       if d.is_dir() and not d.name.startswith('.')]
        print(f"  📦 {len(ref_projects)} 个参考项目")

        # 统计预训练模型
        model_count = 0
        for ext in ["*.zip", "*.pt", "*.pth", "*.onnx"]:
            model_count += len(list(refs_dir.rglob(ext)))
        print(f"  🧠 {model_count} 个预训练模型文件")
    else:
        print(f"  ❌ refs/ 目录缺失!")

    # 5. 记忆文件
    print("\n── 持久数据 ──")
    mem_file = _SCRIPT_DIR / ".go1_memory.json"
    if mem_file.exists():
        try:
            with open(mem_file, "r", encoding="utf-8") as f:
                mem = json.load(f)
            stats = mem.get("stats", {})
            places = mem.get("places", {})
            print(f"  📝 记忆: {stats.get('total_runs', 0)}次运行, "
                  f"{stats.get('total_falls', 0)}次跌倒, "
                  f"{stats.get('total_distance', 0):.1f}m行走")
            print(f"  📍 地点: {', '.join(places.keys()) if places else '无'}")
        except Exception:
            print(f"  ⚠️ 记忆文件存在但读取失败")
    else:
        print(f"  📝 无记忆文件 (首次运行brain后创建)")

    # 6. 端口分配
    print("\n── 端口分配 ──")
    ports = {
        8080: "Gateway", 8081: "MJPEG", 8082: "RTSP",
        8083: "WebRTC", 8084: "Input", 8085: "Brain API",
        8086: "Go1 UDP高层",
    }
    for port, name in ports.items():
        print(f"  :{port}  {name}")

    print(f"\n{'='*55}")

    return {"deps_ok": dep_ok, "deps_fail": dep_fail}


def run_module(module_name, args):
    """运行指定模块，透传参数"""
    info = MODULES.get(module_name)
    if not info:
        print(f"  ❌ 未知模块: {module_name}")
        print(f"  可用: {', '.join(MODULES.keys())}")
        return 1

    script = _SCRIPT_DIR / info["file"]
    if not script.exists():
        print(f"  ❌ 模块文件不存在: {script}")
        return 1

    # 透传执行
    cmd = [sys.executable, str(script)] + args
    try:
        result = subprocess.run(cmd, cwd=str(_SCRIPT_DIR))
        return result.returncode
    except KeyboardInterrupt:
        print("\n  中断")
        return 130


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print_help()
        return 0

    module = sys.argv[1].lower()
    args = sys.argv[2:]

    if module == "status":
        result = system_status()
        return 0
    elif module == "version":
        print(f"Go1 v{VERSION}")
        return 0
    elif module in MODULES:
        return run_module(module, args)
    else:
        print(f"  ❌ 未知命令: {module}")
        print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main() or 0)
