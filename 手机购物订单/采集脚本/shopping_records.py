"""购物记录采集 v2 — 原子化ADB操作，防卡死
每个ADB命令独立执行，超时5秒自动放弃。用Intent直跳订单页，跳过UI导航。
"""
import subprocess, time, xml.etree.ElementTree as ET, os, re, json
from datetime import datetime

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_SCRIPT_DIR)  # 手机购物订单/
ADB = os.path.join(_ROOT, "..", "构建部署", "android-sdk", "platform-tools", "adb.exe")
SERIAL = "158377ff"
OUT = os.path.join(_ROOT, "原始数据")
DUMP = "/sdcard/ui_dump.xml"
LOCAL_DUMP = os.path.join(OUT, "ui_dump.xml")
RESULT_FILE = os.path.join(OUT, f"shopping_all_{datetime.now().strftime('%Y%m%d_%H%M')}.txt")

def adb(*args, t=10):
    try:
        r = subprocess.run([ADB, "-s", SERIAL]+list(args), capture_output=True, text=True, timeout=t, encoding='utf-8', errors='replace')
        return r.stdout.strip()
    except: return ""

def tap(x, y): adb("shell", f"input tap {x} {y}")
def swipe_up(): adb("shell", "input swipe 540 1800 540 600 400")
def home(): adb("shell", "input keyevent KEYCODE_HOME")
def back(): adb("shell", "input keyevent KEYCODE_BACK")
def stop(pkg): adb("shell", f"am force-stop {pkg}")
def wake(): adb("shell", "input keyevent KEYCODE_WAKEUP")

def fg():
    out = adb("shell", "dumpsys window | grep mCurrentFocus")
    m = re.search(r'u0\s+(\S+)', out)
    return m.group(1) if m else ""

def dump_texts():
    """dump UI → 提取所有文本+坐标，单次操作≤3秒"""
    adb("shell", f"uiautomator dump {DUMP}", t=5)
    adb("pull", DUMP, LOCAL_DUMP, t=3)
    try:
        root = ET.parse(LOCAL_DUMP).getroot()
    except: return [], []
    texts, nodes = [], []
    for n in root.iter("node"):
        txt = n.get("text","").strip()
        desc = n.get("content-desc","").strip()
        bounds = n.get("bounds","")
        m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
        if m:
            cx = (int(m[1])+int(m[3]))//2
            cy = (int(m[2])+int(m[4]))//2
            nodes.append({"t": txt, "d": desc, "x": cx, "y": cy})
        if txt and len(txt)>1: texts.append(txt)
        if desc and desc!=txt and len(desc)>1: texts.append(desc)
    return texts, nodes

def find_tap(keywords, nodes):
    """在nodes中找匹配keyword的元素并点击"""
    for kw in keywords:
        for n in nodes:
            if kw in n["t"] or kw in n["d"]:
                tap(n["x"], n["y"])
                return n["t"] or n["d"]
    return None

def dismiss_dialogs(nodes):
    """自动关闭常见弹窗"""
    for kw in ["允许","同意","确定","我知道了","跳过","取消","关闭","以后再说","暂不","不再提醒","当前应用不再提醒"]:
        hit = find_tap([kw], nodes)
        if hit:
            time.sleep(0.5)
            return hit
    return None

def launch_intent(pkg, activity=None, uri=None):
    """用Intent启动，比monkey更可靠"""
    if uri:
        adb("shell", f"am start -a android.intent.action.VIEW -d '{uri}' -p {pkg}")
    elif activity:
        adb("shell", f"am start -n {pkg}/{activity}")
    else:
        adb("shell", f"am start -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -p {pkg}")

def scroll_collect(name, max_scrolls=10):
    """滚动采集文本，去重，返回所有采集到的文本"""
    all_t = []
    seen = set()
    for i in range(max_scrolls+1):
        texts, _ = dump_texts()
        new = [t for t in texts if t not in seen and len(t)>1]
        seen.update(new)
        if new:
            all_t.append(f"\n--- {name} 第{i+1}屏 ({len(new)}条) ---")
            all_t.extend(new)
            print(f"  [{i+1}] +{len(new)}条")
        else:
            print(f"  [{i+1}] 无新内容，停止")
            break
        if i < max_scrolls:
            swipe_up()
            time.sleep(1.2)
    return all_t

# ============ 每个APP独立采集函数 ============

def collect_taobao():
    """淘宝 — 已有数据，跳过"""
    return None  # 第一轮已成功采集

def collect_jd():
    """京东 — 直跳订单页"""
    stop("com.jingdong.app.mall")
    time.sleep(0.5)
    # 先启动京东主页
    launch_intent("com.jingdong.app.mall")
    time.sleep(4)
    # 点击"我的"
    _, nodes = dump_texts()
    dismiss_dialogs(nodes)
    find_tap(["我的"], nodes)
    time.sleep(2)
    # 在"我的"页找订单入口区域并点击
    _, nodes = dump_texts()
    # 京东"我的"页面：订单区在 待付款/待收货/待评价 这一行，上方有"全部"
    # 找到"待付款"元素，往左上方偏移就是"全部订单"
    hit = find_tap(["待付款"], nodes)
    if hit:
        # 待付款左边通常有一个不带文字的"全部"入口，坐标大约在待付款左侧
        # 从dump数据看待付款在y=约1200区域，全部按钮通常在更左边
        # 尝试直接点击整个订单区域的最左侧
        for n in nodes:
            if "全部" in n["t"] and n["y"] > 800 and n["y"] < 1400:
                tap(n["x"], n["y"])
                time.sleep(2)
                break
    else:
        # 备用：直接找"全部订单"区域或"查看全部"
        find_tap(["全部订单","查看全部","查看更多订单"], nodes)
    time.sleep(3)
    # 检查是否到了订单列表页
    cur = fg()
    print(f"  京东前台: {cur}")
    return scroll_collect("京东", max_scrolls=10)

def collect_pdd():
    """拼多多 — Intent启动绕过OPPO拦截"""
    stop("com.xunmeng.pinduoduo")
    time.sleep(0.5)
    # 用Intent直接启动
    launch_intent("com.xunmeng.pinduoduo")
    time.sleep(5)
    _, nodes = dump_texts()
    d = dismiss_dialogs(nodes)
    if d:
        time.sleep(1)
        _, nodes = dump_texts()
        dismiss_dialogs(nodes)
        time.sleep(1)
    # 检查是否启动成功
    cur = fg()
    print(f"  拼多多前台: {cur}")
    if "pinduoduo" not in cur:
        print("  ❌ 拼多多未能启动")
        return [f"❌ 拼多多启动失败 (OPPO安全拦截), 前台={cur}"]
    # 点击"个人中心"
    _, nodes = dump_texts()
    find_tap(["个人中心","我的"], nodes)
    time.sleep(2)
    # 点击订单
    _, nodes = dump_texts()
    find_tap(["我的订单","全部订单","查看全部","全部"], nodes)
    time.sleep(3)
    return scroll_collect("拼多多", max_scrolls=10)

def collect_meituan():
    """美团 — 直接导航到订单"""
    stop("com.sankuai.meituan")
    time.sleep(0.5)
    # 用deeplink跳订单
    launch_intent("com.sankuai.meituan", uri="imeituan://www.meituan.com/orderList")
    time.sleep(4)
    _, nodes = dump_texts()
    dismiss_dialogs(nodes)
    cur = fg()
    print(f"  美团前台: {cur}")
    if "meituan" not in cur:
        # fallback: 常规启动
        launch_intent("com.sankuai.meituan")
        time.sleep(4)
        _, nodes = dump_texts()
        dismiss_dialogs(nodes)
        find_tap(["我的","订单"], nodes)
        time.sleep(2)
        _, nodes = dump_texts()
        find_tap(["我的订单","全部订单"], nodes)
        time.sleep(2)
    return scroll_collect("美团", max_scrolls=8)

def collect_eleme():
    """饿了么"""
    stop("me.ele")
    time.sleep(0.5)
    launch_intent("me.ele")
    time.sleep(5)
    # 多次dismiss弹窗（OPPO系统弹窗）
    for _ in range(3):
        _, nodes = dump_texts()
        d = dismiss_dialogs(nodes)
        if not d: break
        time.sleep(1)
    cur = fg()
    print(f"  饿了么前台: {cur}")
    if "ele" not in cur.lower():
        return [f"❌ 饿了么启动失败, 前台={cur}"]
    _, nodes = dump_texts()
    find_tap(["我的"], nodes)
    time.sleep(2)
    _, nodes = dump_texts()
    find_tap(["全部订单","我的订单","订单"], nodes)
    time.sleep(2)
    return scroll_collect("饿了么", max_scrolls=8)

def collect_xianyu():
    """闲鱼"""
    stop("com.taobao.idlefish")
    time.sleep(0.5)
    launch_intent("com.taobao.idlefish")
    time.sleep(4)
    _, nodes = dump_texts()
    dismiss_dialogs(nodes)
    # 点击"我的"
    find_tap(["我的"], nodes)
    time.sleep(2)
    _, nodes = dump_texts()
    find_tap(["我买到的"], nodes)
    time.sleep(3)
    return scroll_collect("闲鱼", max_scrolls=8)

def collect_dangdang():
    """当当"""
    stop("com.dangdang.buy2")
    time.sleep(0.5)
    launch_intent("com.dangdang.buy2")
    time.sleep(6)  # 当当启动慢
    _, nodes = dump_texts()
    dismiss_dialogs(nodes)
    time.sleep(1)
    _, nodes = dump_texts()
    dismiss_dialogs(nodes)
    cur = fg()
    print(f"  当当前台: {cur}")
    # 点击"我的"
    find_tap(["我的"], nodes)
    time.sleep(2)
    _, nodes = dump_texts()
    find_tap(["我的订单","全部订单","订单"], nodes)
    time.sleep(2)
    return scroll_collect("当当", max_scrolls=8)

# ============ 主流程 ============

APPS = [
    ("淘宝", collect_taobao),
    ("京东", collect_jd),
    ("拼多多", collect_pdd),
    ("美团", collect_meituan),
    ("饿了么", collect_eleme),
    ("闲鱼", collect_xianyu),
    ("当当", collect_dangdang),
]

def main():
    print(f"🛒 购物记录采集 v2 (原子化)")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    wake()

    results = {}
    # 加载第一轮淘宝数据
    old_file = os.path.join(OUT, "shopping_records_20260223_133514.txt")
    if os.path.exists(old_file):
        with open(old_file, "r", encoding="utf-8") as f:
            content = f.read()
        # 提取淘宝部分
        m = re.search(r'## 淘宝\n={60}\n(.*?)(?=\n={60}\n## |\n\n# 共采集)', content, re.DOTALL)
        if m:
            results["淘宝"] = m.group(1).strip().split("\n")
            print(f"✅ 淘宝: 已有 {len(results['淘宝'])} 行数据")

    for name, func in APPS:
        if name in results:
            continue
        print(f"\n{'='*50}")
        print(f"📱 {name}")
        print(f"{'='*50}")
        try:
            data = func()
            if data is not None:
                results[name] = data
                print(f"  📊 {name}: {len(data)} 行")
                # 每个APP采完立即保存（防中断丢数据）
                _save(results)
        except Exception as e:
            print(f"  ❌ {name}: {e}")
            results[name] = [f"❌ 采集失败: {e}"]
        finally:
            home()
            time.sleep(1)

    _save(results)
    print(f"\n✅ 全部完成！保存到: {RESULT_FILE}")
    total = sum(len(v) for v in results.values())
    print(f"📊 {len(results)}个APP, 共{total}行数据")

def _save(results):
    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        f.write(f"# 购物记录采集报告 v2\n# {datetime.now()}\n# OnePlus NE2210\n\n")
        for name, lines in results.items():
            f.write(f"\n{'='*60}\n## {name}\n{'='*60}\n")
            for l in lines: f.write(f"{l}\n")
        f.write(f"\n# 共 {sum(len(v) for v in results.values())} 行\n")

if __name__ == "__main__":
    main()
