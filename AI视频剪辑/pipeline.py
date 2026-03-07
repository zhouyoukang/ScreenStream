"""
Agent 视频工坊 — 统一管线
一键触发: python pipeline.py [命令]

命令:
  status    查看所有项目状态
  build1    构建项目一（B站科技视频: TTS→截图→视频→字幕→BGM）
  build2    构建项目二（录屏智剪: 最新录屏→评分→筛选→合成）
  serve     启动HTTP预览服务器
  collect   汇聚所有精华到本目录
  clean     清理中间产物（保留精华+工具）
  info      显示管线帮助信息
"""
import subprocess, os, sys, shutil, json
from pathlib import Path
from datetime import datetime

HERE = Path(__file__).parent
P1_DIR = Path(r"E:\道\道生一\_video")
P2_DIR = Path(r"D:\屏幕录制")
P3_DIR = Path(r"E:\VideoEdit")

# 项目子目录
P1_OUT = HERE / "01-B站科技视频"
P2_OUT = HERE / "02-录屏智剪"
P3_OUT = HERE / "03-相机AI剪辑"

for d in [P1_OUT, P2_OUT, P3_OUT]:
    d.mkdir(parents=True, exist_ok=True)

def dur(path):
    try:
        r = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
                           "-of","csv=p=0",str(path)], capture_output=True, text=True, timeout=10)
        return float(r.stdout.strip())
    except: return 0

def sz(path):
    try: return path.stat().st_size / (1024*1024)
    except: return 0

def fmt_dur(s):
    m, s = divmod(int(s), 60)
    return f"{m}:{s:02d}"

def print_header(title):
    w = 60
    print(f"\n{'='*w}")
    print(f"  {title}")
    print(f"{'='*w}")

def print_file(path, label="", indent=2):
    if path.exists():
        d = dur(path) if path.suffix in ('.mp4','.mkv','.mp3') else 0
        s = sz(path)
        dstr = f" [{fmt_dur(d)}]" if d > 0 else ""
        print(f"{' '*indent}✅ {label or path.name}: {s:.1f}MB{dstr}")
    else:
        print(f"{' '*indent}❌ {label or path.name}: 缺失")

# ============================================================
# status — 查看所有项目状态
# ============================================================
def cmd_status():
    print_header("Agent 视频工坊 — 全项目状态")
    
    # 项目一
    print("\n📽️  项目一：B站科技视频 \"为什么AI越聊越笨\"")
    print(f"  源: {P1_DIR}")
    p1_finals = ["v16_final.mp4", "v16_subtitled.mp4", "v16_no_subtitle.mp4"]
    for f in p1_finals:
        print_file(P1_DIR / "video_output" / f, f"[源]{f}")
        print_file(P1_OUT / f, f"[汇]{f}")
    p1_assets = ["slides.html","bgm.mp3","tts_full.mp3","02_script.md","bilibili_publish.md","transcript.md"]
    for f in p1_assets:
        print_file(P1_OUT / f, f"[配]{f}")
    
    # 构建工具状态
    tools = ["build_tts.py","capture_slides.py","build_video.py","build_subtitles.py","build_bgm.py"]
    missing = [t for t in tools if not (P1_DIR / t).exists()]
    print(f"  🔧 构建管线: {'✅ 5/5脚本就绪' if not missing else f'❌ 缺失: {missing}'}")
    
    # 中间产物
    intermediates = list((P1_DIR / "video_output").glob("clip_*.mp4")) + \
                    list((P1_DIR / "video_output").glob("seg_*_video.mp4")) + \
                    list((P1_DIR / "video_output").glob("breath_*.mp4"))
    if intermediates:
        total_mb = sum(sz(f) for f in intermediates)
        print(f"  🗑️  中间产物: {len(intermediates)}个 ({total_mb:.0f}MB)")
    
    # 项目二
    print("\n🖥️  项目二：录屏智剪")
    print(f"  源: {P2_DIR}")
    p2_showcases = [
        P2_DIR / "v4_session" / "output" / "showcase_v5.mp4",
        P2_DIR / "realtime_session" / "output" / "showcase_v3.mp4",
    ]
    for p in p2_showcases:
        print_file(p, f"[源]{p.name}")
    print_file(P2_OUT / "showcase_v5.mp4", "[汇]showcase_v5.mp4")
    print_file(P2_OUT / "showcase_v3.mp4", "[汇]showcase_v3.mp4")
    
    mkv_files = list((P2_DIR / "2026-02-开发录屏").glob("*.mkv")) if (P2_DIR / "2026-02-开发录屏").exists() else []
    if mkv_files:
        total_gb = sum(sz(f) for f in mkv_files) / 1024
        print(f"  📹 原始录屏: {len(mkv_files)}个MKV ({total_gb:.1f}GB)")

    # 项目三
    print("\n📷  项目三：相机AI剪辑")
    print(f"  源: {P3_DIR}")
    p3_final = P3_DIR / "06-成品输出_Output" / "final_july2025.mp4"
    print_file(p3_final, "[源]final_july2025.mp4")
    print_file(P3_OUT / "final_july2025.mp4", "[汇]final_july2025.mp4")
    
    camera_files = list((P3_DIR / "02-相机录像_Camera").glob("VID*.mp4")) if (P3_DIR / "02-相机录像_Camera").exists() else []
    if camera_files:
        total_gb = sum(sz(f) for f in camera_files) / 1024
        print(f"  📹 原始素材: {len(camera_files)}个录像 ({total_gb:.1f}GB)")
    
    # 汇总
    print_header("汇总")
    all_finals = [P1_OUT/f for f in p1_finals] + [P2_OUT/"showcase_v5.mp4", P2_OUT/"showcase_v3.mp4", P3_OUT/"final_july2025.mp4"]
    existing = [f for f in all_finals if f.exists()]
    total_dur = sum(dur(f) for f in existing)
    total_sz = sum(sz(f) for f in existing)
    print(f"  精华视频: {len(existing)}/6")
    print(f"  总时长: {fmt_dur(total_dur)}")
    print(f"  总大小: {total_sz:.0f}MB")
    print(f"  前端: {'✅' if (HERE/'index.html').exists() else '❌'} index.html")
    print(f"  文档: {'✅' if (HERE/'README.md').exists() else '❌'} README.md")

# ============================================================
# build1 — 构建项目一（B站科技视频）
# ============================================================
def cmd_build1():
    print_header("构建项目一：B站科技视频")
    os.chdir(P1_DIR)
    
    steps = [
        ("1/5 TTS语音生成", "build_tts.py"),
        ("2/5 幻灯片截图", "capture_slides.py"),
        ("3/5 视频组装", "build_video.py"),
        ("4/5 字幕烧入", "build_subtitles.py"),
        ("5/5 BGM混合", "build_bgm.py"),
    ]
    
    for label, script in steps:
        script_path = P1_DIR / script
        if not script_path.exists():
            print(f"  ❌ {label}: {script} 不存在，跳过")
            continue
        print(f"\n  ▶ {label}...")
        r = subprocess.run([sys.executable, str(script_path)], cwd=str(P1_DIR), timeout=300)
        if r.returncode != 0:
            print(f"  ⚠️  {label} 退出码 {r.returncode}")
    
    # 汇聚到本目录
    print("\n  📦 汇聚精华...")
    _collect_p1()
    print("  ✅ 项目一构建完成")

# ============================================================
# build2 — 构建项目二（录屏智剪）
# ============================================================
def cmd_build2():
    print_header("构建项目二：录屏智剪")
    v5_script = P2_DIR / "v4_session" / "build_v5.py"
    if not v5_script.exists():
        print(f"  ❌ {v5_script} 不存在")
        return
    print("  ▶ 运行 build_v5.py...")
    r = subprocess.run([sys.executable, str(v5_script)], cwd=str(v5_script.parent), timeout=300)
    if r.returncode != 0:
        print(f"  ⚠️  退出码 {r.returncode}")
    _collect_p2()
    print("  ✅ 项目二构建完成")

# ============================================================
# collect — 汇聚所有精华
# ============================================================
def _collect_p1():
    files = {
        P1_DIR/"video_output"/"v16_final.mp4": P1_OUT/"v16_final.mp4",
        P1_DIR/"video_output"/"v16_subtitled.mp4": P1_OUT/"v16_subtitled.mp4",
        P1_DIR/"video_output"/"v16_no_subtitle.mp4": P1_OUT/"v16_no_subtitle.mp4",
        P1_DIR/"slides.html": P1_OUT/"slides.html",
        P1_DIR/"bilibili_publish.md": P1_OUT/"bilibili_publish.md",
        P1_DIR/"transcript.md": P1_OUT/"transcript.md",
        P1_DIR/"02_script.md": P1_OUT/"02_script.md",
        P1_DIR/"bgm.mp3": P1_OUT/"bgm.mp3",
        P1_DIR/"tts_full.mp3": P1_OUT/"tts_full.mp3",
    }
    _do_collect(files, "项目一")

def _collect_p2():
    files = {
        P2_DIR/"v4_session"/"output"/"showcase_v5.mp4": P2_OUT/"showcase_v5.mp4",
        P2_DIR/"realtime_session"/"output"/"showcase_v3.mp4": P2_OUT/"showcase_v3.mp4",
        P2_DIR/"realtime_session"/"output"/"player.html": P2_OUT/"player.html",
    }
    _do_collect(files, "项目二")

def _collect_p3():
    files = {
        P3_DIR/"06-成品输出_Output"/"final_july2025.mp4": P3_OUT/"final_july2025.mp4",
    }
    _do_collect(files, "项目三")

def _do_collect(files, label):
    copied = 0
    for src, dst in files.items():
        if src.exists():
            if not dst.exists() or src.stat().st_mtime > dst.stat().st_mtime:
                shutil.copy2(src, dst)
                print(f"    📄 {dst.name} ({sz(src):.1f}MB)")
                copied += 1
            else:
                pass  # 已是最新
        else:
            print(f"    ⚠️  源不存在: {src.name}")
    if copied == 0:
        print(f"    (已是最新)")

def cmd_collect():
    print_header("汇聚所有精华到 AI视频剪辑/")
    _collect_p1()
    _collect_p2()
    _collect_p3()
    print("\n  ✅ 汇聚完成")

# ============================================================
# serve — 启动HTTP预览
# ============================================================
def cmd_serve():
    port = 9876
    print_header(f"启动预览服务器 http://127.0.0.1:{port}")
    print(f"  目录: {HERE}")
    print(f"  按 Ctrl+C 停止\n")
    subprocess.run([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"], cwd=str(HERE))

# ============================================================
# clean — 清理中间产物
# ============================================================
def cmd_clean():
    print_header("清理中间产物")
    
    # 项目一中间产物
    p1_out = P1_DIR / "video_output"
    patterns = ["clip_*.mp4", "seg_*_video.mp4", "breath_*.mp4", "concat_*.txt", "test_*.mp4", "final_concat.txt"]
    to_delete = []
    for pat in patterns:
        to_delete.extend(p1_out.glob(pat))
    
    # TTS分段
    for i in range(7):
        f = P1_DIR / f"tts_seg_{i}.mp3"
        if f.exists():
            to_delete.append(f)
    f = P1_DIR / "tts_concat.txt"
    if f.exists():
        to_delete.append(f)
    
    if to_delete:
        total = sum(sz(f) for f in to_delete)
        print(f"  项目一: {len(to_delete)}个中间文件 ({total:.0f}MB)")
        for f in to_delete:
            print(f"    🗑️  {f.name}")
        
        confirm = input(f"\n  确认删除 {len(to_delete)} 个文件? [y/N] ").strip().lower()
        if confirm == 'y':
            for f in to_delete:
                f.unlink()
            print(f"  ✅ 已删除 {len(to_delete)} 个文件")
        else:
            print("  ⏭️  跳过")
    else:
        print("  项目一: 无中间产物")

# ============================================================
# analyze — 自动质量分析（对标顶级视频）
# ============================================================
def _probe_video(path):
    """用ffprobe提取视频元数据"""
    try:
        r = subprocess.run([
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", str(path)
        ], capture_output=True, text=True, timeout=15,
           encoding="utf-8", errors="replace")
        return json.loads(r.stdout)
    except: return None

def _analyze_one(path, label):
    """分析单个视频的质量"""
    info = _probe_video(path)
    if not info:
        print(f"  ❌ {label}: 无法分析")
        return None

    fmt = info.get("format", {})
    streams = info.get("streams", [])
    vstream = next((s for s in streams if s.get("codec_type") == "video"), {})
    astream = next((s for s in streams if s.get("codec_type") == "audio"), {})

    duration = float(fmt.get("duration", 0))
    bitrate = int(fmt.get("bit_rate", 0)) // 1000
    size_mb = int(fmt.get("size", 0)) / (1024*1024)
    width = int(vstream.get("width", 0))
    height = int(vstream.get("height", 0))
    fps = eval(vstream.get("r_frame_rate", "0/1")) if "/" in str(vstream.get("r_frame_rate", "0")) else float(vstream.get("r_frame_rate", 0))
    vcodec = vstream.get("codec_name", "?")
    vprofile = vstream.get("profile", "?")
    acodec = astream.get("codec_name", "none")
    asample = int(astream.get("sample_rate", 0))
    achannels = int(astream.get("channels", 0))

    # 评分
    scores = {}
    scores["分辨率"] = (10 if width >= 1920 else 7 if width >= 1280 else 4, f"{width}×{height}")
    scores["帧率"] = (10 if fps >= 29 else 7 if fps >= 24 else 4, f"{fps:.1f}fps")
    scores["码率"] = (10 if bitrate >= 5000 else 8 if bitrate >= 1000 else 5 if bitrate >= 300 else 3, f"{bitrate}kbps")
    scores["编码"] = (10 if "High" in str(vprofile) else 7, f"{vcodec} {vprofile}")
    scores["音频"] = (10 if achannels >= 2 and asample >= 44100 else 7 if acodec != "none" else 0,
                     f"{acodec} {asample}Hz {'stereo' if achannels>=2 else 'mono' if achannels==1 else 'none'}")

    total = sum(v[0] for v in scores.values())
    max_total = len(scores) * 10

    print(f"\n  📊 {label} ({fmt_dur(duration)} / {size_mb:.1f}MB)")
    for k, (score, detail) in scores.items():
        bar = "█" * score + "░" * (10 - score)
        print(f"    {k:6s} {bar} {score}/10  {detail}")
    pct = total / max_total * 100
    grade = "A" if pct >= 85 else "B" if pct >= 70 else "C" if pct >= 55 else "D"
    print(f"    {'总分':6s} {total}/{max_total} ({pct:.0f}%) 等级: {grade}")

    # 问题检测
    issues = []
    if width < 1920: issues.append(f"分辨率不足1080p({width}×{height})")
    if fps < 24: issues.append(f"帧率过低({fps:.0f}fps)")
    if bitrate < 300: issues.append("码率过低(<300kbps)")
    if achannels < 2 and acodec != "none": issues.append("单声道音频")
    if asample > 0 and asample < 44100: issues.append(f"音频采样率偏低({asample}Hz)")
    if acodec == "none": issues.append("无音频轨")
    if duration > 0 and size_mb / (duration/60) > 500: issues.append("码率偏高，可压缩")

    if issues:
        print(f"    ⚠️  问题: {' | '.join(issues)}")
    else:
        print(f"    ✅ 无明显问题")

    return {"path": str(path), "label": label, "score": total, "max": max_total, "grade": grade, "issues": issues,
            "duration": duration, "size_mb": size_mb, "width": width, "height": height, "fps": fps}

def cmd_analyze():
    print_header("全视频质量分析")
    results = []
    videos = [
        (P1_OUT / "v16_final.mp4", "P1 完整版"),
        (P1_OUT / "v16_subtitled.mp4", "P1 字幕版"),
        (P1_OUT / "v16_no_subtitle.mp4", "P1 纯净版"),
        (P2_OUT / "showcase_v5.mp4", "P2 录屏V5"),
        (P2_OUT / "showcase_v3.mp4", "P2 录屏V3"),
        (P3_OUT / "final_july2025.mp4", "P3 相机成品"),
    ]
    for path, label in videos:
        if path.exists():
            r = _analyze_one(path, label)
            if r: results.append(r)

    if results:
        print_header("综合评估")
        for r in sorted(results, key=lambda x: x["score"], reverse=True):
            print(f"  {r['grade']} {r['score']}/{r['max']}  {r['label']} ({fmt_dur(r['duration'])})")
        avg = sum(r["score"] for r in results) / len(results)
        print(f"\n  平均分: {avg:.1f}/{results[0]['max']}")

        all_issues = []
        for r in results:
            all_issues.extend(r["issues"])
        if all_issues:
            unique = list(set(all_issues))
            print(f"\n  🔧 全局问题 ({len(unique)}个):")
            for i in unique:
                print(f"    • {i}")

    # 保存分析报告JSON
    report_path = HERE / "quality_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({"timestamp": datetime.now().isoformat(), "videos": results}, f, ensure_ascii=False, indent=2)
    print(f"\n  📄 报告已保存: {report_path}")

# ============================================================
# thumbnail — 自动生成封面图
# ============================================================
def cmd_thumbnail():
    print_header("自动生成封面图")
    videos = [
        (P1_OUT / "v16_final.mp4", P1_OUT / "cover.jpg", "P1 封面", 5),
        (P2_OUT / "showcase_v5.mp4", P2_OUT / "cover.jpg", "P2 封面", 10),
        (P3_OUT / "final_july2025.mp4", P3_OUT / "cover.jpg", "P3 封面", 30),
    ]
    for video, cover, label, seek_sec in videos:
        if not video.exists():
            print(f"  ❌ {label}: 源视频不存在")
            continue
        d = dur(video)
        t = min(seek_sec, d * 0.3) if d > 0 else 0

        # 提取关键帧
        r = subprocess.run([
            "ffmpeg", "-y", "-ss", str(t), "-i", str(video),
            "-vframes", "1", "-q:v", "2", str(cover)
        ], capture_output=True, timeout=30)
        if r.returncode == 0 and cover.exists():
            print(f"  ✅ {label}: {cover.name} ({sz(cover):.0f}KB) @ {fmt_dur(t)}")
        else:
            print(f"  ❌ {label}: 提取失败")

    print(f"\n  💡 封面已提取，可用图片编辑器叠加标题文字")

# ============================================================
# silence — 静音检测分析
# ============================================================
def cmd_silence():
    print_header("静音检测分析")
    videos = [
        (P1_OUT / "v16_final.mp4", "P1 完整版"),
        (P2_OUT / "showcase_v5.mp4", "P2 录屏V5"),
        (P3_OUT / "final_july2025.mp4", "P3 相机成品"),
    ]
    for path, label in videos:
        if not path.exists():
            continue
        print(f"\n  🔇 {label}:")
        r = subprocess.run([
            "ffmpeg", "-i", str(path), "-af",
            "silencedetect=noise=-35dB:d=1.0",
            "-f", "null", "-"
        ], capture_output=True, text=True, timeout=60, encoding="utf-8", errors="replace")

        silence_starts = []
        silence_ends = []
        for line in r.stderr.split("\n"):
            if "silence_start:" in line:
                try: silence_starts.append(float(line.split("silence_start:")[1].strip().split()[0]))
                except: pass
            if "silence_end:" in line:
                try:
                    parts = line.split("silence_end:")[1].strip().split()
                    silence_ends.append(float(parts[0]))
                except: pass

        d = dur(path)
        pairs = list(zip(silence_starts, silence_ends[:len(silence_starts)]))
        total_silence = sum(e - s for s, e in pairs)

        if pairs:
            print(f"    检测到 {len(pairs)} 段静音，总计 {total_silence:.1f}s ({total_silence/d*100:.1f}%)")
            for i, (s, e) in enumerate(pairs[:10]):
                print(f"    [{fmt_dur(s)} → {fmt_dur(e)}] {e-s:.1f}s")
            if len(pairs) > 10:
                print(f"    ... 还有 {len(pairs)-10} 段")
            if total_silence > d * 0.15:
                print(f"    ⚠️  静音占比>{total_silence/d*100:.0f}%，建议裁剪")
            else:
                print(f"    ✅ 静音占比合理")
        else:
            print(f"    ✅ 无明显静音段（>1s）")

# ============================================================
# info
# ============================================================
def cmd_info():
    print_header("Agent 视频工坊 — 管线说明")
    print("""
  全流程管线（一键触发）:
  
  ┌─────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
  │ 脚本/   │──▶│ TTS语音  │──▶│ 视觉素材 │──▶│ 视频组装 │──▶│ 后期处理 │
  │ 素材输入 │   │ edge-tts │   │ slides/  │   │ ffmpeg   │   │ 字幕+BGM │
  └─────────┘   └──────────┘   │ 录屏     │   └──────────┘   └──────────┘
                                └──────────┘
  
  命令:
    python pipeline.py status   查看所有项目状态
    python pipeline.py build1   构建项目一（B站科技视频）
    python pipeline.py build2   构建项目二（录屏智剪V5）
    python pipeline.py collect  汇聚所有精华到本目录
    python pipeline.py serve    启动HTTP预览 :9876
    python pipeline.py clean    清理中间产物
    python pipeline.py info     显示本帮助
  
  目录结构:
    AI视频剪辑/
    ├── pipeline.py              ← 统一入口（本文件）
    ├── index.html               ← 五感化前端展示
    ├── README.md
    ├── 01-B站科技视频/           ← 3视频 + 配套
    ├── 02-录屏智剪/              ← 2视频
    └── 03-相机AI剪辑/            ← 1视频
""")

# ============================================================
# main
# ============================================================
def main():
    if len(sys.argv) < 2:
        cmd_status()
        print(f"\n  💡 用法: python pipeline.py [status|build1|build2|collect|serve|clean|info]")
        return
    
    cmd = sys.argv[1].lower()
    cmds = {
        "status": cmd_status,
        "build1": cmd_build1,
        "build2": cmd_build2,
        "collect": cmd_collect,
        "serve": cmd_serve,
        "clean": cmd_clean,
        "analyze": cmd_analyze,
        "thumbnail": cmd_thumbnail,
        "silence": cmd_silence,
        "info": cmd_info,
    }
    
    if cmd in cmds:
        cmds[cmd]()
    else:
        print(f"  ❌ 未知命令: {cmd}")
        cmd_info()

if __name__ == "__main__":
    main()
