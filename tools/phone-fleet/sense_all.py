"""多Agent五感中枢 v3 — 五域感知统一入口
=======================================
台式机本地运行，并行感知五个域：
  📱 手机域   — OPPO PEAM00 (phone_lib.py HTTP API :8084)
  🖥  台式机域 — Administrator session (remote_agent :9904)
  💻 笔记本域 — 192.168.31.179 (remote_agent :9903)
  📂 本地域   — E:\\道\\AI之手机\\ 部署状态
  🔩 硬件域   — 本机底层五感 (pc_senses.py CPU/RAM/磁盘/温度/进程)

用法:
  python sense_all.py             # 四域五感全报告
  python sense_all.py --json      # JSON输出(供Agent读取)
  python sense_all.py --phone     # 仅手机域
  python sense_all.py --pc        # 仅台式机域(:9904)
  python sense_all.py --laptop    # 仅笔记本域(:9903)
  python sense_all.py --local     # 仅本地部署状态
  python sense_all.py --research  # AI研究库框架可用性
  python sense_all.py --heal      # 检测+修复所有负面状态
  python sense_all.py --agents    # 扫描所有Agent端口在线状态
  python sense_all.py --hw        # 🔩 硬件底层五感深度报告（CPU/进程/卡顿/事件日志）
  python sense_all.py --hw --watch [秒]  # 持续硬件监控
  python sense_all.py --ws        # 📂 工作区五感（E:\\道目录/日志/关键文件）
  python sense_all.py --all       # 🌐 四维统一报告（用户+多Agent+工作区+电脑）
  python sense_all.py --ai        # 🖥  ai子账号五感（:9905软件资产/进程/截图）
  python sense_all.py --ai --scan # ai子账号全量扫描已安装软件

  python sense_all.py --act phone click 目标文字    # 手机:点击文字
  python sense_all.py --act phone shell "am start" # 手机:ADB命令
  python sense_all.py --act phone command "打开微信" # 手机:AI自然语言
  python sense_all.py --act pc shell "dir E:\\"     # 台式机:Shell命令
  python sense_all.py --act laptop key win          # 笔记本:按键

  python sense_all.py --verify phone 预期文字 5     # 验证手机屏幕(5s超时)
  python sense_all.py --verify pc 预期窗口标题       # 验证PC窗口

  python sense_all.py --monitor 30             # 六感守护(每30s,默认)
  python sense_all.py --loop phone "打开设置"  # 感→行→验 完整闭环
"""
import sys, os, json, argparse, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.request import urlopen, Request
from urllib.error import URLError

# ── 引入底层SDK ──────────────────────────────────────────────
_LIB_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_lib"))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)
try:
    from pc_senses import PC_Senses as _PC_Senses
    _HW_OK = True
except ImportError:
    _HW_OK = False
try:
    from workspace_senses import sense_all_workspace as _ws_sense, print_workspace_report as _ws_print
    _WS_OK = True
except ImportError:
    _WS_OK = False

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── 手机域依赖 ──────────────────────────────────────────
try:
    from phone_lib import Phone
    _PHONE_OK = True
except ImportError:
    _PHONE_OK = False

_PC_BASE     = "http://localhost:9904"
_LAPTOP_BASE = "http://192.168.31.179:9903"

def _domain_base(domain):
    return _PC_BASE if domain in ("desktop", "pc") else _LAPTOP_BASE

# ── HTTP 工具（纯urllib，零外部依赖）────────────────
def _get(base, path, timeout=8):
    try:
        with urlopen(Request(f"{base}{path}"), timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"_error": str(e)}

def _post(base, path, body=None, timeout=10):
    try:
        data = json.dumps(body or {}).encode()
        req = Request(f"{base}{path}", data=data,
                      headers={"Content-Type": "application/json"})
        with urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"_error": str(e)}


# ══════════════════════════════════════════════════════
#  感 — 五感采集（三域并行）
# ══════════════════════════════════════════════════════

def _sense_phone_ocr():
    """ADB+OCR 降级感知 — ScreenStream 不可用时自动启用"""
    r = {"_domain": "phone", "_ok": False, "_fallback": "adb_ocr"}
    try:
        import sys as _sys, io
        _ai_mobile = os.path.join(_LOCAL_DIR, "ai_mobile")
        if _ai_mobile not in _sys.path:
            _sys.path.insert(0, _ai_mobile)
        from adb_executor import ADBExecutor
        from ocr_shared import run_rapidocr
        from rapidocr_onnxruntime import RapidOCR
        from PIL import Image
        import numpy as np

        adb = ADBExecutor(
            adb_path=r"D:\scrcpy\scrcpy-win64-v3.1\adb.exe",
            device_id="KBVSEI4XZDQOKFFE",
        )
        if not adb.is_device_connected():
            r["_error"] = "ADB设备未连接"
            return r

        ok, data = adb.run_raw(["exec-out", "screencap", "-p"])
        if not ok or len(data) < 1000:
            r["_error"] = "ADB截图失败"
            return r

        img = Image.open(io.BytesIO(data)).convert("RGB")
        arr = np.array(img)
        results = run_rapidocr(RapidOCR(), arr, max_width=720)
        texts = [res[1] for res in results if res[2] > 0.5]

        _, bat_out = adb.shell("dumpsys battery | grep level")
        battery = 0
        for line in bat_out.splitlines():
            if "level" in line:
                try: battery = int(line.split(":")[-1].strip())
                except Exception: pass

        _, chg_out = adb.shell("dumpsys battery | grep powered")
        charging = "true" in chg_out.lower()

        _, fg_out = adb.shell("dumpsys activity activities | grep mResumedActivity")
        fg_app = fg_out.split("/")[0].split(" ")[-1] if fg_out.strip() else "?"

        r.update({
            "_ok": True, "_base": "adb://KBVSEI4XZDQOKFFE", "_mode": "adb_ocr",
            "vision":  {"foreground_app": fg_app, "screen_texts": texts[:20],
                        "text_count": len(texts), "clickable_count": 0},
            "hearing": {},
            "touch":   {"input_enabled": True, "screen_off": False},
            "smell":   {"notification_count": 0, "recent": []},
            "taste":   {"battery": battery, "charging": charging,
                        "network": "?", "storage_free_gb": "?", "model": "OPPO PEAM00"},
        })
    except Exception as e:
        r["_error"] = str(e)[:100]
    return r


def sense_phone():
    if not _PHONE_OK:
        return _sense_phone_ocr()
    try:
        p = Phone(auto_discover=True)
        s = p.senses()
        s["_domain"] = "phone"
        s["_base"]   = p.base
        s["_mode"]   = p._connection_mode
        return s
    except Exception:
        return _sense_phone_ocr()  # ScreenStream掉线 → ADB+OCR降级


def sense_pc(base, domain):
    r = {"_domain": domain, "_base": base, "_ok": False}
    h  = _get(base, "/health", 6)
    si = _get(base, "/sysinfo", 6)
    wi = _get(base, "/windows", 6)
    sc = _get(base, "/screen/info", 6)
    if "_error" in h:
        r["_error"] = h["_error"]
        return r
    r["_ok"] = True
    r["health"]    = {"hostname": h.get("hostname"), "user": h.get("user"),
                      "session": h.get("session_name"),
                      "guard": h.get("guard", {}).get("enabled", False)}
    r["vision"]    = {"screen": f"{si.get('screen_w','?')}x{si.get('screen_h','?')}",
                      "is_locked": si.get("is_locked", False),
                      "active_window": sc.get("active_window","?") if "_error" not in sc else "?",
                      "windows": [w.get("title","")[:45] for w in (wi if isinstance(wi,list) else [])[:5]]}
    r["cognition"] = {"os": si.get("os","?"), "user": si.get("user","?"),
                      "hostname": si.get("hostname","?"),
                      "uptime_sec": si.get("uptime_sec", 0)}
    r["resources"] = {"ram_pct": si.get("ram_percent","?"),
                      "disk_free": si.get("disk_free_gb","?")}
    return r


def _run_parallel(tasks):
    results = {}
    with ThreadPoolExecutor(max_workers=max(1, len(tasks))) as ex:
        futs = {ex.submit(fn): name for name, fn in tasks.items()}
        for fut in as_completed(futs):
            name = futs[fut]
            try:
                results[name] = fut.result()
            except Exception as e:
                results[name] = {"_domain": name, "_ok": False, "_error": str(e)}
    return results


# ══════════════════════════════════════════════════════
#  知 — 分析状态，输出建议
# ══════════════════════════════════════════════════════

def analyze(results):
    """知——分析三域状态，返回告警列表+建议"""
    alerts = []
    advice = []
    ph = results.get("phone", {})
    if ph:
        if not ph.get("_ok"):
            alerts.append(("⚠️", "手机离线", ph.get("_error","")))
            advice.append("--heal  # 手机修复")
        else:
            if not ph.get("touch", {}).get("input_enabled"):
                alerts.append(("⚠️", "手机无障碍断开", "装置失联"))
                advice.append("--heal  # 重启无障碍")
            bat = ph.get("taste", {}).get("battery", 100)
            if isinstance(bat, (int, float)) and bat < 15:
                alerts.append(("🔋", f"手机电量低 {bat}%", "建议充电"))
    for key in ("desktop", "laptop"):
        s = results.get(key)
        if s and not s.get("_ok"):
            label = "台式机" if key == "desktop" else "笔记本"
            alerts.append(("⚠️", f"{label}Agent离线", s.get("_error","")))
            port = "9904" if key == "desktop" else "9903"
            advice.append(f"--heal  # 检查 {label}:{port}")
    return alerts, advice


# ══════════════════════════════════════════════════════
#  行 — 在指定域执行动作
# ══════════════════════════════════════════════════════

def act(domain, action, target=""):
    """行——在指定域执行动作
    domain : phone | desktop | laptop
    action : click | tap | shell | wake | home | back | key | text | command | screenshot
    target : 动作参数
    """
    result = {"domain": domain, "action": action, "target": target, "ok": False}
    if domain == "phone":
        if not _PHONE_OK:
            result["msg"] = "phone_lib未找到"
            return result
        try:
            p = Phone(auto_discover=True)
            if   action == "click":   r = p.click(target)
            elif action == "command": r = p.command(target)
            elif action == "home":    p.home(); r = {"ok": True}
            elif action == "back":    p.back(); r = {"ok": True}
            elif action == "wake":    r = p.wake()
            elif action == "text":    r = p.post("/text", {"text": target})
            elif action == "tap":
                xy = target.replace(" ", ",").split(",")
                r = p.tap(float(xy[0]), float(xy[1]))
            elif action == "shell":
                import subprocess
                out = subprocess.run(
                    ["adb", "-s", p._serial, "shell"] + target.split(),
                    capture_output=True, text=True, timeout=10)
                r = {"stdout": out.stdout.strip(), "ok": out.returncode == 0}
            else:
                r = p.post(f"/{action}", {"text": target} if target else {})
            result.update({"ok": True, "response": r})
        except Exception as e:
            result["msg"] = str(e)
    else:
        base = _domain_base(domain)
        if   action == "shell":      r = _post(base, "/shell",  {"cmd": target})
        elif action == "click":      r = _post(base, "/findclick", {"text": target})
        elif action == "key":        r = _post(base, "/key",   {"key": target})
        elif action == "text":       r = _post(base, "/type",  {"text": target})
        elif action == "screenshot": r = _get (base, "/screenshot")
        elif action == "power":      r = _post(base, "/power", {"action": target})
        else:                        r = _post(base, f"/{action}", {"text": target} if target else {})
        result["ok"]       = "_error" not in r
        result["response"] = r
    return result


# ══════════════════════════════════════════════════════
#  验 — 验证预期状态
# ══════════════════════════════════════════════════════

def verify(domain, expected, timeout=5, interval=1):
    """验——轮询干等预期文字出现在指定域屏幕
    返回: (bool, message)
    """
    deadline = time.time() + timeout
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        found = False
        if domain == "phone":
            if not _PHONE_OK:
                return False, "phone_lib未找到"
            try:
                p = Phone(auto_discover=True)
                texts, _ = p.read()
                if expected in " ".join(texts):
                    found = True
            except Exception as e:
                return False, str(e)
        else:
            base = _domain_base(domain)
            wi = _get(base, "/windows", 4)
            if isinstance(wi, list):
                if any(expected.lower() in w.get("title","").lower() for w in wi):
                    found = True
            sc = _get(base, "/screen/info", 4)
            if "_error" not in sc and expected.lower() in str(sc).lower():
                found = True
        if found:
            return True, f"✅ [{attempt}轮] 找到「{expected}」"
        time.sleep(interval)
    return False, f"❌ 超时{timeout}s未找到「{expected}」"


# ══════════════════════════════════════════════════════
#  守 — 六感守护（无感背景循环）
# ══════════════════════════════════════════════════════

def monitor_loop(interval=30):
    """守——六感守护：持续并行感知，自动告警+修复"""
    prev_ok  = {}
    round_n  = 0
    print(f"🔮 六感守护已启动 (间隔{interval}s) —— Ctrl+C 停止", flush=True)
    try:
        while True:
            round_n += 1
            t0 = time.time()
            tasks = {
                "phone":   sense_phone,
                "desktop": lambda: sense_pc(_PC_BASE,     "desktop"),
                "laptop":  lambda: sense_pc(_LAPTOP_BASE, "laptop"),
            }
            res     = _run_parallel(tasks)
            alerts, _ = analyze(res)
            elapsed = time.time() - t0
            online  = sum(1 for s in res.values() if s.get("_ok"))
            total   = len(res)
            icon    = "🟢" if online == total else ("🟡" if online > 0 else "🔴")
            ts = time.strftime("%H:%M:%S")
            print(f"[{ts}] 第{round_n}轮 {icon} {online}/{total}域在线  {elapsed:.1f}s", flush=True)
            for lvl, title, detail in alerts:
                print(f"  {lvl} {title}: {detail}", flush=True)
                # 手机无障碍自动修复
                if "无障碍" in title and _PHONE_OK:
                    try:
                        p = Phone(auto_discover=True)
                        ok, log = p.ensure_alive()
                        print(f"  � 自动修复: {'✅' if ok else '❌'}", flush=True)
                    except Exception:
                        pass
            # 状态变化检测
            for name, s in res.items():
                now_ok = s.get("_ok", False)
                was_ok = prev_ok.get(name)
                if was_ok is not None and was_ok and not now_ok:
                    print(f"  🔴 {name} 刺刺断线!", flush=True)
                elif was_ok is not None and not was_ok and now_ok:
                    print(f"  🟢 {name} 已恢复在线!", flush=True)
                prev_ok[name] = now_ok
            time.sleep(max(1, interval - elapsed))
    except KeyboardInterrupt:
        print(f"\n六感守护已停止 (共{round_n}轮)", flush=True)


# ══════════════════════════════════════════════════════
#  修复
# ══════════════════════════════════════════════════════

def heal_all():
    print("🩺 三域健康检查+修复...", flush=True)
    if _PHONE_OK:
        try:
            p = Phone(auto_discover=True)
            ok, log = p.ensure_alive()
            print(f"\n� 手机: {'✅ 健康' if ok else '❌ 修复失败'}")
            for line in log:
                print(f"   {line}")
        except Exception as e:
            print(f"\n📱 手机: ❌ {e}")
    for label, base in [("🖥  台式机", _PC_BASE), ("💻 笔记本", _LAPTOP_BASE)]:
        h = _get(base, "/health", 5)
        if "_error" in h:
            print(f"\n{label}: ❌ {h['_error']}")
        else:
            print(f"\n{label}: ✅ {h.get('hostname')} Guard={h.get('guard',{}).get('enabled')}")


# ══════════════════════════════════════════════════════
#  本地 + 研究库 + Agent端口 感知
# ══════════════════════════════════════════════════════

_LOCAL_DIR = os.path.dirname(os.path.abspath(__file__))
_RESEARCH_BASE = os.environ.get("PHONE_RESEARCH_BASE", r"Z:\道\AI-操控手机")

_CORE_FILES = {
    "phone_lib.py":         ("Phone类 90+API",          True),
    "phone_sense.py":       ("手机五感探针",              True),
    "five_senses.py":       ("ADB多模式采集",             True),
    "remote_assist.py":     ("18命令远程协助",             True),
    "sense_all.py":         ("四域五感中枢v2",           True),
    "sense_daemon.py":      ("无感守护 六感背景循环",     False),
    "phone_fleet.py":       ("多设备机队管理",            False),
    "remote_setup.py":      ("远程设置工具",               False),
    "FINDINGS.md":          ("实测发现文档",               False),
    "AGENTS.md":            ("经验库文档",                 False),
    "screenstream-dev.apk": ("ScreenStream APK v4.2.10", False),
    "项目全景图.md":         ("7域41项总体架构",            False),
    "核心架构.md":           ("API分类+数据流",             False),
    "deploy-vivo.ps1":      ("Vivo手机专用部署脚本",        False),
}

_CORE_DIRS = [
    ("ai_mobile",    "OCR+YOLO视觉手机控制(V3.0)",  False),
    ("ai_pc",        "视觉驱动PC控制",               False),
    ("双电脑互联",   "双机互联完整文档",              False),
    ("ai_research",  "AI框架精华(antigravity等)",    False),
    ("collect",      "订单采集脚本群",               False),
    ("deploy",       "部署脚本(fleet/guardian)",    False),
    ("智能家居",     "HA深度探索报告",               False),
    ("tests",        "手机控制测试脚本集",            False),
]

_AI_FRAMEWORKS = [
    ("L1", "droidrun",              "DroidRun: ADB元素ID定位"),
    ("L1", "macrodroid_bridge.py",  "MacroDroid导流桥接"),
    ("L2", "DroidBot-GPT",          "XML+LLM点击决策"),
    ("L2", "AutoDroid",             "自动化脚本生成"),
    ("L2", "AgentDroid",            "Android Agent框架"),
    ("L3", "AppAgent",              "截图+XML,GPT-4V"),
    ("L3", "AppAgentX",             "AppAgent扩展版"),
    ("L3", "MobileAgent",           "截图+坐标标注,Qwen-VL"),
    ("L3", "mobile-use",            "XML+截图,多模型"),
    ("L3", "Agent-S",               "UI-TARS语义Grounding"),
    ("L4", "xiaozhi-AutoGLM-mcp",   "MCP协议接入AutoGLM ⭐"),
    ("L4", "Open-AutoGLM",          "开源AutoGLM实现"),
]

_AGENT_PORTS = [
    ("localhost",       8084,  "📱 手机 ScreenStream InputService"),
    ("localhost",       9904,  "🖥  台式机 Admin remote_agent"),
    ("localhost",       9905,  "🖥  台式机 ai会话 remote_agent"),
    ("192.168.31.179",  9903,  "💻 笔记本 remote_agent"),
    ("192.168.31.32",   8084,  "📱 手机 WiFi直连 ScreenStream"),  # /status端点
    ("60.205.171.100", 19903,  "☁️  公网FRP→台式机"),
]


def sense_local():
    """📂 本地部署状态"""
    r = {"_domain": "local", "_ok": True, "path": _LOCAL_DIR, "files": {}, "dirs": {}}
    for fname, (desc, required) in _CORE_FILES.items():
        fp = os.path.join(_LOCAL_DIR, fname)
        exists = os.path.exists(fp)
        r["files"][fname] = {
            "exists": exists,
            "size_kb": os.path.getsize(fp) // 1024 if exists else 0,
            "desc": desc, "required": required,
        }
    for dname, desc, required in _CORE_DIRS:
        dp = os.path.join(_LOCAL_DIR, dname)
        exists = os.path.isdir(dp)
        count  = len(list(os.scandir(dp))) if exists else 0
        r["dirs"][dname] = {"exists": exists, "count": count, "desc": desc, "required": required}
    r["research_base_z"]  = os.path.isdir(_RESEARCH_BASE)
    missing_f = [f for f, v in r["files"].items() if v["required"] and not v["exists"]]
    missing_d = [d for d, v in r["dirs"].items()  if v["required"] and not v["exists"]]
    r["missing"] = missing_f + missing_d
    r["_ok"] = len(r["missing"]) == 0
    return r


def sense_research():
    """🔬 AI研究库框架可用性（Z:\\道\\AI-操控手机\\）"""
    base_ok = os.path.isdir(_RESEARCH_BASE)
    frameworks = []
    for layer, name, desc in _AI_FRAMEWORKS:
        path = os.path.join(_RESEARCH_BASE, name)
        ok = os.path.exists(path)
        frameworks.append({"layer": layer, "name": name, "desc": desc, "available": ok})
    avail = sum(1 for f in frameworks if f["available"])
    return {
        "_domain":        "research",
        "_ok":            base_ok,
        "base":           _RESEARCH_BASE,
        "base_available": base_ok,
        "frameworks":     frameworks,
        "available":      avail,
        "total":          len(frameworks),
    }


def sense_agents():
    """🌐 扫描所有已知Agent端口在线状态"""
    results = []
    for host, port, desc in _AGENT_PORTS:
        # 手机 ScreenStream 用 /status，remote_agent 用 /health
        path = "/status" if (port == 8084 and "WiFi" in desc) else "/health"
        try:
            with urlopen(Request(f"http://{host}:{port}{path}"), timeout=2) as r:
                data = json.loads(r.read())
                info = data.get("hostname", data.get("connected", data.get("status", "ok")))
                info = str(info)[:35]
            results.append({"host": host, "port": port, "desc": desc.replace("  # /status端点",""), "online": True, "info": info})
        except Exception as e:
            results.append({"host": host, "port": port, "desc": desc.replace("  # /status端点",""), "online": False,
                            "error": str(e)[:55]})
    online = sum(1 for r in results if r["online"])
    return {"_domain": "agents", "_ok": online > 0, "ports": results, "online": online}


def print_local(s):
    print(f"\n{'━'*60}")
    print(f"  📂 本地域  [{s.get('path','?')}]")
    print(f"{'━'*60}")
    print(f"  📄 核心文件:")
    for fname, info in s.get("files", {}).items():
        icon = "✅" if info["exists"] else ("⚠️ " if info["required"] else "○ ")
        print(f"    {icon} {fname:<24} {info['size_kb']:>4}KB  {info['desc']}")
    print(f"  📁 子目录:")
    for dname, info in s.get("dirs", {}).items():
        icon = "✅" if info["exists"] else ("⚠️ " if info["required"] else "○ ")
        print(f"    {icon} {dname+'/':.<26} {info['count']:>3}项  {info['desc']}")
    z = "✅" if s.get("research_base_z") else "○ 未挂载"
    print(f"  {z} Z:\\道\\AI-操控手机\\ 笔记本研究库")
    if s.get("missing"):
        print(f"  ⚠️  缺失必要文件: {s['missing']}")


def print_research(s):
    print(f"\n{'━'*60}")
    print(f"  🔬 AI研究库  [{s.get('base','?')}]")
    print(f"{'━'*60}")
    if not s.get("base_available"):
        print(f"  ○ Z:盘笔记本离线或路径不存在")
        print(f"  本地副本: E:\\道\\AI之手机\\ai_research\\ (精华文档已复制)")
        return
    cur_layer = None
    for f in s.get("frameworks", []):
        if f["layer"] != cur_layer:
            cur_layer = f["layer"]
            print(f"  {cur_layer}:")
        icon = "✅" if f["available"] else "○ "
        print(f"    {icon} {f['name']:<30} {f['desc']}")
    print(f"  小计: {s.get('available',0)}/{s.get('total',0)} 框架可用")


def print_agents(s):
    print(f"\n{'━'*60}")
    print(f"  🌐 Agent端口扫描  [{s.get('online',0)}/{len(s.get('ports',[]))} 在线]")
    print(f"{'━'*60}")
    for p in s.get("ports", []):
        icon = "✅" if p["online"] else "○ "
        info = p.get("info", p.get("error", ""))[:35]
        print(f"  {icon} {p['host']}:{p['port']:<6}  {p['desc']:<38} {info}")


# ══════════════════════════════════════════════════════
#  报告打印
# ══════════════════════════════════════════════════════

def _bar(pct, w=15):
    try:
        n = int(float(str(pct).replace('%','')) / 100 * w)
        return '█' * n + '░' * (w - n)
    except Exception:
        return '─' * w

def print_phone(s):
    v  = s.get("vision",  {})
    h  = s.get("hearing", {})
    t  = s.get("touch",   {})
    sm = s.get("smell",   {})
    ta = s.get("taste",   {})
    print(f"\n{'━'*60}")
    print(f"  📱 手机域  [{s.get('_base','?')}]  {s.get('_mode','')}")
    print(f"{'━'*60}")
    if not s.get("_ok") and "_error" in s:
        print(f"  ❌ {s['_error']}")
        return
    fg = v.get("foreground_app","?").split(".")[-1]
    print(f"  👁  视觉   APP={fg:<22} 文本={v.get('text_count',0)}条  点击={v.get('clickable_count',0)}个")
    if v.get("screen_texts"):
        print(f"       屏显: {' │ '.join(str(x) for x in v['screen_texts'][:5])}")
    print(f"  👂 听觉   媒体={h.get('volume_music','?')}  响铸={h.get('volume_ring','?')}  DND={'开' if h.get('dnd') else '关'}")
    a11y = t.get("input_enabled", False)
    print(f"  🖐  触觉   无障碍={'✅' if a11y else '❌断开'}  息屏={'是' if t.get('screen_off') else '否'}")
    print(f"  👃 嗅觉   通知={sm.get('notification_count',0)}条")
    for n in sm.get("recent",[])[:2]:
        print(f"       [{n.get('app','?'):<12}] {n.get('title','')[:38]}")
    bat = ta.get("battery","?")
    print(f"  👅 味觉   电量={bat}%{'⚡' if ta.get('charging') else ''}  网={ta.get('network','?')}  存储剩={ta.get('storage_free_gb','?')}GB")
    print(f"       设备: {ta.get('model','?')}  WiFi={ta.get('wifi_ssid','?')}")

def print_pc(s):
    icon  = "🖥 " if s.get("_domain") == "desktop" else "💻"
    label = "台式机" if s.get("_domain") == "desktop" else "笔记本"
    print(f"\n{'━'*60}")
    print(f"  {icon} {label}域  [{s.get('_base','?')}]")
    print(f"{'━'*60}")
    if not s.get("_ok"):
        print(f"  ❌ 离线: {s.get('_error','')}")
        return
    vi = s.get("vision",    {})
    cg = s.get("cognition", {})
    rs = s.get("resources", {})
    hh = s.get("health",    {})
    aw = vi.get("active_window","?")
    print(f"  👁  视觉   {vi.get('screen','?')}  锁屏={'是' if vi.get('is_locked') else '否'}  活跃窗口: {aw[:40]}")
    for w in vi.get("windows",[])[:2]:
        if w: print(f"       · {w}")
    print(f"  🖐  触觉   Guard={'✅' if hh.get('guard') else '○'}  session={hh.get('session','?')}")
    ut = int(cg.get("uptime_sec", 0)) // 3600
    print(f"  🧠 认知   {cg.get('user','?')}@{cg.get('hostname','?')}  开机{ut}h")
    ram = rs.get("ram_pct", 0)
    print(f"  💾 资源   RAM {ram}% [{_bar(ram)}]  磁盘剩={rs.get('disk_free','?')}GB")


# ══════════════════════════════════════════════════════
#  🌐 四维统一感知 — 用户+多Agent+工作区+电脑
# ══════════════════════════════════════════════════════

def _run_all_senses(args):
    """四维并行感知：用户五感 / 多Agent五感 / 工作区五感 / 电脑五感"""
    t_start = time.time()
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n🌐 四维统一感知 [{ts}] — 并行采集中...", flush=True)

    results = {}
    errors  = {}

    def _do_agents():
        r = {}
        tasks = {
            "phone":   sense_phone,
            "desktop": lambda: sense_pc(_PC_BASE,     "desktop"),
            "laptop":  lambda: sense_pc(_LAPTOP_BASE, "laptop"),
        }
        r = _run_parallel(tasks)
        return r

    def _do_hw():
        if not _HW_OK:
            return {"_ok": False, "_error": "pc_senses未安装"}
        pc = _PC_Senses(capture_screen=False)
        return pc.sense_all()

    def _do_workspace():
        if not _WS_OK:
            return {"_ok": False, "_error": "workspace_senses未安装"}
        return _ws_sense()

    with ThreadPoolExecutor(max_workers=3) as ex:
        futs = {
            ex.submit(_do_agents):   "agents",
            ex.submit(_do_hw):       "hardware",
            ex.submit(_do_workspace):"workspace",
        }
        for fut in as_completed(futs, timeout=45):
            key = futs[fut]
            try:
                results[key] = fut.result()
            except Exception as e:
                errors[key] = str(e)[:80]
                results[key] = {"_ok": False, "_error": str(e)[:80]}

    elapsed = time.time() - t_start

    if getattr(args, 'json', False):
        print(json.dumps(results, ensure_ascii=False, indent=2, default=str))
        return

    # ══ 打印四维报告 ══════════════════════════════════════
    print(f"\n{'═'*68}")
    print(f"  🌐 道之四维感知  [{ts}]  总耗时{elapsed:.1f}s")
    print(f"{'═'*68}")

    # ── 维度一：用户五感（从硬件五感中提取用户视角）──────────────
    hw = results.get("hardware", {})
    print(f"\n  ┌─ 🧑 维度一·用户五感 {'─'*40}")
    if hw.get("taste") or hw.get("eyes") or hw.get("touch"):
        eyes  = hw.get("eyes",  {})
        touch = hw.get("touch", {})
        taste = hw.get("taste", {})
        cpu   = taste.get("cpu",  {})
        ram   = taste.get("ram",  {})
        # 用户视角：我在做什么、电脑快不快、磁盘够不够
        print(f"  │  👁  正在做: {eyes.get('active_window','?')[:55]}")
        print(f"  │  🖐  响应感: {touch.get('lag_level','?')}  (评分{touch.get('lag_score',0):.2f})")
        print(f"  │  💻 电脑感: CPU={cpu.get('total_pct',0):.1f}%  RAM={ram.get('used_pct',0):.1f}%({ram.get('avail_gb',0):.1f}GB可用)")
        # 磁盘压迫感
        disks = taste.get("disks", {})
        disk_warns = [(mp, d['used_pct'], d['free_gb'])
                      for mp, d in disks.items() if d.get('used_pct',0) > 85]
        if disk_warns:
            print(f"  │  💾 磁盘压: {' | '.join(f'{mp} {pct:.0f}%满({free:.0f}GB剩)' for mp,pct,free in disk_warns)}")
        # 事件预警
        ears_hw = hw.get("ears", {})
        if ears_hw.get("error_count", 0) > 0:
            print(f"  │  🔔 系统告: {ears_hw['error_count']}条错误  {ears_hw.get('warning_count',0)}条警告")
    else:
        print(f"  │  ❌ 硬件感知未就绪 {hw.get('_error','')}")

    # ── 维度二：多Agent五感 ──────────────────────────────────────
    agents = results.get("agents", {})
    print(f"\n  ├─ 🤖 维度二·多Agent五感 {'─'*37}")
    for key, label, icon in [("phone","手机","📱"), ("desktop","台式机","🖥"), ("laptop","笔记本","💻")]:
        s = agents.get(key, {})
        if not s:
            print(f"  │  {icon} {label}: 未感知")
            continue
        if not s.get("_ok"):
            print(f"  │  {icon} {label}: ❌ 离线  {s.get('_error','')[:40]}")
            continue
        if key == "phone":
            v  = s.get("vision",  {})
            ta = s.get("taste",   {})
            fg = str(v.get("foreground_app","?")).split(".")[-1][:20]
            bat= ta.get("battery","?")
            print(f"  │  {icon} {label}: ✅ APP={fg:<20} 电量={bat}%  屏显{v.get('text_count',0)}条")
        else:
            vi = s.get("vision",   {})
            rs = s.get("resources",{})
            aw = vi.get("active_window","?")[:35]
            ram_pct = rs.get("ram_pct","?")
            print(f"  │  {icon} {label}: ✅ [{aw}]  RAM={ram_pct}%  磁盘剩={rs.get('disk_free','?')}GB")

    # ── 维度三：工作区五感 ────────────────────────────────────────
    ws = results.get("workspace", {})
    print(f"\n  ├─ 📂 维度三·工作区五感 {'─'*38}")
    if ws.get("_error"):
        print(f"  │  ❌ {ws['_error']}")
    else:
        ws_taste = ws.get("taste", {})
        ws_touch = ws.get("touch", {})
        ws_eyes  = ws.get("eyes",  {})
        ws_ears  = ws.get("ears",  {})
        ws_smell = ws.get("smell", {})
        score = ws_taste.get("health_score",  0)
        level = ws_taste.get("health_level",  "?")
        ok_ct = ws_touch.get("all_critical_ok", False)
        recent_n = ws_eyes.get("recent_count", 0)
        print(f"  │  👅 健康分: {score}分 {level}  关键文件={'✅' if ok_ct else '⚠️ 缺失'}")
        print(f"  │  👁  最近{recent_n}个文件改动  活跃域={ws_taste.get('active_domains','?')}个")
        # 最近修改 top3
        for f in ws_eyes.get("recent_files", [])[:3]:
            print(f"  │    [{f['mtime']}] {f['path'][:50]}")
        # 工作区嗅觉异常
        for a in ws_smell.get("anomalies", [])[:3]:
            print(f"  │  ⚠️  [{a['category']}] {a['issue'][:55]}")
        # HA状态
        ha_err = ws_ears.get("ha_error_count", 0)
        ha_warn = ws_ears.get("ha_warning_count", 0)
        print(f"  │  👂 HA日志: 错误{ha_err}  警告{ha_warn}")
        # 网络挂载
        mounts = ws_touch.get("mounts", [])
        online_m = [m["drive"] for m in mounts if m.get("online")]
        offline_m = [m["drive"] for m in mounts if not m.get("online")]
        if online_m:  print(f"  │  🔗 挂载在线: {' '.join(online_m)}")
        if offline_m: print(f"  │  ○  挂载离线: {' '.join(offline_m)}")

    # ── 维度四：电脑底层五感 ──────────────────────────────────────
    print(f"\n  └─ 🔩 维度四·电脑底层五感 {'─'*36}")
    if hw.get("_error") and not hw.get("taste"):
        print(f"     ❌ {hw['_error']}")
    else:
        taste = hw.get("taste", {})
        cpu   = taste.get("cpu",  {})
        ram   = taste.get("ram",  {})
        net   = taste.get("net",  {})
        io    = taste.get("disk_io", {})
        smell = hw.get("smell", {})
        touch = hw.get("touch", {})

        # CPU
        hot = cpu.get("hot_cores", [])
        hot_str = f" ⚠️热点核{hot}" if hot else ""
        print(f"     👅 CPU  {cpu.get('total_pct',0):.1f}% [{_bar(cpu.get('total_pct',0))}]  "
              f"{cpu.get('freq_ghz',0)}GHz {cpu.get('physical_cores',0)}C{cpu.get('logical_cores',0)}T{hot_str}")
        print(f"        RAM  {ram.get('used_pct',0):.1f}% [{_bar(ram.get('used_pct',0))}]  "
              f"共{ram.get('total_gb',0)}GB  可用{ram.get('avail_gb',0):.1f}GB")
        # 磁盘IO + 网络
        if not io.get("error"):
            print(f"        IO   磁盘R={io.get('read_mbs',0):.1f}MB/s W={io.get('write_mbs',0):.1f}MB/s  "
                  f"网络↑{net.get('up_kbs',0):.0f}KB/s ↓{net.get('dn_kbs',0):.0f}KB/s")
        # 进程大户
        top_cpu = smell.get("top_cpu", [])[:3]
        top_mem = smell.get("top_mem", [])[:3]
        if top_cpu:
            _cpu_str = ' | '.join('%s=%.1f%%' % (p['name'][:18], p['cpu_pct']) for p in top_cpu)
            print(f"     👃 CPU大户: {_cpu_str}")
        if top_mem:
            _mem_str = ' | '.join('%s=%.0fMB' % (p['name'][:18], p['mem_mb']) for p in top_mem)
            print(f"        内存大户: {_mem_str}")

    # ── 综合诊断 ──────────────────────────────────────────────────
    print(f"\n{'─'*68}")
    all_alerts = []

    # 硬件告警
    if _HW_OK and hw.get("taste"):
        pc_obj = _PC_Senses()
        alerts = pc_obj.diagnose(hw)
        for a in alerts:
            all_alerts.append(f"{a['level']} [{a['source']}] {a['issue']}")

    # 工作区告警
    if _WS_OK and not ws.get("_error"):
        ws_touch_data = ws.get("touch", {})
        for f in ws_touch_data.get("critical_files", []):
            if not f["exists"]:
                all_alerts.append(f"🟡 警告 [工作区] 关键文件缺失: {f['path']}")
        ws_smell_data = ws.get("smell", {})
        for a in ws_smell_data.get("anomalies", [])[:3]:
            if "超大" in a.get("category","") or "膨胀" in a.get("category",""):
                all_alerts.append(f"🟡 警告 [工作区/{a['category']}] {a['issue'][:60]}")

    # Agent告警
    for key, label in [("phone","手机"),("desktop","台式机"),("laptop","笔记本"),("ai","ai账号")]:
        if agents.get(key, {}).get("_ok") == False:
            all_alerts.append(f"🟡 警告 [Agent/{label}] 离线")

    if not all_alerts:
        print(f"  ✅ 四维无告警 — 不杂·不乱·不卡·得道")
    else:
        print(f"  🩺 综合告警 ({len(all_alerts)}项):")
        for a in all_alerts[:10]:
            print(f"  {a}")

    print(f"\n  📊 快捷命令:")
    print(f"  --hw          电脑底层五感详情")
    print(f"  --ws          工作区五感详情")
    print(f"  --agents      Agent端口扫描")
    print(f"  --ai          ai子账号五感(:9905)")
    print(f"  --ai --scan   ai子账号软件扫描")
    print(f"  --hw --watch  实时硬件守护")
    print(f"{'═'*68}\n")


# ══════════════════════════════════════════════════════
#  主入口
# ══════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="三域感知·行动·验证·守护 — 得道主脑",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json",    action="store_true", help="JSON输出")
    parser.add_argument("--phone",   action="store_true", help="仅手机域")
    parser.add_argument("--pc",      action="store_true", help="仅台式机域")
    parser.add_argument("--laptop",  action="store_true", help="仅笔记本域")
    parser.add_argument("--heal",     action="store_true", help="检测+修复三域")
    parser.add_argument("--local",    action="store_true", help="本地部署状态")
    parser.add_argument("--research", action="store_true", help="AI研究库框架状态")
    parser.add_argument("--agents",   action="store_true", help="扫描所有Agent端口")
    parser.add_argument("--hw",       action="store_true", help="🔩 硬件底层五感（CPU/RAM/磁盘/进程/卡顿/事件日志）")
    parser.add_argument("--ws",       action="store_true", help="📂 工作区五感（E:\\道目录/日志/关键文件）")
    parser.add_argument("--all",      action="store_true", help="🌐 四维统一报告（用户+多Agent+工作区+电脑）")
    parser.add_argument("--watch",    nargs="?", const=10, type=int, metavar="秒",
                        help="持续硬件监控（配合--hw使用，默认10s）")
    parser.add_argument("--screen",   action="store_true", help="硬件感知时同步截图（配合--hw）")
    parser.add_argument("--act",     nargs="+", metavar="ARG",
                        help="行动: --act phone click 目标 | --act pc shell hostname")
    parser.add_argument("--verify",  nargs="+", metavar="ARG",
                        help="验证: --verify phone 预期文字 [5秒]")
    parser.add_argument("--monitor", nargs="?", const=30, type=int, metavar="秒",
                        help="六感守护循环 (默认30秒)")
    parser.add_argument("--loop",    nargs="+", metavar="ARG",
                        help="感→行→验闭环: --loop phone click 微信")
    parser.add_argument("--ai",      action="store_true", help="🖥  ai子账号五感报告(:9905)")
    parser.add_argument("--scan",    action="store_true", help="配合--ai: 扫描已安装软件")
    args = parser.parse_args()

    # ai子账号五感
    if args.ai:
        _ai_script = os.path.normpath(os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "AI之电脑", "agent", "sense_ai_capabilities.py"))
        _ai_args = [sys.executable, _ai_script]
        if args.scan:   _ai_args.append("--scan-apps")
        if args.json:   _ai_args.append("--json")
        import subprocess as _sp
        _r = _sp.run(_ai_args, capture_output=False, text=True)
        sys.exit(_r.returncode)

    # 本地/研究库/端口 快速查询
    if args.local:
        s = sense_local()
        if args.json: print(json.dumps(s, ensure_ascii=False, indent=2))
        else: print_local(s)
        return
    if args.research:
        s = sense_research()
        if args.json: print(json.dumps(s, ensure_ascii=False, indent=2))
        else: print_research(s)
        return
    if args.agents:
        s = sense_agents()
        if args.json: print(json.dumps(s, ensure_ascii=False, indent=2))
        else: print_agents(s)
        return

    # 📂 工作区五感
    if args.ws:
        if not _WS_OK:
            print("❌ workspace_senses.py 未找到")
            return
        report = _ws_sense()
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        else:
            _ws_print(report)
        return

    # 🌐 四维统一感知 (--all)
    if args.all:
        _run_all_senses(args)
        return

    # 🔩 硬件底层五感
    if args.hw:
        if not _HW_OK:
            print("❌ pc_senses.py 未找到，请确认 E:\\道\\_lib\\pc_senses.py 存在")
            return
        pc = _PC_Senses(capture_screen=getattr(args, 'screen', False))
        if getattr(args, 'watch', None) is not None:
            interval = args.watch if args.watch else 10
            print(f"🔮 硬件五感守护 (间隔{interval}s) — Ctrl+C 停止", flush=True)
            import time as _t
            n = 0
            try:
                while True:
                    n += 1
                    report = pc.sense_all()
                    alerts = pc.diagnose(report)
                    taste  = report.get("taste", {})
                    cpu    = taste.get("cpu",  {})
                    ram    = taste.get("ram",  {})
                    touch  = report.get("touch", {})
                    ts     = time.strftime("%H:%M:%S")
                    icon   = "🟢" if not alerts else ("🟡" if all(a["level"].startswith("🟡") for a in alerts) else "🔴")
                    print(f"[{ts}] #{n} {icon}  CPU={cpu.get('total_pct',0):.1f}%  "
                          f"RAM={ram.get('used_pct',0):.1f}%  "
                          f"卡顿={touch.get('lag_level','?')}  "
                          f"告警:{len(alerts)}", flush=True)
                    for a in alerts:
                        print(f"  {a['level']} [{a['source']}] {a['issue']}", flush=True)
                    _t.sleep(max(1, interval))
            except KeyboardInterrupt:
                print(f"\n守护已停止 (共{n}轮)")
            return
        report = pc.sense_all()
        if args.json:
            out = {k: v for k, v in report.items()}
            print(json.dumps(out, ensure_ascii=False, indent=2))
        else:
            pc.print_report(report)
        return

    # 守 (Monitor)
    if args.monitor is not None:
        monitor_loop(interval=args.monitor)
        return

    # 修复 (Heal)
    if args.heal:
        heal_all()
        return

    # 行 (Act)
    if args.act:
        domain = args.act[0] if len(args.act) > 0 else "phone"
        action = args.act[1] if len(args.act) > 1 else "click"
        target = " ".join(args.act[2:]) if len(args.act) > 2 else ""
        r = act(domain, action, target)
        if args.json:
            print(json.dumps(r, ensure_ascii=False, indent=2))
        else:
            icon = "✅" if r.get("ok") else "❌"
            print(f"{icon} [{domain}] {action}({target!r})")
            resp = r.get("response", {})
            if isinstance(resp, dict):
                for k, v in resp.items():
                    if k not in ("_error", "_ok") and v:
                        print(f"   {k}: {str(v)[:100]}")
            if r.get("msg"): print(f"   {r['msg']}")
        sys.exit(0 if r.get("ok") else 1)

    # 验 (Verify)
    if args.verify:
        domain  = args.verify[0] if len(args.verify) > 0 else "phone"
        text    = args.verify[1] if len(args.verify) > 1 else ""
        timeout = int(args.verify[2]) if len(args.verify) > 2 else 5
        ok, msg = verify(domain, text, timeout)
        print(msg)
        sys.exit(0 if ok else 1)

    # 感→行→验 闭环 (Loop)
    if args.loop:
        domain = args.loop[0] if len(args.loop) > 0 else "phone"
        action = args.loop[1] if len(args.loop) > 1 else "click"
        target = " ".join(args.loop[2:]) if len(args.loop) > 2 else ""
        print(f"\n🔄 闭环: {domain}.{action}({target!r})")
        # 感 (before)
        print("  [1/3] 感 — 采集行动前状态...")
        if domain == "phone":
            before_state = sense_phone()
            before_texts = before_state.get("vision", {}).get("screen_texts", [])
        else:
            before_state = sense_pc(_domain_base(domain), domain)
            before_texts = before_state.get("vision", {}).get("windows", [])
        print(f"      屏幕: {before_texts[:3]}")
        # 行 (act)
        print("  [2/3] 行 — 执行动作...")
        r = act(domain, action, target)
        icon = "✅" if r.get("ok") else "❌"
        print(f"      {icon} {action}({target!r}) -> {r.get('response', r.get('msg', ''))!r:.60}")
        time.sleep(1.5)
        # 验 (verify - check screen changed)
        print("  [3/3] 验 — 检查状态变化...")
        if domain == "phone":
            after_state = sense_phone()
            after_texts = after_state.get("vision", {}).get("screen_texts", [])
            changed = set(after_texts) != set(before_texts)
        else:
            after_state = sense_pc(_domain_base(domain), domain)
            after_texts = after_state.get("vision", {}).get("windows", [])
            changed = set(after_texts) != set(before_texts)
        print(f"      屏幕: {after_texts[:3]}")
        result_icon = "✅ 屏幕已变化" if changed else "⚠️ 屏幕未变化"
        print(f"\n{result_icon}  \u611f→行→验 闭环完成")
        sys.exit(0 if r.get("ok") else 1)

    # 感 (Sense) — 默认模式
    all_domains = not (args.phone or args.pc or args.laptop or args.local or args.research or args.agents)
    tasks = {}
    if all_domains or args.phone:  tasks["phone"]   = sense_phone
    if all_domains or args.pc:     tasks["desktop"]  = lambda: sense_pc(_PC_BASE,     "desktop")
    if all_domains or args.laptop: tasks["laptop"]   = lambda: sense_pc(_LAPTOP_BASE, "laptop")

    print(f"🌐 感知 {len(tasks)} 域...", flush=True)
    t0 = time.time()
    results = _run_parallel(tasks)
    elapsed = time.time() - t0

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    print(f"⏱  {elapsed:.1f}s")
    for key in ["phone", "desktop", "laptop"]:
        if key not in results: continue
        s = results[key]
        if key == "phone": print_phone(s)
        else:              print_pc(s)

    # 知 (Know) — 分析 + 告警
    alerts, advice = analyze(results)
    online = sum(1 for s in results.values() if s.get("_ok"))
    print(f"\n{'━'*60}")
    print(f"  感→知→行→验→守 = 得道   {online}/{len(results)}域在线")
    for lvl, title, detail in alerts:
        print(f"  {lvl} {title}: {detail}")
    if advice:
        print(f"\n💡 建议:")
        for a in advice:
            print(f"  python sense_all.py {a}")
    print(f"\n📊 行·验·守:")
    print(f"  --act phone click 目标文字        手机点击")
    print(f"  --act pc shell 'dir E:\\\'         台式机命令")
    print(f"  --verify phone 预期文字 [5]     验证屏幕")
    print(f"  --loop phone click 微信          感→行→验闭环")
    print(f"  --monitor [30]                   六感守护循环")


if __name__ == "__main__":
    main()
