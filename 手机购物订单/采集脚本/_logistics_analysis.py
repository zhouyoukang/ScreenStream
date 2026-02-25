"""从原始数据中提取有物流记录的订单，结合当前观察生成物流分析报告。"""
import re, os, json
from datetime import datetime
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
RAW_FILE = os.path.join(BASE, "..", "原始数据", "taobao_agent_full.txt")
OUT = os.path.join(BASE, "..", "解析结果", "物流分析报告.md")

# 读取原始数据
with open(RAW_FILE, "r", encoding="utf-8") as f:
    raw = f.read()

lines = [l.strip() for l in raw.split("\n") if l.strip()]

# ============ 提取有"查看物流"按钮的订单 ============
# 在原始数据中，"查看物流"出现在订单卡片的按钮区域
# 只有最近的订单才会显示这个按钮，较老的订单只有"追加评价"

logistics_indices = [i for i, l in enumerate(lines) if l == "查看物流"]
print(f"找到 {len(logistics_indices)} 个'查看物流'按钮位置")

# 从每个"查看物流"位置回溯，提取订单信息
orders_with_logistics = []
for idx in logistics_indices:
    store = ""
    product = ""
    status = ""
    unit_price = ""
    paid = ""
    qty = 1

    # 回溯最多25行
    for j in range(idx - 1, max(0, idx - 25), -1):
        l = lines[j]

        # 跳过UI噪声
        if l in ("更多", "更多操作", "追加评价", "闲鱼转卖", "再买一单", "退货宝",
                 "7天无理由退货", "退款关闭", "退款已关闭", "假一赔四", "极速退款",
                 "加入购物车", "反馈", "回到顶部", "退货包运费"):
            continue
        if l.startswith("=== SCREEN"):
            break

        # 状态
        if l in ("交易成功", "交易关闭", "交易完结,全额退款", "交易成功,部分退款成功"):
            status = l
            continue

        # 价格
        if l.startswith("¥"):
            val = l[1:]
            if not unit_price:
                unit_price = val
            continue

        # 实付款标记
        if l == "实付款":
            # 下一个¥就是实付
            for k in range(j + 1, min(len(lines), j + 3)):
                if lines[k].startswith("¥"):
                    paid = lines[k][1:]
                    break
            continue

        # 数量
        m = re.match(r'^×(\d+)$', l)
        if m:
            qty = int(m.group(1))
            continue

        # 商品名（长文本，含出版社/ISBN等）
        if len(l) > 10 and not product:
            product = l
            continue

        # 店铺名（较短，含"书店/书城"等关键词，或在状态之前）
        store_kw = ['书店', '书城', '书社', '书屋', '图书', '书吧', '书阁',
                    '旗舰店', '专营', '百货', '企业', '工厂', '网', '商城',
                    '家居', '数码', '电子', '杂货', '生活馆', '精品', '优品',
                    '官方', '批发', '小店', '的小店']
        if any(kw in l for kw in store_kw) and not store:
            store = l
            break

    if product:
        orders_with_logistics.append({
            "store": store,
            "product": product,
            "status": status,
            "unit_price": unit_price,
            "paid": paid,
            "qty": qty,
            "raw_index": idx,
        })

print(f"提取出 {len(orders_with_logistics)} 个有物流记录的订单")

# ============ 识别书籍 ============
def is_book(text):
    book_kw = ['出版社', '出版', '978', '正版', '二手', '教材', '课本',
               '旧书', '版第', '第五版', '第四版', '第三版', '第二版',
               '高等教育', '清华大学', '人民出版社', '科学出版社',
               '机械工业', '中国矿业', '北京大学']
    return any(kw in text for kw in book_kw)

book_logistics = [o for o in orders_with_logistics if is_book(o["product"])]
nonbook_logistics = [o for o in orders_with_logistics if not is_book(o["product"])]

print(f"  书籍: {len(book_logistics)} 笔")
print(f"  非书籍: {len(nonbook_logistics)} 笔")

# ============ 今天新发现的订单（不在原始54屏采集中的最新订单） ============
new_orders = [
    {"store": "西科大二手书城", "product": "2手电工学少学时第五版第5版唐介王宁高等教育出版社9787040536515", "qty": 2, "paid": "17.1", "status": "交易成功", "note": "今日新发现"},
    {"store": "格致图书城", "product": "二手正版工程力学(工程静力学与材料力学)第3版范钦珊机械工业出版社9787111600572", "qty": 1, "paid": "5.02", "status": "交易成功", "note": "今日新发现"},
    {"store": "牧风博学书店", "product": "二手正版工程力学(工程静力学与材料力学)第3版范钦珊机械工业出版社9787111600572", "qty": 1, "paid": "5.08", "status": "交易成功", "note": "今日新发现"},
    {"store": "老地方二手书店", "product": "二手2023年版习近平新时代中国特色社会主义思想概论2025两课教材", "qty": 1, "paid": "3.29", "status": "交易成功", "note": "今日新发现"},
]

# ============ 待收货订单（当前在手机上看到的） ============
pending_receipt = [
    {"store": "朵淽旗舰店", "product": "假睫毛镊子免胶睫毛新手自用专用高精密专业美睫嫁接工具金羽夹", "paid": "0", "status": "已签收,待确认收货", "is_book": False},
    {"store": "信管数码专营店", "product": "适用三星水凝膜s25/s24/s23/s22/s21/ultra保护膜", "paid": "0.38", "status": "已签收,待确认收货", "is_book": False},
    {"store": "八卦鼠惠隆达专卖店", "product": "黑色编织纹适用三星s25ultra手机壳", "paid": "23.38", "status": "已签收,待确认收货", "is_book": False},
]

# ============ 生成报告 ============
with open(OUT, "w", encoding="utf-8") as f:
    f.write("# 淘宝订单物流分析报告\n\n")
    f.write(f"> 分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    f.write("> 收货地址: 新疆大学\n\n")

    # === 当前物流状态总览 ===
    f.write("## 一、当前物流状态总览\n\n")
    f.write("### 待取件（已签收未确认，包裹在驿站/快递柜）\n\n")
    f.write("| # | 店铺 | 商品 | 实付 | 是否书籍 |\n")
    f.write("|---|------|------|------|----------|\n")
    for i, o in enumerate(pending_receipt, 1):
        book_flag = "📚是" if o["is_book"] else "❌否"
        f.write(f"| {i} | {o['store']} | {o['product'][:35]} | ¥{o['paid']} | {book_flag} |\n")
    f.write(f"\n> **3个包裹在驿站等你取**，全是非书籍（手机配件+美妆工具）。\n\n")

    # === 最新订单（今日新发现的书籍） ===
    f.write("## 二、最新书籍订单（比原始采集更新）\n\n")
    f.write("这些订单出现在订单列表的最顶部，说明是**最近下单且已完成**的。\n\n")
    f.write("| # | 店铺 | 书名 | ×数量 | 实付 | 状态 |\n")
    f.write("|---|------|------|-------|------|------|\n")
    for i, o in enumerate(new_orders, 1):
        f.write(f"| {i} | {o['store']} | {o['product'][:45]} | ×{o['qty']} | ¥{o['paid']} | {o['status']} |\n")
    f.write(f"\n> 这4笔**新订单**不在原始91笔采集中。总计新增：电工学×2、工程力学×2、习概论×1。\n\n")

    # === 有物流记录的书籍订单 ===
    f.write("## 三、有物流记录的书籍订单（原始数据中含"查看物流"按钮）\n\n")
    f.write("在淘宝订单列表中，只有**最近的订单**才会显示"查看物流"按钮。\n")
    f.write(f"共发现 **{len(book_logistics)}笔** 书籍订单有此按钮，说明它们是最近配送的。\n\n")
    f.write("| # | 店铺 | 书名 | ×数量 | 实付 | 状态 |\n")
    f.write("|---|------|------|-------|------|------|\n")
    for i, o in enumerate(book_logistics, 1):
        f.write(f"| {i} | {o['store'][:15]} | {o['product'][:45]} | ×{o['qty']} | ¥{o.get('paid', o.get('unit_price','?'))} | {o['status']} |\n")

    # 较早的订单没有"查看物流"，说明物流已过期
    total_books = 91
    f.write(f"\n> 91笔书籍订单中，**{len(book_logistics)}笔有近期物流记录**，")
    f.write(f"其余{total_books - len(book_logistics)}笔的物流已不在列表可见范围。\n\n")

    # === 物流到达分析 ===
    f.write("## 四、到达新疆大学的物流推断\n\n")
    f.write("### 已知事实\n")
    f.write("1. **收货地址是新疆大学** — 所有订单寄往同一地址\n")
    f.write("2. **交易成功** = 已确认收货 = 包裹已到达并签收\n")
    f.write("3. **已签收,待确认收货** = 包裹在驿站/快递柜，还没去取\n")
    f.write("4. **交易关闭** = 退货了，包裹已退回\n\n")

    f.write("### 无法获取的信息\n")
    f.write('**精确到达时间**（如"2月22日 14:30签收"）需要进入订单详情页的物流追踪页面。\n')
    f.write("淘宝App的订单卡片UI层级复杂，Agent多次尝试点击"查看物流"按钮和订单详情均未成功。\n\n")

    f.write("### 推断的时间线\n")
    f.write("根据订单在列表中的位置（越靠前=越新）：\n\n")
    f.write("| 时间段 | 订单 | 依据 |\n")
    f.write("|--------|------|------|\n")
    f.write("| 最近1-3天 | 西科大(电工学)、格致(工程力学)、牧风(工程力学)、老地方(习概论) | 列表最顶部，今日新发现 |\n")
    f.write("| 最近1周 | 状元书屋(国防教育)×2、尚祁(英语阅读)、智愚(英语阅读×17) | 原始采集前几屏，有"查看物流" |\n")
    f.write(f"| 最近2-4周 | 其余{len(book_logistics)}笔有"查看物流"的订单 | 中间位置，仍有物流按钮 |\n")
    f.write(f"| 1个月+ | 其余约{total_books - len(book_logistics)}笔订单 | 列表后部，无物流按钮 |\n\n")

    f.write("### 快递到新疆大学的一般时效\n")
    f.write("| 发货地 | 快递公司 | 预计时效 |\n")
    f.write("|--------|----------|----------|\n")
    f.write("| 江浙沪 | 中通/圆通/韵达 | 5-7天 |\n")
    f.write("| 四川/重庆 | 中通/圆通 | 4-6天 |\n")
    f.write("| 湖南/湖北 | 韵达/申通 | 5-7天 |\n")
    f.write("| 山西/陕西 | 中通 | 3-5天 |\n")
    f.write("| 北京 | 顺丰/中通 | 4-6天 |\n\n")
    f.write("> 新疆是全国物流最远的区域之一，绝大多数快递需要5-7个工作日。\n")
    f.write("> 二手书城多在江浙沪/四川/湖南，到新疆大学通常需要6-8天。\n\n")

    # === 获取精确物流时间的方法 ===
    f.write("## 五、如何获取精确到达时间\n\n")
    f.write("Agent无法自动提取精确物流时间（淘宝UI点击限制），以下是可行的替代方案：\n\n")
    f.write("### 方案1：手动查看（最快，30秒/单）\n")
    f.write("打开淘宝 → 我的订单 → 点击任意订单 → 查看物流 → 看签收时间\n\n")
    f.write("### 方案2：安装菜鸟裹裹App（一次性查看所有）\n")
    f.write("菜鸟裹裹会聚合所有淘宝包裹的完整物流轨迹，包括签收时间。\n\n")
    f.write("### 方案3：淘宝PC版（批量导出）\n")
    f.write("电脑浏览器打开 buyertrade.taobao.com → 已买到的宝贝 → 可以看到订单号和物流详情。\n\n")
    f.write("### 方案4：支付宝快递管家\n")
    f.write("支付宝 → 搜索"快递" → 我的快递 → 显示所有包裹状态和签收时间。\n\n")

    # === 待收货提醒 ===
    f.write("## 六、行动提醒\n\n")
    f.write("### 📦 3个包裹等你去取！\n")
    for o in pending_receipt:
        f.write(f"- **{o['store']}**: {o['product'][:30]} (¥{o['paid']})\n")
    f.write("\n这3个包裹状态是"已签收,待确认收货"，说明**已经到了驿站/快递柜**，")
    f.write("再不取可能被退回。\n\n")

    f.write("---\n*报告完毕。精确物流时间需手动查看或安装菜鸟裹裹App。*\n")

print(f"\n📊 物流分析报告: {OUT}")
print(f"\n=== 要点 ===")
print(f"  有物流记录的书籍订单: {len(book_logistics)}笔")
print(f"  今日新发现的书籍订单: {len(new_orders)}笔")
print(f"  待取件包裹: {len(pending_receipt)}个（非书籍）")
print(f"  精确到达时间: 需手动查看（淘宝UI限制）")
