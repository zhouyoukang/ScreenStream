import requests, json
from pathlib import Path

BASE = "https://cg.sanxianjiyi.com/subschool"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": BASE + "/Login/index.html",
}
SAVE_DIR = Path(__file__).parent
ACCOUNTS = [
    {"username": "18368624112", "label": "campus_2"},
    {"username": "15057067548", "label": "campus_3"},
]

for acc in ACCOUNTS:
    sess = requests.Session()
    sess.headers.update(HEADERS)
    sess.get(BASE + "/Login/index.html", timeout=10)
    r = sess.get(BASE + "/Login/verify.html", timeout=10)
    label = acc["label"]
    img_path = SAVE_DIR / ("captcha_" + label + ".png")
    img_path.write_bytes(r.content)
    cookies = {c.name: c.value for c in sess.cookies}
    sess_path = SAVE_DIR / ("session_" + label + ".json")
    sess_path.write_text(json.dumps(cookies), encoding="utf-8")
    print(label, acc["username"], "PHPSESSID=" + cookies.get("PHPSESSID", "?"), img_path.name)

print("Done - check captcha images")
