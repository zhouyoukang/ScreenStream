"""
抖音×ORS6 实时同步演示 — 端到端管线

链路: 音频源 → librosa节拍检测 → funscript生成 → TCode命令 → ORS6 Hub API

用法:
    # 模式1: 合成节拍演示 (无需外部视频)
    python douyin_sync_demo.py --demo
    
    # 模式2: 本地音频文件
    python douyin_sync_demo.py --audio music.mp3
    
    # 模式3: 抖音视频URL (自动下载+提取音频)
    python douyin_sync_demo.py --url "https://www.douyin.com/video/xxxx"
    
    # 配置
    --hub http://localhost:8086   # ORS6 Hub地址
    --bpm 120                    # 合成演示BPM
    --mode beat                  # beat/onset/hybrid
    --multi                      # 多轴模式
"""

import os, sys, json, time, math, logging, argparse, threading, struct, hashlib, base64, socket
from pathlib import Path
from urllib.parse import quote as url_quote
from urllib.request import urlopen, Request

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname).1s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("douyin_sync")


# ── Hub API Client ──────────────────────────────────────────────

class HubClient:
    """ORS6 Hub HTTP + WebSocket客户端"""
    
    def __init__(self, base_url: str = "http://localhost:8086"):
        self.base = base_url.rstrip("/")
        self._ws_sock = None
        self._ws_connected = False
    
    def health(self) -> dict:
        return self._get("/api/health")
    
    def send_cmd(self, cmd: str) -> dict:
        """通过WebSocket发送命令(低延迟)"""
        if self._ws_connected:
            return self._ws_send({"type": "command", "cmd": cmd})
        return self._get(f"/api/send/{url_quote(cmd)}")
    
    def play_pattern(self, name: str, bpm: int = 60) -> dict:
        return self._get(f"/api/play/{url_quote(name)}/{bpm}")
    
    def stop(self) -> dict:
        return self._get("/api/stop")
    
    def state(self) -> dict:
        return self._get("/api/state")
    
    def connect_ws(self):
        """建立WebSocket持久连接 (用于高频命令发送)"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(self.base)
            host = parsed.hostname or "localhost"
            port = parsed.port or 8086
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((host, port))
            sock.settimeout(5)
            
            # WebSocket handshake
            key = base64.b64encode(os.urandom(16)).decode()
            handshake = (
                f"GET / HTTP/1.1\r\n"
                f"Host: {host}:{port}\r\n"
                f"Upgrade: websocket\r\n"
                f"Connection: Upgrade\r\n"
                f"Sec-WebSocket-Key: {key}\r\n"
                f"Sec-WebSocket-Version: 13\r\n"
                f"\r\n"
            )
            sock.sendall(handshake.encode())
            
            # Read response
            resp = b""
            while b"\r\n\r\n" not in resp:
                resp += sock.recv(4096)
            
            if b"101" in resp:
                self._ws_sock = sock
                self._ws_connected = True
                sock.settimeout(0.1)
                logger.info("WebSocket连接成功 (低延迟模式)")
            else:
                sock.close()
                logger.warning("WebSocket握手失败, 回退HTTP")
        except Exception as e:
            logger.warning(f"WebSocket连接失败: {e}, 回退HTTP")
    
    def close_ws(self):
        if self._ws_sock:
            try:
                self._ws_sock.close()
            except Exception:
                pass
            self._ws_connected = False
    
    def _ws_send(self, data: dict) -> dict:
        """通过WebSocket发送JSON帧"""
        try:
            payload = json.dumps(data).encode("utf-8")
            # Build masked WebSocket frame
            frame = bytearray([0x81])  # text frame, FIN
            length = len(payload)
            if length < 126:
                frame.append(0x80 | length)  # masked
            elif length < 65536:
                frame.append(0x80 | 126)
                frame.extend(struct.pack(">H", length))
            else:
                frame.append(0x80 | 127)
                frame.extend(struct.pack(">Q", length))
            
            mask = os.urandom(4)
            frame.extend(mask)
            frame.extend(bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))
            
            self._ws_sock.sendall(bytes(frame))
            
            # Non-blocking drain any incoming frames
            try:
                self._ws_sock.recv(4096)
            except (socket.timeout, BlockingIOError):
                pass
            
            return {"ok": True}
        except Exception as e:
            self._ws_connected = False
            return {"error": str(e)}
    
    def _get(self, path: str) -> dict:
        try:
            req = Request(self.base + path)
            with urlopen(req, timeout=5) as resp:
                return json.loads(resp.read())
        except Exception as e:
            logger.error(f"Hub API error: {e}")
            return {"error": str(e)}


# ── Audio Utilities ─────────────────────────────────────────────

def generate_synthetic_audio(bpm: float = 120, duration: float = 30.0,
                              output_path: str = None) -> str:
    """生成带节拍的合成音频 (用于测试)"""
    import numpy as np
    import soundfile as sf
    
    sr = 22050
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    
    # 基础节拍 (kick drum)
    beat_interval = 60.0 / bpm
    signal = np.zeros_like(t)
    
    for beat_time in np.arange(0, duration, beat_interval):
        # 合成kick: 短促低频脉冲
        mask = (t >= beat_time) & (t < beat_time + 0.08)
        local_t = t[mask] - beat_time
        kick = np.sin(2 * np.pi * 80 * local_t) * np.exp(-local_t * 40)
        signal[mask] += kick * 0.8
    
    # 添加hi-hat (高频,半拍)
    for hat_time in np.arange(beat_interval / 2, duration, beat_interval):
        mask = (t >= hat_time) & (t < hat_time + 0.03)
        local_t = t[mask] - hat_time
        noise = np.random.randn(mask.sum()) * np.exp(-local_t * 100)
        signal[mask] += noise * 0.3
    
    # 添加bassline (低频旋律)
    bass_freqs = [55, 65, 73, 82]  # A1, C2, D2, E2
    bar_duration = beat_interval * 4
    for bar_start in np.arange(0, duration, bar_duration):
        for i, freq in enumerate(bass_freqs):
            note_start = bar_start + i * beat_interval
            note_end = note_start + beat_interval * 0.8
            mask = (t >= note_start) & (t < note_end)
            local_t = t[mask] - note_start
            bass = np.sin(2 * np.pi * freq * local_t) * np.exp(-local_t * 3)
            signal[mask] += bass * 0.4
    
    # Normalize
    signal = signal / (np.abs(signal).max() + 1e-8) * 0.9
    
    if output_path is None:
        output_path = str(PROJECT_ROOT / "douyin_cache" / "synthetic_beat.wav")
    
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    sf.write(output_path, signal, sr)
    logger.info(f"合成音频: {output_path} ({duration}s, {bpm}BPM)")
    return output_path


def download_douyin_audio(video_url: str, output_dir: str = None) -> str:
    """使用yt-dlp下载抖音视频并提取音频"""
    import yt_dlp
    
    if output_dir is None:
        output_dir = str(PROJECT_ROOT / "douyin_cache")
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    output_template = os.path.join(output_dir, "%(id)s.%(ext)s")
    
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "wav",
            "preferredquality": "192",
        }],
        "quiet": True,
        "no_warnings": True,
    }
    
    logger.info(f"下载视频音频: {video_url}")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=True)
        video_id = info.get("id", "unknown")
        title = info.get("title", "")[:50]
    
    audio_path = os.path.join(output_dir, f"{video_id}.wav")
    if not os.path.exists(audio_path):
        # Try other extensions
        for ext in ["m4a", "mp3", "opus", "webm"]:
            alt = os.path.join(output_dir, f"{video_id}.{ext}")
            if os.path.exists(alt):
                audio_path = alt
                break
    
    logger.info(f"音频已提取: {audio_path} ({title})")
    return audio_path


# ── Funscript → TCode Converter ─────────────────────────────────

def funscript_pos_to_tcode(pos: int, axis: str = "L0") -> int:
    """funscript位置(0-100) → TCode位置(0-9999)"""
    return int(pos / 100.0 * 9999)


def build_tcode_command(positions: dict, interval_ms: int = 16) -> str:
    """构建多轴TCode命令
    
    Args:
        positions: {axis: tcode_position} e.g. {"L0": 9999, "R0": 5000}
        interval_ms: 运动时间
    
    Returns:
        TCode命令字符串 e.g. "L09999I16 R05000I16"
    """
    parts = []
    for axis, pos in positions.items():
        pos = max(0, min(9999, int(pos)))
        parts.append(f"{axis}{pos:04d}I{interval_ms}")
    return " ".join(parts)


# ── Real-time Playback Engine ───────────────────────────────────

class SyncPlayer:
    """实时同步播放器 — 驱动ORS6 Hub"""
    
    def __init__(self, hub: HubClient, update_hz: int = 60):
        self.hub = hub
        self.update_hz = update_hz
        self.interval_ms = int(1000 / update_hz)
        self._running = False
        self._thread = None
        self._start_time = 0
        self._elapsed_ms = 0
        self._stats = {"commands": 0, "errors": 0, "max_latency_ms": 0}
    
    def play_funscript(self, actions_by_axis: dict, duration_sec: float):
        """播放多轴funscript动作序列
        
        Args:
            actions_by_axis: {"L0": [{"at": ms, "pos": 0-100}, ...], "R0": [...]}
            duration_sec: 总时长
        """
        self._running = True
        self._start_time = time.monotonic()
        self._stats = {"commands": 0, "errors": 0, "max_latency_ms": 0}
        
        # 预处理: 为每个轴建立时间索引
        axis_cursors = {}
        for axis, actions in actions_by_axis.items():
            axis_cursors[axis] = {
                "actions": sorted(actions, key=lambda a: a["at"]),
                "cursor": 0,
            }
        
        logger.info(f"▶ 开始播放 ({len(actions_by_axis)}轴, {duration_sec:.1f}s)")
        
        tick = 0
        while self._running:
            loop_start = time.monotonic()
            elapsed_ms = int((loop_start - self._start_time) * 1000)
            self._elapsed_ms = elapsed_ms
            
            if elapsed_ms > duration_sec * 1000:
                break
            
            # 为每个轴查找当前位置
            positions = {}
            for axis, data in axis_cursors.items():
                actions = data["actions"]
                cursor = data["cursor"]
                
                # 推进cursor到当前时间
                while cursor < len(actions) - 1 and actions[cursor + 1]["at"] <= elapsed_ms:
                    cursor += 1
                data["cursor"] = cursor
                
                if cursor >= len(actions) - 1:
                    positions[axis] = funscript_pos_to_tcode(actions[-1]["pos"], axis)
                else:
                    # 在两个动作间线性插值
                    a1 = actions[cursor]
                    a2 = actions[cursor + 1]
                    dt = a2["at"] - a1["at"]
                    if dt > 0:
                        progress = (elapsed_ms - a1["at"]) / dt
                        progress = max(0, min(1, progress))
                        pos = a1["pos"] + (a2["pos"] - a1["pos"]) * progress
                    else:
                        pos = a1["pos"]
                    positions[axis] = funscript_pos_to_tcode(int(pos), axis)
            
            # 构建并发送TCode
            if positions:
                cmd = build_tcode_command(positions, self.interval_ms)
                t0 = time.monotonic()
                result = self.hub.send_cmd(cmd)
                latency = (time.monotonic() - t0) * 1000
                
                self._stats["commands"] += 1
                self._stats["max_latency_ms"] = max(
                    self._stats["max_latency_ms"], latency
                )
                if "error" in result:
                    self._stats["errors"] += 1
                
                # 进度显示 (每秒一次)
                if tick % self.update_hz == 0:
                    progress_pct = elapsed_ms / (duration_sec * 10)
                    pos_str = " ".join(f"{a}:{p}" for a, p in positions.items())
                    logger.info(
                        f"  [{progress_pct:5.1f}%] {elapsed_ms/1000:.1f}s | "
                        f"{pos_str} | lat:{latency:.0f}ms"
                    )
            
            tick += 1
            
            # 精确定时
            elapsed_loop = time.monotonic() - loop_start
            sleep_time = (1.0 / self.update_hz) - elapsed_loop
            if sleep_time > 0:
                time.sleep(sleep_time)
        
        # 归位
        self.hub.send_cmd("D1")
        self._running = False
        
        logger.info(
            f"■ 播放结束 | {self._stats['commands']}命令 | "
            f"{self._stats['errors']}错误 | "
            f"最大延迟:{self._stats['max_latency_ms']:.0f}ms"
        )
        return self._stats
    
    def stop(self):
        self._running = False


# ── Main Pipeline ───────────────────────────────────────────────

def run_sync_pipeline(audio_path: str, hub_url: str = "http://localhost:8086",
                       mode: str = "beat", multi_axis: bool = False,
                       beat_divisor: int = 1):
    """运行完整同步管线
    
    audio → beat_detect → funscript → tcode → hub
    """
    from video_sync.beat_sync import BeatSyncer, BeatSyncConfig
    
    hub = HubClient(hub_url)
    
    # 1. 检查Hub连通性
    health = hub.health()
    if "error" in health:
        logger.error(f"Hub不可达: {hub_url}")
        return None
    logger.info(f"Hub连接OK: {health.get('status')} | "
                f"设备:{health.get('device')} | "
                f"模式数:{health.get('patterns')}")
    
    # 2. 节拍分析
    config = BeatSyncConfig(
        mode=mode,
        beat_divisor=beat_divisor,
        intensity_curve="sine",
        multi_axis=multi_axis,
        min_pos=5,
        max_pos=95,
    )
    syncer = BeatSyncer(config)
    
    # 分析音频特征
    analysis = syncer.analyze_audio(audio_path)
    logger.info(
        f"音频分析: {analysis['duration']:.1f}s | "
        f"{analysis['tempo']:.0f}BPM | "
        f"{analysis['beat_count']}拍 | "
        f"{analysis['onset_count']}onset"
    )
    
    # 3. 生成funscript
    actions_by_axis = {}
    
    if multi_axis:
        result = syncer.generate_multi(audio_path)
        for axis, sync_result in result.results.items():
            fs = sync_result.to_funscript()
            actions_by_axis[axis] = fs["actions"]
            logger.info(f"  {axis}: {len(fs['actions'])}动作")
    else:
        result = syncer.generate(audio_path)
        fs = result.to_funscript()
        actions_by_axis["L0"] = fs["actions"]
        logger.info(f"  L0: {len(fs['actions'])}动作")
    
    # 保存funscript
    cache_dir = PROJECT_ROOT / "douyin_cache"
    cache_dir.mkdir(exist_ok=True)
    base_name = Path(audio_path).stem
    
    if multi_axis:
        result.save_all(str(cache_dir), base_name)
    else:
        result.save(str(cache_dir / f"{base_name}.funscript"))
    
    # 4. 建立WebSocket低延迟连接
    hub.connect_ws()
    
    # 5. 实时播放
    player = SyncPlayer(hub, update_hz=30)
    duration = analysis["duration"]
    
    stats = player.play_funscript(actions_by_axis, duration)
    hub.close_ws()
    
    return {
        "audio": audio_path,
        "tempo": analysis["tempo"],
        "duration": duration,
        "axes": list(actions_by_axis.keys()),
        "total_actions": sum(len(a) for a in actions_by_axis.values()),
        "stats": stats,
    }


# ── Entry Point ─────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="抖音×ORS6 同步演示")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--demo", action="store_true",
                       help="合成节拍演示模式")
    group.add_argument("--audio", type=str,
                       help="本地音频文件路径")
    group.add_argument("--url", type=str,
                       help="抖音视频URL")
    
    parser.add_argument("--hub", default="http://localhost:8086",
                       help="ORS6 Hub地址")
    parser.add_argument("--bpm", type=int, default=120,
                       help="合成演示BPM (--demo模式)")
    parser.add_argument("--duration", type=float, default=20.0,
                       help="合成演示时长秒 (--demo模式)")
    parser.add_argument("--mode", choices=["beat", "onset", "hybrid"],
                       default="beat", help="节拍检测模式")
    parser.add_argument("--multi", action="store_true",
                       help="多轴模式 (低频→L0, 中频→R0, 高频→V0)")
    parser.add_argument("--divisor", type=int, default=1,
                       help="节拍细分 (1=全拍, 2=半拍)")
    
    args = parser.parse_args()
    
    # 获取音频
    if args.demo:
        audio_path = generate_synthetic_audio(
            bpm=args.bpm, duration=args.duration
        )
    elif args.url:
        audio_path = download_douyin_audio(args.url)
    else:
        audio_path = args.audio
        if not os.path.exists(audio_path):
            logger.error(f"文件不存在: {audio_path}")
            sys.exit(1)
    
    # 运行管线
    result = run_sync_pipeline(
        audio_path=audio_path,
        hub_url=args.hub,
        mode=args.mode,
        multi_axis=args.multi,
        beat_divisor=args.divisor,
    )
    
    if result:
        print(f"\n{'='*50}")
        print(f"  同步完成!")
        print(f"  BPM: {result['tempo']:.0f}")
        print(f"  时长: {result['duration']:.1f}s")
        print(f"  轴: {', '.join(result['axes'])}")
        print(f"  动作: {result['total_actions']}")
        print(f"  命令: {result['stats']['commands']}")
        print(f"  错误: {result['stats']['errors']}")
        print(f"  最大延迟: {result['stats']['max_latency_ms']:.0f}ms")
        print(f"{'='*50}")


if __name__ == "__main__":
    main()
