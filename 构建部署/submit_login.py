import requests, json, sys, time
from pathlib import Path

BASE = "https://cg.sanxianjiyi.com/subschool"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": BASE + "/Login/index.html",
}
SAVE_DIR = Path(__file__).parent
DATA_DIR = Path(r"e:\道\二手书\data\sanxian")
DATA_DIR.mkdir(parents=True, exist_ok=True)

CAMPUS_1_SESSID = "a082dee50c521c55304ad52dc1fe59b8"  # Already obtained via Playwright

LOGINS = [
    {"label": "campus_2", "username": "18368624112", "password": "12345678", "captcha": sys.argv[1] if len(sys.argv) > 1 else ""},
    {"label": "campus_3", "username": "15057067548", "password": "12345678", "captcha": sys.argv[2] if len(sys.argv) > 2 else ""},
]

results = {"campus_1": {"username": "15606700905", "sessid": CAMPUS_1_SESSID}}

for login in LOGINS:
    label = login["label"]
    sess_file = SAVE_DIR / ("session_" + label + ".json")
    if not sess_file.exists():
        print(label + ": no session file, skip")
        continue

    cookies = json.loads(sess_file.read_text(encoding="utf-8"))
    sess = requests.Session()
    sess.headers.update(HEADERS)
    for name, value in cookies.items():
        sess.cookies.set(name, value, domain="cg.sanxianjiyi.com", path="/")

    r = sess.post(BASE + "/Login/index.html", data={
        "username": login["username"],
        "password": login["password"],
        "verify": login["captcha"],
    }, timeout=15)

    try:
        data = r.json()
        if data.get("code") == 1:
            sessid = sess.cookies.get("PHPSESSID")
            print(label + " " + login["username"] + ": OK sessid=" + sessid)
            results[label] = {"username": login["username"], "sessid": sessid}
        else:
            print(label + " " + login["username"] + ": FAIL " + str(data.get("msg", "")))
    except Exception as e:
        print(label + " " + login["username"] + ": ERROR " + str(e))

# Verify all sessions
print("\n=== Verifying sessions ===")
sys.path.insert(0, str(Path(r"e:\道\二手书\ModularSystem\11.三鲜对接_Sanxian")))
from sanxian_client import SanxianClient

all_valid = True
for label in sorted(results.keys()):
    info = results[label]
    client = SanxianClient.from_phpsessid(info["sessid"])
    valid = client.check_login()
    if valid:
        goods = client.goods_list(limit=500)
        orders = client.school_order_list(limit=500)
        biz = client.business_list()
        cats = client.goods_type_list()
        users = client.user_list(limit=500)
        print(label + " " + info["username"] + ": VALID goods=" + str(len(goods))
              + " orders=" + str(len(orders)) + " biz=" + str(len(biz))
              + " cats=" + str(len(cats)) + " users=" + str(len(users)))
        for b in biz:
            print("  store: [" + str(b.get("business_id","")) + "] " + str(b.get("business_name","")))
        results[label]["survey"] = {
            "goods": len(goods), "orders": len(orders), "biz": len(biz),
            "cats": len(cats), "users": len(users),
            "businesses": [{"id": b.get("business_id"), "name": b.get("business_name")} for b in biz],
            "categories": [{"id": c.get("goods_type_id"), "name": c.get("goods_type_name")} for c in cats],
        }
    else:
        print(label + " " + info["username"] + ": INVALID")
        all_valid = False

# Save multi-campus state
print("\n=== Saving multi-campus config ===")
multi_state = {}
for label, info in results.items():
    multi_state[label] = {
        "username": info["username"],
        "sessid": info["sessid"],
        "cookies": [{
            "name": "PHPSESSID", "value": info["sessid"],
            "domain": ".sanxianjiyi.com", "path": "/",
            "expires": -1, "httpOnly": False, "secure": False, "sameSite": "Lax"
        }],
    }
    if "survey" in info:
        multi_state[label]["survey"] = info["survey"]

multi_path = DATA_DIR / "multi_campus_state.json"
multi_path.write_text(json.dumps(multi_state, indent=2, ensure_ascii=False), encoding="utf-8")
print("Saved: " + str(multi_path))

# Update storage_state.json for backward compatibility (campus_1)
if "campus_1" in multi_state:
    compat = {"cookies": multi_state["campus_1"]["cookies"], "origins": []}
    compat_path = DATA_DIR / "storage_state.json"
    compat_path.write_text(json.dumps(compat, indent=2), encoding="utf-8")
    print("Compat: " + str(compat_path))

if all_valid:
    print("\nALL 3 CAMPUSES VALID")
else:
    print("\nSOME CAMPUSES FAILED - check output above")
