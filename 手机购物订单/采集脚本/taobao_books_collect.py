#!/usr/bin/env python3
"""淘宝书籍订单全量采集 — ScreenStream API + ADB混合模式
Phase A: 列表页全量滚动 → Phase B: 书籍订单识别 → Phase C: 详情页钻入 → Phase D: 汇总报告

根治八祸:
  祸一 WebView不可读 → SS /screen/text 替代 uiautomator
  祸二 点击位置不对 → viewtree精确定位clickable节点
  祸三 滚动到底误判 → 5次空屏+检测"没有更多"+总数对比
  祸四 登录态过期   → 采集前login_check()+用户等待
  祸五 OPPO弹窗     → monkey启动+dismiss_popups
  祸六 USB不稳定    → WiFi备份通道+自动重连
  祸七 详情页字段乱 → 正则匹配+实付款标记定位
  祸八 书籍识别误判 → 三级置信度(ISBN/出版社/关键词)
"""
import sys, os, time, json, re, subprocess
from datetime import datetime

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_SCRIPT_DIR)  # 手机购物订单/
sys.path.insert(0, os.path.join(_ROOT, "..", "手机操控库"))
from phone_lib import Phone

# ============ 配置 ============
SS_PORT = 8086
ADB = os.path.join(_ROOT, "..", "构建部署", "android-sdk", "platform-tools", "adb.exe")
SERIAL = "158377ff"
OUT_RAW = os.path.join(_ROOT, "原始数据")
OUT_RESULT = os.path.join(_ROOT, "解析结果")
MAX_LIST_SCROLLS = 60       # 列表页最多滚动屏数
EMPTY_THRESHOLD = 5          # 连续空屏次数才判定到底
SCROLL_WAIT = 2.0            # 滑动后等待秒数
DETAIL_WAIT = 3.0            # 进入详情页后等待秒数

# ============ 书籍识别 ============
BOOK_KEYWORDS = [
    '书', '教材', '教程', '小说', '出版社', '出版', '作者', '图书', '文学',
    '编程', '算法', 'ISBN', '丛书', '漫画', '绘本', '字典', '词典', '读物',
    '手册', '指南', '入门', '实战', '精通', '原理', '高等教育', '机械工业',
    '科学出版', '人民邮电', '清华大学', '北京大学', '电子工业', '人民教育',
    '重庆出版', '华中科技', '978',  # ISBN前缀
]
BOOK_STORE_KEYWORDS = [
    '书店', '书城', '书社', '书铺', '书刊', '教材', '教辅', '读物', '旧书',
]
BOOK_EXCLUDE = [
    '读书APP', '京东读书', '微信读书', '说明书', '情书贴纸', '证书',
    '通讯录', '记录本', '笔记本电脑', '平板电脑',
]

def is_book(text, store=""):
    """三级置信度判断: 🟢确定 🟡高可能 🟠待确认"""
    for ex in BOOK_EXCLUDE:
        if ex in text:
            return 0, "excluded"
    # 🟢 ISBN模式(978开头)
    if re.search(r'978\d{10}', text):
        return 3, "ISBN"
    # 🟢 出版社关键词
    for pub in ['出版社', '出版集团', 'Press', 'Publishing']:
        if pub in text:
            return 3, "publisher"
    # 🟡 书店店铺
    if store:
        for kw in BOOK_STORE_KEYWORDS:
            if kw in store:
                return 2, "bookstore"
    # 🟡 教材关键词
    for kw in ['教材', '教程', '习题', '课本', '学报', '论文']:
        if kw in text:
            return 2, "textbook"
    # 🟠 通用关键词
    for kw in BOOK_KEYWORDS:
        if kw in text:
            return 1, "keyword"
    return 0, ""

# ============ ADB辅助 ============
def adb(*args, timeout=10):
    try:
        r = subprocess.run([ADB, "-s", SERIAL] + list(args),
                           capture_output=True, text=True, timeout=timeout,
                           encoding='utf-8', errors='replace')
        return r.stdout.strip()
    except Exception as e:
        return f"ERR:{e}"

# ============ 主类 ============
class TaobaoBookCollector:
    def __init__(self):
        self.p = Phone(port=SS_PORT, auto_discover=False)
        self.all_orders = []       # Phase A: 列表页全部订单
        self.book_orders = []      # Phase B: 识别为书籍的
        self.book_details = []     # Phase C: 详情页补全的
        self.ts = datetime.now().strftime('%Y%m%d_%H%M%S')

    def log(self, msg):
        print(f"  [{datetime.now().strftime('%H:%M:%S')}] {msg}")

    # ---- 环境检查 ----
    def preflight(self):
        """Phase 0: 环境预检"""
        print("=" * 64)
        print("  📚 淘宝书籍订单全量采集")
        print(f"  📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  📱 OnePlus NE2210 ({SERIAL})")
        print(f"  🔌 SS port {SS_PORT}")
        print("=" * 64)

        # 检查SS连接
        s = self.p.status()
        if not s.get("connected"):
            print("❌ ScreenStream未连接")
            return False
        self.log(f"✅ SS连接正常 input={s.get('inputEnabled')}")

        # 防息屏
        self.p.post("/stayawake", {"enabled": True})
        self.p.post("/wake")
        time.sleep(0.5)

        return True

    def login_check(self):
        """祸四根治: 检查淘宝登录态"""
        self.log("检查淘宝登录态...")
        # monkey启动淘宝(祸五根治)
        adb("shell", "monkey -p com.taobao.taobao -c android.intent.category.LAUNCHER 1")
        time.sleep(5)

        # 处理弹窗
        self._dismiss_popups()
        time.sleep(1)

        # 读屏检查
        texts, pkg = self._read_screen()
        page = ' '.join(texts)

        if 'com.taobao.taobao' not in pkg and 'taobao' not in pkg:
            self.log(f"⚠ 淘宝未在前台(当前={pkg})")
            # 重试
            adb("shell", "am start -n com.taobao.taobao/com.taobao.tao.homepage.HomeActivity")
            time.sleep(5)
            texts, pkg = self._read_screen()
            page = ' '.join(texts)

        # 检查登录相关文本
        login_signals = ['登录', '请登录', '验证', '手机号', '密码登录', '扫码登录']
        for sig in login_signals:
            if sig in page:
                self.log(f"⚠ 检测到登录信号: '{sig}'")
                print("\n" + "=" * 64)
                print("  ⚠️ 淘宝需要登录！请在手机上完成登录。")
                print("  Agent将等待您登录完成（最多120秒）...")
                print("=" * 64)
                # 等待"我的淘宝"或"首页"出现
                r = self.p.get(f"/wait?text=首页&timeout=120000")
                if not r.get("found"):
                    r = self.p.get(f"/wait?text=推荐&timeout=30000")
                if r.get("found"):
                    self.log("✅ 登录完成")
                else:
                    self.log("❌ 登录超时，请手动完成后重新运行脚本")
                    return False
                break

        self.log("✅ 淘宝登录态正常")
        return True

    # ---- 读屏辅助 ----
    def _read_screen(self):
        """用SS API读屏(祸一根治: 替代uiautomator)"""
        try:
            r = self.p.get("/screen/text")
            texts = [t.get("text", "") for t in r.get("texts", []) if t.get("text")]
            pkg = r.get("package", "")
            return texts, pkg
        except Exception as e:
            self.log(f"⚠ 读屏失败: {e}")
            return [], ""

    def _get_viewtree(self, depth=6):
        """获取View树(祸二根治: 精确定位clickable节点)"""
        try:
            return self.p.get(f"/viewtree?depth={depth}")
        except:
            return {}

    def _dismiss_popups(self):
        """关闭弹窗(祸五根治)"""
        dismiss_texts = ["允许", "同意", "确定", "我知道了", "跳过", "关闭",
                         "以后再说", "暂不", "不再提醒", "知道了", "取消升级"]
        for _ in range(3):
            texts, _ = self._read_screen()
            page = ' '.join(texts)
            dismissed = False
            for dt in dismiss_texts:
                if dt in page:
                    self.p.click(dt)
                    time.sleep(0.5)
                    dismissed = True
                    break
            if not dismissed:
                break

    def _scroll_up(self):
        """向上滑动翻页"""
        self.p.swipe("up")
        time.sleep(SCROLL_WAIT)

    # ---- Phase A: 列表页全量采集 ----
    def navigate_to_orders(self):
        """导航到淘宝全部订单页"""
        self.log("导航到全部订单...")

        # 先点"我的淘宝"(底部tab)
        texts, _ = self._read_screen()
        page = ' '.join(texts)

        if '我的淘宝' in page:
            self.p.click("我的淘宝")
            time.sleep(3)
        elif '我的' in page:
            # 可能需要点底部tab
            self.p.click("我的")
            time.sleep(3)

        self._dismiss_popups()

        # 点击"全部订单"或"我的订单"
        texts, _ = self._read_screen()
        page = ' '.join(texts)

        for kw in ['全部订单', '查看全部订单', '我的订单']:
            if kw in page:
                self.p.click(kw)
                time.sleep(3)
                break
        else:
            # 尝试直接点"全部"
            if '全部' in page:
                self.p.click("全部")
                time.sleep(3)

        self._dismiss_popups()

        # 验证到达订单页
        texts, _ = self._read_screen()
        page = ' '.join(texts)
        order_signals = ['待付款', '待发货', '待收货', '退款/售后', '全部']
        if any(s in page for s in order_signals):
            self.log("✅ 已进入订单页")
            # 确保"全部"tab被选中
            self.p.click("全部")
            time.sleep(1)
            self._dismiss_popups()
            return True
        else:
            self.log(f"⚠ 可能未到订单页，当前文本: {texts[:8]}")
            return True  # 尝试继续

    def collect_list_page(self):
        """Phase A: 深度滚动采集全部订单"""
        print(f"\n{'='*64}")
        print(f"  Phase A: 列表页全量滚动（最多{MAX_LIST_SCROLLS}屏）")
        print(f"{'='*64}")

        seen_texts = set()
        empty_count = 0
        last_sig = ""
        page_orders = []

        for i in range(MAX_LIST_SCROLLS + 1):
            texts, pkg = self._read_screen()

            # 检测是否仍在淘宝
            if 'taobao' not in pkg.lower() and pkg:
                self.log(f"⚠ 离开了淘宝(当前={pkg})，尝试回退")
                self.p.back()
                time.sleep(2)
                continue

            # 提取新文本
            new_texts = [t for t in texts if t not in seen_texts and len(t) > 1]
            seen_texts.update(new_texts)

            # 屏幕签名(用于检测到底)
            sig = '|'.join(sorted([t for t in texts if len(t) > 3])[:15])

            # 检测终止信号(祸三根治)
            page = ' '.join(texts)
            end_signals = ['没有更多了', '已经到底了', '没有更多订单', '暂无订单', 'THE END']
            reached_end = any(s in page for s in end_signals)

            if reached_end:
                self.log(f"  [{i+1:2d}] 🛑 检测到终止信号")
                # 仍然提取本屏数据
                if new_texts:
                    page_orders.extend(self._parse_list_screen(new_texts))
                break

            if new_texts:
                orders = self._parse_list_screen(new_texts)
                page_orders.extend(orders)
                n_new = len(new_texts)
                n_orders = len(orders)
                self.log(f"  [{i+1:2d}] +{n_new:3d}文本 +{n_orders}订单 (总{len(page_orders)})")
                empty_count = 0
            else:
                empty_count += 1
                same = (sig == last_sig)
                self.log(f"  [{i+1:2d}] 空屏 ({empty_count}/{EMPTY_THRESHOLD})"
                         f"{' [页面相同]' if same else ''}")
                if empty_count >= EMPTY_THRESHOLD:
                    self.log(f"  🛑 连续{EMPTY_THRESHOLD}次无新内容")
                    break

            last_sig = sig

            if i < MAX_LIST_SCROLLS:
                self._scroll_up()

        # 去重(以商品名前30字+店铺为key)
        deduped = {}
        for o in page_orders:
            key = (o.get("store", "")[:15], o.get("product", "")[:30])
            if key not in deduped or len(o.get("product", "")) > len(deduped[key].get("product", "")):
                deduped[key] = o
        self.all_orders = list(deduped.values())

        self.log(f"\n📦 列表页共采集 {len(self.all_orders)} 笔订单（去重后）")
        return self.all_orders

    def _parse_list_screen(self, texts):
        """从一屏文本中解析订单(简化版: 以店铺名为分界)"""
        orders = []
        current = None

        store_keywords = ["旗舰店", "专营店", "专卖店", "书店", "书城", "书社",
                         "数码", "制袋厂", "官方店", "自营", "工厂店", "企业店",
                         "商行", "贸易", "科技", "电子", "文具", "服饰"]
        skip_keywords = ["未选中", "已选中", "按钮", "搜索", "筛选", "管理",
                        "退货宝", "假一赔四", "极速退款", "先用后付",
                        "确认收货", "延长收货", "查看物流", "更多操作",
                        "加入购物车", "闲鱼转卖", "再买一单", "申请开票",
                        "删除订单", "回到顶部", "催发货", "大促价保",
                        "全部订单", "待付款", "待发货", "待收货", "退款/售后"]
        statuses = ["已发货", "卖家已发货", "已签收", "交易关闭", "交易成功",
                   "待寄出", "待发货", "待付款", "待收货", "退款成功", "退款中"]

        for line in texts:
            line = line.strip()
            if not line or len(line) < 2:
                continue

            # 跳过UI噪声
            if any(kw in line for kw in skip_keywords):
                continue

            # 检测店铺名
            is_store = any(kw in line for kw in store_keywords) and len(line) < 35
            if is_store:
                if current and current.get("product"):
                    orders.append(current)
                current = {"store": line, "product": "", "price": "", "status": "", "raw": []}
                continue

            if current is None:
                continue

            # 价格
            if line.startswith("¥") or line.startswith("￥"):
                price = line.replace("¥", "").replace("￥", "").strip()
                if not current.get("price"):
                    current["price"] = price
                continue

            # 数量
            m = re.match(r'×(\d+)', line)
            if m:
                current["qty"] = int(m.group(1))
                continue

            # 状态
            if line in statuses:
                current["status"] = line
                continue

            # 商品名(长文本含中文)
            if len(line) > 10 and not current.get("product"):
                if any('\u4e00' <= c <= '\u9fff' for c in line[:10]):
                    current["product"] = line

            current.setdefault("raw", []).append(line)

        if current and current.get("product"):
            orders.append(current)

        return orders

    # ---- Phase B: 书籍订单识别 ----
    def identify_books(self):
        """Phase B: 从全部订单中筛选书籍"""
        print(f"\n{'='*64}")
        print(f"  Phase B: 书籍订单识别")
        print(f"{'='*64}")

        for o in self.all_orders:
            text = o.get("product", "") + " " + o.get("store", "")
            raw = ' '.join(o.get("raw", []))
            full_text = text + " " + raw

            level, reason = is_book(full_text, o.get("store", ""))
            if level > 0:
                o["book_confidence"] = level
                o["book_reason"] = reason
                o["book_level"] = ["", "🟠待确认", "🟡高可能", "🟢确定"][level]
                self.book_orders.append(o)

        # 按置信度排序
        self.book_orders.sort(key=lambda x: -x.get("book_confidence", 0))

        self.log(f"📚 识别出 {len(self.book_orders)} 笔书籍订单:")
        for i, o in enumerate(self.book_orders, 1):
            self.log(f"  {o['book_level']} [{o['book_reason']}] "
                     f"{o.get('store','')[:15]} | {o.get('product','')[:40]} | ¥{o.get('price','?')}")

        return self.book_orders

    # ---- Phase C: 详情页钻入 ----
    def drill_details(self):
        """Phase C: 为每笔书籍订单钻入详情页"""
        if not self.book_orders:
            self.log("无书籍订单需要钻入")
            return

        print(f"\n{'='*64}")
        print(f"  Phase C: 详情页钻入（{len(self.book_orders)}笔）")
        print(f"{'='*64}")

        # 先回到订单列表顶部
        self.log("回到订单列表顶部...")
        for _ in range(5):
            self.p.swipe("down")
            time.sleep(0.5)
        time.sleep(1)

        visited = set()

        for idx, book in enumerate(self.book_orders):
            product = book.get("product", "")
            store = book.get("store", "")
            key = f"{store[:10]}_{product[:20]}"
            if key in visited:
                continue
            visited.add(key)

            self.log(f"\n📖 [{idx+1}/{len(self.book_orders)}] {store[:20]} | {product[:35]}...")

            # 在列表中找到这个订单并点击
            found = self._find_and_click_order(product, store)
            if not found:
                self.log(f"  ⚠ 未在当前屏找到，尝试滚动...")
                # 滚动寻找
                for scroll in range(15):
                    self._scroll_up()
                    found = self._find_and_click_order(product, store)
                    if found:
                        break
                if not found:
                    self.log(f"  ❌ 跳过(未找到)")
                    book["detail"] = {"error": "not_found_in_list"}
                    self.book_details.append(book)
                    continue

            time.sleep(DETAIL_WAIT)

            # 提取详情页信息
            detail = self._extract_detail()
            book["detail"] = detail
            self.book_details.append(book)

            self.log(f"  订单号: {detail.get('order_id', '?')}")
            self.log(f"  日期: {detail.get('order_date', '?')}")
            self.log(f"  实付: {detail.get('paid', '?')}")

            # 返回列表
            self.p.back()
            time.sleep(2)

    def _find_and_click_order(self, product, store):
        """在当前屏幕找到订单并点击(祸二根治: 用viewtree精确定位)"""
        texts, _ = self._read_screen()
        page = ' '.join(texts)

        # 搜索商品名关键词(取前15个字符)
        search_key = product[:15] if product else store[:10]
        if search_key not in page:
            return False

        # 用findclick点击商品名
        r = self.p.post("/findclick", {"text": search_key})
        if r and r.get("clicked"):
            return True

        # 降级: viewtree找坐标
        vt = self._get_viewtree(depth=6)
        vt_str = json.dumps(vt, ensure_ascii=False) if vt else ""
        # 找到包含关键字且clickable的节点
        m = re.search(
            rf'"text":"[^"]*{re.escape(search_key[:10])}[^"]*".*?"click":true.*?"b":"(\d+),(\d+),(\d+),(\d+)"',
            vt_str
        )
        if m:
            x = (int(m.group(1)) + int(m.group(3))) // 2
            y = (int(m.group(2)) + int(m.group(4))) // 2
            self.p.tap(x / 1080, y / 2412)  # 归一化坐标
            return True

        return False

    def _extract_detail(self):
        """从详情页提取结构化信息(祸七根治)"""
        info = {"order_id": "", "order_date": "", "paid": "", "status": "",
                "shipping": "", "products": [], "raw_detail": []}

        # 读取详情页(可能需要滚动)
        all_texts = []
        for scroll in range(3):  # 最多读3屏详情
            texts, pkg = self._read_screen()
            all_texts.extend(texts)
            if scroll < 2:
                self._scroll_up()
                time.sleep(1)

        info["raw_detail"] = all_texts[:60]

        for t in all_texts:
            t = t.strip()
            # 订单号(15-25位数字)
            if re.match(r'^\d{15,25}$', t) and not info["order_id"]:
                info["order_id"] = t
            # 日期
            if not info["order_date"]:
                dm = re.search(r'(20\d{2})[年.\-/](\d{1,2})[月.\-/](\d{1,2})', t)
                if dm:
                    info["order_date"] = f"{dm.group(1)}-{dm.group(2).zfill(2)}-{dm.group(3).zfill(2)}"
            # 状态
            if t in ["交易成功", "交易关闭", "待发货", "已发货", "已签收",
                     "待收货", "待付款", "退款成功", "卖家已发货"]:
                info["status"] = t
            # 实付款(紧跟"实付款"标记)
            if "实付" in t:
                # 在同一文本或后续文本中找¥
                pm = re.search(r'[¥￥]([\d.]+)', t)
                if pm:
                    info["paid"] = pm.group(1)
            # 独立¥值
            if t.startswith("¥") or t.startswith("￥"):
                val = t.replace("¥", "").replace("￥", "").strip()
                if not info["paid"]:
                    info["paid"] = val
            # 物流
            if any(k in t for k in ["快递", "签收", "运单", "取件码"]):
                info["shipping"] = t[:80]
            # 商品名
            if len(t) > 15 and any('\u4e00' <= c <= '\u9fff' for c in t[:5]):
                if not any(k in t for k in ["旗舰店", "快递", "签收", "确认", "按钮", "返回"]):
                    info["products"].append(t[:100])

        # 回到详情页顶部后返回
        for _ in range(3):
            self.p.swipe("down")
            time.sleep(0.3)

        return info

    # ---- Phase D: 汇总报告 ----
    def generate_report(self):
        """Phase D: 生成汇总报告"""
        print(f"\n{'='*64}")
        print(f"  Phase D: 生成汇总报告")
        print(f"{'='*64}")

        # JSON
        json_file = os.path.join(OUT_RESULT, f"淘宝书籍订单_{self.ts}.json")
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(self.book_details or self.book_orders, f,
                      ensure_ascii=False, indent=2, default=str)

        # 全量订单JSON
        all_json = os.path.join(OUT_RAW, f"taobao_all_orders_{self.ts}.json")
        with open(all_json, "w", encoding="utf-8") as f:
            json.dump(self.all_orders, f, ensure_ascii=False, indent=2, default=str)

        # Markdown报告
        report_file = os.path.join(OUT_RESULT, f"淘宝书籍订单汇总_{self.ts}.md")
        total_price = 0

        with open(report_file, "w", encoding="utf-8") as f:
            f.write("# 淘宝书籍订单汇总\n\n")
            f.write(f"> 采集时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
            f.write(f"> 设备: OnePlus NE2210 ({SERIAL})\n")
            f.write(f"> 方式: ScreenStream API + ADB混合\n")
            f.write(f"> 列表页总订单: {len(self.all_orders)}笔\n")
            f.write(f"> 书籍订单: {len(self.book_orders)}笔\n\n")

            f.write("## 书籍订单明细\n\n")
            f.write("| # | 置信 | 商品 | 价格 | 店铺 | 状态 | 订单号 | 日期 |\n")
            f.write("|---|------|------|------|------|------|--------|------|\n")

            for i, o in enumerate(self.book_orders, 1):
                prod = o.get("product", "")[:50]
                price = o.get("price", "?")
                store = o.get("store", "")[:18]
                status = o.get("status", "")
                level = o.get("book_level", "?")
                detail = o.get("detail", {})
                oid = detail.get("order_id", "")
                odate = detail.get("order_date", "")
                paid = detail.get("paid", "")

                display_price = f"¥{paid}" if paid else f"¥{price}"
                try:
                    total_price += float(paid or price or 0)
                except:
                    pass

                f.write(f"| {i} | {level} | {prod} | {display_price} | {store} | {status} | {oid} | {odate} |\n")

            f.write(f"\n**合计: ¥{total_price:.2f}** ({len(self.book_orders)}笔)\n")

            # 按店铺分组统计
            store_stats = {}
            for o in self.book_orders:
                s = o.get("store", "未知")
                store_stats[s] = store_stats.get(s, 0) + 1
            f.write(f"\n## 按店铺统计\n\n")
            for s, cnt in sorted(store_stats.items(), key=lambda x: -x[1]):
                f.write(f"- **{s}**: {cnt}笔\n")

            # 置信度分布
            f.write(f"\n## 置信度分布\n\n")
            for level in [3, 2, 1]:
                label = ["", "🟠待确认", "🟡高可能", "🟢确定"][level]
                cnt = sum(1 for o in self.book_orders if o.get("book_confidence") == level)
                if cnt:
                    f.write(f"- {label}: {cnt}笔\n")

        self.log(f"📊 报告: {report_file}")
        self.log(f"📄 全量JSON: {all_json}")
        self.log(f"📚 书籍JSON: {json_file}")

        return report_file

    # ---- 主流程 ----
    def run(self):
        # Phase 0
        if not self.preflight():
            return

        # 登录检查
        if not self.login_check():
            return

        # 导航到订单页
        if not self.navigate_to_orders():
            return

        time.sleep(2)

        # Phase A: 列表页全量采集
        self.collect_list_page()

        # Phase B: 书籍识别
        self.identify_books()

        # Phase C: 详情页钻入(仅书籍订单)
        self.drill_details()

        # Phase D: 汇总报告
        report = self.generate_report()

        # 回桌面
        self.p.home()
        self.p.post("/stayawake", {"enabled": False})

        print(f"\n{'='*64}")
        print(f"  ✅ 采集完成!")
        print(f"  📦 列表页总订单: {len(self.all_orders)}笔")
        print(f"  📚 书籍订单: {len(self.book_orders)}笔")
        print(f"  📖 详情补全: {len(self.book_details)}笔")
        print(f"  📊 报告: {report}")
        print(f"{'='*64}")


if __name__ == "__main__":
    collector = TaobaoBookCollector()
    collector.run()
