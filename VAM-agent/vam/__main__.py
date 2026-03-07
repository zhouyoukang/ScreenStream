"""
VaM Agent CLI — python -m vam <command>

命令:
  health      VaM健康检查
  report      快速文本报告
  services    VaM服务状态
  scenes      场景列表
  scripts     脚本列表
  plugins     插件概览
  errors      日志错误检测
  disk        磁盘空间
  paths       关键路径检查
  dashboard   VaM综合仪表盘
  scan        完整资源扫描

Voxta相关命令请使用: python -m voxta
"""
import sys
import json

from .agent import VaMAgent


def _json(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


def main():
    agent = VaMAgent()

    commands = {
        'health':    ('VaM健康检查',        lambda: _json(agent.taste_health())),
        'report':    ('快速文本报告',        lambda: print(agent.quick_report())),
        'services':  ('VaM服务状态',        lambda: _json(agent.hear_services())),
        'scenes':    ('场景列表',            lambda: _json(agent.see_scenes())),
        'scripts':   ('脚本列表',            lambda: _json(agent.see_scripts())),
        'plugins':   ('插件概览',            lambda: _json(agent.see_plugins())),
        'errors':    ('日志错误检测',        lambda: _json(agent.smell_errors())),
        'disk':      ('磁盘空间',            lambda: _json(agent.smell_disk())),
        'paths':     ('关键路径检查',        lambda: _json(agent.see_critical_paths())),
        'dashboard': ('VaM综合仪表盘',      lambda: _json(agent.dashboard())),
        'scan':      ('完整资源扫描',        lambda: _json(agent.taste_full_scan())),
    }

    if len(sys.argv) < 2 or sys.argv[1] in ('-h', '--help', 'help'):
        print("VAM Agent CLI — python -m vam <command>\n")
        for cmd, (desc, _) in commands.items():
            print(f"  {cmd:12s}  {desc}")
        return

    cmd = sys.argv[1]
    if cmd in commands:
        commands[cmd][1]()
    else:
        print(f"未知命令: {cmd}")
        print(f"VaM可用命令: {', '.join(commands.keys())}")
        print("Voxta命令请用: python -m voxta")


if __name__ == '__main__':
    main()
