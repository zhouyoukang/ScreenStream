#!/usr/bin/env python3
"""扫描所有购物平台的书籍类订单"""
import sys, os, time, json
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_SCRIPT_DIR)  # 手机购物订单/
sys.path.insert(0, os.path.join(_ROOT, "..", "手机操控库"))
from phone_lib import Phone

p = Phone(port=8084)
BOOK_KEYWORDS = ['书', '教材', '教程', '小说', '出版', '作者', '图书', '文学', '编程',
                 '算法', 'ISBN', '丛书', '漫画', '绘本', '字典', '词典', '读物',
                 '手册', '指南', '入门', '实战', '精通', '原理', '笔记本子']
# 排除误匹配
EXCLUDE = ['读书APP', '京东读书', '微信读书', '说明书', '情书贴纸', '证书']

all_orders = []  # 收集所有书籍订单

def is_book(text):
    """判断文本是否与书籍相关"""
    for ex in EXCLUDE:
        if ex in text:
            return False
    return any(kw in text for kw in BOOK_KEYWORDS)

def read_screen():
    """读取屏幕文本，返回(texts_list, pkg)"""
    r = p.get("/screen/text")
    texts = [t.get("text", "") for t in r.get("texts", [])]
    pkg = r.get("package", "")
    return texts, pkg

def scroll_and_collect(platform, max_scrolls=8):
    """滚动收集当前页面的订单信息，筛选书籍"""
    found = []
    seen_texts = set()

    for i in range(max_scrolls):
        texts, pkg = read_screen()
        page_text = ' | '.join(texts)

        # 去重：如果文本和上一页完全一样说明到底了
        text_hash = hash(page_text[:200])
        if text_hash in seen_texts:
            print(f"    [{platform}] 第{i+1}页：到底了")
            break
        seen_texts.add(text_hash)

        # 搜索书籍关键词
        for t in texts:
            if is_book(t) and len(t) > 4:
                found.append(t)

        if texts:
            print(f"    [{platform}] 第{i+1}页：{len(texts)}个文本元素" +
                  (f"，发现书籍相关: {[f for f in found if f not in [x for x in found[:-3]]]}" if found else ""))
        else:
            print(f"    [{platform}] 第{i+1}页：(空/WebView)")

        # 向上滑动翻页
        p.swipe("up")
        time.sleep(1.5)

    return found

def open_app_safe(pkg, name):
    """安全打开APP，处理OPPO弹窗"""
    print(f"\n{'='*60}")
    print(f"  📱 打开 {name} ({pkg})")
    print(f"{'='*60}")

    p.post("/openapp", {"packageName": pkg})
    time.sleep(4)

    # 检查OPPO安全弹窗
    for attempt in range(3):
        texts, cur_pkg = read_screen()
        page = ' '.join(texts)

        if 'securitypermission' in cur_pkg or '想要打开' in page:
            print(f"    ⚠️ OPPO弹窗，点击允许...")
            # 用viewtree找精确的"打开"按钮
            vt = p.get("/viewtree?depth=6")
            vt_str = json.dumps(vt, ensure_ascii=False)
            if '"text":"打开","id":"android:id/button1"' in vt_str:
                # 先勾选始终允许
                p.post("/findclick", {"text": "始终允许打开"})
                time.sleep(0.3)
                # 解析打开按钮的bounds
                import re
                m = re.search(r'"text":"打开","id":"android:id/button1","click":true,"b":"(\d+),(\d+),(\d+),(\d+)"', vt_str)
                if m:
                    x = (int(m.group(1)) + int(m.group(3))) // 2
                    y = (int(m.group(2)) + int(m.group(4))) // 2
                    p.post("/tap", {"x": x, "y": y})
                    time.sleep(3)
                    continue
            # 回退：直接点
            p.post("/findclick", {"text": "打开"})
            time.sleep(3)
        else:
            break

    fg = p.foreground()
    actual_pkg = fg.get("packageName", "")
    if pkg.split('.')[1] in actual_pkg or actual_pkg == pkg:
        print(f"    ✅ {name} 已打开 (pkg={actual_pkg})")
        return True
    else:
        print(f"    ❌ {name} 未打开 (当前={actual_pkg})")
        return False

def scan_taobao():
    """扫描淘宝订单"""
    if not open_app_safe("com.taobao.taobao", "淘宝"):
        return []

    # 导航到我的淘宝
    texts, _ = read_screen()
    page = ' '.join(texts)

    # 如果不在首页，先回首页
    if '我的淘宝' not in page:
        p.home()
        time.sleep(1)
        p.post("/openapp", {"packageName": "com.taobao.taobao"})
        time.sleep(3)

    # 多次尝试进入我的淘宝
    for _ in range(3):
        texts, _ = read_screen()
        if '我的淘宝' in ' '.join(texts):
            p.click("我的淘宝")
            time.sleep(3)
            break
        p.back()
        time.sleep(1)

    # 点击全部订单
    texts, _ = read_screen()
    page = ' '.join(texts)
    if '我的订单' in page:
        p.click("我的订单全部")
        time.sleep(3)
    elif '全部订单' in page or '待发货' in page:
        pass  # 已经在订单页
    else:
        print("    ⚠️ 未找到订单入口")
        return []

    # 滚动扫描
    found = scroll_and_collect("淘宝")

    # 回桌面
    p.home()
    time.sleep(1)
    return found

def scan_jd():
    """扫描京东订单"""
    if not open_app_safe("com.jingdong.app.mall", "京东"):
        return []

    time.sleep(2)
    texts, _ = read_screen()
    page = ' '.join(texts)

    # 点击"我的"Tab
    if '我的' in page:
        p.click("我的")
        time.sleep(2)

    texts, _ = read_screen()
    page = ' '.join(texts)

    # 点击全部订单
    if '全部订单' in page:
        p.click("全部订单")
        time.sleep(3)
    elif '我的订单' in page:
        p.click("我的订单")
        time.sleep(3)

    found = scroll_and_collect("京东")
    p.home()
    time.sleep(1)
    return found

def scan_pdd():
    """扫描拼多多订单"""
    if not open_app_safe("com.xunmeng.pinduoduo", "拼多多"):
        return []

    time.sleep(2)
    texts, _ = read_screen()
    page = ' '.join(texts)

    # 点击"个人中心"Tab
    if '个人中心' in page:
        p.click("个人中心")
        time.sleep(2)

    texts, _ = read_screen()
    page = ' '.join(texts)

    # 点击全部订单/我的订单
    for kw in ['全部', '我的订单', '查看全部']:
        if kw in page:
            p.click(kw)
            time.sleep(3)
            break

    found = scroll_and_collect("拼多多")
    p.home()
    time.sleep(1)
    return found

def scan_dangdang():
    """扫描当当订单"""
    if not open_app_safe("com.dangdang.buy2", "当当"):
        return []

    time.sleep(2)
    texts, _ = read_screen()
    page = ' '.join(texts)

    # 当当底部Tab：首页/分类/购物车/我的
    if '我的' in page:
        p.click("我的")
        time.sleep(2)

    texts, _ = read_screen()
    page = ' '.join(texts)

    for kw in ['全部订单', '我的订单', '查看全部订单']:
        if kw in page:
            p.click(kw)
            time.sleep(3)
            break

    found = scroll_and_collect("当当")
    p.home()
    time.sleep(1)
    return found

def scan_xianyu():
    """扫描闲鱼订单"""
    if not open_app_safe("com.taobao.idlefish", "闲鱼"):
        return []

    time.sleep(2)
    texts, _ = read_screen()
    page = ' '.join(texts)

    # 闲鱼底部：闲鱼/消息/卖闲置/我的
    if '我的' in page:
        p.click("我的")
        time.sleep(2)

    texts, _ = read_screen()
    page = ' '.join(texts)

    for kw in ['我买到的', '已买到', '购买记录']:
        if kw in page:
            p.click(kw)
            time.sleep(3)
            break

    found = scroll_and_collect("闲鱼")
    p.home()
    time.sleep(1)
    return found

def scan_zhuanzhuan():
    """扫描转转订单"""
    if not open_app_safe("com.wuba.zhuanzhuan", "转转"):
        return []

    time.sleep(2)
    texts, _ = read_screen()
    page = ' '.join(texts)

    if '我的' in page:
        p.click("我的")
        time.sleep(2)

    texts, _ = read_screen()
    page = ' '.join(texts)

    for kw in ['我买到的', '已买到', '我的订单', '全部订单']:
        if kw in page:
            p.click(kw)
            time.sleep(3)
            break

    found = scroll_and_collect("转转")
    p.home()
    time.sleep(1)
    return found

def scan_amazon():
    """扫描亚马逊订单"""
    if not open_app_safe("com.amazon.mShop.android.shopping", "亚马逊"):
        return []

    time.sleep(3)
    texts, _ = read_screen()
    page = ' '.join(texts)

    # 亚马逊底部或汉堡菜单
    for kw in ['我的', '☰', '账户', 'Your Orders', '我的订单', '订单']:
        if kw in page:
            p.click(kw)
            time.sleep(3)
            break

    found = scroll_and_collect("亚马逊")
    p.home()
    time.sleep(1)
    return found

# ==================== 主流程 ====================
print("=" * 64)
print("  📚 全平台书籍订单扫描")
print("=" * 64)

# 先检查连接
s = p.status()
if not s.get("connected"):
    print("❌ 手机未连接"); sys.exit(1)
print(f"✅ 手机已连接\n")

# 先回桌面
p.home()
time.sleep(1)

# 按优先级扫描各平台（当当/京东最可能有书）
platforms = [
    ("当当", scan_dangdang),
    ("京东", scan_jd),
    ("淘宝", scan_taobao),
    ("拼多多", scan_pdd),
    ("闲鱼", scan_xianyu),
    ("转转", scan_zhuanzhuan),
    ("亚马逊", scan_amazon),
]

results = {}
for name, scanner in platforms:
    try:
        found = scanner()
        results[name] = found
        if found:
            print(f"\n  📚 {name} 发现 {len(found)} 条书籍相关:")
            for f in found[:10]:
                print(f"    → {f[:80]}")
    except Exception as e:
        print(f"  💥 {name} 扫描异常: {e}")
        results[name] = []
        p.home()
        time.sleep(1)

# ==================== 汇总 ====================
print("\n" + "=" * 64)
print("  📊 全平台书籍订单汇总")
print("=" * 64)

total_books = 0
for name, found in results.items():
    if found:
        total_books += len(found)
        print(f"\n  📦 {name} ({len(found)}条):")
        for f in found:
            print(f"    • {f[:100]}")
    else:
        print(f"  ○ {name}: 无书籍订单")

print(f"\n  合计: {total_books} 条书籍相关订单项")
print("=" * 64)

# 最后回桌面
p.home()
