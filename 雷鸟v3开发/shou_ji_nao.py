#!/usr/bin/env python3
"""
手机脑调度层 — PC 薄桥接 (临时)

老子第四十二章: 道生一，一生二，二生三，三生万物
  此脚本 = 梯（用后即撤）
  手机脑 = 一切处理在手机 (phone_server.py, 地址由wireless_config管理)
  眼镜   = 纯感知器 (听/说/看/触)
  PC     = 只做 ADB USB relay，逻辑为零

脱PC三阶段:
  Phase 1 (今):  PC运行此脚本 → 桥接眼镜ADB ↔ 手机HTTP
  Phase 2 (近):  眼镜连接WiFi → 手机ADB connect 眼镜 → 撤PC
  Phase 3 (远):  原生SDK App → 完全无线无PC

一听一说一看一触——皆在眼镜呼，而无需于手机呼
"""

import subprocess
import threading
import time
import json
import base64
import urllib.request
import urllib.error
import sys
from pathlib import Path

# ─── 配置（统一由wireless_config管理） ─────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent))
from wireless_config import wm, ADB

# 动态获取（WiFi断重连后地址可能变化）
def _glass_id(): return wm.glass_addr
def _phone_ip(): return wm.phone_ip
def _brain_url(): return wm.brain_url

GLASS_ID   = wm.glass_addr  # 向后兼容初始值
PHONE_IP   = wm.phone_ip
PHONE_PORT = 8765
BRAIN_URL  = wm.brain_url

TTS_DIR    = Path(__file__).resolve().parent

# TP手势阈值
TP_SLIDE_THRESH = 300
TP_DOUBLE_MS    = 400

# ─── 工具 ─────────────────────────────────────────────────
def adb(*args, timeout: int = 15) -> str:
    cmd = [ADB, "-s", _glass_id()] + list(args)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout, encoding="utf-8", errors="replace")
        return r.stdout.strip()
    except Exception:
        return ""

def adb_bg(*args) -> subprocess.Popen:
    cmd = [ADB, "-s", _glass_id()] + list(args)
    return subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace"
    )

def phone_post(endpoint: str, data: dict, timeout: int = 20) -> dict:
    """POST到手机脑"""
    try:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            f"{_brain_url()}{endpoint}",
            data=body,
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.URLError as e:
        print(f"  [桥] 手机脑无响应: {e}")
        return {"error": str(e)}
    except Exception as e:
        return {"error": str(e)}

def phone_get(endpoint: str) -> dict:
    try:
        with urllib.request.urlopen(f"{_brain_url()}{endpoint}", timeout=5) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}

_tts_engine = None
_tts_zh_voice = None
_tts_lock = threading.Lock()

def _get_tts_engine():
    """缓存pyttsx3引擎（避免每次调用都创建新实例）"""
    global _tts_engine, _tts_zh_voice
    if _tts_engine is None:
        import pyttsx3
        _tts_engine = pyttsx3.init()
        _tts_engine.setProperty("rate", 160)
        for v in _tts_engine.getProperty("voices"):
            if any(x in v.name.lower() for x in ["zh","chinese","huihui"]):
                _tts_zh_voice = v.id
                break
    return _tts_engine, _tts_zh_voice

def glasses_tts(text: str):
    """TTS到眼镜（PC生成 pyttsx3 → 推送 → 播放）"""
    tmp = str(TTS_DIR / "_sj_tts.wav")
    try:
        with _tts_lock:
            engine, zh_voice = _get_tts_engine()
            if zh_voice:
                engine.setProperty("voice", zh_voice)
            engine.save_to_file(text, tmp)
            engine.runAndWait()
        adb("push", tmp, "/sdcard/_sj_tts.wav")
        adb("shell", "am", "start", "-a", "android.intent.action.VIEW",
            "-d", "file:///sdcard/_sj_tts.wav", "-t", "audio/wav",
            "--grant-read-uri-permission")
    except Exception as e:
        print(f"  [TTS] {e}")

def check_phone_brain() -> bool:
    """检查手机脑是否在线"""
    r = phone_get("/ping")
    return "error" not in r and ("pong" in r or "pong" in str(r.values()))

# ─── 眼镜TP监听 ───────────────────────────────────────────
class GlassesListener:
    """
    监听眼镜感知事件 → 路由到手机脑
    庖丁之道：依乎天理，一触即达
    """

    def __init__(self):
        self.running = False
        self._x_start = self._x_last = None
        self._t_start = 0.0
        self._last_tap = 0.0
        self._last_photo_path = None

    def start(self):
        self.running = True
        t = threading.Thread(target=self._tp_loop, daemon=True, name="TP")
        b = threading.Thread(target=self._btn_loop, daemon=True, name="Btn")
        t.start()
        b.start()
        print("[桥] 眼镜感知监听已启动")

    def stop(self):
        self.running = False

    # ─── TP 触控 ────────────────────────────────────────────
    def _tp_loop(self):
        proc = adb_bg("shell", "getevent", "-l", "/dev/input/event3")
        for line in proc.stdout:
            if not self.running:
                break
            line = line.strip()
            if "ABS_MT_POSITION_X" in line or "ABS_X" in line:
                try:
                    x = int(line.split()[-1], 16)
                    if self._x_start is None:
                        self._x_start = x
                        self._t_start = time.time()
                    self._x_last = x
                except (ValueError, IndexError):
                    pass
            elif "BTN_TOUCH" in line and "00000000" in line:
                self._process_touch()

    def _process_touch(self):
        if self._x_start is None:
            return
        dx = (self._x_last or self._x_start) - self._x_start
        dur_ms = (time.time() - self._t_start) * 1000
        self._x_start = self._x_last = None

        if abs(dx) > TP_SLIDE_THRESH:
            gesture = "slide_fwd" if dx > 0 else "slide_back"
        elif dur_ms > 600:
            gesture = "long_press"
        else:
            now = time.time()
            gesture = "double_tap" if now - self._last_tap < TP_DOUBLE_MS / 1000 else "tap"
            self._last_tap = now

        print(f"  [眼镜·触] {gesture}")
        threading.Thread(target=self._handle, args=(gesture,), daemon=True).start()

    # ─── ActionButton ────────────────────────────────────────
    def _btn_loop(self):
        proc = adb_bg("shell", "getevent", "-l", "/dev/input/event1")
        press_t = 0.0
        for line in proc.stdout:
            if not self.running:
                break
            line = line.strip()
            if "0000aa" in line or "KEY_PROG2" in line:
                if "00000001" in line:
                    press_t = time.time()
                elif "00000000" in line:
                    dur = (time.time() - press_t) * 1000
                    action = "long_press" if dur > 600 else "tap"
                    threading.Thread(target=self._handle,
                                     args=(f"btn_{action}",), daemon=True).start()

    # ─── 意图路由 → 手机脑 ──────────────────────────────────
    def _handle(self, gesture: str):
        """
        以气听：意图→手机脑路由
        眼镜感知 → 手机AI处理 → 眼镜TTS回馈
        """
        print(f"  [桥→手机脑] {gesture}")

        if gesture == "tap":
            # 视觉：眼镜拍照 → 手机处理
            self._handle_capture()

        elif gesture == "double_tap":
            # 听觉：语音意图→AI问答
            r = phone_post("/glasses", {"event": "double_tap",
                                        "data": {"query": "有什么可以帮你"}})
            if "answer" in r:
                glasses_tts(r["answer"][:60])

        elif gesture == "slide_fwd":
            r = phone_post("/glasses", {"event": "slide_fwd", "data": {}})
            glasses_tts("向前")

        elif gesture == "slide_back":
            r = phone_post("/glasses", {"event": "slide_back", "data": {}})
            glasses_tts("向后")

        elif gesture in ("long_press", "btn_long_press"):
            # 状态报告
            r = phone_post("/glasses", {"event": "status", "data": {}})
            if "battery" in r.get("data", {}):
                d = r["data"]
                msg = f"手机{d.get('battery', '?')}%，AI{'就绪' if d.get('ai_ready') else '离线'}"
                glasses_tts(msg)
            else:
                glasses_tts("状态正常")

        elif gesture == "btn_tap":
            # ActionButton短按 → 通知播报 or 状态
            r = phone_post("/glasses", {"event": "status", "data": {}})
            glasses_tts("三体联动中")

    def _handle_capture(self):
        """眼镜拍照 → 推手机处理 → 眼镜说结果"""
        glasses_tts("正在拍照")
        # 眼镜拍照
        ts = int(time.time())
        adb("shell", "am", "start", "-a",
            "android.media.action.IMAGE_CAPTURE",
            "--ez", "android.intent.extra.quickCapture", "true")
        time.sleep(2.0)
        ls = adb("shell", "ls", "-t", "/sdcard/DCIM/Camera/", "2>/dev/null")
        photo_path = None
        if ls:
            lines = [l.strip() for l in ls.splitlines() if l.strip().endswith(".jpg")]
            if lines:
                remote = f"/sdcard/DCIM/Camera/{lines[0]}"
                local = str(TTS_DIR / f"cap_{ts}.jpg")
                adb("pull", remote, local)
                photo_path = local if Path(local).exists() else None

        if photo_path:
            # 读取图片 → base64 → 发手机脑
            with open(photo_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            r = phone_post("/see", {"image_b64": b64}, timeout=25)
            ans = r.get("answer", r.get("text", "已拍照"))
            glasses_tts(ans[:60])
        else:
            glasses_tts("拍照失败，请重试")


# ─── 部署手机脑 ───────────────────────────────────────────
def deploy_phone_brain():
    """
    将 phone_server.py 推送到手机 + Termux 安装依赖
    一次性操作，之后手机独立运行
    """
    server_py = Path(__file__).parent / "phone_server.py"
    if not server_py.exists():
        print(f"❌ 找不到 {server_py}")
        return False

    from wireless_config import PHONE_USB_SERIAL
    adb_phone = [ADB, "-s", PHONE_USB_SERIAL]  # 手机

    print("[部署] 推送 phone_server.py 到手机...")
    r = subprocess.run(adb_phone + ["push", str(server_py), "/sdcard/phone_server.py"],
                       capture_output=True, text=True)
    if "pushed" not in r.stdout:
        print(f"❌ 推送失败: {r.stderr}")
        return False
    print("  ✅ 文件已推送")

    print("[部署] 复制到Termux HOME目录...")
    subprocess.run(adb_phone + [
        "shell", "run-as", "com.termux",
        "cp", "/sdcard/phone_server.py",
        "/data/data/com.termux/files/home/phone_server.py"
    ], capture_output=True)

    print("[部署] 完成！手机Termux中运行：")
    print("\n  ┌─ 手机Termux命令（复制到Termux执行）──────────────────┐")
    print("  │  pkg install python python-pip -y                   │")
    print("  │  pip install flask requests                         │")
    print("  │  export DASHSCOPE_API_KEY='你的Key'                  │")
    print("  │  python ~/phone_server.py                           │")
    print("  └──────────────────────────────────────────────────────┘\n")
    return True


# ─── 脱PC路径 ─────────────────────────────────────────────
def show_depc_path():
    """显示脱PC三阶段路径"""
    print("""
╔═══════════════════════════════════════════════════════════╗
║            脱PC化三阶段路径                               ║
╚═══════════════════════════════════════════════════════════╝

Phase 1 (今天，此脚本在运行):
  眼镜 ──USB ADB──→ PC ──HTTP──→ 手机脑(Termux:8765)
                         ↑──────── 响应 TTS ─────────┘

Phase 2 (手动操作眼镜连WiFi后, 使用 phone_relay.py):
  1. 眼镜连接到家庭WiFi (IP由wireless_config自动发现)
  2. 手机运行: python phone_relay.py (自动adb connect)
  3. 手机接管: 从此手机替代PC做ADB relay
  4. PC可以关机

Phase 3 (原生App，终极):
  眼镜 ──WiFi/BT──→ 手机(百万App + AI + TTS)
  SDK: MarsAndroidSDK-v1.0.1 已在项目 SDK/ 目录

当其无（PC不在），有车之用 ── 老子第十一章
""")


# ─── 主循环 ───────────────────────────────────────────────
class ShouJiNao:
    """
    手机为中枢调度层

    道生一: 手机脑 (phone_server.py @ Termux)
    一生二: 手机 + 眼镜 (感知接口)
    二生三: 手机 + 眼镜 + AI生态 (百万App + API)
    三生万物: 眼镜呼之即来，而无需于手机呼
    """

    def __init__(self):
        self.listener = GlassesListener()
        self.running = False

    def sense(self):
        """三体状态报告"""
        glass_bat = -1
        bat_out = adb("shell", "dumpsys", "battery")
        for line in bat_out.splitlines():
            if "level:" in line:
                try:
                    glass_bat = int(line.split(":")[-1].strip())
                except (ValueError, IndexError):
                    pass
                break

        phone_ok = check_phone_brain()
        r = phone_get("/status") if phone_ok else {}

        print("\n╔══════════════════════════════════════╗")
        print("║  手机脑 · 三体状态                   ║")
        print("╚══════════════════════════════════════╝")
        print(f"  手机脑: {'✅ 在线' if phone_ok else '❌ 离线'} ({_phone_ip()}:{PHONE_PORT})")
        if phone_ok and r:
            print(f"  手机:   {r.get('battery', '?')}% "
                  f"WiFi:{r.get('wifi', '?')} "
                  f"AI:{'✅' if r.get('ai_ready') else '❌'}")
        print(f"  眼镜:   {'?' if glass_bat < 0 else str(glass_bat) + '%'} (XRGF50)")
        print(f"  PC:     临时桥梁（阶段一）")
        print()

        if not phone_ok:
            print("⚠️  手机脑未启动。在手机Termux中运行：")
            print(f"   python ~/phone_server.py\n")

    def run(self):
        """启动手机为中枢的三体联动"""
        print("\n╔══════════════════════════════════════════════════════╗")
        print("║  手机脑 · 道生一，一生二，二生三，三生万物            ║")
        print("║  眼镜=器（听说看触）  手机=脑（百万App+AI）          ║")
        print("║  PC=梯（Phase 1临时，Phase 2撤除）                   ║")
        print("╚══════════════════════════════════════════════════════╝\n")

        # 检查手机脑
        if not check_phone_brain():
            print(f"⚠️  手机脑 ({_phone_ip()}:{PHONE_PORT}) 未响应")
            print("   请在手机Termux中运行: python ~/phone_server.py")
            print("   等待中（30秒后重试）...\n")
            for i in range(30, 0, -5):
                print(f"   {i}s...", end="\r")
                time.sleep(5)
                if check_phone_brain():
                    break
            if not check_phone_brain():
                print("\n   手机脑仍离线，以PC降级模式运行（TTS本地处理）")

        self.sense()
        self.listener.start()
        self.running = True

        print("✅ 手机脑模式运行中")
        print("  [单击TP]   = 眼镜看 → 手机AI识别 → 眼镜说")
        print("  [双击TP]   = 眼镜问 → 手机AI回答 → 眼镜说")
        print("  [前滑TP]   = 向前/下一")
        print("  [后滑TP]   = 向后/返回")
        print("  [长按TP]   = 三体状态报告")
        print("  [ActionBtn] = 状态播报")
        print("  一听一说一看一触，皆于眼镜，而无需于手机\n")

        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[归根] 手机脑桥接关闭")
            self.running = False
            self.listener.stop()


# ─── CLI ──────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="手机为中枢调度层")
    parser.add_argument("--run",    action="store_true", help="启动手机脑联动")
    parser.add_argument("--sense",  action="store_true", help="三体状态报告")
    parser.add_argument("--deploy", action="store_true", help="部署phone_server到手机")
    parser.add_argument("--path",   action="store_true", help="显示脱PC三阶段路径")
    parser.add_argument("--speak",  type=str,            help="眼镜TTS测试")
    parser.add_argument("--ask",    type=str,            help="向手机AI提问")
    args = parser.parse_args()

    sj = ShouJiNao()

    if args.sense:
        sj.sense()
    elif args.deploy:
        deploy_phone_brain()
    elif args.path:
        show_depc_path()
    elif args.speak:
        glasses_tts(args.speak)
    elif args.ask:
        r = phone_post("/ask", {"query": args.ask})
        print(f"手机AI: {r.get('answer', r)}")
    elif args.run:
        sj.run()
    else:
        sj.sense()
        show_depc_path()
