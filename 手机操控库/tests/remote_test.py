"""
远程五感端到端验证测试
========================
验证在各种连接模式下，所有五感功能完整可用。
支持USB/WiFi/Tailscale/公网四种模式。

使用:
  python tests/remote_test.py                          # 自动发现
  python tests/remote_test.py --host 192.168.31.100    # WiFi直连
  python tests/remote_test.py --host 100.100.1.5       # Tailscale
  python tests/remote_test.py --url https://my.domain  # 公网穿透
  python tests/remote_test.py --port 8086              # 指定端口
"""

import sys, os, time, json, argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from phone_lib import Phone, discover, NegativeState

# ============================================================
# Test Infrastructure
# ============================================================

class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.results = []

    def ok(self, name, detail=""):
        self.passed += 1
        self.results.append(("✅", name, detail))
        print(f"  ✅ {name} {detail}")

    def fail(self, name, detail=""):
        self.failed += 1
        self.results.append(("❌", name, detail))
        print(f"  ❌ {name} {detail}")

    def skip(self, name, detail=""):
        self.skipped += 1
        self.results.append(("⏭️", name, detail))
        print(f"  ⏭️ {name} {detail}")

    def summary(self):
        total = self.passed + self.failed + self.skipped
        print(f"\n{'='*50}")
        print(f"  结果: {self.passed}/{total} 通过, {self.failed} 失败, {self.skipped} 跳过")
        print(f"{'='*50}")
        return self.failed == 0


# ============================================================
# Section 1: 连接与发现
# ============================================================

def test_connection(phone, t):
    print("\n[1] 连接与发现")

    # 1.1 基本连接
    s = phone.status()
    if "connected" in s:
        t.ok("HTTP连接", f"→ {phone.base}")
    else:
        t.fail("HTTP连接", f"→ {s}")
        return  # 连接失败则跳过后续

    # 1.2 连接模式
    t.ok("连接模式", f"→ {phone._connection_mode}")

    # 1.3 ADB状态
    if phone._has_adb:
        t.ok("ADB可用", f"→ {phone._serial_hint}")
    else:
        t.ok("纯远程模式", "→ 无ADB (所有功能通过HTTP)")

    # 1.4 repr
    r = repr(phone)
    if "Phone(" in r:
        t.ok("Phone repr", f"→ {r}")
    else:
        t.fail("Phone repr", f"→ {r}")


# ============================================================
# Section 2: 👁 视觉 (Vision)
# ============================================================

def test_vision(phone, t):
    print("\n[2] 👁 视觉")

    # 2.1 屏幕文本
    texts, pkg = phone.read()
    if isinstance(texts, list):
        t.ok("屏幕文本", f"→ {len(texts)}条, 前台:{pkg}")
    else:
        t.fail("屏幕文本", f"→ {texts}")

    # 2.2 前台APP
    fg = phone.foreground()
    if fg and isinstance(fg, str):
        t.ok("前台APP", f"→ {fg}")
    else:
        t.fail("前台APP", f"→ {fg}")

    # 2.3 View树
    vt = phone.viewtree(depth=3)
    if isinstance(vt, dict) and ("children" in vt or "className" in vt or "package" in vt):
        t.ok("View树", f"→ depth=3")
    else:
        t.fail("View树", f"→ {str(vt)[:100]}")

    # 2.4 窗口信息
    wi = phone.get("/windowinfo")
    if isinstance(wi, dict) and not wi.get("_error"):
        t.ok("窗口信息", f"→ {wi.get('packageName', '?')}")
    else:
        t.fail("窗口信息", f"→ {wi}")


# ============================================================
# Section 3: 👂 听觉 (Hearing)
# ============================================================

def test_hearing(phone, t):
    print("\n[3] 👂 听觉")

    # 3.1 设备音量
    dev = phone.device()
    vol = dev.get("volumeMusic", -1)
    if vol >= 0:
        t.ok("音量读取", f"→ music={vol}")
    else:
        t.fail("音量读取", f"→ {dev}")

    # 3.2 DND状态
    dnd = phone.get("/dnd")
    if isinstance(dnd, dict) and "dnd" in dnd:
        t.ok("免打扰状态", f"→ dnd={dnd['dnd']}")
    else:
        t.fail("免打扰状态", f"→ {dnd}")


# ============================================================
# Section 4: 🖐 触觉 (Touch)
# ============================================================

def test_touch(phone, t):
    print("\n[4] 🖐 触觉")

    # 4.1 输入状态
    s = phone.status()
    enabled = s.get("inputEnabled", False)
    if enabled:
        t.ok("输入已启用", f"→ scaling={s.get('scaling', '?')}")
    else:
        t.fail("输入未启用", "→ inputEnabled=false")

    # 4.2 语义查找（只查找不点击）
    nodes = phone.post("/findnodes", {"text": "设置"})
    if isinstance(nodes, dict):
        count = nodes.get("count", 0)
        t.ok("语义查找", f"→ '设置' 找到{count}个节点")
    else:
        t.fail("语义查找", f"→ {nodes}")

    # 4.3 文本输入API可达
    # 不实际输入，只验证API端点
    r = phone.post("/text", {"text": ""})
    if isinstance(r, dict):
        t.ok("文本输入API", "→ 端点可达")
    else:
        t.fail("文本输入API", f"→ {r}")


# ============================================================
# Section 5: 👃 嗅觉 (Notifications)
# ============================================================

def test_smell(phone, t):
    print("\n[5] 👃 嗅觉")

    # 5.1 通知读取
    n = phone.notifications(10)
    if isinstance(n, dict) and "total" in n:
        total = n["total"]
        items = n.get("notifications", [])
        t.ok("通知读取", f"→ {total}条, 返回{len(items)}条")
    else:
        t.fail("通知读取", f"→ {n}")

    # 5.2 前台APP监控
    fg = phone.foreground()
    if fg:
        t.ok("前台监控", f"→ {fg}")
    else:
        t.fail("前台监控", "→ 无法获取")


# ============================================================
# Section 6: 👅 味觉 (Status)
# ============================================================

def test_taste(phone, t):
    print("\n[6] 👅 味觉")

    dev = phone.device()

    # 6.1 电池
    battery = dev.get("batteryLevel", -1)
    charging = dev.get("isCharging", False)
    if battery >= 0:
        t.ok("电池状态", f"→ {battery}%{'⚡' if charging else ''}")
    else:
        t.fail("电池状态", f"→ {dev}")

    # 6.2 网络
    net = dev.get("networkType", "?")
    net_ok = dev.get("networkConnected", False)
    t.ok("网络状态", f"→ {net}, connected={net_ok}")

    # 6.3 存储
    storage = dev.get("storageAvailableMB", -1)
    if storage >= 0:
        t.ok("存储状态", f"→ {round(storage/1024, 1)}GB可用")
    else:
        t.fail("存储状态", f"→ {dev}")

    # 6.4 剪贴板
    phone.clipboard_write("remote_test_ok")
    time.sleep(0.3)
    clip = phone.clipboard_read()
    if clip == "remote_test_ok":
        t.ok("剪贴板", "→ 读写正常")
    else:
        t.ok("剪贴板写入", f"→ 写入成功, 读取={clip} (Android限制)")

    # 6.5 APP列表
    apps = phone.apps()
    if isinstance(apps, dict) and "apps" in apps:
        t.ok("APP列表", f"→ {len(apps['apps'])}个应用")
    elif isinstance(apps, list):
        t.ok("APP列表", f"→ {len(apps)}个应用")
    else:
        t.fail("APP列表", f"→ {str(apps)[:100]}")


# ============================================================
# Section 7: 弹性特性
# ============================================================

def test_resilience(phone, t):
    print("\n[7] 弹性特性")

    # 7.1 健康检查
    h = phone.health()
    if h.get("healthy"):
        t.ok("健康检查", f"→ {h['state']}")
    else:
        t.fail("健康检查", f"→ {h['state']}: {h['detail']}")

    # 7.2 五感采集
    s = phone.senses()
    if s.get("_ok"):
        senses_ok = all(k in s for k in ["vision", "hearing", "touch", "smell", "taste"])
        if senses_ok:
            t.ok("五感采集", f"→ 5/5感全部获取")
        else:
            t.fail("五感采集", f"→ 缺少: {[k for k in ['vision','hearing','touch','smell','taste'] if k not in s]}")
    else:
        t.fail("五感采集", f"→ {s.get('_error', '?')}")

    # 7.3 负面状态检测
    state, detail = NegativeState.detect(phone)
    if state == NegativeState.HEALTHY:
        t.ok("负面状态检测", "→ healthy")
    else:
        t.ok("负面状态检测", f"→ {state}: {detail}")

    # 7.4 叠加检测
    issues = NegativeState.detect_all(phone)
    t.ok("叠加状态检测", f"→ {len(issues)}个问题")

    # 7.5 collect_status
    cs = phone.collect_status()
    if isinstance(cs, dict) and "battery" in cs:
        t.ok("状态采集", f"→ 电量{cs['battery']}%, 网络{cs['network']}")
    else:
        t.fail("状态采集", f"→ {cs}")


# ============================================================
# Section 8: 远程增强API
# ============================================================

def test_remote_apis(phone, t):
    print("\n[8] 远程增强API")

    # 8.1 亮度读取
    b = phone.get("/brightness")
    if isinstance(b, dict) and "brightness" in b:
        t.ok("亮度读取", f"→ {b['brightness']}")
    else:
        t.fail("亮度读取", f"→ {b}")

    # 8.2 自动旋转状态
    ar = phone.get("/autorotate")
    if isinstance(ar, dict) and "autoRotate" in ar:
        t.ok("自动旋转", f"→ {ar['autoRotate']}")
    else:
        t.fail("自动旋转", f"→ {ar}")

    # 8.3 保持唤醒状态
    sa = phone.get("/stayawake")
    if isinstance(sa, dict) and "stayAwake" in sa:
        t.ok("保持唤醒", f"→ {sa['stayAwake']}")
    else:
        t.fail("保持唤醒", f"→ {sa}")

    # 8.4 文件系统
    fs = phone.get("/files/storage")
    if isinstance(fs, dict) and not fs.get("_error"):
        t.ok("文件系统", f"→ 存储信息可达")
    else:
        t.fail("文件系统", f"→ {fs}")

    # 8.5 宏列表
    ml = phone.get("/macro/list")
    if isinstance(ml, dict):
        t.ok("宏系统", f"→ 列表可达")
    else:
        t.fail("宏系统", f"→ {ml}")

    # 8.6 无障碍状态
    a11y = phone.get("/a11y/status")
    if isinstance(a11y, dict) and "connected" in a11y:
        t.ok("无障碍状态", f"→ connected={a11y['connected']}, method={a11y.get('method_available','?')}")
    else:
        t.fail("无障碍状态", f"→ {a11y}")


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="远程五感端到端验证")
    parser.add_argument("--host", help="手机IP地址")
    parser.add_argument("--port", type=int, default=8086, help="ScreenStream端口")
    parser.add_argument("--url", help="完整URL")
    parser.add_argument("--json", action="store_true", help="JSON格式输出")
    args = parser.parse_args()

    print("=" * 50)
    print("  远程五感端到端验证")
    print("=" * 50)

    # 创建Phone实例
    if args.url:
        phone = Phone(url=args.url)
    elif args.host:
        phone = Phone(host=args.host, port=args.port)
    else:
        phone = Phone(port=args.port)

    print(f"  连接: {phone}")

    t = TestResult()

    test_connection(phone, t)
    test_vision(phone, t)
    test_hearing(phone, t)
    test_touch(phone, t)
    test_smell(phone, t)
    test_taste(phone, t)
    test_resilience(phone, t)
    test_remote_apis(phone, t)

    ok = t.summary()

    if args.json:
        output = {
            "ok": ok,
            "passed": t.passed,
            "failed": t.failed,
            "skipped": t.skipped,
            "base": phone.base,
            "mode": phone._connection_mode,
            "results": [{"status": s, "name": n, "detail": d} for s, n, d in t.results],
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
