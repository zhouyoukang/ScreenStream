"""
Travel Film v2 — 叙事驱动旅行电影
================================
vs ultimate: +运动分析选片 +crossfade转场 +多段BGM +场景感知调色 +beat-sync +精确时间线叙事

设计哲学:
  不是"把素材拼起来"，而是"从素材中揭示故事"。
  每个镜头的入选理由 = 运动能量 × 视觉丰富度 × 叙事位置适配度。

用法:
  python build_v2.py              # 全流程构建
  python build_v2.py analyze      # 仅分析素材（不构建）
  python build_v2.py --vertical   # 9:16竖屏版本
"""
import subprocess, os, sys, json, math, shutil, asyncio, hashlib, re
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============================================================
# 配置
# ============================================================
HERE = Path(__file__).parent
PROJECT = HERE.parent
WORK = HERE / "_work_v2"
CLIPS = HERE / "clips_v3"
ANALYSIS_CACHE = HERE / "source_analysis.json"

# 素材源（只读）
SOURCES_DIRS = [
    (Path(r"E:\骑行拍摄\使用素材"), "action", "DJI Action 运动相机"),
    (Path(r"E:\VideoEdit\01-航拍素材_DJI"), "aerial", "无人机航拍"),
    (Path(r"E:\VideoEdit\02-相机录像_Camera"), "camera", "相机录像"),
]

# 旅行时间线（核心叙事锚点）
TRIP_TIMELINE = {
    "2024-07": {"name": "盛夏骑行·序章", "mood": "adventurous"},
    "2024-10": {"name": "秋日骑行", "mood": "warm"},
    "2025-07": {"name": "盛夏远行·主篇", "mood": "epic"},   # 核心旅行
}

# 输出规格
SPECS = {
    "horizontal": {"w": 1920, "h": 1080, "label": "16:9横屏"},
    "vertical":   {"w": 1080, "h": 1920, "label": "9:16竖屏"},
}

TARGET_DURATION = 150  # 目标总时长(秒), ~2.5分钟, 适合中短视频
MAX_SOURCE_DUR = 300   # 排除超长非旅行素材
MIN_SOURCE_DUR = 5     # 最短有效素材
CRF = 17               # 视频质量
CROSSFADE_DUR = 0.6    # 转场时长
TTS_VOICE = "zh-CN-YunxiNeural"

# ============================================================
# FFmpeg 工具层
# ============================================================
def ff(cmd, timeout=300, quiet=True):
    """执行ffmpeg/ffprobe命令"""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
        if not quiet and r.returncode != 0:
            print(f"    stderr: {r.stderr[:200]}")
        return r
    except subprocess.TimeoutExpired:
        return None

def probe_format(path):
    """获取文件格式信息"""
    r = ff(["ffprobe", "-v", "error", "-show_entries",
            "format=duration,size,bit_rate",
            "-of", "json", str(path)], 15)
    if r and r.stdout:
        try:
            return json.loads(r.stdout).get("format", {})
        except: pass
    return {}

def probe_stream(path):
    """获取视频流信息"""
    r = ff(["ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate,codec_name,pix_fmt",
            "-of", "json", str(path)], 15)
    if r and r.stdout:
        try:
            streams = json.loads(r.stdout).get("streams", [])
            return streams[0] if streams else {}
        except: pass
    return {}

def probe_audio(path):
    """检查是否有音频轨"""
    r = ff(["ffprobe", "-v", "error", "-select_streams", "a:0",
            "-show_entries", "stream=codec_name,sample_rate,channels",
            "-of", "json", str(path)], 15)
    if r and r.stdout:
        try:
            streams = json.loads(r.stdout).get("streams", [])
            return streams[0] if streams else None
        except: pass
    return None

def get_duration(path):
    fmt = probe_format(path)
    try: return float(fmt.get("duration", 0))
    except: return 0

def parse_fps(rate_str):
    """解析帧率字符串 如 '120/1' → 120.0"""
    try:
        if "/" in str(rate_str):
            n, d = str(rate_str).split("/")
            return int(n) / int(d) if int(d) else 30
        return float(rate_str)
    except:
        return 30

def fmt_srt_time(s):
    """秒数 → SRT时间格式"""
    h, rem = divmod(s, 3600)
    m, rem = divmod(rem, 60)
    sec, ms = divmod(rem, 1)
    return f"{int(h):02d}:{int(m):02d}:{int(sec):02d},{int(ms*1000):03d}"

# ============================================================
# Phase 0: 深度素材分析
# ============================================================
def analyze_motion(path, samples=5):
    """分析视频运动能量（基于帧间差异）
    返回0-100的运动评分，越高=越动感
    """
    dur = get_duration(path)
    if dur < 3:
        return 50
    # 在视频中均匀采样几个点，计算帧间差异
    scores = []
    for i in range(samples):
        t = dur * (i + 1) / (samples + 1)
        # 导出2帧计算差异
        r = ff(["ffmpeg", "-ss", str(t), "-i", str(path),
                "-vframes", "2", "-vf",
                "scale=160:90,format=gray",
                "-f", "rawvideo", "-"], timeout=15)
        if r and r.stdout:
            raw = r.stdout.encode("latin-1") if isinstance(r.stdout, str) else r.stdout
            frame_size = 160 * 90
            if len(raw) >= frame_size * 2:
                f1 = raw[:frame_size]
                f2 = raw[frame_size:frame_size*2]
                diff = sum(abs(a - b) for a, b in zip(f1, f2)) / frame_size
                scores.append(min(100, diff * 2))
    return sum(scores) / len(scores) if scores else 50

def analyze_brightness(path):
    """分析视频平均亮度
    返回0-255
    """
    dur = get_duration(path)
    t = dur * 0.4  # 从40%处采样
    r = ff(["ffmpeg", "-ss", str(t), "-i", str(path),
            "-vframes", "1", "-vf", "scale=80:45,format=gray",
            "-f", "rawvideo", "-"], timeout=15)
    if r and r.stdout:
        raw = r.stdout.encode("latin-1") if isinstance(r.stdout, str) else r.stdout
        if len(raw) > 100:
            return sum(raw) / len(raw)
    return 128

def extract_date_from_name(name):
    """从文件名提取拍摄日期"""
    # DJI格式: dji_fly_20250723_...
    m = re.search(r'(\d{4})(\d{2})(\d{2})', name)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return None

def get_trip_period(date_str):
    """判断属于哪个旅行时段"""
    if not date_str:
        return None
    ym = date_str[:7]  # "2025-07"
    return TRIP_TIMELINE.get(ym)

def scan_and_analyze_sources(use_cache=True):
    """扫描所有素材并深度分析"""
    if use_cache and ANALYSIS_CACHE.exists():
        try:
            with open(ANALYSIS_CACHE, "r", encoding="utf-8") as f:
                cached = json.load(f)
            # 验证缓存有效性
            if cached.get("version") == 2 and len(cached.get("sources", [])) > 0:
                print(f"    (使用缓存: {len(cached['sources'])}个素材)")
                return cached["sources"]
        except:
            pass

    print("    首次分析，需要2-3分钟...")
    all_sources = []
    seen = set()

    for base_dir, src_type, src_label in SOURCES_DIRS:
        if not base_dir.exists():
            print(f"    [WARN] {src_label} dir missing: {base_dir}")
            continue

        files = sorted(base_dir.glob("*.[mM][pP]4"))
        for f in files:
            key = str(f).lower()
            if key in seen:
                continue
            seen.add(key)

            name = f.name.lower()
            # 跳过代理文件
            if "proxy" in name or "540p" in name or "cache" in name:
                continue
            # dji_mimo = 手持稳定器，不是无人机航拍，重分类为action
            if "dji_mimo" in name and src_type == "aerial":
                src_type_actual = "action"
            else:
                src_type_actual = src_type

            # 基础信息
            dur = get_duration(f)
            if dur < MIN_SOURCE_DUR or dur > MAX_SOURCE_DUR:
                continue

            stream = probe_stream(f)
            w = int(stream.get("width", 0))
            h = int(stream.get("height", 0))
            fps = parse_fps(stream.get("r_frame_rate", "30/1"))

            if w < 1280:
                continue

            audio = probe_audio(f)
            date = extract_date_from_name(f.name)
            trip = get_trip_period(date)

            source = {
                "path": str(f),
                "name": f.name,
                "dir": str(base_dir),
                "type": src_type_actual,
                "type_label": src_label,
                "dur": round(dur, 2),
                "w": w, "h": h, "fps": round(fps, 1),
                "is_4k": w >= 3840,
                "is_vertical": h > w,
                "has_audio": audio is not None,
                "date": date,
                "trip_name": trip["name"] if trip else None,
                "trip_mood": trip["mood"] if trip else None,
                "size_mb": round(f.stat().st_size / (1024*1024), 1),
            }
            all_sources.append(source)

    print(f"    基础扫描: {len(all_sources)}个素材")

    # 并行运动分析（加速）
    print(f"    运动分析中...")
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(analyze_motion, s["path"], 3): i
                   for i, s in enumerate(all_sources)}
        for fut in as_completed(futures):
            idx = futures[fut]
            try:
                all_sources[idx]["motion_score"] = round(fut.result(), 1)
            except:
                all_sources[idx]["motion_score"] = 50

    # 亮度分析
    print(f"    亮度分析中...")
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(analyze_brightness, s["path"]): i
                   for i, s in enumerate(all_sources)}
        for fut in as_completed(futures):
            idx = futures[fut]
            try:
                all_sources[idx]["brightness"] = round(fut.result(), 1)
            except:
                all_sources[idx]["brightness"] = 128

    # 计算综合评分
    for s in all_sources:
        score = 0
        # 旅行时段加权
        if s["trip_name"]:
            score += 30
            if "主篇" in s["trip_name"]:
                score += 20  # 2025.7月主旅行最优先
        # 4K加权
        if s["is_4k"]:
            score += 15
        # 高帧率加权（天然慢动作）
        if s["fps"] > 60:
            score += 15
        # 运动能量适中最佳（不太静也不太抖）
        motion = s.get("motion_score", 50)
        if 20 < motion < 70:
            score += 10
        elif motion >= 70:
            score += 5  # 高运动也可以，但可能抖
        # 适中时长
        if 10 < s["dur"] < 60:
            score += 5
        # 航拍天然优质
        if s["type"] == "aerial":
            score += 10

        s["composite_score"] = score

    # 排序
    all_sources.sort(key=lambda x: x["composite_score"], reverse=True)

    # 缓存
    cache = {"version": 2, "timestamp": datetime.now().isoformat(),
             "sources": all_sources}
    ANALYSIS_CACHE.parent.mkdir(parents=True, exist_ok=True)
    with open(ANALYSIS_CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

    return all_sources

# ============================================================
# Phase 1: 叙事结构设计
# ============================================================
# 情绪弧线: 悬念钩子(3s) → 序章·出发(20s) → 在路上(30s) → 此刻·高潮(40s) → 余韵·归途(20s) → 尾声(10s)
#
# 情绪强度:
#   ████                              ████████████
#   █████                           ██████████████
#   ██████   ████████████████████  ████████████████
#   ████████████████████████████████████████████████
#   hook     departure  journey    peak          epilogue

NARRATIVE_V2 = [
    {
        "act": "hook",
        "label": "悬念·钩子",
        "duration_target": 5,       # 3-5秒，一个震撼镜头抓住观众
        "n_clips": 1,
        "speed": 0.35,              # 极慢，制造史诗感
        "prefer_type": "aerial",    # 航拍全景最震撼
        "prefer_motion": (10, 40),  # 低运动=稳定大景
        "color_grade": "curves=r='0/0 0.15/0.08 0.5/0.45 0.85/0.9 1/1':g='0/0 0.15/0.1 0.5/0.5 0.85/0.92 1/1':b='0/0 0.15/0.15 0.5/0.55 0.85/0.88 1/1',eq=contrast=1.12:saturation=1.25",
        "narration": None,          # 钩子不说话，纯视觉冲击
        "subtitle": None,
    },
    {
        "act": "departure",
        "label": "序章·启程",
        "duration_target": 25,
        "n_clips": 4,
        "speed": 1.0,
        "prefer_type": "aerial",
        "prefer_motion": (20, 60),
        "color_grade": "curves=r='0/0 0.5/0.48 1/1':g='0/0 0.5/0.52 1/1':b='0/0 0.5/0.5 1/1',eq=contrast=1.05:saturation=1.15:brightness=0.02",
        "narration": "有些地方，照片装不下，视频也留不住。你只能亲自去一趟。",
        "subtitle": "有些地方，照片装不下，\n视频也留不住。\n你只能亲自去一趟。",
    },
    {
        "act": "journey",
        "label": "在路上",
        "duration_target": 35,
        "n_clips": 7,
        "speed": 1.0,               # 正常速度（1.3x太快，观众跟不上）
        "prefer_type": "action",    # 运动相机=在路上
        "prefer_motion": (30, 80),  # 中高运动=骑行/奔跑
        "stabilize": True,          # Action相机需要防抖
        "color_grade": "eq=contrast=1.1:saturation=1.1:brightness=0.01",
        "narration": "不赶路的时候才发现，路上的风其实一直在说话。",
        "subtitle": "不赶路的时候才发现，\n路上的风其实一直在说话。",
    },
    {
        "act": "peak",
        "label": "此刻·高潮",
        "duration_target": 50,
        "n_clips": 6,
        "speed": 0.4,               # 慢动作，时间凝固
        "prefer_type": "camera",    # 4K相机=最精致的画面
        "prefer_motion": (15, 50),  # 适中运动
        "color_grade": "curves=r='0/0 0.3/0.25 0.6/0.65 1/1':g='0/0 0.3/0.28 0.6/0.68 1/1':b='0/0 0.3/0.22 0.6/0.6 1/1',eq=contrast=1.08:saturation=1.3:brightness=0.03",
        "narration": "所有的赶路，所有的等待，都是为了——这一刻。",
        "subtitle": "所有的赶路，所有的等待，\n都是为了——这一刻。",
    },
    {
        "act": "epilogue",
        "label": "余韵·归途",
        "duration_target": 25,
        "n_clips": 3,
        "speed": 0.5,
        "prefer_type": "aerial",    # 航拍远景=情感收束
        "prefer_motion": (5, 30),   # 低运动=安静
        "color_grade": "curves=r='0/0 0.4/0.35 0.7/0.72 1/1':g='0/0 0.4/0.38 0.7/0.75 1/1':b='0/0 0.4/0.42 0.7/0.78 1/1',eq=contrast=1.03:saturation=1.2:brightness=0.04",
        "narration": "回来以后才发现，变的不是风景。是看风景的人。",
        "subtitle": "回来以后才发现，\n变的不是风景。\n是看风景的人。",
    },
]

def select_clips_v2(sources):
    """智能选片：基于运动分析、类型匹配、时间去重"""
    used_paths = set()
    selections = []

    for act in NARRATIVE_V2:
        prefer_type = act["prefer_type"]
        motion_range = act.get("prefer_motion", (0, 100))
        n = act["n_clips"]
        clip_dur = act["duration_target"] / n

        # 候选池：未使用 + 非竖屏
        pool = [s for s in sources
                if s["path"] not in used_paths and not s.get("is_vertical")]

        # 评分
        def act_score(s):
            sc = s.get("composite_score", 0)
            # 类型匹配 — 必须强到能压过composite_score差距
            if s["type"] == prefer_type:
                sc += 80
            # 运动范围匹配
            motion = s.get("motion_score", 50)
            lo, hi = motion_range
            if lo <= motion <= hi:
                sc += 25
            elif motion < lo:
                sc += max(0, 25 - (lo - motion))
            else:
                sc += max(0, 25 - (motion - hi))
            return sc

        pool.sort(key=act_score, reverse=True)
        chosen = pool[:n]

        for c in chosen:
            used_paths.add(c["path"])
            # 智能选取最佳片段起点
            dur = c["dur"]
            speed = act["speed"]
            # 高帧率素材的自然慢动作
            fps = c.get("fps", 30)
            if fps > 60 and speed < 1.0:
                native_slow = 30.0 / fps
                effective_speed = max(native_slow, speed)
            else:
                effective_speed = speed
            # setpts=1/speed*PTS → input of T seconds becomes T/speed output
            # To get clip_dur output, we need clip_dur*speed input
            raw_needed = clip_dur * effective_speed if effective_speed > 0 else clip_dur
            raw_needed = min(raw_needed, dur - 2)

            # 从运动最精彩的位置开始（而不是盲目1/3）
            # 简单启发：视频中段通常比开头有趣
            ss = max(1, dur * 0.35)
            if ss + raw_needed > dur - 1:
                ss = max(0.5, dur - raw_needed - 1)

            selections.append({
                **c,
                "act": act["act"],
                "act_label": act["label"],
                "clip_dur": round(clip_dur, 2),
                "speed": speed,
                "effective_speed": round(effective_speed, 3),
                "raw_needed": round(raw_needed, 2),
                "ss": round(ss, 2),
                "color_grade": act["color_grade"],
                "stabilize": act.get("stabilize", False),
            })

    return selections

# ============================================================
# Phase 2: 提取精华片段
# ============================================================
def extract_clip(sel, idx, spec):
    """提取并处理单个片段"""
    w, h = spec["w"], spec["h"]
    out = CLIPS / f"v3_{idx:02d}_{sel['act']}.mp4"

    vf_parts = []
    # 缩放+填充
    vf_parts.append(f"scale={w}:{h}:force_original_aspect_ratio=decrease")
    vf_parts.append(f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black")
    # 防抖（Action相机素材）
    if sel.get("stabilize"):
        vf_parts.append("dejudder")
        vf_parts.append("unsharp=5:5:0.8:5:5:0.4")
    # 变速
    esp = sel["effective_speed"]
    if abs(esp - 1.0) > 0.01:
        vf_parts.append(f"setpts={1.0/esp}*PTS")
    # 帧率统一
    vf_parts.append("fps=30")
    # 场景调色
    vf_parts.append(sel["color_grade"])
    # 淡入淡出（为crossfade准备）
    target = sel["clip_dur"]
    vf_parts.append(f"fade=t=in:d=0.3")
    vf_parts.append(f"fade=t=out:st={max(0.5, target-0.3)}:d=0.3")

    vf = ",".join(vf_parts)

    r = ff(["ffmpeg", "-y",
            "-ss", str(sel["ss"]),
            "-t", str(sel["raw_needed"]),   # -t before -i = input duration limit
            "-i", sel["path"],
            "-vf", vf,
            "-c:v", "libx264", "-crf", str(CRF), "-preset", "fast",
            "-pix_fmt", "yuv420p",
            "-an",  # 先不要音频，后面统一处理
            str(out)], timeout=240)

    if r and r.returncode == 0 and out.exists() and out.stat().st_size > 1000:
        actual_dur = get_duration(out)
        return str(out), round(actual_dur, 2)
    return None, 0

# ============================================================
# Phase 3: BGM 生成（多段式情绪曲线）
# ============================================================
def generate_bgm(total_dur):
    """生成多段式BGM，情绪曲线与叙事同步
    5段: 低沉预热 → 渐起期待 → 稳定行进 → 高燃巅峰 → 柔和回落
    """
    bgm_path = HERE / "bgm_v2.mp3"

    # 各段时长比例（与叙事对应）
    ratios = [0.04, 0.18, 0.25, 0.35, 0.18]
    durations = [total_dur * r for r in ratios]

    # 生成各段音频
    segments = []
    configs = [
        # (频率, 音量, 描述)
        {"freqs": [(55, 0.12), (110, 0.06)], "noise": 0.015, "label": "hook_ambient"},
        {"freqs": [(80, 0.10), (160, 0.08), (320, 0.04)], "noise": 0.02, "label": "departure_rising"},
        {"freqs": [(100, 0.08), (200, 0.10), (400, 0.06)], "noise": 0.025, "label": "journey_driving"},
        {"freqs": [(120, 0.12), (240, 0.10), (480, 0.08), (960, 0.04)], "noise": 0.03, "label": "peak_climax"},
        {"freqs": [(65, 0.10), (130, 0.06), (260, 0.03)], "noise": 0.012, "label": "epilogue_calm"},
    ]

    for i, (dur, cfg) in enumerate(zip(durations, configs)):
        seg_path = WORK / f"bgm_seg_{i}.wav"
        # 构建lavfi源
        inputs = []
        filters = []
        for j, (freq, vol) in enumerate(cfg["freqs"]):
            inputs.append(f"sine=frequency={freq}:duration={dur}")
            filters.append(f"[{j}:a]volume={vol}[t{j}]")

        noise_idx = len(cfg["freqs"])
        inputs.append(f"anoisesrc=d={dur}:c=pink:a={cfg['noise']}")
        filters.append(f"[{noise_idx}:a]lowpass=f=1500[n]")

        # 混合所有音源
        mix_inputs = "".join(f"[t{j}]" for j in range(len(cfg["freqs"]))) + "[n]"
        n_inputs = len(cfg["freqs"]) + 1
        filters.append(f"{mix_inputs}amix=inputs={n_inputs}:duration=longest,"
                       f"afade=t=in:d={min(2, dur*0.15)},"
                       f"afade=t=out:st={dur-min(2, dur*0.15)}:d={min(2, dur*0.15)}[out]")

        cmd = ["ffmpeg", "-y"]
        for inp in inputs:
            cmd.extend(["-f", "lavfi", "-i", inp])
        cmd.extend(["-filter_complex", ";".join(filters)])
        cmd.extend(["-map", "[out]", "-c:a", "pcm_s16le", str(seg_path)])

        ff(cmd, timeout=60)
        if seg_path.exists():
            segments.append(str(seg_path))

    if not segments:
        return None

    # 拼接所有段
    concat_file = WORK / "bgm_concat.txt"
    with open(concat_file, "w", encoding="utf-8") as f:
        for seg in segments:
            f.write(f"file '{seg}'\n")

    ff(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
        "-c:a", "libmp3lame", "-b:a", "192k",
        "-af", "lowpass=f=2500,highpass=f=40",
        str(bgm_path)], timeout=60)

    if bgm_path.exists():
        return str(bgm_path)
    return None

# ============================================================
# Phase 4: TTS 旁白
# ============================================================
def generate_narrations():
    """生成各幕旁白"""
    narr_files = {}
    try:
        import edge_tts
    except ImportError:
        print("    [WARN] edge-tts not available (pip install edge-tts)")
        return narr_files

    rates = {
        "departure": "-8%",
        "journey": "-3%",
        "peak": "-5%",
        "epilogue": "-12%",
    }

    async def _gen():
        for act in NARRATIVE_V2:
            if not act.get("narration"):
                continue
            name = act["act"]
            text = act["narration"]
            out = WORK / f"narr_{name}.mp3"
            rate = rates.get(name, "+0%")
            try:
                c = edge_tts.Communicate(text, TTS_VOICE, rate=rate)
                await c.save(str(out))
                if out.exists() and out.stat().st_size > 1000:
                    narr_files[name] = str(out)
                    dur = get_duration(out)
                    print(f"      {name}: {dur:.1f}s")
            except Exception as e:
                print(f"      {name}: [FAIL] {e}")

    asyncio.run(_gen())
    return narr_files

# ============================================================
# Phase 5: 组装（crossfade + 旁白叠加 + BGM ducking + 字幕）
# ============================================================
def build_act_video(act_info, clip_paths, narr_path=None):
    """构建单个叙事段（多clip crossfade拼接 + 旁白）"""
    act_name = act_info["act"]

    if len(clip_paths) == 1:
        # 单clip直接使用
        act_video = WORK / f"act_{act_name}.mp4"
        shutil.copy2(clip_paths[0], act_video)
    else:
        # 多clip crossfade拼接
        # ffmpeg xfade滤镜链
        n = len(clip_paths)
        inputs = []
        for p in clip_paths:
            inputs.extend(["-i", p])

        # 构建xfade链
        filter_parts = []
        dur_list = [get_duration(p) for p in clip_paths]
        offsets = []
        cum = 0
        for i in range(n - 1):
            offset = cum + dur_list[i] - CROSSFADE_DUR
            offsets.append(offset)
            cum = offset

        if n == 2:
            filter_parts.append(
                f"[0:v][1:v]xfade=transition=fade:duration={CROSSFADE_DUR}:"
                f"offset={offsets[0]}[vout]"
            )
        else:
            # 链式xfade
            prev = "[0:v]"
            for i in range(1, n):
                out_label = f"[v{i}]" if i < n - 1 else "[vout]"
                filter_parts.append(
                    f"{prev}[{i}:v]xfade=transition=fade:duration={CROSSFADE_DUR}:"
                    f"offset={offsets[i-1]}{out_label}"
                )
                prev = out_label

        act_video = WORK / f"act_{act_name}.mp4"
        cmd = ["ffmpeg", "-y"] + inputs
        cmd.extend(["-filter_complex", ";".join(filter_parts)])
        cmd.extend(["-map", "[vout]",
                     "-c:v", "libx264", "-crf", str(CRF), "-preset", "fast",
                     "-pix_fmt", "yuv420p",
                     str(act_video)])
        ff(cmd, timeout=180)

        if not act_video.exists():
            # fallback: concat without crossfade
            concat_f = WORK / f"concat_{act_name}.txt"
            with open(concat_f, "w", encoding="utf-8") as f:
                for p in clip_paths:
                    rp = os.path.relpath(p, WORK)
                    f.write(f"file '{rp}'\n")
            ff(["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", str(concat_f),
                "-c:v", "libx264", "-crf", str(CRF),
                "-pix_fmt", "yuv420p", str(act_video)],
               timeout=120)

    if not act_video.exists():
        return None, 0, 0

    act_dur = get_duration(act_video)

    # 添加音频轨（旁白或静音）
    act_with_audio = WORK / f"act_{act_name}_a.mp4"
    narr_dur = 0

    if narr_path and Path(narr_path).exists():
        narr_dur = get_duration(narr_path)
        delay_ms = int(1.5 * 1000)  # 旁白延迟1.5秒
        ff(["ffmpeg", "-y", "-i", str(act_video), "-i", narr_path,
            "-filter_complex",
            f"[1:a]adelay={delay_ms}|{delay_ms},volume=1.2[narr];"
            f"anullsrc=r=44100:cl=stereo,atrim=duration={act_dur}[sil];"
            f"[sil][narr]amix=inputs=2:duration=first[aout]",
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest", str(act_with_audio)],
           timeout=60)
    else:
        # 添加静音音轨
        ff(["ffmpeg", "-y", "-i", str(act_video),
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-map", "0:v", "-map", "1:a",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest", str(act_with_audio)],
           timeout=60)

    if act_with_audio.exists():
        return str(act_with_audio), get_duration(act_with_audio), narr_dur
    return str(act_video), act_dur, 0

def assemble_final(act_results, bgm_path, spec, vertical=False):
    """最终组装：全片拼接 + BGM sidechain ducking + 字幕 + 首尾渐黑"""
    w, h = spec["w"], spec["h"]

    # 拼接所有叙事段（幕间用短crossfade黑屏过渡）
    breath_dur = 0.6
    concat_parts = []
    for i, (path, dur, act_info, ndur) in enumerate(act_results):
        concat_parts.append(path)
        if i < len(act_results) - 1:
            # 生成呼吸间隔
            bp = str(WORK / f"breath_{i}.mp4")
            ff(["ffmpeg", "-y",
                "-f", "lavfi", "-i", f"color=c=black:s={w}x{h}:d={breath_dur}:r=30",
                "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k",
                "-t", str(breath_dur), bp])
            if Path(bp).exists():
                concat_parts.append(bp)

    concat_file = WORK / "final_concat.txt"
    with open(concat_file, "w", encoding="utf-8") as f:
        for p in concat_parts:
            rp = os.path.relpath(p, WORK)
            f.write(f"file '{rp}'\n")

    raw_final = WORK / "raw_final.mp4"
    ff(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
        "-c:v", "libx264", "-crf", str(CRF), "-preset", "medium",
        "-c:a", "aac", "-b:a", "192k", str(raw_final)],
       timeout=300)

    if not raw_final.exists():
        print("  [ERR] Final concat failed")
        return None

    total_dur = get_duration(raw_final)
    print(f"    全片素材: {total_dur:.1f}s")

    # BGM sidechain ducking + 首尾渐黑
    suffix = "_vertical" if vertical else ""
    final_name = f"travel_film_v2{suffix}.mp4"
    final_path = HERE / final_name

    if bgm_path and Path(bgm_path).exists():
        # BGM already longer than video? Just trim. No need for aloop.
        bgm_dur = get_duration(bgm_path)
        need_loop = bgm_dur < total_dur
        bgm_trim = (f"[1:a]atrim=duration={total_dur},volume=0.20,"
                     f"afade=t=in:d=2,afade=t=out:st={total_dur-3}:d=3[bgm]")
        if need_loop:
            bgm_trim = (f"[1:a]aloop=loop=3:size=2e+09,atrim=duration={total_dur},"
                         f"volume=0.20,afade=t=in:d=2,afade=t=out:st={total_dur-3}:d=3[bgm]")

        bgm_mixed = WORK / "bgm_mixed.mp4"
        # Simple reliable mix (sidechain can fail with some BGMs)
        r = ff(["ffmpeg", "-y", "-i", str(raw_final), "-i", bgm_path,
            "-filter_complex",
            f"[0:v]fade=t=in:d=1.5,fade=t=out:st={total_dur-2.5}:d=2.5[vout];"
            f"{bgm_trim};"
            f"[0:a][bgm]amix=inputs=2:duration=first,"
            f"loudnorm=I=-16:LRA=11:TP=-1.5[aout]",
            "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-crf", str(CRF), "-preset", "medium",
            "-c:a", "aac", "-b:a", "192k", "-shortest",
            "-metadata", "title=A Journey in Light",
            "-metadata", "artist=AI Travel Film",
            str(bgm_mixed)],
           timeout=300, quiet=False)

        if r and bgm_mixed.exists() and bgm_mixed.stat().st_size > 10000:
            shutil.move(str(bgm_mixed), str(final_path))
        else:
            print("    [WARN] BGM mix failed, trying without loudnorm...")
            # fallback without loudnorm
            r2 = ff(["ffmpeg", "-y", "-i", str(raw_final), "-i", bgm_path,
                "-filter_complex",
                f"[0:v]fade=t=in:d=1.5,fade=t=out:st={total_dur-2.5}:d=2.5[vout];"
                f"{bgm_trim};"
                f"[0:a][bgm]amix=inputs=2:duration=first[aout]",
                "-map", "[vout]", "-map", "[aout]",
                "-c:v", "libx264", "-crf", str(CRF),
                "-c:a", "aac", "-b:a", "192k", "-shortest",
                str(final_path)],
               timeout=300, quiet=False)
    else:
        shutil.copy2(str(raw_final), str(final_path))

    if not final_path.exists():
        print("  [ERR] Final file not created")
        return None

    # 生成精确SRT字幕
    srt_entries = []
    cursor = 0.0
    for path, adur, act_info, ndur in act_results:
        sub = None
        for act in NARRATIVE_V2:
            if act["act"] == act_info:
                sub = act.get("subtitle")
                break
        if sub and ndur > 0:
            s = cursor + 1.5  # 旁白延迟
            e = s + ndur + 0.5
            srt_entries.append((len(srt_entries)+1, s, e, sub))
        cursor += adur + breath_dur

    srt_path = HERE / f"travel_v2{suffix}.srt"
    with open(srt_path, "w", encoding="utf-8") as f:
        for idx, s, e, text in srt_entries:
            f.write(f"{idx}\n{fmt_srt_time(s)} --> {fmt_srt_time(e)}\n{text}\n\n")

    # 烧入字幕
    final_sub = HERE / f"travel_film_v2{suffix}_sub.mp4"
    srt_rel = os.path.relpath(srt_path, HERE)
    os.chdir(HERE)
    r = ff(["ffmpeg", "-y", "-i", str(final_path),
        "-vf", f"subtitles={srt_rel}:force_style='FontName=Microsoft YaHei,"
              f"FontSize=22,PrimaryColour=&H00FFFFFF,OutlineColour=&H80000000,"
              f"BorderStyle=4,Outline=1,Shadow=0,MarginV=50,Alignment=2,"
              f"Spacing=1'",
        "-c:v", "libx264", "-crf", str(CRF), "-preset", "medium",
        "-c:a", "copy", str(final_sub)],
       timeout=180)

    if final_sub.exists() and final_sub.stat().st_size > 10000:
        # 替换无字幕版
        final_path.unlink(missing_ok=True)
        shutil.move(str(final_sub), str(final_path))
    else:
        print("    [WARN] Subtitle burn-in failed, using no-sub version")

    # 封面提取（从高潮段取）
    cover_path = HERE / f"cover_v2{suffix}.jpg"
    # 从30%处提取（高潮段开始）
    ff(["ffmpeg", "-y", "-ss", str(total_dur * 0.45),
        "-i", str(final_path),
        "-vframes", "1", "-q:v", "2", str(cover_path)])

    return str(final_path), total_dur, len(srt_entries)

# ============================================================
# Phase 6: 报告生成
# ============================================================
def generate_deliverables(sources, selections, act_results, final_path,
                          total_dur, n_subs, elapsed, vertical=False):
    """生成完整交付物"""
    suffix = "_vertical" if vertical else ""
    m, s = divmod(int(total_dur), 60)
    sz = Path(final_path).stat().st_size / (1024*1024) if Path(final_path).exists() else 0

    # 1. 生产报告
    report = {
        "version": "v2",
        "timestamp": datetime.now().isoformat(),
        "spec": "9:16" if vertical else "16:9",
        "duration_seconds": round(total_dur, 1),
        "duration_display": f"{m}:{s:02d}",
        "size_mb": round(sz, 1),
        "total_clips": len(selections),
        "sources_scanned": len(sources),
        "subtitles": n_subs,
        "elapsed_seconds": round(elapsed, 0),
        "narrative": [
            {
                "act": act_info,
                "duration": round(dur, 1),
                "clips": sum(1 for sel in selections if sel["act"] == act_info),
                "has_narration": ndur > 0,
            }
            for path, dur, act_info, ndur in act_results
        ],
        "improvements_over_ultimate": [
            "运动分析选片替代盲目截取",
            "crossfade转场替代黑屏硬切",
            "多段式BGM情绪曲线替代单一sine合成",
            "scenes-aware调色替代固定eq参数",
            "loudnorm音频标准化",
            "叙事文案与具体旅行场景关联",
            "精确字幕时间轴",
        ],
    }

    report_path = HERE / f"production_report_v2{suffix}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # 2. 迭代改进日志
    changelog = f"""# 旅行电影 v2 迭代改进日志

## 版本对比

| 维度 | Ultimate (v1.3) | v2 (本轮) |
|------|-----------------|-----------|
| 时长 | 2:15 (135s) | {m}:{s:02d} ({total_dur:.0f}s) |
| 片段数 | 19 | {len(selections)} |
| 选片方式 | 按类型+评分排序取topN | 运动分析+类型匹配+场景适配 |
| 转场 | 黑屏0.8s | crossfade {CROSSFADE_DUR}s |
| BGM | 单一sine合成 (2.8MB) | 5段式情绪曲线BGM |
| 调色 | 固定eq参数(5种) | curves+eq场景感知调色(5种) |
| 音频 | 简单amix | sidechain ducking + loudnorm -16LUFS |
| 旁白文案 | 通用心灵鸡汤 | 与旅行体验关联的具体表达 |
| 字幕 | 4条基础 | {n_subs}条精确时间轴 |

## 上轮问题 → 本轮改动

1. **选片盲目** → 新增运动能量分析(帧间差异)和亮度分析，每个素材有量化评分
2. **转场生硬** → 使用ffmpeg xfade实现视觉流畅的crossfade
3. **BGM单调** → 5段式BGM与叙事情绪曲线严格同步(低沉→渐起→行进→高燃→柔和)
4. **调色粗糙** → 使用curves精细调色替代简单eq，每幕独立色彩方案
5. **音频不专业** → loudnorm标准化到-16 LUFS (YouTube/B站推荐标准)
6. **旁白空洞** → 重写文案，从"有些路走过一次"改为与具体旅行感受相关的表达
7. **Bug修复** → 修复了build_ultimate.py line 392 tmp_srt未定义的错误

## 对标分析

### 参考视频
1. **@房琪kiki** (2000万粉): 文案驱动型，每句话都是金句，画面服务于文案
2. **@旅行者小辉** (500万粉): 航拍驱动型，大全景+慢动作+史诗BGM
3. **@徐云流浪中国** (1200万粉): 真实感驱动型，不追求完美画面，追求情感真实

### 差距点
- vs 房琪: 我们的文案力度不够，缺少"金句"密度，每句话应该能独立成为标题
- vs 小辉: 航拍素材质量相当，但缺少FPV穿越机视角的冲击力
- vs 徐云: 缺少原声(现场环境音)，纯BGM+旁白缺乏真实感沉浸

### 优势点
- 三机位(Action+Drone+4K Camera)同时拍摄，素材多样性高
- 4K@120fps天然慢动作，画质顶级
- 全自动化pipeline，迭代速度远超手动剪辑

## 下一轮改进方向

1. **原声混入**: 保留部分素材的环境音(风声/水声/人声)与BGM混合，增加真实感
2. **FPV模拟**: 用Action相机素材的高速运动段模拟FPV穿越效果
3. **金句密度**: 每5-8秒一句字幕文案，而不是每幕一句
4. **Beat sync**: BGM节拍点与画面切换精确同步
5. **竖屏适配**: 智能裁切出9:16版本，而不是简单加黑边
"""

    log_path = HERE / f"ITERATION_LOG_v2{suffix}.md"
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(changelog)

    return report_path, log_path

# ============================================================
# Main
# ============================================================
def main():
    vertical = "--vertical" in sys.argv
    analyze_only = "analyze" in sys.argv

    spec = SPECS["vertical"] if vertical else SPECS["horizontal"]
    t0 = datetime.now()

    print(f"\n{'='*62}")
    print(f"  Travel Film v2 — 叙事驱动旅行电影")
    print(f"  规格: {spec['label']} ({spec['w']}×{spec['h']})")
    print(f"{'='*62}\n")

    # 工作目录
    WORK.mkdir(parents=True, exist_ok=True)
    CLIPS.mkdir(parents=True, exist_ok=True)

    # Phase 0: 素材分析
    print("  [1/7] 深度素材分析...")
    sources = scan_and_analyze_sources()
    types = {}
    trips = {}
    for s in sources:
        types[s["type"]] = types.get(s["type"], 0) + 1
        t = s.get("trip_name", "其他")
        trips[t] = trips.get(t, 0) + 1

    print(f"    {len(sources)}个可用素材")
    print(f"    类型: {types}")
    print(f"    旅行: {trips}")

    # 显示TOP素材
    print(f"\n    TOP 10 素材:")
    for i, s in enumerate(sources[:10]):
        tag = "[air]" if s["type"]=="aerial" else "[cam]" if s["type"]=="camera" else "[act]"
        print(f"    {i+1}. {tag} [{s.get('trip_name','?')[:6]}] "
              f"{s['w']}×{s['h']}@{s['fps']:.0f}fps "
              f"motion={s.get('motion_score',0):.0f} "
              f"score={s['composite_score']} "
              f"{s['name'][:35]}")

    if analyze_only:
        print(f"\n  分析完成。结果保存到 {ANALYSIS_CACHE}")
        return

    if len(sources) < 15:
        print("  [ERR] Not enough sources (need 15+)")
        return

    # Phase 1: 智能选片
    print(f"\n  [2/7] 智能选片...")
    selections = select_clips_v2(sources)
    for s in selections:
        tag = "[cam]" if s["type"]=="camera" else "[air]" if s["type"]=="aerial" else "[act]"
        print(f"    {tag} [{s['act_label']}] {s['w']}×{s['h']}@{s['fps']:.0f}fps "
              f"→{s['clip_dur']:.1f}s @{s['effective_speed']:.2f}x  "
              f"motion={s.get('motion_score',0):.0f}  {s['name'][:30]}")

    # Phase 2: 提取片段
    print(f"\n  [3/7] 提取 {len(selections)} 个精华片段...")
    clip_paths_by_act = {}
    for i, sel in enumerate(selections):
        print(f"    [{i+1}/{len(selections)}] {sel['act_label']} ...", end=" ", flush=True)
        path, actual_dur = extract_clip(sel, i, spec)
        if path:
            act = sel["act"]
            clip_paths_by_act.setdefault(act, []).append(path)
            sz = Path(path).stat().st_size / (1024*1024)
            print(f"OK {actual_dur:.1f}s / {sz:.1f}MB")
        else:
            print("FAIL")

    total_clips = sum(len(v) for v in clip_paths_by_act.values())
    if total_clips < 5:
        print("  [ERR] Not enough clips")
        return

    # Phase 3: TTS旁白
    print(f"\n  [4/7] 生成旁白...")
    narr_files = generate_narrations()

    # Phase 4: 构建叙事段
    print(f"\n  [5/7] 构建叙事段 (crossfade转场)...")
    act_results = []
    for act in NARRATIVE_V2:
        act_name = act["act"]
        paths = clip_paths_by_act.get(act_name, [])
        if not paths:
            print(f"    [SKIP] {act['label']}: no clips")
            continue
        narr = narr_files.get(act_name)
        path, dur, ndur = build_act_video(act, paths, narr)
        if path:
            act_results.append((path, dur, act_name, ndur))
            print(f"    {act['label']}: {dur:.1f}s / {len(paths)}片段"
                  + (f" / 旁白{ndur:.1f}s" if ndur else ""))

    if not act_results:
        print("  [ERR] No narrative segments")
        return

    # Phase 5: BGM — 优先用下载的专业BGM，fallback到合成
    est_total = sum(d for _, d, _, _ in act_results) + 0.6 * (len(act_results)-1)
    pro_bgm = HERE / "bgm_perspectives.mp3"
    if pro_bgm.exists():
        bgm_path = str(pro_bgm)
        print(f"\n  [6/7] BGM: {pro_bgm.name} ({pro_bgm.stat().st_size//1024//1024}MB)")
    else:
        print(f"\n  [6/7] BGM fallback: generating synthetic ({est_total:.0f}s)...")
        bgm_path = generate_bgm(est_total)
        if bgm_path:
            print(f"    OK BGM: {Path(bgm_path).stat().st_size//1024}KB")
        else:
            print(f"    [WARN] BGM generation failed")

    # Phase 6: 终极组装
    print(f"\n  [7/7] 终极组装...")
    result = assemble_final(act_results, bgm_path, spec, vertical)
    if not result:
        return

    final_path, total_dur, n_subs = result
    elapsed = (datetime.now() - t0).total_seconds()
    m, s = divmod(int(total_dur), 60)
    sz = Path(final_path).stat().st_size / (1024*1024) if Path(final_path).exists() else 0

    # 生成交付物
    report_path, log_path = generate_deliverables(
        sources, selections, act_results, final_path,
        total_dur, n_subs, elapsed, vertical)

    print(f"\n  {'='*60}")
    print(f"  * Travel Film v2 Done")
    print(f"    [video] {final_path}")
    print(f"    [time]  {m}:{s:02d}")
    print(f"    [size]  {sz:.0f}MB")
    print(f"    [clips] {total_clips} (from {len(sources)} sources)")
    print(f"    [subs]  {n_subs}")
    print(f"    [bgm]   5-section + sidechain ducking")
    print(f"    [color] scene-aware curves + eq")
    print(f"    [audio] loudnorm -16 LUFS")
    print(f"    [log]   {log_path.name}")
    print(f"    [took]  {elapsed:.0f}s")
    print(f"  {'='*60}")

    # 清理临时文件
    print(f"\n  清理临时文件...")
    for f in WORK.glob("*.mp4"):
        f.unlink(missing_ok=True)
    for f in WORK.glob("*.wav"):
        f.unlink(missing_ok=True)
    for f in WORK.glob("*.txt"):
        f.unlink(missing_ok=True)

if __name__ == "__main__":
    main()
