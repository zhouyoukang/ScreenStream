"""Agent大脑：解析已采集的淘宝订单原始文本，识别书籍订单并输出报告。"""
import re, json, os
from datetime import datetime

RAW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                   "原始数据", "taobao_agent_full.txt")
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "解析结果")

# 状态关键词
STATUSES = {
    "交易成功", "交易关闭", "交易成功,部分退款成功", "交易完结,全额退款",
    "已发货", "充值成功", "卖家已发货", "退款成功",
}
# 操作按钮（噪声）
BUTTONS = {
    "查看物流", "闲鱼转卖", "再买一单", "加入购物车", "评价", "追加评价",
    "确认收货", "延长收货", "删除订单", "申请开票", "再次充值", "反馈", "回到顶部",
}
# 标签（噪声）
TAGS = {
    "退货宝", "假一赔四", "极速退款", "7天无理由退货", "7天无理由退换",
    "15天价保", "15天退货", "不支持7天无理由", "大促价保", "小贴士", "手把手教你",
    "退款关闭", "退款已关闭", "退款成功", "平台支持退款", "7天价保",
    "公益捐赠0.02元",
}

def parse_orders(lines):
    """从原始文本行中解析订单列表"""
    orders = []
    current = None

    for line in lines:
        line = line.strip()
        if not line or line.startswith("=== SCREEN"):
            continue

        # 跳过按钮和标签
        if line in BUTTONS or line in TAGS:
            continue

        # 跳过支付方式
        if line in ("支付宝", "支付宝余额", "余额宝"):
            continue

        # 状态行 → 可能是新订单的一部分
        if line in STATUSES:
            if current:
                current["status"] = line
            continue

        # 价格行
        if line.startswith("¥"):
            val = line[1:].strip()
            try:
                fval = float(val)
            except:
                continue
            if current:
                if current.get("_next_is_paid"):
                    current["paid"] = val
                    current["_next_is_paid"] = False
                elif not current.get("unit_price"):
                    current["unit_price"] = val
                else:
                    current["last_price"] = val
            continue

        # 数量行
        m = re.match(r'^×(\d+)$', line)
        if m:
            if current:
                current["qty"] = int(m.group(1))
            continue

        # 实付款/合计/金额 标记 → 下一个¥值就是实付款
        if line in ("实付款", "合计", "金额"):
            if current:
                current["_next_is_paid"] = True
            continue

        # 优惠/含集运运费 标记
        if line in ("优惠", "含集运运费"):
            continue

        # 消息按钮
        if re.match(r'^消息\d*\s*按钮$', line):
            continue

        # 判断是否是店铺名（启动新订单）
        # 店铺名特征：较短、含特定关键词、不含¥
        is_store = False
        if 2 < len(line) < 40 and '¥' not in line:
            store_kw = ['店', '书城', '书社', '书屋', '书阁', '书铺', '旗舰',
                       '专营', '百货', '企业', '工厂', '充值中心', '网', '商城',
                       '家居', '数码', '电子', '杂货', '生活馆', '精品', '优品',
                       '官方', '批发', '小店', '的小店', '书吧', '图书']
            if any(kw in line for kw in store_kw):
                is_store = True
            # 特殊格式：xx的小店xx / xx书店xx
            if re.search(r'(书店|书城|书社|书屋|图书)', line):
                is_store = True

        if is_store:
            # 防止商品名被误识别为店铺名：如果文本>25字符且含多个中文，更可能是商品
            if len(line) > 25 and sum(1 for c in line if '\u4e00' <= c <= '\u9fff') > 15:
                if current and not current.get("product"):
                    current["product"] = line
                continue
            # 保存上一个订单
            if current and current.get("product"):
                orders.append(current)
            # 新订单
            current = {
                "store": line, "status": "", "product": "",
                "unit_price": "", "qty": 1, "paid": "",
                "last_price": "", "_next_is_paid": False,
            }
            continue

        # 长文本 → 商品名
        if len(line) > 15 and current and not current.get("product"):
            if any('\u4e00' <= c <= '\u9fff' for c in line[:5]):
                current["product"] = line
                continue

        # 处理 _next_is_paid 标记
        if current and current.get("_next_is_paid"):
            if line.startswith("¥"):
                current["paid"] = line[1:].strip()
            current["_next_is_paid"] = False

    # 最后一个
    if current and current.get("product"):
        orders.append(current)

    # 清理
    for o in orders:
        o.pop("_next_is_paid", None)
        # paid已在解析时通过_next_is_paid标记精确捕获
        # 如果仍为空，降级用last_price或unit_price
        if not o["paid"] and o["last_price"]:
            o["paid"] = o["last_price"]
        if not o["paid"]:
            o["paid"] = o["unit_price"]
        o.pop("last_price", None)

    return orders

def deduplicate(orders):
    """以(店铺+商品名前30字+数量)为key去重"""
    seen = {}
    for o in orders:
        key = (o["store"][:15], o["product"][:30], o.get("qty", 1))
        if key not in seen:
            seen[key] = o
        else:
            # 保留paid信息更完整的
            if o.get("paid") and not seen[key].get("paid"):
                seen[key] = o
    return list(seen.values())

def is_book(product, store):
    """三级书籍识别"""
    text = product + " " + store

    # 排除
    excludes = ['说明书', '情书贴纸', '证书', '笔记本电脑', '平板电脑',
                '购物金', '话费充值', '手机壳', '袜子', '指甲', '勺子',
                '铲子', '扎带', '磁棒', '贴纸', '挂钩', '手电筒', '胶带',
                'LED灯', '感应灯', '美工刀', '卡针', '围度尺', 'CPU', 'AMD',
                '果冻', '豆奶', '遥控器', '戒指', '行李箱', '钥匙扣',
                '电源线', '鳄鱼夹', '记号笔', '纸巾', '水平泡',
                '双面胶', '玻璃纤维', '醋酸胶带', '弹簧',
                '吸盘挂钩', '微缩迷你']
    for ex in excludes:
        if ex in text:
            return 0, ""

    # 🟢 ISBN
    if re.search(r'978\d{10}', text):
        return 3, "ISBN"
    # 🟢 出版社
    for pub in ['出版社', '出版']:
        if pub in text:
            return 3, "publisher"
    # 🟡 书店
    for kw in ['书店', '书城', '书社', '书屋', '书阁', '书铺', '图书']:
        if kw in store:
            return 2, "bookstore"
    # 🟡 教材关键词
    for kw in ['教材', '教程', '习题', '课本', '版', '编著', '编写组', '主编']:
        if kw in product:
            return 2, "textbook"
    # 🟠 通用
    for kw in ['书', '正版', '二手']:
        if kw in text:
            return 1, "keyword"
    return 0, ""

def main():
    with open(RAW, "r", encoding="utf-8") as f:
        lines = f.readlines()

    print(f"读取 {len(lines)} 行原始数据...")

    # 解析
    orders = parse_orders(lines)
    print(f"解析出 {len(orders)} 笔订单（含重复）")

    orders = deduplicate(orders)
    print(f"去重后 {len(orders)} 笔订单")

    # 书籍识别
    books = []
    non_books = []
    for o in orders:
        level, reason = is_book(o["product"], o["store"])
        if level > 0:
            o["book_level"] = level
            o["book_reason"] = reason
            o["book_label"] = ["", "🟠待确认", "🟡高可能", "🟢确定"][level]
            books.append(o)
        else:
            non_books.append(o)

    books.sort(key=lambda x: -x.get("book_level", 0))
    print(f"书籍订单: {len(books)} 笔")
    print(f"非书籍: {len(non_books)} 笔")

    # JSON
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    json_path = os.path.join(OUT_DIR, f"淘宝书籍订单_{ts}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(books, f, ensure_ascii=False, indent=2)

    all_json = os.path.join(OUT_DIR, f"淘宝全部订单_{ts}.json")
    with open(all_json, "w", encoding="utf-8") as f:
        json.dump(orders, f, ensure_ascii=False, indent=2)

    # Markdown报告
    md_path = os.path.join(OUT_DIR, f"淘宝书籍订单汇总_{ts}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# 淘宝书籍订单汇总\n\n")
        f.write(f"> 采集: {datetime.now().strftime('%Y-%m-%d %H:%M')} | 设备: OnePlus NE2210\n")
        f.write(f"> 原始数据: 54屏 {len(lines)}行 | 全部订单: {len(orders)}笔 | 书籍: {len(books)}笔\n\n")

        total = 0
        total_qty = 0

        f.write("## 书籍订单明细\n\n")
        f.write("| # | 置信 | 店铺 | 商品 | 单价 | 数量 | 实付 | 状态 |\n")
        f.write("|---|------|------|------|------|------|------|------|\n")

        for i, o in enumerate(books, 1):
            store = o["store"][:18]
            prod = o["product"][:55]
            up = o.get("unit_price", "?")
            qty = o.get("qty", 1)
            paid = o.get("paid", "?")
            status = o.get("status", "")
            label = o.get("book_label", "?")

            try:
                total += float(paid)
            except:
                pass
            total_qty += qty

            f.write(f"| {i} | {label} | {store} | {prod} | ¥{up} | ×{qty} | ¥{paid} | {status} |\n")

        f.write(f"\n**合计: ¥{total:,.2f}** ({len(books)}笔, {total_qty}册)\n")

        # 按书名分组（同一本书可能从多家店买）
        f.write("\n## 按书名汇总（同书多单合并）\n\n")
        book_groups = {}
        for o in books:
            # 提取核心书名（去掉"二手正版"等前缀）
            name = re.sub(r'^(二手正版?|正版旧书|旧书|正版二手书?|二手书?|【[^】]+】)', '', o["product"])
            name = name[:30]
            if name not in book_groups:
                book_groups[name] = {"name": name, "orders": [], "total_qty": 0, "total_paid": 0}
            book_groups[name]["orders"].append(o)
            book_groups[name]["total_qty"] += o.get("qty", 1)
            try:
                book_groups[name]["total_paid"] += float(o.get("paid", 0))
            except:
                pass

        f.write("| # | 书名 | 总数量 | 总花费 | 订单数 |\n")
        f.write("|---|------|--------|--------|--------|\n")
        for i, (name, g) in enumerate(sorted(book_groups.items(), key=lambda x: -x[1]["total_paid"]), 1):
            f.write(f"| {i} | {g['name']} | ×{g['total_qty']} | ¥{g['total_paid']:,.2f} | {len(g['orders'])}单 |\n")

        # 非书籍订单
        f.write(f"\n## 非书籍订单 ({len(non_books)}笔)\n\n")
        f.write("| # | 店铺 | 商品 | 实付 |\n")
        f.write("|---|------|------|------|\n")
        for i, o in enumerate(non_books, 1):
            f.write(f"| {i} | {o['store'][:15]} | {o['product'][:40]} | ¥{o.get('paid','?')} |\n")

    print(f"\n📊 报告: {md_path}")
    print(f"📚 书籍JSON: {json_path}")
    print(f"📦 全部JSON: {all_json}")

    # 打印书籍摘要
    print(f"\n{'='*70}")
    print(f"  📚 淘宝书籍订单: {len(books)}笔, 合计 ¥{total:,.2f}, {total_qty}册")
    print(f"{'='*70}")
    for i, o in enumerate(books[:10], 1):
        print(f"  {o['book_label']} {o['store'][:15]:15s} | {o['product'][:40]:40s} | ×{o.get('qty',1):3d} ¥{o.get('paid','?')}")
    if len(books) > 10:
        print(f"  ... 还有 {len(books)-10} 笔")

if __name__ == "__main__":
    main()
