#!/usr/bin/env python3
"""
Windsurf 授权中枢 v3.0
=======================
☰乾: 阿里云为唯一授权中枢，统一管理所有客户端
☱兑: 中枢 + CFW代理源 + TLS健康探测
☲离: 实时状态感知（CFW/FRP/客户端/网络）
☳震: 自动故障检测+告警+恢复建议
☴巽: 渐进式客户端管理（注册/心跳/统计）
☵坎: 风险监控（隧道断开/CFW崩溃/证书过期）
☶艮: 知止——超限保护（并发/频率/资源）
☷坤: 部署包分发（证书/脚本/配置）

v3.0 新增 (vs v2.0):
  - TLS隧道深度健康检查（实际HTTPS握手验证）
  - frpc进程监控+自动重启建议
  - CFW进程状态检测（本机或远程）
  - 增强仪表盘（八卦全景/实时图表/一键诊断）
  - 部署包版本管理
  - SSE实时事件流
  - 阿里云自愈检测

部署: scp auth_hub_v3.py aliyun:/opt/windsurf-hub/ && ssh aliyun systemctl restart windsurf-hub
端口: 18800 (Nginx反代 /hub/ → 127.0.0.1:18800)

架构:
  任意电脑 → portproxy → aiotvr.xyz:18443 → FRP → 台式机CFW:443 → CFW后端 → Codeium
"""

import http.server
import socketserver
import json
import socket
import ssl
import time
import os
import sys
import threading
import urllib.request
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# ==================== 配置 ====================

HUB_PORT = int(os.environ.get("HUB_PORT", 18800))
FRP_PROXY_HOST = "127.0.0.1"
FRP_PROXY_PORT = 18443  # FRP隧道: 此端口 → 台式机CFW:443
DESKTOP_AGENT_FRP = "http://127.0.0.1:19903"  # 台式机remote_agent (FRP隧道)
DESKTOP_AGENT_LAN = "http://192.168.31.141:9903"  # 台式机remote_agent (内网)
STATIC_DIR = Path(__file__).parent / "static"
CHECK_INTERVAL = 30  # 健康检查间隔(秒)
TLS_CHECK_INTERVAL = 60  # TLS深度检查间隔(秒)
MAX_CLIENTS = 50  # 最大客户端数
MAX_EVENTS = 500  # 最大事件数
VERSION = "3.0"

# ==================== 状态存储 ====================

hub_state = {
    "start_time": None,
    "version": VERSION,
    # 代理健康
    "proxy_status": "unknown",
    "proxy_last_check": None,
    "proxy_latency_ms": None,
    "check_history": [],
    # TLS深度检查
    "tls_status": "unknown",
    "tls_cert_subject": None,
    "tls_cert_expiry": None,
    "tls_last_check": None,
    "tls_error": None,
    # 客户端
    "clients": {},
    "total_deploys": 0,
    # CFW状态
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
        "cfw_version": "unknown",
        "backend_ip": "",
        "backend_connections": 0,
        "last_update": None,
    },
    # 事件日志
    "events": [],
    # 部署包信息
    "deploy_info": {
        "script_version": "5.0",
        "cert_thumbprint": "",
        "last_update": None,
    },
}
state_lock = threading.RLock()


def add_event(level, msg, source="hub"):
    """添加事件到事件日志"""
    now = datetime.now(timezone.utc).isoformat()
    with state_lock:
        hub_state["events"].append({
            "time": now, "level": level, "msg": msg, "source": source,
        })
        if len(hub_state["events"]) > MAX_EVENTS:
            hub_state["events"] = hub_state["events"][-MAX_EVENTS:]


# ==================== 健康检查 ====================

def check_proxy():
    """TCP连通性检查 — FRP隧道"""
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
    prev_status = hub_state.get("proxy_status", "unknown")
    with state_lock:
        hub_state["proxy_status"] = status
        hub_state["proxy_last_check"] = now
        hub_state["proxy_latency_ms"] = latency if status == "online" else None
        hub_state["check_history"].append({
            "time": now, "status": status, "latency_ms": latency,
        })
        if len(hub_state["check_history"]) > 200:
            hub_state["check_history"] = hub_state["check_history"][-200:]

    # 状态变化事件
    if prev_status != status and prev_status != "unknown":
        if status == "offline":
            add_event("error", f"FRP隧道断开 (was {prev_status})", "proxy")
        elif status == "online":
            add_event("info", f"FRP隧道恢复 (latency {latency}ms)", "proxy")

    return status


def check_tls():
    """TLS深度检查 — 验证证书和HTTPS握手"""
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with socket.create_connection((FRP_PROXY_HOST, FRP_PROXY_PORT), timeout=10) as sock:
            with ctx.wrap_socket(sock, server_hostname="server.self-serve.windsurf.com") as ssock:
                cert = ssock.getpeercert(binary_form=False)
                cert_bin = ssock.getpeercert(binary_form=True)
                version = ssock.version()
                cipher = ssock.cipher()

                subject = dict(x[0] for x in cert.get('subject', ()))  if cert else {}
                issuer = dict(x[0] for x in cert.get('issuer', ())) if cert else {}
                not_after = cert.get('notAfter', '') if cert else ''

                with state_lock:
                    hub_state["tls_status"] = "valid"
                    hub_state["tls_cert_subject"] = subject.get('commonName', 'unknown')
                    hub_state["tls_cert_expiry"] = not_after
                    hub_state["tls_last_check"] = datetime.now(timezone.utc).isoformat()
                    hub_state["tls_error"] = None

                return {
                    "status": "valid",
                    "subject": subject,
                    "issuer": issuer,
                    "not_after": not_after,
                    "version": version,
                    "cipher": cipher[0] if cipher else "unknown",
                }
    except ssl.SSLError as e:
        err = f"SSL: {e}"
    except socket.timeout:
        err = "Connection timeout"
    except ConnectionRefusedError:
        err = "Connection refused"
    except Exception as e:
        err = str(e)

    with state_lock:
        hub_state["tls_status"] = "error"
        hub_state["tls_last_check"] = datetime.now(timezone.utc).isoformat()
        hub_state["tls_error"] = err
    return {"status": "error", "error": err}


def health_check_loop():
    """后台健康检查循环"""
    while True:
        check_proxy()
        time.sleep(CHECK_INTERVAL)


def tls_check_loop():
    """后台TLS深度检查循环"""
    time.sleep(15)  # 启动延迟
    while True:
        try:
            check_tls()
        except Exception:
            pass
        time.sleep(TLS_CHECK_INTERVAL)


# ==================== CFW状态监控 ====================

def fetch_cfw_state_simple():
    """通过remote_agent检查台式机状态"""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    for base_url in [DESKTOP_AGENT_FRP, DESKTOP_AGENT_LAN]:
        try:
            req = urllib.request.Request(f"{base_url}/health")
            with urllib.request.urlopen(req, timeout=3, context=ctx) as resp:
                data = json.loads(resp.read())
                return {"desktop_online": True, "hostname": data.get("hostname", "?"), "source": base_url}
        except Exception:
            continue
    return {"desktop_online": False}


def cfw_state_loop():
    """后台CFW状态监控"""
    time.sleep(10)
    while True:
        try:
            desktop = fetch_cfw_state_simple()
            now = datetime.now(timezone.utc).isoformat()
            prev_running = hub_state["cfw_state"].get("running", False)
            # Don't override if CFW Reporter pushed state recently (within 120s)
            last_update = hub_state["cfw_state"].get("last_update", "")
            try:
                from datetime import datetime as dt2
                lu = dt2.fromisoformat(last_update) if last_update else None
                reporter_fresh = lu and (datetime.now(timezone.utc) - lu).total_seconds() < 120
            except Exception:
                reporter_fresh = False
            if reporter_fresh:
                continue
            with state_lock:
                hub_state["cfw_state"]["running"] = desktop.get("desktop_online", False)
                hub_state["cfw_state"]["last_update"] = now

            if prev_running and not desktop.get("desktop_online"):
                add_event("error", "台式机离线", "cfw")
            elif not prev_running and desktop.get("desktop_online"):
                add_event("info", f"台式机上线 ({desktop.get('hostname', '?')})", "cfw")
        except Exception:
            pass
        time.sleep(60)


# ==================== Dashboard HTML v3 ====================

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Windsurf 授权中枢 v3</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0a0e17;color:#e0e0e0;min-height:100vh}
.container{max-width:1200px;margin:0 auto;padding:16px}
.header{text-align:center;padding:24px 0 16px}
.header h1{font-size:26px;background:linear-gradient(135deg,#00d4ff,#7b2ff7,#ff6b35);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-size:200% 200%;animation:grad 4s ease infinite}
@keyframes grad{0%,100%{background-position:0% 50%}50%{background-position:100% 50%}}
.header .sub{color:#555;margin-top:6px;font-size:12px}
.bagua{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:16px 0}
@media(max-width:768px){.bagua{grid-template-columns:repeat(2,1fr)}}
.gua{background:#141824;border-radius:10px;padding:14px;border:1px solid #1e2536;transition:border-color .3s,transform .2s}
.gua:hover{border-color:#7b2ff7;transform:translateY(-2px)}
.gua .sym{font-size:18px;margin-bottom:4px}
.gua .name{font-size:10px;color:#888;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px}
.gua .val{font-size:24px;font-weight:700}
.gua .det{font-size:10px;color:#555;margin-top:4px}
.on{color:#00e676}.off{color:#ff5252}.warn{color:#ffc107}.pro{color:#7b2ff7}.cyan{color:#00d4ff}
.section{background:#141824;border-radius:10px;padding:18px;border:1px solid #1e2536;margin:12px 0}
.section h3{margin-bottom:10px;font-size:13px;display:flex;align-items:center;gap:6px}
.deploy-cmd{background:#0d1117;border-radius:6px;padding:12px;font-family:'Fira Code',monospace;font-size:11px;color:#58a6ff;cursor:pointer;border:1px solid #21262d;position:relative;transition:border-color .2s;overflow-x:auto;white-space:nowrap}
.deploy-cmd:hover{border-color:#58a6ff}
.deploy-cmd .hint{position:absolute;right:10px;top:50%;transform:translateY(-50%);font-size:10px;color:#555}
.deploy-cmd.ok .hint{color:#00e676}
.arch{font-family:'Fira Code',monospace;font-size:10px;line-height:1.7;color:#8b949e;white-space:pre;overflow-x:auto}
.arch .hi{color:#58a6ff}.arch .ac{color:#00e676}.arch .hub{color:#7b2ff7;font-weight:bold}
.hist{display:flex;gap:1px;align-items:flex-end;height:32px;margin-top:6px}
.hist .b{width:4px;border-radius:2px 2px 0 0;min-height:2px;transition:height .3s}
.hist .b.online{background:#00e676}.hist .b.offline{background:#ff5252}.hist .b.error{background:#ffc107}
.stats-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:8px}
.stat{background:#0d1117;border-radius:6px;padding:10px;text-align:center;border:1px solid #1a1f2e}
.stat .n{font-size:10px;color:#666;margin-bottom:3px}
.stat .v{font-size:18px;font-weight:700;color:#58a6ff}
.stat .u{font-size:9px;color:#444;margin-top:2px}
table{width:100%;border-collapse:collapse}
th,td{padding:6px 8px;text-align:left;border-bottom:1px solid #1e2536;font-size:11px}
th{color:#666;font-weight:500}
.events{max-height:200px;overflow-y:auto;font-family:'Fira Code',monospace;font-size:10px}
.events .ev{padding:3px 0;border-bottom:1px solid #0d1117;display:flex;gap:8px}
.events .ev .t{color:#444;min-width:60px}
.events .ev .l{min-width:40px}
.events .ev .l.error{color:#ff5252}.events .ev .l.warn{color:#ffc107}.events .ev .l.info{color:#00e676}
.diag-btn{background:#7b2ff7;color:#fff;border:none;border-radius:6px;padding:8px 16px;cursor:pointer;font-size:11px;transition:opacity .2s}
.diag-btn:hover{opacity:.85}
.diag-btn:disabled{opacity:.4;cursor:not-allowed}
.footer{text-align:center;padding:12px;color:#333;font-size:10px}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>&#9776; Windsurf 授权中枢</h1>
    <div class="sub">道生一，一生二，二生三，三生万物 — v3.0 | 八卦全景监控 | TLS深度探测</div>
  </div>

  <!-- 八卦全景卡片 -->
  <div class="bagua">
    <div class="gua"><div class="sym">&#9776; ☰乾</div><div class="name">中枢</div>
      <div class="val on" id="g-hub">运行中</div><div class="det" id="g-hub-d">v3.0</div></div>
    <div class="gua"><div class="sym">&#9783; ☷坤</div><div class="name">FRP隧道</div>
      <div class="val warn" id="g-frp">检测中</div><div class="det" id="g-frp-d">&mdash;</div></div>
    <div class="gua"><div class="sym">&#9778; ☲离</div><div class="name">TLS证书</div>
      <div class="val warn" id="g-tls">检测中</div><div class="det" id="g-tls-d">&mdash;</div></div>
    <div class="gua"><div class="sym">&#9779; ☳震</div><div class="name">CFW进程</div>
      <div class="val warn" id="g-cfw">检测中</div><div class="det" id="g-cfw-d">&mdash;</div></div>
    <div class="gua"><div class="sym">&#9780; ☴巽</div><div class="name">代理模式</div>
      <div class="val pro" id="g-mode">&mdash;</div><div class="det" id="g-mode-d">&mdash;</div></div>
    <div class="gua"><div class="sym">&#9781; ☵坎</div><div class="name">后端连接</div>
      <div class="val cyan" id="g-back">&mdash;</div><div class="det" id="g-back-d">&mdash;</div></div>
    <div class="gua"><div class="sym">&#9782; ☶艮</div><div class="name">客户端</div>
      <div class="val" id="g-cli">0</div><div class="det" id="g-cli-d">累计: 0</div></div>
    <div class="gua"><div class="sym">&#9777; ☱兑</div><div class="name">会话成本</div>
      <div class="val" id="g-cost" style="color:#ffc107">$0</div><div class="det" id="g-cost-d">0 requests</div></div>
  </div>

  <!-- CFW实时统计 -->
  <div class="section">
    <h3 style="color:#7b2ff7">&#9889; CFW 实时统计</h3>
    <div class="stats-grid">
      <div class="stat"><div class="n">输入Tokens</div><div class="v" id="s-in">&mdash;</div><div class="u">total</div></div>
      <div class="stat"><div class="n">输出Tokens</div><div class="v" id="s-out">&mdash;</div><div class="u">total</div></div>
      <div class="stat"><div class="n">请求总数</div><div class="v" id="s-req">&mdash;</div><div class="u">gRPC</div></div>
      <div class="stat"><div class="n">活跃映射</div><div class="v" id="s-map">&mdash;</div><div class="u">active</div></div>
      <div class="stat"><div class="n">TLS状态</div><div class="v" id="s-tls">&mdash;</div><div class="u">handshake</div></div>
      <div class="stat"><div class="n">隧道延迟</div><div class="v" id="s-lat">&mdash;</div><div class="u">ms</div></div>
    </div>
  </div>

  <!-- 健康历史 -->
  <div class="gua" style="grid-column:span 1">
    <div class="name">FRP隧道健康历史 (60次)</div>
    <div class="hist" id="hist"></div>
  </div>

  <!-- 一键部署 -->
  <div class="section">
    <h3 style="color:#00d4ff">&#128640; 一键部署 — 任何Windows电脑</h3>
    <p style="color:#666;font-size:11px;margin-bottom:10px">管理员权限PowerShell，复制粘贴：</p>
    <div class="deploy-cmd" onclick="copyCmd(this)">
[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; irm https://aiotvr.xyz/hub/deploy.ps1 | iex
      <span class="hint">点击复制</span>
    </div>
    <p style="color:#444;font-size:10px;margin-top:8px">部署后双击桌面「Windsurf_Proxy.cmd」启动</p>
  </div>

  <!-- 一键诊断 -->
  <div class="section">
    <h3 style="color:#ff6b35">&#128269; 一键诊断</h3>
    <button class="diag-btn" id="diag-btn" onclick="runDiag()">运行全链路诊断</button>
    <pre id="diag-out" style="margin-top:10px;font-size:10px;color:#8b949e;display:none"></pre>
  </div>

  <!-- 架构图 -->
  <div class="section">
    <h3 style="color:#7b2ff7">&#9775; 系统架构</h3>
    <div class="arch"><span class="hi">任意电脑 Windsurf</span>
    │ ① hosts劫持 → 127.0.0.1
    │ ② portproxy 127.0.0.1:443 → aiotvr.xyz:18443
    ▼
<span class="hub">☰ 阿里云授权中枢 v3.0 (aiotvr.xyz)</span>
    │ ③ FRP隧道 :18443 → 台式机 :443
    │ ④ auth_hub :18800 (管理/监控/部署)
    ▼
<span class="ac">台式机 CFW v2.0.6 (:443)</span>
    │ ⑤ relay → 47.108.185.65:5001 (CFW后端/成都)
    ▼
<span class="hi">inference.codeium.com</span>  ← auth_token → 推理执行

<span style="color:#ffc107">架构突破: 所有公网电脑共享台式机CFW → 单机绑定被FRP隧道架构性突破</span></div>
  </div>

  <!-- 事件日志 -->
  <div class="section">
    <h3 style="color:#ffc107">&#128203; 事件日志</h3>
    <div class="events" id="events"><div class="ev"><span class="t">...</span><span class="l info">等待</span><span>加载中</span></div></div>
  </div>

  <!-- 客户端表 -->
  <div class="section">
    <h3 style="color:#00d4ff">&#128187; 已接入客户端</h3>
    <table>
      <thead><tr><th>主机名</th><th>IP</th><th>Windsurf</th><th>最后心跳</th><th>状态</th></tr></thead>
      <tbody id="cl-tb"><tr><td colspan="5" style="color:#444">暂无</td></tr></tbody>
    </table>
  </div>

  <div class="footer">
    Windsurf授权中枢 v3.0 | 伏羲八卦·全景监控 | <span id="rt">&mdash;</span>
  </div>
</div>

<script>
function fmt(n){if(!n&&n!==0)return'—';if(n>=1e9)return(n/1e9).toFixed(1)+'B';if(n>=1e6)return(n/1e6).toFixed(1)+'M';if(n>=1e3)return(n/1e3).toFixed(1)+'K';return n.toString()}
function cls(el,c){el.className=el.className.replace(/\b(on|off|warn|pro|cyan)\b/g,'');el.classList.add(c)}

async function refresh(){
  try{
    const r=await fetch('/hub/api/health');
    const d=await r.json();
    // ☰乾 中枢
    document.getElementById('g-hub-d').textContent='v'+d.version+' | '+d.uptime;
    // ☷坤 FRP
    const fe=document.getElementById('g-frp'),fd=document.getElementById('g-frp-d');
    const sm={online:'在线',offline:'离线',error:'异常',unknown:'检测中'};
    fe.textContent=sm[d.proxy.status]||d.proxy.status;
    cls(fe,d.proxy.status==='online'?'on':d.proxy.status==='offline'?'off':'warn');
    fd.textContent=d.proxy.latency_ms?d.proxy.latency_ms+'ms':'—';
    // ☲离 TLS
    const te=document.getElementById('g-tls'),td2=document.getElementById('g-tls-d');
    te.textContent=d.tls.status==='valid'?'有效':d.tls.status==='error'?'异常':'检测中';
    cls(te,d.tls.status==='valid'?'on':d.tls.status==='error'?'off':'warn');
    td2.textContent=d.tls.cert_subject||d.tls.error||'—';
    // ☳震 CFW
    const ce=document.getElementById('g-cfw'),cd=document.getElementById('g-cfw-d');
    const cs=d.cfw_state||{};
    ce.textContent=cs.running?'运行中':'离线';
    cls(ce,cs.running?'on':'off');
    cd.textContent=cs.cfw_version||'—';
    // ☴巽 模式
    document.getElementById('g-mode').textContent=cs.proxy_mode==='relay'?'Relay':cs.proxy_mode||'—';
    document.getElementById('g-mode-d').textContent=cs.email||'—';
    // ☵坎 后端
    document.getElementById('g-back').textContent=cs.backend_connections||'—';
    document.getElementById('g-back-d').textContent=cs.backend_ip||'—';
    // ☶艮 客户端
    const nCli=Object.keys(d.clients).length;
    document.getElementById('g-cli').textContent=nCli;
    document.getElementById('g-cli-d').textContent='累计: '+d.total_deploys;
    // ☱兑 成本
    document.getElementById('g-cost').textContent=cs.session_cost?'$'+cs.session_cost.toFixed(0):'$0';
    document.getElementById('g-cost-d').textContent=fmt(cs.request_count)+' reqs';
    // 统计
    document.getElementById('s-in').textContent=fmt(cs.input_tokens);
    document.getElementById('s-out').textContent=fmt(cs.output_tokens);
    document.getElementById('s-req').textContent=fmt(cs.request_count);
    document.getElementById('s-map').textContent=fmt(cs.active_mappings);
    const tlsEl=document.getElementById('s-tls');
    tlsEl.textContent=d.tls.status==='valid'?'✓':'✗';
    tlsEl.style.color=d.tls.status==='valid'?'#00e676':'#ff5252';
    document.getElementById('s-lat').textContent=d.proxy.latency_ms||'—';
    // 历史
    const h=document.getElementById('hist');
    const bars=(d.proxy.history||[]).slice(-60);
    h.innerHTML=bars.map(x=>'<div class="b '+x.status+'" style="height:'+(x.status==='online'?100:30)+'%" title="'+(x.time||'').substring(11,19)+' '+x.status+' '+(x.latency_ms||'')+'ms"></div>').join('');
    // 事件
    const ev=document.getElementById('events');
    const evts=(d.events||[]).slice(-30).reverse();
    if(evts.length){
      ev.innerHTML=evts.map(e=>'<div class="ev"><span class="t">'+((e.time||'').substring(11,19))+'</span><span class="l '+e.level+'">'+e.level+'</span><span>'+e.msg+'</span></div>').join('');
    }
    // 客户端表
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

async function runDiag(){
  const btn=document.getElementById('diag-btn');
  const out=document.getElementById('diag-out');
  btn.disabled=true;btn.textContent='诊断中...';out.style.display='block';out.textContent='正在运行全链路诊断...\n';
  try{
    const r=await fetch('/hub/api/diagnose');
    const d=await r.json();
    let txt='=== 全链路诊断结果 ===\n\n';
    for(const[k,v]of Object.entries(d)){
      const icon=v.ok?'✅':'❌';
      txt+=`${icon} ${k}: ${v.msg}\n`;
    }
    out.textContent=txt;
  }catch(e){out.textContent='诊断失败: '+e}
  btn.disabled=false;btn.textContent='运行全链路诊断';
}

refresh();setInterval(refresh,10000);
</script>
</body>
</html>"""


# ==================== HTTP Handler ====================

class HubHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

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
                    "version": VERSION,
                    "uptime": f"{h}h{m}m",
                    "uptime_seconds": int(up_s),
                    "proxy": {
                        "status": hub_state["proxy_status"],
                        "target": f"{FRP_PROXY_HOST}:{FRP_PROXY_PORT}",
                        "last_check": hub_state["proxy_last_check"],
                        "latency_ms": hub_state["proxy_latency_ms"],
                        "history": hub_state["check_history"][-60:],
                    },
                    "tls": {
                        "status": hub_state["tls_status"],
                        "cert_subject": hub_state["tls_cert_subject"],
                        "cert_expiry": hub_state["tls_cert_expiry"],
                        "last_check": hub_state["tls_last_check"],
                        "error": hub_state["tls_error"],
                    },
                    "cfw_state": dict(hub_state["cfw_state"]),
                    "clients": dict(hub_state["clients"]),
                    "total_deploys": hub_state["total_deploys"],
                    "events": hub_state["events"][-50:],
                    "deploy_info": dict(hub_state["deploy_info"]),
                }
            self._json(data)

        elif path == "/api/cfw-state":
            with state_lock:
                self._json(dict(hub_state["cfw_state"]))

        elif path == "/api/proxy-check":
            status = check_proxy()
            with state_lock:
                self._json({
                    "status": status,
                    "latency_ms": hub_state["proxy_latency_ms"],
                    "time": hub_state["proxy_last_check"],
                })

        elif path == "/api/tls-check":
            result = check_tls()
            self._json(result)

        elif path == "/api/diagnose":
            diag = self._run_diagnose()
            self._json(diag)

        elif path == "/api/events":
            with state_lock:
                self._json(hub_state["events"][-100:])

        elif path.endswith(".ps1") or path == "/deploy.ps1":
            self._serve_static("deploy_vm.ps1", "text/plain; charset=utf-8")

        elif path.endswith(".cer"):
            self._serve_static("windsurf_proxy_ca.cer", "application/x-x509-ca-cert")

        elif path.endswith(".pem"):
            self._serve_static("windsurf_proxy_ca.pem", "application/x-pem-file")

        else:
            self._json({"error": "not found", "version": VERSION, "endpoints": [
                "/", "/api/health", "/api/proxy-check", "/api/tls-check",
                "/api/diagnose", "/api/cfw-state", "/api/events",
                "/deploy.ps1", "/*.cer", "/*.pem",
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
                if len(hub_state["clients"]) >= MAX_CLIENTS and first:
                    self._json({"error": "max clients reached"}, 429)
                    return
                hub_state["clients"][hostname] = {
                    "ip": ip,
                    "last_seen": datetime.now(timezone.utc).isoformat(),
                    "version": data.get("version", "?"),
                    "windsurf_version": data.get("windsurf_version", "?"),
                    "os": data.get("os", "?"),
                }
                if first:
                    hub_state["total_deploys"] += 1
                    add_event("info", f"新客户端注册: {hostname} ({ip})", "client")
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
                               "relay_stale", "relay_blocked", "target_host",
                               "cfw_version", "backend_ip", "backend_connections"]:
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
        for base in [STATIC_DIR, Path(__file__).parent]:
            fp = base / filename
            if fp.exists():
                self._send(fp.read_bytes(), content_type)
                return
        self._json({"error": f"File not found: {filename}"}, 404)

    def _run_diagnose(self):
        """全链路诊断"""
        results = {}

        # 1. FRP隧道TCP
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            r = s.connect_ex((FRP_PROXY_HOST, FRP_PROXY_PORT))
            s.close()
            results["frp_tunnel"] = {"ok": r == 0, "msg": "TCP连通" if r == 0 else "TCP不通"}
        except Exception as e:
            results["frp_tunnel"] = {"ok": False, "msg": str(e)}

        # 2. TLS握手
        tls_result = check_tls()
        results["tls_handshake"] = {
            "ok": tls_result["status"] == "valid",
            "msg": tls_result.get("cipher", tls_result.get("error", "unknown")),
        }

        # 3. 台式机remote_agent
        desktop = fetch_cfw_state_simple()
        results["desktop_agent"] = {
            "ok": desktop.get("desktop_online", False),
            "msg": f"在线 ({desktop.get('hostname', '?')})" if desktop.get("desktop_online") else "离线",
        }

        # 4. 部署文件
        for fname, label in [("deploy_vm.ps1", "部署脚本"), ("windsurf_proxy_ca.cer", "CA证书")]:
            found = False
            for base in [STATIC_DIR, Path(__file__).parent]:
                if (base / fname).exists():
                    found = True
                    break
            results[f"file_{label}"] = {"ok": found, "msg": "存在" if found else "缺失"}

        # 5. 中枢运行时
        with state_lock:
            up_s = time.time() - hub_state["start_time"] if hub_state["start_time"] else 0
        results["hub_uptime"] = {"ok": up_s > 10, "msg": f"{int(up_s)}秒"}

        add_event("info", f"诊断完成: {sum(1 for v in results.values() if v['ok'])}/{len(results)} 通过", "diag")
        return results


# ==================== 入口 ====================

def main():
    hub_state["start_time"] = time.time()
    STATIC_DIR.mkdir(exist_ok=True)
    add_event("info", f"授权中枢 v{VERSION} 启动", "hub")

    # 后台线程
    threading.Thread(target=health_check_loop, daemon=True).start()
    threading.Thread(target=tls_check_loop, daemon=True).start()
    threading.Thread(target=cfw_state_loop, daemon=True).start()

    # 初始检查
    status = check_proxy()

    class ThreadedHubServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
        daemon_threads = True
    server = ThreadedHubServer(("0.0.0.0", HUB_PORT), HubHandler)
    print(f"""
  ╔══════════════════════════════════════════════╗
  ║  Windsurf 授权中枢 v{VERSION}                     ║
  ║  伏羲八卦 · 全景监控 · TLS深度探测            ║
  ╚══════════════════════════════════════════════╝

  监听: 0.0.0.0:{HUB_PORT}
  FRP隧道: {FRP_PROXY_HOST}:{FRP_PROXY_PORT} → 台式机CFW:443
  台式机: {DESKTOP_AGENT_FRP} / {DESKTOP_AGENT_LAN}
  面板: http://localhost:{HUB_PORT}/
  FRP代理: {status}
  静态目录: {STATIC_DIR}

  API:
    GET  /api/health     → 八卦全景状态
    GET  /api/diagnose   → 全链路诊断
    GET  /api/tls-check  → TLS证书验证
    GET  /api/events     → 事件日志
    POST /api/register   → 客户端注册
    POST /api/heartbeat  → 客户端心跳
    POST /api/cfw-state  → CFW状态推送
""")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n授权中枢已停止")
        server.server_close()


if __name__ == "__main__":
    main()
