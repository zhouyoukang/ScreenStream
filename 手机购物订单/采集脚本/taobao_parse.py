"""淘宝订单语义解析 — 从原始uiautomator数据中重建完整订单
解决数据偏见: UI噪声/价格多义/跨屏断裂/名称截断
"""
import re, json, os

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_SCRIPT_DIR)  # 手机购物订单/
RAW_FILE = os.path.join(_ROOT, "原始数据", "shopping_records_20260223_133514.txt")
OUT = os.path.join(_ROOT, "解析结果")

# ============ 语义分类器 ============

# UI噪声模式 — 直接丢弃
NOISE = [
    "返回","跳往搜索页","搜索订单","筛选","订单管理","管理","消息 按钮",
    "全部订单未选中","购物已选中","闪购未选中","飞猪未选中",
    "全部","待付款","待发货","待收货","退款/售后",
    "全部未选中","待付款未选中","待发货未选中","待收货未选中","退款/售后未选中",
    "全部已选中","关闭","回到顶部","合计",
    "退货宝","假一赔四","极速退款","7天无理由退货",
    "先用后付","确认收货后再付款","可提前付款",
    "更多","更多操作","延长收货","查看物流","确认收货",
    "加入购物车","闲鱼转卖","评价","再买一单","删除订单","申请开票",
    "大促价保","小贴士","普通水凝膜","反馈","催发货","修改地址",
    "支付宝","今日闪购请客，抽中免单","降价补差",
]

# 订单分界状态 — 表示上一个订单结束/下一个订单区域开始
BOUNDARY_STATUSES = ["交易关闭","交易成功","已签收","已签收,待确认收货"]

def classify_line(line):
    """将每行分类为语义角色"""
    line = line.strip()
    if not line or line.startswith("---") or line.startswith("==") or line.startswith("#"):
        return "skip", line

    # 精确匹配噪声
    if line in NOISE:
        return "noise", line

    # 含"未选中"/"已选中"/"按钮"的
    if any(k in line for k in ["未选中","已选中","按钮"]):
        return "noise", line

    # 价格
    if line.startswith("¥") or line.startswith("￥"):
        val = line.replace("¥","").replace("￥","").strip()
        try:
            return "price", float(val)
        except:
            return "price_text", line

    # 数量 ×N
    m = re.match(r'×(\d+)', line)
    if m:
        return "qty", int(m.group(1))

    # 订单状态
    statuses = {
        "已发货": "已发货", "卖家已发货": "已发货",
        "已签收": "已签收", "已签收,待确认收货": "已签收(待确认)",
        "交易关闭": "交易关闭", "交易成功": "交易成功",
        "待寄出": "待退货寄出",
    }
    if line in statuses:
        return "status", statuses[line]

    # 发货期限
    m = re.match(r'(\d{1,2}月\d{1,2}日\s*\d{1,2}:\d{2})前发货', line)
    if m:
        return "ship_deadline", m.group(1)

    # 物流信息(签收/快递/取件码)
    if any(k in line for k in ["签收","快递","取件码","已签收","自提柜","驿站","包裹"]):
        return "shipping", line

    # 退货提示
    if "请在" in line and "寄出" in line:
        return "return_notice", line

    # 店铺名(末尾含特征词)
    store_patterns = ["旗舰店","专营店","专卖店","书店","书城","书社","数码","制袋厂"]
    if any(line.endswith(k) or k in line for k in store_patterns):
        if len(line) < 30:
            return "store", line
    # 确定的店铺名
    if line in ["上海蓬达电子","百佳龙数码","深圳金海龙数码","博智书店","八卦鼠惠隆达专卖店"]:
        return "store", line

    # 商品名(长文本,含中文)
    if len(line) > 15 and any('\u4e00' <= c <= '\u9fff' for c in line[:8]):
        if not any(k in line for k in ["签收","快递","驿站","投诉","联系"]):
            return "product", line

    # 短文本可能是操作按钮或其他噪声
    if len(line) < 5:
        return "noise_short", line

    # 物流详情(长文本含地址)
    if "已签收" in line or "妥投" in line:
        return "shipping", line

    # 商品被拆分
    if "拆分" in line and "包裹" in line:
        return "split_notice", line

    # 实付款标记
    if line == "实付款":
        return "paid_marker", line

    return "unknown", line

# ============ 订单重建引擎 ============

def new_order(store=""):
    return {
        "store": store,
        "products": [],
        "prices": [],
        "qty": None,
        "status": "",
        "ship_deadline": "",
        "shipping": [],
        "return_notice": "",
        "split": False,
        "paid_marker": False,
    }

def rebuild_orders(lines):
    """从分类后的行重建完整订单
    关键改进:
    1. 状态词(交易关闭/交易成功)后出现新商品名→新订单
    2. 同店铺连续出现不同状态→不同订单
    3. 价格只归属到当前订单，遇到新store/status boundary就截断
    """
    orders = []
    current = None
    saw_boundary_status = False  # 上一行是否是分界状态

    # 先分类每行
    classified = []
    for line in lines:
        role, value = classify_line(line)
        if role != "skip":
            classified.append((role, value, line))

    for i, (role, value, raw) in enumerate(classified):
        if role in ("noise", "noise_short"):
            continue

        # --- 订单边界检测 ---
        start_new = False

        if role == "store":
            start_new = True

        elif role == "status" and value in ["交易关闭","交易成功","已签收(待确认)"]:
            # 这是一个分界状态 — 标记，看下一个非噪声行
            if current:
                current["status"] = current["status"] or value
            saw_boundary_status = True
            continue

        elif saw_boundary_status and role == "product":
            # 分界状态后出现新商品名 → 新订单(可能同店铺)
            start_new = True

        elif saw_boundary_status and role == "store":
            start_new = True

        if role not in ("status",) and value not in BOUNDARY_STATUSES:
            saw_boundary_status = False

        if start_new:
            if current and (current["products"] or current["prices"]):
                finalize_order(current)
                orders.append(current)
            store_name = value if role == "store" else (current["store"] if current else "")
            current = new_order(store_name)
            if role == "product":
                current["products"].append(value)
            continue

        # --- 字段归属 ---
        if current is None:
            continue

        if role == "product":
            current["products"].append(value)
        elif role == "price":
            current["prices"].append(value)
        elif role == "qty":
            current["qty"] = value
        elif role == "status":
            if not current["status"]:
                current["status"] = value
        elif role == "ship_deadline":
            current["ship_deadline"] = value
        elif role == "shipping":
            current["shipping"].append(value[:100])
        elif role == "return_notice":
            current["return_notice"] = value
        elif role == "split_notice":
            current["split"] = True
        elif role == "paid_marker":
            current["paid_marker"] = True

    if current and (current["products"] or current["prices"]):
        finalize_order(current)
        orders.append(current)

    return orders

def finalize_order(order):
    """根据价格列表推断单价/总价/实付"""
    prices = order["prices"]
    qty = order.get("qty")

    if not prices:
        order["unit_price"] = "?"
        order["total"] = "?"
        order["analysis"] = "无价格信息"
        return

    if len(prices) == 1:
        order["unit_price"] = prices[0]
        order["total"] = prices[0]
        order["analysis"] = "单价=总价(1件或无数量信息)"

    elif len(prices) == 2:
        if qty and qty > 1:
            # 第一个是单价，第二个是总价
            order["unit_price"] = prices[0]
            order["total"] = prices[1]
            expected = round(prices[0] * qty, 2)
            if abs(expected - prices[1]) < 0.1:
                order["analysis"] = f"单价×{qty}=总价 ✓"
            else:
                order["analysis"] = f"单价{prices[0]}×{qty}≠总价{prices[1]}(含运费?)"
        else:
            # 可能是两个不同商品的价格，或单价+运费
            order["unit_price"] = prices[0]
            order["total"] = prices[1]
            order["analysis"] = f"两个价格:{prices[0]}和{prices[1]}(可能含运费或折扣)"

    elif len(prices) >= 3:
        # 多个价格：单价/总价/运费/折扣等
        order["unit_price"] = prices[0]
        order["total"] = max(prices)  # 最大值可能是总价
        order["analysis"] = f"{len(prices)}个价格值,最大{max(prices)}可能是总价"

    # 清理
    del order["prices"]
    del order["paid_marker"]

# ============ 主流程 ============

def main():
    # 读取原始数据中的淘宝部分
    with open(RAW_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    # 提取淘宝区段
    m = re.search(r'## 淘宝\n={60}\n(.*?)(?=\n={60}\n## |\Z)', content, re.DOTALL)
    if not m:
        print("❌ 未找到淘宝数据段")
        return

    taobao_lines = m.group(1).strip().split("\n")
    print(f"📊 淘宝原始数据: {len(taobao_lines)}行")

    # 分类统计
    role_counts = {}
    for line in taobao_lines:
        role, _ = classify_line(line)
        role_counts[role] = role_counts.get(role, 0) + 1

    print(f"\n🏷️ 语义分类统计:")
    for role, count in sorted(role_counts.items(), key=lambda x:-x[1]):
        print(f"  {role:15s}: {count:3d}")

    # 重建订单
    orders = rebuild_orders(taobao_lines)
    print(f"\n📦 重建出 {len(orders)} 笔订单")

    # 输出结构化报告
    report = os.path.join(OUT, "淘宝订单解构.md")
    with open(report, "w", encoding="utf-8") as f:
        f.write("# 淘宝订单深度解构\n\n")
        f.write("> 方法: 语义解析引擎 — 从uiautomator原始数据中重建完整订单\n")
        f.write("> 解决的偏见: UI噪声过滤 / 价格多义消歧 / 跨屏断裂修复 / 数量推断\n\n")
        f.write(f"## 数据偏见分析\n\n")
        noise_total = sum(v for k,v in role_counts.items() if "noise" in k or k=="skip")
        signal_total = sum(v for k,v in role_counts.items() if k not in ["noise","noise_short","skip"])
        f.write(f"- 原始数据: **{len(taobao_lines)}行**\n")
        f.write(f"- UI噪声: **{noise_total}行** ({noise_total*100//len(taobao_lines)}%)\n")
        f.write(f"- 有效信号: **{signal_total}行** ({signal_total*100//len(taobao_lines)}%)\n")
        f.write(f"- 不可从列表页获取: 下单日期、订单号、实际支付方式、优惠券详情\n\n")

        f.write(f"## 订单明细 ({len(orders)}笔)\n\n")

        for i, o in enumerate(orders, 1):
            f.write(f"\n### 订单{i}: {o['store']}\n\n")
            f.write(f"| 字段 | 值 |\n|------|----|\n")
            f.write(f"| 店铺 | {o['store']} |\n")
            f.write(f"| 商品 | {'<br>'.join(o['products'][:3]) if o['products'] else '(商品名在其他屏)' } |\n")
            f.write(f"| 单价 | ¥{o.get('unit_price','?')} |\n")
            f.write(f"| 数量 | ×{o.get('qty','1')} |\n")
            f.write(f"| 总价 | ¥{o.get('total','?')} |\n")
            f.write(f"| 状态 | {o.get('status','?')} |\n")
            if o.get("ship_deadline"):
                f.write(f"| 发货期限 | {o['ship_deadline']} |\n")
            if o.get("shipping"):
                f.write(f"| 物流 | {o['shipping'][0][:60]} |\n")
            if o.get("return_notice"):
                f.write(f"| 退货 | {o['return_notice'][:60]} |\n")
            if o.get("split"):
                f.write(f"| 拆包 | 商品被拆分成2个包裹发货 |\n")
            f.write(f"| 价格分析 | {o.get('analysis','')} |\n")

        # 缺失信息说明
        f.write(f"\n## 列表页无法获取的信息\n\n")
        f.write("| 缺失字段 | 原因 | 获取方式 |\n")
        f.write("|----------|------|----------|\n")
        f.write("| 下单日期 | 订单列表页不展示 | 需点入订单详情页 |\n")
        f.write("| 订单编号 | 订单列表页不展示 | 需点入订单详情页 |\n")
        f.write("| 实际支付金额 | 列表页显示单价,不一定是最终付款 | 需点入订单详情页 |\n")
        f.write("| 优惠券/红包 | 列表页不展示 | 需点入订单详情页 |\n")
        f.write("| 收货地址 | 列表页不展示 | 需点入订单详情页 |\n")
        f.write("| 卖家留言 | 列表页不展示 | 需点入订单详情页 |\n\n")
        f.write("### 获取详情页的正确方法\n\n")
        f.write("淘宝订单卡片的**可点击区域**是商品图片和商品名，不是店铺名。\n")
        f.write("改进脚本应: 找到商品名节点 → 检查其clickable属性 → 点击进入详情。\n")

    # 同时保存JSON
    json_file = os.path.join(OUT, "淘宝订单解构.json")
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(orders, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n✅ 报告: {report}")
    print(f"📊 JSON: {json_file}")

if __name__ == "__main__":
    main()
