#!/usr/bin/env python3
"""
RayNeo V3 五感引擎 — 以道统之
Device: 841571AC688C360 | XRGF50 | Android 12 userdebug

视觉(Vision):  摄像头帧 → AI场景识别 → 语音播报
听觉(Hearing): 麦克风唤醒("小雷小雷") → 意图理解 → 响应
触觉(Touch):   右镜腿TP(X轴) → 单击/双击/前后滑 → 操作
空间感(IMU):   加速度计/陀螺仪 → 头部姿态 → 意图推断
环境感(Light): 光传感器 → 自适应亮度状态
无感(Wugan):  一切无缝运转，用户无需思考

连接: wireless_config.py 统一管理 (WiFi优先→USB回退)
SDK:  MarsAndroidSDK-v1.0.1 (本目录 SDK/ 子目录)
"""

import subprocess
import threading
import time
import os
import sys
import json
import re
import struct
from pathlib import Path
from datetime import datetime

# ─── 配置（统一由wireless_config管理） ─────────────────────
_PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_PROJECT_DIR))
from wireless_config import wm, ADB

# DEVICE动态获取（WiFi断重连后地址可能变化）
def _get_device() -> str:
    return wm.glass_addr

# 向后兼容：DEVICE作为初始值保留，但所有函数内部使用_get_device()
DEVICE = wm.glass_addr
SDK_DIR = _PROJECT_DIR
CAPTURE_DIR = SDK_DIR / "captures"
CAPTURE_DIR.mkdir(exist_ok=True)

# 输入设备映射（来自 getevent -i 实测）
DEV_TP = "/dev/input/event3"       # cyttsp5_mt — 右镜腿触控板 X:0-1279
DEV_BTN = "/dev/input/event1"      # gpio-keys — ActionButton(0xaa) + 音量键
DEV_HALL = "/dev/input/event0"     # soc:hall_1 — 佩戴检测
DEV_CAPSENSE = [                   # CapSense Ch0-Ch6 — 电容触感
    f"/dev/input/event{i}" for i in range(5, 12)
]

# TP 手势阈值
TP_X_MAX = 1279
TP_SLIDE_THRESH = 300   # 前后滑动阈值(px)
TP_DOUBLE_MS = 400      # 双击间隔(ms)

# ─── ADB 工具函数 ────────────────────────────────────────
def adb(*args, timeout=15) -> str:
    cmd = [ADB, "-s", _get_device()] + list(args)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding='utf-8', errors='replace')
        return r.stdout.strip()
    except subprocess.TimeoutExpired:
        return ""
    except Exception as e:
        return f"ERROR: {e}"

def adb_bg(*args) -> subprocess.Popen:
    cmd = [ADB, "-s", _get_device()] + list(args)
    return subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding='utf-8', errors='replace'
    )

def device_online() -> bool:
    """检查眼镜是否在线（动态地址，支持WiFi断重连）"""
    dev = _get_device()
    out = subprocess.run([ADB, "devices"], capture_output=True, text=True).stdout
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] == dev and parts[1] == "device":
            return True
    # WiFi断开时尝试重连
    if wm.reconnect_glasses():
        dev = _get_device()
        out = subprocess.run([ADB, "devices"], capture_output=True, text=True).stdout
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[0] == dev and parts[1] == "device":
                return True
    return False

# ─── 视觉感知(Vision) ─────────────────────────────────────
class VisionSense:
    """
    摄像头感知：screencap截屏 → 本地分析
    RayNeo V3 开发版ROM无相机App，直接使用screencap
    """

    def capture_photo(self) -> str | None:
        """截屏并拉取到本地，返回本地路径"""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        remote = "/sdcard/_cap.png"
        local_path = str(CAPTURE_DIR / f"cap_{ts}.png")

        adb("shell", "screencap", "-p", remote)
        # adb pull输出到stderr，用subprocess直接处理
        r = subprocess.run([ADB, "-s", _get_device(), "pull", remote, local_path],
                           capture_output=True, text=True, timeout=15)
        if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
            adb("shell", "rm", remote)
            print(f"  [视] 截屏保存: {local_path}")
            return local_path

        print("  [视] 截屏失败")
        return None

    def _find_latest_photo(self) -> str | None:
        """在多个DCIM目录中查找最新照片"""
        search_dirs = ["/sdcard/DCIM/Camera", "/sdcard/DCIM",
                       "/sdcard/Pictures", "/sdcard/rayneo"]
        for d in search_dirs:
            out = adb("shell", "ls", "-t", d, "2>/dev/null")
            if out and "No such" not in out:
                for f in out.splitlines():
                    f = f.strip()
                    if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                        return f"{d}/{f}"
        return None

    def get_latest_capture(self) -> str | None:
        """获取设备上最新的图片"""
        out = adb("shell", "ls", "-t", "/sdcard/DCIM/Camera/", "2>/dev/null")
        if out:
            lines = [l.strip() for l in out.splitlines() if l.strip()]
            if lines:
                return f"/sdcard/DCIM/Camera/{lines[0]}"
        return None


# ─── 触觉感知(Touch) ─────────────────────────────────────
class TouchSense:
    """
    右镜腿TP手势识别
    硬件: cyttsp5_mt (/dev/input/event3)
    X轴: 0(前端) → 1279(后端)，Y轴固定
    手势: tap(单击) / double_tap(双击) / slide_fwd(前滑) / slide_back(后滑) / long_press(长按)
    """

    def __init__(self, on_gesture):
        self.on_gesture = on_gesture
        self.running = False
        self._proc = None
        self._x_start = None
        self._x_last = None
        self._last_tap_time = 0
        self._touch_start_time = 0

    def start(self):
        self.running = True
        t = threading.Thread(target=self._loop, daemon=True, name="TouchSense")
        t.start()
        print("[触] TP监听已启动 (event3 cyttsp5_mt)")

    def stop(self):
        self.running = False
        if self._proc:
            try:
                self._proc.kill()
            except OSError:
                pass
            self._proc = None

    def _loop(self):
        self._proc = adb_bg("shell", "getevent", "-l", DEV_TP)
        for line in self._proc.stdout:
            if not self.running:
                break
            line = line.strip()
            # X坐标跟踪
            if "ABS_MT_POSITION_X" in line or "ABS_X" in line:
                try:
                    x = int(line.split()[-1], 16)
                    if self._x_start is None:
                        self._x_start = x
                        self._touch_start_time = time.time()
                    self._x_last = x
                except (ValueError, IndexError):
                    pass
            # 触摸抬起 / 同步帧
            elif "BTN_TOUCH" in line and "00000000" in line:
                self._process_gesture()
        if self._proc:
            self._proc.wait()
            self._proc = None

    def _process_gesture(self):
        if self._x_start is None:
            return
        now = time.time()
        dx = (self._x_last or self._x_start) - self._x_start
        duration_ms = (now - self._touch_start_time) * 1000

        if abs(dx) > TP_SLIDE_THRESH:
            # 滑动手势
            gesture = "slide_fwd" if dx > 0 else "slide_back"
        elif duration_ms > 600:
            gesture = "long_press"
        else:
            # 单击 / 双击判断
            if now - self._last_tap_time < TP_DOUBLE_MS / 1000.0:
                gesture = "double_tap"
            else:
                gesture = "tap"
            self._last_tap_time = now

        self._x_start = None
        self._x_last = None
        print(f"  [触] 手势: {gesture} (dx={dx:.0f}px, dur={duration_ms:.0f}ms)")
        self.on_gesture(gesture)


# ─── 空间感(IMU) ──────────────────────────────────────────
class IMUSense:
    """
    头部姿态感知: STMicro lsm6dsr 加速度计+陀螺仪
    动作: nod_down(低头→拍照), nod_up(抬头→提问), shake(摇头→取消)
    数据源优先级: sysfs IIO > dumpsys sensorservice
    """

    NOD_THRESHOLD = 3000      # Y轴变化量触发点头 (raw units)
    SHAKE_THRESHOLD = 2500    # X轴变化量触发摇头
    SHAKE_MIN_COUNT = 3       # 连续方向变化次数判定摇头
    GESTURE_COOLDOWN = 0.8    # 手势去抖间隔(秒)

    def __init__(self, on_motion=None):
        self.on_motion = on_motion
        self.running = False
        self._proc = None
        self._prev_ax = 0.0
        self._prev_ay = 0.0
        self._prev_az = 0.0
        self._shake_count = 0
        self._shake_dir = 0
        self._last_gesture_time = 0
        self._iio_path = None

    def start(self):
        self.running = True
        t = threading.Thread(target=self._loop, daemon=True, name="IMUSense")
        t.start()
        print("[空] IMU监听已启动 (lsm6dsr Accelerometer/Gyroscope)")

    def stop(self):
        self.running = False
        if self._proc:
            try:
                self._proc.kill()
            except OSError:
                pass
            self._proc = None

    def _loop(self):
        """IMU数据采集主循环 — 自动选择最优数据源"""
        self._iio_path = self._find_imu_iio()
        if self._iio_path:
            print(f"  [空] IMU数据源: sysfs IIO ({self._iio_path})")
            self._loop_iio()
        else:
            print("  [空] IMU数据源: dumpsys sensorservice (fallback)")
            self._loop_sensorservice()

    def _find_imu_iio(self) -> str | None:
        """查找LSM6DSR的IIO sysfs设备路径"""
        out = adb("shell", "ls", "/sys/bus/iio/devices/", "2>/dev/null")
        if not out or "No such" in out or "ERROR" in out:
            return None
        for dev in out.split():
            path = f"/sys/bus/iio/devices/{dev}"
            name = adb("shell", "cat", f"{path}/name", "2>/dev/null")
            if name and "lsm6ds" in name.lower():
                return path
            # fallback: name不可读时检查是否有加速度计原始数据文件
            check = adb("shell", "ls", f"{path}/in_accel_x_raw", "2>/dev/null")
            if check and "No such" not in check:
                return path
        return None

    def _loop_iio(self):
        """通过sysfs IIO持续读取加速度计原始数据 (单ADB会话)"""
        p = self._iio_path
        cmd = (f"while true; do "
               f"cat {p}/in_accel_x_raw {p}/in_accel_y_raw {p}/in_accel_z_raw "
               f"2>/dev/null; echo '---'; sleep 0.1; done")
        self._proc = adb_bg("shell", cmd)
        buf = []
        for line in self._proc.stdout:
            if not self.running:
                break
            line = line.strip()
            if line == '---':
                if len(buf) >= 3:
                    try:
                        self._process_accel(
                            float(buf[0]), float(buf[1]), float(buf[2]))
                    except (ValueError, IndexError):
                        pass
                buf = []
            elif line:
                buf.append(line)
        if self._proc:
            self._proc.wait()
            self._proc = None

    def _loop_sensorservice(self):
        """通过dumpsys sensorservice周期性采样 (fallback)
        注意: WiFi ADB下完整dumpsys输出100KB+会导致协议断连，
        在设备端用grep过滤，只传回accel相关行（~100B）"""
        while self.running:
            out = adb("shell",
                      "dumpsys sensorservice 2>/dev/null | grep -i 'accel.*last\\|accel.*value\\|last.*accel'",
                      timeout=5)
            for line in out.splitlines():
                ll = line.lower()
                if "accel" in ll and ("last" in ll or "value" in ll):
                    m = re.search(
                        r'[-+]?\d+\.?\d*\s*,\s*[-+]?\d+\.?\d*\s*,\s*'
                        r'[-+]?\d+\.?\d*', line)
                    if m:
                        try:
                            vals = [float(v.strip())
                                    for v in m.group().split(',')]
                            if len(vals) >= 3:
                                self._process_accel(*vals[:3])
                        except ValueError:
                            pass
                        break
            time.sleep(0.3)

    def _process_accel(self, ax: float, ay: float, az: float):
        """从加速度数据检测头部手势"""
        now = time.time()
        if now - self._last_gesture_time < self.GESTURE_COOLDOWN:
            self._prev_ax, self._prev_ay, self._prev_az = ax, ay, az
            return

        dy = ay - self._prev_ay
        dx = ax - self._prev_ax

        # 点头检测: Y轴大幅变化
        if abs(dy) > self.NOD_THRESHOLD:
            gesture = "nod_down" if dy > 0 else "nod_up"
            print(f"  [空] 头部动作: {gesture} (dy={dy:.0f})")
            if self.on_motion:
                self.on_motion(gesture)
            self._last_gesture_time = now
            self._shake_count = 0
        # 摇头检测: X轴反复方向变化
        elif abs(dx) > self.SHAKE_THRESHOLD:
            cur_dir = 1 if dx > 0 else -1
            if cur_dir != self._shake_dir and self._shake_dir != 0:
                self._shake_count += 1
            self._shake_dir = cur_dir
            if self._shake_count >= self.SHAKE_MIN_COUNT:
                print(f"  [空] 头部动作: shake (count={self._shake_count})")
                if self.on_motion:
                    self.on_motion("shake")
                self._last_gesture_time = now
                self._shake_count = 0
        else:
            if now - self._last_gesture_time > 1.0:
                self._shake_count = 0
                self._shake_dir = 0

        self._prev_ax, self._prev_ay, self._prev_az = ax, ay, az


# ─── 听觉感知(Hearing) ────────────────────────────────────
class HearingSense:
    """
    语音唤醒监听: com.rayneo.aispeech
    唤醒词: "小雷小雷"
    广播: com.rayneo.aispeech.wakeup
    """

    def __init__(self, on_wakeup):
        self.on_wakeup = on_wakeup
        self.running = False
        self._proc = None

    def start(self):
        self.running = True
        t = threading.Thread(target=self._loop, daemon=True, name="HearingSense")
        t.start()
        print("[听] 语音唤醒监听已启动 (com.rayneo.aispeech)")

    def stop(self):
        self.running = False
        if self._proc:
            try:
                self._proc.kill()
            except OSError:
                pass
            self._proc = None

    def _loop(self):
        self._proc = adb_bg("shell", "logcat", "-s",
                            "RayneoAISpeech:V", "VoiceAssist:V",
                            "HotwordEnrollment:V", "*:S")
        for line in self._proc.stdout:
            if not self.running:
                break
            line_lower = line.lower()
            if ("wakeup" in line_lower or "wake_up" in line_lower
                    or "小雷" in line or "hotword" in line_lower):
                print(f"  [听] 唤醒检测: {line.strip()[:80]}")
                self.on_wakeup(line.strip())
        if self._proc:
            self._proc.wait()
            self._proc = None


# ─── ActionButton 监听 ────────────────────────────────────
class ButtonSense:
    """
    右镜腿物理按键: gpio-keys /dev/input/event1
    KEY 0x00aa = ActionButton (短按/长按)
    """

    def __init__(self, on_btn):
        self.on_btn = on_btn
        self.running = False
        self._proc = None
        self._press_time = 0

    def start(self):
        self.running = True
        t = threading.Thread(target=self._loop, daemon=True, name="ButtonSense")
        t.start()
        print("[触] ActionButton监听已启动 (event1 gpio-keys)")

    def stop(self):
        self.running = False
        if self._proc:
            try:
                self._proc.kill()
            except OSError:
                pass
            self._proc = None

    def _loop(self):
        self._proc = adb_bg("shell", "getevent", "-l", DEV_BTN)
        for line in self._proc.stdout:
            if not self.running:
                break
            line = line.strip()
            if "KEY_PROG2" in line or "00000000aa" in line or "KEY_0x0aa" in line or "0000aa" in line:
                if "00000001" in line:   # DOWN
                    self._press_time = time.time()
                    print("  [触] ActionButton 按下")
                elif "00000000" in line:  # UP
                    dur = (time.time() - self._press_time) * 1000
                    action = "long" if dur > 600 else "short"
                    print(f"  [触] ActionButton {action}按 ({dur:.0f}ms)")
                    self.on_btn(action)
        if self._proc:
            self._proc.wait()
            self._proc = None


# ─── 麦克风感知(Mic) ────────────────────────────────────────
class MicSense:
    """
    麦克风音频采集: 3×MEMS麦克风阵列 via ADB
    采集方式: tinycap (原生) > screenrecord (fallback)
    """

    def __init__(self):
        self._has_tinycap = None

    def _check_tinycap(self) -> bool:
        """检查设备上tinycap是否可用"""
        if self._has_tinycap is None:
            out = adb("shell", "which", "tinycap", "2>/dev/null")
            self._has_tinycap = bool(out and "tinycap" in out)
        return self._has_tinycap

    def _find_capture_device(self) -> int:
        """自动探测可用的PCM捕获设备号"""
        out = adb("shell", "ls", "/dev/snd/", "2>/dev/null")
        if not out:
            return 0
        devs = sorted(int(m.group(1)) for m in re.finditer(r'pcmC0D(\d+)c', out))
        return devs[0] if devs else 0

    def record(self, duration: int = 5) -> str | None:
        """录制眼镜麦克风音频，返回本地文件路径
        注意: RayNeo V3的PCM设备由AISpeech服务独占，
              tinycap需su提权且需正确的设备号(非0)
        """
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        remote_wav = f"/sdcard/_mic_{ts}.wav"
        local_wav = str(CAPTURE_DIR / f"mic_{ts}.wav")

        if self._check_tinycap():
            dev = self._find_capture_device()
            print(f"  [听] tinycap录音 {duration}秒 (card=0, device={dev})...")
            # 优先su提权（userdebug ROM），shell用户无audio组权限
            adb("shell", "su", "0", "tinycap", remote_wav,
                "-D", "0", "-d", str(dev), "-c", "1",
                "-r", "16000", "-b", "16", "-T", str(duration),
                timeout=duration + 5)
        else:
            print(f"  [听] tinycap不可用，录音跳过")
            return None

        pull = adb("pull", remote_wav, local_wav, timeout=10)
        if "pulled" in pull or os.path.exists(local_wav):
            size = os.path.getsize(local_wav) if os.path.exists(local_wav) else 0
            if size <= 44:
                print(f"  [听] 录音为空 ({size}B) — PCM设备可能被AISpeech占用")
                adb("shell", "rm", remote_wav)
                return None
            print(f"  [听] 录音保存: {local_wav} ({size} bytes)")
            adb("shell", "rm", remote_wav)
            return local_wav
        print(f"  [听] 录音失败: {pull}")
        return None


# ─── 环境感(Light) ────────────────────────────────────────
class EnvSense:
    """环境光传感器: stk_stk3x3x"""

    def get_light(self) -> float:
        """读取当前光照强度
        WiFi ADB安全: 设备端grep过滤，避免100KB+输出导致协议断连"""
        out = adb("shell",
                  "dumpsys sensorservice 2>/dev/null | grep -i 'light.*value\\|light.*last'")
        for line in out.splitlines():
            if "light" in line.lower() and ("value" in line.lower() or "last" in line.lower()):
                try:
                    m = re.search(r'value[=:\s]+([0-9.]+)', line)
                    if m:
                        return float(m.group(1))
                except (ValueError, AttributeError):
                    pass
        return -1.0

    def is_worn(self) -> bool:
        """通过Hall传感器检测是否佩戴"""
        out = adb("shell", "getevent", "-c", "1", DEV_HALL, "2>/dev/null")
        return "value" in out.lower() or len(out.strip()) > 0


# ─── TTS 语音回馈 ─────────────────────────────────────────
class TTSFeedback:
    """
    语音播报: 优先使用 Android TTS 广播，备用 PC 生成+推送播放
    """

    def __init__(self):
        self._pyttsx3_engine = None
        self._zh_voice_id = None
        self._init_tts()

    def _init_tts(self):
        """初始化 pyttsx3 引擎，找中文语音"""
        try:
            import pyttsx3
            self._pyttsx3_engine = pyttsx3.init()
            self._pyttsx3_engine.setProperty('rate', 160)
            for v in self._pyttsx3_engine.getProperty('voices'):
                vname = v.name.lower()
                if any(x in vname for x in ['zh', 'chinese', 'huihui', 'yaoyao', 'kangkang']):
                    self._zh_voice_id = v.id
                    print(f"  [TTS] 中文语音: {v.name}")
                    break
        except Exception as e:
            print(f"  [TTS] pyttsx3初始化失败: {e}")

    def _play_on_glasses(self, remote_path: str):
        """在眼镜上播放音频 — Android 12兼容多策略"""
        # Strategy 1: am start (shell UID不受FileUriExposedException限制)
        result = adb("shell", "am", "start", "-a", "android.intent.action.VIEW",
                     "-d", f"file://{remote_path}", "-t", "audio/wav",
                     "--grant-read-uri-permission")
        if "Error" not in result and "Exception" not in result:
            return
        # Strategy 2: content:// via MediaStore
        adb("shell", "am", "broadcast", "-a",
            "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
            "-d", f"file://{remote_path}")
        time.sleep(0.5)
        result = adb("shell", "content", "query", "--uri",
                     "content://media/external/audio/media",
                     "--projection", "_id",
                     "--where", f"_data='{remote_path}'")
        if "Row:" in result:
            m = re.search(r'_id=(\d+)', result)
            if m:
                content_uri = f"content://media/external/audio/media/{m.group(1)}"
                adb("shell", "am", "start", "-a",
                    "android.intent.action.VIEW",
                    "-d", content_uri, "-t", "audio/wav")
                return
        # Strategy 3: cmd media_session
        adb("shell", "cmd", "media_session", "dispatch", "play")

    def speak(self, text: str):
        """播放语音 — PC生成推送到眼镜扬声器"""
        print(f"  [无感] TTS: {text}")
        tmp_wav = str(SDK_DIR / "_tts.wav")
        try:
            if self._pyttsx3_engine:
                if self._zh_voice_id:
                    self._pyttsx3_engine.setProperty('voice', self._zh_voice_id)
                self._pyttsx3_engine.save_to_file(text, tmp_wav)
                self._pyttsx3_engine.runAndWait()
                adb("push", tmp_wav, "/sdcard/_tts.wav")
                self._play_on_glasses("/sdcard/_tts.wav")
            else:
                print("  [TTS] 无可用引擎")
        except Exception as e:
            print(f"  [TTS] 播放失败: {e}")

    def beep(self):
        """短促提示音 (100ms 正弦波)"""
        try:
            import wave, array, math
            tmp = str(SDK_DIR / "_beep.wav")
            rate, dur = 44100, 0.12
            n = int(rate * dur)
            data = array.array('h', [int(28000 * math.sin(2*math.pi*880*i/rate)) for i in range(n)])
            with wave.open(tmp, 'w') as wf:
                wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(rate)
                wf.writeframes(data.tobytes())
            adb("push", tmp, "/sdcard/_beep.wav")
            self._play_on_glasses("/sdcard/_beep.wav")
        except Exception as e:
            print(f"  [TTS] beep失败: {e}")


# ─── 五感主引擎 ───────────────────────────────────────────
class RayNeoFiveSenses:
    """
    道之平衡: 无为而治
    用户无需操作，眼镜自知其意
    低头→拍照识物  |  单击→问答  |  前滑→下一页  |  后滑→上一页
    长按→打开AI    |  双击→截屏  |  唤醒词→语音  |  抬头→反馈
    """

    def __init__(self):
        self.tts = TTSFeedback()
        self.vision = VisionSense()
        self.env = EnvSense()
        self.mic = MicSense()
        self.touch = TouchSense(self.on_touch)
        self.button = ButtonSense(self.on_button)
        self.hearing = HearingSense(self.on_wakeup)
        self.imu = IMUSense(self.on_motion)
        self.state = "idle"  # idle / listening / capturing / responding

    # ─── 手势响应 ─────────────────────────────────────────
    def on_touch(self, gesture: str):
        """TP手势处理"""
        if gesture == "tap":
            self._action_capture_and_describe()
        elif gesture == "double_tap":
            self._action_ask_ai("眼前是什么情况？请简短说明")
        elif gesture == "slide_fwd":
            self.tts.speak("向前")
        elif gesture == "slide_back":
            self.tts.speak("向后")
        elif gesture == "long_press":
            self._action_status_report()

    def on_button(self, action: str):
        """ActionButton物理按键"""
        if action == "short":
            self._action_capture_and_describe()
        elif action == "long":
            self._action_status_report()

    def on_wakeup(self, detail: str):
        """语音唤醒响应"""
        self.state = "listening"
        self.tts.speak("我在，请说")

    def on_motion(self, gesture: str):
        """IMU头部动作响应"""
        if gesture == "nod_down":
            self._action_capture_and_describe()
        elif gesture == "nod_up":
            self._action_ask_ai("请简要总结眼前内容")
        elif gesture == "shake":
            self.tts.speak("已取消")
            self.state = "idle"

    # ─── 核心动作 ─────────────────────────────────────────
    def _action_capture_and_describe(self):
        """拍照并通过AI描述场景"""
        if self.state != "idle":
            return
        self.state = "capturing"
        self.tts.speak("正在拍照")
        photo = self.vision.capture_photo()
        if photo:
            self.tts.speak("照片已保存")
            # TODO: 接入通义Vision API进行场景理解
            self._tongyi_vision(photo)
        else:
            self.tts.speak("拍照失败")
        self.state = "idle"

    def _action_ask_ai(self, prompt: str):
        """发起AI问答 — 通义千问文本API"""
        self.tts.speak("正在思考")
        api_key = os.environ.get("DASHSCOPE_API_KEY", "")
        if not api_key:
            self.tts.speak("请设置通义API密钥")
            return
        try:
            payload = json.dumps({
                "model": "qwen-turbo",
                "input": {"messages": [
                    {"role": "system", "content": "用不超过30字简洁回答"},
                    {"role": "user", "content": prompt}
                ]}
            }).encode()
            import urllib.request
            req = urllib.request.Request(
                "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation",
                data=payload,
                headers={"Authorization": f"Bearer {api_key}",
                         "Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
                text = result["output"]["choices"][0]["message"]["content"]
                self.tts.speak(text[:60])
        except Exception as e:
            print(f"  [听] AI问答失败: {e}")
            self.tts.speak("暂时无法回答")

    def _action_status_report(self):
        """状态报告"""
        battery = self._get_battery()
        light = self.env.get_light()
        worn = self.env.is_worn()
        msg = f"电量{battery}%"
        if light >= 0:
            msg += f"，光照{light:.0f}勒克斯"
        if not worn:
            msg += "，未佩戴"
        self.tts.speak(msg)

    def _tongyi_vision(self, photo_path: str):
        """通义Vision API场景理解（需配置API Key）"""
        api_key = os.environ.get("DASHSCOPE_API_KEY", "")
        if not api_key:
            self.tts.speak("请设置通义API密钥")
            return
        try:
            import base64
            with open(photo_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            import urllib.request
            payload = json.dumps({
                "model": "qwen-vl-plus",
                "input": {"messages": [{
                    "role": "user",
                    "content": [
                        {"image": f"data:image/jpeg;base64,{b64}"},
                        {"text": "用一句话描述这张图片里有什么"}
                    ]
                }]}
            }).encode()
            req = urllib.request.Request(
                "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
                data=payload,
                headers={"Authorization": f"Bearer {api_key}",
                         "Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
                text = result["output"]["choices"][0]["message"]["content"][0]["text"]
                self.tts.speak(text)
        except Exception as e:
            print(f"  [视] 通义API错误: {e}")
            self.tts.speak("识别失败，请稍后重试")

    def _get_battery(self) -> int:
        """获取电量"""
        out = adb("shell", "dumpsys", "battery")
        for line in out.splitlines():
            if "level:" in line:
                try:
                    return int(line.split(":")[1].strip())
                except (ValueError, IndexError):
                    pass
        return -1

    # ─── 主循环 ───────────────────────────────────────────
    def sense(self):
        """读取单次全感知状态报告"""
        print("\n═══ RayNeo V3 五感状态 ═══")
        print(f"设备: {_get_device()}")
        print(f"在线: {device_online()}")
        print(f"电量: {self._get_battery()}%")
        print(f"佩戴: {self.env.is_worn()}")
        print(f"光照: {self.env.get_light()}")
        print(f"AISpeech: {adb('shell', 'pm', 'list', 'packages', 'com.rayneo.aispeech')}")
        print("═══════════════════════════\n")

    def run(self):
        """启动五感监听循环"""
        print("\n╔══════════════════════════════╗")
        print("║  RayNeo V3 五感引擎 · 以道统之  ║")
        print("╚══════════════════════════════╝\n")

        if not device_online():
            print("❌ 设备未连接，请检查ADB夹具")
            sys.exit(1)

        self.sense()

        # 启动各感知线程
        self.touch.start()
        self.button.start()
        self.hearing.start()
        self.imu.start()

        print("\n✅ 五感引擎运行中")
        print("手势: [单击]=拍照识别 [双击]=AI问答 [前滑]=下一 [后滑]=上一 [长按]=状态")
        print("按键: [短按]=拍照  [长按]=状态报告")
        print("头部: [低头]=拍照  [抬头]=提问  [摇头]=取消")
        print("语音: 说「小雷小雷」唤醒")
        print("按 Ctrl+C 退出\n")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[五感引擎关闭]")
            self.touch.stop()
            self.button.stop()
            self.hearing.stop()
            self.imu.stop()


# ─── CLI 入口 ─────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="RayNeo V3 五感引擎")
    parser.add_argument("--sense", action="store_true", help="单次感知状态报告")
    parser.add_argument("--run", action="store_true", help="启动五感监听")
    parser.add_argument("--photo", action="store_true", help="拍照一次")
    parser.add_argument("--speak", type=str, help="播报语音")
    parser.add_argument("--battery", action="store_true", help="查看电量")
    parser.add_argument("--record", type=int, nargs='?', const=5, help="录音N秒(默认5)")
    parser.add_argument("--install", action="store_true", help="安装SDK Sample APK")
    args = parser.parse_args()

    engine = RayNeoFiveSenses()

    if args.sense:
        engine.sense()
    elif args.photo:
        print("[视] 拍照中...")
        path = engine.vision.capture_photo()
        print(f"[视] 结果: {path}")
    elif args.speak:
        engine.tts.speak(args.speak)
    elif args.battery:
        print(f"电量: {engine._get_battery()}%")
    elif args.record is not None:
        path = engine.mic.record(duration=args.record)
        print(f"录音: {path}")
    elif args.install:
        sdk = _PROJECT_DIR / "SDK"
        apk = sdk / "MarsSpeech-V2025.06.27.16-release-cn-20250627162035-9d999044.apk"
        print(f"安装: {apk.name}")
        print(adb("install", "-r", str(apk)))
    elif args.run:
        engine.run()
    else:
        # 默认: 状态报告
        engine.sense()
        print("\n使用 --run 启动完整五感引擎")
        print("使用 --help 查看所有选项")
