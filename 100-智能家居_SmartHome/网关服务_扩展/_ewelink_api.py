"""CoolKit v2 API - login and investigate device 10022cf6a2"""
import httpx
import hashlib
import hmac
import json
import time
import asyncio
import base64

APP_ID = "R8Oq3y0eSZSYdKccHlrQzT1ACCOUT9Gv"
APP_SECRET = "1ve5Qk9GXfUhKAn1svnKwpAlxXkMarru"
BASE = "https://cn-apia.coolkit.cn"
PHONE = "8618368624112"
PASSWORD = "zhouyoukang1122"
DEVICE_ID = "10022cf6a2"

def sign(payload: str) -> str:
    dig = hmac.new(APP_SECRET.encode(), payload.encode(), hashlib.sha256).digest()
    return base64.b64encode(dig).decode()

def base_headers():
    return {
        "X-CK-Appid": APP_ID,
        "X-CK-Nonce": "abcd1234",
        "Content-Type": "application/json",
    }

async def main():
    async with httpx.AsyncClient(timeout=15, verify=False) as client:
        # 1. Login
        print("=== Login ===")
        body = {"countryCode": "+86", "password": PASSWORD, "phoneNumber": "+" + PHONE}
        body_str = json.dumps(body, separators=(",", ":"))
        headers = base_headers()
        headers["Authorization"] = f"Sign {sign(body_str)}"
        
        r = await client.post(f"{BASE}/v2/user/login", content=body_str, headers=headers)
        data = r.json()
        print(f"  error={data.get('error')}, msg={data.get('msg','')}")
        
        if data.get("error") != 0:
            print(f"  FULL: {json.dumps(data, ensure_ascii=False)[:500]}")
            return
        
        at = data["data"]["at"]
        user_apikey = data["data"]["user"]["apikey"]
        print(f"  Login OK! apikey={user_apikey}")
        
        auth_headers = base_headers()
        auth_headers["Authorization"] = f"Bearer {at}"
        
        # 2. Get families
        print("\n=== Families ===")
        r = await client.get(f"{BASE}/v2/family", headers=auth_headers)
        fam = r.json()
        if fam.get("error") == 0:
            for f_item in fam["data"]["familyList"]:
                print(f"  {f_item['id']}: {f_item['name']} (members: {len(f_item.get('members',[]))})")
                for m in f_item.get("members", []):
                    print(f"    member: {m.get('nickname','')} / {m.get('phoneNumber','')} / role={m.get('role','')}")
        
        # 3. Get devices
        print("\n=== Devices ===")
        r = await client.get(f"{BASE}/v2/device/thing", headers=auth_headers, params={"num": 0})
        devs = r.json()
        if devs.get("error") == 0:
            for item in devs["data"]["thingList"]:
                d = item.get("itemData", {})
                did = d.get("deviceid", "")
                name = d.get("name", "")
                online = d.get("online", False)
                params = d.get("params", {})
                power = params.get("power", "?")
                switches = params.get("switches", [])
                sw_str = ",".join([f"ch{s['outlet']}={'ON' if s['switch']=='on' else 'OFF'}" for s in switches]) if switches else "?"
                marker = " <<<" if did == DEVICE_ID else ""
                print(f"  {did}: {name} | online={online} | power={power}W | {sw_str}{marker}")
                
                # For our target device, print ALL params
                if did == DEVICE_ID:
                    print(f"\n  === TARGET DEVICE FULL PARAMS ===")
                    for k in sorted(params.keys()):
                        v = params[k]
                        s = json.dumps(v, ensure_ascii=False)
                        if len(s) > 200:
                            s = s[:200] + "..."
                        print(f"    {k}: {s}")
                    
                    # Check timers
                    timers = params.get("timers", [])
                    print(f"\n  === TIMERS ({len(timers)}) ===")
                    for t_item in timers:
                        print(f"    {json.dumps(t_item, ensure_ascii=False)}")
        
        # 4. Get device operation history
        print("\n=== Device History (last 20) ===")
        try:
            r = await client.get(
                f"{BASE}/v2/device/{DEVICE_ID}/history",
                headers=auth_headers
            )
            hist = r.json()
            print(f"  error={hist.get('error')}, msg={hist.get('msg','')}")
            if hist.get("error") == 0:
                for h in hist.get("data", {}).get("histories", [])[:20]:
                    print(f"  {json.dumps(h, ensure_ascii=False)[:300]}")
            else:
                print(f"  {json.dumps(hist, ensure_ascii=False)[:500]}")
        except Exception as e:
            print(f"  Error: {e}")
        
        # 5. Get scenes
        print("\n=== Scenes ===")
        try:
            r = await client.get(f"{BASE}/v2/smartscene/list", headers=auth_headers)
            scenes = r.json()
            if scenes.get("error") == 0:
                for sc in scenes.get("data", []):
                    sc_str = json.dumps(sc, ensure_ascii=False)
                    if DEVICE_ID in sc_str or "插头" in sc_str or "bed" in sc_str:
                        print(f"  *** {sc_str[:500]}")
                    else:
                        print(f"  {sc.get('name','?')}: {sc_str[:200]}")
            else:
                print(f"  {json.dumps(scenes, ensure_ascii=False)[:300]}")
        except Exception as e:
            print(f"  Error: {e}")

asyncio.run(main())
