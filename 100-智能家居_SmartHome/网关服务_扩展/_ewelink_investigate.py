"""Direct CoolKit v2 API investigation - get device history, timers, scenes"""
import httpx
import hashlib
import hmac
import base64
import json
import time

BASE = "https://cn-apia.coolkit.cn"
APP_ID = ""  # Will try without app_id first using the HA credentials
APP_SECRET = ""

# HA Sonoff integration credentials
PHONE = "8618368624112"
PASSWORD = "zhouyoukang1122"
DEVICE_ID = "10022cf6a2"

async def main():
    async with httpx.AsyncClient(timeout=15, verify=False) as client:
        # 1. Try login
        print("=== Attempting CoolKit API login ===")
        
        # Method 1: Try eWeLink v2 API login (used by SonoffLAN)
        login_url = f"{BASE}/v2/user/login"
        body = {
            "phoneNumber": PHONE,
            "password": PASSWORD,
            "countryCode": "+86"
        }
        headers = {
            "Content-Type": "application/json",
            "X-CK-Appid": "YzfeftUVcZ6twZw1OoVKPRFYTrGEg01Q",  # Default SonoffLAN appid
            "X-CK-Nonce": "abcdef12"
        }
        
        # Generate signature
        import time as t
        ts = str(int(t.time()))
        
        try:
            r = await client.post(login_url, json=body, headers=headers)
            print(f"  Status: {r.status_code}")
            print(f"  Response: {r.text[:500]}")
        except Exception as e:
            print(f"  Error: {e}")
        
        # Method 2: Try eWeLink dispatch server first
        print("\n=== Try dispatch server ===")
        dispatch_url = "https://cn-dispa.coolkit.cn/dispatch/app"
        try:
            r = await client.get(dispatch_url, headers={"Accept": "application/json"})
            print(f"  Status: {r.status_code}")
            print(f"  Response: {r.text[:300]}")
        except Exception as e:
            print(f"  Error: {e}")

        # Method 3: Try eWeLink web API (used by web.ewelink.cc)
        print("\n=== Try eWeLink web login ===")
        web_login_url = "https://cn-apia.coolkit.cn/v2/user/login"
        web_body = {
            "phoneNumber": PHONE,
            "password": PASSWORD,
            "countryCode": "+86"
        }
        web_headers = {
            "Content-Type": "application/json",
            "X-CK-Appid": "oeVkj2lYFGnJu5XUtWisfW4utiN4u9Mq",  # eWeLink web appid
            "X-CK-Nonce": "aabbccdd"
        }
        try:
            r = await client.post(web_login_url, json=web_body, headers=web_headers)
            print(f"  Status: {r.status_code}")
            print(f"  Response: {r.text[:500]}")
        except Exception as e:
            print(f"  Error: {e}")

        # Method 4: Try alternative API endpoints
        print("\n=== Try alternative endpoints ===")
        alt_urls = [
            "https://cn-apia.coolkit.cn/v2/homepage/health",
            "https://as-apia.coolkit.cc/v2/user/login",
            "https://eu-apia.coolkit.cc/v2/user/login",
        ]
        for url in alt_urls:
            try:
                r = await client.get(url, timeout=5)
                print(f"  {url}: {r.status_code} {r.text[:100]}")
            except Exception as e:
                print(f"  {url}: {type(e).__name__}: {e}")

import asyncio
asyncio.run(main())
