import httpx, json
r = httpx.get("http://127.0.0.1:8900/devices?source=micloud", timeout=10)
d = r.json()
print(f"Total MiCloud devices: {d['count']}\n")
for x in d["devices"]:
    print(f"  ID: {x['id']:45}  Name: {x.get('name','?'):25}  State: {x.get('state','?')}")

# Also check raw /wx POST reply
import time
xml = (
    "<xml><ToUserName><![CDATA[gh]]></ToUserName>"
    "<FromUserName><![CDATA[u1]]></FromUserName>"
    f"<CreateTime>{int(time.time())}</CreateTime>"
    "<MsgType><![CDATA[text]]></MsgType>"
    "<Content><![CDATA[打开灯带]]></Content>"
    "<MsgId>1</MsgId></xml>"
)
r2 = httpx.post("http://127.0.0.1:8900/wx", content=xml.encode("utf-8"),
                 headers={"Content-Type": "application/xml"}, timeout=15)
print(f"\n--- Raw /wx reply for '打开灯带' ---")
print(r2.text[:600])
