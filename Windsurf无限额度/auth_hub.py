#!/usr/bin/env python3
"""
Windsurf 授权中枢 v2.0
=======================
道生一(☰乾): 阿里云为唯一授权中枢
一生二(☱兑): 中枢 + CFW代理源
二生三(☲离): 中枢 + 代理 + 部署脚本
三生万物: 任意数量客户端接入，不受环境限制

v2.0 新增:
  - CFW实时状态监控 (tokens/requests/cost/models/JWT)
  - 增强仪表盘 (实时统计/模型使用/会话成本)
  - 客户端使用统计跟踪
  - 台式机remote_agent集成
  - 自动故障检测与告警

部署: scp auth_hub.py aliyun:/opt/windsurf-hub/ && ssh aliyun systemctl restart windsurf-hub
端口: 18800 (Nginx反代 /hub/ → 127.0.0.1:18800)

架构:
  任意电脑 → portproxy → aiotvr.xyz:18443 → FRP → 台式机CFW:443 → CFW后端 → Codeium
"""

import http.server
import json
import socket
import time
import os
import sys
import threading
import urllib.request
import ssl
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

# ==================== 配置 ====================

HUB_PORT = int(os.environ.get("HUB_PORT", 18800))
FRP_PROXY_HOST = "127.0.0.1"
FRP_PROXY_PORT = 18443  # FRP隧道: 此端口 → 台式机CFW:443
DESKTOP_AGENT = "http://192.168.31.141:9903"  # 台式机remote_agent (FRP内网)
DESKTOP_AGENT_FRP = "http://127.0.0.1:19903"  # 台式机remote_agent (FRP隧道)
STATIC_DIR = Path(__file__).parent / "static"
CHECK_INTERVAL = 30  # 健康检查间隔(秒)
CFW_STATE_INTERVAL = 60  # CFW状态刷新间隔(秒)

# 状态存储
hub_state = {
    "start_time": None,
    "proxy_status": "unknown",
    "proxy_last_check": None,
    "proxy_latency_ms": None,
    "check_history": [],
    "clients": {},
    "total_deploys": 0,
    # v2: CFW实时状态
    "cfw_state": {
        "proxy_mode": "unknown",
        "email": "",
        "running": False,
        "active_mappings": 0,
        "request_count": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "session_cost": 0.0,
        "mitm_detected": False,
        "security_clean": True,
        "relay_stale": False,
        "relay_blocked": False,
        "target_host": "",
        "last_update": None,
    },
    "cfw_state_history": [],  # 每分钟快照
}
state_lock = threading.Lock()


# ==================== 健康检查 ====================

def check_proxy():
    """检查CFW代理是否可通过FRP隧道访问"""
    start = time.monotonic()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        result = s.connect_ex((FRP_PROXY_HOST, FRP_PROXY_PORT))
        s.close()
        latency = round((time.monotonic() - start) * 1000, 1)
        status = "online" if result == 0 else "offline"
    except Exception:
        latency = None
        status = "error"

    now = datetime.now(timezone.utc).isoformat()
    with state_lock:
        hub_state["proxy_status"] = status
        hub_state["proxy_last_check"] = now
        hub_state["proxy_latency_ms"] = latency if status == "online" else None
        hub_state["check_history"].append({
            "time": now, "status": status, "latency_ms": latency,
        })
        if len(hub_state["check_history"]) > 200:
            hub_state["check_history"] = hub_state["check_history"][-200:]
    return status


def health_check_loop():
    """后台健康检查循环"""
    while True:
        check_proxy()
        time.sleep(CHECK_INTERVAL)


# ==================== v2: CFW状态监控 ====================

def fetch_cfw_state_from_agent():
    """通过台式机remote_agent获取CFW运行时状态"""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    for base_url in [DESKTOP_AGENT_FRP, DESKTOP_AGENT]:
        try:
            url = f"{base_url}/exec"
            # 通过remote_agent执行内存提取命令
            cmd_data = json.dumps({
                "command": "python",
                "args": ["-c", CFW_EXTRACT_SCRIPT],
                "timeout": 30
            }).encode()
            req = urllib.request.Request(url, data=cmd_data, method="POST",
                                        headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
                result = json.loads(resp.read())
                if result.get("stdout"):
                    try:
                        state = json.loads(result["stdout"])
                        return state
                    except json.JSONDecodeError:
                        pass
        except Exception:
            continue
    return None


def fetch_cfw_state_simple():
    """简化版: 通过remote_agent检查CFW进程和端口"""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    for base_url in [DESKTOP_AGENT_FRP, DESKTOP_AGENT]:
        try:
            req = urllib.request.Request(f"{base_url}/health")
            with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
                data = json.loads(resp.read())
                return {"desktop_online": True, "hostname": data.get("hostname", "?")}
        except Exception:
            continue
    return {"desktop_online": False}


def cfw_state_loop():
    """后台CFW状态监控循环"""
    time.sleep(10)  # 启动延迟
    while True:
        try:
            desktop = fetch_cfw_state_simple()
            now = datetime.now(timezone.utc).isoformat()
            with state_lock:
                if desktop.get("desktop_online"):
                    hub_state["cfw_state"]["last_update"] = now
                    hub_state["cfw_state"]["running"] = True
                else:
                    hub_state["cfw_state"]["running"] = False
                    hub_state["cfw_state"]["last_update"] = now
        except Exception:
            pass
        time.sleep(CFW_STATE_INTERVAL)


# CFW内存提取脚本 (在台式机上执行)
CFW_EXTRACT_SCRIPT = r'''
import ctypes, ctypes.wintypes as wt, json, subprocess, re, struct
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
class MBI(ctypes.Structure):
    _fields_ = [("BaseAddress",ctypes.c_ulonglong),("AllocationBase",ctypes.c_ulonglong),
        ("AllocationProtect",wt.DWORD),("_p1",wt.DWORD),("RegionSize",ctypes.c_ulonglong),
        ("State",wt.DWORD),("Protect",wt.DWORD),("Type",wt.DWORD),("_p2",wt.DWORD)]
def get_pid():
    r = subprocess.run(["tasklist","/FI","IMAGENAME eq CodeFreeWindsurf*","/FO","CSV","/NH"],
        capture_output=True,text=True)
    for l in r.stdout.strip().split("\n"):
        if "CodeFree" in l: return int(l.strip('"').split('","')[1])
    return None
pid = get_pid()
if not pid: print(json.dumps({"error":"no_cfw"})); exit()
h = k32.OpenProcess(0x0410,False,pid)
if not h: print(json.dumps({"error":"access_denied"})); exit()
mbi=MBI(); addr=0; found=[]
while k32.VirtualQueryEx(h,ctypes.c_ulonglong(addr),ctypes.byref(mbi),ctypes.sizeof(mbi)):
    if mbi.State==0x1000 and (mbi.Protect&0xFF) in {2,4,8,0x20,0x40,0x80} and 0<mbi.RegionSize<64*1024*1024:
        buf=(ctypes.c_char*mbi.RegionSize)(); nr=ctypes.c_ulonglong(0)
        if k32.ReadProcessMemory(h,ctypes.c_ulonglong(mbi.BaseAddress),buf,mbi.RegionSize,ctypes.byref(nr)):
            data=bytes(buf[:nr.value]); text=data.decode("utf-8",errors="replace")
            for key in ['"proxy_mode"','"active_mappings"','"email"']:
                idx=text.find(key)
                if idx>=0:
                    bs=text.rfind("{",max(0,idx-500),idx)
                    if bs>=0:
                        d=0
                        for i in range(bs,min(len(text),bs+5000)):
                            if text[i]=="{":d+=1
                            elif text[i]=="}":d-=1
                            if d==0:
                                try:
                                    obj=json.loads(text[bs:i+1].replace("\x00",""))
                                    if isinstance(obj,dict) and len(obj)>5: found.append(obj)
                                except: pass
                                break
            if found: break
    na=mbi.BaseAddress+mbi.RegionSize
    if na<=addr or na>0x7FFFFFFFFFFF: break
    addr=na
k32.CloseHandle(h)
if found: print(json.dumps(found[0],ensure_ascii=False))
else: print(json.dumps({"pid":pid,"error":"no_state"}))
'''


# ==================== Dashboard HTML ====================

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Windsurf 授权中枢 v2</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0a0e17;color:#e0e0e0;min-height:100vh}
.container{max-width:1100px;margin:0 auto;padding:20px}
.header{text-align:center;padding:30px 0 20px}
.header h1{font-size:28px;background:linear-gradient(135deg,#00d4ff,#7b2ff7);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.header .sub{color:#555;margin-top:8px;font-size:13px}
.header .ver{color:#333;font-size:11px;margin-top:4px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px;margin:20px 0}
.card{background:#141824;border-radius:12px;padding:18px;border:1px solid #1e2536}
.card h3{font-size:11px;color:#888;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px}
.card .val{font-size:28px;font-weight:700}
.card .det{font-size:11px;color:#555;margin-top:5px}
.on{color:#00e676}.off{color:#ff5252}.unk{color:#ffc107}.pro{color:#7b2ff7}
.section{background:#141824;border-radius:12px;padding:22px;border:1px solid #1e2536;margin:16px 0}
.section h3{margin-bottom:12px;font-size:14px}
.deploy-cmd{background:#0d1117;border-radius:8px;padding:14px;font-family:'Fira Code',monospace;font-size:12px;color:#58a6ff;overflow-x:auto;cursor:pointer;border:1px solid #21262d;position:relative;transition:border-color .2s}
.deploy-cmd:hover{border-color:#58a6ff}
.deploy-cmd .hint{position:absolute;right:12px;top:50%;transform:translateY(-50%);font-size:11px;color:#555}
.deploy-cmd.ok .hint{color:#00e676}
.arch{font-family:'Fira Code',monospace;font-size:11px;line-height:1.8;color:#8b949e;white-space:pre;overflow-x:auto}
.arch .hi{color:#58a6ff}.arch .ac{color:#00e676}.arch .hub{color:#7b2ff7;font-weight:bold}
.hist{display:flex;gap:2px;align-items:flex-end;height:36px;margin-top:6px}
.hist .b{width:5px;border-radius:2px 2px 0 0;min-height:3px;transition:height .3s}
.hist .b.on{background:#00e676}.hist .b.off{background:#ff5252}.hist .b.error{background:#ffc107}
.stats-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px}
.stat{background:#0d1117;border-radius:8px;padding:12px;text-align:center;border:1px solid #1a1f2e}
.stat .n{font-size:11px;color:#666;margin-bottom:4px}
.stat .v{font-size:20px;font-weight:700;color:#58a6ff}
.stat .u{font-size:10px;color:#444;margin-top:2px}
table{width:100%;border-collapse:collapse}
th,td{padding:7px 10px;text-align:left;border-bottom:1px solid #1e2536;font-size:12px}
th{color:#666;font-weight:500}
.pulse{animation:pulse 2s ease-in-out infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}
.footer{text-align:center;padding:16px;color:#333;font-size:11px}
@media(max-width:600px){.cards{grid-template-columns:1fr 1fr}.container{padding:12px}}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>&#9776; Windsurf 授权中枢</h1>
    <div class="sub">道生一，一生二，二生三，三生万物 — 阿里云统一授权，突破单机绑定</div>
    <div class="ver">v2.0 | CFW实时状态监控 | 多客户端管理</div>
  </div>

  <div class="cards">
    <div class="card">
      <h3>中枢状态</h3>
      <div class="val on" id="hub-st">运行中</div>
      <div class="det" id="hub-up">启动中...</div>
    </div>
    <div class="card">
      <h3>CFW代理</h3>
      <div class="val unk" id="px-st">检测中...</div>
      <div class="det" id="px-det">&mdash;</div>
    </div>
    <div class="card">
      <h3>代理模式</h3>
      <div class="val pro" id="cfw-mode">—</div>
      <div class="det" id="cfw-email">&mdash;</div>
    </div>
    <div class="card">
      <h3>接入客户端</h3>
      <div class="val" id="cl-n">0</div>
      <div class="det" id="dp-n">累计部署: 0</div>
    </div>
    <div class="card">
      <h3>会话成本</h3>
      <div class="val" id="cfw-cost" style="color:#ffc107">$0</div>
      <div class="det" id="cfw-reqs">0 requests</div>
    </div>
  </div>

  <!-- v2: CFW实时统计 -->
  <div class="section">
    <h3 style="color:#7b2ff7">&#9889; CFW 实时统计</h3>
    <div class="stats-grid">
      <div class="stat"><div class="n">输入Tokens</div><div class="v" id="s-in">—</div><div class="u">total</div></div>
      <div class="stat"><div class="n">输出Tokens</div><div class="v" id="s-out">—</div><div class="u">total</div></div>
      <div class="stat"><div class="n">请求总数</div><div class="v" id="s-req">—</div><div class="u">gRPC calls</div></div>
      <div class="stat"><div class="n">活跃映射</div><div class="v" id="s-map">—</div><div class="u">active</div></div>
      <div class="stat"><div class="n">安全状态</div><div class="v" id="s-sec">—</div><div class="u">MITM检测</div></div>
      <div class="stat"><div class="n">Relay状态</div><div class="v" id="s-relay">—</div><div class="u">stale check</div></div>
    </div>
  </div>

  <div class="card">
    <h3>代理健康历史 (最近60次)</h3>
    <div class="hist" id="hist"></div>
  </div>

  <div class="section">
    <h3 style="color:#00d4ff">&#9889; 一键部署 — 在任何Windows电脑上运行</h3>
    <p style="color:#666;font-size:12px;margin-bottom:12px">管理员权限打开PowerShell，复制粘贴以下命令：</p>
    <div class="deploy-cmd" onclick="copyCmd(this)">
[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; irm https://aiotvr.xyz/agent/deploy-vm.ps1 | iex
      <span class="hint">点击复制</span>
    </div>
    <p style="color:#444;font-size:11px;margin-top:10px">部署完成后，双击桌面「Windsurf_Proxy.cmd」启动即可无限额度</p>
  </div>

  <div class="section">
    <h3 style="color:#7b2ff7">&#9775; 系统架构</h3>
    <div class="arch"><span class="hi">任意电脑 Windsurf</span>
    │ ① hosts劫持 → 127.0.0.1
    │ ② portproxy 127.0.0.1:443 → aiotvr.xyz:18443
    ▼
<span class="hub">☰ 阿里云授权中枢 v2.0 (aiotvr.xyz)</span>
    │ ③ FRP隧道 :18443 → 台式机 :443
    │ ④ CFW状态监控 (remote_agent :9903)
    ▼
<span class="ac">台式机 CFW v2.0.x (:443)</span>  ← 设备码 4F57-4F49-080E-79C8
    │ ⑤ relay → 47.108.185.65:5001 (Connect-RPC/Go)
    ▼
<span class="hi">inference.codeium.com</span>  ← Relay JWT(2h TTL) → 推理执行

<span style="color:#ffc107">突破: 所有电脑共享台式机CFW → 设备码唯一 → 单机绑定被架构性突破</span></div>
  </div>

  <div class="section">
    <h3 style="color:#ffc107">&#128187; 已接入客户端</h3>
    <table>
      <thead><tr><th>主机名</th><th>IP</th><th>Windsurf版本</th><th>最后心跳</th><th>状态</th></tr></thead>
      <tbody id="cl-tb"><tr><td colspan="5" style="color:#444">暂无客户端注册</td></tr></tbody>
    </table>
  </div>

  <div class="footer">
    Windsurf授权中枢 v2.0 | 道·法·术 三层统一 | <span id="rt">&mdash;</span>
  </div>
</div>

<script>
function fmt(n){if(!n&&n!==0)return'—';if(n>=1e9)return(n/1e9).toFixed(1)+'B';if(n>=1e6)return(n/1e6).toFixed(1)+'M';if(n>=1e3)return(n/1e3).toFixed(1)+'K';return n.toString()}
async function refresh(){
  try{
    const r=await fetch('/hub/api/health');
    const d=await r.json();
    document.getElementById('hub-up').textContent='运行 '+d.uptime;
    // Proxy status
    const ps=document.getElementById('px-st'),pd=document.getElementById('px-det');
    const sm={online:'在线',offline:'离线',error:'异常',unknown:'未知'};
    ps.textContent=sm[d.proxy.status]||d.proxy.status;
    ps.className='val '+(d.proxy.status==='online'?'on':d.proxy.status==='offline'?'off':'unk');
    pd.textContent=d.proxy.latency_ms?d.proxy.latency_ms+'ms延迟':'上次: '+(d.proxy.last_check||'—').substring(11,19);
    // CFW state (v2)
    const c=d.cfw_state||{};
    document.getElementById('cfw-mode').textContent=c.proxy_mode==='relay'?'Relay':c.proxy_mode||'—';
    document.getElementById('cfw-email').textContent=c.email||'—';
    document.getElementById('cfw-cost').textContent=c.session_cost?'$'+c.session_cost.toFixed(0):'$0';
    document.getElementById('cfw-reqs').textContent=fmt(c.request_count)+' requests';
    document.getElementById('s-in').textContent=fmt(c.input_tokens);
    document.getElementById('s-out').textContent=fmt(c.output_tokens);
    document.getElementById('s-req').textContent=fmt(c.request_count);
    document.getElementById('s-map').textContent=fmt(c.active_mappings);
    const secEl=document.getElementById('s-sec');
    secEl.textContent=c.security_clean?'安全':'警告';
    secEl.style.color=c.security_clean?'#00e676':'#ff5252';
    const relEl=document.getElementById('s-relay');
    relEl.textContent=c.relay_stale?'过期':'正常';
    relEl.style.color=c.relay_stale?'#ff5252':'#00e676';
    // Clients
    document.getElementById('cl-n').textContent=Object.keys(d.clients).length;
    document.getElementById('dp-n').textContent='累计部署: '+d.total_deploys;
    // History
    const h=document.getElementById('hist');
    const bars=(d.proxy.history||[]).slice(-60);
    h.innerHTML=bars.map(x=>'<div class="b '+x.status+'" style="height:'+(x.status==='online'?100:30)+'%" title="'+((x.time||'').substring(11,19))+' '+x.status+' '+(x.latency_ms||'')+'ms"></div>').join('');
    // Client table
    const tb=document.getElementById('cl-tb');
    const cl=Object.entries(d.clients);
    if(cl.length>0){
      tb.innerHTML=cl.map(([n,i])=>{
        const ago=Math.round(Date.now()/1000-new Date(i.last_seen).getTime()/1000);
        const st=ago<180?'<span class="on">在线</span>':'<span class="off">离线</span>';
        return '<tr><td>'+n+'</td><td>'+i.ip+'</td><td>'+(i.windsurf_version||'—')+'</td><td>'+(i.last_seen||'').substring(11,19)+'</td><td>'+st+'</td></tr>';
      }).join('');
    }
    document.getElementById('rt').textContent=new Date().toLocaleTimeString();
  }catch(e){console.error(e)}
}
function copyCmd(el){
  const t=el.textContent.replace('点击复制','').trim();
  navigator.clipboard.writeText(t).then(()=>{
    el.classList.add('ok');el.querySelector('.hint').textContent='已复制!';
    setTimeout(()=>{el.classList.remove('ok');el.querySelector('.hint').textContent='点击复制'},2000);
  });
}
refresh();setInterval(refresh,15000);
</script>
</body>
</html>"""


def _refresh_cfw_state_once():
    """一次性刷新CFW状态 (用于手动触发)"""
    try:
        state = fetch_cfw_state_from_agent()
        if state and not state.get("error"):
            now = datetime.now(timezone.utc).isoformat()
            with state_lock:
                for k in ["proxy_mode", "email", "running", "active_mappings",
                           "request_count", "input_tokens", "output_tokens",
                           "session_cost", "mitm_detected", "security_clean",
                           "relay_stale", "relay_blocked", "target_host"]:
                    if k in state:
                        hub_state["cfw_state"][k] = state[k]
                hub_state["cfw_state"]["last_update"] = now
                # 保存历史快照
                hub_state["cfw_state_history"].append({
                    "time": now,
                    "requests": state.get("request_count", 0),
                    "input_tokens": state.get("input_tokens", 0),
                    "output_tokens": state.get("output_tokens", 0),
                    "cost": state.get("session_cost", 0),
                })
                if len(hub_state["cfw_state_history"]) > 1440:  # 24h @ 1/min
                    hub_state["cfw_state_history"] = hub_state["cfw_state_history"][-1440:]
    except Exception:
        pass


# ==================== HTTP Handler ====================

class HubHandler(http.server.BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass  # suppress default logging

    def _send(self, body, content_type="application/json", status=200):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, obj, status=200):
        self._send(json.dumps(obj, ensure_ascii=False), "application/json", status)

    def _route(self, path):
        """Strip /hub prefix for Nginx reverse proxy compatibility"""
        if path.startswith("/hub"):
            path = path[4:]
        return path.rstrip("/") or "/"

    def do_GET(self):
        path = self._route(urlparse(self.path).path)

        if path == "/":
            self._send(DASHBOARD_HTML, "text/html; charset=utf-8")

        elif path == "/api/health":
            with state_lock:
                up_s = time.time() - hub_state["start_time"] if hub_state["start_time"] else 0
                h, m = int(up_s // 3600), int((up_s % 3600) // 60)
                data = {
                    "hub": "online",
                    "version": "2.0",
                    "uptime": f"{h}h{m}m",
                    "uptime_seconds": int(up_s),
                    "proxy": {
                        "status": hub_state["proxy_status"],
                        "target": f"{FRP_PROXY_HOST}:{FRP_PROXY_PORT}",
                        "last_check": hub_state["proxy_last_check"],
                        "latency_ms": hub_state["proxy_latency_ms"],
                        "history": hub_state["check_history"][-60:],
                    },
                    "cfw_state": dict(hub_state["cfw_state"]),
                    "clients": dict(hub_state["clients"]),
                    "total_deploys": hub_state["total_deploys"],
                }
            self._json(data)

        elif path == "/api/cfw-state":
            with state_lock:
                self._json(dict(hub_state["cfw_state"]))

        elif path == "/api/cfw-state/update":
            # Trigger immediate CFW state refresh
            threading.Thread(target=_refresh_cfw_state_once, daemon=True).start()
            self._json({"ok": True, "msg": "refresh triggered"})

        elif path == "/api/proxy-check":
            status = check_proxy()
            with state_lock:
                self._json({
                    "status": status,
                    "latency_ms": hub_state["proxy_latency_ms"],
                    "time": hub_state["proxy_last_check"],
                })

        elif path.endswith(".ps1"):
            self._serve_static("deploy-vm.ps1", "text/plain; charset=utf-8")

        elif path.endswith(".cer"):
            self._serve_static("windsurf_proxy_ca.cer", "application/x-x509-ca-cert")

        elif path.endswith(".pem"):
            self._serve_static("windsurf_proxy_ca.pem", "application/x-pem-file")

        else:
            self._json({"error": "not found", "endpoints": [
                "/", "/api/health", "/api/proxy-check",
                "/api/cfw-state", "/api/cfw-state/update",
            ]}, 404)

    def do_POST(self):
        path = self._route(urlparse(self.path).path)

        if path == "/api/register":
            cl = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(cl).decode() if cl else "{}"
            try:
                data = json.loads(body)
            except Exception:
                data = {}

            hostname = data.get("hostname", "unknown")
            ip = self.client_address[0]
            first = hostname not in hub_state.get("clients", {})

            with state_lock:
                hub_state["clients"][hostname] = {
                    "ip": ip,
                    "last_seen": datetime.now(timezone.utc).isoformat(),
                    "version": data.get("version", "?"),
                    "windsurf_version": data.get("windsurf_version", "?"),
                }
                if first:
                    hub_state["total_deploys"] += 1

            self._json({"ok": True, "proxy_status": hub_state["proxy_status"]})

        elif path == "/api/heartbeat":
            cl = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(cl).decode() if cl else "{}"
            try:
                data = json.loads(body)
            except Exception:
                data = {}

            hostname = data.get("hostname", "unknown")
            with state_lock:
                if hostname in hub_state["clients"]:
                    hub_state["clients"][hostname]["last_seen"] = datetime.now(timezone.utc).isoformat()
                    if data.get("windsurf_version"):
                        hub_state["clients"][hostname]["windsurf_version"] = data["windsurf_version"]

            self._json({"ok": True, "proxy_status": hub_state["proxy_status"]})

        elif path == "/api/cfw-state":
            # v2: 台式机主动推送CFW状态
            cl = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(cl).decode() if cl else "{}"
            try:
                data = json.loads(body)
            except Exception:
                data = {}

            if data:
                now = datetime.now(timezone.utc).isoformat()
                with state_lock:
                    for k in ["proxy_mode", "email", "running", "active_mappings",
                               "request_count", "input_tokens", "output_tokens",
                               "session_cost", "mitm_detected", "security_clean",
                               "relay_stale", "relay_blocked", "target_host"]:
                        if k in data:
                            hub_state["cfw_state"][k] = data[k]
                    hub_state["cfw_state"]["last_update"] = now
                self._json({"ok": True})
            else:
                self._json({"error": "empty body"}, 400)

        else:
            self._json({"error": "not found"}, 404)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _serve_static(self, filename, content_type):
        """Serve a static file from STATIC_DIR or script directory"""
        for base in [STATIC_DIR, Path(__file__).parent]:
            fp = base / filename
            if fp.exists():
                self._send(fp.read_bytes(), content_type)
                return
        self._json({"error": f"File not found: {filename}"}, 404)


# ==================== 入口 ====================

def main():
    hub_state["start_time"] = time.time()

    # Create static dir if needed
    STATIC_DIR.mkdir(exist_ok=True)

    # Start background health checker
    t = threading.Thread(target=health_check_loop, daemon=True)
    t.start()

    # v2: Start CFW state monitor
    t2 = threading.Thread(target=cfw_state_loop, daemon=True)
    t2.start()

    # Initial check
    status = check_proxy()

    server = http.server.HTTPServer(("0.0.0.0", HUB_PORT), HubHandler)
    print(f"""
  ╔══════════════════════════════════════════════╗
  ║  Windsurf 授权中枢 v2.0                      ║
  ║  道生一 · 阿里云统一授权 · CFW实时监控         ║
  ╚══════════════════════════════════════════════╝

  监听: 0.0.0.0:{HUB_PORT}
  代理: {FRP_PROXY_HOST}:{FRP_PROXY_PORT} (FRP隧道 → 台式机CFW)
  台式机: {DESKTOP_AGENT} / {DESKTOP_AGENT_FRP}
  面板: http://localhost:{HUB_PORT}/
  CFW代理: {status}
  静态目录: {STATIC_DIR}

  v2 API:
    GET  /api/health        → 中枢+CFW完整状态
    GET  /api/cfw-state     → CFW实时状态
    GET  /api/cfw-state/update → 触发立即刷新
    POST /api/cfw-state     → 台式机推送状态
    POST /api/register      → 客户端注册
    POST /api/heartbeat     → 客户端心跳
""")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n授权中枢已停止")
        server.server_close()


if __name__ == "__main__":
    main()
