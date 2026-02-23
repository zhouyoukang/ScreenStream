"""淘宝订单深度采集 — 纯ADB方案，滚动到底获取全部订单"""
import subprocess, time, xml.etree.ElementTree as ET, os, re, json
from datetime import datetime

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_SCRIPT_DIR)  # 手机购物订单/
ADB = os.path.join(_ROOT, "..", "构建部署", "android-sdk", "platform-tools", "adb.exe")
S = "158377ff"  # OnePlus NE2210
OUT = os.path.join(_ROOT, "原始数据")
DUMP = "/sdcard/ui_dump.xml"
LD = os.path.join(OUT, "ui_dump.xml")

def a(*args, t=10):
    try:
        r = subprocess.run([ADB, "-s", S] + list(args),
                          capture_output=True, text=True, timeout=t,
                          encoding='utf-8', errors='replace')
        return r.stdout.strip()
    except Exception as e:
        return f"ERR:{e}"

def tap(x, y):
    a("shell", f"input tap {x} {y}")
    time.sleep(0.3)

def swipe_up(duration=500):
    """向上滑动（看更多订单）"""
    a("shell", f"input swipe 540 1800 540 500 {duration}")

def swipe_slow():
    """慢速滑动，避免跳过内容"""
    a("shell", "input swipe 540 1600 540 800 600")

def home():
    a("shell", "input keyevent KEYCODE_HOME")

def back():
    a("shell", "input keyevent KEYCODE_BACK")

def wake():
    a("shell", "input keyevent KEYCODE_WAKEUP")

def fg():
    out = a("shell", "dumpsys window | grep mCurrentFocus")
    m = re.search(r'u0\s+(\S+)', out)
    return m.group(1) if m else ""

def monkey(pkg):
    a("shell", f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1")

def get_nodes():
    """获取UI树所有节点（text + content-desc + bounds）"""
    a("shell", f"uiautomator dump {DUMP}", t=8)
    a("pull", DUMP, LD, t=5)
    try:
        root = ET.parse(LD).getroot()
    except:
        return []
    nodes = []
    for n in root.iter("node"):
        txt = n.get("text", "").strip()
        desc = n.get("content-desc", "").strip()
        bounds = n.get("bounds", "")
        cls = n.get("class", "")
        m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
        if m:
            x1, y1, x2, y2 = int(m[1]), int(m[2]), int(m[3]), int(m[4])
            nodes.append({
                "t": txt, "d": desc, "c": cls,
                "x": (x1+x2)//2, "y": (y1+y2)//2,
                "x1": x1, "y1": y1, "x2": x2, "y2": y2
            })
    return nodes

def find_tap(keywords, nodes):
    """在节点中查找并点击"""
    for kw in keywords:
        for n in nodes:
            if kw in n["t"] or kw in n["d"]:
                tap(n["x"], n["y"])
                return n["t"] or n["d"]
    return None

def dismiss_popups(nodes):
    """关闭各种弹窗"""
    for kw in ["允许", "同意", "确定", "我知道了", "跳过", "关闭",
               "以后再说", "暂不", "不再提醒", "取消", "知道了"]:
        hit = find_tap([kw], nodes)
        if hit:
            time.sleep(0.5)
            return hit
    return None

def extract_texts(nodes):
    """从节点提取所有有意义的文本"""
    seen, texts = set(), []
    for n in nodes:
        for v in [n["t"], n["d"]]:
            if v and len(v) > 1 and v not in seen:
                seen.add(v)
                texts.append(v)
    return texts

def get_screen_signature(nodes):
    """获取屏幕签名（用于检测是否滚动到底）"""
    texts = []
    for n in nodes:
        for v in [n["t"], n["d"]]:
            if v and len(v) > 3:
                texts.append(v)
    return "|".join(sorted(texts[:20]))

# ============================================================
# 主采集流程
# ============================================================

def open_taobao_orders():
    """打开淘宝并导航到全部订单页"""
    print("📱 启动淘宝...")
    home(); time.sleep(0.5)

    # monkey启动淘宝（最可靠，绕过OPPO弹窗）
    monkey("com.taobao.taobao")
    time.sleep(5)

    cur = fg()
    print(f"  前台: {cur}")
    if "taobao" not in cur.lower():
        print("  ⚠ 淘宝未启动，重试...")
        a("shell", "am start -n com.taobao.taobao/com.taobao.tao.homepage.HomeActivity")
        time.sleep(5)
        cur = fg()
        if "taobao" not in cur.lower():
            return False, "淘宝启动失败"

    # 处理可能的弹窗
    for _ in range(3):
        nodes = get_nodes()
        d = dismiss_popups(nodes)
        if not d:
            break
        time.sleep(1)

    # 导航到"我的"页面（底部Tab）
    print("  导航到 我的...")
    nodes = get_nodes()
    hit = find_tap(["我的淘宝", "我的"], nodes)
    if not hit:
        # 底部tab通常在屏幕底部，尝试固定坐标
        tap(972, 2220)  # OnePlus 底部右侧tab
    time.sleep(3)

    # 处理弹窗
    nodes = get_nodes()
    dismiss_popups(nodes)
    time.sleep(0.5)

    # 点击"全部订单"或"查看全部订单"
    print("  导航到 全部订单...")
    nodes = get_nodes()
    hit = find_tap(["全部订单", "查看全部订单", "我的订单"], nodes)
    if not hit:
        # 尝试点击"全部"（订单区域的入口）
        hit = find_tap(["全部"], nodes)
    time.sleep(3)

    # 验证是否到了订单页
    nodes = get_nodes()
    texts = extract_texts(nodes)
    combined = " ".join(texts)
    if any(kw in combined for kw in ["待付款", "待发货", "待收货", "退款/售后", "订单管理"]):
        print("  ✅ 已进入订单页")
        # 确保选中"全部"tab
        find_tap(["全部"], nodes)
        time.sleep(1)
        # 关闭可能的促销弹窗
        nodes = get_nodes()
        find_tap(["关闭"], nodes)
        time.sleep(0.5)
        return True, "ok"
    else:
        print(f"  ⚠ 可能未到订单页，当前文本: {texts[:10]}")
        return True, "uncertain"

def deep_scroll_collect(max_scrolls=50):
    """深度滚动采集全部订单，返回原始文本列表"""
    all_texts = []
    seen = set()
    empty_count = 0
    last_sig = ""

    print(f"\n🔄 开始深度滚动采集（最多{max_scrolls}屏）...")

    for i in range(max_scrolls + 1):
        nodes = get_nodes()

        # 检查并关闭弹窗
        dismiss_popups(nodes)
        if i > 0:
            nodes = get_nodes()

        # 提取新文本
        texts = extract_texts(nodes)
        new = [t for t in texts if t not in seen and len(t) > 1]
        seen.update(new)

        # 获取屏幕签名检测是否到底
        sig = get_screen_signature(nodes)

        if new:
            all_texts.append(f"\n--- 淘宝 第{i+1}屏 ({len(new)}条新) ---")
            all_texts.extend(new)
            print(f"  [{i+1:2d}] +{len(new):3d}条新 (总{len(seen)}条)")
            empty_count = 0
        else:
            empty_count += 1
            same_screen = (sig == last_sig)
            print(f"  [{i+1:2d}] 空屏 ({empty_count}/3) {'[页面相同]' if same_screen else ''}")
            if empty_count >= 3:
                print("  🛑 连续3次无新内容，已到底部")
                break

        last_sig = sig

        if i < max_scrolls:
            # 交替使用两种滑动速度，避免跳过内容
            if i % 3 == 0:
                swipe_slow()
            else:
                swipe_up(500)
            time.sleep(1.5)

    return all_texts

def save_raw(texts, prefix="taobao_orders"):
    """保存原始数据"""
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    path = os.path.join(OUT, f"{prefix}_{ts}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# 淘宝订单深度采集\n")
        f.write(f"# 时间: {datetime.now()}\n")
        f.write(f"# 设备: OnePlus NE2210 (158377ff)\n")
        f.write(f"# 总行数: {len(texts)}\n\n")
        for line in texts:
            f.write(f"{line}\n")
    print(f"💾 原始数据已保存: {path}")
    return path

def parse_taobao_orders(texts):
    """解析淘宝订单文本为结构化数据"""
    orders = []
    current = {}

    # 店铺名关键词
    store_keywords = ["旗舰店", "专营店", "书店", "书城", "书社", "数码",
                      "制袋厂", "百佳龙", "掏书铺", "专卖店", "官方店",
                      "自营", "工厂店", "企业店", "店铺", "商行", "贸易",
                      "科技", "电子", "文具", "服饰", "鞋类"]

    # 应该跳过的UI文本
    skip_keywords = ["未选中", "已选中", "按钮", "搜索", "筛选", "管理",
                     "退货宝", "假一赔四", "极速退款", "先用后付",
                     "确认收货", "延长收货", "查看物流", "更多操作",
                     "加入购物车", "闲鱼转卖", "再买一单", "申请开票",
                     "删除订单", "回到顶部", "催发货", "修改地址",
                     "大促价保", "小贴士", "7天无理由", "实付款",
                     "商品被拆分", "反馈", "可提前付款", "今日闪购",
                     "确认收货后", "全部订单", "全部", "待付款",
                     "待发货", "待收货", "退款/售后", "消息", "返回",
                     "跳往搜索页", "搜索订单", "订单管理", "购物",
                     "闪购", "飞猪", "评价", "关闭", "更多", "合计"]

    # 订单状态
    statuses = ["已发货", "卖家已发货", "已签收", "已签收,待确认收货",
                "交易关闭", "交易成功", "待寄出", "待发货", "待付款",
                "待收货", "退款成功", "退款中"]

    for line in texts:
        line = line.strip()
        if not line or line.startswith("---") or line.startswith("#"):
            continue

        # 检测店铺名
        is_store = any(kw in line for kw in store_keywords) and len(line) < 30
        if is_store:
            if current and current.get("product"):
                orders.append(current)
            current = {"store": line, "product": "", "price": "",
                      "status": "", "shipping": "", "qty": ""}
            continue

        # 检测价格
        if line.startswith("¥"):
            price = line.replace("¥", "").strip()
            if current and not current.get("price"):
                current["price"] = price
            continue

        # 检测数量
        if line.startswith("×"):
            if current:
                current["qty"] = line
            continue

        # 检测状态
        if line in statuses:
            if current:
                current["status"] = line
            continue

        # 检测物流信息
        if ("签收" in line and ("自提" in line or "快递" in line)) or \
           ("发货" in line and "月" in line):
            if current:
                current["shipping"] = line[:80]
            continue

        # 跳过UI文本
        if any(kw in line for kw in skip_keywords):
            continue

        # 商品名（长文本，含中文）
        if len(line) > 10 and current and not current.get("product"):
            has_cn = any('\u4e00' <= c <= '\u9fff' for c in line[:10])
            if has_cn:
                current["product"] = line

    if current and current.get("product"):
        orders.append(current)

    return orders

def generate_report(orders, raw_path):
    """生成结构化Markdown报告"""
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_path = os.path.join(OUT, f"淘宝订单完整报告_{ts}.md")

    # 统计
    total_price = 0
    status_count = {}
    for o in orders:
        try:
            p = float(o.get("price", "0").replace(",", ""))
            total_price += p
        except:
            pass
        st = o.get("status", "未知")
        status_count[st] = status_count.get(st, 0) + 1

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# 淘宝订单完整报告\n\n")
        f.write(f"> 采集时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"> 设备: OnePlus NE2210\n")
        f.write(f"> 方式: ADB自动化 (uiautomator dump + input swipe)\n")
        f.write(f"> 原始数据: {os.path.basename(raw_path)}\n\n")

        f.write("## 概览\n\n")
        f.write(f"- **总订单数**: {len(orders)}笔\n")
        f.write(f"- **总金额**: ¥{total_price:.2f}\n")
        f.write(f"- **订单状态分布**:\n")
        for st, cnt in sorted(status_count.items(), key=lambda x: -x[1]):
            f.write(f"  - {st or '未知'}: {cnt}笔\n")
        f.write("\n")

        f.write("## 订单明细\n\n")
        f.write("| # | 商品 | 价格 | 店铺 | 状态 | 数量 |\n")
        f.write("|---|------|------|------|------|------|\n")
        for i, o in enumerate(orders, 1):
            prod = o.get("product", "")[:55]
            price = o.get("price", "?")
            store = o.get("store", "")[:18]
            status = o.get("status", "")
            qty = o.get("qty", "")
            f.write(f"| {i} | {prod} | ¥{price} | {store} | {status} | {qty} |\n")

        f.write(f"\n## 物流信息\n\n")
        has_shipping = [o for o in orders if o.get("shipping")]
        if has_shipping:
            for o in has_shipping:
                f.write(f"- **{o.get('store','')}**: {o['shipping']}\n")
        else:
            f.write("无物流信息（需展开订单详情才能获取）\n")

        # JSON导出
        f.write(f"\n## 结构化数据 (JSON)\n\n")
        f.write("```json\n")
        f.write(json.dumps(orders, ensure_ascii=False, indent=2))
        f.write("\n```\n")

    print(f"📊 报告已生成: {report_path}")
    return report_path

# ============================================================
# 入口
# ============================================================

def main():
    print(f"{'='*50}")
    print(f"🛒 淘宝订单深度采集")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📱 OnePlus NE2210 (158377ff)")
    print(f"{'='*50}")

    # 唤醒屏幕
    wake()
    time.sleep(1)

    # Step 1: 打开淘宝订单页
    ok, msg = open_taobao_orders()
    if not ok:
        print(f"❌ {msg}")
        return

    time.sleep(2)

    # Step 2: 深度滚动采集
    raw_texts = deep_scroll_collect(max_scrolls=50)

    # Step 3: 保存原始数据
    raw_path = save_raw(raw_texts)

    # Step 4: 解析为结构化订单
    orders = parse_taobao_orders(raw_texts)
    print(f"\n📦 解析出 {len(orders)} 笔订单")

    # Step 5: 生成报告
    report_path = generate_report(orders, raw_path)

    # 回到桌面
    home()

    print(f"\n{'='*50}")
    print(f"✅ 采集完成!")
    print(f"📦 订单数: {len(orders)}笔")
    print(f"📄 原始数据: {raw_path}")
    print(f"📊 结构化报告: {report_path}")
    print(f"{'='*50}")

    return orders

if __name__ == "__main__":
    main()
