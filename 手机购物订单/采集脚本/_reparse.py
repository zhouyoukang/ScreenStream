"""从原始dump中重新正确提取订单数据"""
import json, re, os
from datetime import datetime

_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
RAW = os.path.join(_ROOT, "原始数据")
OUT = os.path.join(_ROOT, "解析结果")

# ── PDD详情页解析 ─────────────────────────────────────────
def parse_pdd_detail(texts):
    joined = " ".join(texts)
    info = {}

    # 订单编号
    m = re.search(r'订单编号[：:]\s*(\d[\d\-]+\d)', joined)
    if m: info["order_id"] = m.group(1)

    # 下单时间
    m = re.search(r'下单时间[：:]\s*(20\d{2}[\-./]\d{2}[\-./]\d{2}\s*\d{2}:\d{2}:\d{2})', joined)
    if m: info["date"] = m.group(1)

    # 商品名称（格式：商品名称：xxx,单价: xx 元）
    m = re.search(r'商品名称[：:]([^,]+),单价', joined)
    if m: info["product"] = m.group(1).strip()[:80]

    # 单价
    m = re.search(r'单价:\s*(\d+\.?\d*)\s*元', joined)
    if m: info["unit_price"] = m.group(1)

    # 实付（模式：实付:xxx元 或 实付:平台大促9.51元,0元）
    m = re.search(r'实付[：:][^\d]*(\d+\.?\d*)\s*元', joined)
    if m: info["paid"] = m.group(1)

    # 应付
    m = re.search(r'应付[：:][^\d]*(\d+\.?\d*)\s*元', joined)
    if m: info["total"] = m.group(1)

    # 状态
    for s in ["交易已取消","退款成功","已签收","待发货","待收货",
              "交易成功","已完成","待评价","已发货"]:
        if s in joined:
            info["status"] = s
            break

    # 店铺
    for t in texts:
        t = t.strip()
        if any(k in t for k in ["旗舰店","专营店","数码店","官方店","食品店","自营"]):
            if len(t) < 30:
                info["store"] = t
                break

    # 收货人
    m = re.search(r'收货人信息:\s*([^,]+)', joined)
    if m: info["receiver"] = m.group(1).strip()

    # 地址
    m = re.search(r'地址[：:]\s*(.+?)(?:\s{2}|$)', joined)
    if m: info["address"] = m.group(1).strip()[:60]

    info["app"] = "pdd"
    return info

# ── PDD列表页解析 ─────────────────────────────────────────
def parse_pdd_screens(screens):
    """从列表页屏幕文本中提取订单（补充详情页未覆盖的）"""
    orders = []
    status_set = {"已签收","待发货","待收货","已取消","退款成功",
                  "交易成功","已完成","待评价","拼单中","待付款","交易已取消"}
    skip = {"全部","待付款","待发货","待收货","退款/售后","筛选",
            "搜索","评价","退货","催发货","确认收货","查看物流",
            "再次购买","删除","客服","多人团","拼单详情","我的订单",
            "个人中心","物流详情","更多","暂无进行中订单","查看全部",
            "待评价","售后"}

    seen_products = set()
    for screen in screens:
        texts = screen.get("texts", [])
        i = 0
        while i < len(texts):
            t = texts[i].strip()
            i += 1
            if not t or len(t) < 3 or t in skip:
                continue

            # 商品名特征：长中文文本
            if (len(t) > 10 and any('\u4e00' <= c <= '\u9fff' for c in t[:5])
                and t[:20] not in seen_products
                and not any(k in t for k in ["旗舰店","专营店","快递","签收",
                    "确认","返回","搜索","地址","评价","客服","物流"])):
                # 可能是商品名，向后看找价格和状态
                product = t[:80]
                price = ""
                status = ""
                for j in range(i, min(i+8, len(texts))):
                    tj = texts[j].strip()
                    pm = re.match(r'^[¥￥](\d+\.?\d*)$', tj)
                    if pm and not price:
                        price = pm.group(1)
                    if tj in status_set and not status:
                        status = tj

                if product[:20] not in seen_products:
                    seen_products.add(product[:20])
                    orders.append({
                        "product": product,
                        "paid": price,
                        "status": status,
                        "app": "pdd",
                        "source": "list"
                    })

    return orders

# ── JD解析 ────────────────────────────────────────────────
def parse_jd_screens(screens):
    orders = []
    seen = set()
    for screen in screens:
        texts = screen.get("texts", [])
        for i, t in enumerate(texts):
            t = t.strip()
            if (len(t) > 10 and any('\u4e00' <= c <= '\u9fff' for c in t[:5])
                and t[:20] not in seen
                and not any(k in t for k in ["返回","搜索","全部","筛选","待付款",
                    "待收货","待发货","评价","退换","客服","京东","我的订单"])):
                price = ""
                status = ""
                for j in range(max(0,i-5), min(i+8, len(texts))):
                    tj = texts[j].strip()
                    pm = re.search(r'[¥￥](\d+\.?\d*)', tj)
                    if pm and not price:
                        price = pm.group(1)
                    for s in ["已完成","待收货","待发货","已取消","待评价","已签收","退款中"]:
                        if s in tj:
                            status = s
                seen.add(t[:20])
                orders.append({"product": t[:80], "paid": price, "status": status, "app": "jd"})
    return orders

# ── 闲鱼解析 ──────────────────────────────────────────────
def parse_xianyu_screens(screens):
    orders = []
    seen = set()
    for screen in screens:
        texts = screen.get("texts", [])
        for i, t in enumerate(texts):
            t = t.strip()
            if (len(t) > 8 and any('\u4e00' <= c <= '\u9fff' for c in t[:5])
                and t[:20] not in seen
                and not any(k in t for k in ["返回","搜索","全部","我买到","闲鱼","客服",
                    "卖了换钱","我卖出","帮助","消息","首页","鱼塘"])):
                price = ""
                status = ""
                for j in range(max(0,i-3), min(i+5, len(texts))):
                    tj = texts[j].strip()
                    pm = re.search(r'[¥￥](\d+\.?\d*)', tj)
                    if pm and not price:
                        price = pm.group(1)
                    for s in ["交易成功","已发货","待发货","已关闭","待付款","已退款"]:
                        if s in tj:
                            status = s
                seen.add(t[:20])
                orders.append({"product": t[:80], "paid": price, "status": status, "app": "xianyu"})
    return orders

# ── 早期淘宝数据 ──────────────────────────────────────────
def parse_earlier_taobao():
    """解析早期采集的淘宝文本文件"""
    orders = []
    fp = os.path.join(RAW, "shopping_FINAL.txt")
    if not os.path.exists(fp):
        return orders

    with open(fp, encoding="utf-8") as f:
        content = f.read()

    # 找所有商品条目
    seen = set()
    for line in content.split("\n"):
        line = line.strip()
        if not line:
            continue
        # 尝试解析结构化行
        if "¥" in line or "元" in line:
            parts = line.split("|")
            if len(parts) >= 2:
                product = parts[0].strip()[:80]
                if product[:20] not in seen and len(product) > 5:
                    seen.add(product[:20])
                    price = ""
                    pm = re.search(r'[¥￥](\d+\.?\d*)', line)
                    if pm: price = pm.group(1)
                    orders.append({"product": product, "paid": price, "app": "taobao"})

    return orders

# ── 主流程 ────────────────────────────────────────────────
def main():
    all_orders = []

    # 1. PDD详情页
    pdd_file = os.path.join(RAW, "dumps", "pdd_raw.json")
    if os.path.exists(pdd_file):
        d = json.load(open(pdd_file, encoding="utf-8"))
        print("=== PDD详情页 ===")
        detail_products = set()
        for i, det in enumerate(d["details"]):
            all_t = det.get("texts", []) + det.get("texts_page2", [])
            info = parse_pdd_detail(all_t)
            if info.get("product"):
                detail_products.add(info["product"][:20])
                info["source"] = "detail"
                all_orders.append(info)
                print("  #{}: {} | {} | {} | {}".format(
                    i+1, info.get("product","?")[:35],
                    info.get("paid") or info.get("unit_price","?"),
                    info.get("status","?"), info.get("order_id","?")))

        # 2. PDD列表页补充
        print("\n=== PDD列表页补充 ===")
        list_orders = parse_pdd_screens(d["screens"])
        for o in list_orders:
            if o["product"][:20] not in detail_products:
                all_orders.append(o)
                print("  + {} | {} | {}".format(o["product"][:35], o.get("paid","?"), o.get("status","?")))

    # 3. JD
    jd_file = os.path.join(RAW, "dumps", "jd_raw.json")
    if os.path.exists(jd_file):
        d = json.load(open(jd_file, encoding="utf-8"))
        print("\n=== 京东 ===")
        jd_orders = parse_jd_screens(d["screens"])
        for o in jd_orders:
            all_orders.append(o)
            print("  {} | {} | {}".format(o["product"][:35], o.get("paid","?"), o.get("status","?")))

    # 4. 闲鱼
    xy_file = os.path.join(RAW, "dumps", "xianyu_raw.json")
    if os.path.exists(xy_file):
        d = json.load(open(xy_file, encoding="utf-8"))
        print("\n=== 闲鱼 ===")
        xy_orders = parse_xianyu_screens(d["screens"])
        for o in xy_orders:
            all_orders.append(o)
            print("  {} | {} | {}".format(o["product"][:35], o.get("paid","?"), o.get("status","?")))

    # 5. 早期淘宝
    print("\n=== 淘宝(早期数据) ===")
    tb_orders = parse_earlier_taobao()
    for o in tb_orders:
        all_orders.append(o)
        print("  {} | {}".format(o["product"][:35], o.get("paid","?")))

    # 6. 也看看extract_now.py的结果
    en_file = os.path.join(OUT, "订单_20260224_194554.json")
    if os.path.exists(en_file):
        ed = json.load(open(en_file, encoding="utf-8"))
        seen = set(o.get("product","")[:20] for o in all_orders)
        for o in ed.get("orders", []):
            if o.get("product","")[:20] not in seen:
                seen.add(o["product"][:20])
                all_orders.append(o)

    # ── 生成报告 ──
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    jp = os.path.join(OUT, "重解析订单_{}.json".format(ts))
    with open(jp, "w", encoding="utf-8") as f:
        json.dump({"meta": {"time": datetime.now().isoformat(),
                           "method": "从原始dump重新正确解析"},
                   "orders": all_orders}, f, ensure_ascii=False, indent=2)

    mp = os.path.join(OUT, "重解析订单报告_{}.md".format(ts))
    with open(mp, "w", encoding="utf-8") as f:
        f.write("# 手机购物订单重解析报告\n\n")
        f.write("> 时间: {}\n".format(datetime.now().strftime("%Y-%m-%d %H:%M")))
        f.write("> 方法: 从原始UI dump文件重新正确提取\n\n")

        apps = {}
        for o in all_orders:
            apps.setdefault(o.get("app","?"), []).append(o)

        names = {"pdd":"拼多多","jd":"京东","xianyu":"闲鱼","taobao":"淘宝"}
        grand_total = 0
        for app_key in ["taobao","pdd","jd","xianyu"]:
            if app_key not in apps: continue
            ords = apps[app_key]
            f.write("## {} ({}笔)\n\n".format(names.get(app_key,app_key), len(ords)))
            f.write("| # | 商品 | 金额 | 状态 | 店铺 | 订单号 | 日期 |\n")
            f.write("|---|------|------|------|------|--------|------|\n")
            total = 0
            for i, o in enumerate(ords, 1):
                p = o.get("paid") or o.get("unit_price") or o.get("price") or "?"
                try: total += float(p); grand_total += float(p)
                except: pass
                f.write("| {} | {} | {} | {} | {} | {} | {} |\n".format(
                    i, o.get("product","?")[:30],
                    "¥"+str(p), o.get("status","?"),
                    o.get("store","")[:15],
                    o.get("order_id","")[:22],
                    o.get("date","")[:19]))
            f.write("\n**小计: ¥{:.2f}**\n\n".format(total))

        f.write("---\n\n**总计: ¥{:.2f}** ({}笔)\n\n".format(grand_total, len(all_orders)))
        f.write("### 数据完整性\n\n")
        has_id = sum(1 for o in all_orders if o.get("order_id"))
        has_date = sum(1 for o in all_orders if o.get("date"))
        has_paid = sum(1 for o in all_orders if o.get("paid") or o.get("unit_price"))
        f.write("| 指标 | 数量 | 比例 |\n")
        f.write("|------|------|------|\n")
        f.write("| 有订单号 | {} | {:.0f}% |\n".format(has_id, has_id/max(len(all_orders),1)*100))
        f.write("| 有日期 | {} | {:.0f}% |\n".format(has_date, has_date/max(len(all_orders),1)*100))
        f.write("| 有金额 | {} | {:.0f}% |\n".format(has_paid, has_paid/max(len(all_orders),1)*100))

    print("\n" + "="*50)
    print("共{}笔订单".format(len(all_orders)))
    for a, ords in apps.items():
        print("  {}: {}笔".format(names.get(a,a), len(ords)))
    print("JSON: {}".format(jp))
    print("报告: {}".format(mp))

if __name__ == "__main__":
    main()
