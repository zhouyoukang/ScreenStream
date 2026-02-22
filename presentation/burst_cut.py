"""爆发点精华版 — 只留最炸裂的6段 + 1.3x加速 + 1080p + NVENC
目标: 6小时原片 → ~9分钟极致精华
"""
import os, subprocess, time, sys, re, json
from concurrent.futures import ThreadPoolExecutor, as_completed
import dashscope
from dashscope import MultiModalConversation

VIDEO1 = "2026-02-18 19-17-54.mkv"
VIDEO2 = "2026-02-18 21-15-31.mkv"
WORK = "burst_temp"
RAW_CONCAT = os.path.join(WORK, "raw_concat.mkv")
OUTPUT = "burst_final.mkv"
SRT_FILE = "burst_final.srt"
SPEED = 1.3  # 1.3x 加速（观众最舒适节奏）
THREADS = 8
API_KEY = sys.argv[1] if len(sys.argv) > 1 else ""

# ==================== 6段绝对爆发点 ====================
# 严选标准: 视觉冲击 / 情绪巅峰 / 金句密度最高的段
SEGMENTS = [
    # 1. HOOK — 开场（90s精简版）
    ("01_hook", VIDEO1, 0, 90,
     "开场：意识流编程，AI的话击中了我"),

    # 2. ACTION — 手机Demo（最直观的视觉冲击）
    ("02_demo", VIDEO1, 1865, 1968,
     "实操Demo：打开微信成功/设置失败"),

    # 3. WOW — MCP回环突破（碰撞最高点）
    ("03_mcp", VIDEO1, 2170, 2290,
     "MCP回环突破：碰撞高点"),

    # 4. PEAK — 盲区发现（情绪巅峰）
    ("04_blind", VIDEO1, 5517, 5650,
     "盲区发现：你在替另一个AI思考"),

    # 5. GOLD — 预防比修复贵四倍（方法论金句）
    ("05_method", VIDEO1, 6117, 6270,
     "方法论：预防比修复贵四倍"),

    # 6. CLOSE — 自我验证收尾（完美句号）
    ("06_close", VIDEO1, 6867, 6975,
     "收尾：用自己的过程求证过程"),
]


def run(cmd, desc=""):
    if desc: print(f"  -> {desc}")
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if r.returncode != 0:
        print(f"  [ERR] {(r.stderr or '')[-300:]}")
    return r

def get_dur(p):
    r = subprocess.run(["ffprobe","-v","quiet","-show_entries","format=duration","-of","csv=p=0",p],
                       capture_output=True, text=True)
    try: return float(r.stdout.strip())
    except: return 0.0

def fmt(s):
    return f"{int(s//3600):02d}:{int(s%3600//60):02d}:{int(s%60):02d}"

def srt_ts(sec):
    h=int(sec//3600); m=int((sec%3600)//60); s=sec%60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".",",")


def main():
    t0 = time.time()
    os.makedirs(WORK, exist_ok=True)

    raw_total = sum(s[3]-s[2] for s in SEGMENTS)
    final_est = raw_total / SPEED
    print("=" * 55)
    print(f"爆发点精华版 — {len(SEGMENTS)}段 x {SPEED}x加速")
    print(f"原片: {fmt(raw_total)} → 预计: {fmt(final_est)}")
    print(f"编码: h264_nvenc (GPU) + 1080p降分辨率")
    print(f"输出: {OUTPUT}")
    print("=" * 55)

    # ===== Step 1: copy模式裁剪 =====
    print("\n[Step 1] 裁剪爆发段 (copy模式)")
    parts = []
    for name, src, ss, ee, desc in SEGMENTS:
        out = os.path.join(WORK, f"{name}.mkv")
        r = run(["ffmpeg","-y","-ss",str(ss),"-i",src,"-t",str(ee-ss),
                 "-c","copy","-avoid_negative_ts","make_zero",out],
                f"{name}: {ee-ss}s")
        if r.returncode == 0 and os.path.exists(out):
            d = get_dur(out)
            print(f"    OK {d:.1f}s")
            parts.append(out)

    # ===== Step 2: copy拼接原始段 =====
    print(f"\n[Step 2] 拼接 {len(parts)} 段")
    cf = os.path.join(WORK, "concat.txt")
    with open(cf,"w",encoding="utf-8") as f:
        for p in parts: f.write(f"file '{os.path.basename(p)}'\n")
    run(["ffmpeg","-y","-f","concat","-safe","0",
         "-i",os.path.abspath(cf),"-c","copy",os.path.abspath(RAW_CONCAT)],
        "拼接原始段")
    raw_dur = get_dur(RAW_CONCAT)
    print(f"    原始拼接: {fmt(raw_dur)}")

    # ===== Step 3: 加速 + 降分辨率 + 音频均衡 (单遍NVENC) =====
    print(f"\n[Step 3] {SPEED}x加速 + 1080p + loudnorm (NVENC)")

    # 先测量 loudnorm 参数
    r = run(["ffmpeg","-y","-i",RAW_CONCAT,
             "-af","loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json",
             "-f","null","-"], "测量音频响度")
    
    # 提取 loudnorm JSON
    stderr = r.stderr or ""
    json_match = re.search(r'\{[^{}]*"input_i"[^{}]*\}', stderr)
    
    if json_match:
        params = json.loads(json_match.group())
        loudnorm_filter = (
            f"loudnorm=I=-16:TP=-1.5:LRA=11:"
            f"measured_I={params['input_i']}:"
            f"measured_TP={params['input_tp']}:"
            f"measured_LRA={params['input_lra']}:"
            f"measured_thresh={params['input_thresh']}:"
            f"offset={params['target_offset']}:"
            f"linear=true"
        )
    else:
        loudnorm_filter = "loudnorm=I=-16:TP=-1.5:LRA=11"

    # 单遍完成: 加速 + 缩放 + 音频均衡
    vf = f"setpts=PTS/{SPEED},scale=1920:1080:flags=lanczos"
    af = f"atempo={SPEED},{loudnorm_filter}"

    run(["ffmpeg","-y","-i",RAW_CONCAT,
         "-vf",vf,
         "-af",af,
         "-c:v","h264_nvenc","-preset","p4","-cq","22","-b:v","8M",
         "-c:a","aac","-b:a","192k","-ar","48000",
         "-movflags","+faststart",
         OUTPUT], f"NVENC编码 {SPEED}x + 1080p")

    if not os.path.exists(OUTPUT) or os.path.getsize(OUTPUT) == 0:
        print("  NVENC失败，回退到 libx264 ultrafast")
        run(["ffmpeg","-y","-i",RAW_CONCAT,
             "-vf",vf,"-af",af,
             "-c:v","libx264","-preset","ultrafast","-crf","20",
             "-c:a","aac","-b:a","192k",
             "-movflags","+faststart",
             OUTPUT], "libx264 ultrafast 回退")

    final_dur = get_dur(OUTPUT)
    final_sz = os.path.getsize(OUTPUT) / 1024 / 1024 if os.path.exists(OUTPUT) else 0
    print(f"    结果: {fmt(final_dur)} | {final_sz:.0f}MB")

    # ===== Step 4: 提取音频 + 30s分片转录 + SRT =====
    if API_KEY:
        print(f"\n[Step 4] 字幕转录 (qwen3-asr-flash)")
        
        # 提取加速后的音频
        audio_wav = os.path.join(WORK, "burst_audio.wav")
        run(["ffmpeg","-y","-i",OUTPUT,"-vn","-acodec","pcm_s16le",
             "-ar","16000","-ac","1",audio_wav], "提取音频")
        
        audio_dur = get_dur(audio_wav)
        chunk_dir = os.path.join(WORK, "srt_chunks")
        os.makedirs(chunk_dir, exist_ok=True)
        
        # 30s分片
        chunks = []
        pos = 0.0; idx = 0
        while pos < audio_dur:
            end = min(pos + 30, audio_dur)
            cp = os.path.join(chunk_dir, f"c_{idx:04d}.wav")
            run(["ffmpeg","-y","-ss",str(pos),"-i",audio_wav,
                 "-t",str(end-pos),"-acodec","pcm_s16le","-ar","16000","-ac","1",cp])
            if os.path.exists(cp) and os.path.getsize(cp) > 1000:
                chunks.append((pos, end, cp))
            pos = end; idx += 1
        print(f"    分片: {len(chunks)} 个")

        # 并行转录
        def transcribe(s, e, path, i, n):
            msgs = [{"role":"user","content":[{"audio":path}]}]
            for retry in range(3):
                try:
                    resp = MultiModalConversation.call(
                        api_key=API_KEY, model="qwen3-asr-flash",
                        messages=msgs, result_format="message",
                        asr_options={"language":"zh","enable_itn":False})
                    if resp and resp.output and resp.output.choices:
                        txt = resp.output.choices[0].message.content[0].get("text","").strip()
                        if txt:
                            print(f"  [{i+1}/{n}] {s:.0f}s: {txt[:50]}...")
                            return (s, e, txt)
                    break
                except:
                    if retry < 2: time.sleep(2)
            return (s, e, "")

        results = []
        with ThreadPoolExecutor(max_workers=THREADS) as pool:
            futs = {pool.submit(transcribe, s, e, p, i, len(chunks)): i
                    for i, (s, e, p) in enumerate(chunks)}
            for f in as_completed(futs):
                r = f.result()
                if r and r[2]: results.append(r)
        results.sort(key=lambda x: x[0])

        # 生成 SRT
        with open(SRT_FILE, "w", encoding="utf-8") as f:
            si = 1
            for s, e, txt in results:
                if re.match(r'^[嗯啊哦呃。，、\s]+$', txt.strip()): continue
                f.write(f"{si}\n{srt_ts(s)} --> {srt_ts(e)}\n{txt.strip()}\n\n")
                si += 1
        print(f"    字幕: {si-1} 条 → {SRT_FILE}")

        # 嵌入字幕
        final_with_srt = OUTPUT.replace(".mkv", "_sub.mkv")
        run(["ffmpeg","-y","-i",OUTPUT,"-i",SRT_FILE,
             "-c:v","copy","-c:a","copy","-c:s","srt",
             "-metadata:s:s:0","language=chi",
             "-metadata:s:s:0","title=字幕",
             final_with_srt], "嵌入字幕")
        if os.path.exists(final_with_srt):
            os.replace(final_with_srt, OUTPUT)
            print(f"    字幕已嵌入 {OUTPUT}")

    # ===== 完成 =====
    elapsed = time.time() - t0
    print("\n" + "=" * 55)
    if os.path.exists(OUTPUT):
        d = get_dur(OUTPUT); sz = os.path.getsize(OUTPUT)/1024/1024
        orig = 6975 + 14918
        print(f"DONE!")
        print(f"  文件: {OUTPUT}")
        print(f"  时长: {fmt(d)} (原片6h的{d/orig*100:.1f}%)")
        print(f"  大小: {sz:.0f}MB")
        print(f"  加速: {SPEED}x | 分辨率: 1080p | 编码: NVENC")
        print(f"  字幕: {SRT_FILE}")
        print(f"  耗时: {elapsed:.1f}s")
    print("=" * 55)

    # 章节
    print("\n章节:")
    off = 0.0
    for name, src, ss, ee, desc in SEGMENTS:
        sp = os.path.join(WORK, f"{name}.mkv")
        if os.path.exists(sp):
            sd = get_dur(sp) / SPEED
            print(f"  {fmt(off)} {desc}")
            off += sd


if __name__ == "__main__":
    main()
