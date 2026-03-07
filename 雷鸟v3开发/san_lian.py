#!/usr/bin/env python3
"""
三联道 · 一生二 二生三 三生万物
San Lian Dao — Three-Body Integration

老子第四十二章:
  道生一，一生二，二生三，三生万物。

  道  →  PC主脑（算法·AI·调度）
  一  →  PC独感知（sense_all.py）
  二  →  PC + 手机 NE2210（移动视觉·触控·通知）
  三  →  PC + 手机 + 眼镜 XRGF50（第一人称·无感·TTS）
  万物 →  三体联动·感知涌现·超越各部分之和

设备:
  手机: 158377ff | NE2210 | Android 15 | IP由wireless_config管理
  眼镜: XRGF50 | WiFi ADB 由wireless_config管理

核心场景（万物）:
  scene_1: 眼镜看 → PC AI → 眼镜说   （第一人称AI助手）
  scene_2: 手机屏 → OCR → 眼镜播     （手机→眼镜信息中继）
  scene_3: 通知   → 眼镜播报          （手机通知音频化）
  scene_4: 眼镜触控 → 手机操作        （跨设备遥控）
  scene_5: 三体感知融合报告            （三体状态全景）
"""

import subprocess
import threading
import time
import os
import sys
import json
import re
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Optional

# ─── 路径配置（统一由wireless_config管理） ────────────────────
BASE_DIR   = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
from wireless_config import wm, ADB, GLASS_USB_SERIAL, PHONE_USB_SERIAL as PHONE_ID

# 动态获取（WiFi断重连后地址可能变化）
def _glass_id(): return wm.glass_addr
def _phone_ip(): return wm.phone_ip

GLASS_ID   = wm.glass_addr  # 向后兼容初始值
PHONE_IP   = wm.phone_ip
PHONE_RES  = (1080, 2412)

CAPTURE_DIR = BASE_DIR / "san_lian_captures"
CAPTURE_DIR.mkdir(exist_ok=True)


# ─── ADB 工具 ─────────────────────────────────────────────
def adb(device: str, *args, timeout: int = 15) -> str:
    cmd = [ADB, "-s", device] + list(args)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout, encoding="utf-8", errors="replace")
        return r.stdout.strip()
    except subprocess.TimeoutExpired:
        return ""
    except Exception as e:
        return f"ERROR: {e}"

def adb_raw(device: str, *args, timeout: int = 15) -> bytes:
    """返回原始字节（截图用）"""
    cmd = [ADB, "-s", device] + list(args)
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
        return r.stdout
    except Exception:
        return b""

def all_online() -> dict:
    """检查三体连接状态"""
    out = subprocess.run([ADB, "devices"], capture_output=True,
                         text=True).stdout
    phone_ok = glasses_ok = False
    for line in out.splitlines():
        if PHONE_ID in line and "device" in line and "offline" not in line:
            phone_ok = True
        if _glass_id() in line and "device" in line and "offline" not in line:
            glasses_ok = True
    return {"phone": phone_ok, "glasses": glasses_ok}


# ─── 手机臂 (PhoneArm) ───────────────────────────────────
class PhoneArm:
    """
    二 — PC + 手机
    手机的核心价值: 移动视觉 / 大屏 / 触控 / 通知感知
    NE2210 Android 15, 1080×2412, WiFi IP由wireless_config管理
    """

    DEVICE = PHONE_ID

    def screenshot(self) -> Optional[str]:
        """截取手机屏幕，保存到本地，返回路径"""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        local = str(CAPTURE_DIR / f"phone_{ts}.png")
        data = adb_raw(self.DEVICE, "exec-out", "screencap", "-p")
        if data and len(data) > 1000:
            with open(local, "wb") as f:
                f.write(data)
            return local
        return None

    def ocr(self, img_path: str) -> str:
        """OCR 识别图片文字（优先 RapidOCR，降级 pytesseract）"""
        try:
            from rapidocr_onnxruntime import RapidOCR
            engine = RapidOCR()
            result, _ = engine(img_path)
            if result:
                return "\n".join([line[1] for line in result if line and len(line) > 1])
        except ImportError:
            pass
        try:
            from PIL import Image
            import pytesseract
            img = Image.open(img_path)
            return pytesseract.image_to_string(img, lang="chi_sim+eng")
        except Exception:
            pass
        return ""

    def get_foreground_app(self) -> str:
        """获取当前前台应用
        WiFi ADB安全: 设备端grep过滤避免大输出断连"""
        out = adb(self.DEVICE, "shell",
                  "dumpsys activity activities 2>/dev/null | grep -E 'mResumedActivity|ResumedActivity'")
        for line in out.splitlines():
            m = re.search(r'([a-z][a-z.]+)/[.\w]+', line)
            if m:
                return m.group(1)
        return "unknown"

    def get_notifications(self, limit: int = 5) -> list:
        """获取最近通知摘要
        WiFi ADB安全: 设备端grep过滤避免大输出断连"""
        out = adb(self.DEVICE, "shell",
                  "dumpsys notification --noredact 2>/dev/null | grep -E 'pkg=|tickerText=|text='")
        notifications = []
        pkg_re = re.compile(r'pkg=(\S+)')
        text_re = re.compile(r'(?:tickerText|text)=(.+?)(?:\n|$)')
        current_pkg = ""
        for line in out.splitlines():
            pm = pkg_re.search(line)
            if pm:
                current_pkg = pm.group(1)
            tm = text_re.search(line)
            if tm and current_pkg:
                text = tm.group(1).strip()
                if text and len(text) > 2:
                    notifications.append({"pkg": current_pkg, "text": text})
                    if len(notifications) >= limit:
                        break
        return notifications

    def get_battery(self) -> int:
        out = adb(self.DEVICE, "shell", "dumpsys", "battery")
        for line in out.splitlines():
            if "level:" in line:
                try:
                    return int(line.split(":")[1].strip())
                except ValueError:
                    pass
        return -1

    def tap(self, x: int, y: int):
        """点击手机屏幕"""
        adb(self.DEVICE, "shell", "input", "tap", str(x), str(y))

    def swipe(self, x1: int, y1: int, x2: int, y2: int, ms: int = 300):
        adb(self.DEVICE, "shell", "input", "swipe",
            str(x1), str(y1), str(x2), str(y2), str(ms))

    def input_text(self, text: str):
        adb(self.DEVICE, "shell", "input", "text", text.replace(" ", "%s"))

    def launch_app(self, package: str):
        adb(self.DEVICE, "shell", "monkey", "-p", package,
            "-c", "android.intent.category.LAUNCHER", "1")

    def sense(self) -> dict:
        """手机五感状态"""
        return {
            "online":   PHONE_ID in subprocess.run([ADB, "devices"],
                            capture_output=True, text=True).stdout,
            "battery":  self.get_battery(),
            "app":      self.get_foreground_app(),
            "wifi_ip":  _phone_ip(),
        }


# ─── 眼镜臂 (GlassesArm) ────────────────────────────────
class GlassesArm:
    """
    三 — PC + 手机 + 眼镜
    眼镜的核心价值: 第一人称视角 / 无感交互 / TTS输出
    """

    @property
    def DEVICE(self):
        return _glass_id()

    def __init__(self):
        self._tts_engine = None
        self._zh_voice = None

    def _init_tts(self):
        if self._tts_engine is None:
            try:
                import pyttsx3
                self._tts_engine = pyttsx3.init()
                self._tts_engine.setProperty("rate", 160)
                for v in self._tts_engine.getProperty("voices"):
                    if any(x in v.name.lower() for x in
                           ["zh", "chinese", "huihui", "yaoyao"]):
                        self._zh_voice = v.id
                        break
            except Exception:
                pass

    def speak(self, text: str):
        """TTS 播报到眼镜扬声器"""
        print(f"  [眼镜·说] {text}")
        self._init_tts()
        tmp = str(BASE_DIR / "_sl_tts.wav")
        try:
            if self._tts_engine:
                if self._zh_voice:
                    self._tts_engine.setProperty("voice", self._zh_voice)
                self._tts_engine.save_to_file(text, tmp)
                self._tts_engine.runAndWait()
                adb(self.DEVICE, "push", tmp, "/sdcard/_sl_tts.wav")
                adb(self.DEVICE, "shell", "am", "start",
                    "-a", "android.intent.action.VIEW",
                    "-d", "file:///sdcard/_sl_tts.wav", "-t", "audio/wav",
                    "--grant-read-uri-permission")
        except Exception as e:
            print(f"  [TTS] 失败: {e}")

    def capture(self) -> Optional[str]:
        """眼镜截屏（RayNeo V3无相机App，使用screencap）"""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        remote = "/sdcard/_cap.png"
        adb(self.DEVICE, "shell", "screencap", "-p", remote)
        local = str(CAPTURE_DIR / f"glasses_{ts}.png")
        # adb pull输出到stderr，用subprocess直接处理
        r = subprocess.run([ADB, "-s", self.DEVICE, "pull", remote, local],
                           capture_output=True, text=True, timeout=15)
        if os.path.exists(local) and os.path.getsize(local) > 0:
            return local
        return None

    def get_battery(self) -> int:
        out = adb(self.DEVICE, "shell", "dumpsys", "battery")
        for line in out.splitlines():
            if "level:" in line:
                try:
                    return int(line.split(":")[1].strip())
                except ValueError:
                    pass
        return -1

    def sense(self) -> dict:
        out = subprocess.run([ADB, "devices"], capture_output=True, text=True).stdout
        online = False
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[0] == _glass_id() and parts[1] == "device":
                online = True
                break
        return {
            "online":  online,
            "battery": self.get_battery(),
            "model":   "XRGF50",
            "rom":     "userdebug",
        }


# ─── PC 脑 (PCBrain) ─────────────────────────────────────
class PCBrain:
    """
    道/一 — PC 主脑
    PC 的核心价值: AI 调用 / 算法调度 / 感知聚合
    """

    def tongyi_vision(self, image_path: str, question: str = "用一句话描述图片里有什么") -> str:
        """通义视觉识别"""
        api_key = os.environ.get("DASHSCOPE_API_KEY", "")
        if not api_key:
            return "（需设置 DASHSCOPE_API_KEY）"
        try:
            import base64, urllib.request
            with open(image_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            payload = json.dumps({
                "model": "qwen-vl-plus",
                "input": {"messages": [{"role": "user", "content": [
                    {"image": f"data:image/jpeg;base64,{b64}"},
                    {"text": question}
                ]}]}
            }).encode()
            req = urllib.request.Request(
                "https://dashscope.aliyuncs.com/api/v1/services/aigc/"
                "multimodal-generation/generation",
                data=payload,
                headers={"Authorization": f"Bearer {api_key}",
                         "Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=12) as resp:
                result = json.loads(resp.read())
                return result["output"]["choices"][0]["message"]["content"][0]["text"]
        except Exception as e:
            return f"（AI调用失败: {e}）"

    def ollama_ask(self, prompt: str, model: str = "qwen2.5:7b") -> str:
        """本地 Ollama 问答"""
        try:
            import urllib.request
            payload = json.dumps({
                "model": model, "prompt": prompt, "stream": False
            }).encode()
            req = urllib.request.Request(
                "http://localhost:11434/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read())
                return result.get("response", "").strip()
        except Exception as e:
            return f"（Ollama离线: {e}）"

    def ocr_simple(self, image_path: str) -> str:
        """简单 OCR（优先 RapidOCR）"""
        try:
            from rapidocr_onnxruntime import RapidOCR
            engine = RapidOCR()
            result, _ = engine(image_path)
            if result:
                return "\n".join([line[1] for line in result if line])
        except Exception:
            pass
        return ""


# ─── 三联道主引擎 ─────────────────────────────────────────
class SanLian:
    """
    三联道 — 一生二 二生三 三生万物

    道生一: PC 主脑
    一生二: PC + 手机 = 移动感知延伸
    二生三: PC + 手机 + 眼镜 = 第一人称无感智能
    三生万物: 三体联动涌现，超越各部分之和

    核心联动场景:
      scene_1: 眼镜触发 → 眼镜拍照 → OCR/AI → 眼镜播报
      scene_2: 手机屏幕 → OCR → AI摘要 → 眼镜播报
      scene_3: 手机通知 → 眼镜播报（通知镜转）
      scene_4: 眼镜手势 → 手机操作（跨设备遥控）
      scene_5: 三体全景感知报告
    """

    def __init__(self):
        self.phone   = PhoneArm()
        self.glasses = GlassesArm()
        self.brain   = PCBrain()
        self._running = False

    # ─── 万物场景 ──────────────────────────────────────────

    def scene_1_glasses_see_and_speak(self, question: str = "眼前有什么"):
        """
        场景一: 眼镜看 → PC AI识别 → 眼镜说
        第一人称AI助手: 看到什么，立即知道什么
        """
        print("\n[三联·场景一] 眼镜看 → AI识别 → 眼镜播报")
        self.glasses.speak("正在识别，请稍候")

        photo = self.glasses.capture()
        if not photo:
            # 降级：手机拍照代替
            print("  [降级] 眼镜拍照失败，使用手机截图")
            photo = self.phone.screenshot()
            if not photo:
                self.glasses.speak("拍摄失败")
                return

        # 优先通义，降级 OCR+Ollama
        answer = self.brain.tongyi_vision(photo, question)
        if "需设置" in answer or "失败" in answer:
            # Ollama 降级
            ocr_text = self.brain.ocr_simple(photo)
            if ocr_text.strip():
                prompt = f"图片中OCR识别到以下文字，请一句话总结：{ocr_text[:200]}"
                answer = self.brain.ollama_ask(prompt)
            else:
                answer = "识别完成，内容暂时无法解析"

        print(f"  [AI] {answer}")
        self.glasses.speak(answer[:60])  # 眼镜TTS限60字

    def scene_2_phone_to_glasses(self):
        """
        场景二: 手机屏幕 → OCR → AI摘要 → 眼镜播报
        手机作为眼镜的信息延伸：手机上看到的，眼镜帮你说出来
        """
        print("\n[三联·场景二] 手机屏 → OCR → 眼镜播报")
        self.glasses.speak("读取手机屏幕")

        screenshot = self.phone.screenshot()
        if not screenshot:
            self.glasses.speak("手机截图失败")
            return

        app = self.phone.get_foreground_app()
        ocr_text = self.brain.ocr_simple(screenshot)

        if not ocr_text.strip():
            self.glasses.speak(f"当前手机运行{app.split('.')[-1]}")
            return

        # 用 Ollama 摘要（本地，快速）
        prompt = f"以下是手机{app}应用的屏幕文字，请用不超过20字概括主要内容：\n{ocr_text[:300]}"
        summary = self.brain.ollama_ask(prompt)
        if "Ollama离线" in summary:
            # 降级：直接取前80字
            summary = ocr_text.replace("\n", " ").strip()[:80]

        print(f"  [手机屏] {app}: {summary}")
        self.glasses.speak(summary[:60])

    def scene_3_notify_relay(self):
        """
        场景三: 手机通知 → 眼镜播报
        不看手机，眼镜告诉你重要消息
        """
        print("\n[三联·场景三] 手机通知 → 眼镜播报")
        notifs = self.phone.get_notifications(limit=3)
        if not notifs:
            self.glasses.speak("手机没有新通知")
            return

        for n in notifs[:2]:
            pkg_name = n["pkg"].split(".")[-1]
            text = n["text"][:40]
            msg = f"{pkg_name}：{text}"
            print(f"  [通知] {msg}")
            self.glasses.speak(msg)
            time.sleep(0.5)

    def scene_4_glasses_control_phone(self, action: str = "scroll_down"):
        """
        场景四: 眼镜手势 → 手机操作
        眼镜前滑 → 手机下翻；眼镜单击 → 手机截图
        """
        print(f"\n[三联·场景四] 眼镜指令 → 手机操作: {action}")
        w, h = PHONE_RES

        if action == "scroll_down":
            self.phone.swipe(w//2, h*2//3, w//2, h//3, 400)
            self.glasses.speak("已向下翻页")
        elif action == "scroll_up":
            self.phone.swipe(w//2, h//3, w//2, h*2//3, 400)
            self.glasses.speak("已向上翻页")
        elif action == "home":
            adb(PHONE_ID, "shell", "input", "keyevent", "3")
            self.glasses.speak("已返回主页")
        elif action == "back":
            adb(PHONE_ID, "shell", "input", "keyevent", "4")
            self.glasses.speak("已返回")
        elif action == "screenshot":
            path = self.phone.screenshot()
            self.glasses.speak("手机截图已保存" if path else "截图失败")

    def scene_5_tri_sense(self) -> dict:
        """
        场景五: 三体感知融合报告
        一句话掌握三体状态
        """
        print("\n[三联·场景五] 三体全景感知")
        states = {}

        # 并行感知三体（相忘于江湖：各自独立）
        results = {}
        def sense_phone():
            results["phone"] = self.phone.sense()
        def sense_glasses():
            results["glasses"] = self.glasses.sense()

        t1 = threading.Thread(target=sense_phone, daemon=True)
        t2 = threading.Thread(target=sense_glasses, daemon=True)
        t1.start(); t2.start()
        t1.join(timeout=8); t2.join(timeout=8)

        p = results.get("phone", {})
        g = results.get("glasses", {})

        print(f"  道(PC)   : ✅ 在线")
        print(f"  二(手机) : {'✅' if p.get('online') else '❌'} "
              f"NE2210 电量{p.get('battery', '?')}% "
              f"前台:{p.get('app','?').split('.')[-1]}")
        print(f"  三(眼镜) : {'✅' if g.get('online') else '❌'} "
              f"XRGF50 电量{g.get('battery', '?')}%")

        # 三体状态播报到眼镜
        phone_bat = p.get("battery", -1)
        glass_bat = g.get("battery", -1)
        msg_parts = []
        if phone_bat >= 0:
            msg_parts.append(f"手机{phone_bat}%")
        if glass_bat >= 0:
            msg_parts.append(f"眼镜{glass_bat}%")
        if msg_parts:
            self.glasses.speak("三体已联，" + "，".join(msg_parts))

        return {"phone": p, "glasses": g, "pc": {"online": True}}

    # ─── 联动监听循环 ──────────────────────────────────────

    def wan_wu_run(self):
        """
        三生万物 — 完整三体联动监听
        眼镜手势 → 路由到对应场景

        手势映射（三联版）:
          单击     → 场景一: 眼镜看→AI→眼镜说
          双击     → 场景二: 手机屏→眼镜说
          前滑     → 场景四: 手机下翻
          后滑     → 场景四: 手机上翻
          长按     → 场景五: 三体感知报告
          ActionBtn短按 → 场景三: 通知播报
          ActionBtn长按 → 场景五: 三体报告
        """
        print("\n╔══════════════════════════════════════════════╗")
        print("║  三联道 · 一生二 二生三 三生万物              ║")
        print("║  道生一(PC) → 一生二(+手机) → 二生三(+眼镜)  ║")
        print("╚══════════════════════════════════════════════╝\n")

        status = all_online()
        if not status["glasses"]:
            print("❌ 眼镜未连接，请检查ADB夹具")
            return
        if not status["phone"]:
            print("⚠️  手机未连接，仅眼镜单机模式")

        self.scene_5_tri_sense()
        self.glasses.speak("三联道已启动，万物已通")

        print("\n✅ 三体联动运行中")
        print("  [单击TP]  = 眼镜拍照→AI识别→播报")
        print("  [双击TP]  = 读手机屏幕→眼镜播报")
        print("  [前滑TP]  = 手机下翻页")
        print("  [后滑TP]  = 手机上翻页")
        print("  [长按TP]  = 三体状态报告")
        print("  [ActionBtn] = 播报手机通知")
        print("  按 Ctrl+C 归根\n")

        self._running = True

        # 启动 TP 监听（从眼镜）
        tp_thread = threading.Thread(target=self._tp_loop, daemon=True)
        tp_thread.start()

        # 启动 ActionButton 监听
        btn_thread = threading.Thread(target=self._btn_loop, daemon=True)
        btn_thread.start()

        try:
            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[三联·归根] 三体联动关闭")
            self._running = False
            for p in [getattr(self, '_tp_proc', None), getattr(self, '_btn_proc', None)]:
                if p and p.poll() is None:
                    p.kill()

    def _tp_loop(self):
        """监听眼镜 TP 并路由到三联场景"""
        import subprocess as sp
        proc = sp.Popen(
            [ADB, "-s", _glass_id(), "shell", "getevent", "-l",
             "/dev/input/event3"],
            stdout=sp.PIPE, stderr=sp.PIPE,
            text=True, encoding="utf-8", errors="replace"
        )
        self._tp_proc = proc
        x_start = x_last = None
        t_start = 0.0
        last_tap = 0.0
        THRESH = 300

        for line in proc.stdout:
            if not self._running:
                break
            line = line.strip()
            if "ABS_MT_POSITION_X" in line or "ABS_X" in line:
                try:
                    x = int(line.split()[-1], 16)
                    if x_start is None:
                        x_start = x
                        t_start = time.time()
                    x_last = x
                except (ValueError, IndexError):
                    pass
            elif "BTN_TOUCH" in line and "00000000" in line:
                if x_start is None:
                    continue
                dx = (x_last or x_start) - x_start
                dur = (time.time() - t_start) * 1000
                x_start = x_last = None

                if abs(dx) > THRESH:
                    gesture = "slide_fwd" if dx > 0 else "slide_back"
                elif dur > 600:
                    gesture = "long_press"
                else:
                    now = time.time()
                    gesture = "double_tap" if now - last_tap < 0.4 else "tap"
                    last_tap = now

                threading.Thread(target=self._handle_gesture,
                                 args=(gesture,), daemon=True).start()

    def _btn_loop(self):
        """监听眼镜 ActionButton → 通知播报"""
        import subprocess as sp
        proc = sp.Popen(
            [ADB, "-s", _glass_id(), "shell", "getevent", "-l",
             "/dev/input/event1"],
            stdout=sp.PIPE, stderr=sp.PIPE,
            text=True, encoding="utf-8", errors="replace"
        )
        self._btn_proc = proc
        press_time = 0.0
        for line in proc.stdout:
            if not self._running:
                break
            line = line.strip()
            if "0000aa" in line or "KEY_PROG2" in line:
                if "00000001" in line:
                    press_time = time.time()
                elif "00000000" in line:
                    dur = (time.time() - press_time) * 1000
                    action = "long" if dur > 600 else "short"
                    threading.Thread(target=self._handle_btn,
                                     args=(action,), daemon=True).start()

    def _handle_gesture(self, gesture: str):
        print(f"[三联·手势] {gesture}")
        if gesture == "tap":
            self.scene_1_glasses_see_and_speak()
        elif gesture == "double_tap":
            self.scene_2_phone_to_glasses()
        elif gesture == "slide_fwd":
            self.scene_4_glasses_control_phone("scroll_down")
        elif gesture == "slide_back":
            self.scene_4_glasses_control_phone("scroll_up")
        elif gesture == "long_press":
            self.scene_5_tri_sense()

    def _handle_btn(self, action: str):
        print(f"[三联·按键] ActionButton {action}")
        if action == "short":
            self.scene_3_notify_relay()
        elif action == "long":
            self.scene_5_tri_sense()

    # ─── 快速测试 ─────────────────────────────────────────
    def quick_test(self):
        """快速验证三体联动链路"""
        print("\n[三联道·快速测试]")
        print("1. 检查三体连接...")
        s = all_online()
        print(f"   手机: {'✅' if s['phone'] else '❌'}  眼镜: {'✅' if s['glasses'] else '❌'}")

        print("2. 手机截图...")
        shot = self.phone.screenshot()
        print(f"   {'✅ ' + shot if shot else '❌ 失败'}")

        print("3. 眼镜TTS测试...")
        self.glasses.speak("三联道测试，一生二，二生三，三生万物")
        print("   ✅ TTS已发送")

        print("4. 手机电量...")
        pb = self.phone.get_battery()
        gb = self.glasses.get_battery()
        print(f"   手机: {pb}%  眼镜: {gb}%")
        print("\n✅ 三联道快速测试完成\n")


# ─── CLI 入口 ─────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="三联道 · 一生二 二生三 三生万物")
    parser.add_argument("--run",      action="store_true", help="启动三体联动监听")
    parser.add_argument("--test",     action="store_true", help="快速测试三体链路")
    parser.add_argument("--sense",    action="store_true", help="三体感知报告")
    parser.add_argument("--scene",    type=int, choices=[1,2,3,4,5], help="运行指定场景")
    parser.add_argument("--speak",    type=str, help="眼镜TTS播报")
    parser.add_argument("--phone-shot", action="store_true", help="手机截图+OCR")
    args = parser.parse_args()

    sl = SanLian()

    if args.test:
        sl.quick_test()
    elif args.sense:
        sl.scene_5_tri_sense()
    elif args.speak:
        sl.glasses.speak(args.speak)
    elif args.phone_shot:
        path = sl.phone.screenshot()
        if path:
            print(f"截图: {path}")
            text = sl.brain.ocr_simple(path)
            print(f"OCR: {text[:200] if text else '（无文字）'}")
    elif args.scene == 1:
        sl.scene_1_glasses_see_and_speak()
    elif args.scene == 2:
        sl.scene_2_phone_to_glasses()
    elif args.scene == 3:
        sl.scene_3_notify_relay()
    elif args.scene == 4:
        sl.scene_4_glasses_control_phone()
    elif args.scene == 5:
        sl.scene_5_tri_sense()
    elif args.run:
        sl.wan_wu_run()
    else:
        sl.quick_test()
