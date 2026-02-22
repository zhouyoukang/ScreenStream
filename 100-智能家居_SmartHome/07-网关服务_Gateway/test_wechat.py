#!/usr/bin/env python3
"""
微信公众号模块离线单元测试 — 不需要微信服务器，不需要运行中的 Gateway

用法:
  python test_wechat.py

在线测试请使用:
  python test_wx_live.py           # 本地 Gateway 在线测试
  python test_wx_public.py <URL>   # 公网 URL 端到端测试
"""

import time
import hashlib

# ============================================================
# 1. 单元测试: 签名验证
# ============================================================
print("\n=== 1. 签名验证测试 ===")

from wechat_handler import verify_signature, parse_xml, text_reply

TOKEN = "test_token_123"
timestamp = str(int(time.time()))
nonce = "abc123"

# 正确签名
tmp = sorted([TOKEN, timestamp, nonce])
correct_sig = hashlib.sha1("".join(tmp).encode()).hexdigest()

assert verify_signature(TOKEN, correct_sig, timestamp, nonce), "正确签名应通过"
assert not verify_signature(TOKEN, "wrong_signature", timestamp, nonce), "错误签名应失败"
assert not verify_signature("wrong_token", correct_sig, timestamp, nonce), "错误Token应失败"
print("  [PASS] 签名验证: 正确签名通过, 错误签名拒绝")

# ============================================================
# 2. XML 解析测试
# ============================================================
print("\n=== 2. XML 解析测试 ===")

text_xml = """<xml>
<ToUserName><![CDATA[gh_test]]></ToUserName>
<FromUserName><![CDATA[user123]]></FromUserName>
<CreateTime>1348831860</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[打开灯带]]></Content>
<MsgId>1234567890123456</MsgId>
</xml>""".encode("utf-8")

msg = parse_xml(text_xml)
assert msg["MsgType"] == "text", f"Expected text, got {msg['MsgType']}"
assert msg["Content"] == "打开灯带", f"Expected '打开灯带', got {msg['Content']}"
assert msg["FromUserName"] == "user123"
print(f"  [PASS] 文本消息解析: MsgType={msg['MsgType']}, Content={msg['Content']}")

voice_xml = """<xml>
<ToUserName><![CDATA[gh_test]]></ToUserName>
<FromUserName><![CDATA[user123]]></FromUserName>
<CreateTime>1348831860</CreateTime>
<MsgType><![CDATA[voice]]></MsgType>
<Recognition><![CDATA[关闭风扇。]]></Recognition>
<MsgId>1234567890123456</MsgId>
</xml>""".encode("utf-8")

msg2 = parse_xml(voice_xml)
assert msg2["MsgType"] == "voice"
assert msg2["Recognition"] == "关闭风扇。"
print(f"  [PASS] 语音消息解析: Recognition={msg2['Recognition']}")

event_xml = """<xml>
<ToUserName><![CDATA[gh_test]]></ToUserName>
<FromUserName><![CDATA[user123]]></FromUserName>
<CreateTime>1348831860</CreateTime>
<MsgType><![CDATA[event]]></MsgType>
<Event><![CDATA[subscribe]]></Event>
</xml>""".encode("utf-8")

msg3 = parse_xml(event_xml)
assert msg3["MsgType"] == "event"
assert msg3["Event"] == "subscribe"
print(f"  [PASS] 事件消息解析: Event={msg3['Event']}")

# ============================================================
# 3. XML 回复生成测试
# ============================================================
print("\n=== 3. 回复生成测试 ===")

reply = text_reply("user123", "gh_test", "灯带已打开")
assert "<ToUserName><![CDATA[user123]]>" in reply
assert "<Content><![CDATA[灯带已打开]]>" in reply
assert "<MsgType><![CDATA[text]]>" in reply
print("  [PASS] 文本回复XML生成正确")

# ============================================================
# 4. 命令路由测试 (离线, 无需Gateway)
# ============================================================
print("\n=== 4. 命令路由测试 ===")

from wechat_handler import WeChatCommandRouter, DEVICE_ALIASES, SCENE_ALIASES

router = WeChatCommandRouter({
    "micloud": None,
    "ewelink": None,
    "mina": None,
    "scene_macros": {
        "home": {"name": "回家模式", "commands": ["打开灯带"]},
        "sleep": {"name": "睡眠模式", "commands": ["关闭所有灯"]},
    },
    "find_speaker": lambda: None,
})

import asyncio

async def test_commands():
    # 帮助
    r = await router.handle_text("帮助")
    assert "命令列表" in r, f"帮助应包含'命令列表': {r[:50]}"
    print(f"  [PASS] 帮助命令: 返回 {len(r)} 字符")

    # 设备状态(无后端)
    r = await router.handle_text("状态")
    assert "设备状态" in r or "暂无" in r
    print(f"  [PASS] 状态查询: {r[:50]}")

    # 场景宏(无音箱)
    r = await router.handle_text("回家模式")
    assert "不可用" in r or "没有" in r
    print(f"  [PASS] 场景宏(无音箱): {r[:50]}")

    # 设备控制(无后端)
    r = await router.handle_text("打开灯带")
    assert "未找到" in r or "不可用" in r
    print(f"  [PASS] 设备控制(无后端): {r[:50]}")

    # 全部关闭(无后端)
    r = await router.handle_text("全部关闭")
    assert "不可用" in r
    print(f"  [PASS] 快捷操作(无后端): {r[:50]}")

    # TTS(无音箱)
    r = await router.handle_text("说 你好世界")
    assert "不可用" in r or "没有" in r
    print(f"  [PASS] TTS(无音箱): {r[:50]}")

    # 关注事件
    r = await router.handle_event("subscribe")
    assert "欢迎" in r
    print(f"  [PASS] 关注事件: {r[:50]}")

asyncio.run(test_commands())

# ============================================================
# 5. 别名覆盖率检查
# ============================================================
print("\n=== 5. 别名覆盖率 ===")
print(f"  设备别名: {len(DEVICE_ALIASES)} 个")
print(f"  场景别名: {len(SCENE_ALIASES)} 个")

# ============================================================
# Summary
# ============================================================
print("\n" + "=" * 50)
print("  微信公众号模块离线测试完成!")
print("  在线测试: python test_wx_live.py")
print("=" * 50)
