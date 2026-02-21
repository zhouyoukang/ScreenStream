#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复剩余平台比价 — 逐个击破"""
import sys, os, time, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from phone_lib import Phone

p = Phone(port=8086)
all_results = {}

def sec(name):
    print(f"\n{'='*55}\n  {name}\n{'='*55}")

def safe_print(texts, limit=25):
    for i, t in enumerate(texts[:limit]):
        # 替换不可打印字符
        safe = t.replace('\xa0', ' ')[:80]
        print(f"    [{i}] {safe}")

# ==================== 1. 慢慢买 ====================
sec("1. 慢慢买比价 — 剪贴板识别法")
# 慢慢买支持剪贴板识别商品链接，但更直接的方式是用其搜索
p.home()
time.sleep(1)
p.monkey_open("com.manmanbuy.bijia", wait_sec=3)

texts, pkg = p.read()
print(f"  当前: {len(texts)}项, pkg={pkg}")
safe_print(texts, 10)

# 慢慢买的搜索在"查历史价"tab → 顶部搜索框
# 先尝试tap顶部搜索区域
from phone_lib import _find_adb
import subprocess
adb = _find_adb()

# 慢慢买首页搜索框在顶部，尝试findclick
r = p.click("查历史价")
time.sleep(1)
texts, pkg = p.read()
print(f"  查历史价tab: {len(texts)}项")
safe_print(texts, 10)

# 直接tap搜索区域（慢慢买搜索框通常在顶部中央）
subprocess.run([adb, "shell", "input", "tap", "540", "200"], capture_output=True, timeout=5)
time.sleep(1)
texts, pkg = p.read()
print(f"  点击搜索区域后: {len(texts)}项")
safe_print(texts, 10)

# 输入搜索词
subprocess.run([adb, "shell", "input", "text", "baseus+M3s"], capture_output=True, timeout=5)
time.sleep(0.5)
subprocess.run([adb, "shell", "input", "keyevent", "66"], capture_output=True, timeout=5)  # Enter
time.sleep(3)

texts, pkg = p.read()
print(f"  搜索结果: {len(texts)}项")
safe_print(texts, 30)

# 提取价格
for t in texts:
    if any(c in t for c in ['¥', '元', '￥', '价']):
        safe = t.replace('\xa0', ' ')[:100]
        print(f"  [价格] {safe}")

all_results["慢慢买"] = texts[:30]
p.home()
time.sleep(1)

# ==================== 2. 抖音商城 ====================
sec("2. 抖音商城 — 商城tab内搜索")
p.monkey_open("com.ss.android.ugc.aweme", wait_sec=3)

# 先进商城tab
r = p.click("商城")
time.sleep(2)
print(f"  点击商城: {r}")

texts, pkg = p.read()
print(f"  商城tab: {len(texts)}项")

# 在商城tab点击搜索框
r = p.click("搜索")
time.sleep(1)
texts, pkg = p.read()
print(f"  点击搜索后: {len(texts)}项")
safe_print(texts, 10)

# 输入搜索词
subprocess.run([adb, "shell", "input", "text", "baseus+M3s"], capture_output=True, timeout=5)
time.sleep(0.5)
subprocess.run([adb, "shell", "input", "keyevent", "66"], capture_output=True, timeout=5)
time.sleep(3)

texts, pkg = p.read()
print(f"  搜索结果: {len(texts)}项")
safe_print(texts, 30)

for t in texts:
    if any(c in t for c in ['¥', '元', '￥']):
        safe = t.replace('\xa0', ' ')[:100]
        print(f"  [价格] {safe}")

all_results["抖音"] = texts[:30]
p.home()
time.sleep(1)

# ==================== 3. 闲鱼 ====================
sec("3. 闲鱼 — 二手参考价")
p.monkey_open("com.taobao.idlefish", wait_sec=3)

texts, pkg = p.read()
print(f"  首页: {len(texts)}项, pkg={pkg}")

# 闲鱼搜索框：尝试点击"搜索"
r = p.click("搜索")
if not r.get("ok"):
    # 直接tap顶部搜索区域
    subprocess.run([adb, "shell", "input", "tap", "540", "150"], capture_output=True, timeout=5)
time.sleep(1)

texts, pkg = p.read()
print(f"  搜索框: {len(texts)}项")
safe_print(texts, 10)

# 输入并搜索
subprocess.run([adb, "shell", "input", "text", "baseus+M3s"], capture_output=True, timeout=5)
time.sleep(0.5)
subprocess.run([adb, "shell", "input", "keyevent", "66"], capture_output=True, timeout=5)
time.sleep(3)

texts, pkg = p.read()
print(f"  搜索结果: {len(texts)}项")
safe_print(texts, 30)

for t in texts:
    if any(c in t for c in ['¥', '元', '￥']):
        safe = t.replace('\xa0', ' ')[:100]
        print(f"  [价格] {safe}")

all_results["闲鱼"] = texts[:30]
p.home()
time.sleep(1)

# ==================== 4. 得物 ====================
sec("4. 得物 — 处理升级弹窗")
p.monkey_open("com.shizhuang.duapp", wait_sec=3)

texts, pkg = p.read()
print(f"  首页: {len(texts)}项")
safe_print(texts, 10)

# 处理升级弹窗
if any("升级" in t or "更新" in t for t in texts):
    r = p.click("后台下载")
    if not r.get("ok"):
        r = p.click("取消")
        if not r.get("ok"):
            p.back()
    time.sleep(2)
    print(f"  处理升级弹窗: {r}")

texts, pkg = p.read()
print(f"  弹窗后: {len(texts)}项")
safe_print(texts, 10)

# 搜索
if "shizhuang" in pkg or "du" in pkg:
    subprocess.run([adb, "shell", "input", "tap", "540", "150"], capture_output=True, timeout=5)
    time.sleep(1)
    subprocess.run([adb, "shell", "input", "text", "baseus+M3s"], capture_output=True, timeout=5)
    time.sleep(0.5)
    subprocess.run([adb, "shell", "input", "keyevent", "66"], capture_output=True, timeout=5)
    time.sleep(3)
    
    texts, pkg = p.read()
    print(f"  搜索结果: {len(texts)}项")
    safe_print(texts, 25)
    
    for t in texts:
        if any(c in t for c in ['¥', '元', '￥']):
            safe = t.replace('\xa0', ' ')[:100]
            print(f"  [价格] {safe}")
    
    all_results["得物"] = texts[:30]

p.home()
time.sleep(1)

# ==================== 5. 京东极速版 ====================
sec("5. 京东极速版 — 处理隐私协议")
p.monkey_open("com.jd.jdlite", wait_sec=3)

texts, pkg = p.read()
print(f"  首页: {len(texts)}项")
safe_print(texts, 10)

# 处理隐私协议
if any("同意" in t for t in texts):
    r = p.click("同意")
    time.sleep(3)
    print(f"  同意隐私协议: {r}")

texts, pkg = p.read()
print(f"  协议后: {len(texts)}项")
safe_print(texts, 10)

# 搜索
if "jd" in pkg.lower():
    p.search_in_app("倍思M3s")
    texts, pkg = p.read()
    print(f"  搜索结果: {len(texts)}项")
    safe_print(texts, 25)
    
    for t in texts:
        if any(c in t for c in ['¥', '元', '￥']):
            safe = t.replace('\xa0', ' ')[:100]
            print(f"  [价格] {safe}")
    
    all_results["京东极速版"] = texts[:30]

p.home()
time.sleep(1)

# ==================== 汇总 ====================
sec("=== 全平台采集完成 ===")
print(f"  成功采集平台数: {len(all_results)}")
for platform, texts in all_results.items():
    price_count = sum(1 for t in texts if any(c in t for c in ['¥', '元', '￥']))
    print(f"  {platform}: {len(texts)}项文本, {price_count}条价格信息")
