"""
Travel Film — 全自动旅行电影生成器
从骑行拍摄/使用素材 + VideoEdit高分素材中自动生成旅行短片

设计理念：
  顶级旅行视频 = 叙事结构(开篇震撼→铺垫→高潮→余韵) × 情绪曲线(BGM节奏驱动) × 视觉节奏(快慢交替)

用法:
  python travel_film.py          一键生成旅行电影
"""
import subprocess, json, os, sys, random
from pathlib import Path
from datetime import datetime

HERE = Path(__file__).parent
OUTPUT = HERE / "05-旅行电影"
OUTPUT.mkdir(parents=True, exist_ok=True)

# 素材源
RIDE_素材 = Path(r"E:\骑行拍摄\使用素材")  # 17个已筛选精华(DJI Action运动相机)
VIDEOEDIT = Path(r"E:\VideoEdit")
DJI_DIR = VIDEOEDIT / "01-航拍素材_DJI"
CAM_DIR = VIDEOEDIT / "02-相机录像_Camera"
BGM = HERE / "01-B站科技视频" / "bgm.mp3"

FINAL = OUTPUT / "travel_film.mp4"

def run_ff(cmd, timeout=120):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
        return r
    except subprocess.TimeoutExpired:
        return None

def get_dur(path):
    r = run_ff(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "csv=p=0", str(path)], timeout=15)
    if r and r.stdout.strip():
        try: return float(r.stdout.strip())
        except: pass
    return 0

def get_res(path):
    r = run_ff(["ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "csv=p=0", str(path)], timeout=15)
    if r and r.stdout.strip():
        try:
            w, h = r.stdout.strip().split(",")
            return int(w), int(h)
        except: pass
    return 0, 0

# ============================================================
# 叙事结构设计
# ============================================================
# 旅行电影的情绪曲线：
# [开篇] 最震撼的航拍全景 → 抓注意力 (5-8s, 慢速)
# [铺垫] 出发/准备/路上 → 建立期待 (快节奏, 2-3s/镜头)
# [高潮] 最精彩的运动/风景 → 情绪顶点 (变速, 快慢交替)
# [余韵] 日落/远景/安静画面 → 收束情绪 (慢速, 长镜头)

STRUCTURE = [
    {"act": "opening",  "label": "开篇·震撼", "clip_dur": 6, "speed": 0.5, "count": 2, "prefer": "航拍"},
    {"act": "buildup",  "label": "铺垫·出发", "clip_dur": 3, "speed": 1.5, "count": 5, "prefer": "运动"},
    {"act": "climax",   "label": "高潮·精彩", "clip_dur": 4, "speed": 1.0, "count": 6, "prefer": "4K"},
    {"act": "climax2",  "label": "高潮·运动", "clip_dur": 3, "speed": 2.0, "count": 4, "prefer": "运动"},
    {"act": "denouement","label": "余韵·远景", "clip_dur": 8, "speed": 0.7, "count": 3, "prefer": "航拍"},
]

def collect_sources():
    """收集所有可用素材"""
    sources = []

    # 骑行拍摄/使用素材 (DJI Action运动相机, 标记为"运动")
    if RIDE_素材.exists():
        for f in sorted(RIDE_素材.glob("*.MP4")) + sorted(RIDE_素材.glob("*.mp4")):
            d = get_dur(f)
            w, h = get_res(f)
            if d >= 5 and w >= 1280:
                sources.append({"path": str(f), "dur": d, "w": w, "h": h,
                               "type": "运动", "name": f.name})

    # VideoEdit 航拍 (标记为"航拍")
    if DJI_DIR.exists():
        for f in sorted(DJI_DIR.glob("*.mp4")):
            if "proxy" in str(f).lower(): continue
            d = get_dur(f)
            w, h = get_res(f)
            if d >= 8 and w >= 1920:
                sources.append({"path": str(f), "dur": d, "w": w, "h": h,
                               "type": "航拍", "name": f.name})

    # VideoEdit 相机 (4K标记为"4K", 其余标记为"相机")
    if CAM_DIR.exists():
        for f in sorted(CAM_DIR.glob("VID*.mp4")):
            if "proxy" in str(f).lower(): continue
            d = get_dur(f)
            w, h = get_res(f)
            if d >= 8 and w >= 1280:
                t = "4K" if w >= 3840 else "相机"
                sources.append({"path": str(f), "dur": d, "w": w, "h": h,
                               "type": t, "name": f.name})

    return sources

def select_clips(sources, structure):
    """按叙事结构选择素材"""
    used = set()
    selections = []

    for act in structure:
        prefer = act["prefer"]
        candidates = [s for s in sources if s["type"] == prefer and s["path"] not in used]
        if len(candidates) < act["count"]:
            # 不够则从所有未用素材中补充
            extras = [s for s in sources if s["path"] not in used and s["path"] not in [c["path"] for c in candidates]]
            candidates.extend(extras)

        # 按时长排序（长素材有更多精华可提取）
        candidates.sort(key=lambda x: x["dur"], reverse=True)
        chosen = candidates[:act["count"]]

        for c in chosen:
            used.add(c["path"])
            selections.append({**c, "act": act["act"], "label": act["label"],
                              "target_dur": act["clip_dur"], "speed": act["speed"]})

    return selections

def extract_clip(src, idx, target_dur, speed, out_dir):
    """从素材中提取精华片段"""
    dur = src["dur"]
    # 从1/3处开始取（跳过开头通常不精彩的部分）
    ss = max(2, dur * 0.3)
    # 考虑变速后需要的原始时长
    raw_dur = target_dur * speed
    if ss + raw_dur > dur:
        ss = max(1, dur - raw_dur - 1)

    clip_path = out_dir / f"clip_{idx:02d}_{src['act']}.mp4"

    # 变速 + 统一1080p + fade in/out
    vf_parts = [
        "scale=1920:1080:force_original_aspect_ratio=decrease",
        "pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
        f"setpts={1/speed}*PTS" if speed != 1.0 else None,
        "fps=30",
        "fade=t=in:d=0.3",
        f"fade=t=out:st={target_dur-0.3}:d=0.3",
    ]
    vf = ",".join(p for p in vf_parts if p)

    r = run_ff([
        "ffmpeg", "-y", "-ss", str(ss), "-i", src["path"],
        "-t", str(raw_dur),
        "-vf", vf,
        "-c:v", "libx264", "-crf", "18", "-preset", "fast",
        "-an",
        str(clip_path)
    ], timeout=180)

    if r and r.returncode == 0 and clip_path.exists():
        return str(clip_path)
    return None

def main():
    print(f"\n{'='*60}")
    print(f"  Travel Film — 全自动旅行电影")
    print(f"{'='*60}\n")

    # 1. 收集素材
    print("  [1/5] 扫描素材...")
    sources = collect_sources()
    types = {}
    for s in sources:
        types[s["type"]] = types.get(s["type"], 0) + 1
    print(f"    发现 {len(sources)} 个可用素材: {types}")

    if len(sources) < 10:
        print("  ❌ 素材不足10个，无法生成旅行电影")
        return

    # 2. 按叙事结构选择
    print("\n  [2/5] 叙事结构选片...")
    selections = select_clips(sources, STRUCTURE)
    for s in selections:
        print(f"    [{s['label']}] {s['type']} {s['w']}×{s['h']} {s['dur']:.0f}s → {s['target_dur']}s @{s['speed']}x  {s['name'][:40]}")

    # 3. 提取精华片段
    print(f"\n  [3/5] 提取 {len(selections)} 个精华片段...")
    clips_dir = OUTPUT / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    clip_paths = []
    for i, sel in enumerate(selections):
        print(f"    [{i+1}/{len(selections)}] {sel['label']} {sel['name'][:30]}...", end=" ", flush=True)
        path = extract_clip(sel, i, sel["target_dur"], sel["speed"], clips_dir)
        if path:
            sz = Path(path).stat().st_size / (1024*1024)
            print(f"✅ {sz:.1f}MB")
            clip_paths.append(path)
        else:
            print("❌")

    if not clip_paths:
        print("  ❌ 无可用片段")
        return

    # 4. 拼接
    print(f"\n  [4/5] 拼接 {len(clip_paths)} 个片段...")
    concat_file = OUTPUT / "concat.txt"
    with open(concat_file, "w", encoding="utf-8") as f:
        for p in clip_paths:
            f.write(f"file '{p}'\n")

    raw = OUTPUT / "travel_raw.mp4"
    r = run_ff([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
        "-c:v", "libx264", "-crf", "18", "-preset", "medium",
        "-pix_fmt", "yuv420p", str(raw)
    ], timeout=300)

    if not r or r.returncode != 0 or not raw.exists():
        print("  ❌ 拼接失败")
        return

    total_dur = get_dur(raw)
    print(f"    ✅ {total_dur:.0f}s / {raw.stat().st_size/(1024*1024):.0f}MB")

    # 5. 加BGM + 元数据
    print(f"\n  [5/5] 混入BGM + 写入元数据...")
    if BGM.exists():
        r = run_ff([
            "ffmpeg", "-y", "-i", str(raw), "-i", str(BGM),
            "-filter_complex",
            f"[1:a]aloop=loop=-1:size=2e+09,atrim=duration={total_dur},"
            f"volume=0.25,afade=t=in:d=3,afade=t=out:st={total_dur-4}:d=4[bgm];"
            f"[bgm]apad[out]",
            "-map", "0:v", "-map", "[out]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            "-metadata", "title=Travel Film - A Journey in Light",
            "-metadata", "artist=AI Travel Film Maker",
            "-metadata", f"date={datetime.now().year}",
            str(FINAL)
        ], timeout=120)

        if r and r.returncode == 0 and FINAL.exists():
            print(f"    ✅ BGM混入完成")
        else:
            print(f"    ⚠️  BGM失败，使用原始版")
            import shutil
            shutil.copy2(raw, FINAL)
    else:
        import shutil
        shutil.copy2(raw, FINAL)

    # 封面
    run_ff(["ffmpeg", "-y", "-ss", "3", "-i", str(FINAL),
            "-vframes", "1", "-q:v", "2", str(OUTPUT / "cover.jpg")])

    m, s = divmod(int(get_dur(FINAL)), 60)
    sz = FINAL.stat().st_size / (1024*1024)
    print(f"\n  {'='*55}")
    print(f"  ★ 旅行电影已生成")
    print(f"    📽️  {FINAL}")
    print(f"    ⏱️  {m}:{s:02d}")
    print(f"    📦  {sz:.0f}MB")
    print(f"    🎬  {len(clip_paths)}个精华片段")
    print(f"    🎵  BGM: {'✅' if BGM.exists() else '❌'}")
    print(f"    📊  叙事: 开篇震撼→铺垫出发→高潮精彩→高潮运动→余韵远景")
    print(f"  {'='*55}")

    # 保存制作报告
    report = {
        "timestamp": datetime.now().isoformat(),
        "output": str(FINAL),
        "duration": get_dur(FINAL),
        "size_mb": sz,
        "clips": len(clip_paths),
        "sources_scanned": len(sources),
        "structure": [{"act": s["act"], "label": s["label"], "name": s["name"],
                       "type": s["type"], "speed": s["speed"]} for s in selections]
    }
    with open(OUTPUT / "production_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
