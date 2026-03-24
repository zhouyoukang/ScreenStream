/**
 * Windsurf小助手 · 号池仪表盘 v7.0
 * 道法自然 · 三模式渲染 + 交互
 */
(function(){
var V;try{V=acquireVsCodeApi();}catch(e){V={postMessage:function(){}};};
var D=window.__INIT||{};
var _rmTimer={};
var _lastDataHash='';
var _renderRAF=null;
var _localExpanded=null; // local override for detailExpanded to avoid race-condition flips
var _lastPoolSource=null;
var _lastAcctCount=-1;
var _fullRenderNeeded=true;

function S(t,d){if(V&&V.postMessage)V.postMessage(Object.assign({type:t},d||{}));}
function _esc(s){return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}

// ── Toast ──
function toast(msg,isErr){
  var el=document.getElementById('toast');
  if(!el)return;
  el.textContent=msg;el.className=isErr?'err':'ok';
  clearTimeout(toast._t);toast._t=setTimeout(function(){el.className='';},3000);
}

// ── Stat helper ──
function stat(val,label,cls){
  return '<div class="stat"><div class="stat-value '+(cls||'')+'">'+val+'</div><div class="stat-label">'+label+'</div></div>';
}
function quotaBar(label,val,max,cls){
  var pct=max?Math.round(val/max*100):0;
  var fc=pct<20?'quota-fill-low':cls;
  return '<div class="quota-bar-wrap"><div class="quota-bar-label"><span>'+label+'</span><span>'+pct+'%</span></div>'+
    '<div class="quota-bar"><div class="quota-fill '+fc+'" style="width:'+pct+'%"></div></div></div>';
}

// ══════════════════════════════
//  RENDER — 主渲染入口
// ══════════════════════════════
function render(){
  var app=document.getElementById('app');
  if(!app)return;
  if(_localExpanded!==null) D.detailExpanded=_localExpanded;

  // Full rebuild only when structure changes (mode switch, first render)
  var accts=D.accounts||[];
  var needFull=_fullRenderNeeded||_lastPoolSource!==D.poolSource||_lastAcctCount!==accts.length;
  _lastPoolSource=D.poolSource;
  _lastAcctCount=accts.length;
  _fullRenderNeeded=false;

  if(needFull){
    var scrollTop=app.scrollTop;
    var h='';
    h+=renderHeader();
    h+=renderPoolSummary();
    h+=renderModeTabs();
    h+=renderModeIndicator();
    switch(D.poolSource){
      case 'cloud': h+=renderCloud(); break;
      case 'hybrid': h+=renderHybrid(); break;
      default: h+=renderLocal(); break;
    }
    app.innerHTML=h;
    app.scrollTop=scrollTop;
  } else {
    // Incremental: patch only changed parts
    patchPoolSummary();
    patchAccountRows();
  }
}
function scheduleRender(){
  if(_renderRAF) cancelAnimationFrame(_renderRAF);
  _renderRAF=requestAnimationFrame(function(){_renderRAF=null;render();});
}

// ── Incremental patchers ──
function patchPoolSummary(){
  var el=document.querySelector('.pool-summary');
  if(!el)return;
  var tmp=document.createElement('div');
  tmp.innerHTML=renderPoolSummary();
  var neo=tmp.firstChild;
  if(neo&&el.innerHTML!==neo.innerHTML) el.innerHTML=neo.innerHTML;
}
function patchAccountRows(){
  var accts=D.accounts||[];
  for(var i=0;i<accts.length;i++){
    var row=document.getElementById('row'+i);
    if(!row)continue;
    var a=accts[i];
    // Patch quota label
    var qEl=row.querySelector('.acct-d');
    if(qEl&&qEl.textContent!==a.label) qEl.textContent=a.label;
    // Patch current state
    var wantCur=a.isCurrent;
    var hasCur=row.classList.contains('cur');
    if(wantCur!==hasCur){ row.classList.toggle('cur',wantCur); }
    // Patch switch button
    var swBtn=row.querySelector('.acct-btn-switch');
    if(swBtn){
      swBtn.classList.toggle('cur',wantCur);
      var swTxt=wantCur?'\u2713':'\u26A1';
      if(swBtn.textContent!==swTxt) swBtn.textContent=swTxt;
    }
    // Patch rate-limit / expired
    row.classList.toggle('rl',!!a.rl);
    row.classList.toggle('exp',!!a.isExpired);
  }
}

function renderHeader(){
  return '<div class="header"><div class="header-title">Windsurf小助手<span>号池引擎</span></div>'+
    '<button class="btn btn-ghost btn-sm" data-action="refreshAllAndRotate">&#x1F504; 刷新</button></div>';
}

function renderPoolSummary(){
  var b=D.bar||{};var p=D.pool||{};var a=D.active||{};
  var h='<div class="pool-summary"><div class="pool-value">';
  if(D.poolSource==='cloud'){
    var cw=D.cloud&&D.cloud.poolW;
    h+='<span class="w-val">W'+(cw!=null?cw+'%':'--')+'</span>';
    h+='<span class="num-tag">云端W资源</span>';
  } else if(D.poolSource==='hybrid'){
    h+='<span class="d-val">D'+(p.sumDaily!=null?p.sumDaily+'%':'--')+'</span>';
    h+='<span class="sep">·</span>';
    var hw=D.cloud&&D.cloud.availW;
    h+='<span class="w-val">W'+(hw!=null?hw+'%':'--')+'</span>';
    h+='<span class="num-tag">混合总值</span>';
  } else {
    h+='<span class="d-val">'+(b.line||'--')+'</span>';
    h+='<span class="num-tag">号池总值'+(b.bottleneck?' <span style="color:var(--w2);font-size:9px">W瓶颈</span>':'')+'</span>';
  }
  h+='</div>';
  // Meta stats
  h+='<div class="pool-meta">';
  h+='<span><b>'+p.available+'</b>可用</span>';
  h+='<span><b>'+p.total+'</b>总计</span>';
  if(p.depleted>0) h+='<span style="color:var(--d2)"><b>'+p.depleted+'</b>耗尽</span>';
  if(p.rateLimited>0) h+='<span style="color:var(--w2)"><b>'+p.rateLimited+'</b>限流</span>';
  if(p.urgentCount>0) h+='<span style="color:var(--d2)"><b>'+p.urgentCount+'</b>紧急</span>';
  if(D.switchCount>0) h+='<span>切换<b>'+D.switchCount+'</b>次</span>';
  if(D.poolSource!=='local'){
    var on=D.cloud&&D.cloud.online;
    h+='<span style="color:'+(on?'var(--ok2)':'var(--d2)')+'">&#x2601; '+(on?'在线':'离线')+'</span>';
  }
  h+='</div>';
  // Bar
  var bpct=b.pct||0;var bc=b.color||'var(--ok)';
  h+='<div class="pool-bar"><div class="pool-bar-d" style="width:'+bpct+'%;background:'+bc+'"></div></div>';
  // Active account
  if(a.index>=0){
    h+='<div class="pool-active">活跃: #'+(a.index+1)+' '+_esc(a.label);
    if(a.planTag) h+=' <span style="color:var(--p2);font-size:9px;border:1px solid var(--p2);border-radius:3px;padding:0 3px">'+_esc(a.planTag)+'</span>';
    if(a.quotaTag) h+=' <span style="color:var(--blue2)">'+_esc(a.quotaTag)+'</span>';
    if(a.expiryHtml) h+=' '+a.expiryHtml;
    h+='</div>';
    if(a.resetInfo) h+='<div class="pool-active" style="font-size:9px">'+_esc(a.resetInfo)+'</div>';
  }
  h+='</div>';
  return h;
}

function renderModeTabs(){
  var m=D.poolSource||'local';
  return '<div class="mode-tabs">'+
    '<button class="mode-tab'+(m==='local'?' active':'')+'" data-action="setPoolSource" data-mode="local"><span class="mode-icon">&#x1F4BB;</span> 本地</button>'+
    '<button class="mode-tab'+(m==='cloud'?' active':'')+'" data-action="setPoolSource" data-mode="cloud"><span class="mode-icon">&#x2601;</span> 云端</button>'+
    '<button class="mode-tab'+(m==='hybrid'?' active':'')+'" data-action="setPoolSource" data-mode="hybrid"><span class="mode-icon">&#x267E;</span> 混合</button>'+
    '</div>';
}

function renderModeIndicator(){
  var m=D.poolSource||'local';
  var colors={local:'var(--ok)',cloud:'var(--p)',hybrid:'var(--blue)'};
  var labels={local:'本地模式 · 仅消耗本地D额度',cloud:'云端模式 · 和而不同W资源',hybrid:'混合模式 · 本地优先 · 云端兜底'};
  return '<div class="mode-indicator"><span class="mode-dot" style="background:'+colors[m]+'"></span>'+
    '<span style="color:'+colors[m]+'">'+labels[m]+'</span></div>';
}

// ══════════════════════════════
//  LOCAL MODE
// ══════════════════════════════
function renderLocal(){
  var h='';
  // Actions
  h+='<div class="actions">';
  h+='<button class="btn btn-gold btn-sm" data-action="refreshAllAndRotate">&#x1F504; 刷新全部</button>';
  if(D.pool&&D.pool.rateLimited>0) h+='<button class="btn btn-ghost btn-sm" data-action="clearAllRateLimits">&#x1F513; 清限流('+D.pool.rateLimited+')</button>';
  h+='<div style="margin-left:auto;display:flex;gap:4px">';
  h+='<button class="btn btn-ghost btn-sm" data-action="exportAccounts">&#x1F4E4;</button>';
  h+='<button class="btn btn-ghost btn-sm" data-action="importAccounts">&#x1F4E5;</button>';
  h+='</div></div>';
  // Add accounts
  h+=renderAddBar();
  // Accounts section
  h+=renderAccountSection();
  return h;
}

// ══════════════════════════════
//  CLOUD MODE
// ══════════════════════════════
function renderCloud(){
  var c=D.cloud||{};var h='';
  var online=c.online||c.ok||false;
  var activated=c.device_activated||false;
  var mc=c.machine_code||c.machineCode||c.deviceId||'';

  // ── 本机码显示 ──
  if(mc){
    h+='<div class="machine-box">';
    h+='<div class="machine-label">本机识别码</div>';
    h+='<div class="machine-code" data-action="cloudCopyCode" data-code="'+_esc(mc)+'">'+_esc(mc.slice(0,16))+'</div>';
    h+='<div style="font-size:9px;color:var(--m);margin-top:2px">点击复制 · 用于激活和远程管理</div>';
    h+='</div>';
  }

  // ── W资源卡片 ──
  h+='<div class="card card-glow-cloud">';
  h+='<div class="card-title"><span class="icon">&#x26A1;</span> W资源 · 和而不同</div>';

  if(!online){
    h+='<div class="empty">&#x2601; 云端未连接<br><span style="font-size:9px;color:var(--m)">请检查管理端是否运行</span></div>';
  } else if(!activated){
    // 新用户激活
    h+='<div class="activate-box">';
    h+='<h3>&#x1F381; 新用户激活</h3>';
    h+='<p>激活后即可使用云端W资源</p>';
    h+='<div class="activate-bonus">100% <small>W免费额度</small></div>';
    h+='<button class="btn btn-gold btn-block" style="margin-top:8px" data-action="cloudActivate" data-code="'+_esc(mc)+'">&#x26A1; 立即激活</button>';
    h+='</div>';
  } else {
    h+='<div class="grid">';
    h+=stat('W'+(c.poolW||c.w_percent||0)+'%','池总W','c-p');
    h+=stat((c.availW||c.w_available||0)+'%','可用W','c-ok');
    h+=stat(c.devices||c.total_devices||0,'激活设备','c-cyan');
    h+='</div>';
    var myW=c.my_w!=null?c.my_w:100;
    var myWAvail=c.my_w_available!=null?c.my_w_available:(c.my_w!=null?c.my_w:100);
    var myWUsed=myW-myWAvail;
    h+=quotaBar('W额度',myWAvail,myW,'quota-fill-w');
    h+='<div class="w-info-row"><span class="w-info-key">本机W总量</span><span class="w-info-val">'+myW+'%</span></div>';
    h+='<div class="w-info-row"><span class="w-info-key">本机可用</span><span class="w-info-val" style="color:var(--ok2)">'+myWAvail+'%</span></div>';
  }

  h+='<div style="display:flex;justify-content:flex-end;margin-top:8px">';
  h+='<button class="btn btn-primary btn-sm" data-action="refreshAllAndRotate">刷新云端</button>';
  h+='</div>';
  h+='</div>';

  // ── 公网远程管理（已迁移至管理端）──
  h+='<div class="remote-panel">';
  h+='<h3><span>&#x1F310;</span> 公网远程直连</h3>';
  h+='<div style="font-size:11px;color:var(--m);margin-bottom:8px">通过机器码远程直连，排查Windsurf配置问题</div>';
  h+='<div style="background:var(--bg);border-radius:8px;padding:10px;font-size:11px">';
  h+='<span style="color:var(--cyan2)">&#x2139;&#xFE0F;</span> ';
  h+='<span style="color:var(--t)">公网远程直连功能已迁移至</span> ';
  h+='<b style="color:var(--p2)">号池管理端</b>';
  h+='<span style="color:var(--m)"> → 云池 → 远程管理</span>';
  h+='</div>';
  if(mc){
    h+='<div style="margin-top:8px;font-size:10px;color:var(--m)">本机码: ';
    h+='<span style="color:var(--cyan2);font-family:monospace;cursor:pointer" data-action="cloudCopyCode" data-code="'+_esc(mc)+'">'+_esc(mc.slice(0,16))+'</span>';
    h+=' <span style="color:var(--m)">(点击复制，提供给管理端)</span>';
    h+='</div>';
  }
  h+='</div>';

  return h;
}

// ══════════════════════════════
//  HYBRID MODE
// ══════════════════════════════
function renderHybrid(){
  var c=D.cloud||{};var p=D.pool||{};var h='';
  var localD=p.avgDaily!=null?p.avgDaily:(p.health||0);
  var cloudW=c.availW!=null?c.availW:(c.poolW||0);
  // Dual quota (simplified)
  h+='<div class="card card-glow-hybrid">';
  h+='<div class="card-title"><span class="icon">&#x267E;</span> 双额度</div>';
  h+='<div class="dual-quota">';
  h+='<div class="dual-quota-half" style="border:1px solid rgba(16,185,129,.2)">';
  h+='<div class="dual-quota-val" style="color:var(--ok2)">D'+localD+'%</div>';
  h+='<div class="dual-quota-label">本地</div>';
  h+='</div>';
  h+='<div class="consumption-arrow">&#x2192;</div>';
  h+='<div class="dual-quota-half" style="border:1px solid rgba(124,58,237,.2)">';
  h+='<div class="dual-quota-val" style="color:var(--p2)">W'+(cloudW||'--')+'%</div>';
  h+='<div class="dual-quota-label">云端</div>';
  h+='</div></div>';
  h+='<div style="height:6px;border-radius:3px;background:var(--bg);overflow:hidden;display:flex;margin-bottom:6px">';
  h+='<div style="width:'+localD*0.6+'%;background:linear-gradient(90deg,var(--ok),var(--ok2));border-radius:3px 0 0 3px"></div>';
  h+='<div style="width:2px;background:var(--b)"></div>';
  h+='<div style="width:'+(cloudW||0)*0.4+'%;background:linear-gradient(90deg,var(--p),var(--p2));border-radius:0 3px 3px 0"></div>';
  h+='</div></div>';
  // Actions + accounts
  h+='<div class="actions">';
  h+='<button class="btn btn-gold btn-sm" data-action="refreshAllAndRotate">&#x1F504; 刷新</button>';
  if(p.rateLimited>0) h+='<button class="btn btn-ghost btn-sm" data-action="clearAllRateLimits">&#x1F513; 清限流('+p.rateLimited+')</button>';
  h+='</div>';
  h+=renderAccountSection();
  return h;
}

// ══════════════════════════════
//  SHARED — Account section
// ══════════════════════════════
function renderAddBar(){
  return '<div class="addbar"><textarea id="bi" rows="1" placeholder="粘贴账号 (自动识别格式)"></textarea>'+
    '<button class="btn btn-primary btn-sm" data-action="doBatch">+</button></div>'+
    '<div id="preview"></div>';
}

function renderAccountSection(){
  var accts=D.accounts||[];var total=accts.length;
  var expanded=D.detailExpanded;
  var h='<div class="sect">';
  h+='<div class="stog" data-action="toggleDetail">';
  h+='<span class="sarr" id="detArr" style="'+(expanded?'transform:rotate(90deg)':'')+'">&#x25B6;</span>';
  h+='<span>'+total+'个账号</span>';
  if(D.active&&D.active.index>=0){
    h+='<span style="margin-left:auto;font-size:9px;color:var(--m)">活跃: '+_esc(D.active.label)+'</span>';
  }
  h+='</div>';
  h+='<div class="sbox'+(expanded?' open':'')+'" id="detBox">';
  if(total>0){
    accts.forEach(function(a,i){
      var cur=a.isCurrent;
      var cls='acct-row'+(cur?' cur':'')+(a.rl?' rl':'')+(a.isExpired?' exp':'');
      h+='<div class="'+cls+'" id="row'+i+'">';
      h+='<span class="acct-idx">'+(i+1)+'</span>';
      var tn=_esc(a.name);if(tn.length>14)tn=tn.slice(0,12)+'..';
      h+='<span class="acct-name" title="'+_esc(a.email)+'">'+tn;
      if(a.isExpired) h+='<span class="acct-day" style="color:var(--d)">过期</span>';
      else if(a.planDays!=null) {
        var dc=a.urgency===0?'var(--d)':a.urgency===1?'var(--w)':a.urgency===2?'var(--ok)':'var(--m)';
        h+='<span class="acct-day" style="color:'+dc+'">'+a.planDays+'d</span>';
      }
      h+='</span>';
      h+='<span class="acct-quota"><span class="acct-d">'+_esc(a.label)+'</span></span>';
      h+='<div class="acct-actions">';
      h+='<button class="acct-btn acct-btn-switch'+(cur?' cur':'')+'" data-action="login" data-index="'+i+'">'+(cur?'&#x2713;':'&#x26A1;')+'</button>';
      h+='<button class="acct-btn acct-btn-copy" id="cp'+i+'" data-action="copyPwd" data-index="'+i+'">&#x1F4CB;</button>';
      h+='<button class="acct-btn acct-btn-del" id="bx'+i+'" data-action="remove" data-index="'+i+'">&#x2715;</button>';
      h+='</div></div>';
    });
  } else {
    h+='<div class="empty">号池为空<br><span style="color:var(--p2)">粘贴账号到上方输入框</span></div>';
  }
  h+='</div></div>';
  return h;
}

// ══════════════════════════════
//  EVENTS — 事件委托
// ══════════════════════════════
document.addEventListener('click',function(e){
  var el=e.target;
  while(el&&el!==document.body){if(el.getAttribute&&el.getAttribute('data-action'))break;el=el.parentElement;}
  if(!el||!el.getAttribute)return;
  var act=el.getAttribute('data-action'),idx=el.getAttribute('data-index');
  if(idx!==null&&idx!==undefined)idx=parseInt(idx);
  switch(act){
    case 'login': S('login',{index:idx}); break;
    case 'copyPwd':
      var cpb=document.getElementById('cp'+idx);
      if(cpb){cpb.textContent='\u2026';cpb.style.opacity='1';}
      S('copyPwd',{index:idx}); break;
    case 'remove':
      var btn=document.getElementById('bx'+idx);
      if(!btn)break;
      if(btn.dataset.confirm==='1'){
        clearTimeout(_rmTimer[idx]);delete _rmTimer[idx];
        var row=document.getElementById('row'+idx);
        if(row){row.style.opacity='0';row.style.transition='opacity .15s';}
        setTimeout(function(){S('remove',{index:idx});},150);
      } else {
        btn.dataset.confirm='1';btn.textContent='确?';btn.style.color='var(--w2)';btn.style.opacity='1';
        _rmTimer[idx]=setTimeout(function(){if(btn){btn.textContent='✕';btn.style.color='';btn.dataset.confirm='0';}},2000);
      }
      break;
    case 'refreshAllAndRotate': S('refreshAllAndRotate'); break;
    case 'smartRotate': S('smartRotate'); break;
    case 'panicSwitch': S('panicSwitch'); break;
    case 'setPoolSource': S('setPoolSource',{mode:el.getAttribute('data-mode')}); break;
    case 'exportAccounts': S('exportAccounts'); break;
    case 'importAccounts': S('importAccounts'); break;
    case 'removeEmpty': S('removeEmpty'); break;
    case 'resetFingerprint': S('resetFingerprint'); break;
    case 'clearAllRateLimits': S('clearAllRateLimits'); break;
    case 'cloudCopyCode': {
      var code=el.getAttribute('data-code')||'';
      if(code&&navigator.clipboard){
        navigator.clipboard.writeText(code).then(function(){toast('✓ 机器码已复制');}).catch(function(){toast('复制失败',true);});
      } else if(code){
        var ta=document.createElement('textarea');ta.value=code;ta.style.position='fixed';ta.style.opacity='0';
        document.body.appendChild(ta);ta.select();try{document.execCommand('copy');toast('✓ 已复制');}catch(x){toast('请手动复制',true);}document.body.removeChild(ta);
      }
      break;
    }
    case 'cloudActivate': S('cloudActivate',{machineCode:el.getAttribute('data-code')||''}); break;
    case 'doBatch':
      var t=(document.getElementById('bi')||{}).value;
      if(t&&t.trim()){S('batchAdd',{text:t.trim()});document.getElementById('bi').value='';var pv=document.getElementById('preview');if(pv)pv.innerHTML='';} break;
    case 'toggleDetail':
      var box=document.getElementById('detBox'),arr=document.getElementById('detArr');
      var op = box ? box.classList.toggle('open') : false;
      if(arr)arr.style.transform=op?'rotate(90deg)':'';
      _localExpanded=op;
      S('toggleDetail'); break;
  }
});

document.addEventListener('input',function(e){
  if(e.target.id==='bi'){
    var t=e.target.value.trim(),p=document.getElementById('preview');
    if(!t){if(p)p.innerHTML='';return;}
    S('preview',{text:t});
  }
});

// ── Messages from extension ──
window.addEventListener('message',function(e){
  var m=e.data;
  if(m.type==='toast') toast(m.msg,m.isError);
  if(m.type==='loading'){var app=document.getElementById('app');if(app)app.classList.toggle('dimmed',m.on);}
  if(m.type==='dataUpdate' && m.data){
    D=m.data;
    scheduleRender();
    return;
  }
  if(m.type==='previewResult'){
    var p=document.getElementById('preview');
    if(!p)return;
    if(m.accounts&&m.accounts.length>0){
      p.innerHTML='<span class="pf">'+m.accounts.length+'个</span> '+m.accounts.map(function(a){return '<span class="pe">'+_esc(a.email.split("@")[0])+'</span>:<span class="pp">'+_esc(a.password.substring(0,4))+'..</span>'}).join(' ');
    } else {
      p.innerHTML='<span style="color:var(--d);font-size:9px">未识别</span>';
    }
  }
  if(m.type==='pwdResult'){
    var btn=document.getElementById('cp'+m.index);
    if(btn&&m.pwd){
      navigator.clipboard.writeText(m.pwd).then(function(){
        btn.textContent='\u2713';btn.style.color='var(--ok2)';
        setTimeout(function(){btn.textContent='\uD83D\uDCCB';btn.style.color='';btn.style.opacity='';},1500);
      }).catch(function(){btn.textContent='!';setTimeout(function(){btn.textContent='\uD83D\uDCCB';},1000);});
    }
  }
});

// ── Init ──
render();
})();
