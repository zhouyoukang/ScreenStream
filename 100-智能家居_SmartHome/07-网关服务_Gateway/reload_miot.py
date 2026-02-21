import asyncio, json, websockets

TOKEN = "REDACTED_HA_TOKEN_1"

async def main():
    async with websockets.connect("ws://127.0.0.1:8123/api/websocket") as ws:
        await ws.recv()
        await ws.send(json.dumps({"type": "auth", "access_token": TOKEN}))
        msg = json.loads(await ws.recv())
        if msg["type"] != "auth_ok":
            print("Auth failed")
            return

        # List config entries
        await ws.send(json.dumps({"id": 1, "type": "config_entries/get"}))
        msg = json.loads(await ws.recv())
        for e in msg.get("result", []):
            if "miot" in e.get("domain", ""):
                eid = e["entry_id"]
                state = e.get("state", "?")
                title = e.get("title", "?")
                print(f"Found: entry_id={eid} domain={e['domain']} state={state} title={title}")
                
                # Reload entry
                await ws.send(json.dumps({"id": 2, "type": "config_entries/reload", "entry_id": eid}))
                r = json.loads(await ws.recv())
                print(f"Reload result: success={r.get('success')} error={r.get('error')}")

        # Wait and check entities
        await asyncio.sleep(10)
        await ws.send(json.dumps({"id": 3, "type": "config/entity_registry/list"}))
        msg = json.loads(await ws.recv())
        entities = msg.get("result", [])
        miot_entities = [e for e in entities if "miot" in e.get("platform", "")]
        print(f"\nTotal entities: {len(entities)}")
        print(f"Xiaomi Miot entities: {len(miot_entities)}")
        for e in miot_entities[:30]:
            print(f"  {e['entity_id']} [{e.get('name', e.get('original_name', '?'))}]")

asyncio.run(main())
