"""精准重解析 v2 — 只信任可靠信号，彻底去噪
PDD: "店铺名称：" "订单状态：" "商品名称：" "商品价格：" 前缀
闲鱼: "订单信息, ¥X.XX" 边界标记
JD: 需要重新分析
淘宝: 早期浅层数据 + extract_now结果
"""
import json, re, os
from datetime import datetime

_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
RAW = os.path.join(_ROOT, "原始数据")
OUT = os.path.join(_ROOT, "解析结果")

# ══════════════════════════════════════════════════════════
# PDD 精准解析
# ══════════════════════════════════════════════════════════

def parse_pdd_all():
    """PDD: 详情页(主) + 列表页(补充)"""
    fp = os.path.join(RAW, "dumps", "pdd_raw.json")
    if not os.path.exists(fp): return []
    d = json.load(open(fp, encoding="utf-8"))
    orders = []
    seen = set()

    # ── 详情页（最可靠）──
    for det in d["details"]:
        all_t = det.get("texts", []) + det.get("texts_page2", [])
        joined = " ".join(all_t)
        info = {"app": "pdd", "source": "detail"}

        m = re.search(r'订单编号[：:]\s*(\d[\d\-]+\d)', joined)
        if m: info["order_id"] = m.group(1)

        m = re.search(r'下单时间[：:]\s*(20\d{2}[\-./]\d{2}[\-./]\d{2}\s*\d{2}:\d{2}:\d{2})', joined)
        if m: info["date"] = m.group(1)

        m = re.search(r'商品名称[：:]([^,]+),单价', joined)
        if m: info["product"] = m.group(1).strip()[:80]
        elif not info.get("product"):
            # fallback: 找长中文文本
            for t in all_t:
                if len(t) > 15 and any('\u4e00' <= c <= '\u9fff' for c in t[:5]):
                    if not any(k in t for k in ["店铺","商品名称","订单","返回","复制","拼单","查看","删除"]):
                        info["product"] = t[:80]; break

        m = re.search(r'单价:\s*(\d+\.?\d*)\s*元', joined)
        if m: info["unit_price"] = m.group(1)

        m = re.search(r'实付[：:][^\d]*(\d+\.?\d*)\s*元', joined)
        if m: info["paid"] = m.group(1)

        m = re.search(r'应付[：:][^\d]*(\d+\.?\d*)\s*元', joined)
        if m and not info.get("paid"): info["paid"] = m.group(1)

        for s in ["交易已取消","退款成功","已签收","待发货","待收货","交易成功","已完成","待评价","已发货"]:
            if s in joined: info["status"] = s; break

        for t in all_t:
            if any(k in t for k in ["旗舰店","专营店","数码店","官方","食品"]) and len(t) < 30 and "店铺名称" not in t:
                info["store"] = t; break

        m = re.search(r'收货人信息:\s*([^,]+)', joined)
        if m: info["receiver"] = m.group(1).strip()

        if info.get("product"):
            key = info["product"][:20]
            if key not in seen:
                seen.add(key)
                orders.append(info)

    # ── 列表页（用前缀标记识别真实订单卡片）──
    noise_markers = ["已售", "全网热销", "券后价", "淘宝秒杀", "直降",
                     "关注", "推荐", "闪购", "国补", "穿搭", "飞猪",
                     "搜索栏", "拍立淘", "首页", "视频", "购物车",
                     "我的淘宝", "领225元", "88VIP"]

    for screen in d["screens"]:
        texts = screen["texts"]
        joined_screen = " ".join(texts)
        # 如果屏幕包含推荐流标记，跳过整屏
        if any(nm in joined_screen for nm in noise_markers):
            continue

        # 找"店铺名称："开头的订单卡片
        i = 0
        while i < len(texts):
            t = texts[i]
            if t.startswith("店铺名称："):
                # 新订单卡片开始
                store = t.replace("店铺名称：", "").strip()
                card = {"app": "pdd", "source": "list", "store": store}
                # 向后扫描直到下一个"店铺名称："或屏幕结束
                j = i + 1
                while j < len(texts) and not texts[j].startswith("店铺名称："):
                    tj = texts[j]
                    if tj.startswith("订单状态："):
                        card["status"] = tj.replace("订单状态：", "").strip()
                    elif tj.startswith("商品名称："):
                        card["product"] = tj.replace("商品名称：", "").strip()[:80]
                    elif tj.startswith("商品价格："):
                        m = re.search(r'(\d+\.?\d*)', tj)
                        if m: card["unit_price"] = m.group(1)
                    elif "实付:" in tj or "实付：" in tj:
                        pass  # 实付金额通常在下一行
                    elif re.match(r'^\d+\.?\d*$', tj) and not card.get("paid"):
                        # 纯数字行可能是实付金额（出现在"实付:"之后）
                        if j > 0 and ("实付" in texts[j-1] or "应付" in texts[j-1]):
                            card["paid"] = tj
                    elif re.match(r'^[¥￥](\d+\.?\d*)$', tj):
                        m = re.match(r'^[¥￥](\d+\.?\d*)$', tj)
                        if m and not card.get("unit_price"):
                            card["unit_price"] = m.group(1)
                    j += 1

                if card.get("product"):
                    key = card["product"][:20]
                    if key not in seen:
                        seen.add(key)
                        if not card.get("paid"):
                            card["paid"] = card.get("unit_price", "")
                        orders.append(card)
                i = j
            else:
                i += 1

    return orders

# ══════════════════════════════════════════════════════════
# 闲鱼精准解析
# ══════════════════════════════════════════════════════════

def parse_xianyu_all():
    """闲鱼订单解析 — 基于实测UI结构:
    每个订单卡片:
      '订单信息, ¥X.XX'           ← 边界+价格
      '卖家名, 卖家名'            ← 逗号分隔重复
      '状态, 状态'                ← 可选
      '商品名, 商品名'            ← 逗号分隔重复
      '规格:xxx, 规格:xxx'        ← 可选
      'xxx，按钮, xxx'            ← 操作按钮(跳过)
    """
    fp = os.path.join(RAW, "dumps", "xianyu_raw.json")
    if not os.path.exists(fp): return []
    d = json.load(open(fp, encoding="utf-8"))
    orders = []
    seen = set()

    status_keywords = ["交易成功", "交易关闭", "退款", "待发货", "待收货",
                       "等待见面", "等待卖家", "已发货", "已签收"]
    skip_keywords = ["按钮", "好评", "中评", "差评", "交易完成",
                     "购物体验", "评价让", "满意度", "分享一下",
                     "宝贝好不好", "返回", "筛选", "第 "]

    for screen in d["screens"]:
        texts = screen["texts"]
        i = 0
        while i < len(texts):
            t = texts[i]
            if not t.startswith("订单信息"):
                i += 1
                continue

            price_m = re.search(r'[¥￥](\d+\.?\d*)', t)
            price = price_m.group(1) if price_m else ""

            seller = ""
            product = ""
            status = ""
            spec = ""

            # 向后扫描（闲鱼格式：每项都是 "text, text" 重复格式）
            for j in range(i + 1, min(i + 12, len(texts))):
                tj = texts[j]
                if tj.startswith("订单信息"):
                    break

                # 跳过按钮和评价提示
                if any(k in tj for k in skip_keywords):
                    continue

                # 取逗号前半部分（闲鱼每项格式是 "内容, 内容"）
                part = tj.split(", ")[0].strip() if ", " in tj else tj.strip()

                # 状态
                if any(sk in part for sk in status_keywords):
                    if not status:
                        status = part
                    continue

                # 规格（"规格:xxx", "类型:xxx", etc.）
                if re.match(r'^(规格|类型|份数|时间|套餐|天数|积分|数量)[：:]', part):
                    spec = part
                    continue

                # 纯数字行（跳过）
                if re.match(r'^[¥￥×x]?\d', part) and len(part) < 10:
                    continue

                # 卖家名 vs 商品名：
                # - 卖家名通常短（<15字），在商品名之前出现
                # - 商品名通常长（>10字）或包含品牌/描述性词汇
                if not seller and not product:
                    if len(part) > 15 or any(k in part for k in ["Windsurf","spacedesk","京东","会员","软件","电脑","押金","海上"]):
                        product = part[:80]
                    else:
                        seller = part[:20]
                elif seller and not product:
                    product = part[:80]

            # 如果只有seller没有product，seller可能就是商品
            if not product and seller:
                product = seller
                seller = ""

            if price:
                # 用价格+商品前缀去重
                key = price + "|" + (product or seller or "")[:15]
                if key not in seen:
                    seen.add(key)
                    orders.append({
                        "app": "xianyu",
                        "product": product or "(未识别商品)",
                        "paid": price,
                        "status": status,
                        "store": seller,
                        "spec": spec,
                        "source": "list"
                    })

            i += 1

    return orders

# ══════════════════════════════════════════════════════════
# 京东解析
# ══════════════════════════════════════════════════════════

def parse_jd_all():
    fp = os.path.join(RAW, "dumps", "jd_raw.json")
    if not os.path.exists(fp): return []
    d = json.load(open(fp, encoding="utf-8"))
    orders = []
    seen = set()

    # 先看JD列表页的结构
    for screen in d["screens"]:
        texts = screen["texts"]
        joined = " ".join(texts)
        # 跳过非订单页
        if not any(k in joined for k in ["待付款","待收货","已完成","全部订单"]):
            continue

        i = 0
        while i < len(texts):
            t = texts[i]
            # JD状态标记（订单卡片起始信号）
            jd_statuses = {"已完成","待收货","待发货","已取消","待付款","待评价","已签收","退款中"}
            if t in jd_statuses:
                status = t
                product = ""
                price = ""
                store = ""
                # 向后找商品名和价格
                for j in range(i+1, min(i+15, len(texts))):
                    tj = texts[j]
                    if tj in jd_statuses: break  # 下一个订单
                    if len(tj) > 10 and any('\u4e00' <= c <= '\u9fff' for c in tj[:5]) and not product:
                        if not any(k in tj for k in ["退换","客服","评价","删除","再次","取消","京东","全部订单"]):
                            product = tj[:80]
                    pm = re.search(r'[¥￥](\d+\.?\d*)', tj)
                    if pm and not price:
                        price = pm.group(1)
                    if "自营" in tj or "旗舰店" in tj or "专营店" in tj:
                        store = tj[:20]

                if product:
                    key = product[:20]
                    if key not in seen:
                        seen.add(key)
                        orders.append({"app": "jd", "product": product, "paid": price,
                                      "status": status, "store": store, "source": "list"})
            i += 1

    return orders

# ══════════════════════════════════════════════════════════
# 淘宝（已有浅层数据）
# ══════════════════════════════════════════════════════════

def parse_taobao_existing():
    """从extract_now.py的结果中提取"""
    fp = os.path.join(OUT, "订单_20260224_194554.json")
    if not os.path.exists(fp): return []
    d = json.load(open(fp, encoding="utf-8"))
    orders = []
    for o in d.get("orders", []):
        if o.get("app") == "taobao" and o.get("product"):
            orders.append({
                "app": "taobao", "product": o["product"][:80],
                "paid": o.get("price", ""), "status": o.get("status", ""),
                "store": o.get("store", ""), "source": "list"
            })
    return orders

# ══════════════════════════════════════════════════════════
# 报告
# ══════════════════════════════════════════════════════════

def generate_report(all_orders):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    jp = os.path.join(OUT, "精准订单_{}.json".format(ts))
    with open(jp, "w", encoding="utf-8") as f:
        json.dump({"meta": {"time": datetime.now().isoformat(),
                           "method": "从原始dump精准提取(v2去噪)"},
                   "orders": all_orders}, f, ensure_ascii=False, indent=2)

    mp = os.path.join(OUT, "精准订单报告_{}.md".format(ts))
    apps = {}
    for o in all_orders:
        apps.setdefault(o.get("app", "?"), []).append(o)

    with open(mp, "w", encoding="utf-8") as f:
        f.write("# 手机购物订单精准报告\n\n")
        f.write("> 时间: {}\n".format(datetime.now().strftime("%Y-%m-%d %H:%M")))
        f.write("> 方法: 原始UI dump精准提取 (v2去噪去重)\n\n")

        names = {"taobao": "淘宝", "pdd": "拼多多", "jd": "京东", "xianyu": "闲鱼"}
        icons = {"taobao": "🛒", "pdd": "🍊", "jd": "🔴", "xianyu": "🐟"}
        grand_total = 0
        grand_count = 0

        for app_key in ["taobao", "pdd", "jd", "xianyu"]:
            if app_key not in apps: continue
            ords = apps[app_key]
            icon = icons.get(app_key, "")
            name = names.get(app_key, app_key)
            f.write("## {} {} ({}笔)\n\n".format(icon, name, len(ords)))
            f.write("| # | 商品 | 金额 | 状态 | 店铺 | 订单号 | 日期 |\n")
            f.write("|---|------|------|------|------|--------|------|\n")
            total = 0
            for i, o in enumerate(ords, 1):
                p = o.get("paid") or o.get("unit_price") or ""
                try: total += float(p)
                except: pass
                f.write("| {} | {} | {} | {} | {} | {} | {} |\n".format(
                    i,
                    o.get("product", "?")[:35],
                    "¥" + p if p else "?",
                    o.get("status", ""),
                    o.get("store", "")[:15],
                    o.get("order_id", "")[:22],
                    o.get("date", "")[:19]))
            f.write("\n**小计: ¥{:.2f}** ({}笔)\n\n".format(total, len(ords)))
            grand_total += total
            grand_count += len(ords)

        f.write("---\n\n")
        f.write("**总计: ¥{:.2f}** ({}笔)\n\n".format(grand_total, grand_count))

        # 数据质量
        f.write("### 数据完整性\n\n")
        has_id = sum(1 for o in all_orders if o.get("order_id"))
        has_date = sum(1 for o in all_orders if o.get("date"))
        has_paid = sum(1 for o in all_orders if o.get("paid") or o.get("unit_price"))
        has_store = sum(1 for o in all_orders if o.get("store"))
        n = max(len(all_orders), 1)
        f.write("| 指标 | 数量/总数 | 完整率 |\n")
        f.write("|------|----------|--------|\n")
        f.write("| 有订单号 | {}/{} | {:.0f}% |\n".format(has_id, n, has_id/n*100))
        f.write("| 有日期 | {}/{} | {:.0f}% |\n".format(has_date, n, has_date/n*100))
        f.write("| 有金额 | {}/{} | {:.0f}% |\n".format(has_paid, n, has_paid/n*100))
        f.write("| 有店铺 | {}/{} | {:.0f}% |\n".format(has_store, n, has_store/n*100))

        f.write("\n### 待补采\n\n")
        f.write("- **淘宝**: 仅4单(浅层), 需重新深度采集全部订单+详情页\n")
        f.write("- **拼多多**: 详情页仅覆盖前9单, 其余需补采详情\n")
        f.write("- **京东**: 仅列表页数据, 需进详情页补全订单号/日期\n")
        f.write("- **闲鱼**: 仅列表页, 需进详情页补全\n")
        f.write("- **饿了么/抖音/天猫**: 未采集\n")

    print("JSON: {}".format(jp))
    print("报告: {}".format(mp))
    return jp, mp

# ══════════════════════════════════════════════════════════

def main():
    print("="*55)
    print("精准重解析 v2 | {}".format(datetime.now().strftime("%Y-%m-%d %H:%M")))
    print("="*55)

    all_orders = []

    tb = parse_taobao_existing()
    print("淘宝: {}笔".format(len(tb)))
    all_orders.extend(tb)

    pdd = parse_pdd_all()
    print("拼多多: {}笔".format(len(pdd)))
    all_orders.extend(pdd)

    jd = parse_jd_all()
    print("京东: {}笔".format(len(jd)))
    all_orders.extend(jd)

    xy = parse_xianyu_all()
    print("闲鱼: {}笔".format(len(xy)))
    all_orders.extend(xy)

    print("\n共: {}笔".format(len(all_orders)))
    generate_report(all_orders)

if __name__ == "__main__":
    main()
