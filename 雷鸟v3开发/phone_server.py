#!/usr/bin/env python3
"""
手机脑服务器 — 运行于 Termux (端口8765, IP自动获取)

老子第四十二章：道生一，一生二，二生三，三生万物
  手机 = 一（百万App + AI平台 + 网络 + 传感器）
  眼镜 = 器（纯感知接口：听/说/看/触）
  PC   = 梯（初始桥接，用后可撤）
  万物 = 通过眼镜使用一切，而无需触碰手机

此脚本运行在手机 Termux 内。
眼镜的任何动作（TP触控/拍照/语音）→ HTTP到此 → 手机处理 → 眼镜响应

─── Termux 安装（在手机Termux中运行一次）────────────────
  pkg install python python-pip -y
  pip install flask requests
  # 开机自启（可选）
  echo "python ~/phone_server.py &" >> ~/.bashrc
─────────────────────────────────────────────────────────

API端点：
  POST /tts       {"text":"..."}           → 手机TTS+眼镜TTS
  POST /ask       {"query":"...","ctx":""}  → AI问答
  POST /see       {"image_b64":"..."}       → 视觉识别
  POST /hear      {"text":"..."}            → 语音转意图
  POST /app       {"app":"kimi","q":"..."}  → 启动手机App
  POST /glasses   {"event":"tap","data":{}} → 眼镜事件路由
  GET  /status                              → 三体状态
"""

import os
import sys
import re
import json
import time
import base64
import threading
import subprocess
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# ─── 配置 ─────────────────────────────────────────────────
PORT       = 8765
BRAIN_DIR  = Path(os.environ.get("HOME", "/sdcard")) / "phone_brain"
BRAIN_DIR.mkdir(exist_ok=True)

DASHSCOPE_KEY = os.environ.get("DASHSCOPE_API_KEY", "")
OPENAI_KEY    = os.environ.get("OPENAI_API_KEY", "")

# 手机App包名（已确认安装）
APPS = {
    "chatgpt" : "com.openai.chatgpt",
    "kimi"    : "com.moonshot.kimichat",
    "tongyi"  : "com.aliyun.tongyi",
    "wechat"  : "com.tencent.mm",
    "feishu"  : "com.ss.android.lark",
    "dingtalk": "com.alibaba.android.rimet",
    "baidu"   : "com.baidu.newapp",
    "maps"    : "com.baidu.BaiduMap",
    "tasker"  : "net.dinglisch.android.taskerm",
    "bing"    : "com.microsoft.bing",
    "music"   : "com.netease.cloudmusic",
}


# ─── 工具函数 ─────────────────────────────────────────────
def shell(cmd: str) -> str:
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True,
                           text=True, timeout=10)
        return r.stdout.strip()
    except Exception:
        return ""


def tts_speak(text: str):
    """
    手机TTS → 通过ADB发给眼镜TTS
    多路降级：termux-tts-speak → am TTS广播
    """
    text = text[:100]  # 眼镜TTS限长

    # 方式1: Termux:API termux-tts-speak (最佳，支持中文)
    r = subprocess.run(
        ["termux-tts-speak", "-l", "zh-CN", "-r", "0.9", text],
        capture_output=True, timeout=8
    )
    if r.returncode == 0:
        return True

    # 方式2: Android TTS broadcast
    safe = _sanitize_shell(text)
    shell(f'am broadcast -a android.speech.tts.SpeakText '
          f'--es text "{safe}" --es utterance_id "phone_brain"')
    return True


def ask_ai(query: str, system: str = "用不超过30字简洁回答") -> str:
    """
    AI问答路由链：DashScope → OpenAI → 降级
    """
    # ① 通义千问 (DashScope)
    if DASHSCOPE_KEY:
        try:
            payload = json.dumps({
                "model": "qwen-turbo",
                "input": {
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": query}
                    ]
                }
            }).encode()
            req = urllib.request.Request(
                "https://dashscope.aliyuncs.com/api/v1/services/aigc/"
                "text-generation/generation",
                data=payload,
                headers={"Authorization": f"Bearer {DASHSCOPE_KEY}",
                         "Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                r = json.loads(resp.read())
                return r["output"]["choices"][0]["message"]["content"].strip()
        except Exception:
            pass

    # ② OpenAI
    if OPENAI_KEY:
        try:
            payload = json.dumps({
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": query}
                ]
            }).encode()
            req = urllib.request.Request(
                "https://api.openai.com/v1/chat/completions",
                data=payload,
                headers={"Authorization": f"Bearer {OPENAI_KEY}",
                         "Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                r = json.loads(resp.read())
                return r["choices"][0]["message"]["content"].strip()
        except Exception:
            pass

    # ③ 百度搜索降级（无API也能用）
    try:
        import urllib.parse
        url = f"https://www.baidu.com/s?wd={urllib.parse.quote(query)}"
        req = urllib.request.Request(url, headers={"User-Agent": "curl/7.68.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            html = resp.read().decode("utf-8", errors="ignore")[:2000]
            # 简单提取摘要（无需解析库）
            m = re.search(r'<div[^>]*class="[^"]*c-abstract[^"]*"[^>]*>(.*?)</div>',
                          html, re.S)
            if m:
                text = re.sub(r'<[^>]+>', '', m.group(1)).strip()[:80]
                if text:
                    return text
    except Exception:
        pass

    return "暂时无法连接AI，请稍后再试"


def _sanitize_shell(s: str) -> str:
    """移除shell元字符，防止命令注入"""
    return re.sub(r'["$`\\;|&<>(){}\[\]!#~]', '', s)[:200]


def open_app(app_key: str, query: str = "") -> bool:
    """启动手机App（从眼镜触发）"""
    pkg = APPS.get(app_key.lower(), "")
    if not pkg:
        return False

    safe_q = _sanitize_shell(query)
    if safe_q:
        if app_key == "bing" or app_key == "browser":
            shell(f'am start -a android.intent.action.WEB_SEARCH '
                  f'-e query "{safe_q}"')
        elif app_key == "baidu":
            shell(f'am start -a android.intent.action.WEB_SEARCH '
                  f'-e query "{safe_q}" -n {pkg}/com.baidu.searchbox.MainActivity')
        elif app_key == "kimi":
            shell(f'am start -n {pkg}/.ui.MainActivity '
                  f'--es query "{safe_q}"')
        else:
            shell(f'monkey -p {pkg} -c android.intent.category.LAUNCHER 1')
    else:
        shell(f'monkey -p {pkg} -c android.intent.category.LAUNCHER 1')
    return True


def get_phone_status() -> dict:
    """手机当前状态"""
    battery_out = shell("dumpsys battery | grep level")
    battery = int(battery_out.split(":")[-1].strip()) if "level" in battery_out else -1
    wifi_out = shell("ip addr show wlan0 2>/dev/null | grep 'inet '")
    wifi_ip = wifi_out.split()[1].split("/")[0] if "inet" in wifi_out else "offline"
    app_out = shell("dumpsys activity activities | grep mResumedActivity")
    app = ""
    if app_out:
        m = re.search(r'([a-z][a-z.]+)/[.\w]+', app_out)
        app = m.group(1).split(".")[-1] if m else ""
    return {
        "battery": battery,
        "wifi": wifi_ip,
        "foreground_app": app,
        "ai_ready": bool(DASHSCOPE_KEY or OPENAI_KEY),
        "apps_available": list(APPS.keys()),
    }


def route_glasses_event(event: str, data: dict) -> dict:
    """
    眼镜事件路由器 — 心斋·以气听
    事件 → 意图 → 手机处理 → 响应

    事件映射（老子·庖丁：依乎天理，一触到位）:
      tap         → 拍照识别（视觉场景）
      double_tap  → AI问答（语音意图）
      slide_fwd   → App切换/下一页
      slide_back  → 返回/上一页
      long_press  → 状态报告
      voice       → 语音识别 → AI → TTS
      photo       → 图像分析 → TTS
    """
    if event == "tap" or event == "photo":
        img_b64 = data.get("image_b64", "")
        if img_b64:
            img_path = str(BRAIN_DIR / f"cap_{int(time.time())}.jpg")
            with open(img_path, "wb") as f:
                f.write(base64.b64decode(img_b64))
            # OCR
            ocr = shell(f"tesseract {img_path} stdout -l chi_sim+eng 2>/dev/null")
            if ocr.strip():
                ans = ask_ai(f"图片文字：{ocr[:200]}，请简要说明")
                tts_speak(ans[:60])
                return {"event": "photo_analyzed", "text": ocr, "answer": ans}
            else:
                ans = ask_ai("眼镜拍了照片但没有文字，可能是一个场景，请说：正在观察")
                tts_speak("已拍照，场景已记录")
                return {"event": "photo_saved", "path": img_path}
        else:
            tts_speak("请再单击一次触发拍照")
            return {"event": "no_photo"}

    elif event == "double_tap" or event == "voice":
        query = data.get("query", data.get("text", "有什么可以帮你？"))
        ans = ask_ai(query)
        tts_speak(ans)
        return {"event": "answered", "answer": ans}

    elif event == "slide_fwd":
        shell("input swipe 540 1600 540 600 300")  # 向下滚动内容
        tts_speak("向前")
        return {"event": "navigated"}

    elif event == "slide_back":
        shell("input keyevent 4")  # 返回键
        tts_speak("向后")
        return {"event": "navigated"}

    elif event == "long_press" or event == "status":
        s = get_phone_status()
        msg = f"手机{s['battery']}%, AI{'就绪' if s['ai_ready'] else '离线'}"
        tts_speak(msg)
        return {"event": "status", "data": s}

    elif event == "open_app":
        app = data.get("app", "kimi")
        ok = open_app(app, data.get("query", ""))
        tts_speak(f"已打开{app}" if ok else "打开失败")
        return {"event": "app_opened", "app": app, "ok": ok}

    return {"event": "unknown", "input": event}


# ─── HTTP 请求处理器 ──────────────────────────────────────
class PhoneBrainHandler(BaseHTTPRequestHandler):

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = {}
        if length:
            raw = self.rfile.read(length)
            try:
                body = json.loads(raw)
            except json.JSONDecodeError:
                pass

        if self.path == "/tts":
            text = body.get("text", "")
            tts_speak(text)
            self._ok({"done": True, "text": text})

        elif self.path == "/ask":
            query = body.get("query", "")
            sys_prompt = body.get("system", "用不超过30字简洁回答")
            ans = ask_ai(query, sys_prompt)
            tts_speak(ans[:80])
            self._ok({"answer": ans})

        elif self.path == "/see":
            result = route_glasses_event("photo", body)
            self._ok(result)

        elif self.path == "/hear":
            result = route_glasses_event("voice", body)
            self._ok(result)

        elif self.path == "/app":
            app = body.get("app", "")
            query = body.get("query", "")
            ok = open_app(app, query)
            tts_speak(f"已打开{app}" if ok else f"找不到{app}")
            self._ok({"opened": ok, "app": app})

        elif self.path == "/glasses":
            event = body.get("event", "unknown")
            data = body.get("data", {})
            result = route_glasses_event(event, data)
            self._ok(result)

        else:
            self._respond(404, {"error": "unknown endpoint"})

    def do_GET(self):
        if self.path == "/status":
            self._ok(get_phone_status())
        elif self.path == "/ping":
            self._ok({"pong": True, "brain": "phone"})
        elif self.path == "/" or self.path == "/ui":
            self._serve_ui()
        else:
            self._respond(404, {"error": "not found"})

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _ok(self, data: dict):
        self._respond(200, data)

    def _err(self, msg: str):
        self._respond(400, {"error": msg})

    def _respond(self, code: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _serve_ui(self):
        html = PHONE_UI_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html)))
        self.end_headers()
        self.wfile.write(html)

    def log_message(self, fmt, *args):
        ts = time.strftime("%H:%M:%S")
        path = self.path if hasattr(self, 'path') else '?'
        print(f"[{ts}] {path} {args[1] if len(args) > 1 else ''}")


# ─── 手机端管理UI（移动优先） ─────────────────────────────
PHONE_UI_HTML = r"""
<!DOCTYPE html><html lang="zh-CN"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>手机脑 · Phone Brain</title>
<style>
:root{--bg:#0a0a0f;--bg2:#14141f;--bg3:#1e1e30;--fg:#e8e8f0;--fg2:#8888a8;--cyan:#00d4ff;--green:#22c55e;--red:#ef4444;--gold:#f0b429;--r:10px}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui,-apple-system,sans-serif;background:var(--bg);color:var(--fg);min-height:100vh;padding:12px;padding-bottom:80px}
.header{text-align:center;padding:16px 0 12px}
.header h1{font-size:18px;font-weight:700}.header h1 span{color:var(--cyan)}
.header .sub{font-size:11px;color:var(--fg2);margin-top:4px}
.chips{display:flex;justify-content:center;gap:8px;margin:10px 0}
.chip{font-size:11px;padding:4px 12px;border-radius:16px;border:1px solid var(--bg3)}
.chip.on{color:var(--green);border-color:rgba(34,197,94,.4)}
.chip.off{color:var(--red);border-color:rgba(239,68,68,.3)}
.section{margin-bottom:14px}
.section h3{font-size:11px;text-transform:uppercase;letter-spacing:1px;color:var(--fg2);margin-bottom:8px;padding-left:4px}
.card{background:var(--bg2);border:1px solid var(--bg3);border-radius:var(--r);padding:14px;margin-bottom:8px}
.row{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;font-size:13px}
.row .label{color:var(--fg2)}
.row .val{font-weight:600;font-family:monospace}
.val.g{color:var(--green)}.val.r{color:var(--red)}.val.y{color:var(--gold)}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:6px}
.grid-btn{background:var(--bg3);border:1px solid rgba(255,255,255,.06);color:var(--fg);padding:12px 4px;border-radius:var(--r);text-align:center;cursor:pointer;font-size:12px;-webkit-tap-highlight-color:transparent;transition:all .15s}
.grid-btn:active{background:var(--cyan);color:#000;border-color:var(--cyan)}
.grid-btn .icon{font-size:20px;display:block;margin-bottom:4px}
.input-row{display:flex;gap:6px;margin-bottom:6px}
.input-row input{flex:1;background:var(--bg3);border:1px solid rgba(255,255,255,.06);color:var(--fg);padding:10px 12px;border-radius:var(--r);font-size:14px}
.input-row input:focus{outline:none;border-color:var(--cyan)}
.btn{background:rgba(0,212,255,.15);border:1px solid rgba(0,212,255,.3);color:var(--cyan);padding:10px 16px;border-radius:var(--r);font-size:13px;font-weight:600;cursor:pointer}
.btn:active{background:var(--cyan);color:#000}
.log{max-height:200px;overflow-y:auto;font-family:monospace;font-size:10px;color:var(--fg2);background:var(--bg3);border-radius:var(--r);padding:8px;margin-top:8px}
.log div{padding:2px 0;border-bottom:1px solid rgba(255,255,255,.03)}
.toast{position:fixed;top:16px;left:50%;transform:translateX(-50%);background:var(--cyan);color:#000;padding:8px 20px;border-radius:20px;font-size:13px;font-weight:600;opacity:0;transition:opacity .3s;pointer-events:none;z-index:99}
.toast.show{opacity:1}
</style></head><body>
<div class="toast" id="toast"></div>
<div class="header">
  <h1>🧠 <span>手机脑</span> · Phone Brain</h1>
  <div class="sub">道生一，一生二，二生三，三生万物</div>
</div>
<div class="chips">
  <span class="chip" id="cBrain">🧠 检测中</span>
  <span class="chip" id="cAI">🤖 AI</span>
  <span class="chip" id="cBatt">🔋 --%</span>
</div>

<div class="section">
  <h3>📊 系统状态</h3>
  <div class="card">
    <div class="row"><span class="label">🔋 电量</span><span class="val" id="sBatt">—</span></div>
    <div class="row"><span class="label">📶 WiFi</span><span class="val" id="sWifi">—</span></div>
    <div class="row"><span class="label">🤖 AI后端</span><span class="val" id="sAI">—</span></div>
    <div class="row"><span class="label">📱 前台App</span><span class="val" id="sApp">—</span></div>
  </div>
</div>

<div class="section">
  <h3>🖐 眼镜手势模拟</h3>
  <div class="grid">
    <div class="grid-btn" onclick="gesture('tap')"><span class="icon">👆</span>单击·拍照</div>
    <div class="grid-btn" onclick="gesture('double_tap')"><span class="icon">👆👆</span>双击·AI</div>
    <div class="grid-btn" onclick="gesture('long_press')"><span class="icon">⏳</span>长按·状态</div>
    <div class="grid-btn" onclick="gesture('slide_fwd')"><span class="icon">➡️</span>前滑</div>
    <div class="grid-btn" onclick="gesture('slide_back')"><span class="icon">⬅️</span>后滑</div>
    <div class="grid-btn" onclick="refreshStatus()"><span class="icon">🔄</span>刷新</div>
  </div>
</div>

<div class="section">
  <h3>📢 TTS 播报</h3>
  <div class="input-row">
    <input type="text" id="ttsInput" placeholder="输入播报内容..." value="道可道，非常道">
    <button class="btn" onclick="doTTS()">🔊</button>
  </div>
</div>

<div class="section">
  <h3>🤖 AI 问答</h3>
  <div class="input-row">
    <input type="text" id="aiInput" placeholder="问一个问题..." value="今天天气怎么样">
    <button class="btn" onclick="doAsk()">🧠</button>
  </div>
  <div id="aiResult" style="font-size:12px;color:var(--fg2);margin-top:6px;min-height:16px"></div>
</div>

<div class="section">
  <h3>📱 快速启动App</h3>
  <div class="grid" id="appGrid"></div>
</div>

<div class="section">
  <h3>📋 日志</h3>
  <div class="log" id="log"></div>
</div>

<script>
const BASE = location.origin;
const APPS = {kimi:['🌙','Kimi'],tongyi:['🧠','通义'],chatgpt:['🤖','ChatGPT'],wechat:['💬','微信'],
  feishu:['🐦','飞书'],baidu:['🔍','百度'],maps:['🗺','地图'],music:['🎵','音乐'],bing:['🔎','Bing']};

function init(){
  const g=document.getElementById('appGrid');
  for(const[k,[icon,name]]of Object.entries(APPS)){
    const d=document.createElement('div');d.className='grid-btn';
    d.innerHTML=`<span class="icon">${icon}</span>${name}`;
    d.onclick=()=>openApp(k);g.appendChild(d);}
  refreshStatus();
  setInterval(refreshStatus,30000);
}

async function api(method,path,body){
  try{
    const opt={method,headers:{'Content-Type':'application/json'}};
    if(body)opt.body=JSON.stringify(body);
    const r=await fetch(BASE+path,opt);
    return await r.json();
  }catch(e){log('❌ '+e.message);return{error:e.message};}
}

async function refreshStatus(){
  const s=await api('GET','/status');
  if(s.error)return;
  document.getElementById('sBatt').textContent=s.battery+'%';
  document.getElementById('sBatt').className='val '+(s.battery>20?'g':'r');
  document.getElementById('sWifi').textContent=s.wifi||'—';
  document.getElementById('sAI').textContent=s.ai_ready?'✅ 就绪':'❌ 无Key';
  document.getElementById('sAI').className='val '+(s.ai_ready?'g':'r');
  document.getElementById('sApp').textContent=s.foreground_app||'—';
  document.getElementById('cBrain').className='chip on';document.getElementById('cBrain').textContent='🧠 在线';
  document.getElementById('cAI').className='chip '+(s.ai_ready?'on':'off');
  document.getElementById('cAI').textContent=s.ai_ready?'🤖 AI就绪':'🤖 无AI';
  document.getElementById('cBatt').textContent='🔋 '+s.battery+'%';
  document.getElementById('cBatt').className='chip '+(s.battery>20?'on':'off');
  log('📊 状态刷新完成');
}

async function gesture(g){
  toast(g);log('👆 手势: '+g);
  const r=await api('POST','/glasses',{event:g,data:{}});
  if(r.answer)document.getElementById('aiResult').textContent=r.answer;
}

async function doTTS(){
  const t=document.getElementById('ttsInput').value;if(!t)return;
  toast('🔊 '+t);log('🔊 TTS: '+t);await api('POST','/tts',{text:t});
}

async function doAsk(){
  const q=document.getElementById('aiInput').value;if(!q)return;
  document.getElementById('aiResult').textContent='思考中...';
  log('🧠 提问: '+q);
  const r=await api('POST','/ask',{query:q});
  document.getElementById('aiResult').textContent=r.answer||r.error||'无响应';
  if(r.answer)log('💡 回答: '+r.answer);
}

async function openApp(k){
  toast('📱 '+k);log('📱 打开: '+k);await api('POST','/app',{app:k});
}

function toast(msg){
  const t=document.getElementById('toast');t.textContent=msg;t.classList.add('show');
  setTimeout(()=>t.classList.remove('show'),1500);
}
function log(msg){
  const l=document.getElementById('log');
  const d=document.createElement('div');
  d.textContent=new Date().toLocaleTimeString('zh',{hour12:false,hour:'2-digit',minute:'2-digit',second:'2-digit'})+' '+msg;
  l.appendChild(d);if(l.children.length>100)l.removeChild(l.firstChild);l.scrollTop=l.scrollHeight;
}
init();
</script></body></html>
"""  # noqa: E501

# ─── 主入口 ───────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="手机脑服务器")
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--test", action="store_true", help="测试TTS和AI")
    args = parser.parse_args()

    if args.test:
        print("测试TTS...")
        tts_speak("手机脑测试，道生一，一生二，二生三，三生万物")
        print("测试AI...")
        ans = ask_ai("今天天气如何")
        print(f"AI: {ans}")
        print("测试App打开...")
        print(f"App列表: {list(APPS.keys())}")
        sys.exit(0)

    print(f"\n╔══════════════════════════════════════╗")
    print(f"║  手机脑 · Phone Brain Server          ║")
    print(f"║  老子第42章：三生万物                  ║")
    print(f"╚══════════════════════════════════════╝")
    print(f"\n  地址: http://0.0.0.0:{args.port}")
    print(f"  AI:   {'DashScope✅' if DASHSCOPE_KEY else '无Key'} "
          f"{'OpenAI✅' if OPENAI_KEY else ''}")
    print(f"  App:  {len(APPS)}个（{', '.join(list(APPS.keys())[:5])}...）")
    print(f"\n  眼镜→手机路由已就绪")
    print(f"  POST /glasses {{event, data}} → 全自动处理\n")

    server = HTTPServer(("0.0.0.0", args.port), PhoneBrainHandler)
    server.serve_forever()
