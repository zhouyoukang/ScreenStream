#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全平台比价脚本 — 降噪耳机（倍思M3s）"""
import sys, time, json, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from phone_lib import Phone

p = Phone(port=8086)
results = {}  # {platform: {price, title, detail}}

def section(name):
    print(f"\n{'='*55}")
    print(f"  {name}")
    print(f"{'='*55}")

def safe_read():
    """读取屏幕，返回texts和pkg"""
    texts, pkg = p.read()
    return texts, pkg

def extract_prices(texts):
    """从文本列表中提取价格信息"""
    items = []
    for t in texts:
        if any(c in t for c in ['¥', '元', '￥']):
            items.append(t)
    return items

# ==================== 已有数据（上轮采集） ====================
section("Phase 0: 已有数据汇入")
results["淘宝"] = {"price": 150.46, "title": "倍思M3s 降噪第1名", "sales": "10万+", "source": "上轮采集"}
results["京东"] = {"price": 150.70, "title": "倍思M3s -50dB 政府补贴", "sales": "9万+", "source": "上轮采集"}
results["拼多多"] = {"price": 159.00, "title": "倍思M3s 补贴90元", "sales": "500万+", "source": "上轮采集"}
for k, v in results.items():
    print(f"  {k}: {v['price']}元 — {v['title']}")

# ==================== 慢慢买比价 ====================
section("Phase 1: 慢慢买比价（全平台历史价格）")
p.home()
time.sleep(1)
p.monkey_open("com.manmanbuy.bijia", wait_sec=3)
fg = p.foreground()
print(f"  前台: {fg}")

# 慢慢买搜索：直接用搜索功能
texts, pkg = safe_read()
print(f"  当前页面: {len(texts)}项")

# 尝试搜索
p.search_in_app("倍思M3s")
texts, pkg = safe_read()
price_lines = extract_prices(texts)
print(f"  搜索结果: {len(texts)}项, 含价格{len(price_lines)}行")
for t in texts[:20]:
    print(f"    {t[:80]}")

# 记录慢慢买数据
mmm_prices = []
for t in texts:
    if "¥" in t or "元" in t:
        mmm_prices.append(t)
if mmm_prices:
    results["慢慢买"] = {"price": 0, "title": "比价汇总", "detail": " | ".join(mmm_prices[:5]), "source": "实测"}
    print(f"  慢慢买价格行: {mmm_prices[:5]}")

p.home()
time.sleep(1)

# ==================== 1688 批发价 ====================
section("Phase 2: 1688（批发价/出厂价）")
p.monkey_open("com.alibaba.wireless", wait_sec=4)
fg = p.foreground()
print(f"  前台: {fg}")

if "alibaba" in fg.lower():
    texts, pkg = safe_read()
    print(f"  首页: {len(texts)}项")
    
    # 搜索
    p.search_in_app("倍思M3s降噪耳机")
    texts, pkg = safe_read()
    print(f"  搜索结果: {len(texts)}项")
    for t in texts[:25]:
        print(f"    {t[:80]}")
    
    price_lines = extract_prices(texts)
    if price_lines:
        results["1688"] = {"price": 0, "title": "批发价", "detail": " | ".join(price_lines[:5]), "source": "实测"}
else:
    print(f"  1688未能打开, fg={fg}")

p.home()
time.sleep(1)

# ==================== 抖音商城 ====================
section("Phase 3: 抖音商城")
p.monkey_open("com.ss.android.ugc.aweme", wait_sec=4)
fg = p.foreground()
print(f"  前台: {fg}")

if "aweme" in fg.lower() or "douyin" in fg.lower():
    texts, pkg = safe_read()
    print(f"  首页: {len(texts)}项")
    
    # 抖音商城：点击"商城"tab 或直接搜索
    r = p.click("商城")
    if r.get("ok"):
        time.sleep(2)
        print("  已进入商城tab")
    
    p.search_in_app("倍思M3s降噪耳机")
    texts, pkg = safe_read()
    print(f"  搜索结果: {len(texts)}项")
    for t in texts[:25]:
        print(f"    {t[:80]}")
    
    price_lines = extract_prices(texts)
    if price_lines:
        results["抖音"] = {"price": 0, "title": "抖音商城", "detail": " | ".join(price_lines[:5]), "source": "实测"}
else:
    print(f"  抖音未能打开, fg={fg}")

p.home()
time.sleep(1)

# ==================== 得物 ====================
section("Phase 4: 得物")
p.monkey_open("com.shizhuang.duapp", wait_sec=4)
fg = p.foreground()
print(f"  前台: {fg}")

if "shizhuang" in fg.lower() or "du" in fg.lower():
    texts, pkg = safe_read()
    print(f"  首页: {len(texts)}项")
    
    p.search_in_app("倍思M3s")
    texts, pkg = safe_read()
    print(f"  搜索结果: {len(texts)}项")
    for t in texts[:20]:
        print(f"    {t[:80]}")
    
    price_lines = extract_prices(texts)
    if price_lines:
        results["得物"] = {"price": 0, "title": "得物", "detail": " | ".join(price_lines[:5]), "source": "实测"}
else:
    print(f"  得物未能打开, fg={fg}")

p.home()
time.sleep(1)

# ==================== 京东极速版 ====================
section("Phase 5: 京东极速版（百亿补贴）")
p.monkey_open("com.jd.jdlite", wait_sec=4)
fg = p.foreground()
print(f"  前台: {fg}")

if "jd" in fg.lower():
    texts, pkg = safe_read()
    print(f"  首页: {len(texts)}项")
    
    p.search_in_app("倍思M3s")
    texts, pkg = safe_read()
    print(f"  搜索结果: {len(texts)}项")
    for t in texts[:25]:
        print(f"    {t[:80]}")
    
    price_lines = extract_prices(texts)
    if price_lines:
        results["京东极速版"] = {"price": 0, "title": "京东极速版", "detail": " | ".join(price_lines[:5]), "source": "实测"}
else:
    print(f"  京东极速版未能打开, fg={fg}")

p.home()
time.sleep(1)

# ==================== 闲鱼（二手参考） ====================
section("Phase 6: 闲鱼（二手参考价）")
p.monkey_open("com.taobao.idlefish", wait_sec=4)
fg = p.foreground()
print(f"  前台: {fg}")

if "idlefish" in fg.lower() or "taobao" in fg.lower():
    texts, pkg = safe_read()
    print(f"  首页: {len(texts)}项")
    
    p.search_in_app("倍思M3s")
    texts, pkg = safe_read()
    print(f"  搜索结果: {len(texts)}项")
    for t in texts[:20]:
        print(f"    {t[:80]}")
    
    price_lines = extract_prices(texts)
    if price_lines:
        results["闲鱼"] = {"price": 0, "title": "二手参考", "detail": " | ".join(price_lines[:5]), "source": "实测"}
else:
    print(f"  闲鱼未能打开, fg={fg}")

p.home()
time.sleep(1)

# ==================== 终极汇总 ====================
section("=== 终极比价汇总 ===")
print(f"\n  共覆盖 {len(results)} 个平台\n")

# 已知确切价格
known = {k: v for k, v in results.items() if v["price"] > 0}
unknown = {k: v for k, v in results.items() if v["price"] == 0}

if known:
    print("  【确切价格（已验证）】")
    for k, v in sorted(known.items(), key=lambda x: x[1]["price"]):
        star = " <<<< 最低价" if v["price"] == min(x["price"] for x in known.values()) else ""
        print(f"    {k}: {v['price']:.2f}元 ({v.get('sales','')}) {star}")

if unknown:
    print("\n  【新渠道价格数据】")
    for k, v in unknown.items():
        detail = v.get("detail", "无数据")
        print(f"    {k}: {detail[:80]}")

# 写入剪贴板
clip_text = f"【倍思M3s全平台比价 {time.strftime('%m-%d %H:%M')}】\n"
for k, v in sorted(results.items(), key=lambda x: x[1]["price"] if x[1]["price"] > 0 else 999):
    if v["price"] > 0:
        clip_text += f"{k}: {v['price']:.2f}元\n"
    else:
        clip_text += f"{k}: {v.get('detail','待确认')[:50]}\n"

p.clipboard_write(clip_text.strip())
print(f"\n  比价报告已写入手机剪贴板 ({len(clip_text)}字)")
print("\n" + "="*55)
