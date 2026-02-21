#!/usr/bin/env python3
"""
批量APP深度能力扫描
===================
扫描所有已安装中国区APP的: openapp启动 + screen/text可读性 + findclick能力
生成自动化能力评级，输出到APP_AUTOMATION_MAP.md

用法: python app_capability_scan.py [--port 8086]
"""

import sys, time, json, argparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError

parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int, default=8086)
args = parser.parse_args()

BASE = f"http://127.0.0.1:{args.port}"

def http(method, path, body=None, timeout=10):
    url = BASE + path
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            try: return json.loads(raw)
            except: return {"_raw": raw}
    except: return {"_error": True}

def GET(p): return http("GET", p)
def POST(p, b=None): return http("POST", p, b)
def wait(s): time.sleep(s)
def home(): POST("/home"); wait(0.8)

# APP列表（未在之前深度测试中覆盖的）
APPS = [
    ("美团", "com.sankuai.meituan", "meituan"),
    ("京东", "com.jingdong.app.mall", "jingdong"),
    ("拼多多", "com.xunmeng.pinduoduo", "pinduoduo"),
    ("饿了么", "me.ele", "ele"),
    ("QQ", "com.tencent.mobileqq", "mobileqq"),
    ("钉钉", "com.alibaba.android.rimet", "rimet"),
    ("网易云音乐", "com.netease.cloudmusic", "cloudmusic"),
    ("微博", "com.sina.weibo", "weibo"),
    ("知乎", "com.zhihu.android", "zhihu"),
    ("夸克浏览器", "com.quark.browser", "quark"),
]

print("=" * 60)
print("  批量APP深度能力扫描")
print("=" * 60)

if "_error" in GET("/status"):
    print("❌ API不可达"); sys.exit(1)
print("✓ 连接正常\n")

results = []

for name, pkg, key in APPS:
    # 1. 启动APP
    POST("/openapp", {"packageName": pkg})
    wait(3)

    # 2. 处理OPPO弹窗
    fg = GET("/foreground")
    fg_pkg = fg.get("packageName", "").lower()
    if "permission" in fg_pkg:
        POST("/findclick", {"text": "允许"}); wait(0.5)
        POST("/back"); wait(1)
        fg = GET("/foreground")
        fg_pkg = fg.get("packageName", "").lower()

    in_app = key.lower() in fg_pkg

    # 3. 读取screen/text
    st = GET("/screen/text")
    text_count = st.get("textCount", 0)
    click_count = st.get("clickableCount", 0)
    texts = [t.get("text", "") for t in st.get("texts", [])]
    sample = [t for t in texts if len(t) > 3][:3]

    # 4. 测试findclick（用常见tab名称）
    fc_ok = False
    for tab in ["首页", "我的", "消息", "推荐"]:
        r = POST("/findclick", {"text": tab})
        if isinstance(r, dict) and r.get("ok"):
            fc_ok = True
            break
    wait(0.5)

    # 5. 评级
    if in_app and text_count > 10 and fc_ok:
        rating = "⭐⭐⭐"
    elif in_app and text_count > 5:
        rating = "⭐⭐"
    elif in_app:
        rating = "⭐"
    else:
        rating = "○"

    results.append({
        "name": name, "pkg": pkg, "in_app": in_app,
        "texts": text_count, "clicks": click_count,
        "findclick": fc_ok, "rating": rating, "sample": sample
    })

    print(f"  {rating} {name}: texts={text_count} clicks={click_count} findclick={'✅' if fc_ok else '❌'} pkg={fg_pkg.split('.')[-1]}")

    home()

# 总结
print(f"\n{'='*60}")
print("  扫描结果")
print(f"{'='*60}")

stars3 = sum(1 for r in results if "⭐⭐⭐" in r["rating"])
stars2 = sum(1 for r in results if r["rating"] == "⭐⭐")
stars1 = sum(1 for r in results if r["rating"] == "⭐")
basic = sum(1 for r in results if r["rating"] == "○")

print(f"  ⭐⭐⭐ 全面可自动化: {stars3}个")
print(f"  ⭐⭐ 文本可读: {stars2}个")
print(f"  ⭐ 基础可启动: {stars1}个")
print(f"  ○ 受限: {basic}个")

# 输出可自动化APP的详细能力
print(f"\n  📊 可深度操控APP (texts>5):")
for r in results:
    if r["texts"] > 5:
        print(f"    {r['name']}: texts={r['texts']} clicks={r['clicks']} fc={'✅' if r['findclick'] else '❌'}")
        if r["sample"]:
            print(f"      样本: {r['sample']}")

print(f"{'='*60}")
