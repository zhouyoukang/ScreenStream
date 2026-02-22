"""匹配叠加合成 — AI配音叠加录屏画面 + 真实反应穿插

核心思路:
  - hybrid段: 录屏画面 + AI配音 (内容匹配, 录屏音频静音, 零冲突)
  - 反应段: 录屏画面 + 录屏音频 (真实情感, AI不说话, 零冲突)
  - 纯AI段: AI slides + AI voice (抽象理论, slides更好看)

素材来源:
  - burst_final.mkv (9.3min, 1920x1080/30fps) — 对话A裁好的录屏精华
  - consciousness_stream/seg*.mp4 (V5) — 对话B的AI叙述段
  - burst_final.srt — 录屏字幕

输出: matched_final.mp4 (~7:20, B站发布级)
"""
import os, subprocess, time, re, json

BASE = os.path.dirname(os.path.abspath(__file__))
CS_DIR = os.path.join(BASE, "presentation", "video_output", "consciousness_stream")
WORK = os.path.join(BASE, "matched_temp")
OUTPUT_RAW = os.path.join(WORK, "matched_raw.mp4")
OUTPUT = os.path.join(BASE, "matched_final.mp4")

RECORDING = os.path.join(BASE, "burst_final.mkv")
SRT_SRC = os.path.join(BASE, "burst_final.srt")

W, H, FPS = 1920, 1080, 25

# AI叙述段 (对话B V5)
AI_SEGS = {
    "seg0": "seg0_cold_open.mp4",
    "seg1": "seg1_method_result.mp4",
    "seg2": "seg2_why_it_works.mp4",
    "seg3": "seg3_mirror_blindspot.mp4",
    "seg4": "seg4_step_four.mp4",
    "seg5": "seg5_danger_dao.mp4",
    "seg6": "seg6_closing.mp4",
}

TITLE_CARD = os.path.join(CS_DIR, "title_card_audio.mp4")
END_CARD = os.path.join(CS_DIR, "end_card_audio.mp4")
GAP = os.path.join(CS_DIR, "seg_gap_audio.mp4")


def run(cmd, desc=""):
    if desc:
        print(f"  -> {desc}")
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if r.returncode != 0:
        err = (r.stderr or "")[-500:]
        print(f"  [ERR] {err}")
        return False, r
    return True, r


def get_dur(p):
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
        capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except:
        return 0.0


def ai_path(name):
    return os.path.join(CS_DIR, AI_SEGS[name])


def step1_create_hybrid_segments():
    """创建hybrid段: 录屏视频 + AI音频"""
    print("=" * 60)
    print("Step 1: 创建 hybrid 段 (录屏画面 + AI配音)")

    hybrids = []

    # --- hybrid_seg1: AI说"打开微信957ms" + 录屏展示实际操作 ---
    # burst_final.mkv 1:00-1:37 = 实际演示打开微信/设置
    # seg1 AI音频 = 37.5s
    seg1_dur = get_dur(ai_path("seg1"))
    out1 = os.path.join(WORK, "hybrid_seg1.mp4")

    # 提取录屏视频(无音频) + 缩放到25fps + 色彩校正 + fade
    # 提取AI音频
    # 合并: 录屏视频 + AI音频
    fo1 = max(0.5, seg1_dur - 0.5)
    ok, _ = run([
        "ffmpeg", "-y",
        "-ss", "60", "-i", RECORDING, "-t", str(seg1_dur),  # 录屏视频 1:00起
        "-i", ai_path("seg1"),                                # AI音频源
        "-map", "0:v", "-map", "1:a",                         # 录屏视频 + AI音频
        "-vf", (
            f"fps={FPS},"
            f"eq=brightness=0.04:contrast=1.08:saturation=1.12,"
            f"fade=in:st=0:d=0.5:color=black,"
            f"fade=out:st={fo1}:d=0.5:color=black"
        ),
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "copy",
        "-shortest",
        "-movflags", "+faststart",
        out1
    ], f"hybrid_seg1: 录屏[1:00-1:37] + AI声'打开微信957ms' ({seg1_dur:.0f}s)")

    if ok and os.path.exists(out1):
        d = get_dur(out1)
        sz = os.path.getsize(out1) / 1024 / 1024
        print(f"    OK {sz:.1f}MB, {d:.1f}s")
        hybrids.append(("hybrid_seg1", out1))
    else:
        print(f"    FAIL, 回退到纯AI seg1")
        hybrids.append(("seg1", ai_path("seg1")))

    return hybrids


def step2_create_reaction_clips():
    """从录屏裁出真实反应片段 (保留录屏原声)"""
    print("=" * 60)
    print("Step 2: 裁出真实反应片段 (录屏画面+音频)")

    reactions = []
    clips = [
        # (name, start_sec, duration, description)
        ("reaction_A", 240, 15, "碰撞高点: 我靠牛逼 [4:00-4:15]"),
        ("reaction_B", 255, 15, "盲区反应: 你叫别人不要做的事 [4:15-4:30]"),
        ("reaction_C", 510, 46, "高潮结尾: 方法论自证+牛逼 [8:30-9:16]"),
    ]

    for name, ss, dur, desc in clips:
        out = os.path.join(WORK, f"{name}.mp4")
        fo = max(0.5, dur - 0.5)

        # 添加字幕烧入
        srt_escaped = SRT_SRC.replace("\\", "/").replace(":", "\\:")
        vf = (
            f"fps={FPS},"
            f"eq=brightness=0.04:contrast=1.08:saturation=1.12,"
            f"subtitles='{srt_escaped}':force_style='FontName=Microsoft YaHei,"
            f"FontSize=22,PrimaryColour=&H00FFFFFF,OutlineColour=&H80000000,"
            f"BackColour=&H80000000,Outline=2,Shadow=1,MarginV=40,"
            f"Alignment=2,BorderStyle=3',"
            f"fade=in:st=0:d=0.5:color=black,"
            f"fade=out:st={fo}:d=0.5:color=black"
        )

        # 先提取原始片段
        raw_out = os.path.join(WORK, f"{name}_raw.mp4")
        ok, _ = run([
            "ffmpeg", "-y", "-ss", str(ss), "-i", RECORDING,
            "-t", str(dur),
            "-vf", vf,
            "-af", f"afade=in:st=0:d=0.3,afade=out:st={fo}:d=0.5",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
            "-r", str(FPS), "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            raw_out
        ], f"{name}: {desc} ({dur}s)")

        # 对录屏片段单独loudnorm到-17 LUFS，匹配AI叙述段音量
        if ok and os.path.exists(raw_out):
            ok, _ = run([
                "ffmpeg", "-y", "-i", raw_out,
                "-c:v", "copy",
                "-af", "loudnorm=I=-17:TP=-1.5:LRA=11",
                "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                "-movflags", "+faststart",
                out
            ], f"{name}: loudnorm -> -17 LUFS")

        if ok and os.path.exists(out):
            d = get_dur(out)
            sz = os.path.getsize(out) / 1024 / 1024
            print(f"    OK {sz:.1f}MB, {d:.1f}s")
            reactions.append((name, out))
        else:
            print(f"    SKIP {name}")

    return reactions


def step3_concat_all(hybrids, reactions):
    """拼接最终视频: 标题卡 + 混合结构 + 结尾卡"""
    print("=" * 60)
    print("Step 3: 拼接最终视频")

    # 构建拼接顺序
    segments = []
    gap_ok = os.path.exists(GAP)

    def add(path, label=""):
        if os.path.exists(path):
            segments.append((label, path))
            if gap_ok:
                segments.append(("gap", GAP))
        else:
            print(f"  [WARN] 缺少: {label}")

    # 查找helper
    hybrid_map = {name: path for name, path in hybrids}
    reaction_map = {name: path for name, path in reactions}

    # === 拼接结构 ===
    # seg0 直接开场（去掉暗黑标题卡，B站前3秒留人）: 纯AI 冷开场 (抽象, slides最好)
    add(ai_path("seg0"), "seg0 纯AI: 冷开场")

    # seg1: HYBRID — 录屏画面 + AI配音 "打开微信957ms"
    if "hybrid_seg1" in hybrid_map:
        add(hybrid_map["hybrid_seg1"], "seg1 HYBRID: 录屏+AI声'打开微信'")
    else:
        add(ai_path("seg1"), "seg1 纯AI: 方法+结果")

    # 反应A: 碰撞高点 (真实反应)
    if "reaction_A" in reaction_map:
        add(reaction_map["reaction_A"], "反应A: 碰撞高点")

    # seg2: 纯AI (理论, slides有架构图)
    add(ai_path("seg2"), "seg2 纯AI: 为什么有效")

    # seg3: 纯AI (镜子理论, slides更有意境)
    add(ai_path("seg3"), "seg3 纯AI: 镜子与盲区")

    # 反应B: 盲区发现反应
    if "reaction_B" in reaction_map:
        add(reaction_map["reaction_B"], "反应B: 盲区反应")

    # seg4: 纯AI (数据对比, slides清晰)
    add(ai_path("seg4"), "seg4 纯AI: 失败了就修")

    # seg5: 纯AI (道德经, slides太美不换)
    add(ai_path("seg5"), "seg5 纯AI: 危险与道")

    # seg6: 纯AI (方法论总结)
    add(ai_path("seg6"), "seg6 纯AI: 收尾")

    # 反应C: 高潮结尾 (录屏真实反应)
    if "reaction_C" in reaction_map:
        add(reaction_map["reaction_C"], "反应C: 高潮结尾'牛逼'")

    # 结尾卡 (去掉最后一个gap)
    if segments and segments[-1][0] == "gap":
        segments.pop()
    segments.append(("结尾卡", END_CARD))

    # 验证
    missing = [(label, p) for label, p in segments if not os.path.exists(p)]
    if missing:
        print(f"  [ERR] 缺少 {len(missing)} 个文件:")
        for label, p in missing:
            print(f"    - {label}: {p}")
        return False

    # 写concat
    concat_file = os.path.join(WORK, "concat_matched.txt")
    with open(concat_file, "w", encoding="utf-8") as f:
        for label, seg in segments:
            safe = seg.replace("\\", "/")
            f.write(f"file '{safe}'\n")

    # 打印结构
    total_dur = 0
    print(f"\n  拼接 {len(segments)} 个片段:")
    for i, (label, seg) in enumerate(segments):
        dur = get_dur(seg)
        total_dur += dur
        tag = "HYBRID" if "HYBRID" in label else ("REC" if "反应" in label else ("AI" if "纯AI" in label else "..."))
        name = os.path.basename(seg)
        print(f"    {i+1:2d}. [{tag:6s}] {name:32s} {dur:5.1f}s  {label}")
    print(f"\n  预计总时长: {int(total_dur//60)}:{int(total_dur%60):02d} ({total_dur:.0f}s)")

    # 拼接
    ok, _ = run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", concat_file,
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        "-r", str(FPS), "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        OUTPUT_RAW
    ], "拼接 -> matched_raw.mp4")

    return ok


def step4_loudnorm():
    """EBU R128 loudnorm 2-pass + 棕噪声氛围"""
    print("=" * 60)
    print("Step 4: EBU R128 loudnorm 2-pass")

    if not os.path.exists(OUTPUT_RAW):
        print("  [ERR] matched_raw.mp4 不存在")
        return False

    # Pass 1
    print("  Pass 1: 测量...")
    _, r = run([
        "ffmpeg", "-y", "-i", OUTPUT_RAW,
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json",
        "-f", "null", "-"
    ])

    stderr = r.stderr or ""
    json_match = re.search(r'\{[^{}]*"input_i"[^{}]*\}', stderr)
    if not json_match:
        print("  [WARN] 2-pass失败, 用单遍")
        ok, _ = run([
            "ffmpeg", "-y", "-i", OUTPUT_RAW,
            "-c:v", "copy",
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-movflags", "+faststart", OUTPUT
        ], "单遍 loudnorm")
        return ok

    params = json.loads(json_match.group())
    print(f"    输入: {params.get('input_i','?')} LUFS, 峰值: {params.get('input_tp','?')} dBTP")

    # Pass 2 + 极微弱棕噪声
    af = (
        f"loudnorm=I=-16:TP=-1.5:LRA=11:"
        f"measured_I={params['input_i']}:"
        f"measured_TP={params['input_tp']}:"
        f"measured_LRA={params['input_lra']}:"
        f"measured_thresh={params['input_thresh']}:"
        f"offset={params['target_offset']}:"
        f"linear=true"
    )

    ok, _ = run([
        "ffmpeg", "-y",
        "-i", OUTPUT_RAW,
        "-f", "lavfi", "-i", "anoisesrc=color=brown:amplitude=0.0006:duration=600",
        "-filter_complex",
        f"[0:a]{af}[norm]; [1:a]atrim=0:duration=600[amb]; [norm][amb]amix=inputs=2:weights=1 0.06:duration=shortest[out]",
        "-map", "0:v", "-map", "[out]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart",
        OUTPUT
    ], "Pass 2: 均衡 + 氛围音")

    return ok


def main():
    t0 = time.time()
    os.makedirs(WORK, exist_ok=True)

    print("=" * 60)
    print("匹配叠加合成 — AI配音叠加录屏 + 真实反应穿插")
    print(f"输出: {OUTPUT}")
    print("=" * 60)

    # 检查素材
    ai_ok = sum(1 for s in AI_SEGS.values() if os.path.exists(os.path.join(CS_DIR, s)))
    rec_ok = os.path.exists(RECORDING)
    srt_ok = os.path.exists(SRT_SRC)
    print(f"  AI叙述段: {ai_ok}/{len(AI_SEGS)}")
    print(f"  录屏精华: {'OK' if rec_ok else 'MISSING'} ({RECORDING})")
    print(f"  SRT字幕: {'OK' if srt_ok else 'MISSING'}")

    if not rec_ok:
        print("  [FATAL] 录屏文件不存在!")
        return

    # Step 1: 创建hybrid段 (录屏视频 + AI音频)
    hybrids = step1_create_hybrid_segments()
    print(f"  hybrid段: {len(hybrids)} 个")

    # Step 2: 裁出真实反应片段
    reactions = step2_create_reaction_clips()
    print(f"  反应片段: {len(reactions)} 个")

    # Step 3: 拼接
    ok = step3_concat_all(hybrids, reactions)
    if not ok:
        print("FAILED at Step 3")
        return

    # Step 4: loudnorm
    ok = step4_loudnorm()

    elapsed = time.time() - t0
    print("\n" + "=" * 60)
    if ok and os.path.exists(OUTPUT):
        dur = get_dur(OUTPUT)
        sz = os.path.getsize(OUTPUT) / 1024 / 1024
        print("DONE!")
        print(f"  文件: {OUTPUT}")
        print(f"  时长: {int(dur//60)}:{int(dur%60):02d} ({dur:.1f}s)")
        print(f"  大小: {sz:.1f} MB")
        print(f"  耗时: {elapsed:.1f}s")
        print(f"  结构: hybrid叠加 + 纯AI + 真实反应 | 零声音冲突")
    else:
        print("FAILED")
    print("=" * 60)


if __name__ == "__main__":
    main()

