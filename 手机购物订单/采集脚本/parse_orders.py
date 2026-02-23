"""解析所有采集数据 → 结构化购物记录报告"""
import re, os
from datetime import datetime

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_SCRIPT_DIR)  # 手机购物订单/
OUT = os.path.join(_ROOT, "解析结果")

def parse_taobao(lines):
    """解析淘宝订单数据"""
    orders = []
    current = {}
    for line in lines:
        line = line.strip()
        if not line or line.startswith("---"): continue
        # 店铺名
        if any(kw in line for kw in ["旗舰店","专营店","书店","书城","书社","数码","制袋厂","百佳龙"]):
            if current and current.get("product"):
                orders.append(current)
            current = {"store": line, "product": "", "price": "", "status": "", "shipping": ""}
        # 商品名（长文本，含中文描述）
        elif len(line) > 15 and not line.startswith("¥") and not line.startswith("×") and "签收" not in line and "取件码" not in line and any(u'\u4e00' <= c <= u'\u9fff' for c in line[:5]):
            if not current.get("product") and not any(kw in line for kw in ["未选中","已选中","按钮","搜索","筛选","管理","退货宝","假一赔四","极速退款","先用后付","确认收货","延长收货","查看物流","更多操作","加入购物车","闲鱼转卖","再买一单","申请开票","删除订单","回到顶部","催发货","修改地址","大促价保","小贴士","7天无理由","实付款","商品被拆分","反馈","可提前付款","今日闪购"]):
                current["product"] = line
        # 价格
        elif line.startswith("¥"):
            price = line.replace("¥","").strip()
            if not current.get("price"):
                current["price"] = price
        # 状态
        elif line in ["已发货","卖家已发货","已签收","已签收,待确认收货","交易关闭","交易成功","待寄出"]:
            current["status"] = line
        # 物流
        elif "签收" in line and "自提柜" in line:
            current["shipping"] = line[:60]
        elif "发货" in line and "月" in line:
            current["shipping"] = line
    if current and current.get("product"):
        orders.append(current)
    return orders

def parse_pdd(lines):
    """解析拼多多订单数据"""
    orders = []
    current = {}
    for line in lines:
        line = line.strip()
        if not line or line.startswith("---"): continue
        if line.startswith("商品名称："):
            if current and current.get("product"):
                orders.append(current)
            current = {"product": line.replace("商品名称：",""), "price":"", "status":"", "store":"", "qty":""}
        elif line.startswith("商品价格："):
            current["price"] = line.replace("商品价格：¥","").replace("商品价格：","")
        elif line.startswith("订单状态："):
            current["status"] = line.replace("订单状态：","")
        elif line.startswith("店铺名称：") and not current.get("store"):
            current["store"] = line.replace("店铺名称：","")
        elif line.startswith("×"):
            current["qty"] = line
        elif line.startswith("充值号码"):
            current["note"] = line
    if current and current.get("product"):
        orders.append(current)
    return orders

def parse_meituan(lines):
    """解析美团订单数据"""
    orders = []
    for line in lines:
        line = line.strip()
        if "单车" in line:
            orders.append({"type":"单车","detail":"","price":"","time":""})
        elif "开锁" in line:
            if orders: orders[-1]["time"] = line
        elif "时长" in line:
            if orders: orders[-1]["detail"] = line
        elif line.startswith(".") and orders:
            orders[-1]["price"] = line
    return orders

def main():
    DATA = os.path.join(_ROOT, "原始数据")

    # 读取淘宝原始数据
    with open(os.path.join(DATA, "shopping_records_20260223_133514.txt"), "r", encoding="utf-8") as f:
        content = f.read()
    m = re.search(r'## 淘宝\n={60}\n(.*?)(?=\n={60}\n## )', content, re.DOTALL)
    taobao_lines = m.group(1).split("\n") if m else []

    # 读取拼多多原始数据 (从FINAL汇总文件)
    with open(os.path.join(DATA, "shopping_FINAL.txt"), "r", encoding="utf-8") as f:
        content = f.read()
    m = re.search(r'## 拼多多\n={60}\n(.*?)(?=\n={60}\n## )', content, re.DOTALL)
    pdd_lines = m.group(1).split("\n") if m else []

    # 读取美团数据
    with open(os.path.join(DATA, "shopping_FINAL.txt"), "r", encoding="utf-8") as f:
        content = f.read()
    m = re.search(r'## 美团\n={60}\n(.*?)(?=\n={60}\n## )', content, re.DOTALL)
    mt_lines = m.group(1).split("\n") if m else []

    # 解析
    tb_orders = parse_taobao(taobao_lines)
    pdd_orders = parse_pdd(pdd_lines)
    mt_orders = parse_meituan(mt_lines)

    # 输出结构化报告
    report = os.path.join(OUT, "购物记录汇总报告.md")
    with open(report, "w", encoding="utf-8") as f:
        f.write("# 📱 OnePlus手机购物记录汇总\n\n")
        f.write(f"> 采集时间: 2026-02-23 | 设备: OnePlus NE2210 | 方式: ADB自动化\n\n")

        # 概览
        f.write("## 📊 采集概览\n\n")
        f.write("| APP | 状态 | 订单数 | 说明 |\n")
        f.write("|-----|------|--------|------|\n")
        f.write(f"| 淘宝 | ✅ 成功 | {len(tb_orders)}笔 | 全部订单页9屏滚动 |\n")
        f.write(f"| 拼多多 | ✅ 成功 | {len(pdd_orders)}笔 | 全部订单页11屏滚动 |\n")
        f.write(f"| 美团 | ✅ 部分 | {len(mt_orders)}笔 | 订单页首屏 |\n")
        f.write("| 京东 | ⚠️ 受限 | - | 滑动拼图验证码阻塞全部订单 |\n")
        f.write("| 闲鱼 | ⚠️ 受限 | 200笔(页面显示) | Flutter渲染,uiautomator无法滚动采集 |\n")
        f.write("| 饿了么 | ⚠️ 受限 | - | 订单入口未识别 |\n")
        f.write("| 当当 | ❌ 失败 | - | 启动广告页无法跳过 |\n\n")

        # 淘宝详单
        f.write("---\n\n## 🛒 淘宝订单明细\n\n")
        f.write("| # | 商品 | 价格 | 店铺 | 状态 |\n")
        f.write("|---|------|------|------|------|\n")
        for i, o in enumerate(tb_orders, 1):
            prod = o.get("product","")[:50]
            price = o.get("price","?")
            store = o.get("store","")[:15]
            status = o.get("status","")
            f.write(f"| {i} | {prod} | ¥{price} | {store} | {status} |\n")

        # 拼多多详单
        f.write(f"\n---\n\n## 🍊 拼多多订单明细\n\n")
        f.write("| # | 商品 | 价格 | 店铺 | 状态 |\n")
        f.write("|---|------|------|------|------|\n")
        for i, o in enumerate(pdd_orders, 1):
            prod = o.get("product","")[:50]
            price = o.get("price","?")
            store = o.get("store","")[:20]
            status = o.get("status","")
            qty = o.get("qty","")
            note = o.get("note","")
            extra = f" {qty}" if qty else ""
            extra += f" {note}" if note else ""
            f.write(f"| {i} | {prod}{extra} | ¥{price} | {store} | {status} |\n")

        # 美团
        f.write(f"\n---\n\n## 🥡 美团订单明细\n\n")
        if mt_orders:
            for o in mt_orders:
                f.write(f"- **{o['type']}** | {o.get('time','')} | {o.get('detail','')} | {o.get('price','')}\n")
        else:
            f.write("美团订单页采集到的数据：\n\n")
            f.write("- 共5页订单（页面显示\"第2页，共5页\"）\n")
            f.write("- 可见订单: 单车骑行 2026-02-07 15:30, 时长14分25秒, ¥0.99(已抵扣¥0.51)\n")

        # 京东说明
        f.write(f"\n---\n\n## 🔴 京东\n\n")
        f.write("京东APP打开\"全部订单\"时触发**滑动拼图验证码**，ADB无法自动完成。\n")
        f.write("通过\"待收货\"和\"待评价\"tab绕过验证码，但当前在途订单极少。\n\n")
        f.write("**京东账号信息** (从\"我的\"页面采集):\n")
        f.write("- 会员等级: 金牌会员, PLUS 2年\n")
        f.write("- 京豆: 125\n")
        f.write("- 购物车: 85件\n")
        f.write("- 关注店铺: 40\n")
        f.write("- 收藏: 3\n")
        f.write("- 待评价: 13笔\n\n")

        # 闲鱼说明
        f.write(f"\n---\n\n## 🐟 闲鱼\n\n")
        f.write("闲鱼\"我买到的\"显示 **200笔** 订单。\n")
        f.write("但闲鱼使用Flutter渲染,uiautomator只能获取首屏框架,无法滚动读取列表内容。\n\n")
        f.write("可见的订单标签: 全部 / 待付款 / 待发货 / 待收货 / 待评价 / 退款中\n\n")

        # 技术限制说明
        f.write("---\n\n## ⚙️ 技术说明\n\n")
        f.write("### 采集方法\n")
        f.write("- 纯ADB操控: `monkey`启动APP + `uiautomator dump`读取UI树 + `input`点击/滑动\n")
        f.write("- 无需ROOT, 无需ScreenStream API\n\n")
        f.write("### 各APP限制原因\n")
        f.write("| APP | 限制 | 技术原因 |\n")
        f.write("|-----|------|----------|\n")
        f.write("| 京东 | 滑动拼图验证码 | 访问\"全部订单\"触发反自动化机制 |\n")
        f.write("| 闲鱼 | Flutter渲染 | 列表内容不暴露在accessibility tree中 |\n")
        f.write("| 饿了么 | UI导航失败 | \"我的\"页面订单入口文本不匹配 |\n")
        f.write("| 当当 | 启动广告 | StartupActivity无可点击跳过按钮 |\n")
        f.write("| 拼多多 | `am start`被拦截 | OPPO自启动限制, 仅monkey可绕过 |\n\n")
        f.write("### 解决方案建议\n")
        f.write("- **京东**: 手动在手机上完成一次滑动验证后, 重新运行脚本即可采集\n")
        f.write("- **闲鱼**: 需使用截屏+OCR方案, 或通过闲鱼网页版导出\n")
        f.write("- **饿了么**: 手动打开到订单页后, 运行 `python deep_scroll.py 饿了么` 即可采集\n")

    print(f"✅ 报告已生成: {report}")
    print(f"📊 淘宝 {len(tb_orders)}笔 + 拼多多 {len(pdd_orders)}笔 + 美团 {len(mt_orders)}笔")

if __name__ == "__main__":
    main()
