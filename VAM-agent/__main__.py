"""
VAM-agent 统一CLI入口 — MasterAgent 全域控制

用法:
    python -m VAM-agent status        # 快速状态
    python -m VAM-agent discover      # 自动发现所有可操作空间
    python -m VAM-agent capabilities  # 能力矩阵
    python -m VAM-agent health        # 全域健康检查
    python -m VAM-agent startup       # 一键全栈启动
    python -m VAM-agent scene         # 一键场景搭建
    python -m VAM-agent chat <角色> <消息>  # 一键对话
    python -m VAM-agent fix           # 自动修复(dry-run)
    python -m VAM-agent fix --apply   # 自动修复(执行)
    python -m VAM-agent report        # 综合报告
"""
import sys
import json


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return

    cmd = args[0].lower()

    from master import MasterAgent
    m = MasterAgent()

    if cmd == "status":
        print(m.quick_report())

    elif cmd == "discover":
        state = m.discover()
        # Summary output
        ch = state.get("channels", {})
        online = sum(1 for c in ch.values() if c.get("online", False))
        print(f"通道: {online}/{len(ch)} 在线")
        for name, info in ch.items():
            icon = "ON" if info.get("online") else "--"
            print(f"  [{icon}] {name}")

        vam = state.get("vam", {})
        print(f"\nVaM:")
        print(f"  场景: {len(vam.get('scenes', []))}个")
        print(f"  脚本: {len(vam.get('scripts', []))}个")
        print(f"  Bridge: {'在线' if vam.get('runtime', {}).get('alive') else '离线'}")

        voxta = state.get("voxta", {})
        print(f"\nVoxta:")
        print(f"  角色: {len(voxta.get('characters', []))}个")
        print(f"  模块: {len(voxta.get('modules', {}).get('enabled_by_category', {}))}类")

        caps = state.get("capabilities", {})
        summary = caps.get("_summary", {})
        print(f"\n能力: {summary.get('coverage', '?')} 可用")
        print(f"非侵入: {summary.get('non_invasive_rate', '?')}")

    elif cmd == "capabilities":
        caps = m.capabilities()
        for name, info in caps.items():
            if name.startswith("_"):
                continue
            avail = "YES" if info.get("available") else "NO"
            invasive = " [侵入]" if info.get("invasive") else ""
            channel = info.get("channel", "?")
            print(f"\n[{avail}] {name} ({channel}){invasive}")
            for op in info.get("ops", []):
                print(f"    - {op}")
        summary = caps.get("_summary", {})
        print(f"\n总计: {summary.get('coverage', '?')} 可用 | "
              f"非侵入: {summary.get('non_invasive_rate', '?')}")

    elif cmd == "health":
        report = m.full_health()
        print(f"全域健康评分: {report.get('total_health_score', 0)}/100")
        print(f"  VaM: {report.get('vam_health', {}).get('health_score', '?')}/100")
        print(f"  Voxta: {report.get('voxta_health', {}).get('health_score', '?')}/100")

        ch = report.get("channels", {})
        online = sum(1 for c in ch.values() if c.get("online", False))
        print(f"  通道: {online}/{len(ch)} 在线")

        issues = report.get("issues", [])
        if issues:
            print(f"\n问题 ({len(issues)}):")
            for i in issues:
                print(f"  [{i['level']}] {i['component']}: {i['msg']}")

        fixes = report.get("auto_fix_available", [])
        if fixes:
            print(f"\n可自动修复 ({len(fixes)}):")
            for f in fixes:
                print(f"  - {f.get('action', '?')}: {f.get('name', f.get('module', '?'))}")

    elif cmd == "startup":
        include_tg = "--textgen" in args
        result = m.workflow_startup(include_textgen=include_tg)
        for step in result.get("steps", []):
            icon = "OK" if step.get("ok", True) else "FAIL"
            print(f"  [{icon}] {step.get('step', '?')}")
        summary = result.get("summary", {})
        print(f"\n{summary.get('channels_online', '?')} 通道在线")

    elif cmd == "scene":
        scene_name = args[1] if len(args) > 1 else None
        char_name = args[2] if len(args) > 2 else None
        result = m.workflow_scene(scene_name=scene_name, character_name=char_name)
        for step in result.get("steps", []):
            icon = "OK" if step.get("ok", True) else "FAIL"
            print(f"  [{icon}] {step.get('step', '?')}")

    elif cmd == "chat":
        char = args[1] if len(args) > 1 else None
        msg = " ".join(args[2:]) if len(args) > 2 else None
        result = m.workflow_chat(character_name=char, message=msg)
        if "error" in result:
            print(f"Error: {result['error']}")
        else:
            for step in result.get("steps", []):
                reply = step.get("reply", {})
                if reply.get("text"):
                    print(f"[{reply.get('character', '?')}] {reply['text']}")
                elif step.get("usage"):
                    print(f"Ready: {step['usage']}")
                else:
                    print(f"  {step.get('step', '?')}: {step}")

    elif cmd == "fix":
        dry_run = "--apply" not in args
        result = m.auto_fix(dry_run=dry_run)
        mode = "预览" if dry_run else "执行"
        print(f"自动修复 ({mode}):")
        fixes = result.get("fixes", [])
        if fixes:
            for f in fixes:
                print(f"  - {f.get('action', '?')}: {f.get('name', f.get('module', '?'))}")
        else:
            print("  无需修复")
        if dry_run and fixes:
            print(f"\n运行 'python -m VAM-agent fix --apply' 执行修复")

    elif cmd == "report":
        print(m.quick_report())
        print()
        print(m.voxta.quick_report())

    elif cmd == "json":
        subcmd = args[1] if len(args) > 1 else "status"
        if subcmd == "discover":
            print(json.dumps(m.discover(), indent=2, ensure_ascii=False, default=str))
        elif subcmd == "health":
            print(json.dumps(m.full_health(), indent=2, ensure_ascii=False, default=str))
        elif subcmd == "capabilities":
            print(json.dumps(m.capabilities(), indent=2, ensure_ascii=False, default=str))
        else:
            print(json.dumps(m.status(), indent=2, ensure_ascii=False, default=str))

    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)


if __name__ == "__main__":
    main()
