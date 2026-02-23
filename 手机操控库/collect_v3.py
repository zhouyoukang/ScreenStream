"""v3 补采脚本 — monkey启动 + 精准导航 + 每步独立防卡死"""
import subprocess, time, xml.etree.ElementTree as ET, os, re
from datetime import datetime

ADB = r"e:\道\道生一\一生二\构建部署\android-sdk\platform-tools\adb.exe"
S = "158377ff"
OUT = r"e:\道\道生一\一生二\手机操控库"
DUMP = "/sdcard/ui_dump.xml"
LD = os.path.join(OUT, "ui_dump.xml")

def a(*args, t=8):
    try:
        r = subprocess.run([ADB,"-s",S]+list(args), capture_output=True, text=True, timeout=t, encoding='utf-8', errors='replace')
        return r.stdout.strip()
    except: return ""

def tap(x,y): a("shell",f"input tap {x} {y}")
def swipe(): a("shell","input swipe 540 1800 540 600 400")
def home(): a("shell","input keyevent KEYCODE_HOME")
def back(): a("shell","input keyevent KEYCODE_BACK")

def monkey(pkg):
    a("shell",f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1")

def fg():
    out = a("shell","dumpsys window | grep mCurrentFocus")
    m = re.search(r'u0\s+(\S+)', out)
    return m.group(1) if m else ""

def nodes():
    a("shell",f"uiautomator dump {DUMP}", t=5)
    a("pull", DUMP, LD, t=3)
    try: root = ET.parse(LD).getroot()
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
    for kw in ["允许","同意","确定","我知道了","跳过","关闭","以后再说","暂不","不再提醒","当前应用不再提醒","取消"]:
        h = ftap([kw], ns)
        if h: time.sleep(0.5); return h
    return None

def texts_from_nodes(ns):
    seen, out2 = set(), []
    for n in ns:
        for v in [n["t"], n["d"]]:
            if v and len(v)>1 and v not in seen:
                seen.add(v); out2.append(v)
    return out2

def scroll_get(name, mx=10):
    all_t, seen = [], set()
    for i in range(mx+1):
        ns = nodes()
        new = [v for n in ns for v in [n["t"],n["d"]] if v and len(v)>1 and v not in seen]
        seen.update(new)
        if new:
            all_t.append(f"\n--- {name} 第{i+1}屏 ({len(new)}条) ---")
            all_t.extend(new)
            print(f"  [{i+1}] +{len(new)}条")
        else:
            print(f"  [{i+1}] 停止"); break
        if i < mx: swipe(); time.sleep(1.2)
    return all_t

def save(results):
    f = os.path.join(OUT, f"shopping_final_{datetime.now().strftime('%Y%m%d_%H%M')}.txt")
    with open(f, "w", encoding="utf-8") as fp:
        fp.write(f"# 购物记录采集 v3 Final\n# {datetime.now()}\n# OnePlus NE2210\n\n")
        for name, lines in results.items():
            fp.write(f"\n{'='*60}\n## {name}\n{'='*60}\n")
            for l in lines: fp.write(f"{l}\n")
        fp.write(f"\n# 共 {sum(len(v) for v in results.values())} 行\n")
    print(f"💾 已保存: {f}")
    return f

# ============ 各APP采集 ============

def do_jd():
    """京东: monkey启动 → 我的 → 待收货/待评价(避开全部订单的验证码)"""
    print("\n📱 京东")
    home(); time.sleep(0.5)
    monkey("com.jingdong.app.mall"); time.sleep(5)
    cur = fg()
    print(f"  前台: {cur}")
    if "jingdong" not in cur:
        return ["❌ 京东启动失败"]
    # 点击"我的"
    tap(972, 2205); time.sleep(3)
    ns = nodes()
    dismiss(ns)
    # 尝试点"待收货"tab — 不触发验证码
    hit = ftap(["待收货"], ns)
    print(f"  点击: {hit}")
    time.sleep(3)
    cur = fg()
    print(f"  当前: {cur}")
    # 如果又到了验证页，回退换"待评价"
    if "Risk" in cur:
        back(); time.sleep(2)
        ns = nodes()
        ftap(["待评价"], ns); time.sleep(3)
        cur = fg()
        if "Risk" in cur:
            back(); time.sleep(1)
            # 放弃进入订单页，直接采集"我的"页面的订单摘要
            print("  ⚠ 京东验证码阻塞，采集我的页面摘要")
            return scroll_get("京东(我的页)", mx=3)
    return scroll_get("京东订单", mx=10)

def do_pdd():
    """拼多多: 多种启动方式尝试"""
    print("\n📱 拼多多")
    home(); time.sleep(0.5)
    # 方法1: monkey
    monkey("com.xunmeng.pinduoduo"); time.sleep(5)
    cur = fg()
    print(f"  monkey后前台: {cur}")
    if "pinduoduo" not in cur:
        # 方法2: 用specific activity
        a("shell","am start -n com.xunmeng.pinduoduo/.ui.activity.HomeActivity")
        time.sleep(5)
        cur = fg()
        print(f"  intent后前台: {cur}")
    if "pinduoduo" not in cur:
        # 方法3: 通过URL scheme
        a("shell","am start -a android.intent.action.VIEW -d 'pinduoduo://com.xunmeng.pinduoduo/order_list.html'")
        time.sleep(5)
        cur = fg()
        print(f"  deeplink后前台: {cur}")
    if "pinduoduo" not in cur:
        return ["❌ 拼多多全部启动方式失败(OPPO自启动拦截)"]
    ns = nodes()
    for _ in range(3):
        d = dismiss(ns)
        if not d: break
        time.sleep(1); ns = nodes()
    # 导航到订单
    ftap(["个人中心","我的"], ns); time.sleep(2)
    ns = nodes()
    ftap(["我的订单","全部订单","查看全部","全部"], ns); time.sleep(3)
    return scroll_get("拼多多", mx=10)

def do_meituan():
    """美团: monkey启动 → 订单tab"""
    print("\n📱 美团")
    home(); time.sleep(0.5)
    monkey("com.sankuai.meituan"); time.sleep(5)
    cur = fg()
    print(f"  前台: {cur}")
    if "meituan" not in cur:
        return ["❌ 美团启动失败"]
    ns = nodes()
    dismiss(ns)
    # 美团底部有"我的订单"tab
    hit = ftap(["我的订单","订单"], ns)
    print(f"  点击: {hit}")
    time.sleep(3)
    ns = nodes()
    # 如果到了订单列表，可能需要点"全部"tab
    ftap(["全部"], ns)
    time.sleep(2)
    return scroll_get("美团", mx=8)

def do_eleme():
    """饿了么: monkey启动 → dismiss弹窗 → 订单"""
    print("\n📱 饿了么")
    home(); time.sleep(0.5)
    monkey("me.ele"); time.sleep(5)
    # 多次dismiss OPPO系统弹窗
    for _ in range(4):
        ns = nodes()
        d = dismiss(ns)
        if not d: break
        time.sleep(1)
    cur = fg()
    print(f"  前台: {cur}")
    if "ele" not in cur.lower() and "Launcher" in cur:
        return ["❌ 饿了么启动失败(被OPPO弹窗拦截)"]
    ns = nodes()
    # 饿了么底部: 首页/发现/订单/我的
    hit = ftap(["订单","我的订单"], ns)
    print(f"  点击: {hit}")
    time.sleep(3)
    if not hit:
        # 可能需要先点"我的"
        ftap(["我的"], ns); time.sleep(2)
        ns = nodes()
        ftap(["全部订单","我的订单","订单"], ns); time.sleep(2)
    return scroll_get("饿了么", mx=8)

def do_xianyu():
    """闲鱼: monkey启动 → 我的 → 我买到的 → 滚动采集"""
    print("\n📱 闲鱼")
    home(); time.sleep(0.5)
    monkey("com.taobao.idlefish"); time.sleep(5)
    cur = fg()
    print(f"  前台: {cur}")
    if "idlefish" not in cur:
        return ["❌ 闲鱼启动失败"]
    ns = nodes()
    dismiss(ns)
    ftap(["我的"], ns); time.sleep(2)
    ns = nodes()
    hit = ftap(["我买到的"], ns)
    print(f"  点击: {hit}")
    time.sleep(3)
    return scroll_get("闲鱼", mx=8)

def do_dangdang():
    """当当: monkey启动 → 等广告 → 订单"""
    print("\n📱 当当")
    home(); time.sleep(0.5)
    monkey("com.dangdang.buy2"); time.sleep(7)
    # 当当启动慢，可能有广告页
    for _ in range(3):
        ns = nodes()
        d = dismiss(ns)
        if not d:
            # 试试点击屏幕跳过广告
            ftap(["跳过","SKIP","skip","进入"], ns)
            break
        time.sleep(1)
    time.sleep(2)
    cur = fg()
    print(f"  前台: {cur}")
    if "dangdang" not in cur:
        return ["❌ 当当启动失败"]
    ns = nodes()
    ftap(["我的"], ns); time.sleep(2)
    ns = nodes()
    hit = ftap(["我的订单","全部订单","订单"], ns)
    print(f"  点击: {hit}")
    time.sleep(3)
    return scroll_get("当当", mx=8)

# ============ 主流程 ============

def main():
    print(f"🛒 购物记录补采 v3")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    a("shell","input keyevent KEYCODE_WAKEUP")

    results = {}

    # 加载已有淘宝数据
    old = os.path.join(OUT, "shopping_records_20260223_133514.txt")
    if os.path.exists(old):
        with open(old, "r", encoding="utf-8") as f:
            c = f.read()
        m = re.search(r'## 淘宝\n={60}\n(.*?)(?=\n={60}\n## )', c, re.DOTALL)
        if m:
            results["淘宝"] = m.group(1).strip().split("\n")
            print(f"✅ 淘宝: 复用 {len(results['淘宝'])} 行")

    tasks = [
        ("京东", do_jd),
        ("拼多多", do_pdd),
        ("美团", do_meituan),
        ("饿了么", do_eleme),
        ("闲鱼", do_xianyu),
        ("当当", do_dangdang),
    ]

    for name, func in tasks:
        try:
            data = func()
            if data:
                results[name] = data
                print(f"  📊 {name}: {len(data)}行")
                save(results)  # 每个APP保存一次
        except Exception as e:
            print(f"  ❌ {name}: {e}")
            results[name] = [f"❌ {e}"]
        finally:
            home(); time.sleep(0.5)

    f = save(results)
    total = sum(len(v) for v in results.values())
    print(f"\n✅ 全部完成! {len(results)}个APP, {total}行")
    return f

if __name__ == "__main__":
    main()
