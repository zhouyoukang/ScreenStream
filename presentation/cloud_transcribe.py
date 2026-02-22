"""阿里云百炼 Qwen3-ASR 云端转录脚本
用法: python cloud_transcribe.py --key sk-xxx [--audio audio.wav]
原理: ffmpeg静音检测分片(≤3min) → 并行调DashScope API → 合并生成SRT
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# DashScope SDK
import dashscope
from dashscope import MultiModalConversation

CHUNK_DIR = "chunks"
MAX_DURATION = 150  # 每片最长2.5分钟(留余量,API限3分钟)
OUTPUT_SRT = "subtitle.srt"
OUTPUT_JSON = "transcript.json"


def detect_silence(audio_path, noise_threshold=-35, min_silence=0.5):
    """用 ffmpeg 检测静音段，返回静音区间列表 [(start, end), ...]"""
    cmd = [
        "ffmpeg", "-i", audio_path,
        "-af", f"silencedetect=noise={noise_threshold}dB:d={min_silence}",
        "-f", "null", "-"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    stderr = result.stderr

    silences = []
    starts = re.findall(r"silence_start: ([\d.]+)", stderr)
    ends = re.findall(r"silence_end: ([\d.]+)", stderr)
    for s, e in zip(starts, ends):
        silences.append((float(s), float(e)))
    return silences


def split_audio(audio_path, silences, max_dur=MAX_DURATION):
    """基于静音点将音频分成 ≤max_dur 秒的片段，返回 [(start, end, chunk_path), ...]"""
    os.makedirs(CHUNK_DIR, exist_ok=True)

    # 获取总时长
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", audio_path],
        capture_output=True, text=True
    )
    total_duration = float(probe.stdout.strip())

    # 构建切割点：在静音中点切
    cut_points = [0.0]
    for s, e in silences:
        mid = (s + e) / 2
        cut_points.append(mid)
    cut_points.append(total_duration)

    # 合并切割点，使每段 ≤ max_dur
    segments = []
    seg_start = 0.0
    for i in range(1, len(cut_points)):
        seg_end = cut_points[i]
        if seg_end - seg_start > max_dur and segments:
            # 当前段已超长，在上一个切割点结束
            pass
        if seg_end - seg_start > max_dur:
            # 强制在 max_dur 处切
            while seg_start < seg_end:
                chunk_end = min(seg_start + max_dur, seg_end)
                segments.append((seg_start, chunk_end))
                seg_start = chunk_end
        elif i == len(cut_points) - 1:
            segments.append((seg_start, seg_end))
        elif cut_points[i] - seg_start <= max_dur:
            continue
        else:
            # 回退到上一个切割点
            prev = cut_points[i - 1]
            if prev > seg_start:
                segments.append((seg_start, prev))
                seg_start = prev
            # 继续
            if i == len(cut_points) - 1:
                segments.append((seg_start, seg_end))

    # 简化：如果segments为空或不完整，用均匀分割
    if not segments or segments[-1][1] < total_duration - 1:
        segments = []
        pos = 0.0
        # 找最近的静音点
        while pos < total_duration:
            best_end = min(pos + max_dur, total_duration)
            # 在 [pos+max_dur*0.7, pos+max_dur] 范围内找最近的静音中点
            best_cut = best_end
            for s, e in silences:
                mid = (s + e) / 2
                if pos + max_dur * 0.5 <= mid <= pos + max_dur:
                    best_cut = mid
                    break
            segments.append((pos, best_cut))
            pos = best_cut
            if best_cut >= total_duration - 0.5:
                break

    # 导出分片
    chunks = []
    for i, (start, end) in enumerate(segments):
        chunk_path = os.path.join(CHUNK_DIR, f"chunk_{i:04d}.wav")
        duration = end - start
        if duration < 0.5:
            continue
        cmd = [
            "ffmpeg", "-y", "-i", audio_path,
            "-ss", f"{start:.3f}", "-t", f"{duration:.3f}",
            "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            chunk_path
        ]
        subprocess.run(cmd, capture_output=True)
        chunks.append((start, end, chunk_path))
        
    return chunks


def transcribe_chunk(chunk_info, api_key):
    """调用 DashScope qwen3-asr-flash 转录单个分片"""
    start, end, chunk_path = chunk_info
    abs_path = os.path.abspath(chunk_path)
    
    try:
        messages = [
            {"role": "system", "content": [{"text": ""}]},
            {"role": "user", "content": [{"audio": f"file://{abs_path}"}]}
        ]
        response = MultiModalConversation.call(
            api_key=api_key,
            model="qwen3-asr-flash",
            messages=messages,
            result_format="message",
            asr_options={"language": "zh", "enable_itn": False}
        )
        
        # 提取文本
        if response and response.output:
            choices = response.output.get("choices", [])
            if choices:
                content = choices[0].get("message", {}).get("content", [])
                if content:
                    text = content[0].get("text", "")
                    return (start, end, text.strip())
        return (start, end, "")
    except Exception as e:
        print(f"  [错误] chunk {chunk_path}: {e}")
        return (start, end, "")


def to_srt(results, output_path):
    """将结果转为 SRT 字幕文件"""
    # 按开始时间排序
    results.sort(key=lambda x: x[0])
    
    srt_lines = []
    idx = 0
    for start, end, text in results:
        if not text.strip():
            continue
        idx += 1
        
        def fmt(seconds):
            h = int(seconds // 3600)
            m = int((seconds % 3600) // 60)
            s = int(seconds % 60)
            ms = int((seconds % 1) * 1000)
            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
        
        srt_lines.append(str(idx))
        srt_lines.append(f"{fmt(start)} --> {fmt(end)}")
        srt_lines.append(text)
        srt_lines.append("")
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(srt_lines))
    print(f"SRT 字幕: {output_path} ({idx} 段)")


def main():
    parser = argparse.ArgumentParser(description="阿里云百炼 Qwen3-ASR 云端转录")
    parser.add_argument("--key", required=True, help="DashScope API Key (sk-xxx)")
    parser.add_argument("--audio", default="audio.wav", help="音频文件路径")
    parser.add_argument("--threads", type=int, default=4, help="并行线程数")
    parser.add_argument("--output", default=OUTPUT_SRT, help="SRT 输出路径")
    args = parser.parse_args()

    dashscope.base_http_api_url = 'https://dashscope.aliyuncs.com/api/v1'
    audio = args.audio
    
    if not os.path.exists(audio):
        print(f"文件不存在: {audio}")
        return

    start_time = time.time()
    
    # Step 1: 静音检测
    print("=" * 50)
    print("Step 1: 静音检测...")
    silences = detect_silence(audio)
    print(f"  检测到 {len(silences)} 个静音段")

    # Step 2: 分片
    print("=" * 50)
    print("Step 2: 音频分片 (每片≤2.5分钟)...")
    chunks = split_audio(audio, silences)
    print(f"  共 {len(chunks)} 个分片")
    for i, (s, e, p) in enumerate(chunks):
        print(f"    [{i+1}] {s:.1f}s - {e:.1f}s ({e-s:.1f}s)")

    # Step 3: 并行转录
    print("=" * 50)
    print(f"Step 3: 并行转录 ({args.threads} 线程)...")
    results = []
    completed = 0
    
    with ThreadPoolExecutor(max_workers=args.threads) as executor:
        futures = {
            executor.submit(transcribe_chunk, chunk, args.key): chunk
            for chunk in chunks
        }
        for future in as_completed(futures):
            chunk = futures[future]
            result = future.result()
            results.append(result)
            completed += 1
            start_s, end_s, text = result
            preview = text[:40] + "..." if len(text) > 40 else text
            print(f"  [{completed}/{len(chunks)}] {start_s:.0f}s-{end_s:.0f}s: {preview}")

    # Step 4: 生成 SRT
    print("=" * 50)
    print("Step 4: 生成字幕文件...")
    to_srt(results, args.output)

    # 保存 JSON
    results.sort(key=lambda x: x[0])
    json_data = [{"start": s, "end": e, "text": t} for s, e, t in results if t.strip()]
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    print(f"JSON 结果: {OUTPUT_JSON}")

    elapsed = time.time() - start_time
    print(f"\n总耗时: {elapsed/60:.1f} 分钟")


if __name__ == "__main__":
    main()
