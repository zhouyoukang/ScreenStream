#!/usr/bin/env python3
"""模拟真实用户发送各种微信命令 — 全品类覆盖测试"""
import os
os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")
import httpx, time, re

client = httpx.Client(proxy=None, timeout=10)
BASE = "http://127.0.0.1:8900"

def extract(xml):
    m = re.search(r"<Content><!\[CDATA\[(.*?)\]\]></Content>", xml, re.DOTALL)
    return m.group(1) if m else xml[:200]

def send(content):
    msg = (
        "<xml><ToUserName><![CDATA[gh_test]]></ToUserName>"
        "<FromUserName><![CDATA[user1]]></FromUserName>"
        f"<CreateTime>{int(time.time())}</CreateTime>"
        "<MsgType><![CDATA[text]]></MsgType>"
        f"<Content><![CDATA[{content}]]></Content>"
        "<MsgId>1</MsgId></xml>"
    ).encode()
    r = client.post(f"{BASE}/wx", content=msg, headers={"Content-Type": "application/xml"})
    return extract(r.text)

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"

# === 全品类测试 ===
tests = [
    # 帮助类
    ("帮助", lambda r: "命令列表" in r),
    ("help", lambda r: "命令列表" in r),
    ("?", lambda r: "命令列表" in r),
    # 设备状态
    ("状态", lambda r: "设备状态" in r),
    ("设备列表", lambda r: "设备状态" in r),
    # 设备控制 — 各种设备
    ("打开灯带", lambda r: "灯带" in r),
    ("关闭风扇", lambda r: "风扇" in r or "执行中" in r or "已操作" in r),
    ("打开筒灯", lambda r: "筒灯" in r),
    ("关闭摄像头", lambda r: "摄像" in r or "未找到" in r),
    ("打开电热毯", lambda r: "电热毯" in r),
    # 场景宏
    ("回家模式", lambda r: "回家" in r or "执行中" in r),
    ("睡眠模式", lambda r: "睡眠" in r or "执行中" in r),
    ("离家模式", lambda r: "离家" in r or "执行中" in r or "未知场景" in r),
    # 快捷操作
    ("全部关闭", lambda r: "全部关闭" in r or "执行中" in r or "已操作" in r),
    ("关灯", lambda r: "关灯" in r or "执行中" in r or "已操作" in r),
    # TTS
    ("说 你好世界", lambda r: "已播报" in r or "不可用" in r),
    ("播报 测试消息", lambda r: "已播报" in r or "不可用" in r),
    # 语音代理
    ("小爱 今天天气怎么样", lambda r: "已发送" in r or "不可用" in r),
    # 兜底（未识别命令→语音代理）
    ("随便说句话测试兜底", lambda r: len(r) > 0),
    # 空消息
    ("", lambda r: "发送指令" in r),
]

passed = 0
for cmd, check in tests:
    try:
        reply = send(cmd)
        ok = check(reply)
        short = reply[:70].replace("\n", " ")
        print(f"  [{PASS if ok else FAIL}] \"{cmd}\" -> {short}")
        if ok:
            passed += 1
    except Exception as e:
        ename = type(e).__name__
        print(f"  [{FAIL}] \"{cmd}\" -> {ename}: {e}"[:100])

print(f"\n{'='*50}")
print(f"  {passed}/{len(tests)} passed")
if passed == len(tests):
    print(f"  \033[92m全部通过!\033[0m")
else:
    print(f"  \033[91m有 {len(tests)-passed} 个失败\033[0m")
print(f"{'='*50}")
