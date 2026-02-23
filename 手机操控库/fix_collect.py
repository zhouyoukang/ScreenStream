"""精确补采 — 逐个修复失败APP，每个独立运行"""
import subprocess, time, xml.etree.ElementTree as ET, os, re, sys
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

def tap(x,y):
    a("shell",f"input tap {x} {y}"); time.sleep(0.3)

def swipe():
    a("shell","input swipe 540 1800 540 600 400"); time.sleep(1.2)

def home():
    a("shell","input keyevent KEYCODE_HOME"); time.sleep(0.5)

def back():
    a("shell","input keyevent KEYCODE_BACK"); time.sleep(0.5)

def monkey(pkg):
    a("shell",f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1")

def fg():
    out = a("shell","dumpsys window | grep mCurrentFocus")
    m = re.search(r'u0\s+(\S+)', out)
    return m.group(1) if m else ""

def get_nodes():
    a("shell",f"uiautomator dump {DUMP}", t=5)
    a("pull", DUMP, LD, t=3)
    try: root = ET.parse(LD).getroot()
    except: return []
    ns = []
    for n in root.iter("node"):
        t2 = n.get("text","").strip()
        d = n.get("content-desc","").strip()
        b = n.get("bounds","")
        m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', b)
        if m:
            ns.append({"t":t2,"d":d,"x":(int(m[1])+int(m[3]))//2,"y":(int(m[2])+int(m[4]))//2,
                       "x1":int(m[1]),"y1":int(m[2]),"x2":int(m[3]),"y2":int(m[4])})
    return ns

def ftap(kws, ns=None):
    if ns is None: ns = get_nodes()
    for kw in kws:
        for n in ns:
            if kw in n["t"] or kw in n["d"]:
                tap(n["x"], n["y"])
                print(f"    → 点击 '{n['t'] or n['d']}' ({n['x']},{n['y']})")
                return True
    print(f"    ✗ 未找到: {kws}")
    return False

def ftap_region(kws, ns, ymin=0, ymax=9999):
    """在指定y范围内找匹配元素并点击"""
    for kw in kws:
        for n in ns:
            if (kw in n["t"] or kw in n["d"]) and ymin <= n["y"] <= ymax:
                tap(n["x"], n["y"])
                print(f"    → 区域点击 '{n['t'] or n['d']}' ({n['x']},{n['y']})")
                return True
    return False

def dismiss(ns=None):
    if ns is None: ns = get_nodes()
    for kw in ["允许","同意","确定","我知道了","跳过","暂不升级","关闭","以后再说","暂不","不再提醒","当前应用不再提醒","取消"]:
        for n in ns:
            if kw in n["t"] or kw in n["d"]:
                tap(n["x"], n["y"])
                print(f"    → 关闭弹窗: '{n['t'] or n['d']}'")
                return True
    return False

def scroll_collect(name, mx=10):
    all_t, seen = [], set()
    for i in range(mx+1):
        ns = get_nodes()
        new = []
        for n in ns:
            for v in [n["t"], n["d"]]:
                if v and len(v)>1 and v not in seen:
                    seen.add(v); new.append(v)
        if new:
            all_t.append(f"\n--- {name} 第{i+1}屏 ({len(new)}条) ---")
            all_t.extend(new)
            print(f"  [{i+1}] +{len(new)}条")
        else:
            print(f"  [{i+1}] 无新内容，停止"); break
        if i < mx: swipe()
    return all_t

def print_all_nodes(ns, keyword=None):
    """调试用：打印所有节点"""
    for n in ns:
        if keyword and keyword not in n["t"]+n["d"]: continue
        if n["t"] or n["d"]:
            print(f"    t='{n['t'][:30]}' d='{n['d'][:30]}' ({n['x']},{n['y']})")

# ============ 各APP精确修复 ============

def fix_jd():
    """京东: 绕过全部订单验证码，分别采集待收货+待评价"""
    print("\n" + "="*50)
    print("📱 京东 (分tab采集绕过验证码)")
    print("="*50)
    home()
    monkey("com.jingdong.app.mall"); time.sleep(5)
    cur = fg()
    print(f"  前台: {cur}")
    if "jingdong" not in cur:
        return ["❌ 京东未启动"]
    
    # 点击底部"我的"tab (通常在最右边)
    ns = get_nodes()
    # 底部tab在 y>2100 区域
    ftap_region(["我的"], ns, ymin=2100)
    time.sleep(3)
    
    all_data = []
    
    # 依次采集各个tab: 待收货、待评价
    for tab_name in ["待收货", "待评价"]:
        ns = get_nodes()
        # 订单区tab在 y=1000~1200 区域
        hit = ftap_region([tab_name], ns, ymin=900, ymax=1200)
        if not hit:
            # 试desc
            hit = ftap([tab_name], ns)
        time.sleep(3)
        cur2 = fg()
        print(f"  {tab_name} → 前台: {cur2}")
        if "Risk" in cur2:
            print(f"  ⚠ {tab_name} 也触发验证码，跳过")
            back(); time.sleep(2)
            continue
        data = scroll_collect(f"京东-{tab_name}", mx=6)
        all_data.extend(data)
        back(); time.sleep(2)
    
    if not all_data:
        all_data = ["⚠ 京东所有订单入口均触发滑动验证码，无法自动采集。需手动验证后重试。"]
    return all_data

def fix_meituan():
    """美团: 先dismiss升级弹窗，再导航到订单"""
    print("\n" + "="*50)
    print("📱 美团")
    print("="*50)
    home()
    monkey("com.sankuai.meituan"); time.sleep(5)
    cur = fg()
    print(f"  前台: {cur}")
    if "meituan" not in cur:
        return ["❌ 美团未启动"]
    
    # 处理升级弹窗
    ns = get_nodes()
    dismiss(ns)
    time.sleep(1)
    # 再次dismiss（可能有多个弹窗）
    ns = get_nodes()
    dismiss(ns)
    time.sleep(1)
    
    # 美团底部tab: 首页/附近/+/消息/我的
    # 先点"我的"
    ns = get_nodes()
    # 底部"我的"在y>2100区域
    if not ftap_region(["我的"], ns, ymin=2100):
        # 可能直接有"订单"tab
        ftap_region(["订单"], ns, ymin=2100)
    time.sleep(3)
    
    # 在"我的"页面找"我的订单"
    ns = get_nodes()
    if not ftap(["我的订单", "全部订单"], ns):
        # 打印所有元素帮助调试
        print("  当前页面元素:")
        print_all_nodes(ns, "订单")
        print_all_nodes(ns, "全部")
    time.sleep(3)
    
    return scroll_collect("美团", mx=8)

def fix_eleme():
    """饿了么: dismiss所有弹窗 → 点击底部"订单"tab"""
    print("\n" + "="*50)
    print("📱 饿了么")
    print("="*50)
    home()
    monkey("me.ele"); time.sleep(5)
    
    # 多次dismiss弹窗
    for _ in range(5):
        ns = get_nodes()
        if not dismiss(ns): break
        time.sleep(1)
    
    cur = fg()
    print(f"  前台: {cur}")
    
    # 检查OPPO弹窗是否还在
    ns = get_nodes()
    # OPPO的SceneService弹窗
    for n in ns:
        if "外卖服务提醒" in n["t"] or "SceneService" in n["t"] or "添加" in n["t"]:
            # 点"取消"
            ftap(["取消","当前应用不再提醒"], ns)
            time.sleep(1)
            break
    
    ns = get_nodes()
    # 饿了么底部tab通常有：首页/天天红包/消息/购物车/我的
    # 先找"订单"或"我的"
    print("  底部元素:")
    print_all_nodes(ns, "订单")
    
    # 点击"我的"（底部tab）
    ftap_region(["我的"], ns, ymin=2100)
    time.sleep(3)
    
    # 找"全部订单"
    ns = get_nodes()
    ftap(["全部订单","我的订单","历史订单","订单"], ns)
    time.sleep(3)
    
    return scroll_collect("饿了么", mx=8)

def fix_xianyu():
    """闲鱼: 确保进入"我的"tab → "我买到的" """
    print("\n" + "="*50)
    print("📱 闲鱼")
    print("="*50)
    home()
    # 先强制回桌面再monkey
    a("shell","am force-stop com.taobao.idlefish"); time.sleep(1)
    monkey("com.taobao.idlefish"); time.sleep(5)
    
    cur = fg()
    print(f"  前台: {cur}")
    if "idlefish" not in cur:
        return ["❌ 闲鱼未启动"]
    
    ns = get_nodes()
    dismiss(ns)
    
    # 闲鱼底部tab: 闲鱼/回收/发布/消息/我的
    # "我的"通常在底部最右边 y>2100
    print("  底部元素(y>2100):")
    for n in ns:
        if n["y"] > 2100 and (n["t"] or n["d"]):
            print(f"    '{n['t'] or n['d']}' ({n['x']},{n['y']})")
    
    # 用content-desc匹配（闲鱼可能用desc标注tab状态）
    if not ftap_region(["我的"], ns, ymin=2100):
        # 直接点最右边区域 (大约x=960, y=2200)
        print("    → 直接点击底部右侧区域")
        tap(960, 2200)
    time.sleep(3)
    
    ns = get_nodes()
    print("  我的页面元素:")
    for n in ns:
        if any(k in n["t"]+n["d"] for k in ["买","卖","订单","收藏"]):
            print(f"    '{n['t'] or n['d']}' ({n['x']},{n['y']})")
    
    ftap(["我买到的"], ns)
    time.sleep(3)
    
    return scroll_collect("闲鱼", mx=10)

def fix_dangdang():
    """当当: 等完整启动 → 跳过广告 → 订单"""
    print("\n" + "="*50)
    print("📱 当当")
    print("="*50)
    home()
    a("shell","am force-stop com.dangdang.buy2"); time.sleep(1)
    monkey("com.dangdang.buy2"); time.sleep(8)
    
    # 多次尝试dismiss
    for _ in range(5):
        ns = get_nodes()
        if dismiss(ns):
            time.sleep(1)
            continue
        if ftap(["跳过","SKIP","进入当当"], ns):
            time.sleep(1)
            continue
        break
    
    time.sleep(2)
    cur = fg()
    print(f"  前台: {cur}")
    
    ns = get_nodes()
    print("  当前页面元素(前10):")
    count = 0
    for n in ns:
        if (n["t"] or n["d"]) and count < 15:
            print(f"    '{(n['t'] or n['d'])[:40]}' ({n['x']},{n['y']})")
            count += 1
    
    # 底部tab
    ftap_region(["我的"], ns, ymin=2100)
    time.sleep(3)
    
    ns = get_nodes()
    ftap(["我的订单","全部订单","订单中心"], ns)
    time.sleep(3)
    
    return scroll_collect("当当", mx=6)

# ============ 主流程 ============

def main():
    print(f"🔧 精确补采 v4")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    a("shell","input keyevent KEYCODE_WAKEUP")
    
    results = {}
    
    # 加载已有的好数据
    old = os.path.join(OUT, "shopping_records_20260223_133514.txt")
    if os.path.exists(old):
        with open(old, "r", encoding="utf-8") as f:
            c = f.read()
        m = re.search(r'## 淘宝\n={60}\n(.*?)(?=\n={60}\n## )', c, re.DOTALL)
        if m:
            results["淘宝"] = m.group(1).strip().split("\n")
            print(f"✅ 淘宝: {len(results['淘宝'])}行")
    
    old2 = os.path.join(OUT, "shopping_final_20260223_1448.txt")
    if os.path.exists(old2):
        with open(old2, "r", encoding="utf-8") as f:
            c = f.read()
        m = re.search(r'## 拼多多\n={60}\n(.*?)(?=\n={60}\n## )', c, re.DOTALL)
        if m:
            results["拼多多"] = m.group(1).strip().split("\n")
            print(f"✅ 拼多多: {len(results['拼多多'])}行")
    
    tasks = [
        ("京东", fix_jd),
        ("美团", fix_meituan),
        ("饿了么", fix_eleme),
        ("闲鱼", fix_xianyu),
        ("当当", fix_dangdang),
    ]
    
    target = sys.argv[1] if len(sys.argv) > 1 else None
    
    for name, func in tasks:
        if target and target != name:
            continue
        try:
            data = func()
            if data:
                results[name] = data
                print(f"  📊 {name}: {len(data)}行")
        except Exception as e:
            print(f"  ❌ {name}: {e}")
            results[name] = [f"❌ {e}"]
        finally:
            home(); time.sleep(0.5)
    
    # 保存最终结果
    out_file = os.path.join(OUT, "shopping_FINAL.txt")
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(f"# 购物记录最终报告\n# {datetime.now()}\n# OnePlus NE2210\n\n")
        for name, lines in results.items():
            f.write(f"\n{'='*60}\n## {name}\n{'='*60}\n")
            for l in lines: f.write(f"{l}\n")
        total = sum(len(v) for v in results.values())
        f.write(f"\n# 共 {total} 行, {len(results)} 个APP\n")
    
    total = sum(len(v) for v in results.values())
    print(f"\n✅ 保存到: {out_file}")
    print(f"📊 {len(results)}个APP, {total}行")

if __name__ == "__main__":
    main()
