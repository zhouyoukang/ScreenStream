"""纯ADB订单采集器 — 无外部依赖，即连即跑
策略：列表页滚动采集（uiautomator） + 详情页尝试（WebView降级处理）
"""
import subprocess, time, os, re, json, xml.etree.ElementTree as ET
from datetime import datetime

_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_DIR)
ADB = os.path.join(_ROOT, "..", "构建部署", "android-sdk", "platform-tools", "adb.exe")
SN = "158377ff"
OUT = os.path.join(_ROOT, "解析结果")
TMP = os.path.join(os.environ.get("TEMP", "/tmp"), "ui_dump.xml")
os.makedirs(OUT, exist_ok=True)

# ── ADB 基础 ──────────────────────────────────────────────

def adb(*a, t=10):
    try:
        r = subprocess.run([ADB, "-s", SN] + list(a),
            capture_output=True, text=True, timeout=t, encoding='utf-8', errors='replace')
        return r.stdout.strip()
    except: return ""

def tap(x, y, w=0.3):  adb("shell", f"input tap {x} {y}"); time.sleep(w)
def back(w=1.5):        adb("shell", "input keyevent KEYCODE_BACK"); time.sleep(w)
def home():             adb("shell", "input keyevent KEYCODE_HOME"); time.sleep(0.5)
def swipe_up():         adb("shell", "input swipe 540 1800 540 600 500"); time.sleep(1.5)
def wake():             adb("shell", "input keyevent KEYCODE_WAKEUP"); time.sleep(0.5)

def force_start(pkg):
    adb("shell", f"am force-stop {pkg}"); time.sleep(1)
    adb("shell", f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1"); time.sleep(5)

# ── UI Dump ───────────────────────────────────────────────

def dump():
    """uiautomator dump → 解析全部节点"""
    adb("shell", "uiautomator dump /sdcard/ui_dump.xml", t=8)
    adb("pull", "/sdcard/ui_dump.xml", TMP, t=5)
    try: root = ET.parse(TMP).getroot()
    except: return []
    nodes = []
    for n in root.iter("node"):
        txt = n.get("text", "").strip()
        desc = n.get("content-desc", "").strip()
        b = n.get("bounds", "")
        cl = n.get("clickable", "false") == "true"
        cls = n.get("class", "").split(".")[-1]
        m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', b)
        if m:
            x1, y1, x2, y2 = int(m[1]), int(m[2]), int(m[3]), int(m[4])
            nodes.append({
                "t": txt, "d": desc, "cl": cl, "cls": cls,
                "cx": (x1+x2)//2, "cy": (y1+y2)//2,
                "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                "w": x2-x1, "h": y2-y1
            })
    return nodes

def texts(nodes):
    """提取所有文本（去重保序）"""
    seen, out = set(), []
    for n in nodes:
        for v in [n["t"], n["d"]]:
            if v and len(v) > 1 and v not in seen:
                seen.add(v); out.append(v)
    return out

def has_text(nodes, *kws):
    all_t = " ".join(texts(nodes))
    return any(k in all_t for k in kws)

def dismiss(nodes):
    for kw in ["允许","同意","确定","我知道了","跳过","关闭","以后再说","暂不","知道了"]:
        for n in nodes:
            if kw == n["t"] or kw == n["d"]:
                tap(n["cx"], n["cy"]); time.sleep(0.5); return True
    return False

# ── 淘宝采集 ──────────────────────────────────────────────

def taobao_collect():
    """淘宝：列表页逐屏采集（不进详情页，避免WebView盲区）"""
    print("\n" + "="*50)
    print("🛒 淘宝订单采集")
    print("="*50)

    force_start("com.taobao.taobao")
    for _ in range(3):
        nd = dump()
        if not dismiss(nd): break
        time.sleep(0.5)

    # 我的淘宝 tab
    print("  → 我的淘宝")
    tap(972, 2196, w=3)
    nd = dump(); dismiss(nd); time.sleep(0.5)

    # 全部订单（实测坐标 x=967, y=791）
    print("  → 全部订单")
    tap(967, 791, w=3)

    nd = dump()
    if not has_text(nd, "待付款", "待收货", "全部订单"):
        print("  ❌ 未进入订单页，尝试备选路径...")
        # 备选：找"全部"文本点击
        for n in nd:
            if n["t"] == "全部" and n["cy"] < 900 and n["cy"] > 700:
                tap(n["cx"], n["cy"], w=3); break
        nd = dump()
        if not has_text(nd, "待付款", "待收货"):
            print("  ❌ 无法进入订单页"); return []

    print("  ✅ 进入订单列表")

    # 逐屏滚动采集
    orders = []
    seen_products = set()
    empty = 0

    for scroll in range(30):
        nd = dump()
        # 解析当前屏的订单卡片
        screen_orders = _parse_taobao_list(nd)
        new_count = 0
        for o in screen_orders:
            key = o["product"][:25]
            if key not in seen_products:
                seen_products.add(key)
                orders.append(o)
                new_count += 1
                print(f"  📦 {len(orders)}: {o['product'][:40]} | ¥{o['price']} | {o['status']}")

        if new_count == 0:
            empty += 1
            if empty >= 3:
                print("  🛑 连续3屏无新订单，到底")
                break
        else:
            empty = 0

        swipe_up()

    home()
    return orders

def _parse_taobao_list(nodes):
    """从淘宝订单列表UI树中解析订单卡片
    结构模式：店铺名 → 状态 → 商品名 → 价格 → 数量 → [标签] → 实付款 → [物流] → 操作按钮
    """
    ts = texts(nodes)
    orders = []

    # 状态关键词
    status_set = {"已发货","交易成功","交易关闭","待发货","待收货","待付款",
                  "已签收","退款成功","退款中","已取消","待评价"}
    # 操作按钮（标记订单边界）
    action_set = {"延长收货","查看物流","确认收货","评价","闲鱼转卖",
                  "再买一单","更多","催发货","删除订单","申请售后"}
    # 标签（跳过）
    tag_set = {"退货宝","假一赔四","极速退款","7天无理由退货","先用后付",
               "大促价保","商品被拆分","品质保障","正品保证"}
    # 非商品名
    skip_product = status_set | action_set | tag_set | {
        "全部","待付款","待发货","待收货","退款/售后","筛选","管理",
        "搜索订单","暂无进行中订单","查看全部","实付款","合计"}

    # 从节点中提取结构化订单
    # 按y排序，找店铺→商品→价格模式
    sorted_nodes = sorted([n for n in nodes if (n["t"] or n["d"]) and n["cy"] > 400], key=lambda n: n["cy"])

    current = None
    for n in sorted_nodes:
        v = n["t"] or n["d"]
        if not v or len(v) < 2: continue

        # 店铺名（含"店"/"专营"/"数码"/"科技"等，或在节点右侧有状态）
        is_store = (any(k in v for k in ["旗舰店","专营店","官方店","企业店","自营"])
                   or (len(v) < 20 and n["cy"] > 500 and n["cx"] < 500
                       and any(s["t"] in status_set for s in sorted_nodes
                              if abs(s["cy"] - n["cy"]) < 30 and s["cx"] > 800)))
        if is_store and v not in skip_product:
            if current and current.get("product"):
                orders.append(current)
            current = {"store": v, "product": "", "price": "", "quantity": "",
                      "status": "", "shipping": "", "app": "taobao"}
            continue

        if current is None: continue

        # 状态
        if v in status_set and not current["status"]:
            current["status"] = v; continue

        # 价格
        pm = re.match(r'^[¥￥](\d+\.?\d*)$', v)
        if pm and not current["price"]:
            current["price"] = pm.group(1); continue

        # 数量
        qm = re.match(r'^[×x](\d+)$', v)
        if qm:
            current["quantity"] = qm.group(1); continue

        # 物流信息
        if "快递" in v or "护送" in v or "签收" in v:
            current["shipping"] = v[:60]; continue

        # 跳过标签和按钮
        if v in skip_product or v in tag_set: continue

        # 商品名（长中文文本）
        if (len(v) > 12 and not current["product"]
            and any('\u4e00' <= c <= '\u9fff' for c in v[:5])
            and v not in skip_product):
            current["product"] = v[:100]

    if current and current.get("product"):
        orders.append(current)

    return orders

# ── 拼多多采集 ────────────────────────────────────────────

def pdd_collect():
    """拼多多：列表页采集 + 详情页尝试"""
    print("\n" + "="*50)
    print("🍊 拼多多订单采集")
    print("="*50)

    force_start("com.xunmeng.pinduoduo")
    for _ in range(3):
        nd = dump()
        if not dismiss(nd): break
        time.sleep(0.5)

    # 个人中心
    print("  → 个人中心")
    nd = dump()
    found = False
    for n in nd:
        if "个人中心" in (n["t"] + n["d"]) and n["cy"] > 2000:
            tap(n["cx"], n["cy"], w=3); found = True; break
    if not found:
        tap(919, 2220, w=3)
    nd = dump(); dismiss(nd); time.sleep(0.5)

    # 全部订单
    print("  → 我的订单")
    nd = dump()
    for n in nd:
        v = n["t"] + n["d"]
        if any(k in v for k in ["查看全部", "全部订单", "我的订单"]) and n["cy"] < 1200:
            tap(n["cx"], n["cy"], w=3); break

    nd = dump()
    if not has_text(nd, "待发货", "待收货", "全部"):
        print("  ❌ 未进入订单页"); return []

    print("  ✅ 进入订单列表")

    orders = []
    seen = set()
    empty = 0

    for scroll in range(30):
        nd = dump()
        screen_orders = _parse_pdd_list(nd)
        new_count = 0
        for o in screen_orders:
            key = o["product"][:25]
            if key not in seen:
                seen.add(key)
                orders.append(o)
                new_count += 1
                print(f"  📦 {len(orders)}: {o['product'][:40]} | ¥{o['price']} | {o['status']}")

        if new_count == 0:
            empty += 1
            if empty >= 3:
                print("  🛑 到底")
                break
        else:
            empty = 0

        swipe_up()

    # 拼多多详情页尝试（逐单钻入）
    print("\n  📋 尝试补全订单号（逐单钻入详情）...")
    _pdd_fill_details(orders)

    home()
    return orders

def _parse_pdd_list(nodes):
    """从拼多多列表页解析订单"""
    orders = []
    sorted_n = sorted([n for n in nodes if n["t"] and n["cy"] > 300], key=lambda n: n["cy"])

    status_set = {"已签收","待发货","待收货","已取消","退款成功","交易成功",
                  "已完成","待评价","拼单中","待付款"}
    skip = {"评价","退货","售后","再次购买","物流详情","客服","催发货",
            "确认收货","查看物流","全部","待发货","待收货","待付款",
            "筛选","待评价","退款/售后","多人团","拼单详情"}

    current = None
    for n in sorted_n:
        v = n["t"]
        if not v or len(v) < 2: continue

        # 状态
        if v in status_set:
            if current and current.get("product"):
                orders.append(current)
            current = {"store": "", "product": "", "price": "", "quantity": "",
                      "status": v, "order_id": "", "app": "pdd"}
            continue

        if current is None: continue

        # 价格
        pm = re.match(r'^[¥￥](\d+\.?\d*)$', v)
        if pm and not current["price"]:
            current["price"] = pm.group(1); continue

        # 数量
        qm = re.match(r'^[×x](\d+)$', v)
        if qm:
            current["quantity"] = qm.group(1); continue

        if v in skip: continue

        # 商品名
        if (len(v) > 10 and not current["product"]
            and any('\u4e00' <= c <= '\u9fff' for c in v[:5])):
            current["product"] = v[:100]

    if current and current.get("product"):
        orders.append(current)

    return orders

def _pdd_fill_details(orders):
    """回到拼多多订单列表，逐单点击补全订单号"""
    if not orders: return

    # 重新导航到订单列表
    force_start("com.xunmeng.pinduoduo"); time.sleep(2)
    for _ in range(2):
        nd = dump()
        if not dismiss(nd): break

    # 个人中心 → 订单
    tap(919, 2220, w=3)
    nd = dump(); dismiss(nd)
    for n in nd:
        v = n["t"] + n["d"]
        if any(k in v for k in ["查看全部", "全部订单", "我的订单"]):
            tap(n["cx"], n["cy"], w=3); break

    filled = 0
    max_fill = min(len(orders), 10)  # 最多补全10单

    for i, order in enumerate(orders[:max_fill]):
        nd = dump()
        # 找到匹配的商品名
        target = None
        for n in nd:
            if order["product"][:20] in n["t"]:
                target = n; break

        if not target:
            # 商品不在当前屏，滚动找
            swipe_up()
            nd = dump()
            for n in nd:
                if order["product"][:20] in n["t"]:
                    target = n; break

        if not target: continue

        # 点击进入详情
        tap(target["cx"], target["cy"], w=3)
        detail = dump()
        detail_text = " ".join(texts(detail))

        # 提取订单号
        for t in texts(detail):
            if re.match(r'^\d{12,25}$', t):
                order["order_id"] = t
                filled += 1
                print(f"    ✅ 订单{i+1} 补全: {t}")
                break

        # 提取日期
        for t in texts(detail):
            if re.match(r'20\d{2}[.\-/]\d{1,2}[.\-/]\d{1,2}', t):
                order["order_date"] = t
                break

        back()
        time.sleep(1)

    print(f"  补全了 {filled}/{max_fill} 单的订单号")

# ── 输出 ──────────────────────────────────────────────────

def save(all_orders):
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')

    # JSON
    data = {
        "meta": {"time": datetime.now().isoformat(), "device": f"OnePlus NE2210 ({SN})",
                 "method": "纯ADB uiautomator列表采集 + 详情补全"},
        "orders": all_orders
    }
    jp = os.path.join(OUT, f"订单_{ts}.json")
    with open(jp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # MD报告
    mp = os.path.join(OUT, f"订单报告_{ts}.md")
    with open(mp, "w", encoding="utf-8") as f:
        f.write("# 手机购物订单采集报告\n\n")
        f.write(f"> 时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"> 设备: OnePlus NE2210\n")
        f.write(f"> 方法: ADB uiautomator列表采集 + 详情页补全\n\n")

        for app, name in [("taobao","🛒 淘宝"), ("pdd","🍊 拼多多")]:
            app_orders = [o for o in all_orders if o.get("app") == app]
            f.write(f"## {name} ({len(app_orders)}笔)\n\n")
            if not app_orders:
                f.write("无数据\n\n"); continue

            f.write("| # | 商品 | 单价 | 数量 | 状态 | 店铺 | 订单号 |\n")
            f.write("|---|------|------|------|------|------|--------|\n")
            total = 0
            for i, o in enumerate(app_orders, 1):
                p = o.get("price", "?")
                try: total += float(p)
                except: pass
                f.write(f"| {i} | {o['product'][:30]} | ¥{p} "
                        f"| {o.get('quantity','1')} | {o.get('status','?')} "
                        f"| {o.get('store','?')[:15]} "
                        f"| {o.get('order_id','')[:18]} |\n")
            f.write(f"\n**合计: ¥{total:.2f}** ({len(app_orders)}笔)\n\n")

    print(f"\n📊 {jp}")
    print(f"📄 {mp}")
    return jp, mp

# ── 入口 ──────────────────────────────────────────────────

def main():
    print("="*60)
    print(f"📱 手机购物订单采集器 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📱 OnePlus NE2210 ({SN}) | 纯ADB模式")
    print("="*60)

    # 验证连接
    out = adb("devices")
    if SN not in out:
        print(f"❌ 设备未连接"); return

    wake()
    all_orders = []

    tb = taobao_collect()
    all_orders.extend(tb)
    print(f"\n淘宝: {len(tb)}笔")

    pdd = pdd_collect()
    all_orders.extend(pdd)
    print(f"拼多多: {len(pdd)}笔")

    save(all_orders)

    print("\n" + "="*60)
    print(f"✅ 采集完成! 共{len(all_orders)}笔 (淘宝{len(tb)} + 拼多多{len(pdd)})")
    print("="*60)

if __name__ == "__main__":
    main()
