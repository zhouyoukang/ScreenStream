"""五感采集 — 多种感官并用突破WebView/Flutter内嵌页面
感官1: uiautomator dump (标准UI树)
感官2: accessibility dump (含WebView辅助功能节点)  
感官3: screencap截屏 (视觉证据)
感官4: activity top dump (Activity视图层级)
感官5: window dump (窗口内容)
"""
import subprocess, time, xml.etree.ElementTree as ET, os, re, sys, json
from datetime import datetime

ADB = r"e:\道\道生一\一生二\构建部署\android-sdk\platform-tools\adb.exe"
S = "158377ff"
OUT = r"e:\道\道生一\一生二\手机操控库\五感采集"
os.makedirs(OUT, exist_ok=True)

def a(*args, t=10):
    try:
        r = subprocess.run([ADB,"-s",S]+list(args), capture_output=True, text=True, timeout=t, encoding='utf-8', errors='replace')
        return r.stdout.strip()
    except: return ""

def a_raw(*args, t=10):
    """返回bytes用于截屏"""
    try:
        r = subprocess.run([ADB,"-s",S]+list(args), capture_output=True, timeout=t)
        return r.stdout
    except: return b""

def tap(x,y): a("shell",f"input tap {x} {y}"); time.sleep(0.3)
def swipe(): a("shell","input swipe 540 1800 540 600 400"); time.sleep(1.2)
def home(): a("shell","input keyevent KEYCODE_HOME"); time.sleep(0.5)
def back(): a("shell","input keyevent KEYCODE_BACK"); time.sleep(0.5)
def monkey(pkg): a("shell",f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1")

def fg():
    out = a("shell","dumpsys window | grep mCurrentFocus")
    m = re.search(r'u0\s+(\S+)', out)
    return m.group(1) if m else ""

def get_nodes():
    a("shell","uiautomator dump /sdcard/ui_dump.xml", t=5)
    a("pull","/sdcard/ui_dump.xml", os.path.join(OUT,"_ui.xml"), t=3)
    try: root = ET.parse(os.path.join(OUT,"_ui.xml")).getroot()
    except: return []
    ns = []
    for n in root.iter("node"):
        t2,d,b = n.get("text","").strip(), n.get("content-desc","").strip(), n.get("bounds","")
        m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', b)
        if m:
            ns.append({"t":t2,"d":d,"x":(int(m[1])+int(m[3]))//2,"y":(int(m[2])+int(m[4]))//2})
    return ns

def ftap(kws, ns):
    for kw in kws:
        for n in ns:
            if kw in n["t"] or kw in n["d"]:
                tap(n["x"], n["y"])
                return n["t"] or n["d"]
    return None

def dismiss(ns):
    for kw in ["允许","同意","确定","我知道了","跳过","暂不升级","关闭","以后再说","暂不","当前应用不再提醒"]:
        h = ftap([kw], ns)
        if h: time.sleep(0.5); return h
    return None

# ============ 五感采集核心 ============

def sense_uiautomator(name):
    """感官1: 标准uiautomator dump → 提取文本"""
    a("shell","uiautomator dump /sdcard/ui_dump.xml", t=5)
    local = os.path.join(OUT, f"{name}_ui.xml")
    a("pull","/sdcard/ui_dump.xml", local, t=3)
    try:
        root = ET.parse(local).getroot()
        texts = []
        for n in root.iter("node"):
            for attr in ["text","content-desc"]:
                v = n.get(attr,"").strip()
                if v and len(v)>1: texts.append(v)
        return texts
    except: return []

def sense_accessibility(name):
    """感官2: accessibility dump → 含WebView内部节点"""
    out = a("shell","dumpsys accessibility", t=15)
    local = os.path.join(OUT, f"{name}_a11y.txt")
    with open(local,"w",encoding="utf-8") as f:
        f.write(out)
    # 提取所有text=和contentDescription=
    texts = []
    for line in out.split("\n"):
        for pattern in [r'text:\s*(.+)', r'contentDescription:\s*(.+)', r'stateDescription:\s*(.+)']:
            m = re.search(pattern, line)
            if m:
                v = m.group(1).strip()
                if v and v != "null" and len(v)>1:
                    texts.append(v)
    return texts

def sense_screenshot(name, idx=0):
    """感官3: 截屏保存"""
    remote = f"/sdcard/ss_{idx}.png"
    a("shell", f"screencap -p {remote}", t=5)
    local = os.path.join(OUT, f"{name}_screen_{idx}.png")
    a("pull", remote, local, t=5)
    if os.path.exists(local) and os.path.getsize(local) > 1000:
        print(f"    📸 截屏: {local} ({os.path.getsize(local)//1024}KB)")
        return local
    return None

def sense_activity_dump(name):
    """感官4: activity top视图层级"""
    out = a("shell","dumpsys activity top", t=10)
    local = os.path.join(OUT, f"{name}_activity.txt")
    # 只保存最后一个TASK的内容(当前Activity)
    lines = out.split("\n")
    # 找到最后一个ACTIVITY
    start = 0
    for i,l in enumerate(lines):
        if "ACTIVITY" in l: start = i
    relevant = "\n".join(lines[start:]) if start > 0 else out[-5000:]
    with open(local,"w",encoding="utf-8") as f:
        f.write(relevant)
    # 提取mText=
    texts = []
    for line in relevant.split("\n"):
        m = re.search(r'mText[=:]\s*"?([^"]+)"?', line)
        if m:
            v = m.group(1).strip()
            if v and len(v)>2: texts.append(v)
        m = re.search(r'text[=:]\s*"?([^"\n]+)"?', line)
        if m:
            v = m.group(1).strip()
            if v and len(v)>2 and not v.startswith("0x"): texts.append(v)
    return texts

def multi_sense_collect(name, max_scrolls=15):
    """五感滚动采集: 每屏用多种方式提取,截屏保存"""
    all_texts = []
    seen = set()
    screenshots = []
    
    for i in range(max_scrolls + 1):
        # 感官1: uiautomator
        ui_texts = sense_uiautomator(f"{name}_{i}")
        # 感官3: 截屏
        ss = sense_screenshot(name, i)
        if ss: screenshots.append(ss)
        
        # 合并去重
        new = []
        for t in ui_texts:
            if t not in seen and len(t) > 1:
                seen.add(t); new.append(t)
        
        if new:
            all_texts.append(f"\n--- {name} 第{i+1}屏 ({len(new)}条) ---")
            all_texts.extend(new)
            print(f"  [{i+1:2d}] UI:{len(new):3d}条")
        else:
            # uiautomator没新内容,试感官2: accessibility
            a11y_texts = sense_accessibility(f"{name}_{i}")
            a11y_new = [t for t in a11y_texts if t not in seen and len(t)>1]
            seen.update(a11y_new)
            if a11y_new:
                all_texts.append(f"\n--- {name} 第{i+1}屏 [a11y] ({len(a11y_new)}条) ---")
                all_texts.extend(a11y_new)
                print(f"  [{i+1:2d}] A11Y:{len(a11y_new):3d}条")
            else:
                print(f"  [{i+1:2d}] 空屏")
                # 连续2次空屏才停
                if i > 0:
                    prev = all_texts[-1] if all_texts else ""
                    if "空" in str(prev) or not new:
                        break
                
        if i < max_scrolls:
            swipe()
    
    # 首屏额外用感官4: activity dump
    act_texts = sense_activity_dump(name)
    act_new = [t for t in act_texts if t not in seen and len(t)>2]
    if act_new:
        all_texts.append(f"\n--- {name} [activity dump] ({len(act_new)}条) ---")
        all_texts.extend(act_new[:50])  # 限制数量
    
    return all_texts, screenshots

# ============ 各APP采集 ============

def do_dangdang():
    """当当: 已在主页，导航到订单"""
    print("\n" + "="*50)
    print("📚 当当")
    print("="*50)
    cur = fg()
    print(f"  前台: {cur}")
    if "dangdang" not in cur:
        monkey("com.dangdang.buy2")
        time.sleep(8)
        ns = get_nodes()
        dismiss(ns)
        time.sleep(2)
        ns = get_nodes()
        dismiss(ns)
    
    ns = get_nodes()
    # 当当底部tab
    ftap(["我的"], ns)
    time.sleep(3)
    ns = get_nodes()
    hit = ftap(["我的订单","全部订单","订单"], ns)
    print(f"  点击: {hit}")
    time.sleep(3)
    return multi_sense_collect("当当", max_scrolls=10)

def do_jd():
    """京东: 用URL scheme跳搜索已购订单,绕过全部订单验证码"""
    print("\n" + "="*50)
    print("🔴 京东")
    print("="*50)
    home()
    # 尝试京东URL scheme直接跳到订单页
    a("shell","am start -a android.intent.action.VIEW -d 'openApp.jdMobile://virtual?params={\"category\":\"jump\",\"des\":\"orderList\"}' -p com.jingdong.app.mall")
    time.sleep(5)
    cur = fg()
    print(f"  前台: {cur}")
    if "Risk" in cur:
        print("  ⚠ 验证码页面，尝试快速验证")
        ns = get_nodes()
        ftap(["快速验证"], ns)
        time.sleep(5)
        cur = fg()
        if "Risk" in cur:
            print("  ⚠ 仍在验证码，改用monkey+待收货tab")
            back(); time.sleep(1)
            back(); time.sleep(1)
            home(); time.sleep(0.5)
            monkey("com.jingdong.app.mall")
            time.sleep(5)
            ns = get_nodes()
            # 点击底部"我的"
            for n in ns:
                if "我的" in n["t"] and n["y"] > 2100:
                    tap(n["x"], n["y"]); break
            time.sleep(3)
            ns = get_nodes()
            # 点"待收货"
            for n in ns:
                if "待收货" in (n["t"]+n["d"]) and 900 < n["y"] < 1200:
                    tap(n["x"], n["y"]); break
            time.sleep(3)
    return multi_sense_collect("京东", max_scrolls=10)

def do_eleme():
    """饿了么: URL scheme直跳订单 + 五感采集"""
    print("\n" + "="*50)
    print("🥡 饿了么")
    print("="*50)
    home()
    a("shell","am start -a android.intent.action.VIEW -d 'eleme://orderlist'")
    time.sleep(5)
    cur = fg()
    print(f"  前台: {cur}")
    # 处理弹窗
    for _ in range(3):
        ns = get_nodes()
        if not dismiss(ns): break
        time.sleep(1)
    return multi_sense_collect("饿了么", max_scrolls=10)

def do_xianyu():
    """闲鱼: 导航到我买到的 + 五感采集"""
    print("\n" + "="*50)
    print("🐟 闲鱼")
    print("="*50)
    home()
    monkey("com.taobao.idlefish")
    time.sleep(5)
    ns = get_nodes()
    dismiss(ns)
    # 点"我的"
    for n in ns:
        if "我的" in (n["t"]+n["d"]) and n["y"] > 2100:
            tap(n["x"], n["y"]); break
    time.sleep(3)
    ns = get_nodes()
    ftap(["我买到的"], ns)
    time.sleep(4)
    return multi_sense_collect("闲鱼", max_scrolls=15)

# ============ 主流程 ============

def save_result(name, texts, screenshots, results_all):
    """保存单个APP结果"""
    results_all[name] = {"texts": texts, "screenshots": screenshots, "count": len(texts)}
    # 增量保存
    out_file = os.path.join(OUT, "采集汇总.txt")
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(f"# 五感采集汇总\n# {datetime.now()}\n\n")
        for n, data in results_all.items():
            f.write(f"\n{'='*60}\n## {n} ({data['count']}行, {len(data['screenshots'])}张截屏)\n{'='*60}\n")
            for l in data["texts"]: f.write(f"{l}\n")
    print(f"  💾 已保存 ({len(texts)}行, {len(screenshots)}张截屏)")

def main():
    print(f"🖐️ 五感采集 — 突破内嵌页面")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    a("shell","input keyevent KEYCODE_WAKEUP")
    
    results = {}
    
    target = sys.argv[1] if len(sys.argv) > 1 else None
    
    tasks = [
        ("当当", do_dangdang),
        ("京东", do_jd),
        ("饿了么", do_eleme),
        ("闲鱼", do_xianyu),
    ]
    
    for name, func in tasks:
        if target and target != name:
            continue
        try:
            texts, screenshots = func()
            save_result(name, texts, screenshots, results)
        except Exception as e:
            print(f"  ❌ {name}: {e}")
            results[name] = {"texts": [f"❌ {e}"], "screenshots": [], "count": 1}
        finally:
            home(); time.sleep(0.5)
    
    total_texts = sum(d["count"] for d in results.values())
    total_ss = sum(len(d["screenshots"]) for d in results.values())
    print(f"\n✅ 五感采集完成: {len(results)}个APP, {total_texts}行文本, {total_ss}张截屏")
    print(f"📁 输出目录: {OUT}")

if __name__ == "__main__":
    main()
