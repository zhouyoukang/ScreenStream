"""全量订单采集器 — 暴力dump策略
不做实时解析，先收集所有原始数据，再离线提取。
每个APP：导航到订单列表 → 深度滚动dump每屏 → 逐单钻入详情页dump
"""
import subprocess, time, os, re, json, xml.etree.ElementTree as ET
from datetime import datetime

_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_DIR)
ADB = os.path.join(_ROOT, "..", "构建部署", "android-sdk", "platform-tools", "adb.exe")
SN = "158377ff"
RAW = os.path.join(_ROOT, "原始数据", "dumps")
OUT = os.path.join(_ROOT, "解析结果")
TMP = os.path.join(os.environ.get("TEMP", "/tmp"), "ui_dump.xml")
os.makedirs(RAW, exist_ok=True)
os.makedirs(OUT, exist_ok=True)

# ── ADB ───────────────────────────────────────────────────
def adb(*a, t=10):
    try:
        r = subprocess.run([ADB, "-s", SN] + list(a),
            capture_output=True, text=True, timeout=t, encoding='utf-8', errors='replace')
        return r.stdout.strip()
    except: return ""

def tap(x, y, w=0.5):  adb("shell", f"input tap {x} {y}"); time.sleep(w)
def back(w=1.5):        adb("shell", "input keyevent KEYCODE_BACK"); time.sleep(w)
def home():             adb("shell", "input keyevent KEYCODE_HOME"); time.sleep(0.5)
def swipe_up(slow=False):
    d = 800 if slow else 400
    adb("shell", f"input swipe 540 1700 540 700 {d}"); time.sleep(1.2)
def wake():             adb("shell", "input keyevent KEYCODE_WAKEUP"); time.sleep(0.5)
def force_start(pkg):
    adb("shell", f"am force-stop {pkg}"); time.sleep(1)
    adb("shell", f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1"); time.sleep(5)

# ── dump核心 ──────────────────────────────────────────────
def dump_nodes():
    """uiautomator dump → 完整节点列表"""
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
        if not m: continue
        x1, y1, x2, y2 = int(m[1]), int(m[2]), int(m[3]), int(m[4])
        nodes.append({"t": txt, "d": desc, "cl": cl, "cls": cls,
                      "cx": (x1+x2)//2, "cy": (y1+y2)//2,
                      "w": x2-x1, "h": y2-y1, "y1": y1, "y2": y2})
    return nodes

def get_texts(nodes):
    """去重保序提取所有文本"""
    seen, out = set(), []
    for n in nodes:
        for v in [n["t"], n["d"]]:
            if v and v not in seen:
                seen.add(v); out.append(v)
    return out

def has(nodes, *kws):
    t = " ".join(get_texts(nodes))
    return any(k in t for k in kws)

def dismiss(nodes):
    for kw in ["允许","同意","确定","我知道了","跳过","关闭","以后再说","暂不","知道了","不再提醒","残忍拒绝","拒绝"]:
        for n in nodes:
            if kw == n["t"] or kw == n["d"]:
                tap(n["cx"], n["cy"]); time.sleep(0.5); return True
    return False

def find_and_tap(nodes, *keywords, y_range=None):
    """找到包含关键词的节点并点击"""
    for kw in keywords:
        for n in nodes:
            v = n["t"] + n["d"]
            if kw in v:
                if y_range and not (y_range[0] <= n["cy"] <= y_range[1]):
                    continue
                tap(n["cx"], n["cy"], w=2)
                return True
    return False

# ── 通用滚动采集 ─────────────────────────────────────────
def scroll_collect(app_name, max_scrolls=40, detail_click=True):
    """通用的订单列表滚动采集：
    1. 逐屏dump所有文本（保存原始数据）
    2. 找可点击的订单卡片，逐个钻入详情页dump
    返回：{screens: [...], details: [...]}
    """
    all_screens = []
    all_details = []
    prev_texts_sig = ""
    empty = 0
    detail_visited = set()

    for scroll_idx in range(max_scrolls):
        nodes = dump_nodes()
        cur_texts = get_texts(nodes)
        cur_sig = "|".join(cur_texts[:20])

        # 检测是否到底（连续相同内容）
        if cur_sig == prev_texts_sig:
            empty += 1
            if empty >= 4:
                print(f"    🛑 到底 (第{scroll_idx}屏)")
                break
        else:
            empty = 0
        prev_texts_sig = cur_sig

        # 保存屏幕原始数据
        screen_data = {"idx": scroll_idx, "texts": cur_texts, "node_count": len(nodes)}
        all_screens.append(screen_data)

        # 找可点击的"大块"容器（订单卡片）用于钻入详情
        if detail_click:
            clickable_cards = []
            for n in nodes:
                if (n["cl"] and n["w"] > 700 and 150 < n["h"] < 400
                    and n["y1"] > 350 and n["y2"] < 2200
                    and n["cls"] in ("LinearLayout", "FrameLayout", "ViewGroup", "RelativeLayout", "View")):
                    # 去重：用y坐标范围
                    card_key = f"{n['cy']//50}"
                    if card_key not in detail_visited:
                        clickable_cards.append(n)
                        detail_visited.add(card_key)

            for card in clickable_cards:
                # 点击进入详情
                tap(card["cx"], card["cy"], w=3)
                detail_nodes = dump_nodes()
                detail_texts = get_texts(detail_nodes)

                # 判断页面是否变化（进入了详情）
                detail_sig = "|".join(detail_texts[:10])
                if detail_sig != cur_sig[:len(detail_sig)] and len(detail_texts) > 3:
                    # 保存详情页首屏
                    detail = {"texts": detail_texts}

                    # 在详情页向下滚动看更多信息
                    swipe_up(slow=True)
                    time.sleep(0.8)
                    more_nodes = dump_nodes()
                    more_texts = get_texts(more_nodes)
                    detail["texts_page2"] = more_texts

                    all_details.append(detail)
                    print(f"    📋 详情页 ({len(detail_texts)}+{len(more_texts)} 文本)")

                # 返回列表
                back(w=1.5)
                # 验证回到列表
                check = dump_nodes()
                if not has(check, "待付款", "待收货", "全部", "订单"):
                    back(w=1)

        swipe_up(slow=True)
        print(f"    📜 第{scroll_idx+1}屏: {len(cur_texts)}条文本, 累计{len(all_details)}个详情")

    return {"screens": all_screens, "details": all_details}

# ── APP导航 ───────────────────────────────────────────────

def nav_taobao():
    """淘宝 → 我的 → 全部订单"""
    force_start("com.taobao.taobao")
    for _ in range(3):
        nd = dump_nodes()
        if not dismiss(nd): break
    tap(972, 2196, w=3)  # 我的淘宝
    nd = dump_nodes(); dismiss(nd)
    tap(967, 791, w=3)   # 全部订单 (实测坐标)
    nd = dump_nodes()
    if has(nd, "待付款", "待收货", "全部订单"):
        return True
    # 备选
    find_and_tap(nd, "全部", y_range=(350,500))
    time.sleep(2)
    return has(dump_nodes(), "待付款", "待收货")

def nav_pdd():
    """拼多多 → 个人中心 → 全部订单"""
    force_start("com.xunmeng.pinduoduo")
    for _ in range(3):
        nd = dump_nodes()
        if not dismiss(nd): break
    # 个人中心
    nd = dump_nodes()
    if not find_and_tap(nd, "个人中心", y_range=(2000,2300)):
        tap(919, 2220, w=3)
    else:
        time.sleep(2)
    nd = dump_nodes(); dismiss(nd)
    # 查看全部订单
    find_and_tap(nd, "查看全部", "全部订单", "我的订单")
    time.sleep(2)
    return has(dump_nodes(), "待发货", "待收货", "全部")

def nav_jd():
    """京东 → 我的 → 全部订单"""
    force_start("com.jingdong.app.mall")
    for _ in range(3):
        nd = dump_nodes()
        if not dismiss(nd): break
    # 我的tab
    nd = dump_nodes()
    if not find_and_tap(nd, "我的", y_range=(2000,2300)):
        tap(972, 2196, w=3)
    else:
        time.sleep(2)
    nd = dump_nodes(); dismiss(nd)
    # 全部订单
    if not find_and_tap(nd, "全部订单", "查看全部", "我的订单"):
        # 京东"全部"可能在订单区域
        find_and_tap(nd, "全部", y_range=(400,1000))
    time.sleep(3)
    return has(dump_nodes(), "待付款", "待收货", "全部")

def nav_eleme():
    """饿了么 → 我的 → 全部订单"""
    force_start("me.ele")
    for _ in range(3):
        nd = dump_nodes()
        if not dismiss(nd): break
    nd = dump_nodes()
    if not find_and_tap(nd, "我的", y_range=(2000,2300)):
        tap(972, 2196, w=3)
    else:
        time.sleep(2)
    nd = dump_nodes(); dismiss(nd)
    find_and_tap(nd, "全部订单", "查看全部", "我的订单", "历史订单")
    time.sleep(3)
    return has(dump_nodes(), "订单", "待付款", "待收货", "已完成")

def nav_xianyu():
    """闲鱼 → 我的 → 我买到的"""
    force_start("com.taobao.idlefish")
    for _ in range(3):
        nd = dump_nodes()
        if not dismiss(nd): break
    nd = dump_nodes()
    if not find_and_tap(nd, "我的", y_range=(2000,2300)):
        tap(972, 2196, w=3)
    else:
        time.sleep(2)
    nd = dump_nodes(); dismiss(nd)
    find_and_tap(nd, "我买到的", "购买记录", "全部订单")
    time.sleep(3)
    return has(dump_nodes(), "订单", "买到", "全部")

def nav_douyin():
    """抖音 → 我 → 订单"""
    force_start("com.ss.android.ugc.aweme")
    for _ in range(5):
        nd = dump_nodes()
        if not dismiss(nd): break
        time.sleep(1)
    nd = dump_nodes()
    if not find_and_tap(nd, "我", y_range=(2000,2300)):
        tap(972, 2196, w=3)
    else:
        time.sleep(2)
    nd = dump_nodes(); dismiss(nd)
    # 抖音商城订单入口
    if not find_and_tap(nd, "全部订单", "我的订单", "订单"):
        find_and_tap(nd, "更多", y_range=(300,800))
        time.sleep(1)
        nd = dump_nodes()
        find_and_tap(nd, "订单")
    time.sleep(3)
    return has(dump_nodes(), "订单", "待付款", "全部")

# ── 离线解析 ──────────────────────────────────────────────

def parse_orders(app, raw_data):
    """从原始dump数据中离线提取订单"""
    orders = []
    seen = set()

    # 合并所有屏幕的文本
    all_text_blocks = []
    for s in raw_data.get("screens", []):
        all_text_blocks.append(s["texts"])

    # 从详情页提取（最精确）
    for d in raw_data.get("details", []):
        info = _extract_from_detail(d.get("texts", []) + d.get("texts_page2", []))
        if info and info.get("product"):
            key = info["product"][:25]
            if key not in seen:
                seen.add(key)
                info["app"] = app
                info["source"] = "detail"
                orders.append(info)

    # 从列表页补充（详情页可能遗漏的）
    for texts in all_text_blocks:
        list_orders = _extract_from_list(texts, app)
        for o in list_orders:
            key = o["product"][:25]
            if key not in seen:
                seen.add(key)
                o["source"] = "list"
                orders.append(o)

    return orders

def _extract_from_detail(texts):
    """从详情页文本提取单个订单完整信息"""
    info = {"product": "", "order_id": "", "order_date": "", "store": "",
            "price": "", "paid": "", "status": "", "quantity": "",
            "shipping": "", "address": ""}

    status_set = {"交易成功","交易关闭","待发货","已发货","已签收","待收货",
                  "待付款","退款成功","退款中","已取消","已完成","待评价",
                  "已收货","配送中","已送达","已退款"}

    for i, t in enumerate(texts):
        t = t.strip()
        if not t: continue
        # 订单号
        if re.match(r'^\d{12,25}$', t) and not info["order_id"]:
            info["order_id"] = t
        # 日期
        if not info["order_date"] and re.match(r'20\d{2}[年.\-/]\d{1,2}[月.\-/]\d{1,2}', t):
            info["order_date"] = t
        # 状态
        if t in status_set:
            info["status"] = t
        # 价格/实付
        pm = re.search(r'[¥￥](\d+\.?\d*)', t)
        if pm:
            val = pm.group(1)
            if "实付" in t or "实际" in t or "合计" in t:
                info["paid"] = val
            elif not info["price"]:
                info["price"] = val
        # 店铺
        if any(k in t for k in ["旗舰店","专营店","自营","官方店","企业店"]) and len(t) < 30:
            info["store"] = t
        # 地址
        if ("省" in t and "市" in t) or "收货" in t:
            if len(t) > 8:
                info["address"] = t[:60]
        # 物流
        if ("快递" in t or "物流" in t or "签收" in t) and len(t) > 5:
            if "查看" not in t:
                info["shipping"] = t[:60]
        # 商品名
        if (len(t) > 12 and not info["product"]
            and any('\u4e00' <= c <= '\u9fff' for c in t[:5])
            and t not in status_set
            and not any(k in t for k in ["旗舰店","专营店","快递","签收","确认","返回",
                                          "搜索","收货地址","付款","运费","客服","评价"])):
            info["product"] = t[:100]

    if not info["paid"] and info["price"]:
        info["paid"] = info["price"]
    return info if info["product"] else None

def _extract_from_list(texts, app):
    """从列表页一屏文本中提取订单（宽松匹配）"""
    orders = []
    status_set = {"交易成功","交易关闭","待发货","已发货","已签收","待收货",
                  "待付款","退款成功","已取消","已完成","待评价","拼单中",
                  "已收货","配送中","已送达","已退款","退款中"}
    skip = {"全部","待付款","待发货","待收货","退款/售后","筛选","管理",
            "搜索","暂无","查看全部","评价","退货","售后","催发货",
            "确认收货","查看物流","延长收货","再买一单","闲鱼转卖",
            "更多","删除","申请","投诉","回到顶部","反馈","更多操作",
            "退货宝","假一赔四","极速退款","7天无理由退货","先用后付",
            "大促价保","合计","实付款","拼单详情","多人团","物流详情",
            "客服","收藏","分享","加购物车"}

    current = None
    for t in texts:
        t = t.strip()
        if not t or len(t) < 2: continue

        # 跳过UI文本
        if t in skip or any(t.startswith(s) for s in ["未选中","已选中"]): continue
        if "按钮" in t: continue

        # 价格
        pm = re.match(r'^[¥￥](\d+\.?\d*)$', t)
        if pm:
            if current:
                current["price"] = pm.group(1)
            continue

        # 数量
        qm = re.match(r'^[×x](\d+)$', t)
        if qm:
            if current:
                current["quantity"] = qm.group(1)
            continue

        # 状态 → 新订单的开始标志
        if t in status_set:
            if current and current.get("product"):
                orders.append(current)
            current = {"product": "", "price": "", "quantity": "1",
                      "status": t, "store": "", "app": app,
                      "order_id": "", "order_date": "", "paid": ""}
            continue

        if current is None:
            # 还没遇到第一个状态，检查是否是店铺名（也可以作为订单开始标志）
            if any(k in t for k in ["旗舰店","专营店","自营","官方店"]) and len(t) < 25:
                current = {"product": "", "price": "", "quantity": "1",
                          "status": "", "store": t, "app": app,
                          "order_id": "", "order_date": "", "paid": ""}
            continue

        # 店铺名
        if any(k in t for k in ["旗舰店","专营店","自营","官方店","企业店"]) and len(t) < 25:
            if current.get("product"):
                orders.append(current)
            current = {"product": "", "price": "", "quantity": "1",
                      "status": "", "store": t, "app": app,
                      "order_id": "", "order_date": "", "paid": ""}
            continue

        # 商品名（长中文文本）
        if (len(t) > 10 and not current.get("product")
            and any('\u4e00' <= c <= '\u9fff' for c in t[:5])):
            current["product"] = t[:100]

    if current and current.get("product"):
        orders.append(current)

    return orders

# ── 报告生成 ──────────────────────────────────────────────

def generate_report(all_orders):
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')

    # JSON
    jp = os.path.join(OUT, f"全量订单_{ts}.json")
    with open(jp, "w", encoding="utf-8") as f:
        json.dump({"meta": {"time": datetime.now().isoformat(),
                           "device": f"OnePlus NE2210 ({SN})"},
                   "orders": all_orders}, f, ensure_ascii=False, indent=2)

    # MD
    mp = os.path.join(OUT, f"全量订单报告_{ts}.md")
    with open(mp, "w", encoding="utf-8") as f:
        f.write("# 手机购物订单全量采集报告\n\n")
        f.write(f"> 采集时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"> 设备: OnePlus NE2210\n\n")

        apps = {}
        for o in all_orders:
            a = o.get("app", "unknown")
            apps.setdefault(a, []).append(o)

        grand_total = 0
        for app_key in ["taobao","pdd","jd","eleme","xianyu","douyin","tianmao","dianping"]:
            if app_key not in apps: continue
            orders = apps[app_key]
            names = {"taobao":"🛒 淘宝","pdd":"🍊 拼多多","jd":"🔴 京东",
                     "eleme":"🔵 饿了么","xianyu":"🐟 闲鱼","douyin":"🎵 抖音",
                     "tianmao":"🐱 天猫","dianping":"📍 大众点评"}
            f.write(f"## {names.get(app_key, app_key)} ({len(orders)}笔)\n\n")
            f.write("| # | 商品 | 金额 | 状态 | 店铺 | 订单号 | 日期 | 来源 |\n")
            f.write("|---|------|------|------|------|--------|------|------|\n")
            total = 0
            for i, o in enumerate(orders, 1):
                p = o.get("paid") or o.get("price", "?")
                try: total += float(p); grand_total += float(p)
                except: pass
                f.write(f"| {i} | {o['product'][:28]} | ¥{p} "
                        f"| {o.get('status','?')} | {o.get('store','')[:12]} "
                        f"| {o.get('order_id','')[:16]} | {o.get('order_date','')[:10]} "
                        f"| {o.get('source','')} |\n")
            f.write(f"\n**小计: ¥{total:.2f}** ({len(orders)}笔)\n\n")

        f.write(f"---\n\n**总计: ¥{grand_total:.2f}** ({len(all_orders)}笔)\n")

    print(f"\n📊 {jp}")
    print(f"📄 {mp}")
    return jp, mp

# ── 主流程 ────────────────────────────────────────────────

APPS = [
    ("taobao",  "🛒 淘宝",   nav_taobao),
    ("pdd",     "🍊 拼多多",  nav_pdd),
    ("jd",      "🔴 京东",    nav_jd),
    ("eleme",   "🔵 饿了么",  nav_eleme),
    ("xianyu",  "🐟 闲鱼",   nav_xianyu),
    ("douyin",  "🎵 抖音",    nav_douyin),
]

def main():
    print("=" * 60)
    print(f"📱 全量订单采集 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📱 OnePlus NE2210 ({SN})")
    print("=" * 60)

    out = adb("devices")
    if SN not in out:
        print("❌ 设备未连接"); return

    wake()
    all_orders = []
    raw_dumps = {}

    for app_key, app_name, nav_func in APPS:
        print(f"\n{'='*50}")
        print(f"{app_name} 订单采集")
        print(f"{'='*50}")

        try:
            ok = nav_func()
        except Exception as e:
            print(f"  ❌ 导航失败: {e}")
            home(); continue

        if not ok:
            print(f"  ❌ 无法进入{app_name}订单页，跳过")
            home(); continue

        print(f"  ✅ 进入{app_name}订单列表，开始深度采集...")
        raw = scroll_collect(app_name, max_scrolls=40, detail_click=True)
        raw_dumps[app_key] = raw

        # 保存原始dump
        dump_file = os.path.join(RAW, f"{app_key}_raw.json")
        with open(dump_file, "w", encoding="utf-8") as f:
            json.dump(raw, f, ensure_ascii=False, indent=2)

        # 离线解析
        orders = parse_orders(app_key, raw)
        all_orders.extend(orders)
        print(f"\n  📊 {app_name}: {len(orders)}笔订单 ({len(raw['screens'])}屏, {len(raw['details'])}个详情)")

        home()
        time.sleep(1)

    # 生成报告
    generate_report(all_orders)

    print("\n" + "=" * 60)
    apps_summary = {}
    for o in all_orders:
        a = o.get("app", "?")
        apps_summary[a] = apps_summary.get(a, 0) + 1
    print(f"✅ 全量采集完成! 共{len(all_orders)}笔订单")
    for a, c in apps_summary.items():
        print(f"   {a}: {c}笔")
    print("=" * 60)

if __name__ == "__main__":
    main()
