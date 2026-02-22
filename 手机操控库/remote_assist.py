"""
远程家庭协助工具 — 帮家人解决手机问题
==========================================
场景：你在外面，家人微信说"手机出问题了"。
一键连上 → 看到屏幕 → 帮他们操作 → 诊断 → 解决。

使用:
  python remote_assist.py                          # 自动发现家人手机
  python remote_assist.py --name 妈妈              # 连接已保存的家人手机
  python remote_assist.py --host 100.100.1.5       # Tailscale直连
  python remote_assist.py --scan                   # 扫描局域网所有手机
"""

import argparse, json, os, sys, time, threading
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from phone_lib import Phone, discover, NegativeState, _probe, _get_local_subnet, log

# ============================================================
# 家人手机配置管理
# ============================================================

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "family_phones.json")

def load_family():
    """加载家人手机配置"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_family(data):
    """保存家人手机配置"""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def add_family(name, host, port=8086, notes=""):
    """添加家人手机"""
    family = load_family()
    family[name] = {
        "host": host,
        "port": port,
        "notes": notes,
        "added": datetime.now().isoformat(),
        "last_connect": None,
    }
    save_family(family)
    print(f"  ✅ 已添加: {name} → {host}:{port}")

def get_family_phone(name):
    """获取家人手机配置并创建Phone"""
    family = load_family()
    if name not in family:
        print(f"  ❌ 未找到 '{name}'。已有: {', '.join(family.keys()) or '无'}")
        return None
    cfg = family[name]
    phone = Phone(host=cfg["host"], port=cfg["port"])
    # 更新最后连接时间
    cfg["last_connect"] = datetime.now().isoformat()
    save_family(family)
    return phone


# ============================================================
# 诊断报告
# ============================================================

def diagnose(phone):
    """完整手机诊断，返回问题列表和建议"""
    print("\n  🔍 正在诊断...")
    issues = []
    suggestions = []

    # 1. 连接状态
    alive, recovery_log = phone.ensure_alive()
    if not alive:
        return ["❌ 手机无法连接"], ["请让家人确认手机已开机且WiFi正常"], recovery_log

    # 2. 设备信息
    dev = phone.device()
    status = phone.status()

    # 3. 电量检查
    battery = dev.get("batteryLevel", -1)
    charging = dev.get("isCharging", False)
    if battery < 20 and not charging:
        issues.append(f"🔋 电量低: {battery}%")
        suggestions.append("请让家人把手机插上充电器")
    elif battery < 50:
        issues.append(f"🔋 电量偏低: {battery}%")

    # 4. 存储检查
    storage_mb = dev.get("storageAvailableMB", -1)
    if storage_mb >= 0:
        storage_gb = round(storage_mb / 1024, 1)
        if storage_gb < 2:
            issues.append(f"💾 存储不足: 仅剩{storage_gb}GB")
            suggestions.append("需要清理手机存储（见清理功能）")
        elif storage_gb < 5:
            issues.append(f"💾 存储偏低: {storage_gb}GB")

    # 5. 网络检查
    net_ok = dev.get("networkConnected", False)
    net_type = dev.get("networkType", "?")
    if not net_ok:
        issues.append("📶 网络断开")
        suggestions.append("请让家人检查WiFi是否连接正常")
    elif net_type == "mobile":
        issues.append("📶 使用移动数据中（非WiFi）")
        suggestions.append("如在家里，建议连接WiFi节省流量")

    # 6. 屏幕状态
    if status.get("screenOffMode", False):
        issues.append("📱 屏幕已关闭")
        phone.wake()
        suggestions.append("已自动唤醒")

    # 7. 无障碍检查
    if not status.get("inputEnabled", False):
        issues.append("⚙️ 远程操控功能未启用")
        suggestions.append("需要在手机设置中重新启用无障碍服务")

    # 8. 通知堆积
    notif = phone.notifications(30)
    notif_count = notif.get("total", 0)
    if notif_count > 20:
        issues.append(f"🔔 通知堆积: {notif_count}条未读")
        suggestions.append("建议清理通知")

    # 9. 前台应用检查
    fg = phone.foreground()
    if fg:
        issues.append(f"📱 当前打开: {fg.split('.')[-1]}")

    if not issues:
        issues = ["✅ 手机状态良好"]

    return issues, suggestions, {
        "battery": battery,
        "charging": charging,
        "storage_gb": round(storage_mb / 1024, 1) if storage_mb >= 0 else -1,
        "network": net_type,
        "net_ok": net_ok,
        "notifications": notif_count,
        "foreground": fg,
    }


# ============================================================
# 常见家庭协助场景
# ============================================================

def assist_clean_storage(phone):
    """帮家人清理手机存储"""
    print("\n  🧹 清理手机存储")
    dev = phone.device()
    before = dev.get("storageAvailableMB", 0)
    print(f"  当前可用: {round(before/1024, 1)}GB")

    # 步骤1: 打开手机管家/设置-存储
    print("  → 打开存储设置...")
    phone.intent("android.intent.action.MANAGE_ALL_APPLICATIONS_SETTINGS")
    phone.wait(2)

    # 步骤2: 检查大文件
    print("  → 检查文件...")
    files = phone.files("/sdcard/DCIM")
    if isinstance(files, dict) and "files" in files:
        total_photos = len(files["files"])
        print(f"  📸 相册: {total_photos}个文件")

    files = phone.files("/sdcard/Download")
    if isinstance(files, dict) and "files" in files:
        total_dl = len(files["files"])
        print(f"  📥 下载: {total_dl}个文件")

    # 步骤3: 建议
    print("\n  💡 建议:")
    print("  1. 把照片备份到云盘后删除手机上的")
    print("  2. 清理微信/QQ的缓存（占用最大）")
    print("  3. 卸载不用的APP")
    print("  4. 清理下载文件夹")

    return True


def assist_wifi_setup(phone):
    """帮家人连WiFi"""
    print("\n  📶 WiFi设置")
    phone.intent("android.settings.WIFI_SETTINGS")
    phone.wait(2)
    texts, _ = phone.read()
    print(f"  当前WiFi页面文本:")
    for t in texts[:10]:
        if t.strip():
            print(f"    {t}")
    print("\n  💡 操作:")
    print("  - 点击目标WiFi名称")
    print("  - 输入密码")
    print("  - 点击连接")


def assist_install_app(phone, app_name):
    """帮家人安装APP"""
    print(f"\n  📲 安装APP: {app_name}")
    # 打开应用商店搜索
    phone.intent("android.intent.action.VIEW",
                 data=f"market://search?q={app_name}")
    phone.wait(3)
    texts, pkg = phone.read()
    if "market" in pkg.lower() or "store" in pkg.lower() or "appstore" in pkg.lower():
        print(f"  ✅ 已打开应用商店，搜索: {app_name}")
        # 尝试点击安装/下载
        for btn in ["安装", "下载", "获取", "免费"]:
            r = phone.click(btn)
            if r.get("ok"):
                print(f"  → 已点击: {btn}")
                phone.wait(5)
                phone._dismiss_oppo()
                break
    else:
        print(f"  ⚠️ 应用商店未打开 (当前: {pkg})")
        print(f"  💡 尝试手动: 打开应用商店 → 搜索 '{app_name}' → 安装")


def assist_check_wechat(phone):
    """帮家人检查微信消息"""
    print("\n  💬 检查微信")
    phone.open_app("com.tencent.mm")
    phone.wait(2)
    texts, pkg = phone.read()
    if "tencent" in pkg.lower() or "mm" in pkg.lower():
        print("  ✅ 微信已打开")
        # 查找未读数
        unread = [t for t in texts if any(c.isdigit() for c in t) and len(t) <= 5]
        if unread:
            print(f"  未读: {unread}")
        # 显示聊天列表
        chats = [t for t in texts if len(t) > 2 and not t.isdigit()][:10]
        print(f"  最近聊天:")
        for c in chats:
            print(f"    {c}")
    else:
        print(f"  ⚠️ 微信未正常打开 (当前: {pkg})")


def assist_quick_pay(phone):
    """帮家人打开付款码"""
    print("\n  💳 打开付款码")
    phone.alipay("20000056")
    phone.wait(2)
    if phone.is_app("alipay") or phone.is_app("eg.android"):
        print("  ✅ 支付宝付款码已打开")
        print("  💡 让家人把手机对准收银台扫码")
    else:
        print("  ⚠️ 支付宝未正常打开")
        print("  💡 手动: 打开支付宝 → 首页 → 付钱")


def assist_find_photo(phone, keyword=None):
    """帮家人找照片"""
    print("\n  📸 查找照片")
    # 打开相册
    phone.intent("android.intent.action.VIEW",
                 data="content://media/internal/images/media")
    phone.wait(2)
    fg = phone.foreground()
    if "gallery" in fg.lower() or "photo" in fg.lower() or "album" in fg.lower():
        print(f"  ✅ 相册已打开 ({fg.split('.')[-1]})")
    else:
        # 回退: 打开Google Photos或系统相册
        phone.open_app("com.google.android.apps.photos")
        phone.wait(2)
        print(f"  当前: {phone.foreground().split('.')[-1]}")

    if keyword:
        print(f"  → 搜索: {keyword}")
        phone.click("搜索")
        phone.wait(1)
        phone.post("/text", {"text": keyword})
        phone.post("/key", {"keysym": 0xFF0D, "down": True})
        phone.post("/key", {"keysym": 0xFF0D, "down": False})
        phone.wait(2)


def assist_screen_too_small(phone):
    """帮家人调大字体"""
    print("\n  🔤 调大字体/显示")
    phone.intent("android.settings.DISPLAY_SETTINGS")
    phone.wait(2)
    texts, _ = phone.read()
    # 查找字体大小/显示大小
    for kw in ["字体", "显示大小", "放大", "Font"]:
        r = phone.click(kw)
        if r.get("ok"):
            print(f"  → 找到并点击: {kw}")
            phone.wait(1)
            break
    else:
        print("  💡 在显示设置中找 '字体大小' 或 '显示大小'")
        for t in texts[:15]:
            if t.strip():
                print(f"    {t}")


def assist_screenshot_and_share(phone):
    """截屏并通过剪贴板获取屏幕信息"""
    print("\n  📋 采集屏幕信息")
    texts, pkg = phone.read()
    print(f"  前台: {pkg.split('.')[-1]}")
    print(f"  屏幕文本 ({len(texts)}条):")
    for i, t in enumerate(texts[:30]):
        if t.strip():
            print(f"    [{i}] {t}")
    return texts


# ============================================================
# 交互式命令面板
# ============================================================

COMMANDS = {
    "h": ("健康诊断", "完整检查手机状态"),
    "s": ("看屏幕", "读取屏幕全部文本"),
    "5": ("五感采集", "一次获取全部感知数据"),
    "c": ("点击", "语义查找并点击 (输入文字)"),
    "t": ("打字", "在当前输入框输入文字"),
    "b": ("返回", "按返回键"),
    "m": ("回桌面", "回到主屏幕"),
    "w": ("微信", "打开微信检查消息"),
    "p": ("付款码", "打开支付宝付款码"),
    "a": ("装APP", "帮安装应用 (输入名称)"),
    "f": ("找照片", "帮找照片 (可输入关键词)"),
    "n": ("WiFi", "打开WiFi设置页面"),
    "d": ("大字体", "调大字体/显示"),
    "k": ("清理", "检查并清理存储"),
    "i": ("设备信息", "电量/存储/网络"),
    "l": ("通知", "查看最近通知"),
    "x": ("滑动", "上下左右滑动 (u/d/l/r)"),
    "o": ("打开APP", "输入包名打开"),
    "q": ("退出", "结束远程协助"),
}


def interactive_loop(phone, family_name=""):
    """交互式远程协助"""
    title = f" 远程协助: {family_name}" if family_name else " 远程协助"
    print(f"\n{'='*50}")
    print(f"  📱{title}")
    print(f"  连接: {phone.base} ({phone._connection_mode})")
    print(f"{'='*50}")
    print(f"\n  命令列表:")
    for key, (name, desc) in COMMANDS.items():
        print(f"    [{key}] {name:8s} — {desc}")
    print()

    while True:
        try:
            cmd = input("  > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            break

        if not cmd:
            continue

        if cmd == "q":
            print("  👋 远程协助结束")
            break
        elif cmd == "h":
            issues, suggestions, data = diagnose(phone)
            print("\n  📋 诊断结果:")
            for i in issues:
                print(f"    {i}")
            if suggestions:
                print("  💡 建议:")
                for s in suggestions:
                    print(f"    → {s}")
        elif cmd == "s":
            assist_screenshot_and_share(phone)
        elif cmd == "5":
            s = phone.senses()
            print(json.dumps(s, ensure_ascii=False, indent=2))
        elif cmd.startswith("c"):
            text = cmd[1:].strip() or input("  点击什么? > ").strip()
            if text:
                r = phone.click(text)
                print(f"  → {'✅ 已点击' if r.get('ok') else '❌ 未找到'}: {text}")
                phone.wait(0.5)
        elif cmd.startswith("t"):
            text = cmd[1:].strip() or input("  输入什么? > ").strip()
            if text:
                phone.post("/text", {"text": text})
                print(f"  → 已输入: {text}")
        elif cmd == "b":
            phone.back()
            print("  → 已返回")
        elif cmd == "m":
            phone.home()
            print("  → 已回桌面")
        elif cmd == "w":
            assist_check_wechat(phone)
        elif cmd == "p":
            assist_quick_pay(phone)
        elif cmd.startswith("a"):
            name = cmd[1:].strip() or input("  APP名称? > ").strip()
            if name:
                assist_install_app(phone, name)
        elif cmd.startswith("f"):
            kw = cmd[1:].strip() or None
            assist_find_photo(phone, kw)
        elif cmd == "n":
            assist_wifi_setup(phone)
        elif cmd == "d":
            assist_screen_too_small(phone)
        elif cmd == "k":
            assist_clean_storage(phone)
        elif cmd == "i":
            dev = phone.device()
            bat = dev.get("batteryLevel", -1)
            chg = dev.get("isCharging", False)
            sto = round(dev.get("storageAvailableMB", 0) / 1024, 1)
            net = dev.get("networkType", "?")
            mdl = f"{dev.get('manufacturer', '')} {dev.get('model', '')}".strip()
            print(f"  📱 {mdl}")
            print(f"  🔋 电量: {bat}%{'⚡充电中' if chg else ''}")
            print(f"  💾 存储: {sto}GB可用")
            print(f"  📶 网络: {net}")
        elif cmd == "l":
            n = phone.notifications(10)
            items = n.get("notifications", [])
            print(f"  🔔 通知 ({n.get('total', 0)}条):")
            for item in items[:10]:
                app = item.get("package", "").split(".")[-1]
                title = item.get("title", "")
                text = item.get("text", "")[:40]
                print(f"    [{app}] {title}: {text}")
        elif cmd.startswith("x"):
            d = cmd[1:].strip() or input("  方向? (u/d/l/r) > ").strip()
            directions = {"u": "up", "d": "down", "l": "left", "r": "right"}
            if d in directions:
                phone.swipe(directions[d])
                print(f"  → 已滑动: {directions[d]}")
            else:
                print(f"  ❌ 未知方向: {d}")
        elif cmd.startswith("o"):
            pkg = cmd[1:].strip() or input("  包名? > ").strip()
            if pkg:
                phone.open_app(pkg)
                print(f"  → 已打开: {pkg}")
        elif cmd.startswith("tap"):
            # tap 0.5 0.5
            parts = cmd.split()
            if len(parts) == 3:
                phone.tap(float(parts[1]), float(parts[2]))
                print(f"  → 已点击: ({parts[1]}, {parts[2]})")
        else:
            print(f"  ❓ 未知命令: {cmd} (输入q退出)")


# ============================================================
# 扫描局域网
# ============================================================

def scan_network(port_range=(8080, 8082, 8084, 8086, 8088)):
    """扫描局域网中的ScreenStream设备"""
    print("\n  🔍 扫描局域网...")
    subnet = _get_local_subnet()
    if not subnet:
        print("  ❌ 无法获取本机IP")
        return []

    print(f"  网段: {subnet}.x")
    found = []

    def _check(ip, port):
        url = f"http://{ip}:{port}"
        if _probe(url, timeout=1.0):
            found.append((ip, port, url))

    threads = []
    for suffix in range(1, 255):
        ip = f"{subnet}.{suffix}"
        for port in port_range:
            t = threading.Thread(target=_check, args=(ip, port), daemon=True)
            threads.append(t)
            t.start()

    # 等待所有线程（最多10秒）
    deadline = time.time() + 10
    for t in threads:
        remaining = deadline - time.time()
        if remaining > 0:
            t.join(timeout=remaining)

    if found:
        print(f"\n  📱 发现 {len(found)} 台设备:")
        for ip, port, url in found:
            try:
                p = Phone(host=ip, port=port, auto_discover=False, retry=0)
                dev = p.device()
                model = f"{dev.get('manufacturer', '')} {dev.get('model', '')}".strip()
                bat = dev.get("batteryLevel", -1)
                print(f"    {url} — {model} (电量{bat}%)")
            except Exception:
                print(f"    {url}")
    else:
        print("  未发现设备")

    return found


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="远程家庭协助工具")
    parser.add_argument("--name", help="家人名字（从已保存配置连接）")
    parser.add_argument("--host", help="手机IP地址")
    parser.add_argument("--port", type=int, default=8086, help="端口")
    parser.add_argument("--url", help="完整URL")
    parser.add_argument("--scan", action="store_true", help="扫描局域网")
    parser.add_argument("--add", nargs=2, metavar=("NAME", "HOST"), help="添加家人手机")
    parser.add_argument("--list", action="store_true", help="列出已保存的家人手机")
    parser.add_argument("--diagnose", action="store_true", help="仅诊断不进入交互")
    parser.add_argument("--heartbeat", type=int, default=0, help="心跳间隔(秒)")
    args = parser.parse_args()

    # 管理命令
    if args.add:
        add_family(args.add[0], args.add[1], args.port)
        return

    if args.list:
        family = load_family()
        if not family:
            print("  暂无保存的家人手机。使用 --add 名字 IP 添加")
            return
        print("\n  📱 已保存的家人手机:")
        for name, cfg in family.items():
            last = cfg.get("last_connect", "从未")
            print(f"    {name}: {cfg['host']}:{cfg['port']}  (上次: {last})")
        return

    if args.scan:
        found = scan_network()
        if found and not args.host:
            # 用第一个发现的
            ip, port, _ = found[0]
            args.host = ip
            args.port = port
        elif not found:
            return

    # 连接
    phone = None
    family_name = ""

    if args.name:
        phone = get_family_phone(args.name)
        family_name = args.name
        if not phone:
            return
    elif args.url:
        phone = Phone(url=args.url, heartbeat_sec=args.heartbeat)
    elif args.host:
        phone = Phone(host=args.host, port=args.port, heartbeat_sec=args.heartbeat)
    else:
        phone = Phone(heartbeat_sec=args.heartbeat)

    # 确保连接
    alive, recovery_log = phone.ensure_alive()
    if recovery_log:
        for line in recovery_log:
            log.info(line)
    if not alive:
        print("\n  ❌ 无法连接到手机")
        print("  💡 检查:")
        print("  1. 家人手机WiFi是否正常")
        print("  2. ScreenStream是否在运行")
        print("  3. 是否在同一网络 / Tailscale是否连接")
        return

    # 诊断模式
    if args.diagnose:
        issues, suggestions, data = diagnose(phone)
        print("\n  📋 诊断报告:")
        for i in issues:
            print(f"    {i}")
        if suggestions:
            print("  💡 建议:")
            for s in suggestions:
                print(f"    → {s}")
        return

    # 交互模式
    interactive_loop(phone, family_name)


if __name__ == "__main__":
    main()
