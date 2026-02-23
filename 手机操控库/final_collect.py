"""最终采集 — 针对内嵌页面：当当坐标点击+闲鱼截屏+深度滚动"""
import subprocess, time, xml.etree.ElementTree as ET, os, re, sys
from datetime import datetime

ADB = r"e:\道\道生一\一生二\构建部署\android-sdk\platform-tools\adb.exe"
S = "158377ff"
OUT = r"e:\道\道生一\一生二\手机操控库"
os.makedirs(os.path.join(OUT, "screenshots"), exist_ok=True)

def a(*args, t=8):
    try:
        r = subprocess.run([ADB,"-s",S]+list(args), capture_output=True, text=True, timeout=t, encoding='utf-8', errors='replace')
        return r.stdout.strip()
    except: return ""

def tap(x,y): a("shell",f"input tap {x} {y}"); time.sleep(0.3)
def swipe(): a("shell","input swipe 540 1800 540 600 400"); time.sleep(1.5)
def home(): a("shell","input keyevent KEYCODE_HOME"); time.sleep(0.5)
def monkey(pkg): a("shell",f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1")

def fg():
    out = a("shell","dumpsys window | grep mCurrentFocus")
    m = re.search(r'u0\s+(\S+)', out)
    return m.group(1) if m else ""

def screenshot(name, idx):
    path = f"/sdcard/sc_{idx}.png"
    a("shell",f"screencap -p {path}", t=5)
    local = os.path.join(OUT, "screenshots", f"{name}_{idx:02d}.png")
    a("pull", path, local, t=5)
    sz = os.path.getsize(local) if os.path.exists(local) else 0
    if sz > 1000:
        print(f"    📸 {local} ({sz//1024}KB)")
        return local
    return None

def dump_texts():
    a("shell","uiautomator dump /sdcard/ui_dump.xml", t=5)
    a("pull","/sdcard/ui_dump.xml", os.path.join(OUT,"ui_dump.xml"), t=3)
    try: root = ET.parse(os.path.join(OUT,"ui_dump.xml")).getroot()
    except: return [], []
    texts, nodes = [], []
    for n in root.iter("node"):
        t2,d,b = n.get("text","").strip(), n.get("content-desc","").strip(), n.get("bounds","")
        m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', b)
        if m:
            cx,cy = (int(m[1])+int(m[3]))//2, (int(m[2])+int(m[4]))//2
            nodes.append({"t":t2,"d":d,"x":cx,"y":cy})
        if t2 and len(t2)>1: texts.append(t2)
        if d and d!=t2 and len(d)>1: texts.append(d)
    return texts, nodes

def ftap(kws, ns):
    for kw in kws:
        for n in ns:
            if kw in n["t"] or kw in n["d"]:
                tap(n["x"], n["y"]); return n["t"] or n["d"]
    return None

def dismiss(ns):
    for kw in ["允许","同意","确定","我知道了","跳过","暂不升级","关闭","以后再说","暂不"]:
        h = ftap([kw], ns)
        if h: time.sleep(0.5); return h
    return None

def scroll_and_screenshot(name, max_scrolls=20):
    """滚动采集文本+每屏截屏"""
    all_t, seen = [], set()
    shots = []
    empty = 0
    for i in range(max_scrolls+1):
        # 截屏
        s = screenshot(name, i)
        if s: shots.append(s)
        # dump文本
        texts, _ = dump_texts()
        new = [t for t in texts if t not in seen and len(t)>1]
        seen.update(new)
        if new:
            all_t.append(f"\n--- {name} 第{i+1}屏 ({len(new)}条) ---")
            all_t.extend(new)
            print(f"  [{i+1:2d}] +{len(new):3d}条 📸")
            empty = 0
        else:
            empty += 1
            print(f"  [{i+1:2d}] 空屏 ({empty}/3) 📸")
            if empty >= 3: break
        if i < max_scrolls: swipe()
    return all_t, shots

# ============ 当当 ============
def do_dangdang():
    print("\n" + "="*50)
    print("📚 当当")
    print("="*50)
    home()
    monkey("com.dangdang.buy2"); time.sleep(8)
    # dismiss弹窗
    _, ns = dump_texts()
    dismiss(ns); time.sleep(1)
    _, ns = dump_texts()
    dismiss(ns)
    cur = fg()
    print(f"  前台: {cur}")
    if "dangdang" not in cur:
        return [], []
    
    # 当当底部tab是图片无文本，直接点坐标
    # 典型5tab: 首页(108) 分类(324) 购物车(540) 我的(756/972)
    # 当当通常4tab: 首页 分类 购物车 我的
    # 点击"我的" — 最右边tab区域
    print("  → 点击底部'我的'(坐标)")
    tap(920, 2260); time.sleep(3)
    
    # 检查是否到了"我的"页面
    _, ns = dump_texts()
    # 在"我的"页找订单
    hit = ftap(["我的订单","全部订单","订单中心","订单"], ns)
    if not hit:
        # 当当我的页面可能订单入口不同，看看有什么
        print("  当前页面关键元素:")
        for n in ns:
            if any(k in n["t"]+n["d"] for k in ["订单","待","收货","评价","退"]):
                print(f"    '{n['t'] or n['d']}' ({n['x']},{n['y']})")
        # 尝试点"待发货"等订单区域
        hit = ftap(["待发货","待收货","待评价","查看全部订单"], ns)
    print(f"  点击: {hit}")
    time.sleep(3)
    
    return scroll_and_screenshot("当当", max_scrolls=12)

# ============ 闲鱼(截屏为主) ============
def do_xianyu():
    print("\n" + "="*50)
    print("🐟 闲鱼 (截屏采集)")
    print("="*50)
    home()
    monkey("com.taobao.idlefish"); time.sleep(5)
    _, ns = dump_texts()
    dismiss(ns)
    # 点"我的"(底部右侧)
    for n in ns:
        if ("我的" in n["t"] or "我的" in n["d"]) and n["y"] > 2100:
            tap(n["x"], n["y"])
            print(f"  → 点击 '{n['t'] or n['d']}'")
            break
    time.sleep(3)
    _, ns = dump_texts()
    ftap(["我买到的"], ns)
    time.sleep(4)
    
    cur = fg()
    print(f"  前台: {cur}")
    # Flutter页面：uiautomator读不到内容，但截屏能看到
    return scroll_and_screenshot("闲鱼", max_scrolls=25)

# ============ 京东(待收货tab) ============
def do_jd():
    print("\n" + "="*50)
    print("🔴 京东 (待收货+待评价)")
    print("="*50)
    home()
    monkey("com.jingdong.app.mall"); time.sleep(5)
    cur = fg()
    print(f"  前台: {cur}")
    if "jingdong" not in cur:
        return [], []
    
    # 底部"我的"
    _, ns = dump_texts()
    for n in ns:
        if "我的" in n["t"] and n["y"] > 2100:
            tap(n["x"], n["y"]); break
    time.sleep(3)
    
    all_t, all_shots = [], []
    
    # 尝试各个tab
    for tab in ["待收货", "待评价"]:
        _, ns = dump_texts()
        hit = None
        for n in ns:
            if tab in (n["t"]+n["d"]) and 900 < n["y"] < 1200:
                tap(n["x"], n["y"])
                hit = n["t"] or n["d"]
                break
        if not hit: continue
        print(f"  → 点击 {hit}")
        time.sleep(3)
        
        cur = fg()
        if "Risk" in cur:
            print(f"  ⚠ {tab}触发验证码")
            # 截屏验证码页面
            screenshot(f"京东验证码_{tab}", 0)
            back(); time.sleep(2)
            continue
        
        texts, shots = scroll_and_screenshot(f"京东_{tab}", max_scrolls=5)
        all_t.extend(texts)
        all_shots.extend(shots)
        back(); time.sleep(2)
    
    return all_t, all_shots

# ============ 主流程 ============
def main():
    print(f"🖐️ 最终内嵌页面采集")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    a("shell","input keyevent KEYCODE_WAKEUP")
    
    target = sys.argv[1] if len(sys.argv) > 1 else None
    
    tasks = [
        ("当当", do_dangdang),
        ("闲鱼", do_xianyu),
        ("京东", do_jd),
    ]
    
    for name, func in tasks:
        if target and target != name: continue
        try:
            texts, shots = func()
            # 保存到独立文件
            out_file = os.path.join(OUT, f"final_{name}.txt")
            with open(out_file, "w", encoding="utf-8") as f:
                f.write(f"# {name} 订单采集\n# {datetime.now()}\n# 文本{len(texts)}行, 截屏{len(shots)}张\n\n")
                for l in texts: f.write(f"{l}\n")
                f.write(f"\n# 截屏文件:\n")
                for s in shots: f.write(f"# {s}\n")
            print(f"  💾 {name}: {len(texts)}行文本, {len(shots)}张截屏 → {out_file}")
        except Exception as e:
            print(f"  ❌ {name}: {e}")
        finally:
            home(); time.sleep(0.5)
    
    print(f"\n✅ 完成! 截屏保存在: {os.path.join(OUT,'screenshots')}")

if __name__ == "__main__":
    main()
