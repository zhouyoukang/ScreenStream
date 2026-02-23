"""淘宝订单深度解构 — 钻入每笔订单详情页,获取完整信息
脱离列表页的数据偏见:价格多义/日期缺失/名称截断/订单号缺失
"""
import subprocess, time, xml.etree.ElementTree as ET, os, re, json
from datetime import datetime

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_SCRIPT_DIR)  # 手机购物订单/
ADB = os.path.join(_ROOT, "..", "构建部署", "android-sdk", "platform-tools", "adb.exe")
S = "158377ff"
OUT = os.path.join(_ROOT, "原始数据")

def a(*args, t=8):
    try:
        r = subprocess.run([ADB,"-s",S]+list(args), capture_output=True, text=True, timeout=t, encoding='utf-8', errors='replace')
        return r.stdout.strip()
    except: return ""

def tap(x,y): a("shell",f"input tap {x} {y}"); time.sleep(0.3)
def swipe_up(): a("shell","input swipe 540 1800 540 600 400"); time.sleep(1)
def back(): a("shell","input keyevent KEYCODE_BACK"); time.sleep(1)
def home(): a("shell","input keyevent KEYCODE_HOME"); time.sleep(0.5)

def fg():
    out = a("shell","dumpsys window | grep mCurrentFocus")
    m = re.search(r'u0\s+(\S+)', out)
    return m.group(1) if m else ""

def get_all():
    """dump UI → 返回(texts列表, nodes列表)"""
    a("shell","uiautomator dump /sdcard/ui_dump.xml", t=5)
    a("pull","/sdcard/ui_dump.xml", os.path.join(OUT,"ui_dump.xml"), t=3)
    try: root = ET.parse(os.path.join(OUT,"ui_dump.xml")).getroot()
    except: return [], []
    texts, nodes = [], []
    for n in root.iter("node"):
        t2,d,b,cl = n.get("text","").strip(), n.get("content-desc","").strip(), n.get("bounds",""), n.get("clickable","false")
        m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', b)
        if m:
            cx,cy = (int(m[1])+int(m[3]))//2, (int(m[2])+int(m[4]))//2
            h = int(m[4])-int(m[2])
            nodes.append({"t":t2,"d":d,"x":cx,"y":cy,"h":h,"click":cl=="true",
                         "x1":int(m[1]),"y1":int(m[2]),"x2":int(m[3]),"y2":int(m[4])})
        if t2 and len(t2)>1: texts.append(t2)
        if d and d!=t2 and len(d)>1: texts.append(d)
    return texts, nodes

def find_order_cards(nodes):
    """在订单列表页找到可点击的订单卡片区域
    淘宝订单卡片通常：有店铺名（含旗舰店/书店/数码等）+ 下方有商品名和价格
    返回每个订单卡片的y坐标(用于点击进入详情)
    """
    cards = []
    # 找所有包含店铺名特征的元素
    store_keywords = ["旗舰店","专营店","书店","书城","书社","数码","制袋","百佳龙","劲欢","八卦鼠","元素"]
    for n in nodes:
        if any(k in n["t"]+n["d"] for k in store_keywords):
            # 店铺名下方的区域就是订单卡片
            cards.append({"store": n["t"] or n["d"], "y": n["y"], "x": 540})
    return cards

def extract_detail_page():
    """从订单详情页提取结构化信息"""
    texts, nodes = get_all()

    info = {
        "order_id": "",
        "order_date": "",
        "store": "",
        "products": [],
        "total_paid": "",
        "status": "",
        "shipping": "",
        "raw_texts": texts[:80]  # 保留原始文本前80行
    }

    for t in texts:
        # 订单号
        if re.match(r'^\d{15,25}$', t):
            info["order_id"] = t
        # 日期
        if re.match(r'20\d{2}[年\-/]\d{1,2}[月\-/]\d{1,2}', t):
            info["order_date"] = t
        elif re.match(r'\d{4}\.\d{2}\.\d{2}', t):
            info["order_date"] = t
        # 状态
        if t in ["交易成功","交易关闭","待发货","已发货","已签收","待收货","待付款","退款成功","卖家已发货"]:
            info["status"] = t
        # 实付款
        if "实付款" in t or "实付" in t:
            # 下一个¥值就是实付
            pass
        # 店铺
        if any(k in t for k in ["旗舰店","专营店","书店","书城","数码"]) and not info["store"]:
            info["store"] = t
        # 物流
        if "快递" in t or "签收" in t or "运单" in t:
            info["shipping"] = t[:80]

    # 提取所有¥值
    prices = []
    for t in texts:
        if t.startswith("¥") or t.startswith("￥"):
            p = t.replace("¥","").replace("￥","").strip()
            try:
                prices.append(float(p))
            except: pass
    info["all_prices"] = prices

    # 提取商品名(长文本,含中文)
    for t in texts:
        if len(t) > 15 and any('\u4e00' <= c <= '\u9fff' for c in t[:5]):
            if not any(k in t for k in ["旗舰店","专营店","书店","快递","签收","确认","申请","投诉","按钮","返回","搜索","复制","拨打"]):
                info["products"].append(t[:100])

    return info

def main():
    print(f"🔍 淘宝订单深度解构")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    a("shell","input keyevent KEYCODE_WAKEUP")

    # 启动淘宝 → 订单页
    home()
    a("shell","monkey -p com.taobao.taobao -c android.intent.category.LAUNCHER 1")
    time.sleep(5)

    # 导航到"我的订单"
    _, nodes = get_all()
    # 点击底部"我的"tab
    for n in nodes:
        if "我的" in n["t"] and n["y"] > 2100:
            tap(n["x"], n["y"]); break
    time.sleep(3)
    _, nodes = get_all()
    # 点击"我的订单"或"查看全部订单"
    for n in nodes:
        if any(k in n["t"]+n["d"] for k in ["我的订单","全部订单","查看全部"]):
            tap(n["x"], n["y"]); break
    time.sleep(3)

    cur = fg()
    print(f"  前台: {cur}")

    # 收集所有订单详情
    all_orders = []
    order_idx = 0
    max_scrolls = 12
    visited_stores = set()  # 防重复

    for scroll in range(max_scrolls):
        texts, nodes = get_all()

        # 找订单卡片 — 通过查找可点击的大区域
        # 淘宝订单列表中,每个订单是一个大的可点击卡片
        # 策略: 找到商品名/店铺名所在区域,点击进入详情

        # 找当前屏幕上的店铺名
        stores_on_screen = []
        for n in nodes:
            txt = n["t"] + n["d"]
            if any(k in txt for k in ["旗舰店","专营店","书店","书城","书社","数码","制袋厂","百佳龙","劲欢"]):
                key = n["t"] or n["d"]
                if key not in visited_stores:
                    stores_on_screen.append(n)

        if not stores_on_screen:
            # 没找到新店铺,试试找商品名区域
            for n in nodes:
                if len(n["t"]) > 20 and n["click"] and n["y"] > 300 and n["y"] < 2000:
                    if n["t"][:10] not in str(visited_stores):
                        stores_on_screen.append(n)
                        break

        if not stores_on_screen:
            print(f"  [屏{scroll+1}] 无新订单可点击")
            swipe_up()
            continue

        for store_node in stores_on_screen:
            store_name = store_node["t"] or store_node["d"]
            visited_stores.add(store_name)
            order_idx += 1

            print(f"\n  📦 订单{order_idx}: {store_name}")

            # 点击该订单区域(点击店铺名下方的商品区域)
            click_y = store_node["y"] + 80  # 店铺名下方
            tap(540, min(click_y, 2000))
            time.sleep(3)

            # 检查是否进入了详情页
            cur = fg()
            if "OrderDetail" in cur or "order" in cur.lower() or cur != fg():
                # 在详情页,提取信息
                info = extract_detail_page()
                info["store"] = info["store"] or store_name
                info["idx"] = order_idx
                all_orders.append(info)

                # 打印关键信息
                print(f"    订单号: {info['order_id'] or '?'}")
                print(f"    日期: {info['order_date'] or '?'}")
                print(f"    状态: {info['status'] or '?'}")
                print(f"    价格: {info['all_prices']}")
                print(f"    商品: {info['products'][:2]}")

                # 如果详情页有更多信息(需要滚动),采集
                # 但为了速度,只取首屏

                back()
                time.sleep(2)
            else:
                print(f"    ⚠ 未进入详情页 (前台: {cur})")
                # 可能是点击位置不对,跳过
                back()
                time.sleep(1)

        swipe_up()
        time.sleep(1)

    # 保存结果
    out_file = os.path.join(OUT, "淘宝订单详解.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(all_orders, f, ensure_ascii=False, indent=2)

    # 生成可读报告
    report_file = os.path.join(OUT, "淘宝订单详解.md")
    with open(report_file, "w", encoding="utf-8") as f:
        f.write("# 淘宝订单深度解构\n\n")
        f.write(f"> 采集时间: {datetime.now()} | 方法: 逐单点入详情页\n\n")
        f.write(f"共采集 {len(all_orders)} 笔订单\n\n")

        for o in all_orders:
            f.write(f"\n---\n### 订单{o['idx']}: {o['store']}\n\n")
            f.write(f"- **订单号**: {o.get('order_id','?')}\n")
            f.write(f"- **下单日期**: {o.get('order_date','?')}\n")
            f.write(f"- **状态**: {o.get('status','?')}\n")
            f.write(f"- **价格信息**: {o.get('all_prices',[])}\n")
            f.write(f"- **商品**: {'; '.join(o.get('products',[])[:3])}\n")
            f.write(f"- **物流**: {o.get('shipping','?')}\n")

    print(f"\n✅ 完成! {len(all_orders)}笔订单")
    print(f"  JSON: {out_file}")
    print(f"  报告: {report_file}")

if __name__ == "__main__":
    main()
