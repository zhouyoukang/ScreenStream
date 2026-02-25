"""统一深度订单提取器 v2
混合架构：ADB操控 + ScreenStream API读屏（解决WebView盲区）

诊断发现（2026-02-23实测）：
- 淘宝订单卡片需双击商品容器进入详情页（单击无效）
- 详情页是WebView，uiautomator dump读不到内容
- ScreenStream AccessibilityService (端口8086) 能读WebView
- 必须force-stop再启动APP，避免残留页面状态
- 淘宝"我的"页"全部"入口在 y=791 x=967
- 订单卡片可点击容器是商品区域的父LinearLayout
"""
import subprocess, time, os, re, json
from datetime import datetime
import urllib.request, urllib.error

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_SCRIPT_DIR)
ADB = os.path.join(_ROOT, "..", "构建部署", "android-sdk", "platform-tools", "adb.exe")
S = "158377ff"
DATA = os.path.join(_ROOT, "原始数据")
OUT = os.path.join(_ROOT, "解析结果")
SS_PORT = 8086

os.makedirs(DATA, exist_ok=True)
os.makedirs(OUT, exist_ok=True)

# ============================================================
# ADB 操控层（物理交互）
# ============================================================

def adb(*args, t=10):
    try:
        r = subprocess.run([ADB, "-s", S] + list(args),
                          capture_output=True, text=True, timeout=t,
                          encoding='utf-8', errors='replace')
        return r.stdout.strip()
    except:
        return ""

def tap(x, y, wait=0.3):
    adb("shell", f"input tap {x} {y}")
    time.sleep(wait)

def double_tap(x, y):
    """双击 — 淘宝订单卡片需要此操作进入详情"""
    adb("shell", f"input tap {x} {y}")
    time.sleep(0.12)
    adb("shell", f"input tap {x} {y}")
    time.sleep(3)

def back(wait=1.5):
    adb("shell", "input keyevent KEYCODE_BACK")
    time.sleep(wait)

def home():
    adb("shell", "input keyevent KEYCODE_HOME")
    time.sleep(0.5)

def swipe_up(duration=500):
    adb("shell", f"input swipe 540 1800 540 600 {duration}")
    time.sleep(1.5)

def wake():
    adb("shell", "input keyevent KEYCODE_WAKEUP")

def force_start(pkg):
    """force-stop后重启，确保干净状态"""
    adb("shell", f"am force-stop {pkg}")
    time.sleep(1)
    adb("shell", f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1")
    time.sleep(5)

# ============================================================
# ScreenStream API 读屏层（能读WebView）
# ============================================================

def ss_setup():
    """建立adb forward端口转发"""
    adb("forward", f"tcp:{SS_PORT}", f"tcp:{SS_PORT}")
    time.sleep(0.5)

def ss_get(path, timeout=5):
    """调用ScreenStream HTTP API，返回JSON"""
    url = f"http://127.0.0.1:{SS_PORT}{path}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        return None

def read_screen():
    """读取当前屏幕所有文本（通过ScreenStream AccessibilityService）
    返回文本列表（比uiautomator丰富，能读WebView）
    """
    data = ss_get("/screen/text")
    if not data or "texts" not in data:
        return []
    return [item.get("text", "") for item in data["texts"] if item.get("text", "").strip()]

def screen_has(*keywords):
    """检查屏幕是否包含指定关键词"""
    texts = read_screen()
    combined = " ".join(texts)
    return any(kw in combined for kw in keywords)

def screen_signature():
    """页面文本签名（用于检测页面是否变化）"""
    texts = read_screen()
    meaningful = [t for t in texts if len(t) > 3][:30]
    return hash("|".join(sorted(meaningful)))

def dismiss_popup():
    """关闭弹窗（基于屏幕文本匹配 + 固定关键词tap）"""
    texts = read_screen()
    popup_kw = ["允许", "同意", "确定", "我知道了", "跳过", "关闭",
                "以后再说", "暂不", "知道了", "不再提醒"]
    for kw in popup_kw:
        if kw in texts:
            # 找到弹窗关键词，用uiautomator找坐标点击
            import xml.etree.ElementTree as ET
            tmp = os.path.join(os.environ.get("TEMP", "/tmp"), "ui_popup.xml")
            adb("shell", "uiautomator dump /sdcard/ui_dump.xml", t=6)
            adb("pull", "/sdcard/ui_dump.xml", tmp, t=4)
            try:
                root = ET.parse(tmp).getroot()
                for n in root.iter("node"):
                    t = n.get("text", "").strip()
                    if t == kw:
                        b = n.get("bounds", "")
                        m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', b)
                        if m:
                            cx = (int(m[1]) + int(m[3])) // 2
                            cy = (int(m[2]) + int(m[4])) // 2
                            tap(cx, cy)
                            time.sleep(0.5)
                            return True
            except:
                pass
    return False

# ============================================================
# 通用提取逻辑
# ============================================================

def extract_fields(texts):
    """从文本列表中提取订单核心字段（通用，淘宝/拼多多/京东共用）"""
    info = {
        "order_id": "", "order_date": "", "store": "",
        "products": [], "total_paid": "", "status": "",
        "shipping": "", "address": "",
    }

    statuses = {"交易成功", "交易关闭", "待发货", "已发货", "已签收",
                "待收货", "待付款", "退款成功", "退款中", "卖家已发货",
                "已取消", "已完成", "待评价"}

    store_kw = ["旗舰店", "专营店", "书店", "书城", "数码", "科技",
                "贸易", "自营", "商行", "工厂", "官方店", "企业店"]

    skip_product = {"旗舰店", "专营店", "快递", "签收", "确认", "申请",
                    "投诉", "按钮", "返回", "搜索", "复制", "收货地址",
                    "付款方式", "运费险", "客服", "评价", "退货", "售后"}

    for i, t in enumerate(texts):
        t = t.strip()
        if not t:
            continue

        # 订单号（12-25位纯数字）
        if re.match(r'^\d{12,25}$', t) and not info["order_id"]:
            info["order_id"] = t

        # 日期（多种格式）
        if not info["order_date"]:
            if re.match(r'20\d{2}[年.\-/]\d{1,2}[月.\-/]\d{1,2}', t):
                info["order_date"] = t
            elif re.match(r'20\d{2}\.\d{2}\.\d{2}', t):
                info["order_date"] = t

        # 状态
        if t in statuses:
            info["status"] = t

        # 店铺名
        if any(k in t for k in store_kw) and len(t) < 30 and not info["store"]:
            info["store"] = t

        # 物流
        if ("快递" in t or "签收" in t or "运单" in t) and len(t) > 5:
            if "查看物流" not in t:
                info["shipping"] = t[:80]

        # 收货地址
        if "收货地址" in t or ("省" in t and "市" in t and len(t) > 8):
            info["address"] = t[:60]

    # 实付款：找"实付"/"合计"附近的¥值
    for i, t in enumerate(texts):
        if "实付" in t or ("合计" in t and "订单" not in t):
            for j in range(max(0, i - 2), min(i + 5, len(texts))):
                pm = re.search(r'[¥￥](\d+\.?\d*)', texts[j])
                if pm:
                    info["total_paid"] = pm.group(1)
                    break
            if info["total_paid"]:
                break

    # 商品名（长中文文本，排除UI文本）
    for t in texts:
        t = t.strip()
        if (len(t) > 15
            and any('\u4e00' <= c <= '\u9fff' for c in t[:5])
            and not any(k in t for k in skip_product)):
            info["products"].append(t[:100])

    return info

# ============================================================
# 淘宝深度采集
# ============================================================

def taobao_navigate_to_orders():
    """淘宝：force-stop → 启动 → 我的 → 全部订单"""
    print("  启动淘宝（干净状态）...")
    force_start("com.taobao.taobao")

    # 关弹窗
    for _ in range(3):
        if not dismiss_popup():
            break
        time.sleep(1)

    # 底部tab "我的淘宝" (实测坐标 x=972, y=2196)
    print("  → 我的淘宝")
    tap(972, 2196, wait=3)

    # 关弹窗
    dismiss_popup()
    time.sleep(0.5)

    # "我的订单" 右侧 "全部" (实测坐标 x=967, y=791)
    print("  → 全部订单")
    tap(967, 791, wait=3)

    # 验证
    if screen_has("待付款", "待收货", "全部订单"):
        print("  ✅ 已进入淘宝订单列表")
        return True
    else:
        print("  ❌ 未能进入订单列表")
        # 二次尝试：直接点"全部"tab
        tap(119, 395, wait=2)
        if screen_has("待付款", "待收货"):
            print("  ✅ 二次尝试成功")
            return True
        return False

def taobao_find_clickable_cards():
    """找淘宝订单列表中可点击的订单卡片容器
    基于uiautomator找clickable=true的大区域LinearLayout
    （ScreenStream不返回bounds，这步用uiautomator）
    """
    import xml.etree.ElementTree as ET
    tmp = os.path.join(os.environ.get("TEMP", "/tmp"), "ui_cards.xml")
    adb("shell", "uiautomator dump /sdcard/ui_dump.xml", t=8)
    adb("pull", "/sdcard/ui_dump.xml", tmp, t=5)
    try:
        root = ET.parse(tmp).getroot()
    except:
        return []

    cards = []
    for n in root.iter("node"):
        cl = n.get("clickable", "false")
        if cl != "true":
            continue
        b = n.get("bounds", "")
        cls = n.get("class", "")
        m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', b)
        if not m:
            continue
        x1, y1, x2, y2 = int(m[1]), int(m[2]), int(m[3]), int(m[4])
        h = y2 - y1
        w = x2 - x1
        # 订单卡片容器特征：宽>800, 高100-350, y在400-2200, 是LinearLayout
        if w > 800 and 100 < h < 350 and 400 < y1 < 2200 and "LinearLayout" in cls:
            # 检查是否是商品区域（非按钮行、非tab行）
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            # 排除tab区域(y<500) 和 action按钮行(h<130且含"更多""评价"等)
            if y1 > 500:
                cards.append({"cx": cx, "cy": cy, "y1": y1, "y2": y2, "h": h})

    return cards

def collect_taobao(max_orders=20):
    """淘宝深度采集主流程"""
    print("\n" + "=" * 50)
    print("🛒 淘宝订单深度提取")
    print("=" * 50)

    wake()
    time.sleep(1)
    if not taobao_navigate_to_orders():
        return []

    all_orders = []
    visited_sigs = set()
    scroll_count = 0
    empty_streak = 0

    while len(all_orders) < max_orders and scroll_count <= 25:
        # 找可点击的订单卡片容器
        cards = taobao_find_clickable_cards()

        # 过滤已访问的（用y坐标+页面签名去重）
        page_sig = screen_signature()
        new_cards = []
        for c in cards:
            key = f"{page_sig}_{c['cy']}"
            if key not in visited_sigs:
                new_cards.append(c)
                visited_sigs.add(key)

        if not new_cards:
            empty_streak += 1
            if empty_streak >= 3:
                print("  🛑 连续3屏无新订单，到底部")
                break
            print(f"  [滚动{scroll_count + 1}] 无新卡片，继续...")
            swipe_up()
            scroll_count += 1
            continue

        empty_streak = 0

        for card in new_cards:
            idx = len(all_orders) + 1
            # 先读列表页该位置附近的商品名
            list_texts = read_screen()
            product_hint = ""
            for t in list_texts:
                if len(t) > 15 and any('\u4e00' <= c <= '\u9fff' for c in t[:5]):
                    product_hint = t[:50]
                    break

            card_cy = card["cy"]
            print(f"\n  📦 订单{idx}: {product_hint or f'卡片y={card_cy}'}")

            # 双击进入详情页
            sig_before = screen_signature()
            double_tap(card["cx"], card["cy"])

            # 用ScreenStream读取（能读WebView）
            detail_texts = read_screen()
            sig_after = screen_signature()

            # 判断是否页面变化了
            if sig_after == sig_before or len(detail_texts) < 5:
                print(f"    ⚠ 页面未变化，跳过")
                continue

            # 检测是否在详情页
            combined = " ".join(detail_texts)
            is_detail = any(k in combined for k in
                           ["订单编号", "订单号", "创建时间", "下单时间",
                            "收货地址", "付款时间", "商品总价", "实付款"])

            if is_detail:
                info = extract_fields(detail_texts)

                # 首屏没有订单号？滚动看更多
                if not info["order_id"]:
                    swipe_up(400)
                    time.sleep(1)
                    more = read_screen()
                    info2 = extract_fields(more)
                    for k, v in info2.items():
                        if v and not info.get(k):
                            info[k] = v

                info["list_product"] = product_hint
                info["app"] = "taobao"
                all_orders.append(info)
                print(f"    ✅ {info['order_id'] or '?'} | ¥{info['total_paid'] or '?'} | {info['status'] or '?'}")
            else:
                # 可能进入了商品页/店铺页
                print(f"    ⚠ 非订单详情 (文本: {detail_texts[:3]})")

            # 返回列表
            back()
            time.sleep(1)
            if not screen_has("待付款", "待收货", "全部订单"):
                back()
                time.sleep(1)

        swipe_up()
        scroll_count += 1

    home()
    return all_orders

# ============================================================
# 拼多多深度采集
# ============================================================

def pdd_navigate_to_orders():
    """拼多多：force-stop → 启动 → 个人中心 → 全部订单"""
    print("  启动拼多多（干净状态）...")
    force_start("com.xunmeng.pinduoduo")

    for _ in range(3):
        if not dismiss_popup():
            break
        time.sleep(1)

    # 底部tab "个人中心"
    print("  → 个人中心")
    tap(919, 2220, wait=3)
    dismiss_popup()
    time.sleep(0.5)

    # 点击"我的订单"/"查看全部"
    print("  → 全部订单")
    # 拼多多"我的订单"区域通常在y=400-600
    # 用uiautomator找"全部"或"查看全部"
    import xml.etree.ElementTree as ET
    tmp = os.path.join(os.environ.get("TEMP", "/tmp"), "ui_pdd.xml")
    adb("shell", "uiautomator dump /sdcard/ui_dump.xml", t=8)
    adb("pull", "/sdcard/ui_dump.xml", tmp, t=5)
    try:
        root = ET.parse(tmp).getroot()
        for n in root.iter("node"):
            txt = n.get("text", "").strip() + n.get("content-desc", "").strip()
            if any(k in txt for k in ["全部订单", "查看全部", "我的订单"]):
                b = n.get("bounds", "")
                bm = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', b)
                if bm:
                    cx = (int(bm[1]) + int(bm[3])) // 2
                    cy = (int(bm[2]) + int(bm[4])) // 2
                    tap(cx, cy, wait=3)
                    break
    except:
        pass

    if screen_has("待发货", "待收货", "全部"):
        print("  ✅ 已进入拼多多订单列表")
        return True
    print("  ❌ 未能进入拼多多订单列表")
    return False

def pdd_find_order_cards():
    """拼多多订单列表：找可点击的商品卡片
    拼多多比淘宝简单——商品名文本通常可以直接点击
    """
    import xml.etree.ElementTree as ET
    tmp = os.path.join(os.environ.get("TEMP", "/tmp"), "ui_pdd.xml")
    adb("shell", "uiautomator dump /sdcard/ui_dump.xml", t=8)
    adb("pull", "/sdcard/ui_dump.xml", tmp, t=5)
    try:
        root = ET.parse(tmp).getroot()
    except:
        return []

    cards = []
    skip = {"评价", "退货", "售后", "再次购买", "物流", "客服",
            "催发货", "确认收货", "待付款", "待发货", "待收货", "全部"}
    for n in root.iter("node"):
        t = n.get("text", "").strip()
        b = n.get("bounds", "")
        bm = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', b)
        if not bm:
            continue
        x1, y1, x2, y2 = int(bm[1]), int(bm[2]), int(bm[3]), int(bm[4])
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        # 商品名：长中文文本，y在300-2100
        if (len(t) > 12 and 300 < cy < 2100
            and any('\u4e00' <= c <= '\u9fff' for c in t[:5])
            and not any(k in t for k in skip)):
            cards.append({"product": t, "cx": cx, "cy": cy})

    return cards

def collect_pdd(max_orders=20):
    """拼多多深度采集"""
    print("\n" + "=" * 50)
    print("🍊 拼多多订单深度提取")
    print("=" * 50)

    wake()
    time.sleep(1)
    if not pdd_navigate_to_orders():
        return []

    all_orders = []
    visited = set()
    empty_streak = 0

    for scroll in range(25):
        cards = pdd_find_order_cards()
        new_cards = [c for c in cards if c["product"][:25] not in visited]

        if not new_cards:
            empty_streak += 1
            if empty_streak >= 3:
                print("  🛑 到底部")
                break
            swipe_up()
            continue

        empty_streak = 0
        for card in new_cards:
            key = card["product"][:25]
            if key in visited:
                continue
            visited.add(key)

            idx = len(all_orders) + 1
            print(f"\n  📦 订单{idx}: {card['product'][:50]}")

            sig_before = screen_signature()
            tap(card["cx"], card["cy"], wait=3)

            # 用ScreenStream读详情页（能读WebView）
            detail_texts = read_screen()
            combined = " ".join(detail_texts)

            if any(k in combined for k in ["订单编号", "订单号", "收货信息", "物流信息", "实付"]):
                info = extract_fields(detail_texts)
                if not info["order_id"]:
                    swipe_up(400)
                    time.sleep(1)
                    info2 = extract_fields(read_screen())
                    for k, v in info2.items():
                        if v and not info.get(k):
                            info[k] = v
                info["list_product"] = card["product"][:100]
                info["app"] = "pdd"
                all_orders.append(info)
                print(f"    ✅ {info['order_id'] or '?'} | ¥{info['total_paid'] or '?'} | {info['status'] or '?'}")
            else:
                print(f"    ⚠ 非详情页")

            back()
            time.sleep(1)
            if not screen_has("待发货", "待收货", "全部"):
                back()
                time.sleep(1)

        swipe_up()

    home()
    return all_orders

# ============================================================
# 输出
# ============================================================

def save_results(orders_by_app):
    """保存JSON + MD报告"""
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')

    # JSON
    all_data = {
        "meta": {
            "timestamp": datetime.now().isoformat(),
            "device": "OnePlus NE2210",
            "method": "ADB + ScreenStream API (双击进详情, AccessibilityService读WebView)"
        },
        **orders_by_app
    }
    json_path = os.path.join(OUT, f"深度订单_{ts}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

    # MD报告
    md_path = os.path.join(OUT, f"深度订单报告_{ts}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# 手机购物订单深度提取报告\n\n")
        f.write(f"> 时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"> 方法: ADB双击进详情 + ScreenStream AccessibilityService读WebView\n\n")

        app_names = {"taobao": "🛒 淘宝", "pdd": "🍊 拼多多"}
        for app_key, orders in orders_by_app.items():
            name = app_names.get(app_key, app_key)
            f.write(f"## {name} ({len(orders)}笔)\n\n")
            if not orders:
                f.write("无数据\n\n")
                continue

            f.write("| # | 订单号 | 日期 | 商品 | 实付 | 状态 | 店铺 |\n")
            f.write("|---|--------|------|------|------|------|------|\n")
            total = 0
            for i, o in enumerate(orders, 1):
                prod = (o.get("products") or [o.get("list_product", "")])[0][:35]
                paid = o.get("total_paid", "?")
                try:
                    total += float(paid)
                except:
                    pass
                f.write(f"| {i} | {o.get('order_id', '?')[:18]} "
                        f"| {o.get('order_date', '?')[:12]} "
                        f"| {prod} | ¥{paid} "
                        f"| {o.get('status', '?')} "
                        f"| {o.get('store', '?')[:12]} |\n")
            f.write(f"\n**总计: ¥{total:.2f}**\n\n")

    print(f"\n📊 JSON: {json_path}")
    print(f"📄 报告: {md_path}")
    return json_path, md_path

# ============================================================
# 入口
# ============================================================

def preflight():
    """飞行前检查：设备连接 + ScreenStream API可用"""
    # ADB
    out = adb("devices")
    if S not in out:
        print(f"❌ 设备 {S} 未连接")
        print(f"  ADB输出: {out}")
        return False

    # ScreenStream端口转发
    ss_setup()

    # API可用性
    data = ss_get("/status")
    if data is None:
        print(f"❌ ScreenStream API不可用 (端口{SS_PORT})")
        print("  请确认ScreenStream正在运行且投屏已启动")
        return False

    print(f"✅ 设备 {S} 已连接, ScreenStream API正常")
    return True

def main():
    print("=" * 60)
    print("📱 手机购物订单深度提取器 v2")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📱 OnePlus NE2210 ({S})")
    print(f"🔗 ScreenStream API @ port {SS_PORT}")
    print("=" * 60)

    if not preflight():
        return

    results = {}

    # 淘宝
    tb = collect_taobao(max_orders=20)
    results["taobao"] = tb
    print(f"\n淘宝: {len(tb)}笔")

    # 拼多多
    pdd = collect_pdd(max_orders=20)
    results["pdd"] = pdd
    print(f"\n拼多多: {len(pdd)}笔")

    # 保存
    save_results(results)

    print("\n" + "=" * 60)
    grand = sum(len(v) for v in results.values())
    print(f"✅ 深度提取完成! 共{grand}笔订单")
    for k, v in results.items():
        print(f"   {k}: {len(v)}笔")
    print("=" * 60)

if __name__ == "__main__":
    main()
