"""Download a dancing video for hip sync testing - uses proxy for YouTube"""
import yt_dlp, sys
from pathlib import Path

OUT = Path(__file__).parent / "douyin_cache"
OUT.mkdir(exist_ok=True)

opts = {
    "format": "best[height<=480]",
    "outtmpl": str(OUT / "dance_test.%(ext)s"),
    "socket_timeout": 20,
    "proxy": "http://127.0.0.1:7890",
    "overwrites": True,
}

# Try a short dance video
urls = [
    "https://www.youtube.com/shorts/ZY3J3Y_OU0w",  # short dance
    "https://www.youtube.com/shorts/2jqG0FO4K6g",  # dance practice
]

for url in urls:
    print(f"Trying: {url}")
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "?")[:60]
            dur = info.get("duration", 0)
            print(f"OK: {title} ({dur}s)")
            break
    except Exception as e:
        print(f"Failed: {e}")

# List results
print("\n--- Videos in cache ---")
for f in sorted(OUT.iterdir()):
    if f.suffix in (".mp4", ".webm", ".mkv", ".flv"):
        print(f"  {f.name} ({f.stat().st_size // 1024}KB)")
