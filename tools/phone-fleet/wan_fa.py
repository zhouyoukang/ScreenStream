#!/usr/bin/env python3
r"""
wan_fa.py — 万法归宗
手机为宗，万物为法。手机浏览器访问此服务，连通手机·电脑·AI·万物一切能力。
手机连电脑（非电脑调手机），以此为门，万法归一。
运行：python wan_fa.py
访问：手机浏览器 -> http://[电脑IP]:9915
"""
import json, sys, socket, threading, argparse, os
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import urlopen, Request
from urllib.error import URLError

# ── 配置 ────────────────────────────────────────────────
PORT         = 9915
PHONE_URL    = os.environ.get("WF_PHONE", "http://192.168.31.32:8084")
PC_AGENT_URL = os.environ.get("WF_PC",    "http://localhost:9904")
OLLAMA_URL   = os.environ.get("WF_AI",    "http://localhost:11434")

# 尝试导入 phone_lib（增强自动发现）
try:
    sys.path.insert(0, os.path.dirname(__file__))
    from phone_lib import Phone as _Phone, discover as _discover
    _PHONE_LIB = True
except Exception:
    _PHONE_LIB = False

# ── HTTP 工具 ────────────────────────────────────────────
def _http(url, data=None, timeout=5):
    try:
        req = Request(url,
                      data=json.dumps(data).encode() if data is not None else None,
                      headers={"Content-Type": "application/json"})
        with urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", errors="replace"))
    except Exception as e:
        return {"error": str(e)}

def _phone(path, data=None, timeout=4):
    return _http(f"{PHONE_URL}{path}", data, timeout)

def _pc(path, data=None, timeout=6):
    return _http(f"{PC_AGENT_URL}{path}", data, timeout)

def _ai(path, data=None, timeout=30):
    return _http(f"{OLLAMA_URL}{path}", data, timeout)

# ── 本机 IP ──────────────────────────────────────────────
def _local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]; s.close(); return ip
    except Exception:
        return "127.0.0.1"

# ── 请求处理 ─────────────────────────────────────────────
class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *_): pass

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, d, code=200):
        body = json.dumps(d, ensure_ascii=False, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._cors(); self.end_headers(); self.wfile.write(body)

    def _html(self, html):
        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers(); self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n)) if n else {}

    def do_OPTIONS(self):
        self.send_response(200); self._cors(); self.end_headers()

    def do_GET(self):
        p = self.path.split("?")[0]
        if p == "/":
            self._html(_HTML.replace("{{PC_IP}}", _local_ip())
                              .replace("{{PORT}}", str(PORT))
                              .replace("{{PHONE_URL}}", PHONE_URL))
        elif p == "/api/agents":
            r = {}
            def chk(k, url):
                r[k] = "online" if "error" not in _http(url, timeout=2) else "offline"
            ts = [threading.Thread(target=chk, args=a) for a in [
                ("phone", f"{PHONE_URL}/status"),
                ("pc",    f"{PC_AGENT_URL}/status"),
                ("ai",    f"{OLLAMA_URL}/api/tags"),
            ]]
            for t in ts: t.start()
            for t in ts: t.join(timeout=3)
            self._json(r)
        elif p == "/api/sense":
            out = {}
            def s_phone():
                s = _phone("/status", timeout=3)
                if "error" not in s:
                    b = _phone("/battery", timeout=2)
                    s["battery_level"] = b.get("level", "?")
                out["phone"] = s
            def s_pc():
                out["pc"] = _pc("/status", timeout=3)
            ts = [threading.Thread(target=f) for f in [s_phone, s_pc]]
            for t in ts: t.start()
            for t in ts: t.join(timeout=4)
            self._json(out)
        elif p == "/api/screen":
            r = _phone("/screen/text", timeout=5)
            texts = [t.get("text", "") for t in r.get("texts", []) if t.get("text")]
            self._json({"texts": texts, "pkg": r.get("package", "")})
        elif p == "/api/notifications":
            r = _phone("/notifications/read?limit=8", timeout=4)
            self._json(r)
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        p = self.path; b = self._body()
        if p == "/api/phone/key":
            self._json(_phone("/key", {"keyCode": b.get("key","HOME")}))
        elif p == "/api/phone/open":
            self._json(_phone("/openapp", {"packageName": b.get("pkg","")}))
        elif p == "/api/phone/tap":
            self._json(_phone("/tap", {"nx": b.get("nx",0.5), "ny": b.get("ny",0.5)}))
        elif p == "/api/phone/text":
            self._json(_phone("/text", {"text": b.get("text","")}))
        elif p == "/api/pc/shell":
            self._json(_pc("/shell", {"command": b.get("cmd","")}, timeout=10))
        elif p == "/api/ai/chat":
            prompt = b.get("prompt","")
            model  = b.get("model","qwen2.5:7b")
            r = _ai("/api/generate", {"model":model,"prompt":prompt,"stream":False})
            self._json({"response": r.get("response", r.get("error",""))})
        elif p == "/api/phone/wake":
            self._json(_phone("/wake"))
        else:
            self._json({"error": "not found"}, 404)

# ── HTML 页面 ─────────────────────────────────────────────
_HTML = r"""<!DOCTYPE html>
<html lang="zh"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<meta name="apple-mobile-web-app-capable" content="yes">
<title>万法归宗</title>
<style>
:root{--bg:#080810;--card:#0f0f1a;--b:#1a1a2e;--ac:#8b7cf8;--ac2:#4ecdc4;--tx:#dde0f0;--mu:#5a5a7a;--gr:#22d360;--rd:#f87171;--yw:#fbbf24}
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
body{background:var(--bg);color:var(--tx);font-family:-apple-system,'PingFang SC',sans-serif;font-size:14px;min-height:100vh;overscroll-behavior:none}
.hd{padding:14px 16px 10px;background:linear-gradient(135deg,#130d2a 0%,#091524 100%);border-bottom:1px solid var(--b)}
.hd h1{font-size:18px;color:var(--ac);letter-spacing:3px;font-weight:700}
.hd p{color:var(--mu);font-size:11px;margin-top:3px}
.hd .addr{color:var(--ac2);font-size:11px;margin-top:2px;font-family:monospace}
.tabs{display:flex;background:var(--card);border-bottom:1px solid var(--b);overflow-x:auto;-webkit-overflow-scrolling:touch;scrollbar-width:none}
.tabs::-webkit-scrollbar{display:none}
.tab{flex:0 0 auto;padding:10px 14px;font-size:12px;color:var(--mu);border-bottom:2px solid transparent;cursor:pointer;transition:.2s;white-space:nowrap}
.tab.on{color:var(--ac);border-bottom-color:var(--ac)}
.pn{display:none;padding:12px;animation:fi .2s}
.pn.on{display:block}
@keyframes fi{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
.card{background:var(--card);border:1px solid var(--b);border-radius:10px;padding:12px;margin-bottom:10px}
.ct{font-size:10px;color:var(--mu);text-transform:uppercase;letter-spacing:1px;margin-bottom:8px}
.row{display:flex;justify-content:space-between;align-items:center;padding:7px 0;border-bottom:1px solid var(--b)}
.row:last-child{border-bottom:none}
.rl{color:var(--mu);font-size:12px}
.rv{font-size:12px}
.btn{display:block;width:100%;padding:12px;background:var(--ac);color:#fff;border:none;border-radius:8px;font-size:14px;cursor:pointer;margin-bottom:8px;transition:opacity .15s;font-weight:500}
.btn:active{opacity:.7}
.btn.sec{background:var(--card);border:1px solid var(--b);color:var(--tx)}
.btn.sml{padding:9px 6px;font-size:12px}
.g2{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.g3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-bottom:10px}
.sc{background:var(--bg);border:1px solid var(--b);border-radius:8px;padding:10px;max-height:220px;overflow-y:auto;font-size:12px;line-height:1.8;color:var(--ac2);white-space:pre-wrap;word-break:break-all;font-family:monospace}
.chat{background:var(--bg);border:1px solid var(--b);border-radius:8px;padding:10px;min-height:120px;max-height:240px;overflow-y:auto;margin-bottom:8px;font-size:13px;line-height:1.7;white-space:pre-wrap;word-break:break-all}
.ir{display:flex;gap:8px}
.ir input,.ir textarea{flex:1;background:var(--card);border:1px solid var(--b);color:var(--tx);padding:10px;border-radius:8px;font-size:14px;outline:none}
.ir button{padding:10px 14px;background:var(--ac);color:#fff;border:none;border-radius:8px;cursor:pointer;font-size:14px}
.badge{display:inline-block;padding:2px 9px;border-radius:20px;font-size:11px;font-weight:600}
.online{background:#0a2a18;color:var(--gr);border:1px solid #1a4a28}
.offline{background:#2a0a0a;color:var(--rd);border:1px solid #4a1a1a}
.ld{color:var(--mu);font-style:italic;font-size:12px}
.stat{text-align:center}
.bnum{font-size:26px;font-weight:700;color:var(--ac)}
.blab{font-size:10px;color:var(--mu);margin-top:2px}
.toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:#222238;color:var(--tx);padding:8px 18px;border-radius:20px;font-size:13px;z-index:9999;border:1px solid var(--b);pointer-events:none;transition:opacity .3s}
input[type=text]{width:100%;background:var(--card);border:1px solid var(--b);color:var(--tx);padding:10px;border-radius:8px;font-size:14px;outline:none;margin-bottom:8px}
.appgrid{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-top:8px}
.appbtn{background:var(--bg);border:1px solid var(--b);border-radius:8px;padding:8px 4px;text-align:center;font-size:11px;cursor:pointer;color:var(--tx)}
.appbtn:active{background:var(--b)}
.appicon{font-size:22px;display:block;margin-bottom:3px}
</style></head><body>
<div class="hd">
  <h1>万 法 归 宗</h1>
  <p>手机为宗 · 万物为法 · 连之于道</p>
  <div class="addr">http://{{PC_IP}}:{{PORT}}</div>
</div>
<div class="tabs">
  <div class="tab on" onclick="sw('sense')">☯ 感知</div>
  <div class="tab" onclick="sw('phone')">📱 手机</div>
  <div class="tab" onclick="sw('pc')">💻 电脑</div>
  <div class="tab" onclick="sw('ai')">🧠 AI</div>
  <div class="tab" onclick="sw('act')">⚡ 行动</div>
</div>

<!-- 感知 -->
<div id="pn-sense" class="pn on">
  <div class="g3">
    <div class="card stat"><div class="bnum" id="si-phone">…</div><div class="blab">手机</div></div>
    <div class="card stat"><div class="bnum" id="si-pc">…</div><div class="blab">电脑</div></div>
    <div class="card stat"><div class="bnum" id="si-ai">…</div><div class="blab">AI</div></div>
  </div>
  <div class="card">
    <div class="ct">连接状态</div>
    <div id="agents-list" class="ld">检测中…</div>
  </div>
  <div class="card">
    <div class="ct">手机状态</div>
    <div id="phone-detail" class="ld">加载中…</div>
  </div>
  <button class="btn sec" onclick="doSense()">⟳ 刷新全感知</button>
</div>

<!-- 手机 -->
<div id="pn-phone" class="pn">
  <div class="card">
    <div class="ct">屏幕文字</div>
    <div id="screen-box" class="sc ld">点击「读取屏幕」…</div>
  </div>
  <div class="g2" style="margin-bottom:8px">
    <button class="btn" onclick="readScreen()">👁 读取屏幕</button>
    <button class="btn sec" onclick="apiGet('/api/notifications').then(r=>showToast(r.error||JSON.stringify(r.notifications||r).slice(0,60)))">🔔 通知</button>
  </div>
  <div class="card">
    <div class="ct">导航</div>
    <div class="g2">
      <button class="btn sec sml" onclick="phoneKey('HOME')">🏠 主屏</button>
      <button class="btn sec sml" onclick="phoneKey('BACK')">← 返回</button>
      <button class="btn sec sml" onclick="phoneKey('VOLUME_UP')">🔊 音量+</button>
      <button class="btn sec sml" onclick="phoneKey('VOLUME_DOWN')">🔉 音量-</button>
      <button class="btn sec sml" onclick="phoneKey('APP_SWITCH')">⧉ 多任务</button>
      <button class="btn sec sml" onclick="phoneWake()">⏻ 唤醒</button>
    </div>
  </div>
  <div class="card">
    <div class="ct">常用 App</div>
    <div class="appgrid">
      <div class="appbtn" onclick="openApp('com.tencent.mm')"><span class="appicon">💬</span>微信</div>
      <div class="appbtn" onclick="openApp('com.taobao.taobao')"><span class="appicon">🛒</span>淘宝</div>
      <div class="appbtn" onclick="openApp('com.jingdong.app.mall')"><span class="appicon">📦</span>京东</div>
      <div class="appbtn" onclick="openApp('com.ss.android.ugc.aweme')"><span class="appicon">🎵</span>抖音</div>
      <div class="appbtn" onclick="openApp('com.xingin.xhs')"><span class="appicon">📖</span>小红书</div>
      <div class="appbtn" onclick="openApp('com.baidu.BaiduMap')"><span class="appicon">🗺</span>百度地图</div>
      <div class="appbtn" onclick="openApp('com.eg.android.AlipayGphone')"><span class="appicon">💳</span>支付宝</div>
      <div class="appbtn" onclick="openApp('com.netease.cloudmusic')"><span class="appicon">🎧</span>网易云</div>
    </div>
  </div>
  <div class="card">
    <div class="ct">输入文字</div>
    <div class="ir">
      <input id="txt-input" type="text" placeholder="输入文字发送到手机…" />
      <button onclick="sendText()">发送</button>
    </div>
  </div>
</div>

<!-- 电脑 -->
<div id="pn-pc" class="pn">
  <div class="card">
    <div class="ct">电脑状态</div>
    <div id="pc-detail" class="ld">加载中…</div>
  </div>
  <div class="card">
    <div class="ct">执行命令</div>
    <input id="pc-cmd" type="text" placeholder="tasklist 或 dir E:\道 /b …" />
    <button class="btn" onclick="runCmd()">▶ 执行</button>
    <div id="pc-out" class="sc" style="display:none"></div>
  </div>
  <div class="card">
    <div class="ct">快捷命令</div>
    <div class="g2">
      <button class="btn sec sml" onclick="qcmd('tasklist | findstr -i python')">Python进程</button>
      <button class="btn sec sml" onclick="qcmd('dir E:\\道 /b')">道目录</button>
      <button class="btn sec sml" onclick="qcmd('wmic os get FreePhysicalMemory')">剩余内存</button>
      <button class="btn sec sml" onclick="qcmd('ipconfig | findstr IPv4')">本机IP</button>
    </div>
  </div>
</div>

<!-- AI -->
<div id="pn-ai" class="pn">
  <div class="card">
    <div class="ct">AI 对话 · <span id="model-name" style="color:var(--ac2)">qwen2.5:7b</span></div>
    <div id="chat-box" class="chat">道可道，非常道。\n\n在此与AI对话，万法归宗，AI为法之一。</div>
    <div class="ir">
      <input id="chat-in" type="text" placeholder="提问…" onkeydown="if(event.key==='Enter')chat()" />
      <button onclick="chat()">问</button>
    </div>
  </div>
  <div class="card">
    <div class="ct">选择模型</div>
    <div class="g2">
      <button class="btn sec sml" onclick="setModel('qwen2.5:7b')">Qwen2.5 7B</button>
      <button class="btn sec sml" onclick="setModel('deepseek-r1:8b')">DeepSeek R1</button>
      <button class="btn sec sml" onclick="setModel('qwen3:8b')">Qwen3 8B</button>
      <button class="btn sec sml" onclick="setModel('gemma3:4b')">Gemma3 4B</button>
    </div>
  </div>
</div>

<!-- 行动 -->
<div id="pn-act" class="pn">
  <div class="card">
    <div class="ct">万法归宗 · 一键全感知</div>
    <button class="btn" onclick="wanfa_all()">⊙ 全域感知（手机+电脑+AI）</button>
    <button class="btn sec" onclick="wanfa_screen_ai()">📷 屏幕→AI 智能分析</button>
    <button class="btn sec" onclick="wanfa_notify()">🔔 通知→AI 摘要</button>
  </div>
  <div class="card">
    <div class="ct">手机快捷</div>
    <div class="g2">
      <button class="btn sec sml" onclick="phoneKey('HOME')">🏠 主屏</button>
      <button class="btn sec sml" onclick="phoneWake()">⏻ 唤醒</button>
      <button class="btn sec sml" onclick="phoneKey('VOLUME_MUTE')">🔇 静音</button>
      <button class="btn sec sml" onclick="openApp('com.tencent.mm')">💬 微信</button>
    </div>
  </div>
  <div class="card">
    <div class="ct">感知日志</div>
    <div id="act-log" class="sc" style="min-height:80px">等待操作…</div>
  </div>
</div>

<script>
const TABS=['sense','phone','pc','ai','act'];
let curModel='qwen2.5:7b';
let actLog=[];

function sw(name){
  TABS.forEach((t,i)=>{
    document.querySelectorAll('.tab')[i].classList.toggle('on',t===name);
    document.getElementById('pn-'+t).classList.toggle('on',t===name);
  });
  if(name==='sense') doSense();
  if(name==='pc') loadPC();
}

async function apiGet(p){
  try{const r=await fetch(p);return await r.json();}catch(e){return{error:e.message};}
}
async function apiPost(p,d){
  try{const r=await fetch(p,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)});return await r.json();}catch(e){return{error:e.message};}
}

function toast(msg,dur=2200){
  const t=document.createElement('div');t.className='toast';t.textContent=msg;
  document.body.appendChild(t);
  setTimeout(()=>{t.style.opacity='0';setTimeout(()=>t.remove(),350);},dur);
}

function log2act(msg){
  actLog.unshift(new Date().toLocaleTimeString('zh')+' '+msg);
  if(actLog.length>30)actLog.pop();
  const el=document.getElementById('act-log');
  if(el)el.textContent=actLog.join('\n');
}

async function doSense(){
  document.getElementById('agents-list').innerHTML='<span class="ld">检测中…</span>';
  const [ag,se]=await Promise.all([apiGet('/api/agents'),apiGet('/api/sense')]);

  document.getElementById('si-phone').textContent=ag.phone==='online'?'✅':'❌';
  document.getElementById('si-pc').textContent=ag.pc==='online'?'✅':'❌';
  document.getElementById('si-ai').textContent=ag.ai==='online'?'✅':'❌';

  const names={phone:'📱 手机',pc:'💻 电脑',ai:'🧠 AI'};
  document.getElementById('agents-list').innerHTML=
    Object.entries(ag).map(([k,v])=>
      `<div class="row"><span class="rl">${names[k]||k}</span><span class="badge ${v}">${v==='online'?'在线':'离线'}</span></div>`
    ).join('');

  const ph=se.phone||{};
  if(!ph.error){
    let h=`<div class="row"><span class="rl">连接</span><span class="rv" style="color:var(--gr)">✅ 已连接</span></div>`;
    if(ph.battery_level!=null)h+=`<div class="row"><span class="rl">电量</span><span class="rv">${ph.battery_level}%</span></div>`;
    if(ph.model)h+=`<div class="row"><span class="rl">型号</span><span class="rv">${ph.model}</span></div>`;
    document.getElementById('phone-detail').innerHTML=h;
  }else{
    document.getElementById('phone-detail').innerHTML=`<span style="color:var(--rd)">❌ ${ph.error}</span>`;
  }
  log2act('全感知完成');
}

async function readScreen(){
  document.getElementById('screen-box').textContent='读取中…';
  const r=await apiGet('/api/screen');
  const el=document.getElementById('screen-box');
  if(r.texts&&r.texts.length){
    el.textContent=r.texts.join('\n');
    log2act('屏幕读取 '+r.texts.length+' 条文字');
  }else if(r.error){
    el.textContent='❌ '+r.error;
  }else{
    el.textContent='（无文字）';
  }
}

async function phoneKey(k){
  const r=await apiPost('/api/phone/key',{key:k});
  toast(r.error?'❌ '+r.error:'✓ '+k);
  log2act('按键 '+k);
}

async function phoneWake(){
  await apiPost('/api/phone/wake',{});
  toast('✓ 唤醒');
}

async function openApp(pkg){
  const r=await apiPost('/api/phone/open',{pkg});
  toast(r.error?'❌ '+r.error:'✓ 已打开');
  log2act('打开 '+pkg.split('.').pop());
}

async function sendText(){
  const t=document.getElementById('txt-input').value.trim();
  if(!t)return;
  const r=await apiPost('/api/phone/text',{text:t});
  toast(r.error?'❌ '+r.error:'✓ 已发送');
  document.getElementById('txt-input').value='';
}

async function loadPC(){
  const r=await apiGet('/api/sense');
  const pc=r.pc||{};
  const el=document.getElementById('pc-detail');
  if(!pc.error){
    el.innerHTML='<div class="row"><span class="rl">状态</span><span class="badge online">在线</span></div>';
  }else{
    el.innerHTML=`<span style="color:var(--rd)">❌ ${pc.error}</span>`;
  }
}

async function runCmd(){
  const cmd=document.getElementById('pc-cmd').value.trim();
  if(!cmd)return;
  const el=document.getElementById('pc-out');
  el.style.display='block'; el.textContent='执行中…';
  const r=await apiPost('/api/pc/shell',{cmd});
  el.textContent=r.output||r.stdout||r.error||JSON.stringify(r);
  log2act('PC命令: '+cmd.slice(0,30));
}

function qcmd(c){document.getElementById('pc-cmd').value=c;runCmd();}

async function chat(){
  const inp=document.getElementById('chat-in');
  const prompt=inp.value.trim();if(!prompt)return;
  inp.value='';
  const box=document.getElementById('chat-box');
  box.textContent+='\n\n👤 '+prompt+'\n🤖 生成中…';
  box.scrollTop=box.scrollHeight;
  const r=await apiPost('/api/ai/chat',{prompt,model:curModel});
  box.textContent=box.textContent.replace('🤖 生成中…','🤖 '+(r.response||r.error||''));
  box.scrollTop=box.scrollHeight;
  log2act('AI对话: '+prompt.slice(0,20)+'…');
}

function setModel(m){curModel=m;document.getElementById('model-name').textContent=m;toast('模型: '+m);}

async function wanfa_all(){
  toast('⊙ 全域感知启动…',1500);
  await doSense();
  await readScreen();
  toast('✅ 感知完成');
  log2act('万法归宗·全域感知');
}

async function wanfa_screen_ai(){
  toast('读取屏幕…',1500);
  const sr=await apiGet('/api/screen');
  const texts=(sr.texts||[]).join('\n');
  if(!texts){toast('❌ 屏幕无文字');return;}
  sw('ai');
  document.getElementById('chat-in').value='请分析这个手机屏幕内容：\n'+texts;
  toast('✓ 已填入AI，点问发送');
  log2act('屏幕→AI分析');
}

async function wanfa_notify(){
  toast('读取通知…',1500);
  const r=await apiGet('/api/notifications');
  const notifs=r.notifications||r.items||[];
  if(!notifs.length){toast('❌ 无通知');return;}
  sw('ai');
  document.getElementById('chat-in').value='请摘要以下手机通知：\n'+JSON.stringify(notifs,null,2).slice(0,500);
  toast('✓ 已填入AI，点问发送');
  log2act('通知→AI摘要');
}

// 初始化
doSense();
setInterval(doSense,60000);
</script>
</body></html>
"""

# ── 主入口 ─────────────────────────────────────────────
def main():
    global PORT, PHONE_URL, PC_AGENT_URL
    ap = argparse.ArgumentParser(description="万法归宗 — 手机为宗，万物为法")
    ap.add_argument("--port",  type=int, default=PORT,     help="监听端口 (默认9915)")
    ap.add_argument("--phone", type=str, default=PHONE_URL, help="手机ScreenStream URL")
    ap.add_argument("--pc",    type=str, default=PC_AGENT_URL, help="电脑Agent URL")
    args = ap.parse_args()
    PORT = args.port; PHONE_URL = args.phone; PC_AGENT_URL = args.pc

    ip = _local_ip()

    # 后台发现手机（不阻塞服务器启动）
    def _bg_discover():
        global PHONE_URL
        if not _PHONE_LIB:
            return
        try:
            found = _discover(timeout=1.5)
            if found:
                PHONE_URL = found
                print(f"  📡 手机自动发现: {found}")
        except Exception:
            pass
    threading.Thread(target=_bg_discover, daemon=True).start()

    print(f"""
╔══════════════════════════════════════════╗
║           万  法  归  宗                 ║
║   手机为宗 · 万物为法 · 连之于道         ║
╠══════════════════════════════════════════╣
║  手机浏览器访问：                        ║
║  http://{ip}:{PORT:<5}                    ║
║                                          ║
║  手机：{PHONE_URL:<35}║
║  电脑：{PC_AGENT_URL:<35}║
║  AI  ：{OLLAMA_URL:<35}║
╚══════════════════════════════════════════╝
""")

    server = HTTPServer(("0.0.0.0", PORT), _Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  ⏹ 万法归宗 · 止")

if __name__ == "__main__":
    main()
