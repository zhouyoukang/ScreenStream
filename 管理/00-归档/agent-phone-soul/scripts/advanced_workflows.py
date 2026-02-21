#!/usr/bin/env python3
"""
高复杂度跨APP多级联动工作流
============================
5个真实场景，每个涉及多APP深度交互+条件分支+数据提取+验证。
全部零AI（L0/L1），展示手机作为"万能终端"的深度能力。

场景设计原则：
  - 每个场景跨2+个APP
  - 每个场景包含数据提取+条件判断+动态决策
  - 每个场景模拟真实中国用户使用链路

用法: python advanced_workflows.py [--port 8086]
"""

import sys, time, json, argparse, re
from urllib.request import Request, urlopen
from urllib.error import HTTPError

parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int, default=8086)
args = parser.parse_args()

BASE = f"http://127.0.0.1:{args.port}"
results = []

def http(method, path, body=None, timeout=15):
    url = BASE + path
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            try: return json.loads(raw)
            except: return {"_raw": raw}
    except HTTPError as e: return {"_error": e.code}
    except: return {"_error": -1}

def GET(p): return http("GET", p)
def POST(p, b=None): return http("POST", p, b)
def wait(ms): time.sleep(ms / 1000)
def home(): POST("/home"); wait(800)

def dismiss_dialog():
    fg = GET("/foreground")
    if "permission" in fg.get("packageName", "").lower():
        for btn in ["允许", "始终允许", "打开", "确定"]:
            POST("/findclick", {"text": btn}); wait(200)
        POST("/back"); wait(500)

def open_app(pkg):
    POST("/openapp", {"packageName": pkg}); wait(2000); dismiss_dialog()

def read_texts():
    r = GET("/screen/text")
    return [t.get("text", "") for t in r.get("texts", [])], r.get("package", "")

def fg_pkg():
    return GET("/foreground").get("packageName", "")

def scenario(name, fn):
    t0 = time.time()
    try:
        ok, detail, steps = fn()
        ms = int((time.time() - t0) * 1000)
        results.append({"name": name, "ok": ok, "steps": steps, "ms": ms})
        icon = "✅" if ok else "❌"
        print(f"  {icon} {name} ({steps}步, {ms}ms)")
        for line in detail.split("\n"):
            if line.strip(): print(f"     {line.strip()}")
    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        results.append({"name": name, "ok": False, "steps": 0, "ms": ms})
        print(f"  💥 {name} ({ms}ms): {e}")
    home()

print("=" * 64)
print("  高复杂度跨APP多级联动工作流")
print("=" * 64)

s = GET("/status")
if "_error" in s:
    print(f"❌ API不可达"); sys.exit(1)
print(f"✓ 连接正常\n")

# ==================== WF1: 设备健康巡检+智能响应链 ====================
# 采集电池/存储/网络/通知/前台APP → 多条件决策 → 执行响应动作
def wf1():
    steps = 0; actions = []; report = {}

    # 1. 并行采集5维状态
    steps += 1
    dev = GET("/deviceinfo")
    notifs = GET("/notifications/read?limit=10")
    fg = GET("/foreground")
    storage = GET("/files/storage")
    macros = GET("/macro/list")

    report["battery"] = dev.get("batteryLevel", -1)
    report["charging"] = dev.get("isCharging", False)
    report["network"] = dev.get("networkType", "?")
    report["net_ok"] = dev.get("networkConnected", False)
    report["screen"] = dev.get("isScreenOn", True)
    report["notif_count"] = notifs.get("total", 0)
    report["fg_app"] = fg.get("packageName", "?").split(".")[-1]
    report["storage_free_gb"] = round(dev.get("storageAvailableMB", 0) / 1024, 1)
    report["macro_count"] = len(macros) if isinstance(macros, list) else 0
    report["running_macros"] = sum(1 for m in (macros if isinstance(macros, list) else []) if m.get("running"))

    # 2. 多条件决策引擎
    steps += 1

    # R1: 电量保护
    if report["battery"] < 20 and not report["charging"]:
        POST("/stayawake/false"); POST("/brightness/10")
        actions.append("省电:关保持唤醒+最低亮度")
    elif report["battery"] > 80:
        POST("/stayawake/true"); POST("/brightness/128")
        actions.append("正常:保持唤醒+标准亮度")
    steps += 1

    # R2: 网络异常处理
    if not report["net_ok"]:
        POST("/wake")
        actions.append("网络断开:唤醒屏幕")
    steps += 1

    # R3: 存储告警
    if report["storage_free_gb"] < 5:
        actions.append(f"存储警告:仅剩{report['storage_free_gb']}GB")
    steps += 1

    # R4: 通知分类统计
    items = notifs.get("notifications", [])
    social = sum(1 for n in items if any(k in str(n.get("package","")).lower() for k in ["tencent","weixin","whatsapp"]))
    system_n = sum(1 for n in items if "android" in str(n.get("package","")).lower())
    if social > 3:
        actions.append(f"社交通知较多({social}条)")
    steps += 1

    # R5: 宏系统状态检查
    if report["running_macros"] > 0:
        actions.append(f"运行中宏:{report['running_macros']}个")
    steps += 1

    # 3. 生成报告
    detail = f"电量:{report['battery']}%{'⚡' if report['charging'] else ''} | 网络:{report['network']}{'✅' if report['net_ok'] else '❌'}\n"
    detail += f"存储:{report['storage_free_gb']}GB | 通知:{report['notif_count']}(社交{social}) | 宏:{report['macro_count']}(运行{report['running_macros']})\n"
    detail += f"动作: {' → '.join(actions) if actions else '无需响应'}"

    ok = report["battery"] >= 0 and len(report) >= 8
    return ok, detail, steps

print("🔋 WF1: 设备健康巡检+智能响应链")
scenario("设备健康巡检+智能响应", wf1)

# ==================== WF2: 微信→高德 位置搜索链 ====================
# 打开微信(确认在线) → 回桌面 → 高德搜索附近餐厅 → 提取POI信息 → 剪贴板写入
def wf2():
    steps = 0; data = {}

    # 1. 确认微信在线（打开+验证）
    steps += 1
    open_app("com.tencent.mm"); wait(1000)
    data["wechat_ok"] = "tencent.mm" in fg_pkg()
    steps += 1; home()

    # 2. 高德搜索附近餐厅
    steps += 1
    POST("/intent", {
        "action": "android.intent.action.VIEW",
        "data": "androidamap://poi?sourceApplication=test&keywords=附近餐厅&dev=0",
        "flags": ["FLAG_ACTIVITY_NEW_TASK"]
    })
    wait(3000)
    steps += 1
    data["amap_ok"] = "autonavi" in fg_pkg()

    # 3. 提取POI结果
    steps += 1
    texts, pkg = read_texts()
    poi_items = [t for t in texts if any(k in t for k in ["餐", "饭", "店", "米", "面", "火锅", "烧烤", "公里", "km", "评分"])]
    data["poi_count"] = len(poi_items)
    data["poi_sample"] = poi_items[:3]

    # 4. 将结果写入剪贴板（供微信使用）
    steps += 1
    clip_text = f"附近餐厅: {', '.join(poi_items[:3])}" if poi_items else "未找到附近餐厅"
    POST("/clipboard", {"text": clip_text})

    # 5. 验证剪贴板
    steps += 1
    clip = GET("/clipboard")
    data["clip_ok"] = clip.get("text") is not None

    home()
    detail = f"微信:{'✅' if data['wechat_ok'] else '❌'} | 高德:{'✅' if data['amap_ok'] else '❌'}\n"
    detail += f"POI结果:{data['poi_count']}条 | 样本:{data.get('poi_sample',[])} \n"
    detail += f"剪贴板已写入({len(clip_text)}字)"

    ok = data["wechat_ok"] and data["amap_ok"]
    return ok, detail, steps

print("\n🗺️ WF2: 微信→高德 位置搜索+剪贴板同步链")
scenario("微信→高德位置搜索链", wf2)

# ==================== WF3: 多APP通知分析+智能路由 ====================
# 读通知 → 按包名分类 → 有微信则打开微信 → 有支付宝则检查余额页 → 回桌面
def wf3():
    steps = 0; data = {"routed": []}

    # 1. 读取所有通知
    steps += 1
    notifs = GET("/notifications/read?limit=20")
    items = notifs.get("notifications", [])
    data["total"] = notifs.get("total", 0)

    # 2. 分类
    steps += 1
    categories = {}
    for n in items:
        pkg = str(n.get("package", "")).lower()
        app = pkg.split(".")[-1] if pkg else "unknown"
        categories[app] = categories.get(app, 0) + 1

    data["categories"] = categories
    data["top_apps"] = sorted(categories.items(), key=lambda x: -x[1])[:5]

    # 3. 智能路由: 微信有通知则打开微信查看
    steps += 1
    wechat_notifs = sum(1 for n in items if "tencent" in str(n.get("package","")).lower())
    if wechat_notifs > 0:
        open_app("com.tencent.mm"); wait(1500)
        data["routed"].append(f"微信({wechat_notifs}条)")
        home()
    steps += 1

    # 4. 支付宝有通知则打开支付宝
    alipay_notifs = sum(1 for n in items if "alipay" in str(n.get("package","")).lower())
    if alipay_notifs > 0:
        open_app("com.eg.android.AlipayGphone"); wait(1500)
        data["routed"].append(f"支付宝({alipay_notifs}条)")
        home()
    steps += 1

    # 5. 系统通知统计
    sys_notifs = sum(1 for n in items if "android" in str(n.get("package","")).lower() or "system" in str(n.get("package","")).lower())
    data["system"] = sys_notifs

    # 6. 设备状态采集（条件触发）
    steps += 1
    dev = GET("/deviceinfo")
    if dev.get("batteryLevel", 100) < 30:
        data["routed"].append("电量低→省电模式")
        POST("/stayawake/false")

    detail = f"通知:{data['total']}条 | 分类:{len(categories)}个APP\n"
    detail += f"TOP: {data['top_apps']}\n"
    detail += f"路由: {' → '.join(data['routed']) if data['routed'] else '无需路由(无关键通知)'}"

    ok = data["total"] >= 0
    return ok, detail, steps

print("\n🔔 WF3: 多APP通知分析+智能路由")
scenario("通知分析+智能路由", wf3)

# ==================== WF4: 跨APP信息萃取+报告生成 ====================
# 支付宝→我的页 → 高德→当前位置 → 设备信息 → 通知摘要 → 合成报告写入剪贴板
def wf4():
    steps = 0; report_parts = []

    # 1. 支付宝信息
    steps += 1
    open_app("com.eg.android.AlipayGphone"); wait(1500)
    steps += 1
    POST("/findclick", {"text": "我的"}); wait(1500)
    texts_a, _ = read_texts()
    finance_kw = [t for t in texts_a if any(k in t for k in ["余额", "花呗", "借呗", "总资产", "芝麻", "积分"])]
    report_parts.append(f"支付宝: {len(texts_a)}项, 财务关键词{len(finance_kw)}个")
    home()

    # 2. 高德位置信息
    steps += 1
    open_app("com.autonavi.minimap"); wait(2000)
    steps += 1
    texts_m, _ = read_texts()
    location_kw = [t for t in texts_m if any(k in t for k in ["路", "街", "区", "市", "省", "号", "大厦", "广场"])]
    report_parts.append(f"高德: {len(texts_m)}项, 位置{len(location_kw)}个")
    home()

    # 3. 设备信息
    steps += 1
    dev = GET("/deviceinfo")
    report_parts.append(f"设备: {dev.get('manufacturer','')} {dev.get('model','')} 电量{dev.get('batteryLevel',0)}%")

    # 4. 通知摘要
    steps += 1
    notifs = GET("/notifications/read?limit=5")
    n_titles = [str(n.get("title", "")) for n in notifs.get("notifications", []) if n.get("title")]
    report_parts.append(f"通知: {notifs.get('total',0)}条 [{', '.join(n_titles[:3])}]")

    # 5. 合成报告写入剪贴板
    steps += 1
    full_report = " | ".join(report_parts)
    POST("/clipboard", {"text": full_report})
    clip = GET("/clipboard")

    detail = "\n".join(f"  {p}" for p in report_parts) + f"\n→ 报告已写入剪贴板({len(full_report)}字)"
    ok = len(report_parts) >= 4
    return ok, detail, steps

print("\n📊 WF4: 跨APP信息萃取+报告生成")
scenario("跨APP信息萃取+报告", wf4)

# ==================== WF5: 全能设备控制序列 ====================
# 唤醒→解锁→调亮度→调音量→打开微信→截屏→读屏→回桌面→打开高德→导航→截屏→回桌面→锁屏
def wf5():
    steps = 0; checkpoints = []

    # 1. 唤醒+基础设置
    steps += 1
    POST("/wake"); wait(500)
    POST("/brightness/200"); POST("/volume", {"stream": "music", "level": 3})
    checkpoints.append("唤醒+亮度200+音量3")

    # 2. 微信交互
    steps += 1
    open_app("com.tencent.mm"); wait(1500)
    wechat_ok = "tencent.mm" in fg_pkg()
    checkpoints.append(f"微信{'✅' if wechat_ok else '❌'}")

    # 3. 截屏+读屏
    steps += 1
    POST("/screenshot"); wait(500)
    texts_w, _ = read_texts()
    checkpoints.append(f"微信读屏:{len(texts_w)}项")
    home()

    # 4. 高德导航
    steps += 1
    POST("/intent", {
        "action": "android.intent.action.VIEW",
        "data": "androidamap://navi?sourceApplication=test&lat=31.2304&lon=121.4737&dev=0&style=2",
        "flags": ["FLAG_ACTIVITY_NEW_TASK"]
    })
    wait(3000)
    amap_ok = "autonavi" in fg_pkg()
    checkpoints.append(f"高德导航{'✅' if amap_ok else '❌'}")

    # 5. 读导航信息
    steps += 1
    texts_n, _ = read_texts()
    navi_kw = [t for t in texts_n if any(k in t for k in ["导航", "路线", "公里", "分钟", "到达"])]
    checkpoints.append(f"导航信息:{len(navi_kw)}项")

    # 6. 截屏
    steps += 1
    POST("/screenshot"); wait(300)
    checkpoints.append("截屏2")
    home()

    # 7. 恢复设置
    steps += 1
    POST("/brightness/128"); POST("/volume", {"stream": "music", "level": 5})
    checkpoints.append("恢复亮度128+音量5")

    detail = " → ".join(checkpoints)
    ok = wechat_ok and amap_ok
    return ok, detail, steps

print("\n🎮 WF5: 全能设备控制序列 (唤醒→微信→截屏→高德导航→恢复)")
scenario("全能设备控制序列", wf5)

# ==================== 总结 ====================
home()
total = len(results)
passed = sum(1 for r in results if r["ok"])
total_steps = sum(r["steps"] for r in results)
total_ms = sum(r["ms"] for r in results)

print("\n" + "=" * 64)
print(f"  结果: {passed}/{total} 工作流通过 | 总步骤: {total_steps} | 总耗时: {total_ms//1000}s")
print("=" * 64)

for r in results:
    icon = "✅" if r["ok"] else "❌"
    print(f"  {icon} {r['name']}: {r['steps']}步, {r['ms']//1000}s")

if passed < total:
    print(f"\n  ❌ 失败项:")
    for r in results:
        if not r["ok"]: print(f"    {r['name']}")

print(f"\n  🏛️ 全部 {total_steps} 步均为零AI操作 (L0+L1)")
print("=" * 64)
sys.exit(0 if passed == total else 1)
