"""Download a Douyin dancing video for hip sync testing"""
import yt_dlp, os, glob
from pathlib import Path

OUT_DIR = Path(__file__).parent / "douyin_cache"
OUT_DIR.mkdir(exist_ok=True)

# Try multiple popular dancing video URLs
DANCE_URLS = [
    "https://www.douyin.com/video/7448966498168498470",
    "https://www.douyin.com/video/7320686498232742182",
    "https://www.douyin.com/video/7356543210419875083",
]

opts = {
    "format": "best[height<=720]",
    "outtmpl": str(OUT_DIR / "dance_%(id)s.%(ext)s"),
    "quiet": False,
    "no_warnings": False,
    "socket_timeout": 15,
    "retries": 2,
}

for url in DANCE_URLS:
    print(f"\n>>> Trying: {url}")
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            vid_id = info.get("id", "unknown")
            title = info.get("title", "?")[:60]
            dur = info.get("duration", 0)
            print(f"    OK: {title} ({dur}s)")
            # Find the downloaded file
            for f in OUT_DIR.glob(f"dance_{vid_id}.*"):
                print(f"    File: {f.name} ({f.stat().st_size // 1024}KB)")
            break
    except Exception as e:
        print(f"    Failed: {e}")
        continue

# List all videos in cache
print("\n--- Cache contents ---")
for f in sorted(OUT_DIR.iterdir()):
    if f.suffix in ('.mp4', '.webm', '.mkv', '.flv'):
        print(f"  {f.name} ({f.stat().st_size // 1024}KB)")
