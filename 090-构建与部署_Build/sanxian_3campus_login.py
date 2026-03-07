#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[已废弃] 三校区自动登录 — 用Playwright获取验证码+自动提交

⚠️ 此脚本已被 ModularSystem/11.三鲜对接_Sanxian/ 下的模块替代:
  - session_manager.py — SessionManager + OCR自动登录 + 心跳保活
  - campus_login.py — CLI工具
  - api_routes.py — FastAPI端点 (/api/sanxian/session/*)

请勿使用此脚本。正确用法:
  cd e:\\道\\二手书
  python ModularSystem/11.三鲜对接_Sanxian/campus_login.py auto
"""
import json, time, sys
from pathlib import Path

import requests

BASE = "https://cg.sanxianjiyi.com/subschool"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": f"{BASE}/Login/index.html",
}
DATA_DIR = Path(r"e:\道\二手书\data\sanxian")
DATA_DIR.mkdir(parents=True, exist_ok=True)

ACCOUNTS = [
    {"username": "15606700905", "password": "12345678", "label": "campus_1"},
    {"username": "18368624112", "password": "12345678", "label": "campus_2"},
    {"username": "15057067548", "password": "12345678", "label": "campus_3"},
]


def login_one(username, password, label, sessid_override=None):
    """用已知PHPSESSID或新session登录一个校区"""
    if sessid_override:
        # 直接用已有的PHPSESSID验证
        sess = requests.Session()
        sess.headers.update(HEADERS)
        sess.cookies.set("PHPSESSID", sessid_override, domain="cg.sanxianjiyi.com", path="/")
        try:
            r = sess.post(f"{BASE}/ZhGoods/index", data={"page": 1, "limit": 1, "offset": 0}, timeout=15)
            data = r.json()
            if data.get("rows"):
                return sessid_override
        except Exception:
            pass
    return None


def prepare_and_login_via_requests(username, password, label):
    """通过requests获取验证码图片，返回(session, captcha_path)"""
    sess = requests.Session()
    sess.headers.update(HEADERS)
    sess.get(f"{BASE}/Login/index.html", timeout=10)
    captcha_resp = sess.get(f"{BASE}/Login/verify.html", timeout=10)
    captcha_path = DATA_DIR / f"captcha_{label}.png"
    captcha_path.write_bytes(captcha_resp.content)

    # Save session cookies
    cookies = {c.name: c.value for c in sess.cookies}
    sess_file = DATA_DIR / f"_session_{label}.json"
    sess_file.write_text(json.dumps(cookies), encoding="utf-8")

    return sess, captcha_path


def submit_login(label, username, password, captcha_code):
    """提交登录"""
    sess_file = DATA_DIR / f"_session_{label}.json"
    if not sess_file.exists():
        return None

    cookies = json.loads(sess_file.read_text(encoding="utf-8"))
    sess = requests.Session()
    sess.headers.update(HEADERS)
    for name, value in cookies.items():
        sess.cookies.set(name, value, domain="cg.sanxianjiyi.com", path="/")

    r = sess.post(f"{BASE}/Login/index.html", data={
        "username": username, "password": password, "verify": captcha_code,
    }, timeout=10)

    try:
        data = r.json()
        if data.get("code") == 1:
            return sess.cookies.get("PHPSESSID")
    except Exception:
        pass
    return None


def survey_campus(label, sessid):
    """探查校区数据"""
    sys.path.insert(0, str(Path(r"e:\道\二手书\ModularSystem\11.三鲜对接_Sanxian")))
    from sanxian_client import SanxianClient

    client = SanxianClient.from_phpsessid(sessid)
    if not client.check_login():
        return None

    goods = client.goods_list(limit=500)
    orders = client.school_order_list(limit=500)
    businesses = client.business_list()
    categories = client.goods_type_list()
    users = client.user_list(limit=500)

    return {
        "label": label,
        "sessid": sessid,
        "goods_count": len(goods),
        "orders_count": len(orders),
        "business_count": len(businesses),
        "category_count": len(categories),
        "user_count": len(users),
        "businesses": [{"id": b.get("business_id"), "name": b.get("business_name")} for b in businesses],
        "categories": [{"id": c.get("goods_type_id"), "name": c.get("goods_type_name")} for c in categories],
        "goods_sample": goods[:3],
        "orders_sample": orders[:3],
    }


def save_multi_campus(results):
    """保存多校区配置"""
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

    # Save multi-campus state
    multi_path = DATA_DIR / "multi_campus_state.json"
    multi_path.write_text(json.dumps(multi_state, indent=2, ensure_ascii=False), encoding="utf-8")

    # Also update storage_state.json with campus_1 for backward compatibility
    if "campus_1" in multi_state:
        compat = {"cookies": multi_state["campus_1"]["cookies"], "origins": []}
        (DATA_DIR / "storage_state.json").write_text(json.dumps(compat, indent=2), encoding="utf-8")

    print(f"Multi-campus config saved: {multi_path}")
    return multi_path


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "prepare"

    if mode == "prepare":
        print("=== Preparing captchas for 3 campuses ===")
        for acc in ACCOUNTS:
            sess, path = prepare_and_login_via_requests(acc["username"], acc["password"], acc["label"])
            print(f"  [{acc['label']}] {acc['username']} -> {path}")
        print("\nCaptcha images saved. Run with: python script.py login <c1> <c2> <c3>")

    elif mode == "login":
        codes = sys.argv[2:5]
        if len(codes) != 3:
            print("Need 3 captcha codes")
            sys.exit(1)

        results = {}
        for i, acc in enumerate(ACCOUNTS):
            sessid = submit_login(acc["label"], acc["username"], acc["password"], codes[i])
            if sessid:
                print(f"  [{acc['label']}] {acc['username']}: LOGIN OK, PHPSESSID={sessid}")
                results[acc["label"]] = {"username": acc["username"], "sessid": sessid}
            else:
                print(f"  [{acc['label']}] {acc['username']}: LOGIN FAILED")

        if results:
            save_multi_campus(results)

        # Survey
        for label, info in results.items():
            s = survey_campus(label, info["sessid"])
            if s:
                print(f"\n--- {label} ({info['username']}) ---")
                print(f"  Goods: {s['goods_count']}, Orders: {s['orders_count']}, "
                      f"Biz: {s['business_count']}, Cat: {s['category_count']}, Users: {s['user_count']}")
                for b in s["businesses"]:
                    print(f"    Store: [{b['id']}] {b['name']}")

    elif mode == "survey":
        # Survey with existing sessids
        multi = json.loads((DATA_DIR / "multi_campus_state.json").read_text(encoding="utf-8"))
        for label, info in multi.items():
            s = survey_campus(label, info["sessid"])
            if s:
                print(f"\n--- {label} ({info['username']}) ---")
                print(f"  Goods: {s['goods_count']}, Orders: {s['orders_count']}, "
                      f"Biz: {s['business_count']}, Cat: {s['category_count']}, Users: {s['user_count']}")
