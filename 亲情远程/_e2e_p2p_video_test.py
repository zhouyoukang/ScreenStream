"""E2E test: Verify P2P video streaming with forceKeyFrame fix.
Polls page-level variables + injects a minimal DC binary frame counter
to verify config/key/delta frame delivery.
"""
import asyncio
import json
import time
from playwright.async_api import async_playwright

ROOM = "402997"
TIMEOUT = 20

DC_INTERCEPT_INIT = """
// Intercept RTCDataChannel.onmessage at prototype level to count frame types
window._fs = {c:0,k:0,d:0,o:0,bytes:0,sps:null,types:[],err:null};
try {
    const desc = Object.getOwnPropertyDescriptor(RTCDataChannel.prototype, 'onmessage');
    if(desc && desc.set) {
        const origSet = desc.set;
        Object.defineProperty(RTCDataChannel.prototype, 'onmessage', {
            set: function(handler) {
                const wrapped = function(ev) {
                    try {
                        if(ev.data && (ev.data instanceof ArrayBuffer)) {
                            const u8 = new Uint8Array(ev.data);
                            if(u8.length >= 10) {
                                const ft = u8[0];
                                window._fs.bytes += u8.length;
                                if(ft===0) { window._fs.c++;
                                    for(let i=9;i<u8.length-5;i++){
                                        if(u8[i]===0&&u8[i+1]===0&&(u8[i+2]===1||(u8[i+2]===0&&u8[i+3]===1))){
                                            const sc=u8[i+2]===1?3:4;
                                            if((u8[i+sc]&0x1F)===7&&u8.length>i+sc+3){
                                                window._fs.sps='avc1.'+[u8[i+sc+1],u8[i+sc+2],u8[i+sc+3]].map(v=>v.toString(16).padStart(2,'0')).join('');
                                                break;
                                            }
                                        }
                                    }
                                }
                                else if(ft===1) window._fs.k++;
                                else if(ft===2) window._fs.d++;
                                else if(ft===3) window._fs.o++;
                                if(window._fs.types.length<30) window._fs.types.push(ft);
                            }
                        }
                    } catch(e) { window._fs.err = e.message; }
                    if(handler) handler.call(this, ev);
                };
                origSet.call(this, wrapped);
            },
            get: desc.get,
            configurable: true
        });
    }
} catch(e) { window._fs.err = 'init:'+e.message; }
"""

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(ignore_https_errors=True, viewport={"width":800,"height":600})
        page = await ctx.new_page()
        
        logs = []
        page.on("console", lambda msg: logs.append(f"[{msg.type}] {msg.text}"))
        
        # Inject DC prototype patch BEFORE page load
        await page.add_init_script(DC_INTERCEPT_INIT)
        
        url = f"http://localhost:9101/cast/?room={ROOM}&_v={int(time.time())}"
        print(f"[TEST] Opening {url}")
        await page.goto(url, wait_until="networkidle", timeout=15000)
        print(f"[TEST] Page loaded, waiting {TIMEOUT}s for P2P data...")
        
        start = time.time()
        while time.time() - start < TIMEOUT:
            await asyncio.sleep(3)
            elapsed = int(time.time() - start)
            try:
                fs = await page.evaluate("() => window._fs")
                extra = await page.evaluate("""() => ({
                    mode: typeof currentMode!=='undefined'?currentMode:'?',
                    dc: typeof dcBytesReceived!=='undefined'?dcBytesReceived:0,
                    cfg: typeof hasConfig!=='undefined'?hasConfig:null,
                    fps: typeof fpsCount!=='undefined'?fpsCount:0,
                    dec: typeof decoder!=='undefined'&&decoder?decoder.state:'none',
                })""")
                print(f"[+{elapsed:2d}s] mode={extra['mode']} dc={extra['dc']}B cfg={extra['cfg']} fps={extra['fps']} dec={extra['dec']} | intercepted: c={fs['c']} k={fs['k']} d={fs['d']} {fs['bytes']}B types={fs['types'][:10]}")
            except: pass
        
        # Final
        fs = await page.evaluate("() => window._fs")
        extra = await page.evaluate("""() => ({
            currentMode: typeof currentMode!=='undefined'?currentMode:'unknown',
            dcBytesReceived: typeof dcBytesReceived!=='undefined'?dcBytesReceived:0,
            hasConfig: typeof hasConfig!=='undefined'?hasConfig:null,
            fpsCount: typeof fpsCount!=='undefined'?fpsCount:0,
            decoderState: typeof decoder!=='undefined'&&decoder?decoder.state:'none',
            lastCodec: typeof lastCodec!=='undefined'?lastCodec:null,
            canvas: (()=>{const c=document.getElementById('relayCanvas');return c?c.style.display!=='none':false})(),
        })""")
        
        print(f"\n{'='*60}")
        print("[RESULTS]")
        print(f"Page vars: {json.dumps(extra)}")
        print(f"Intercepted: {json.dumps(fs)}")
        
        print(f"\n[VERIFICATION]")
        ok = lambda c,m: f"  {'PASS' if c else 'FAIL'} {m}"
        p2p = extra['currentMode']=='p2p'
        dc = extra['dcBytesReceived']>0
        # hasConfig may be reset by decoder error cycle, check if DC bytes indicate config was sent
        cfg_sent = fs['c']>0 or extra.get('hasConfig')==True
        key_sent = fs['k']>0
        delta_sent = fs['d']>0
        total = fs['c']+fs['k']+fs['d']+fs['o']
        
        print(ok(p2p, f"P2P connected: mode={extra['currentMode']}"))
        print(ok(dc, f"DC data received: {extra['dcBytesReceived']} bytes"))
        print(ok(cfg_sent, f"Config frame (SPS/PPS): intercepted={fs['c']}, sps={fs.get('sps')}"))
        print(ok(key_sent, f"Key frame: intercepted={fs['k']}"))
        print(ok(delta_sent, f"Delta frames: intercepted={fs['d']}"))
        print(ok(total>5, f"Total frames: {total}"))
        print(f"  INFO Frame type sequence: {fs['types'][:20]}")
        print(f"  INFO Codec: {extra.get('lastCodec')} | Decoder: {extra['decoderState']}")
        print(f"  INFO Headless Chromium has no H264 WebCodecs - decode verification N/A")
        
        passed = sum([p2p, dc, cfg_sent, key_sent, delta_sent, total>5])
        print(f"\n  Score: {passed}/6")
        
        relevant = [l for l in logs if any(k in l for k in ['DC','Signal','Decoder','key','frame','Error'])]
        if relevant:
            print(f"\n[LOGS] ({len(relevant)})")
            for l in relevant[:15]: print(f"  {l}")
        
        await browser.close()

asyncio.run(main())
