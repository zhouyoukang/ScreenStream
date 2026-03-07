module.exports = function(PUBLIC_URL, AUTH_AGENT_KEY) {
return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>道 · 远程中枢</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>道</text></svg>">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0a0e17;color:#e0e0e0;font-family:-apple-system,'Segoe UI','Microsoft YaHei',sans-serif;min-height:100vh}
.app{max-width:820px;margin:0 auto;padding:12px 16px}
.hdr{display:flex;align-items:center;justify-content:space-between;padding:16px 0;flex-wrap:wrap;gap:8px}
.hdr h1{font-size:20px;color:#7c8aff;letter-spacing:2px}
.hdr .sub{font-size:11px;color:#556;margin-top:2px}
.pills{display:flex;gap:8px}
.pill{display:flex;align-items:center;gap:5px;padding:5px 12px;border-radius:20px;font-size:12px;font-weight:600;transition:all .3s}
.pill .d{width:7px;height:7px;border-radius:50%;animation:pulse 1.5s infinite}
.pill.on{background:#0d1a0d;color:#4caf50}.pill.on .d{background:#4caf50}
.pill.off{background:#1a1a2a;color:#556}.pill.off .d{background:#556;animation:none}
.pill.wait{background:#1a1a0d;color:#ffa726}.pill.wait .d{background:#ffa726}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
.tabs{display:flex;gap:2px;border-bottom:1px solid #1a2040;margin-bottom:16px;overflow-x:auto}
.tab{background:none;border:none;color:#556;padding:10px 16px;font-size:13px;cursor:pointer;border-bottom:2px solid transparent;font-family:inherit;transition:all .2s;white-space:nowrap}
.tab:hover{color:#a0a8c0}.tab.act{color:#7c8aff;border-bottom-color:#7c8aff}
.page{display:none}.page.act{display:block}
.card{background:#111828;border-radius:12px;padding:18px;margin-bottom:14px;border:1px solid #1a2040}
.card h3{color:#7c8aff;font-size:15px;margin-bottom:10px}
.card p{font-size:13px;color:#889;line-height:1.8}
.card p b{color:#c0c8e0}
.card.connected{border-color:#4caf5040}
.cmd-box{background:#0a0e14;border:1px solid #2a3050;border-radius:8px;padding:14px;margin:10px 0;font-family:'Cascadia Code','Fira Code',Consolas,monospace;font-size:12px;color:#7c8aff;word-break:break-all;white-space:pre-wrap;user-select:all}
.cbtn{background:#7c8aff;color:#fff;border:none;padding:6px 14px;border-radius:6px;cursor:pointer;font-size:12px;font-family:inherit;margin-top:4px;transition:all .2s}
.cbtn:hover{background:#6a78ee;transform:translateY(-1px)}.cbtn.ok{background:#4caf50}
.cbtn:active{transform:translateY(0)}
.msg{padding:12px 16px;margin:8px 0;border-radius:10px;font-size:13px;line-height:1.7;animation:fadeIn .3s}
@keyframes fadeIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
.msg.system{background:#111828;border-left:3px solid #7c8aff;color:#a0a8c0}
.msg.alert-ok{background:#0d1a0d;border-left:3px solid #4caf50;color:#a0d0a0}
.msg.alert-warn{background:#1a1a0d;border-left:3px solid #ffa726;color:#d0c090}
.msg.alert-err{background:#1a0d0d;border-left:3px solid #f44336;color:#d0a0a0}
.msg.action{background:#131a2a;border:1px solid #2a3050}
.msg.action h3{color:#7c8aff;font-size:14px;margin-bottom:8px}
.msg.action .steps{font-size:12px;color:#889;line-height:2}.msg.action .steps b{color:#c0c8e0}
.term{background:#060a10;border:1px solid #1a2040;border-radius:10px;min-height:300px;max-height:70vh;overflow-y:auto;font-family:'Cascadia Code','Fira Code',Consolas,monospace;font-size:12px;padding:12px}
.te{margin-bottom:12px;border-bottom:1px solid #111828;padding-bottom:10px}
.te-cmd{color:#4caf50;margin-bottom:4px}.te-cmd::before{content:'> ';color:#556}
.te-out{color:#a0a8c0;white-space:pre-wrap;word-break:break-all;max-height:400px;overflow-y:auto}
.te-err{color:#f44336}
.te-t{color:#445;font-size:10px;margin-top:4px}
.te-pending .te-out{color:#ffa726;animation:pulse 1.5s infinite}
.ti{display:flex;gap:8px;margin-top:10px}
.ti input{flex:1;background:#0a0e14;border:1px solid #2a3050;border-radius:8px;padding:10px 14px;color:#e0e0e0;font-family:'Cascadia Code','Fira Code',Consolas,monospace;font-size:13px;outline:none;transition:border-color .2s}
.ti input:focus{border-color:#7c8aff}
.ti input::placeholder{color:#334}
.ti button{background:#7c8aff;color:#fff;border:none;padding:10px 20px;border-radius:8px;cursor:pointer;font-size:13px;font-family:inherit;transition:all .2s}
.ti button:hover:not(:disabled){background:#6a78ee}
.ti button:disabled{background:#222;color:#445;cursor:not-allowed}
.empty{text-align:center;color:#334;padding:40px;font-size:14px}
.pw{background:#1a2040;border-radius:6px;height:5px;margin:10px 0;overflow:hidden}
.pf{height:100%;background:linear-gradient(90deg,#7c8aff,#4caf50);border-radius:6px;transition:width .4s}
.ti-r{display:flex;align-items:center;padding:6px 0;font-size:12px;border-bottom:1px solid #0a0e17}
.ti-r .n{flex:1;color:#889}
.ti-r .r{padding:2px 8px;border-radius:6px;font-size:11px;font-weight:600;min-width:36px;text-align:center}
.ti-r .r.pass{background:#0d1a0d;color:#4caf50}
.ti-r .r.fail{background:#1a0d0d;color:#f44336}
.ti-r .r.wait{background:#1a1a0d;color:#ffa726}
.ti-r .dd{font-size:10px;color:#556;margin-left:8px;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.sg{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}
.si{background:#0d1220;border-radius:10px;padding:14px;border:1px solid #1a204020}
.si .l{font-size:11px;color:#556;margin-bottom:4px;text-transform:uppercase;letter-spacing:.5px}
.si .v{font-size:15px;color:#c0c8e0;font-weight:600}
.si .v.sm{font-size:12px;font-weight:400}
.bigb{display:block;width:100%;padding:12px;margin:10px 0;border-radius:10px;border:none;font-size:14px;font-family:inherit;cursor:pointer;text-align:center;background:linear-gradient(135deg,#7c8aff,#5a68dd);color:#fff;transition:all .2s}
.bigb:hover{transform:translateY(-1px);box-shadow:0 4px 20px #7c8aff40}
.bigb:active{transform:translateY(0)}
.info-bar{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:4px}
.user-input{display:flex;gap:8px;margin:14px 0}
.user-input textarea{flex:1;background:#0a0e14;border:1px solid #2a3050;border-radius:8px;padding:10px 14px;color:#e0e0e0;font-family:'Cascadia Code','Fira Code',Consolas,monospace;font-size:13px;outline:none;resize:vertical;min-height:40px;max-height:200px;transition:border-color .2s}
.user-input textarea:focus{border-color:#7c8aff}
.user-input textarea::placeholder{color:#334}
.user-input button{background:linear-gradient(135deg,#7c8aff,#5a68dd);color:#fff;border:none;padding:10px 20px;border-radius:8px;cursor:pointer;font-size:13px;font-family:inherit;align-self:flex-end;transition:all .2s}
.user-input button:hover{transform:translateY(-1px);box-shadow:0 2px 12px #7c8aff40}
.info-chip{background:#111828;border:1px solid #1a2040;border-radius:8px;padding:8px 14px;font-size:11px;color:#889;display:flex;align-items:center;gap:6px}
.info-chip b{color:#c0c8e0;font-weight:600}
.diag-summary{display:flex;gap:12px;margin:12px 0;flex-wrap:wrap}
.ds-item{background:#0d1220;border-radius:8px;padding:10px 16px;font-size:13px;font-weight:600;display:flex;align-items:center;gap:6px}
.ds-item.ok{color:#4caf50}.ds-item.fail{color:#f44336}
.dev-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px;margin:12px 0}
.dev-card{background:#111828;border:1px solid #1a2040;border-radius:12px;padding:16px;transition:all .3s;position:relative}
.dev-card:hover{border-color:#7c8aff40;transform:translateY(-1px)}
.dev-card.selected{border-color:#7c8aff;box-shadow:0 0 12px #7c8aff20}
.dev-card.offline{opacity:.5;border-color:#33333380}
.dev-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px}
.dev-name{font-size:15px;font-weight:700;color:#c0c8e0;display:flex;align-items:center;gap:6px}
.dev-name .dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.dev-name .dot.on{background:#4caf50;box-shadow:0 0 6px #4caf5060;animation:pulse 1.5s infinite}
.dev-name .dot.off{background:#556}
.dev-badge{padding:3px 8px;border-radius:10px;font-size:10px;font-weight:700;letter-spacing:.3px}
.dev-badge.configured{background:#0d1a0d;color:#4caf50}
.dev-badge.needed{background:#1a1a0d;color:#ffa726}
.dev-badge.partial{background:#1a0d0d;color:#f44336}
.dev-badge.checking{background:#131a2a;color:#7c8aff}
.dev-meta{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px}
.dev-meta span{font-size:11px;color:#667;background:#0a0e14;padding:2px 8px;border-radius:6px}
.dev-meta span b{color:#889}
.dev-actions{display:flex;gap:6px;flex-wrap:wrap}
.dev-btn{padding:5px 12px;border-radius:6px;border:1px solid #1a2040;background:#0a0e14;color:#a0a8c0;font-size:11px;cursor:pointer;transition:all .2s;font-family:inherit}
.dev-btn:hover{border-color:#7c8aff;color:#7c8aff;background:#131a2a}
.dev-btn.primary{background:linear-gradient(135deg,#7c8aff,#5a68dd);color:#fff;border:none}
.dev-btn.primary:hover{transform:translateY(-1px);box-shadow:0 2px 8px #7c8aff40}
.dev-btn.danger{background:linear-gradient(135deg,#e94560,#c73e54);color:#fff;border:none}
.dev-btn:disabled{opacity:.4;cursor:not-allowed;transform:none!important;box-shadow:none!important}
</style>
</head>
<body>
<div id="simpleMode" class="app">
  <div style="text-align:center;padding:30px 0 16px">
    <h1 style="color:#7c8aff;font-size:26px;letter-spacing:2px">Windsurf 配置助手</h1>
    <p style="color:#556;font-size:12px;margin-top:6px">一行命令 · 全自动配置</p>
  </div>
  <div class="card">
    <h3>在目标电脑运行以下命令</h3>
    <p>以<b>管理员</b>打开 PowerShell，粘贴并回车</p>
    <div class="cmd-box" id="sCmd">irm "${PUBLIC_URL.indexOf('aiotvr.xyz')>=0?'https':'http'}://${PUBLIC_URL}/agent.ps1?key=${AUTH_AGENT_KEY}" | iex</div>
    <button class="cbtn" onclick="cpEl('sCmd',this)">复制命令</button>
  </div>
  <div id="sDevices">
    <div id="sWait" class="card" style="border-color:#ffa72640;text-align:center;padding:20px">
      <div class="pill wait" style="display:inline-flex;margin-bottom:6px"><span class="d"></span>等待连接...</div>
      <p style="color:#445;font-size:11px">运行命令后此处自动更新</p>
    </div>
  </div>
  <div id="sSetupArea" style="display:none">
    <div class="card">
      <div id="sText"></div>
      <div class="pw" style="margin:10px 0"><div class="pf" id="sBar" style="width:0%"></div></div>
      <div id="sLog"></div>
    </div>
  </div>
  <div id="sMsgs"></div>
  <div style="text-align:center;padding:16px"><a onclick="toggleAdmin()" style="color:#2a3050;font-size:10px;cursor:pointer">管理员模式</a></div>
</div>
<div class="app" id="adminApp" style="display:none">
  <div class="hdr">
    <div><h1>道 · 远程中枢</h1><div class="sub">五感连接远方 · 大脑分析万象</div></div>
    <div class="pills">
      <span id="sPill" class="pill wait"><span class="d"></span>五感</span>
      <span id="aPill" class="pill off"><span class="d"></span>Agent</span>
      <select id="agentSel" style="background:#111828;color:#7c8aff;border:1px solid #1e3a5f;border-radius:8px;padding:5px 10px;font-size:12px;font-family:inherit;outline:none;display:none;cursor:pointer" onchange="switchAgent(this.value)"></select>
    </div>
  </div>
  <div class="tabs">
    <button class="tab act" onclick="go('home',this)">首页</button>
    <button class="tab" onclick="go('term',this)">终端</button>
    <button class="tab" onclick="go('diag',this)">诊断</button>
    <button class="tab" onclick="go('sys',this)">系统</button>
    <button class="tab" onclick="go('wssetup',this)">Windsurf配置</button>
  </div>
  <div id="p-home" class="page act">
    <div id="agentCard" class="card">
      <h3>连接 Agent（远程之手）</h3>
      <p>在目标电脑以<b>管理员身份</b>打开 PowerShell，粘贴以下命令：</p>
      <div class="cmd-box" id="installCmd">irm "${PUBLIC_URL.indexOf('aiotvr.xyz')>=0?'https':'http'}://${PUBLIC_URL}/agent.ps1?key=${AUTH_AGENT_KEY}" | iex</div>
      <button class="cbtn" onclick="cpEl('installCmd',this)">复制安装命令</button>
      <p style="margin-top:10px;font-size:11px;color:#445">Agent连接后解锁远程终端、系统信息等全部能力</p>
    </div>
    <div id="devicesSection" style="display:none">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
        <h3 style="color:#7c8aff;font-size:14px">已连接设备</h3>
        <span id="devCount" style="font-size:11px;color:#556"></span>
      </div>
      <div id="devGrid" class="dev-grid"></div>
    </div>
    <div id="agentInfo" style="display:none"></div>
    <div class="card" style="border-color:#7c8aff30">
      <h3 style="font-size:13px;margin-bottom:8px">发送消息给大脑</h3>
      <div class="user-input">
        <textarea id="userMsg" rows="1" placeholder="输入消息、配置信息、或任何内容..." onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendUserMsg()}"></textarea>
        <button onclick="sendUserMsg()">发送</button>
      </div>
    </div>
    <div id="msgs"></div>
  </div>
  <div id="p-term" class="page">
    <div id="termNotice" class="card" style="display:none;border-color:#ffa72640">
      <p style="color:#ffa726;text-align:center">Agent未连接，无法执行命令。请先在首页连接Agent。</p>
    </div>
    <div class="term" id="termOut"><div class="empty" id="termEmpty">等待命令执行...</div></div>
    <div class="ti">
      <input type="text" id="termIn" placeholder="输入 PowerShell 命令..." onkeydown="if(event.key==='Enter')termSend()">
      <button id="termBtn" onclick="termSend()" disabled>执行</button>
    </div>
  </div>
  <div id="p-diag" class="page">
    <div id="diagBox"><div class="card"><h3>网络诊断</h3><p>连接后自动运行浏览器级网络可达性测试</p></div></div>
  </div>
  <div id="p-sys" class="page">
    <div id="sysBox"><div class="empty">等待 Agent 发送系统信息...</div></div>
  </div>
  <div id="p-wssetup" class="page">
    <div class="card">
      <h3>Windsurf 共享代理 — 一键配置</h3>
      <p>全自动配置，让此电脑通过共享代理使用 Windsurf 全模型（Claude/GPT/Gemini等）。<br><b>自动检测网络</b>（LAN直连/FRP公网）并选择最优路径，配置完成后<b>自动重启Windsurf</b>。</p>
      <p style="margin-top:8px"><b>前提:</b> ① Agent已连接（管理员权限） ② 已安装Windsurf IDE ③ 主机代理运行中<br><b>零手动操作</b> — 全部自动完成，无需重启电脑</p>
      <div style="margin:16px 0">
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px">
          <div class="info-chip"><b>代理地址:</b> aiotvr.xyz:18443</div>
          <div class="info-chip"><b>配置项:</b> 证书+hosts+端口转发+SSL_CERT_FILE+settings+快捷方式</div>
        </div>
        <button class="bigb" id="wsSetupBtn" onclick="runWindsurfSetup()" style="background:linear-gradient(135deg,#e94560,#7c8aff)">一键配置 Windsurf 共享代理</button>
      </div>
      <div id="wsSetupLog" style="display:none">
        <div class="pw"><div class="pf" id="wsSetupProgress" style="width:0%"></div></div>
        <div id="wsSetupResults"></div>
      </div>
    </div>
    <div class="card" style="border-color:#1a204040">
      <h3 style="font-size:13px;color:#889">配置说明</h3>
      <p style="font-size:12px;line-height:2;color:#667">
        <b>1.</b> 检查管理员权限<br>
        <b>2.</b> 🔍 自动检测网络拓扑(LAN直连/FRP公网)<br>
        <b>3.</b> 安装TLS自签证书到受信任根<br>
        <b>4.</b> 设置hosts劫持条目(自动选择IP)<br>
        <b>5.</b> 配置网络路由(LAN跳过/FRP端口转发)<br>
        <b>6.</b> 设置SSL_CERT_FILE环境变量<br>
        <b>7.</b> 配置Windsurf settings.json<br>
        <b>8.</b> 检测Windsurf安装路径(全盘扫描)<br>
        <b>9.</b> 创建代理启动器<br>
        <b>10.</b> 端到端连通性验证<br>
        <b>11.</b> 🔄 自动重启Windsurf(代理模式)<br>
        <br>全部自动完成，<b>无需任何手动操作</b>。
      </p>
    </div>
  </div>
</div>
<script>
var ws=null,agentOk=false,diagRan=false,pendingCmds={},cmdId=0;
var basePath=location.pathname.replace(/\\/+$/,'');
var allAgents=[];
function renderDeviceCards(agents,selected){
  allAgents=agents||[];
  var connected=allAgents.filter(function(a){return a.connected});
  var sd=document.getElementById('sDevices');
  if(sd){
    if(connected.length===0){
      sd.innerHTML='<div class="card" style="border-color:#ffa72640;text-align:center;padding:20px"><div class="pill wait" style="display:inline-flex;margin-bottom:6px"><span class="d"></span>\u7b49\u5f85\u8fde\u63a5...</div><p style="color:#445;font-size:11px">\u8fd0\u884c\u547d\u4ee4\u540e\u6b64\u5904\u81ea\u52a8\u66f4\u65b0</p></div>';
    } else {
      var h='<div class="dev-grid">';
      connected.forEach(function(a){
        var cfg=a.wsConfig||'checking';
        var bc=cfg==='configured'?'configured':cfg==='needed'?'needed':cfg==='partial'?'partial':'checking';
        var bt=cfg==='configured'?'\u2705 \u5df2\u914d\u7f6e':cfg==='needed'?'\u2699\ufe0f \u5f85\u914d\u7f6e':cfg==='partial'?'\u26a0\ufe0f \u90e8\u5206':'\ud83d\udd0d \u68c0\u6d4b\u4e2d';
        h+='<div class="dev-card'+(a.id===selected?' selected':'')+'">';
        h+='<div class="dev-head"><span class="dev-name"><span class="dot on"></span>'+esc(a.hostname||a.id)+'</span><span class="dev-badge '+bc+'">'+bt+'</span></div>';
        h+='<div class="dev-meta"><span><b>'+esc(a.user||'?')+'</b></span><span>'+esc(a.os||'?').replace(/Microsoft /g,'')+'</span>'+(a.isAdmin?'<span style="color:#4caf50"><b>\u7ba1\u7406\u5458</b></span>':'')+'</div>';
        h+='<div class="dev-actions">';
        if(cfg==='configured')h+='<button class="dev-btn" onclick="runWindsurfSetup(\\x27'+esc(a.id)+'\\x27)">\u91cd\u65b0\u914d\u7f6e</button>';
        else if(cfg==='needed')h+='<button class="dev-btn primary" onclick="runWindsurfSetup(\\x27'+esc(a.id)+'\\x27)">\u4e00\u952e\u914d\u7f6e</button>';
        else if(cfg==='partial')h+='<button class="dev-btn danger" onclick="runWindsurfSetup(\\x27'+esc(a.id)+'\\x27)">\u4fee\u590d\u914d\u7f6e</button>';
        else h+='<button class="dev-btn" disabled>\u68c0\u6d4b\u4e2d...</button>';
        h+='<button class="dev-btn" onclick="switchAgent(\\x27'+esc(a.id)+'\\x27);toggleAdmin()">\u7ba1\u7406</button>';
        h+='</div></div>';
      });
      h+='</div>';
      sd.innerHTML=h;
    }
  }
  // Sync agentCard visibility with device cards
  var ac=document.getElementById('agentCard');
  if(ac&&connected.length>0)ac.style.display='none';
  var dg=document.getElementById('devGrid'),ds=document.getElementById('devicesSection'),dc=document.getElementById('devCount');
  if(dg&&ds){
    if(allAgents.length===0){ds.style.display='none';return}
    ds.style.display='';
    if(dc)dc.textContent=connected.length+'/'+allAgents.length+' \u5728\u7ebf';
    var h2='';
    allAgents.forEach(function(a){
      var isOn=a.connected,cfg=a.wsConfig||'checking';
      var bc=cfg==='configured'?'configured':cfg==='needed'?'needed':cfg==='partial'?'partial':'checking';
      var bt=cfg==='configured'?'\u2705 \u5df2\u914d\u7f6e':cfg==='needed'?'\u2699\ufe0f \u5f85\u914d\u7f6e':cfg==='partial'?'\u26a0\ufe0f \u90e8\u5206':'\ud83d\udd0d \u68c0\u6d4b\u4e2d';
      if(!isOn){bc='';bt='\u274c \u79bb\u7ebf'}
      h2+='<div class="dev-card'+(a.id===selected?' selected':'')+(isOn?'':' offline')+'">';
      h2+='<div class="dev-head"><span class="dev-name"><span class="dot '+(isOn?'on':'off')+'"></span>'+esc(a.hostname||a.id)+'</span><span class="dev-badge '+bc+'">'+bt+'</span></div>';
      h2+='<div class="dev-meta"><span><b>'+esc(a.user||'?')+'</b></span><span>'+esc(a.os||'?').replace(/Microsoft /g,'')+'</span>'+(a.isAdmin?'<span style="color:#4caf50"><b>\u7ba1\u7406\u5458</b></span>':'')+'</div>';
      h2+='<div class="dev-actions">';
      if(isOn){
        if(cfg==='configured')h2+='<button class="dev-btn" onclick="runWindsurfSetup(\\x27'+esc(a.id)+'\\x27)">\u91cd\u65b0\u914d\u7f6e</button>';
        else if(cfg==='needed')h2+='<button class="dev-btn primary" onclick="runWindsurfSetup(\\x27'+esc(a.id)+'\\x27)">\u4e00\u952e\u914d\u7f6e</button>';
        else if(cfg==='partial')h2+='<button class="dev-btn danger" onclick="runWindsurfSetup(\\x27'+esc(a.id)+'\\x27)">\u4fee\u590d\u914d\u7f6e</button>';
        else h2+='<button class="dev-btn" disabled>\u68c0\u6d4b\u4e2d...</button>';
        h2+='<button class="dev-btn'+(a.id===selected?' primary':'')+'" onclick="switchAgent(\\x27'+esc(a.id)+'\\x27)">'+(a.id===selected?'\u2605 \u5f53\u524d':'\u5207\u6362')+'</button>';
      }
      h2+='</div></div>';
    });
    dg.innerHTML=h2;
  }
}
function getToken(){var c=document.cookie.split(';').map(function(s){return s.trim()}).find(function(s){return s.startsWith('dao_token=')});return c?c.split('=')[1]:''}
function connect(){
  var proto=location.protocol==='https:'?'wss:':'ws:';
  ws=new WebSocket(proto+'//'+location.host+basePath+'/ws/sense?token='+getToken());
  ws.onopen=function(){
    sPill('on','五感');
    ws.send(JSON.stringify({type:'hello',ua:navigator.userAgent,time:new Date().toISOString(),screen:screen.width+'x'+screen.height}));
    if(!diagRan){diagRan=true;runDiag()}
  };
  ws.onmessage=function(e){try{handle(JSON.parse(e.data))}catch(x){console.error(x)}};
  ws.onclose=function(){sPill('wait','重连中...');setTimeout(connect,3000)};
  ws.onerror=function(){};
}
function handle(m){
  if(m.type==='say') addMsg(m.level||'system',m.text);
  else if(m.type==='command') showCmd(m.title||'命令',m.cmd,m.steps||'');
  else if(m.type==='run_diag'){diagRan=true;runDiag()}
  else if(m.type==='agent_status'){
    agentOk=m.connected;
    if(m.connected){
      aPill('on',m.hostname||'Agent');
      document.getElementById('agentCard').style.display='none';
      var ds0=document.getElementById('devicesSection');if(ds0&&allAgents.length>0)ds0.style.display='';
      document.getElementById('termBtn').disabled=false;
      document.getElementById('termNotice').style.display='none';
      showAgentInfo(m);
    } else {
      aPill('off','\u79bb\u7ebf');
      document.getElementById('agentCard').style.display='';
      document.getElementById('agentInfo').style.display='none';
      document.getElementById('termBtn').disabled=true;
      document.getElementById('termNotice').style.display='';
    }
  }
  else if(m.type==='terminal') addTerm(m.cmd,m.output,m.ok,m.id);
  else if(m.type==='sysinfo') showSys(m);
  else if(m.type==='agents_list'){updateAgentSel(m.agents,m.selected);renderDeviceCards(m.agents,m.selected)}
  else if(m.type==='agent_switch'){updateAgentSel(m.agents,m.selected);renderDeviceCards(m.agents,m.selected)}
  else if(m.type==='setup_status'){
    if(m.status==='needed'&&!window._autoSetupDone){
      window._autoSetupDone=true;
      var sa2=document.getElementById('sSetupArea');if(sa2)sa2.style.display='';
      var st2=document.getElementById('sText');if(st2)st2.innerHTML='<h3 style="color:#ffa726">\u2699\ufe0f '+esc(m.hostname||'')+' \u672a\u914d\u7f6e\uff0c\u81ea\u52a8\u5f00\u59cb...</h3>';
      setTimeout(function(){runWindsurfSetup(m.agentId)},1500);
    }else if(m.status==='configured'){
      var sa3=document.getElementById('sSetupArea');if(sa3)sa3.style.display='';
      var st3=document.getElementById('sText');if(st3)st3.innerHTML='<h3 style="color:#4caf50">\u2705 '+esc(m.hostname||'')+' \u5df2\u914d\u7f6e</h3><p style="color:#889;font-size:12px">\u65e0\u9700\u64cd\u4f5c\u3002\u5982\u9700\u91cd\u65b0\u914d\u7f6e\u8bf7\u70b9\u51fb\u8bbe\u5907\u5361\u7247\u4e0a\u7684\u6309\u94ae\u3002</p>';
    }
  }
}
function showAgentInfo(m){
  var el=document.getElementById('agentInfo');
  el.style.display='';
  el.innerHTML='<div class="card connected"><div class="info-bar">'
    +'<div class="info-chip"><b>'+esc(m.hostname||'?')+'</b></div>'
    +'<div class="info-chip">'+esc(m.user||'?')+(m.isAdmin?' <b style="color:#4caf50">(管理员)</b>':'')+'</div>'
    +'<div class="info-chip">'+esc(m.os||'?')+'</div>'
    +'</div></div>';
}
var tests=[
  {name:'DNS: windsurf.com',type:'dns',host:'windsurf.com'},
  {name:'DNS: auth.windsurf.com',type:'dns',host:'auth.windsurf.com'},
  {name:'DNS: unleash.codeium.com',type:'dns',host:'unleash.codeium.com'},
  {name:'DNS: marketplace.windsurf.com',type:'dns',host:'marketplace.windsurf.com'},
  {name:'HTTPS: windsurf.com',type:'fetch',url:'https://windsurf.com'},
  {name:'HTTPS: auth.windsurf.com',type:'fetch',url:'https://auth.windsurf.com'},
  {name:'HTTPS: unleash.codeium.com',type:'fetch',url:'https://unleash.codeium.com'},
  {name:'IP: windsurf.com (直连)',type:'fetch',url:'https://windsurf.com/favicon.ico'},
  {name:'IP: codeium.com (直连)',type:'fetch',url:'https://unleash.codeium.com/favicon.ico'},
  {name:'DNS: github.com (ref)',type:'dns',host:'github.com'},
  {name:'HTTPS: github.com (ref)',type:'fetch',url:'https://github.com'}
];
async function runDiag(){
  var box=document.getElementById('diagBox');
  box.innerHTML='<div class="card"><h3>网络诊断</h3><b style="color:#ffa726">正在检测...</b><div class="pw"><div id="dp" class="pf" style="width:0%"></div></div><div id="dt"></div></div>';
  var results=[],pass=0,fail=0;
  for(var i=0;i<tests.length;i++){
    document.getElementById('dp').style.width=((i+1)/tests.length*100)+'%';
    var t=tests[i],r={name:t.name,status:'fail',detail:''};
    var row=document.createElement('div');row.className='ti-r';
    row.innerHTML='<span class="n">'+t.name+'</span><span class="r wait">...</span><span class="dd"></span>';
    document.getElementById('dt').appendChild(row);
    try{
      if(t.type==='dns'){
        var resp=await fetch('https://dns.alidns.com/resolve?name='+t.host+'&type=A',{signal:AbortSignal.timeout(8000)});
        var d=await resp.json();
        if(d.Answer&&d.Answer.length>0){r.status='pass';r.detail=d.Answer.map(function(a){return a.data}).join(', ')}
        else{r.detail='NXDOMAIN'}
      }else if(t.type==='fetch'){
        var s=Date.now();
        try{await fetch(t.url,{mode:'no-cors',signal:AbortSignal.timeout(10000)});r.status='pass';r.detail=(Date.now()-s)+'ms'}
        catch(e){r.detail=e.name==='AbortError'?'timeout':e.message}
      }
    }catch(e){r.detail=e.message||'error'}
    results.push(r);
    if(r.status==='pass')pass++;else fail++;
    row.querySelector('.r').className='r '+r.status;
    row.querySelector('.r').textContent=r.status==='pass'?'OK':'FAIL';
    row.querySelector('.dd').textContent=r.detail;
    if(ws&&ws.readyState===1) ws.send(JSON.stringify({type:'test_result',index:i,name:r.name,status:r.status,detail:r.detail}));
  }
  if(ws&&ws.readyState===1) ws.send(JSON.stringify({type:'diagnostics_complete',results:results,ua:navigator.userAgent,time:new Date().toISOString()}));
  var summary='<div class="diag-summary"><div class="ds-item ok">'+pass+' 通过</div>'+(fail?'<div class="ds-item fail">'+fail+' 失败</div>':'')+'</div>';
  var btn='<button class="bigb" onclick="diagRan=true;runDiag()">重新诊断</button>';
  box.insertAdjacentHTML('beforeend',summary+btn);
}
function termSend(){
  var inp=document.getElementById('termIn'),cmd=inp.value.trim();
  if(!cmd||!ws||ws.readyState!==1)return;
  if(!agentOk){addTerm(cmd,'Agent未连接，请先在首页连接Agent',false);return}
  var id='p'+(++cmdId);
  ws.send(JSON.stringify({type:'user_exec',cmd:cmd,id:id}));
  inp.value='';
  var te=document.getElementById('termEmpty');if(te)te.remove();
  var d=document.createElement('div');d.className='te te-pending';d.id=id;
  d.innerHTML='<div class="te-cmd">'+esc(cmd)+'</div><div class="te-out">执行中...</div>';
  document.getElementById('termOut').appendChild(d);
  d.scrollIntoView({behavior:'smooth'});
  pendingCmds[id]=cmd;
}
function addTerm(cmd,output,ok,id){
  var te=document.getElementById('termEmpty');if(te)te.remove();
  var pid=id||Object.keys(pendingCmds).find(function(k){return pendingCmds[k]===cmd});
  if(pid&&pendingCmds[pid]){
    var el=document.getElementById(pid);
    if(el){el.className='te';el.id='';el.innerHTML='<div class="te-cmd">'+esc(cmd)+'</div><div class="te-out'+(ok?'':' te-err')+'">'+esc(output||'(no output)')+'</div><div class="te-t">'+new Date().toLocaleTimeString()+'</div>';el.scrollIntoView({behavior:'smooth'})}
    delete pendingCmds[pid];
  } else {
    var d=document.createElement('div');d.className='te';
    d.innerHTML='<div class="te-cmd">'+esc(cmd)+'</div><div class="te-out'+(ok?'':' te-err')+'">'+esc(output||'(no output)')+'</div><div class="te-t">'+new Date().toLocaleTimeString()+'</div>';
    document.getElementById('termOut').appendChild(d);
    d.scrollIntoView({behavior:'smooth'});
  }
}
function showSys(m){
  if(m.error){document.getElementById('sysBox').innerHTML='<div class="card"><p style="color:#f44336">'+esc(m.error)+'</p></div>';return}
  var h='<div class="sg">';
  h+='<div class="si"><div class="l">CPU</div><div class="v sm">'+esc(m.cpu||'?')+'</div></div>';
  h+='<div class="si"><div class="l">操作系统</div><div class="v sm">'+esc(m.os||'?')+'</div></div>';
  h+='<div class="si"><div class="l">内存</div><div class="v">'+esc(m.ramGB||'?')+' GB <span style="color:#556">/ 空闲 '+esc(m.ramFreeGB||'?')+' GB</span></div></div>';
  h+='<div class="si"><div class="l">进程数</div><div class="v">'+esc(m.processes||'?')+'</div></div>';
  h+='<div class="si"><div class="l">运行时间</div><div class="v">'+esc(m.uptime||'?')+' h</div></div>';
  var dl=m.disks;if(dl){if(!Array.isArray(dl))dl=[dl];dl.forEach(function(dk){h+='<div class="si"><div class="l">磁盘 '+esc(dk.drive||'?')+'</div><div class="v">'+esc(dk.freeGB||'?')+' / '+esc(dk.sizeGB||'?')+' GB</div></div>'})}
  var al=m.adapters;if(al){if(!Array.isArray(al))al=[al];al.forEach(function(a){h+='<div class="si"><div class="l">'+esc(a.name||'?')+'</div><div class="v sm">'+esc(a.desc||'?')+' ('+esc(a.speed||'?')+')</div></div>'})}
  h+='</div>';
  h+='<button class="bigb" style="margin-top:14px" onclick="refreshSys()">刷新系统信息</button>';
  document.getElementById('sysBox').innerHTML=h;
}
function refreshSys(){if(ws&&ws.readyState===1)ws.send(JSON.stringify({type:'request_sysinfo'}))}
function go(id,btn){
  document.querySelectorAll('.tab').forEach(function(t){t.className='tab'});
  document.querySelectorAll('.page').forEach(function(p){p.className='page'});
  btn.className='tab act';
  document.getElementById('p-'+id).className='page act';
}
function sPill(s,t){var e=document.getElementById('sPill');e.className='pill '+s;e.innerHTML='<span class="d"></span>'+t}
function aPill(s,t){var e=document.getElementById('aPill');e.className='pill '+s;e.innerHTML='<span class="d"></span>'+t}
function addMsg(level,html){
  var el=document.createElement('div');el.className='msg '+level;el.innerHTML=html;
  document.getElementById('msgs').appendChild(el);
  el.scrollIntoView({behavior:'smooth',block:'end'});
  var sm=document.getElementById('sMsgs');if(sm){var el2=document.createElement('div');el2.className='msg '+level;el2.innerHTML=html;sm.appendChild(el2)}
}
function showCmd(title,cmd,steps){
  var h='<h3>'+esc(title)+'</h3>';
  if(steps) h+='<div class="steps">'+steps+'</div>';
  h+='<div class="cmd-box">'+esc(cmd)+'</div>';
  h+='<button class="cbtn" onclick="cpNear(this)">复制命令</button>';
  addMsg('action',h);
}
function cpNear(btn){
  var box=btn.parentElement.querySelector('.cmd-box');
  if(!box)return;
  var t=box.textContent.trim();
  if(navigator.clipboard&&navigator.clipboard.writeText){
    navigator.clipboard.writeText(t).then(function(){cpDone(btn)}).catch(function(){cpFB(t,btn)});
  }else{cpFB(t,btn)}
}
function cpEl(id,btn){
  var t=document.getElementById(id).textContent.trim();
  if(navigator.clipboard&&navigator.clipboard.writeText){
    navigator.clipboard.writeText(t).then(function(){cpDone(btn,'复制安装命令')}).catch(function(){cpFB(t,btn)});
  }else{cpFB(t,btn)}
}
function cpDone(btn,orig){btn.textContent='已复制!';btn.className='cbtn ok';setTimeout(function(){btn.textContent=orig||'复制命令';btn.className='cbtn'},2000)}
function cpFB(t,btn){var ta=document.createElement('textarea');ta.value=t;ta.style.cssText='position:fixed;left:-9999px';document.body.appendChild(ta);ta.select();try{document.execCommand('copy');cpDone(btn)}catch(e){}document.body.removeChild(ta)}
function sendUserMsg(){
  var ta=document.getElementById('userMsg'),t=ta.value.trim();
  if(!t||!ws||ws.readyState!==1)return;
  ws.send(JSON.stringify({type:'user_message',text:t,time:new Date().toISOString()}));
  addMsg('system','<b>你:</b> '+esc(t));
  ta.value='';
  ta.style.height='auto';
}
function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}
function updateAgentSel(agents,selected){
  var sel=document.getElementById('agentSel');
  if(!agents||agents.length===0){sel.style.display='none';return}
  sel.style.display='';
  sel.innerHTML=agents.map(function(a){return '<option value="'+esc(a.id)+'"'+(a.id===selected?' selected':'')+'>'+esc(a.hostname||a.id)+(a.connected?' \u2705':' \u274c')+'</option>'}).join('');
  if(agents.length<=1)sel.style.display='none';
}
function switchAgent(id){
  if(ws&&ws.readyState===1)ws.send(JSON.stringify({type:'select_agent',id:id}));
}
function runWindsurfSetup(targetAgentId){
  if(!agentOk&&!targetAgentId){var wl0=document.getElementById('wsSetupLog');if(wl0)wl0.style.display='';var wr0=document.getElementById('wsSetupResults');if(wr0)wr0.innerHTML='<div class="msg alert-err">Agent\u672a\u8fde\u63a5</div>';return}
  var targetName='';
  if(targetAgentId){for(var i=0;i<allAgents.length;i++){if(allAgents[i].id===targetAgentId){targetName=allAgents[i].hostname||targetAgentId;break}}}
  var btn=document.getElementById('wsSetupBtn');
  if(btn){btn.disabled=true;btn.textContent='\u914d\u7f6e\u4e2d'+(targetName?' ('+targetName+')':'')+'...';btn.style.opacity='0.6'}
  var wl=document.getElementById('wsSetupLog');if(wl)wl.style.display='';
  var wr=document.getElementById('wsSetupResults');if(wr)wr.innerHTML='<div class="empty">\u6b63\u5728\u4e3a '+(targetName||'Agent')+' \u6267\u884c\u81ea\u52a8\u914d\u7f6e...</div>';
  var wp=document.getElementById('wsSetupProgress');if(wp)wp.style.width='5%';
  var sa=document.getElementById('sSetupArea');if(sa)sa.style.display='';
  var st=document.getElementById('sText');if(st)st.innerHTML='<h3 style="color:#ffa726">\u2699\ufe0f '+(targetName||'')+' \u81ea\u52a8\u914d\u7f6e\u4e2d...</h3>';
  var sb=document.getElementById('sBar');if(sb)sb.style.width='5%';
  var payload=targetAgentId?{agentId:targetAgentId}:{};
  fetch(basePath+'/brain/windsurf-setup',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+getToken()},body:JSON.stringify(payload)})
  .then(function(r){return r.json()})
  .then(function(d){
    var h='';
    if(d.results){
      d.results.forEach(function(r,i){
        var icon=r.ok?'\u2705':'\u274c';
        var cls=r.ok?'pass':'fail';
        h+='<div class="ti-r"><span class="n">'+icon+' '+(i+1)+'. '+esc(r.name)+'</span><span class="r '+cls+'">'+(r.ok?'OK':'FAIL')+'</span><span class="dd">'+esc((r.output||'').substring(0,80))+'</span></div>';
      });
    }
    if(wr)wr.innerHTML=h;if(wp)wp.style.width='100%';
    if(btn){if(d.ok){btn.textContent='\u2705 '+(targetName||'')+' \u914d\u7f6e\u5b8c\u6210'+(d.mode==='lan'?' (LAN\u76f4\u8fde)':' (FRP\u516c\u7f51)');btn.style.background='linear-gradient(135deg,#4caf50,#2e7d32)'}else{btn.textContent='\u26a0\ufe0f \u90e8\u5206\u5931\u8d25';btn.style.background='linear-gradient(135deg,#ffa726,#e65100)';btn.disabled=false;btn.style.opacity='1'}}
    var sl=document.getElementById('sLog');if(sl)sl.innerHTML=h;
    if(sb)sb.style.width='100%';
    if(st){if(d.ok)st.innerHTML='<h3 style="color:#4caf50">\u2705 '+(targetName||'')+' \u914d\u7f6e\u5b8c\u6210!</h3><p style="color:#a0d0a0;font-size:14px;margin-top:8px">Windsurf\u5df2\u901a\u8fc7\u4ee3\u7406\u6a21\u5f0f\u81ea\u52a8\u91cd\u542f<br><span style="font-size:11px;color:#889">'+(d.mode==='lan'?'\ud83c\udfe0 LAN\u76f4\u8fde\u6a21\u5f0f':'\ud83c\udf10 FRP\u516c\u7f51\u6a21\u5f0f')+'</span></p>';else st.innerHTML='<h3 style="color:#ffa726">\u26a0\ufe0f '+d.passed+'/'+d.total+' \u901a\u8fc7</h3><p style="color:#889;font-size:11px">\u5207\u6362\u7ba1\u7406\u5458\u6a21\u5f0f\u67e5\u770b\u8be6\u60c5</p>'}
  })
  .catch(function(e){
    if(wr)wr.innerHTML='<div class="msg alert-err">'+esc(e.message)+'</div>';
    if(btn){btn.textContent='\u274c \u5931\u8d25';btn.disabled=false;btn.style.opacity='1';btn.style.background='linear-gradient(135deg,#f44336,#b71c1c)'}
    if(st)st.innerHTML='<h3 style="color:#f44336">\u274c \u914d\u7f6e\u5931\u8d25</h3><p style="color:#d0a0a0;font-size:11px">'+esc(e.message)+'</p>';
  });
}
function toggleAdmin(){var s=document.getElementById('simpleMode'),a=document.getElementById('adminApp');if(a.style.display==='none'){a.style.display='';s.style.display='none'}else{a.style.display='none';s.style.display=''}}
connect();
</script>
</body>
</html>`;
};
