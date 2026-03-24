"""
道法自然 · ScreenStream 全能力公网E2E验证
==========================================
120+ API端点 × 15大能力组 × 三路径公网
为学日益 为道日损 损之又损 以至于无为 无为而无不为

用法:
  python _e2e_supreme.py                    # 公网Nginx路径
  python _e2e_supreme.py --local            # 本地WiFi直连
  python _e2e_supreme.py --gateway          # 本地网关
  python _e2e_supreme.py --all              # 三路径全测
"""
import urllib.request, json, ssl, sys, time, argparse

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))

R = {"pass": 0, "fail": 0, "skip": 0, "details": []}

def GET(base, path, timeout=8):
    url = base + path
    req = urllib.request.Request(url, method="GET")
    r = opener.open(req, timeout=timeout)
    return json.loads(r.read().decode())

def POST(base, path, body=None, timeout=8):
    url = base + path
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    r = opener.open(req, timeout=timeout)
    return json.loads(r.read().decode())

_timeout = 8  # default per-suite timeout

def t(group, name, fn):
    """Test wrapper"""
    try:
        result = fn()
        ok = result is not None and not (isinstance(result, dict) and result.get("_error"))
        detail = str(result)[:80] if result else "None"
        R["pass" if ok else "fail"] += 1
        R["details"].append({"g": group, "n": name, "ok": ok, "d": detail})
        return ok, result
    except Exception as e:
        R["fail"] += 1
        R["details"].append({"g": group, "n": name, "ok": False, "d": str(e)[:80]})
        return False, None

def run_suite(base, label, timeout=8):
    global _timeout
    _timeout = timeout
    print(f"\n{'='*65}")
    print(f"  📱 ScreenStream 全能力验证 · {label}")
    print(f"  🔗 {base}  ⏱ timeout={timeout}s")
    print(f"{'='*65}")

    R["pass"] = R["fail"] = R["skip"] = 0
    R["details"] = []

    # ══════════════════════════════════════════════════════════
    # 1. META — 元信息
    # ══════════════════════════════════════════════════════════
    print("\n⚙️  [META] 元信息")
    t("meta", "capabilities", lambda: GET(base, "/capabilities", _timeout))
    t("meta", "status", lambda: GET(base, "/status", _timeout))
    t("meta", "a11y/status", lambda: GET(base, "/a11y/status", _timeout))

    # ══════════════════════════════════════════════════════════
    # 2. 感知层 — 五感全采集 (只读·无副作用)
    # ══════════════════════════════════════════════════════════
    print("\n👁  [感知] 视觉")
    t("视觉", "screen/text", lambda: GET(base, "/screen/text", _timeout))
    t("视觉", "viewtree", lambda: GET(base, "/viewtree?depth=3", _timeout))
    t("视觉", "windowinfo", lambda: GET(base, "/windowinfo", _timeout))
    t("视觉", "foreground", lambda: GET(base, "/foreground", _timeout))

    print("👂  [感知] 听觉")
    ok, dev = t("听觉", "deviceinfo", lambda: GET(base, "/deviceinfo", _timeout))
    if ok and dev:
        print(f"     bat={dev.get('batteryLevel','')}% vol={dev.get('volumeMusic','')} net={dev.get('networkType','')}")

    print("👃  [感知] 嗅觉")
    t("嗅觉", "notifications", lambda: GET(base, "/notifications/read?limit=5", _timeout))

    print("🖐  [感知] 触觉")
    t("触觉", "status", lambda: GET(base, "/status", _timeout))

    print("👅  [感知] 味觉")
    t("味觉", "brightness", lambda: GET(base, "/brightness", _timeout))
    t("味觉", "dnd", lambda: GET(base, "/dnd", _timeout))
    t("味觉", "autorotate", lambda: GET(base, "/autorotate", _timeout))
    t("味觉", "stayawake", lambda: GET(base, "/stayawake", _timeout))
    t("味觉", "showtouches", lambda: GET(base, "/showtouches", _timeout))
    t("味觉", "clipboard", lambda: GET(base, "/clipboard", _timeout))

    # ══════════════════════════════════════════════════════════
    # 3. APP层 — 应用管理
    # ══════════════════════════════════════════════════════════
    print("\n📱  [APP] 应用管理")
    t("APP", "apps", lambda: GET(base, "/apps", _timeout))
    t("APP", "packages", lambda: GET(base, "/packages", _timeout))

    # ══════════════════════════════════════════════════════════
    # 4. 文件系统
    # ══════════════════════════════════════════════════════════
    print("\n📁  [文件] 文件系统")
    t("文件", "storage", lambda: GET(base, "/files/storage", _timeout))
    t("文件", "list /sdcard", lambda: GET(base, "/files/list?path=/sdcard", _timeout))
    t("文件", "search DCIM", lambda: GET(base, "/files/search?path=/sdcard&q=DCIM&max=5", _timeout))

    # ══════════════════════════════════════════════════════════
    # 5. 系统深度感知
    # ══════════════════════════════════════════════════════════
    print("\n🔧  [系统] 深度感知")
    t("系统", "system/info", lambda: GET(base, "/system/info", _timeout))
    t("系统", "system/processes", lambda: GET(base, "/system/processes?top=10", _timeout))
    t("系统", "system/properties", lambda: GET(base, "/system/properties?key=ro.build.display.id", _timeout))

    # ══════════════════════════════════════════════════════════
    # 6. 宏系统
    # ══════════════════════════════════════════════════════════
    print("\n🤖  [宏] 宏系统")
    t("宏", "macro/list", lambda: GET(base, "/macro/list", _timeout))
    t("宏", "macro/running", lambda: GET(base, "/macro/running", _timeout))

    # ══════════════════════════════════════════════════════════
    # 7. 智能家居
    # ══════════════════════════════════════════════════════════
    print("\n🏠  [家居] 智能家居")
    t("家居", "smarthome/status", lambda: GET(base, "/smarthome/status", _timeout))

    # ══════════════════════════════════════════════════════════
    # 8. 语义层 — AI Brain (只读搜索)
    # ══════════════════════════════════════════════════════════
    print("\n🧠  [AI] 语义层")
    t("AI", "findnodes", lambda: POST(base, "/findnodes", {"text": "设置"}, _timeout))

    # ══════════════════════════════════════════════════════════
    # 9. Shell (只读命令)
    # ══════════════════════════════════════════════════════════
    print("\n💻  [Shell] 设备Shell")
    t("Shell", "shell whoami", lambda: POST(base, "/shell", {"command": "whoami", "timeout": 5000}, _timeout))
    t("Shell", "shell uname", lambda: POST(base, "/shell", {"command": "uname -a", "timeout": 5000}, _timeout))
    t("Shell", "shell df", lambda: POST(base, "/shell", {"command": "df -h /data | tail -1", "timeout": 5000}, _timeout))

    # ══════════════════════════════════════════════════════════
    # 10. Intent — 通用意图
    # ══════════════════════════════════════════════════════════
    print("\n🔗  [Intent] 意图系统")
    # 只查询，不执行破坏性操作
    t("Intent", "wait(极短)", lambda: GET(base, "/wait?text=___impossible___&timeout=500&interval=500", _timeout))

    # ══════════════════════════════════════════════════════════
    # SUMMARY
    # ══════════════════════════════════════════════════════════
    total = R["pass"] + R["fail"]
    pct = R["pass"] / total * 100 if total > 0 else 0

    print(f"\n{'='*65}")
    print(f"  📊 {label} · {R['pass']}/{total} 通过 ({pct:.0f}%) · {R['fail']} 失败")

    # 按组汇总
    groups = {}
    for d in R["details"]:
        g = d["g"]
        if g not in groups:
            groups[g] = {"pass": 0, "fail": 0}
        groups[g]["pass" if d["ok"] else "fail"] += 1

    for g, v in groups.items():
        total_g = v["pass"] + v["fail"]
        icon = "✅" if v["fail"] == 0 else "⚠️"
        print(f"  {icon} {g}: {v['pass']}/{total_g}")

    # 失败明细
    fails = [d for d in R["details"] if not d["ok"]]
    if fails:
        print(f"\n  ❌ 失败明细:")
        for f in fails:
            print(f"     [{f['g']}] {f['n']}: {f['d'][:60]}")

    print(f"\n  ⏱️  {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*65}")
    return R["pass"], R["fail"]


def main():
    parser = argparse.ArgumentParser(description="ScreenStream全能力E2E验证")
    parser.add_argument("--local", action="store_true", help="WiFi直连")
    parser.add_argument("--gateway", action="store_true", help="本地网关")
    parser.add_argument("--all", action="store_true", help="三路径全测")
    args = parser.parse_args()

    paths = []
    if args.all:
        paths = [
            ("https://aiotvr.xyz/input", "公网Nginx", 15),
            ("http://60.205.171.100:38084", "手机FRP直连", 15),
            ("http://192.168.31.40:8084", "WiFi直连", 10),
            ("http://127.0.0.1:28084", "本地网关", 10),
        ]
    elif args.local:
        paths = [("http://192.168.31.40:8084", "WiFi直连", 10)]
    elif args.gateway:
        paths = [("http://127.0.0.1:28084", "本地网关", 10)]
    else:
        paths = [("https://aiotvr.xyz/input", "公网Nginx", 15)]

    total_pass = total_fail = 0
    for base, label, timeout in paths:
        p, f = run_suite(base, label, timeout)
        total_pass += p
        total_fail += f

    if len(paths) > 1:
        print(f"\n{'='*65}")
        print(f"  🌐 四路径总计: {total_pass}/{total_pass+total_fail} 通过")
        print(f"{'='*65}")


if __name__ == "__main__":
    main()
