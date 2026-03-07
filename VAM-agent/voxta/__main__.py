"""
Voxta Agent CLI — python -m voxta <command>

== 查看 ==
  dashboard      Voxta综合仪表板
  characters     角色列表
  char-detail    角色详情 (ID)
  modules        模块评估
  chats          最近对话
  messages       最近消息
  scenarios      场景列表
  presets        预设列表
  memories       记忆书
  stats          数据库统计
  tables         所有表及行数
  logs           Voxta日志

== 连接 ==
  signalr        测试SignalR连接
  services       Voxta服务状态

== 操作 ==
  backup         备份数据库
  start          启动服务 (voxta/edgetts/textgen/all)
  enable         启用模块 (ID)
  disable        禁用模块 (ID)
  char-create    创建角色 (名称 人格 简介)
  char-edit      编辑角色 (ID 字段 值)
  tts            合成语音 (文本)

== 聊天 ==
  chat           独立模式对话 (角色名)
  chat-voxta     Voxta连接对话 (角色名)
  list           列出角色(聊天用)
  prompt         显示system prompt (角色名)
  test-llm       测试LLM连接
  test-tts       测试TTS (文本)

== 诊断 ==
  health         健康检查
  diagnose       全链路诊断
  fix-dry        预览自动修复
  fix            执行自动修复
  json           JSON全状态输出
"""
import sys
import json

from .agent import VoxtaAgent


def _json(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


def main():
    agent = VoxtaAgent()

    commands = {
        # 查看
        'dashboard':  ('Voxta综合仪表板',    lambda: _json(agent.see_dashboard())),
        'characters': ('角色列表',            lambda: _json(agent.see_characters())),
        'char-detail':('角色详情',            lambda: cmd_char_detail(agent)),
        'modules':    ('模块评估',            lambda: _json(agent.smell_modules())),
        'chats':      ('最近对话',            lambda: _json(agent.see_chats())),
        'messages':   ('最近消息',            lambda: _json(agent.see_messages())),
        'scenarios':  ('场景列表',            lambda: _json(agent.see_scenarios())),
        'presets':    ('预设列表',            lambda: _json(agent.see_hub_presets())),
        'memories':   ('记忆书',              lambda: _json(agent.see_hub_memory_books())),
        'stats':      ('数据库统计',          lambda: _json(agent.see_stats())),
        'tables':     ('所有表及行数',        lambda: _json(agent.see_all_tables())),
        'logs':       ('Voxta日志',           lambda: _json(agent.see_log())),
        # 连接
        'signalr':    ('测试SignalR连接',     lambda: cmd_signalr()),
        'services':   ('Voxta服务状态',       lambda: _json(agent.hear_services())),
        # 操作
        'backup':     ('备份数据库',          lambda: print(agent.touch_backup())),
        'start':      ('启动服务',            lambda: cmd_start(agent)),
        'enable':     ('启用模块',            lambda: cmd_module(agent, True)),
        'disable':    ('禁用模块',            lambda: cmd_module(agent, False)),
        'char-create':('创建角色',            lambda: cmd_char_create(agent)),
        'char-edit':  ('编辑角色',            lambda: cmd_char_edit(agent)),
        'tts':        ('合成语音',            lambda: cmd_tts(agent)),
        # 聊天
        'chat':       ('独立模式对话',        lambda: cmd_chat(agent, 'standalone')),
        'chat-voxta': ('Voxta连接对话',       lambda: cmd_chat(agent, 'voxta')),
        'list':       ('列出角色(聊天用)',    lambda: cmd_list_chars()),
        'prompt':     ('显示system prompt',   lambda: cmd_prompt()),
        'test-llm':   ('测试LLM连接',        lambda: cmd_test_llm()),
        'test-tts':   ('测试TTS',             lambda: cmd_test_tts()),
        # 诊断
        'health':     ('健康检查',            lambda: _json(agent.taste_health())),
        'diagnose':   ('全链路诊断',          lambda: print(agent.smell_diagnose_text())),
        'fix-dry':    ('预览自动修复',        lambda: _json(agent.touch_auto_fix(dry_run=True))),
        'fix':        ('执行自动修复',        lambda: _json(agent.touch_auto_fix(dry_run=False))),
        'json':       ('JSON全状态输出',      lambda: _json(agent.smell_diagnose_json())),
    }

    if len(sys.argv) < 2 or sys.argv[1] in ('-h', '--help', 'help'):
        print("Voxta Agent CLI v2.0 — python -m voxta <command>\n")
        section = None
        sections = {
            'dashboard': '查看', 'signalr': '连接', 'backup': '操作',
            'chat': '聊天', 'health': '诊断',
        }
        for cmd, (desc, _) in commands.items():
            if cmd in sections:
                if section:
                    print()
                section = sections[cmd]
                print(f"  [{section}]")
            print(f"    {cmd:14s}  {desc}")
        return

    cmd = sys.argv[1]
    if cmd in commands:
        commands[cmd][1]()
    else:
        print(f"未知命令: {cmd}")
        print(f"可用命令: {', '.join(commands.keys())}")


# ── 子命令实现 ──

def cmd_signalr():
    from .signalr import check_signalr
    _json(check_signalr())


def cmd_start(agent):
    key = sys.argv[2] if len(sys.argv) > 2 else 'all'
    if key == 'all':
        results = agent.touch_start_all()
        _json(results)
    else:
        ok, msg = agent.touch_start_service(key)
        print(f"{'OK' if ok else 'FAIL'}: {msg}")


def cmd_module(agent, enabled):
    if len(sys.argv) < 3:
        print(f"用法: python -m voxta {'enable' if enabled else 'disable'} <module_id>")
        return
    ok = agent.touch_set_module(sys.argv[2], enabled)
    print(f"{'启用' if enabled else '禁用'}: {'OK' if ok else 'FAIL'}")


def cmd_char_detail(agent):
    if len(sys.argv) < 3:
        print("用法: python -m voxta char-detail <id>")
        return
    detail = agent.see_character_detail(sys.argv[2])
    if detail:
        _json(detail)
    else:
        print(f"角色未找到: {sys.argv[2]}")


def cmd_char_create(agent):
    if len(sys.argv) < 5:
        print("用法: python -m voxta char-create <名称> <人格> <简介>")
        print("例: python -m voxta char-create 小月 温柔体贴 一个善良的AI助手")
        return
    name, personality, profile = sys.argv[2], sys.argv[3], sys.argv[4]
    local_id = agent.touch_create_character(name, profile, personality)
    print(f"创建成功: {name} [{local_id}]")


def cmd_char_edit(agent):
    if len(sys.argv) < 5:
        print("用法: python -m voxta char-edit <id> <字段> <值>")
        print("字段: Name, Personality, Profile, Description, Culture, FirstMessage")
        return
    char_id, field, value = sys.argv[2], sys.argv[3], sys.argv[4]
    ok = agent.touch_update_character(char_id, field, value)
    print(f"更新 {field}: {'OK' if ok else 'FAIL'}")


def cmd_tts(agent):
    if len(sys.argv) < 3:
        print("用法: python -m voxta tts <文本> [voice]")
        return
    text = sys.argv[2]
    voice = sys.argv[3] if len(sys.argv) > 3 else 'zh-CN-XiaoxiaoNeural'
    ok, result = agent.touch_tts(text, voice)
    print(f"TTS: {'OK' if ok else 'FAIL'} — {result}")


def cmd_chat(agent, mode):
    if len(sys.argv) < 3:
        print(f"用法: python -m voxta {'chat' if mode == 'standalone' else 'chat-voxta'} <角色名>")
        return
    from .chat import ChatEngine
    engine = ChatEngine(mode=mode)
    char = engine.load_character(sys.argv[2])
    if not char:
        print(f"角色未找到: {sys.argv[2]}")
        return
    engine.interactive()


def cmd_list_chars():
    from .chat import CharacterLoader
    loader = CharacterLoader()
    for c in loader.list_all():
        print(f"  {c.get('Name', ''):14s} [{c.get('Culture', '')}] "
              f"{(c.get('Description', '') or '')[:40]}")


def cmd_prompt():
    if len(sys.argv) < 3:
        print("用法: python -m voxta prompt <角色名>")
        return
    from .chat import CharacterLoader, PromptBuilder
    loader = CharacterLoader()
    char = loader.load(sys.argv[2])
    if char:
        prompt = PromptBuilder.build_system_prompt(char, memories=char.get('memories', []))
        print(f"=== System Prompt for {char['name']} ===")
        print(prompt)
        print(f"\n=== Length: {len(prompt)} chars ===")
    else:
        print(f"角色未找到: {sys.argv[2]}")


def cmd_test_llm():
    from .chat import LLMClient
    llm = LLMClient()
    result = llm.chat_local([{"role": "user", "content": "Hello, respond in one word."}])
    if result.get('error'):
        print(f"本地LLM: FAIL ({result['error']})")
    else:
        print(f"本地LLM: OK — {result.get('text', '')[:60]}")


def cmd_test_tts():
    if len(sys.argv) < 3:
        print("用法: python -m voxta test-tts <文本>")
        return
    from .chat import TTSClient
    tts = TTSClient()
    text = ' '.join(sys.argv[2:])
    result = tts.speak(text)
    print(f"TTS: {'OK' if result.get('ok') else 'FAIL'} — {result}")


if __name__ == '__main__':
    main()
