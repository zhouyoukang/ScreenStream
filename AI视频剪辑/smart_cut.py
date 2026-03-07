"""
Smart Cut — AI自动精华提取器
从 E:\VideoEdit 的50个素材中自动分析、评分、提取精华、组装成品

用法:
  python smart_cut.py scan      扫描所有素材，生成评分报告
  python smart_cut.py cut       从高分素材中提取精华片段
  python smart_cut.py assemble  组装精华片段+BGM→最终成品
  python smart_cut.py all       一键全流程 (scan→cut→assemble)

原理:
  1. ffprobe 提取元数据（分辨率/时长/编码/帧率）
  2. ffmpeg scene detect 检测场景变化丰富度
  3. ffmpeg volumedetect 检测音频活跃度
  4. 综合评分 → 提取每个高分素材的最佳15s片段
  5. 按评分排序拼接 + BGM淡入淡出 → 最终成品
"""
import subprocess, json, os, sys, math
from pathlib import Path
from datetime import datetime

VIDEOEDIT = Path(r"E:\VideoEdit")
HERE = Path(__file__).parent
OUTPUT = HERE / "04-智能精华"
OUTPUT.mkdir(parents=True, exist_ok=True)

SCAN_REPORT = OUTPUT / "scan_report.json"
BGM = HERE / "01-B站科技视频" / "bgm.mp3"
FINAL = OUTPUT / "smart_highlight.mp4"

# 素材目录（只扫描原始素材，不扫描proxy/output）
SCAN_DIRS = [
    VIDEOEDIT / "01-航拍素材_DJI",
    VIDEOEDIT / "02-相机录像_Camera",
]

CLIP_DURATION = 12  # 每个片段提取秒数
MAX_CLIPS = 15      # 最多提取片段数
MIN_DURATION = 5    # 最短素材时长（秒）

def run_ff(cmd, timeout=60):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                       encoding="utf-8", errors="replace")
    return r

def probe(path):
    r = run_ff(["ffprobe", "-v", "quiet", "-print_format", "json",
                "-show_format", "-show_streams", str(path)])
    try: return json.loads(r.stdout)
    except: return None

def get_dur(path):
    info = probe(path)
    if info:
        try: return float(info["format"]["duration"])
        except: pass
    return 0

def get_scene_score(path, max_seconds=20):
    """用ffmpeg检测前N秒的场景变化次数（4K素材先降采样加速）"""
    dur = min(get_dur(path), max_seconds)
    if dur < 3: return 0
    try:
        r = run_ff([
            "ffmpeg", "-t", str(dur), "-i", str(path),
            "-vf", "scale=640:-1,select='gt(scene,0.25)',showinfo",
            "-f", "null", "-"
        ], timeout=45)
        count = r.stderr.count("pts_time:")
        return count / dur * 10
    except:
        return 5  # 超时给默认中等分

def get_audio_score(path):
    """检测音频均值音量"""
    try:
        r = run_ff([
            "ffmpeg", "-t", "10", "-i", str(path),
            "-af", "volumedetect", "-f", "null", "-"
        ], timeout=30)
    except:
        return 3  # 超时给默认低分
    for line in r.stderr.split("\n"):
        if "mean_volume:" in line:
            try:
                vol = float(line.split("mean_volume:")[1].strip().split()[0])
                # -90dB=静音(0分), -30dB=正常人声(10分), -10dB=很响(10分)
                if vol < -70: return 0
                if vol < -50: return 3
                if vol < -35: return 7
                return 10
            except: pass
    return 0

def score_video(path):
    """综合评分一个视频素材"""
    info = probe(path)
    if not info: return None

    fmt = info.get("format", {})
    streams = info.get("streams", [])
    vs = next((s for s in streams if s.get("codec_type") == "video"), {})

    dur = float(fmt.get("duration", 0))
    if dur < MIN_DURATION: return None

    w = int(vs.get("width", 0))
    h = int(vs.get("height", 0))
    try:
        fr = vs.get("r_frame_rate", "0/1")
        fps = eval(fr) if "/" in str(fr) else float(fr)
    except: fps = 0

    size_mb = int(fmt.get("size", 0)) / (1024*1024)
    bitrate = int(fmt.get("bit_rate", 0)) // 1000

    # 分维度评分
    res_score = 10 if w >= 3840 else 8 if w >= 1920 else 5 if w >= 1280 else 3
    fps_score = 10 if fps >= 60 else 7 if fps >= 30 else 4
    dur_score = 10 if dur >= 30 else 7 if dur >= 15 else 4 if dur >= 5 else 1
    bitrate_score = 10 if bitrate >= 10000 else 8 if bitrate >= 3000 else 5

    # 场景丰富度（耗时操作，仅对分辨率≥1080p的素材）
    scene_score = 0
    if w >= 1280:
        scene_score = min(10, get_scene_score(path))

    # 音频活跃度
    audio_score = get_audio_score(path)

    # 加权总分
    total = (res_score * 2 + fps_score * 1.5 + dur_score * 1 +
             bitrate_score * 1 + scene_score * 3 + audio_score * 1.5)
    max_total = (10*2 + 10*1.5 + 10*1 + 10*1 + 10*3 + 10*1.5)

    # 判断类型
    fname = path.name.lower()
    vtype = "航拍" if "dji" in fname else "相机" if "vid" in fname else "其他"

    return {
        "path": str(path),
        "name": path.name,
        "type": vtype,
        "duration": dur,
        "width": w, "height": h, "fps": fps,
        "size_mb": round(size_mb, 1),
        "bitrate_kbps": bitrate,
        "scores": {
            "分辨率": res_score,
            "帧率": fps_score,
            "时长": dur_score,
            "码率": bitrate_score,
            "场景丰富": round(scene_score, 1),
            "音频活跃": audio_score,
        },
        "total": round(total, 1),
        "max": max_total,
        "pct": round(total / max_total * 100, 1),
    }

# ============================================================
# scan — 扫描所有素材
# ============================================================
def cmd_scan():
    print(f"\n{'='*60}")
    print(f"  Smart Cut — 素材扫描")
    print(f"{'='*60}\n")

    all_videos = []
    for d in SCAN_DIRS:
        if d.exists():
            # 排除proxy目录
            for f in sorted(d.glob("*.mp4")):
                if "proxy" not in str(f).lower():
                    all_videos.append(f)

    print(f"  发现 {len(all_videos)} 个素材\n")

    results = []
    for i, v in enumerate(all_videos):
        print(f"  [{i+1}/{len(all_videos)}] {v.name}...", end=" ", flush=True)
        r = score_video(v)
        if r:
            results.append(r)
            print(f"{r['pct']:.0f}% ({r['type']} {r['width']}×{r['height']} {r['duration']:.0f}s)")
        else:
            print("跳过 (太短或无法分析)")

    results.sort(key=lambda x: x["total"], reverse=True)

    # 保存报告
    report = {"timestamp": datetime.now().isoformat(), "count": len(results), "videos": results}
    with open(SCAN_REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # 输出排名
    print(f"\n{'='*60}")
    print(f"  评分排名 (Top 15)")
    print(f"{'='*60}")
    for i, r in enumerate(results[:15]):
        d = r["duration"]
        m, s = divmod(int(d), 60)
        print(f"  {i+1:2d}. {r['pct']:5.1f}%  {r['type']}  {r['width']}×{r['height']}  {m}:{s:02d}  {r['name'][:45]}")

    print(f"\n  报告: {SCAN_REPORT}")
    return results

# ============================================================
# cut — 提取精华片段
# ============================================================
def cmd_cut():
    print(f"\n{'='*60}")
    print(f"  Smart Cut — 精华提取")
    print(f"{'='*60}\n")

    if not SCAN_REPORT.exists():
        print("  ⚠️  请先运行 scan")
        return

    with open(SCAN_REPORT, "r", encoding="utf-8") as f:
        report = json.load(f)

    videos = report["videos"][:MAX_CLIPS]
    clips_dir = OUTPUT / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    clip_paths = []
    for i, v in enumerate(videos):
        src = Path(v["path"])
        if not src.exists():
            print(f"  ❌ 源不存在: {src.name}")
            continue

        dur = v["duration"]
        # 选取最佳起始点：跳过开头2s，取中段精华
        if dur <= CLIP_DURATION + 2:
            ss = 1
            t = min(dur - 1, CLIP_DURATION)
        else:
            # 从1/4处开始取（通常比开头更精彩）
            ss = max(2, dur * 0.25)
            t = CLIP_DURATION

        clip_path = clips_dir / f"clip_{i:02d}_{v['type']}_{v['pct']:.0f}pct.mp4"

        print(f"  [{i+1}/{len(videos)}] {v['name'][:35]}  @{ss:.0f}s  →{t:.0f}s...", end=" ", flush=True)

        # 提取片段：统一1080p30fps + fade in/out
        r = run_ff([
            "ffmpeg", "-y", "-ss", str(ss), "-i", str(src),
            "-t", str(t),
            "-vf", f"scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30,fade=t=in:d=0.5,fade=t=out:st={t-0.5}:d=0.5",
            "-c:v", "libx264", "-crf", "20", "-preset", "fast",
            "-an",  # 去掉原始音频（后面统一加BGM）
            str(clip_path)
        ], timeout=120)

        if r.returncode == 0 and clip_path.exists():
            sz = clip_path.stat().st_size / (1024*1024)
            print(f"✅ {sz:.1f}MB")
            clip_paths.append(str(clip_path))
        else:
            print(f"❌")

    # 保存片段列表
    clips_list = OUTPUT / "clips_list.json"
    with open(clips_list, "w", encoding="utf-8") as f:
        json.dump(clip_paths, f, ensure_ascii=False, indent=2)

    print(f"\n  提取完成: {len(clip_paths)} 个片段")
    return clip_paths

# ============================================================
# assemble — 组装最终成品
# ============================================================
def cmd_assemble():
    print(f"\n{'='*60}")
    print(f"  Smart Cut — 组装成品")
    print(f"{'='*60}\n")

    clips_list = OUTPUT / "clips_list.json"
    if not clips_list.exists():
        print("  ⚠️  请先运行 cut")
        return

    with open(clips_list, "r", encoding="utf-8") as f:
        clip_paths = json.load(f)

    existing = [p for p in clip_paths if Path(p).exists()]
    if not existing:
        print("  ❌ 无可用片段")
        return

    # 1. 拼接所有片段
    concat_file = OUTPUT / "concat.txt"
    with open(concat_file, "w", encoding="utf-8") as f:
        for p in existing:
            f.write(f"file '{p}'\n")

    no_bgm = OUTPUT / "smart_highlight_raw.mp4"
    print(f"  [1/3] 拼接 {len(existing)} 个片段...")
    r = run_ff([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
        "-c:v", "libx264", "-crf", "18", "-preset", "medium",
        "-pix_fmt", "yuv420p",
        str(no_bgm)
    ], timeout=300)

    if r.returncode != 0 or not no_bgm.exists():
        print(f"  ❌ 拼接失败")
        return

    total_dur = get_dur(no_bgm)
    sz = no_bgm.stat().st_size / (1024*1024)
    print(f"  ✅ {total_dur:.0f}s / {sz:.1f}MB")

    # 2. 添加BGM
    if BGM.exists():
        print(f"  [2/3] 混入BGM...")
        r = run_ff([
            "ffmpeg", "-y", "-i", str(no_bgm), "-i", str(BGM),
            "-filter_complex",
            f"[1:a]aloop=loop=-1:size=2e+09,atrim=duration={total_dur},"
            f"volume=0.2,afade=t=in:d=2,afade=t=out:st={total_dur-3}:d=3[bgm];"
            f"[bgm]apad[out]",
            "-map", "0:v", "-map", "[out]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
            "-shortest",
            str(FINAL)
        ], timeout=120)

        if r.returncode == 0 and FINAL.exists():
            sz = FINAL.stat().st_size / (1024*1024)
            print(f"  ✅ BGM混入完成: {sz:.1f}MB")
        else:
            print(f"  ⚠️  BGM混入失败，使用无BGM版本")
            import shutil
            shutil.copy2(no_bgm, FINAL)
    else:
        print(f"  ⚠️  BGM不存在，跳过")
        import shutil
        shutil.copy2(no_bgm, FINAL)

    # 3. 生成封面
    print(f"  [3/3] 提取封面...")
    cover = OUTPUT / "cover.jpg"
    run_ff(["ffmpeg", "-y", "-ss", "3", "-i", str(FINAL),
            "-vframes", "1", "-q:v", "2", str(cover)])

    m, s = divmod(int(total_dur), 60)
    print(f"\n  {'='*50}")
    print(f"  ★ 成品: {FINAL}")
    print(f"    时长: {m}:{s:02d}")
    print(f"    大小: {FINAL.stat().st_size/(1024*1024):.1f}MB")
    print(f"    片段: {len(existing)}个精华")
    print(f"  {'='*50}")

# ============================================================
# all — 一键全流程
# ============================================================
def cmd_all():
    cmd_scan()
    cmd_cut()
    cmd_assemble()

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1].lower()
    {"scan": cmd_scan, "cut": cmd_cut, "assemble": cmd_assemble, "all": cmd_all}.get(
        cmd, lambda: print(f"未知命令: {cmd}\n{__doc__}"))()

if __name__ == "__main__":
    main()
