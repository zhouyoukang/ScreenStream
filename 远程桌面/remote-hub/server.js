const http = require('http');
const { WebSocketServer } = require('ws');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
try { fs.readFileSync(path.join(__dirname, '.env'), 'utf8').split('\n').forEach(function(line) { var m = line.match(/^\s*([\w]+)\s*=\s*(.*)\s*$/); if (m && !process.env[m[1]]) process.env[m[1]] = m[2]; }); } catch(e) {}

const PORT = process.env.PORT || 3002;
const PROXY_LAN_IP = process.env.PROXY_LAN_IP || '192.168.31.141';
const PUBLIC_URL = process.env.PUBLIC_URL || 'localhost:' + PORT;
const SECURE = process.env.SECURE === '1' || PUBLIC_URL.indexOf('aiotvr.xyz') >= 0;
const WS_PROTO = SECURE ? 'wss://' : 'ws://';
const HTTP_PROTO = SECURE ? 'https://' : 'http://';
const AUTH_PASSWORD = process.env.AUTH_PASSWORD || (() => { console.error('FATAL: AUTH_PASSWORD not set in .env or environment'); process.exit(1); })();
const AUTH_AGENT_KEY = crypto.createHash('sha256').update(AUTH_PASSWORD + ':agent').digest('hex').substring(0, 16);
const validTokens = new Set();

function generateToken() { var t = crypto.randomUUID(); validTokens.add(t); if (validTokens.size > 1000) { var first = validTokens.values().next().value; validTokens.delete(first); } return t; }
function checkAuth(req) {
  var cookies = (req.headers.cookie || '').split(';').map(function(c){return c.trim()});
  var tc = cookies.find(function(c){return c.startsWith('dao_token=')});
  if (tc && validTokens.has(tc.split('=')[1])) return true;
  var auth = req.headers.authorization;
  if (auth && auth.startsWith('Bearer ') && validTokens.has(auth.slice(7))) return true;
  var url = new URL(req.url, 'http://localhost');
  if (url.searchParams.get('token') && validTokens.has(url.searchParams.get('token'))) return true;
  return false;
}

// ==================== STATE ====================
const agents = new Map();
let selectedAgentId = null;
let senseSocket = null;
let senseData = { connected: false, ua: null, diagnostics: null, lastUpdate: null };
let commandHistory = [];
const pendingCommands = new Map();
let messageQueue = [];

function getAgent(id) { return id ? agents.get(id) : null; }
function getSelectedAgent() {
  if (selectedAgentId && agents.has(selectedAgentId)) { var a = agents.get(selectedAgentId); if (a.ws && a.ws.readyState === 1) return a; }
  for (var entry of agents) { if (entry[1].ws && entry[1].ws.readyState === 1) { selectedAgentId = entry[0]; return entry[1]; } }
  return null;
}
function getAgentList() {
  var list = [];
  agents.forEach(function(a, id) { list.push({ id: id, hostname: a.data.hostname, user: a.data.user, os: a.data.os, isAdmin: a.data.isAdmin, connected: a.ws && a.ws.readyState === 1, selected: id === selectedAgentId, lastUpdate: a.data.lastUpdate, wsConfig: a.data.wsConfig || null }); });
  return list;
}

// ==================== 无感层: HOSTS GUARD ====================
function startHostsGuard(agentId) {
  var agent = agents.get(agentId); if (!agent || agent.hostsGuardTimer) return;
  // Skip hosts guard for agents that have windsurf-setup portproxy (they NEED hosts entries)
  var guardCmd = '$pp=netsh interface portproxy show v4tov4 2>$null; $hp=Get-Content "$env:SystemRoot\\System32\\drivers\\etc\\hosts" -EA SilentlyContinue; $ws=$hp|Where-Object{$_ -match "windsurf|codeium"}; if($pp -match "18443" -or $ws -match "192.168"){"SKIP:windsurf-configured"}elseif($hp|Where-Object{$_ -match "windsurf|codeium|exafunction"}){"DIRTY:"+($ws-join",")}else{"CLEAN"}';
  var cleanCmd = '$hp="$env:SystemRoot\\System32\\drivers\\etc\\hosts"; $h=Get-Content $hp -Encoding UTF8; $h=$h | Where-Object { $_ -notmatch "windsurf|codeium|exafunction" }; $h | Set-Content $hp -Encoding ASCII; ipconfig /flushdns | Out-Null; "FIXED"';
  agent.hostsGuardTimer = setInterval(function() {
    var a = agents.get(agentId); if (!a || !a.ws || a.ws.readyState !== 1) return;
    execOnAgent(guardCmd, 10000, agentId).then(function(r) {
      var out = (r.output || '').trim();
      if (out.startsWith('DIRTY:')) {
        console.log('[guard:' + agentId + '] hosts dirty, auto-cleaning...');
        execOnAgent(cleanCmd, 10000, agentId).then(function(r2) {
          console.log('[guard:' + agentId + '] hosts cleaned:', (r2.output || '').trim());
          notifySense('say', { level: 'system', text: '<b>无感守护[' + agentId + ']:</b> 检测到hosts写入，已自动清理。' });
        }).catch(function() {});
      }
    }).catch(function() {});
  }, 60000);
  console.log('[guard:' + agentId + '] hosts guard started (60s interval)');
}
function stopHostsGuard(agentId) {
  var agent = agents.get(agentId); if (!agent || !agent.hostsGuardTimer) return;
  clearInterval(agent.hostsGuardTimer); agent.hostsGuardTimer = null; console.log('[guard:' + agentId + '] stopped');
}

// ==================== EXEC ENGINE ====================
function execOnAgent(cmd, timeout, agentId) {
  timeout = timeout || 30000;
  return new Promise(function(resolve, reject) {
    var agent = agentId ? agents.get(agentId) : getSelectedAgent();
    if (!agent || !agent.ws || agent.ws.readyState !== 1) return reject(new Error('agent not connected'));
    var id = crypto.randomUUID();
    var timer = setTimeout(function() { pendingCommands.delete(id); reject(new Error('timeout')); }, timeout);
    pendingCommands.set(id, { resolve: resolve, reject: reject, timer: timer, cmd: cmd });
    agent.ws.send(JSON.stringify({ type: 'exec', id: id, cmd: cmd }));
    console.log('[brain->' + (agent.data.hostname || '?') + ']', cmd.substring(0, 80));
  });
}

function notifySense(type, data) {
  if (senseSocket && senseSocket.readyState === 1) {
    senseSocket.send(JSON.stringify(Object.assign({ type: type }, data)));
  }
}

function forwardTerminal(id, cmd, output, ok) {
  notifySense('terminal', { id: id, cmd: cmd, output: output, ok: ok });
}

// ==================== AGENT SCRIPT ====================
function getAgentScript() {
  var L = [];
  L.push('# Dao Remote Agent v2.0');
  L.push('# Run as Admin: irm "' + HTTP_PROTO + PUBLIC_URL + '/agent.ps1?key=' + AUTH_AGENT_KEY + '" | iex');
  L.push('$ErrorActionPreference = "Continue"');
  L.push('[Console]::OutputEncoding = [System.Text.Encoding]::UTF8');
  L.push('chcp 65001 | Out-Null');
  L.push('$server = "' + WS_PROTO + PUBLIC_URL + '/ws/agent?key=' + AUTH_AGENT_KEY + '"');
  L.push('Write-Host "`n  ===== Dao Remote Agent =====`n  Target: $server`n" -ForegroundColor Cyan');
  L.push('function Send-Msg($ws, $obj) {');
  L.push('  $j = $obj | ConvertTo-Json -Depth 5 -Compress');
  L.push('  $b = [Text.Encoding]::UTF8.GetBytes($j)');
  L.push('  $ws.SendAsync([ArraySegment[byte]]::new($b), [Net.WebSockets.WebSocketMessageType]::Text, $true, [Threading.CancellationToken]::None).GetAwaiter().GetResult() | Out-Null');
  L.push('}');
  L.push('function Get-Info { @{ hostname=$env:COMPUTERNAME; user=$env:USERNAME; os=(Get-CimInstance Win32_OperatingSystem -EA SilentlyContinue).Caption; isAdmin=([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator); psVer=$PSVersionTable.PSVersion.ToString(); arch=$env:PROCESSOR_ARCHITECTURE } }');
  L.push('while ($true) {');
  L.push('  try {');
  L.push('    $ws = [Net.WebSockets.ClientWebSocket]::new()');
  L.push('    $ws.Options.KeepAliveInterval = [TimeSpan]::FromSeconds(15)');
  L.push('    $ct = [Threading.CancellationToken]::None');
  L.push('    Write-Host "[...] Connecting..." -ForegroundColor Yellow');
  L.push('    $ws.ConnectAsync([Uri]$server, $ct).GetAwaiter().GetResult()');
  L.push('    Write-Host "[OK] Connected!" -ForegroundColor Green');
  L.push('    Send-Msg $ws @{type="hello"; sysinfo=(Get-Info)}');
  L.push('    $buf = [byte[]]::new(1048576)');
  L.push('    while ($ws.State -eq [Net.WebSockets.WebSocketState]::Open) {');
  L.push('      $seg = [ArraySegment[byte]]::new($buf)');
  L.push('      $r = $ws.ReceiveAsync($seg, $ct).GetAwaiter().GetResult()');
  L.push('      if ($r.MessageType -eq [Net.WebSockets.WebSocketMessageType]::Close) { break }');
  L.push('      $n = $r.Count; while (-not $r.EndOfMessage) { $seg = [ArraySegment[byte]]::new($buf,$n,$buf.Length-$n); $r = $ws.ReceiveAsync($seg,$ct).GetAwaiter().GetResult(); $n += $r.Count }');
  L.push('      $msg = [Text.Encoding]::UTF8.GetString($buf,0,$n) | ConvertFrom-Json');
  L.push('      switch ($msg.type) {');
  L.push('        "exec" {');
  L.push('          Write-Host "[>] $($msg.cmd)" -ForegroundColor Yellow');
  L.push('          try { $sw=[Diagnostics.Stopwatch]::StartNew(); $out=(Invoke-Expression $msg.cmd) 2>&1|Out-String; $sw.Stop(); $out=$out.TrimEnd()');
  L.push('            if($out.Length -gt 102400){$out=$out.Substring(0,102400)+"`n...[truncated]"}');
  L.push('            Write-Host "[<] $($sw.ElapsedMilliseconds)ms" -ForegroundColor Green');
  L.push('            Send-Msg $ws @{type="cmd_result";id=$msg.id;ok=$true;output=$out;ms=$sw.ElapsedMilliseconds}');
  L.push('          } catch { Write-Host "[!] $_" -ForegroundColor Red; Send-Msg $ws @{type="cmd_result";id=$msg.id;ok=$false;output=$_.Exception.Message;ms=0} }');
  L.push('        }');
  L.push('        "get_sysinfo" {');
  L.push('          try { $c=(Get-CimInstance Win32_Processor -EA SilentlyContinue|Select -First 1).Name; $o=Get-CimInstance Win32_OperatingSystem -EA SilentlyContinue');
  L.push('            $dk=Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" -EA SilentlyContinue|%{@{drive=$_.DeviceID;sizeGB=[math]::Round($_.Size/1GB,1);freeGB=[math]::Round($_.FreeSpace/1GB,1)}}');
  L.push('            $ad=Get-NetAdapter -EA SilentlyContinue|?{$_.Status -eq "Up"}|%{@{name=$_.Name;desc=$_.InterfaceDescription;speed=$_.LinkSpeed}}');
  L.push('            Send-Msg $ws @{type="sysinfo";cpu=$c;os=$o.Caption+" "+$o.Version;ramGB=[math]::Round($o.TotalVisibleMemorySize/1MB,1);ramFreeGB=[math]::Round($o.FreePhysicalMemory/1MB,1);disks=$dk;adapters=$ad;processes=(Get-Process -EA SilentlyContinue).Count;uptime=[math]::Round((New-TimeSpan -Start $o.LastBootUpTime).TotalHours,1)}');
  L.push('          } catch { Send-Msg $ws @{type="sysinfo";error=$_.Exception.Message} }');
  L.push('        }');
  L.push('        "ping" { Send-Msg $ws @{type="pong";time=(Get-Date -Format o)} }');
  L.push('      }');
  L.push('    }');
  L.push('  } catch { Write-Host "[-] $_" -ForegroundColor Red }');
  L.push('  Write-Host "[...] Reconnect 5s..." -ForegroundColor Yellow; Start-Sleep 5');
  L.push('}');
  return L.join('\r\n');
}

// ==================== SENSE PAGE ====================
function getSensePage() {
  return require('./page.js')(PUBLIC_URL, AUTH_AGENT_KEY);
}

// ==================== ANALYSIS ENGINE (BROWSER DIAG) ====================
function analyzeDiagnostics(results) {
  var dns = results.filter(function(r) { return r.name.startsWith('DNS:') && !r.name.includes('ref'); });
  var https = results.filter(function(r) { return r.name.startsWith('HTTPS:') && !r.name.includes('ref'); });
  var ip = results.filter(function(r) { return r.name.startsWith('IP:'); });
  var ref = results.filter(function(r) { return r.name.includes('ref'); });
  var dnsOk = dns.filter(function(r) { return r.status === 'pass'; }).length;
  var dnsFail = dns.filter(function(r) { return r.status === 'fail'; }).length;
  var httpsOk = https.filter(function(r) { return r.status === 'pass'; }).length;
  var httpsFail = https.filter(function(r) { return r.status === 'fail'; }).length;
  var refOk = ref.filter(function(r) { return r.status === 'pass'; }).length;

  // Detect Clash/VPN environment:
  // Pattern 1: DNS returns 198.18.0.x fake-IPs (Clash fake-IP mode)
  // Pattern 2: DNS all fail but HTTPS all pass (Clash blocks DoH but proxies HTTPS)
  var clashByFakeIP = dns.some(function(r) { return r.detail && r.detail.match(/198\.18\./); });
  var clashByProxy = dnsFail > 0 && httpsFail === 0 && httpsOk >= 2;
  var clashDetected = clashByFakeIP || clashByProxy;

  var a = { level: '', summary: '', fixParts: [], clash: clashDetected };

  if (clashDetected) {
    // Clash/VPN env: traffic goes through proxy tunnel
    if (httpsOk > 0) {
      a.level = 'alert-ok';
      var mode = clashByFakeIP ? 'fake-IP模式' : 'DoH拦截+HTTPS代理';
      a.summary = '<b>网络正常 (Clash/VPN代理中)</b> — ' + mode + '，HTTPS通道畅通(' + httpsOk + '/' + https.length + ')。如Windsurf仍有问题，请检查Clash规则或hosts文件。';
      a.fixParts = ['hosts', 'cache'];
    } else {
      a.level = 'alert-warn';
      a.summary = '<b>Clash/VPN代理异常</b> — 检测到代理环境但HTTPS全部失败。请检查Clash是否正常运行。';
      a.fixParts = ['hosts', 'cache'];
    }
  } else if (dnsFail === 0 && httpsFail === 0) {
    a.level = 'alert-ok';
    a.summary = '<b>网络完全正常!</b> DNS全通、HTTPS全通。如Windsurf仍有问题，根因在本地缓存或配置。';
    a.fixParts = ['proxy', 'cache'];
  } else if (dnsFail > 0 && refOk > 0) {
    a.level = 'alert-err'; a.summary = '<b>DNS解析异常</b> — GitHub可达但Windsurf域名(' + dnsFail + '个)失败，疑似DNS污染或hosts劫持。'; a.fixParts = ['proxy', 'dns', 'hosts', 'cache'];
  } else if (httpsFail > 0 && dnsOk > 0) {
    a.level = 'alert-warn'; a.summary = '<b>HTTPS连接异常</b> — DNS正常但HTTPS失败(' + httpsFail + '个)，可能被防火墙或代理拦截。'; a.fixParts = ['proxy', 'firewall', 'cache'];
  } else if (dnsFail > 0 && httpsFail > 0) {
    a.level = 'alert-err'; a.summary = '<b>网络严重异常</b> — DNS+HTTPS大面积失败，服务不可达。'; a.fixParts = ['proxy', 'dns', 'hosts', 'firewall', 'cache'];
  } else if (refOk === 0) {
    a.level = 'alert-err'; a.summary = '<b>网络整体不通</b> — 连GitHub都无法访问，请检查网线/WiFi/路由器。'; a.fixParts = ['proxy', 'dns'];
  } else {
    a.level = 'alert-warn'; a.summary = '<b>部分异常</b> (DNS:' + dnsOk + '/' + dns.length + ' HTTPS:' + httpsOk + '/' + https.length + ')'; a.fixParts = ['proxy', 'dns', 'hosts', 'firewall', 'cache'];
  }
  a.fixCmd = buildFixCommand(a.fixParts);
  return a;
}

function buildFixCommand(parts) {
  var c = ['Write-Host "===== Windsurf Fix =====" -ForegroundColor Cyan'], s = 1, t = parts.length;
  if (parts.includes('proxy')) {
    c.push('Write-Host "[' + s + '/' + t + '] Proxy..." -ForegroundColor Yellow');
    c.push("& \"$env:SystemRoot\\System32\\netsh.exe\" winhttp reset proxy");
    c.push("[Environment]::SetEnvironmentVariable('HTTP_PROXY','','User')");
    c.push("[Environment]::SetEnvironmentVariable('HTTPS_PROXY','','User')");
    c.push("[Environment]::SetEnvironmentVariable('ALL_PROXY','','User')");
    c.push("Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings' -Name ProxyEnable -Value 0 -EA SilentlyContinue");
    c.push("Write-Host '  OK' -ForegroundColor Green"); s++;
  }
  if (parts.includes('dns')) {
    c.push('Write-Host "[' + s + '/' + t + '] DNS..." -ForegroundColor Yellow');
    c.push("& \"$env:SystemRoot\\System32\\ipconfig.exe\" /flushdns"); c.push("& \"$env:SystemRoot\\System32\\netsh.exe\" winsock reset");
    c.push("$a=Get-NetAdapter|?{$_.Status -eq 'Up'}; foreach($n in $a){Set-DnsClientServerAddress -InterfaceIndex $n.ifIndex -ServerAddresses ('223.5.5.5','8.8.8.8') -EA SilentlyContinue}");
    c.push("Write-Host '  DNS->223.5.5.5/8.8.8.8' -ForegroundColor Green"); s++;
  }
  if (parts.includes('hosts')) {
    c.push('Write-Host "[' + s + '/' + t + '] Hosts..." -ForegroundColor Yellow');
    c.push('$hp="$env:SystemRoot\\System32\\drivers\\etc\\hosts"');
    c.push("$h=Get-Content $hp -EA SilentlyContinue; if($h){$h|?{$_ -notmatch 'codeium|windsurf|exafunction'}|Set-Content $hp -Encoding ASCII}");
    c.push("Write-Host '  OK' -ForegroundColor Green"); s++;
  }
  if (parts.includes('firewall')) {
    c.push('Write-Host "[' + s + '/' + t + '] Firewall..." -ForegroundColor Yellow');
    c.push("Remove-NetFirewallRule -DisplayName 'Windsurf*' -EA SilentlyContinue");
    c.push("Write-Host '  OK' -ForegroundColor Green"); s++;
  }
  if (parts.includes('cache')) {
    c.push('Write-Host "[' + s + '/' + t + '] Cache..." -ForegroundColor Yellow');
    c.push("Stop-Process -Name Windsurf -Force -EA SilentlyContinue; Start-Sleep 2");
    c.push("Remove-Item \"$env:APPDATA\\Windsurf\\Cache\" -Recurse -Force -EA SilentlyContinue");
    c.push("Remove-Item \"$env:APPDATA\\Windsurf\\Network\" -Recurse -Force -EA SilentlyContinue");
    c.push("Write-Host '  OK' -ForegroundColor Green");
  }
  c.push('Write-Host "`n===== Done! Restart PC =====" -ForegroundColor Cyan');
  return c.join('; ');
}

// ==================== AUTO ANALYSIS ENGINE (AGENT DIAG) ====================
function analyzeAutoResults(results) {
  var get = function(name) { var r = results.find(function(x){return x.name===name}); return r ? r.output : ''; };
  var ok = function(name) { var r = results.find(function(x){return x.name===name}); return r && r.ok; };

  var issues = [];
  var fixes = [];
  var level = 'alert-ok';

  // Detect Clash/VPN: DNS returns 198.18.0.x (Clash fake-IP) or DNS config has 198.18.0.x
  var dnsWS = get('dns_windsurf');
  var dnsGH = get('dns_github');
  var dnsConfig = get('dns_config');
  var clashDetected = /198\.18\./.test(dnsWS) || /198\.18\./.test(dnsGH) || /198\.18\./.test(dnsConfig);

  // Check hosts — this is critical in BOTH normal and Clash environments
  var hosts = get('hosts_windsurf');
  if (hosts && hosts !== '(clean)') {
    issues.push('<b>hosts文件劫持:</b> ' + hosts.substring(0,80));
    if (clashDetected) {
      fixes.push('<b>关键!</b> hosts条目绕过了Clash代理，导致Windsurf直连失败。删除hosts中的windsurf/codeium条目');
    } else {
      fixes.push('清理hosts文件中的windsurf/codeium条目');
    }
    level = 'alert-err';
  }

  if (clashDetected) {
    // Clash/VPN environment — different analysis logic
    var pingOk = get('ping_windsurf').indexOf('True') >= 0;
    if (pingOk && issues.length === 0) {
      // Clash working + no hosts issue = likely OK
      level = 'alert-ok';
    } else if (!pingOk && issues.length === 0) {
      issues.push('Clash/VPN代理下windsurf.com:443不可达 — 检查Clash规则');
      fixes.push('确认Clash规则包含windsurf.com和codeium.com的代理规则');
      level = 'alert-warn';
    }
    // Don't flag 198.18.0.x DNS as pollution — it's Clash fake-IP
    // Don't flag system proxy — Clash manages it
  } else {
    // Normal (non-VPN) environment — original analysis logic
    var proxy = get('proxy_check');
    var envProxy = get('env_proxy');
    if (ok('proxy_check') && proxy.indexOf('直接访问') < 0 && proxy.indexOf('Direct') < 0) {
      issues.push('系统代理已配置: ' + proxy.replace(/\n/g,' ').substring(0,60));
      fixes.push('清除系统代理: <code>netsh winhttp reset proxy</code>');
      if (level === 'alert-ok') level = 'alert-warn';
    }
    if (envProxy.indexOf('HTTP_PROXY=') >= 0 && envProxy.replace(/HTTP_PROXY= \|/,'').replace(/HTTPS_PROXY= \|/,'').replace(/ALL_PROXY=/,'').trim()) {
      issues.push('环境变量代理: ' + envProxy);
      fixes.push('清除代理环境变量');
      if (level === 'alert-ok') level = 'alert-warn';
    }

    // DNS check (only in non-Clash env)
    if (!ok('dns_windsurf') && ok('dns_github')) {
      issues.push('Windsurf DNS解析失败但GitHub正常 — DNS劫持或污染');
      fixes.push('切换DNS到 223.5.5.5 / 8.8.8.8');
      level = 'alert-err';
    } else if (!ok('dns_windsurf') && !ok('dns_github')) {
      issues.push('DNS完全不可用');
      fixes.push('检查网络连接, 切换DNS');
      level = 'alert-err';
    }

    // Connectivity check
    var ping = get('ping_windsurf');
    if (ping.indexOf('False') >= 0) {
      issues.push('windsurf.com:443 TCP连接失败');
      if (issues.length === 1) fixes.push('检查防火墙规则, 考虑添加Windsurf白名单');
      level = 'alert-err';
    }

    // Firewall check
    var fw = get('firewall_windsurf');
    if (fw.indexOf('Block') >= 0) {
      issues.push('防火墙规则阻止了Windsurf');
      fixes.push('删除阻止规则: <code>Remove-NetFirewallRule -DisplayName "Windsurf*"</code>');
      level = 'alert-err';
    }
  }

  // Check Windsurf process (both envs)
  var wsProc = get('windsurf_process');
  var wsPath = get('windsurf_path');
  if (wsProc.indexOf('not running') >= 0) { issues.push('Windsurf未运行'); }
  if (wsPath.indexOf('not found') >= 0) { issues.push('未找到Windsurf安装路径'); fixes.push('重新安装Windsurf'); level = 'alert-err'; }

  // Check memory (both envs)
  var cpuMem = get('cpu_mem');
  var freeMatch = cpuMem.match(/free ([\d.]+)GB/);
  if (freeMatch && parseFloat(freeMatch[1]) < 1.0) {
    issues.push('内存不足: 仅剩 ' + freeMatch[1] + 'GB 空闲');
    fixes.push('关闭不必要的程序释放内存');
    if (level === 'alert-ok') level = 'alert-warn';
  }

  // Summary
  var env = clashDetected ? ' <span style="color:#ffa726">[Clash/VPN环境]</span>' : '';
  var summary;
  if (issues.length === 0) {
    summary = '<b>诊断完成: 一切正常</b>' + env + ' — 网络通畅, hosts干净。如Windsurf仍有问题,建议清除缓存后重启。';
    fixes.push('清除Windsurf缓存: 删除 %APPDATA%\\Windsurf\\Cache 和 Network 目录, 重启电脑');
  } else {
    summary = '<b>发现 ' + issues.length + ' 个问题:</b>' + env + '<br>' + issues.map(function(x){return '• '+x}).join('<br>');
  }

  return { level: level, summary: summary, issues: issues, fixes: fixes, clash: clashDetected };
}

// ==================== HTTP SERVER ====================
function readBody(req, cb) { var b = ''; req.on('data', function(c) { b += c; }); req.on('end', function() { cb(b); }); }
function jsonReply(res, data, code) { res.writeHead(code || 200, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }); res.end(JSON.stringify(data)); }

function getLoginPage() {
  return '<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>\u9053 \u00b7 \u767b\u5f55</title>'
  + '<style>*{margin:0;padding:0;box-sizing:border-box}body{background:#0a0e17;color:#e0e0e0;font-family:-apple-system,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh}'
  + '.box{background:#111827;border:1px solid #1e3a5f;border-radius:16px;padding:40px;width:340px;text-align:center}'
  + 'h1{font-size:28px;margin-bottom:8px}p{color:#667;font-size:13px;margin-bottom:24px}'
  + 'input{width:100%;padding:12px;background:#0a0e17;border:1px solid #1e3a5f;border-radius:8px;color:#e0e0e0;font-size:15px;margin-bottom:16px;outline:none}'
  + 'input:focus{border-color:#7c8aff}button{width:100%;padding:12px;background:#7c8aff;color:#fff;border:none;border-radius:8px;font-size:15px;cursor:pointer}'
  + 'button:hover{background:#6b7bff}.err{color:#ff6b6b;font-size:13px;margin-top:12px;display:none}</style></head>'
  + '<body><div class="box"><h1>\u9053 \u00b7 \u8fdc\u7a0b\u4e2d\u67a2</h1><p>\u8bf7\u8f93\u5165\u7ba1\u7406\u5bc6\u7801</p>'
  + '<input id="pw" type="password" placeholder="\u5bc6\u7801" autofocus onkeydown="if(event.key===\'Enter\')go()"><button onclick="go()">\u767b\u5f55</button>'
  + '<div class="err" id="err"></div></div>'
  + '<script>var bp=location.pathname.replace(/\\/+$/,"");function go(){var p=document.getElementById("pw").value;if(!p)return;fetch(bp+"/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({password:p})})'
  + '.then(function(r){return r.json()}).then(function(d){if(d.ok){document.cookie="dao_token="+d.token+";path=/;max-age=31536000;SameSite=Lax";location.href=bp+"/"}'
  + 'else{var e=document.getElementById("err");e.textContent=d.error||"\u5bc6\u7801\u9519\u8bef";e.style.display="block"}})}</script></body></html>';
}

const server = http.createServer(function(req, res) {
  var url = new URL(req.url, 'http://localhost');
  if (req.method === 'OPTIONS') { res.writeHead(204, { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET,POST', 'Access-Control-Allow-Headers': 'Content-Type,Authorization' }); res.end(); return; }

  // Public endpoints (no auth)
  if (req.method === 'POST' && url.pathname === '/login') {
    readBody(req, function(body) {
      try { var m = JSON.parse(body);
        if (m.password === AUTH_PASSWORD) { var token = generateToken(); res.writeHead(200, { 'Content-Type': 'application/json', 'Set-Cookie': 'dao_token=' + token + '; Path=/; Max-Age=31536000; SameSite=Lax' }); res.end(JSON.stringify({ ok: true, token: token })); }
        else { jsonReply(res, { ok: false, error: '密码错误' }, 401); }
      } catch(e) { jsonReply(res, { error: 'bad json' }, 400); }
    }); return;
  }
  if (req.method === 'GET' && url.pathname === '/agent.ps1') {
    var agentKey = url.searchParams.get('key');
    if (agentKey !== AUTH_AGENT_KEY) { res.writeHead(403); res.end('Forbidden'); return; }
    res.writeHead(200, { 'Content-Type': 'text/plain; charset=utf-8' }); res.end(getAgentScript()); return;
  }

  if (req.method === 'GET' && url.pathname === '/favicon.ico') { res.writeHead(204); res.end(); return; }

  // Public deploy script for VM setup
  if (req.method === 'GET' && url.pathname === '/deploy-vm.ps1') {
    var scriptPath = path.resolve(__dirname, '..', '..', 'Windsurf无限额度', 'deploy_vm.ps1');
    try { var scriptData = fs.readFileSync(scriptPath, 'utf8'); res.writeHead(200, { 'Content-Type': 'text/plain; charset=utf-8', 'Content-Length': Buffer.byteLength(scriptData) }); res.end(scriptData); }
    catch(e) { res.writeHead(404); res.end('deploy script not found'); }
    return;
  }

  // Public cert endpoints (agent downloads these during windsurf-setup)
  if (req.method === 'GET' && url.pathname === '/windsurf-cert.cer') {
    var cerPath = path.resolve(__dirname, '..', '..', 'Windsurf无限额度', 'windsurf_proxy_ca.cer');
    try { var cerData = fs.readFileSync(cerPath); res.writeHead(200, { 'Content-Type': 'application/x-x509-ca-cert', 'Content-Length': cerData.length }); res.end(cerData); }
    catch(e) { res.writeHead(404); res.end('cert not found'); }
    return;
  }
  if (req.method === 'GET' && url.pathname === '/windsurf-cert.pem') {
    var pemPath = path.resolve(__dirname, '..', '..', 'Windsurf无限额度', 'windsurf_proxy_ca.pem');
    try { var pemData = fs.readFileSync(pemPath); res.writeHead(200, { 'Content-Type': 'application/x-pem-file', 'Content-Length': pemData.length }); res.end(pemData); }
    catch(e) { res.writeHead(404); res.end('pem not found'); }
    return;
  }

  // ==================== ☰乾: HEALTH (public, no auth) ====================
  if (req.method === 'GET' && url.pathname === '/health') {
    var agentList = [];
    agents.forEach(function(a, id) {
      agentList.push({ id: id, connected: !!(a.ws && a.ws.readyState === 1), hostname: a.data.hostname, user: a.data.user, lastPong: a.data.lastPong || null });
    });
    jsonReply(res, {
      status: 'ok', version: '3.1', uptime: process.uptime(),
      agents: { total: agents.size, connected: agentList.filter(function(a){return a.connected}).length, list: agentList },
      sense: { connected: senseData.connected },
      memory: { rss: Math.round(process.memoryUsage().rss / 1048576), tokens: validTokens.size, history: commandHistory.length, pending: pendingCommands.size }
    });
    return;
  }

  // Auth check for all other endpoints
  if (!checkAuth(req)) {
    if (req.method === 'GET' && (url.pathname === '/' || url.pathname === '/sense' || url.pathname === '/login')) {
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' }); res.end(getLoginPage()); return;
    }
    jsonReply(res, { error: 'unauthorized' }, 401); return;
  }

  // Authenticated endpoints
  if (req.method === 'GET' && (url.pathname === '/' || url.pathname === '/sense')) {
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' }); res.end(getSensePage()); return;
  }
  if (req.method === 'GET' && url.pathname === '/brain/state') {
    var sa = getSelectedAgent(); var ad = sa ? sa.data : { connected: false };
    jsonReply(res, { sense: senseData, agent: ad, agents: getAgentList(), selectedAgent: selectedAgentId, pending: pendingCommands.size, history: commandHistory.length }); return;
  }
  if (req.method === 'GET' && url.pathname === '/brain/agents') {
    jsonReply(res, { ok: true, agents: getAgentList(), selected: selectedAgentId }); return;
  }
  if (req.method === 'POST' && url.pathname === '/brain/select') {
    readBody(req, function(body) {
      try { var m = JSON.parse(body);
        if (agents.has(m.id)) { selectedAgentId = m.id; notifySense('agent_switch', { id: m.id, agents: getAgentList() }); jsonReply(res, { ok: true, selected: m.id }); }
        else { jsonReply(res, { ok: false, error: 'agent not found' }, 404); }
      } catch(e) { jsonReply(res, { error: 'bad json' }, 400); }
    }); return;
  }
  if (req.method === 'GET' && url.pathname === '/brain/results') { jsonReply(res, senseData.diagnostics || []); return; }
  if (req.method === 'GET' && url.pathname === '/brain/terminal') {
    var n = parseInt(url.searchParams.get('n')) || 20; jsonReply(res, commandHistory.slice(-n)); return;
  }
  if (req.method === 'POST' && url.pathname === '/brain/say') {
    readBody(req, function(body) {
      try { var m = JSON.parse(body);
        if (senseSocket && senseSocket.readyState === 1) { senseSocket.send(JSON.stringify({ type: 'say', level: m.level || 'system', text: m.text })); jsonReply(res, { ok: true, delivered: true }); }
        else { messageQueue.push(m); jsonReply(res, { ok: true, queued: true }); }
      } catch(e) { jsonReply(res, { error: 'bad json' }, 400); }
    }); return;
  }
  if (req.method === 'POST' && url.pathname === '/brain/command') {
    readBody(req, function(body) {
      try { var m = JSON.parse(body);
        if (senseSocket && senseSocket.readyState === 1) { senseSocket.send(JSON.stringify({ type: 'command', title: m.title, cmd: m.cmd, steps: m.steps || '' })); jsonReply(res, { ok: true }); }
        else { jsonReply(res, { ok: false, error: 'sense not connected' }); }
      } catch(e) { jsonReply(res, { error: 'bad json' }, 400); }
    }); return;
  }
  if (req.method === 'GET' && url.pathname === '/brain/messages') {
    var msgs = global.userMessages || [];
    var clear = url.searchParams.get('clear') !== 'false';
    if (clear) global.userMessages = [];
    jsonReply(res, { ok: true, count: msgs.length, messages: msgs });
    return;
  }
  if (req.method === 'POST' && url.pathname === '/brain/exec') {
    readBody(req, function(body) {
      try { var m = JSON.parse(body);
        execOnAgent(m.cmd, m.timeout || 30000).then(function(r) {
          commandHistory.push({ cmd: m.cmd, output: r.output, ok: r.ok, ms: r.ms, time: new Date().toISOString() });
          if (commandHistory.length > 500) commandHistory = commandHistory.slice(-500);
          forwardTerminal(null, m.cmd, r.output, r.ok);
          jsonReply(res, { ok: r.ok, output: r.output, ms: r.ms });
        }).catch(function(e) { jsonReply(res, { ok: false, error: e.message }); });
      } catch(e) { jsonReply(res, { error: 'bad json' }, 400); }
    }); return;
  }
  if (req.method === 'POST' && url.pathname === '/brain/sysinfo') {
    var sa = getSelectedAgent();
    if (sa && sa.ws.readyState === 1) {
      sa.ws.send(JSON.stringify({ type: 'get_sysinfo' }));
      var w = 0, ck = setInterval(function() {
        w += 500;
        if (sa.data.sysinfo && sa.data.lastUpdate && Date.now() - new Date(sa.data.lastUpdate).getTime() < 15000) { clearInterval(ck); jsonReply(res, { ok: true, data: sa.data.sysinfo }); }
        else if (w > 10000) { clearInterval(ck); jsonReply(res, { ok: false, error: 'timeout' }); }
      }, 500);
    } else { jsonReply(res, { ok: false, error: 'agent not connected' }); }
    return;
  }
  if (req.method === 'POST' && url.pathname === '/brain/auto') {
    var sa = getSelectedAgent();
    if (!sa || sa.ws.readyState !== 1) { jsonReply(res, { ok: false, error: 'agent not connected' }); return; }
    var diagSteps = [
      { name: 'hostname', cmd: '$env:COMPUTERNAME' },
      { name: 'user', cmd: '$env:USERNAME + " | Admin=" + ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)' },
      { name: 'os', cmd: '(Get-CimInstance Win32_OperatingSystem).Caption + " " + (Get-CimInstance Win32_OperatingSystem).Version' },
      { name: 'uptime', cmd: '[math]::Round((New-TimeSpan -Start (Get-CimInstance Win32_OperatingSystem).LastBootUpTime).TotalHours, 1).ToString() + " hours"' },
      { name: 'cpu_mem', cmd: '$c=(Get-CimInstance Win32_Processor|Select -First 1).Name; $o=Get-CimInstance Win32_OperatingSystem; "$c | RAM: $([math]::Round($o.TotalVisibleMemorySize/1MB,1))GB (free $([math]::Round($o.FreePhysicalMemory/1MB,1))GB)"' },
      { name: 'disk', cmd: 'Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" | ForEach-Object { "$($_.DeviceID) $([math]::Round($_.FreeSpace/1GB,1))/$([math]::Round($_.Size/1GB,1))GB" }' },
      { name: 'network_adapters', cmd: 'Get-NetAdapter | Where Status -eq Up | ForEach-Object { "$($_.Name): $($_.InterfaceDescription) ($($_.LinkSpeed))" }' },
      { name: 'dns_config', cmd: 'Get-DnsClientServerAddress -AddressFamily IPv4 | Where ServerAddresses | ForEach-Object { "$($_.InterfaceAlias): $($_.ServerAddresses -join \',\')" }' },
      { name: 'proxy_check', cmd: '& "$env:SystemRoot\\System32\\netsh.exe" winhttp show proxy' },
      { name: 'env_proxy', cmd: '"HTTP_PROXY=" + $env:HTTP_PROXY + " | HTTPS_PROXY=" + $env:HTTPS_PROXY + " | ALL_PROXY=" + $env:ALL_PROXY' },
      { name: 'hosts_windsurf', cmd: '$h=Get-Content "$env:SystemRoot\\System32\\drivers\\etc\\hosts" -EA SilentlyContinue | Where-Object {$_ -match "windsurf|codeium"}; if($h){$h}else{"(clean)"}' },
      { name: 'dns_windsurf', cmd: 'Resolve-DnsName windsurf.com -Type A -EA SilentlyContinue | Select -First 1 | ForEach-Object { "$($_.Name) -> $($_.IPAddress)" }' },
      { name: 'dns_github', cmd: 'Resolve-DnsName github.com -Type A -EA SilentlyContinue | Select -First 1 | ForEach-Object { "$($_.Name) -> $($_.IPAddress)" }' },
      { name: 'ping_windsurf', cmd: 'Test-NetConnection windsurf.com -Port 443 -WarningAction SilentlyContinue | ForEach-Object { "TCP443=$($_.TcpTestSucceeded) latency=$($_.PingReplyDetails.RoundtripTime)ms" }' },
      { name: 'windsurf_process', cmd: 'Get-Process Windsurf -EA SilentlyContinue | ForEach-Object { "PID=$($_.Id) Mem=$([math]::Round($_.WorkingSet64/1MB))MB CPU=$([math]::Round($_.CPU,1))s" }; if(-not (Get-Process Windsurf -EA SilentlyContinue)){"(not running)"}' },
      { name: 'windsurf_path', cmd: '$paths=@("$env:LOCALAPPDATA\\Programs\\Windsurf\\Windsurf.exe","C:\\Program Files\\Windsurf\\Windsurf.exe","D:\\Windsurf\\Windsurf.exe","F:\\Windsurf\\Windsurf.exe"); $found=$paths|?{Test-Path $_}|Select -First 1; if($found){$found}else{"(not found)"}' },
      { name: 'firewall_windsurf', cmd: '$r=Get-NetFirewallRule -EA SilentlyContinue|?{$_.DisplayName -match "Windsurf|Codeium"}; if($r){$r|%{"$($_.DisplayName) $($_.Direction) $($_.Action)"}}else{"(no rules)"}' },
    ];
    (async function() {
      var results = [];
      notifySense('say', { level: 'system', text: '<b>自动诊断启动</b> — ' + diagSteps.length + ' 项检查...' });
      for (var i = 0; i < diagSteps.length; i++) {
        var step = diagSteps[i];
        try {
          var r = await execOnAgent(step.cmd, 15000);
          results.push({ name: step.name, ok: r.ok, output: (r.output || '').trim(), ms: r.ms });
          console.log('[auto] ' + (i+1) + '/' + diagSteps.length, step.name, '->', (r.output || '').substring(0, 60).replace(/\n/g, ' '));
        } catch(e) {
          results.push({ name: step.name, ok: false, output: e.message, ms: 0 });
        }
      }
      var analysis = analyzeAutoResults(results);
      notifySense('say', { level: analysis.level, text: analysis.summary });
      if (analysis.fixes.length > 0) {
        notifySense('say', { level: 'system', text: '<b>建议修复:</b><br>' + analysis.fixes.map(function(f,i){return (i+1)+'. '+f}).join('<br>') });
      }
      jsonReply(res, { ok: true, results: results, analysis: analysis });
    })();
    return;
  }
  // ==================== WINDSURF SHARED PROXY AUTO-SETUP ====================
  if (req.method === 'POST' && url.pathname === '/brain/windsurf-setup') {
    readBody(req, function(body) {
      var opts = {};
      try { opts = JSON.parse(body); } catch(e) {}
      var targetId = opts.agentId || selectedAgentId;
      var sa = targetId ? agents.get(targetId) : getSelectedAgent();
      if (!sa || !sa.ws || sa.ws.readyState !== 1) { jsonReply(res, { ok: false, error: 'agent not connected' }); return; }
      if (targetId && targetId !== selectedAgentId) { selectedAgentId = targetId; }
      var frpHost = opts.proxyHost || 'aiotvr.xyz';
      var frpPort = opts.proxyPort || 18443;
      var lanIP = PROXY_LAN_IP;
      var findPaths = '$paths=@("$env:LOCALAPPDATA\\\\Programs\\\\Windsurf\\\\Windsurf.exe","C:\\\\Program Files\\\\Windsurf\\\\Windsurf.exe","D:\\\\Windsurf\\\\Windsurf.exe"); Get-ChildItem "C:\\\\Users" -Directory -EA SilentlyContinue|ForEach-Object{$p=Join-Path $_.FullName "AppData\\\\Local\\\\Programs\\\\Windsurf\\\\Windsurf.exe";if($p -notin $paths){$paths+=$p}}; $found=$paths|?{Test-Path $_}|Select -First 1; $found';
      var findDesktop = '$dt=[Environment]::GetFolderPath("Desktop"); if(-not $dt -or $dt -match "systemprofile" -or -not(Test-Path $dt)){$eu=(Get-CimInstance Win32_ComputerSystem -EA SilentlyContinue).UserName; if($eu){$un=$eu.Split("\\\\")[-1]; $dt="C:\\\\Users\\\\$un\\\\Desktop"; if(-not(Test-Path $dt)){$dt=(Get-ChildItem "C:\\\\Users" -Directory -EA SilentlyContinue|?{$_.Name -ne "Public" -and $_.Name -ne "Default" -and $_.Name -notmatch "systemprofile"}|Select -First 1).FullName+"\\\\Desktop"}}; if(-not $dt -or -not(Test-Path $dt)){$dt="C:\\\\Users\\\\Public\\\\Desktop"}}; $dt';

      (async function() {
        var results = [];
        var mode = 'frp'; // default: FRP public network
        var proxyIP = '127.0.0.1';

        // Step 1: Check admin
        notifySense('say', { level: 'system', text: '<b>Windsurf全自动配置启动</b> — 检测网络拓扑...' });
        try {
          var r1 = await execOnAgent('if(([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){"ADMIN"}else{"NOT_ADMIN"}', 10000);
          var out1 = (r1.output || '').trim();
          results.push({ name: 'check_admin', ok: r1.ok && out1 === 'ADMIN', output: out1 });
          notifySense('say', { level: out1 === 'ADMIN' ? 'alert-ok' : 'alert-err', text: (out1 === 'ADMIN' ? '✅' : '❌') + ' [1] <b>管理员权限</b>: ' + out1 });
          if (out1 !== 'ADMIN') {
            notifySense('say', { level: 'alert-err', text: '❌ <b>需要管理员权限!</b> 请以管理员身份重新运行Agent。' });
            jsonReply(res, { ok: false, error: 'admin required', results: results });
            return;
          }
        } catch(e) {
          results.push({ name: 'check_admin', ok: false, output: e.message });
          jsonReply(res, { ok: false, error: e.message, results: results });
          return;
        }

        // Step 2: Detect network — LAN direct vs FRP
        try {
          var netCmd = 'try{$tcp=New-Object Net.Sockets.TcpClient;$tcp.Connect("' + lanIP + '",443);$tcp.Close();"LAN_OK"}catch{"LAN_FAIL"}';
          var r2 = await execOnAgent(netCmd, 10000);
          var out2 = (r2.output || '').trim();
          if (out2 === 'LAN_OK') { mode = 'lan'; proxyIP = lanIP; }
          results.push({ name: 'detect_network', ok: true, output: mode === 'lan' ? 'LAN直连(' + lanIP + ') ✓ 延迟最低' : 'FRP公网(' + frpHost + ':' + frpPort + ')' });
          notifySense('say', { level: 'alert-ok', text: '✅ [2] <b>网络检测</b>: ' + (mode === 'lan' ? '🏠 LAN直连模式 (' + lanIP + ')' : '🌐 FRP公网模式 (' + frpHost + ')') });
        } catch(e) {
          results.push({ name: 'detect_network', ok: true, output: 'FRP公网(检测超时)' });
          notifySense('say', { level: 'alert-ok', text: '✅ [2] <b>网络检测</b>: 🌐 FRP公网模式(默认)' });
        }

        // Build dynamic steps based on detected mode
        var stepNum = 3;
        var totalSteps = mode === 'lan' ? 10 : 11;
        var dynamicSteps = [
          { name: 'install_cert', cmd: '$certUrl="' + HTTP_PROTO + PUBLIC_URL + '/windsurf-cert.cer"; $tmp="$env:TEMP\\\\windsurf_proxy_ca.cer"; Invoke-WebRequest -Uri $certUrl -OutFile $tmp -UseBasicParsing -EA Stop; $r=certutil -addstore Root $tmp 2>&1; if($LASTEXITCODE -eq 0 -or $r -match "already in store|已在存储中"){"CERT_OK"}else{"CERT_FAIL: $r"}' },
          { name: 'setup_hosts', cmd: '$hp="$env:SystemRoot\\\\System32\\\\drivers\\\\etc\\\\hosts"; $h=Get-Content $hp -EA SilentlyContinue; $clean=$h|Where-Object{$_ -notmatch "windsurf|codeium"}; $clean+="' + proxyIP + ' server.self-serve.windsurf.com"; $clean+="' + proxyIP + ' server.codeium.com"; $clean|Set-Content $hp -Encoding ASCII; "HOSTS_SET: ' + proxyIP + ' (mode=' + mode + ')"' },
        ];
        if (mode === 'frp') {
          dynamicSteps.push({ name: 'setup_portproxy', cmd: '& "$env:SystemRoot\\\\System32\\\\netsh.exe" interface portproxy delete v4tov4 listenaddress=127.0.0.1 listenport=443 2>$null; & "$env:SystemRoot\\\\System32\\\\netsh.exe" interface portproxy add v4tov4 listenaddress=127.0.0.1 listenport=443 connectaddress=' + frpHost + ' connectport=' + frpPort + '; if($LASTEXITCODE -eq 0){"PORTPROXY_OK: 127.0.0.1:443 -> ' + frpHost + ':' + frpPort + '"}else{"PORTPROXY_FAIL"}' });
        } else {
          dynamicSteps.push({ name: 'cleanup_portproxy', cmd: '& "$env:SystemRoot\\\\System32\\\\netsh.exe" interface portproxy delete v4tov4 listenaddress=127.0.0.1 listenport=443 2>$null; schtasks /Delete /TN "WindsurfPortProxy" /F 2>$null; "PORTPROXY_CLEANED: LAN不需要端口转发"' });
        }
        dynamicSteps.push(
          { name: 'setup_ssl_cert_file', cmd: '$pemUrl="' + HTTP_PROTO + PUBLIC_URL + '/windsurf-cert.pem"; $dest="$env:ProgramData\\\\windsurf_proxy_ca.pem"; Invoke-WebRequest -Uri $pemUrl -OutFile $dest -UseBasicParsing -EA Stop; [Environment]::SetEnvironmentVariable("SSL_CERT_FILE",$dest,"Machine"); $env:SSL_CERT_FILE=$dest; "SSL_CERT_FILE=$dest"' },
          { name: 'setup_settings', cmd: '$sd="$env:APPDATA\\\\Windsurf\\\\User"; New-Item $sd -ItemType Directory -Force -EA SilentlyContinue|Out-Null; $sp="$sd\\\\settings.json"; $s=@{}; if(Test-Path $sp){try{$s=Get-Content $sp -Raw|ConvertFrom-Json -AsHashtable}catch{$s=@{}}}; $s["http.proxyStrictSSL"]=$false; $s["http.proxySupport"]="off"; $s|ConvertTo-Json -Depth 5|Set-Content $sp -Encoding UTF8; "SETTINGS_OK"' },
          { name: 'find_windsurf', cmd: findPaths + '; if($found){"FOUND: $found"}else{"NOT_FOUND"}' },
          { name: 'create_launcher', cmd: findPaths + '; ' + findDesktop + '; if($found -and $dt){New-Item $dt -ItemType Directory -Force -EA SilentlyContinue|Out-Null; "@echo off`r`nstart `"`" `"$found`" `"--host-resolver-rules=MAP server.self-serve.windsurf.com ' + proxyIP + ',MAP server.codeium.com ' + proxyIP + '`""|Set-Content "$dt\\\\Windsurf_Proxy.cmd" -Encoding ASCII; if(Test-Path "$dt\\\\Windsurf_Proxy.cmd"){"LAUNCHER_OK: $dt\\\\Windsurf_Proxy.cmd"}else{"LAUNCHER_FAIL"}}else{"SKIP: Windsurf=$found Desktop=$dt"}' }
        );
        if (mode === 'frp') {
          dynamicSteps.push({ name: 'portproxy_persist', cmd: 'schtasks /Delete /TN "WindsurfPortProxy" /F 2>$null; $pp="& \\"$env:SystemRoot\\\\System32\\\\netsh.exe\\" interface portproxy add v4tov4 listenaddress=127.0.0.1 listenport=443 connectaddress=' + frpHost + ' connectport=' + frpPort + '"; schtasks /Create /TN "WindsurfPortProxy" /TR ("powershell -WindowStyle Hidden -Command "+$pp) /SC ONLOGON /RU SYSTEM /RL HIGHEST /F 2>&1|Out-Null; if($LASTEXITCODE -eq 0){"PERSIST_OK: WindsurfPortProxy ONLOGON"}else{"PERSIST_FAIL"}' });
        }
        dynamicSteps.push(
          { name: 'connectivity_test', cmd: 'try{$tcp=New-Object Net.Sockets.TcpClient;$tcp.Connect("' + proxyIP + '",443);$tcp.Close();$r1="TCP_OK"}catch{$r1="TCP_FAIL: $_"};try{$dns=[System.Net.Dns]::GetHostAddresses("server.self-serve.windsurf.com")[0].IPAddressToString;if($dns -eq "' + proxyIP + '"){$r2="DNS_OK"}else{$r2="DNS_WRONG:$dns"}}catch{$r2="DNS_FAIL"};$env:SSL_CERT_FILE=[Environment]::GetEnvironmentVariable("SSL_CERT_FILE","Machine");"$r1 | $r2 | mode=' + mode + '"' },
          { name: 'restart_windsurf', cmd: findPaths + '; ' + findDesktop + '; $ws=Get-Process -Name "Windsurf" -EA SilentlyContinue; if($ws){$ws|Stop-Process -Force -EA SilentlyContinue; Start-Sleep 2; "KILLED "+$ws.Count+" processes"}else{"NO_RUNNING_INSTANCE"}; if($found -and $dt){$cmd="$dt\\\\Windsurf_Proxy.cmd"; if(Test-Path $cmd){Start-Process "cmd.exe" "/c `"$cmd`"" -WindowStyle Hidden; Start-Sleep 3; $newWs=Get-Process -Name "Windsurf" -EA SilentlyContinue; if($newWs){"RESTARTED: "+$newWs.Count+" processes via Proxy launcher"}else{"STARTED: launcher executed, waiting for Windsurf..."}}else{"SKIP: launcher not found at $cmd"}}else{"SKIP: Windsurf=$found Desktop=$dt"}' }
        );

        for (var i = 0; i < dynamicSteps.length; i++) {
          var step = dynamicSteps[i];
          try {
            var r = await execOnAgent(step.cmd, step.name === 'restart_windsurf' ? 45000 : 30000);
            var output = (r.output || '').trim();
            results.push({ name: step.name, ok: r.ok, output: output, ms: r.ms });
            var icon = r.ok ? '✅' : '❌';
            notifySense('say', { level: r.ok ? 'alert-ok' : 'alert-err', text: icon + ' [' + stepNum + '/' + totalSteps + '] <b>' + step.name + '</b>: ' + output.substring(0, 150) });
          } catch(e) {
            results.push({ name: step.name, ok: false, output: e.message, ms: 0 });
            notifySense('say', { level: 'alert-err', text: '❌ [' + stepNum + '/' + totalSteps + '] <b>' + step.name + '</b>: ' + e.message });
          }
          stepNum++;
        }

        var passed = results.filter(function(x){return x.ok}).length;
        var total = results.length;
        var allOk = passed === total;
        var modeLabel = mode === 'lan' ? 'LAN直连(' + lanIP + ')' : 'FRP公网';
        // Store per-agent config result
        if (sa && sa.data) { sa.data.wsConfig = allOk ? 'configured' : 'partial'; sa.data.wsMode = mode; }
        notifySense('say', { level: allOk ? 'alert-ok' : 'alert-warn', text: '<b>配置完成:</b> ' + passed + '/' + total + ' 通过 [' + modeLabel + ']' + (allOk ? '。Windsurf已通过代理模式自动重启！' : '。部分步骤失败，请查看详情。') });
        notifySense('agents_list', { agents: getAgentList(), selected: selectedAgentId });
        jsonReply(res, { ok: allOk, results: results, passed: passed, total: total, mode: mode, proxyIP: proxyIP, agentId: targetId });
      })();
    });
    return;
  }
  // ==================== ☱兑: BROADCAST EXEC (all agents) ====================
  if (req.method === 'POST' && url.pathname === '/brain/broadcast') {
    readBody(req, function(body) {
      try {
        var m = JSON.parse(body);
        var timeout = m.timeout || 30000;
        var promises = [];
        agents.forEach(function(a, id) {
          if (a.ws && a.ws.readyState === 1) {
            promises.push(execOnAgent(m.cmd, timeout, id).then(function(r) {
              return { id: id, hostname: a.data.hostname, ok: r.ok, output: r.output, ms: r.ms };
            }).catch(function(e) {
              return { id: id, hostname: a.data.hostname, ok: false, output: e.message, ms: 0 };
            }));
          }
        });
        if (promises.length === 0) { jsonReply(res, { ok: false, error: 'no agents connected' }); return; }
        Promise.all(promises).then(function(results) {
          jsonReply(res, { ok: true, count: results.length, results: results });
        });
      } catch(e) { jsonReply(res, { error: 'bad json' }, 400); }
    });
    return;
  }

  res.writeHead(404); res.end('Not found');
});

// ==================== ☷坤: STALE AGENT CLEANUP (entropy reduction) ====================
setInterval(function() {
  var now = Date.now();
  agents.forEach(function(a, id) {
    if (!a.ws || a.ws.readyState !== 1) {
      var lastUpdate = a.data.lastUpdate ? new Date(a.data.lastUpdate).getTime() : 0;
      if (now - lastUpdate > 300000) {
        if (a.pingTimer) clearInterval(a.pingTimer);
        stopHostsGuard(id);
        agents.delete(id);
        if (selectedAgentId === id) { selectedAgentId = null; getSelectedAgent(); }
        console.log('[cleanup] removed stale agent:', id);
        notifySense('agents_list', { agents: getAgentList(), selected: selectedAgentId });
      }
    }
  });
}, 60000);

// ==================== WEBSOCKET ====================
const wss = new WebSocketServer({ server });

wss.on('connection', function(ws, req) {
  var urlObj = new URL(req.url, 'http://localhost');
  var path = urlObj.pathname || '';

  // ---- SENSE (Browser) ----
  if (path.startsWith('/ws/sense')) {
    var senseToken = urlObj.searchParams.get('token');
    if (!senseToken || !validTokens.has(senseToken)) { ws.close(4001, 'unauthorized'); return; }
    console.log('[sense] connected');
    senseSocket = ws; senseData.connected = true; senseData.lastUpdate = new Date().toISOString();
    while (messageQueue.length > 0) { var m = messageQueue.shift(); ws.send(JSON.stringify({ type: 'say', level: m.level || 'system', text: m.text })); }
    var sa = getSelectedAgent();
    if (sa) {
      notifySense('agent_status', { connected: true, hostname: sa.data.hostname, user: sa.data.user, os: sa.data.os, isAdmin: sa.data.isAdmin });
      if (sa.data.sysinfo) { notifySense('sysinfo', sa.data.sysinfo); }
      sa.ws.send('{"type":"get_sysinfo"}');
      // Re-run auto-check for sense that connected after agent
      setTimeout(function() {
        var curAgent = getSelectedAgent();
        if (!curAgent || !curAgent.ws || curAgent.ws.readyState !== 1) return;
        var checkCmd = '$pp=& "$env:SystemRoot\\System32\\netsh.exe" interface portproxy show v4tov4 2>$null; $cert=Get-ChildItem Cert:\\LocalMachine\\Root -EA SilentlyContinue|?{$_.Thumbprint -eq "EE8978E69E0CFE3FBD6FFD7E511BE6337A2FC4F7"}; $hp=Get-Content "$env:SystemRoot\\System32\\drivers\\etc\\hosts" -EA SilentlyContinue; $lanMode=$hp|?{$_ -match "192\\.168.*windsurf"}; if($cert -and ($pp -match "18443" -or $lanMode)){"CONFIGURED"}else{"NOT_CONFIGURED"}';
        execOnAgent(checkCmd, 15000).then(function(r) {
          var out = (r.output || '').trim();
          var status = out === 'CONFIGURED' ? 'configured' : 'needed';
          curAgent.data.wsConfig = status;
          notifySense('setup_status', { status: status, hostname: curAgent.data.hostname, agentId: selectedAgentId });
          notifySense('agents_list', { agents: getAgentList(), selected: selectedAgentId });
        }).catch(function() {});
      }, 3000);
    } else {
      notifySense('agent_status', { connected: false });
    }
    notifySense('agents_list', { agents: getAgentList(), selected: selectedAgentId });

    ws.on('message', function(data) {
      try {
        var msg = JSON.parse(data);
        if (msg.type === 'hello') { senseData.ua = msg.ua; senseData.lastUpdate = new Date().toISOString(); console.log('[sense] ua:', (msg.ua || '').substring(0, 50)); }
        if (msg.type === 'test_result') { console.log('[sense]', msg.name, msg.status, msg.detail || ''); }
        if (msg.type === 'diagnostics_complete') {
          console.log('[sense] diag complete:', msg.results.length);
          senseData.diagnostics = msg.results; senseData.lastUpdate = new Date().toISOString();
          var a = analyzeDiagnostics(msg.results);
          console.log('[brain]', a.level, a.summary.replace(/<[^>]*>/g, ''));
          ws.send(JSON.stringify({ type: 'say', level: a.level, text: a.summary }));
          if (a.fixCmd) { ws.send(JSON.stringify({ type: 'command', title: '\u5b9a\u5236\u4fee\u590d\u65b9\u6848', cmd: a.fixCmd, steps: '<b>1.</b> \u53f3\u952e\u5f00\u59cb\u2192\u7ec8\u7aef(\u7ba1\u7406\u5458)<br><b>2.</b> \u590d\u5236\u547d\u4ee4<br><b>3.</b> \u7c98\u8d34\u2192\u56de\u8f66<br><b>4.</b> \u91cd\u542f\u7535\u8111' })); }
        }
        if (msg.type === 'user_message') {
          console.log('[sense] USER MSG:', msg.text);
          if (!global.userMessages) global.userMessages = [];
          global.userMessages.push({ text: msg.text, time: msg.time || new Date().toISOString() });
          if (global.userMessages.length > 200) global.userMessages = global.userMessages.slice(-200);
          ws.send(JSON.stringify({ type: 'say', level: 'system', text: '<b>\u5927\u8111\u5df2\u6536\u5230</b> \u2014 \u6d88\u606f\u5df2\u8bb0\u5f55\uff0c\u7b49\u5f85\u5904\u7406\u3002' }));
        }
        if (msg.type === 'user_exec') {
          var curAgent = getSelectedAgent();
          if (curAgent && curAgent.ws.readyState === 1) {
            var id = msg.id || crypto.randomUUID();
            pendingCommands.set(id, {
              resolve: function(r) { forwardTerminal(id, msg.cmd, r.output, r.ok); commandHistory.push({ cmd: msg.cmd, output: r.output, ok: r.ok, ms: r.ms, time: new Date().toISOString() }); if (commandHistory.length > 500) commandHistory = commandHistory.slice(-500); },
              reject: function() { forwardTerminal(id, msg.cmd, 'Timeout', false); },
              timer: setTimeout(function() { var p = pendingCommands.get(id); if (p) { pendingCommands.delete(id); p.reject(new Error('timeout')); } }, 60000), cmd: msg.cmd
            });
            curAgent.ws.send(JSON.stringify({ type: 'exec', id: id, cmd: msg.cmd }));
          } else { ws.send(JSON.stringify({ type: 'terminal', cmd: msg.cmd, output: 'Error: Agent\u672a\u8fde\u63a5', ok: false })); }
        }
        if (msg.type === 'request_sysinfo') { var ca = getSelectedAgent(); if (ca && ca.ws.readyState === 1) ca.ws.send('{"type":"get_sysinfo"}'); }
        if (msg.type === 'select_agent') {
          if (agents.has(msg.id)) { selectedAgentId = msg.id; var switched = agents.get(msg.id); notifySense('agent_status', { connected: true, hostname: switched.data.hostname, user: switched.data.user, os: switched.data.os, isAdmin: switched.data.isAdmin }); notifySense('agents_list', { agents: getAgentList(), selected: selectedAgentId }); if (switched.data.sysinfo) notifySense('sysinfo', switched.data.sysinfo); }
        }
      } catch (e) { console.error('[sense] err:', e.message); }
    });
    ws.on('close', function() { console.log('[sense] disconnected'); senseSocket = null; senseData.connected = false; });
    return;
  }

  // ---- AGENT (PowerShell) ----
  if (path.startsWith('/ws/agent')) {
    var agentKey = urlObj.searchParams.get('key');
    if (agentKey !== AUTH_AGENT_KEY) { ws.close(4001, 'bad key'); return; }
    var agentId = null;
    console.log('[agent] connected from:', req.socket.remoteAddress);

    ws.on('message', function(data) {
      try {
        var msg = JSON.parse(data);
        if (msg.type === 'hello') {
          var si = msg.sysinfo || {};
          agentId = si.hostname || crypto.randomUUID().substring(0, 8);
          var existing = agents.get(agentId);
          if (existing && existing.ws && existing.ws.readyState === 1) { existing.ws.close(4002, 'replaced'); stopHostsGuard(agentId); if (existing.pingTimer) clearInterval(existing.pingTimer); }
          var agentObj = { ws: ws, data: { connected: true, hostname: si.hostname, user: si.user, os: si.os, isAdmin: si.isAdmin, sysinfo: null, lastUpdate: new Date().toISOString() }, pingTimer: null, hostsGuardTimer: null };
          agentObj.pingTimer = setInterval(function() { if (agentObj.ws && agentObj.ws.readyState === 1) agentObj.ws.send('{"type":"ping"}'); }, 30000);
          agents.set(agentId, agentObj);
          if (!selectedAgentId) selectedAgentId = agentId;
          console.log('[agent:' + agentId + ']', si.hostname, si.user, 'admin=' + si.isAdmin, 'total=' + agents.size);
          notifySense('agent_status', { connected: true, hostname: si.hostname, user: si.user, os: si.os, isAdmin: si.isAdmin });
          notifySense('agents_list', { agents: getAgentList(), selected: selectedAgentId });
          notifySense('say', { level: 'alert-ok', text: '<b>Agent\u5df2\u8fde\u63a5</b> \u2014 ' + (si.hostname || '?') + ' / ' + (si.user || '?') + (si.isAdmin ? ' (\u7ba1\u7406\u5458)' : '') + ' [' + agents.size + '\u53f0]' });
          startHostsGuard(agentId);
          setTimeout(function() { if (agentObj.ws && agentObj.ws.readyState === 1) agentObj.ws.send('{"type":"get_sysinfo"}'); }, 2000);
          // Auto-check windsurf proxy configuration
          setTimeout(function() {
            var ag = agents.get(agentId);
            if (!ag || !ag.ws || ag.ws.readyState !== 1) return;
            var checkCmd = '$pp=& "$env:SystemRoot\\System32\\netsh.exe" interface portproxy show v4tov4 2>$null; $cert=Get-ChildItem Cert:\\LocalMachine\\Root -EA SilentlyContinue|?{$_.Thumbprint -eq "EE8978E69E0CFE3FBD6FFD7E511BE6337A2FC4F7"}; $hp=Get-Content "$env:SystemRoot\\System32\\drivers\\etc\\hosts" -EA SilentlyContinue; $lanMode=$hp|?{$_ -match "192\\.168.*windsurf"}; if($cert -and ($pp -match "18443" -or $lanMode)){"CONFIGURED"}else{"NOT_CONFIGURED"}';
            execOnAgent(checkCmd, 15000, agentId).then(function(r) {
              var out = (r.output || '').trim();
              var status = out === 'CONFIGURED' ? 'configured' : 'needed';
              console.log('[auto-check:' + agentId + '] windsurf proxy:', out);
              ag.data.wsConfig = status;
              notifySense('setup_status', { status: status, hostname: ag.data.hostname, agentId: agentId });
              notifySense('agents_list', { agents: getAgentList(), selected: selectedAgentId });
            }).catch(function(e) { console.log('[auto-check:' + agentId + '] error:', e.message); });
          }, 5000);
        }
        if (msg.type === 'cmd_result') {
          var p = pendingCommands.get(msg.id);
          if (p) { clearTimeout(p.timer); pendingCommands.delete(msg.id); p.resolve({ ok: msg.ok, output: msg.output, ms: msg.ms }); }
          console.log('[agent:' + (agentId||'?') + '] result:', msg.ok ? 'OK' : 'FAIL', (msg.output || '').substring(0, 80));
        }
        if (msg.type === 'sysinfo' && agentId) {
          var ag = agents.get(agentId); if (ag) { ag.data.sysinfo = msg; ag.data.lastUpdate = new Date().toISOString(); }
          if (agentId === selectedAgentId) notifySense('sysinfo', msg);
          console.log('[agent:' + agentId + '] sysinfo');
        }
        if (msg.type === 'pong' && agentId) { var ag2 = agents.get(agentId); if (ag2) ag2.data.lastPong = new Date().toISOString(); }
      } catch (e) { console.error('[agent] err:', e.message); }
    });
    ws.on('close', function() {
      console.log('[agent:' + (agentId||'?') + '] disconnected');
      if (agentId && agents.has(agentId)) {
        var ag = agents.get(agentId);
        if (ag.pingTimer) clearInterval(ag.pingTimer);
        stopHostsGuard(agentId);
        ag.data.connected = false; ag.ws = null;
        agents.delete(agentId);
        if (selectedAgentId === agentId) { selectedAgentId = null; getSelectedAgent(); }
        notifySense('agents_list', { agents: getAgentList(), selected: selectedAgentId });
        var nextAgent = getSelectedAgent();
        if (nextAgent) {
          notifySense('agent_status', { connected: true, hostname: nextAgent.data.hostname, user: nextAgent.data.user, os: nextAgent.data.os, isAdmin: nextAgent.data.isAdmin });
        } else {
          notifySense('agent_status', { connected: false });
          notifySense('say', { level: 'alert-warn', text: '<b>Agent\u5df2\u65ad\u5f00</b> \u2014 ' + (agentId || '?') + ' [\u5269\u4f59' + agents.size + '\u53f0]' });
        }
      }
    });
    return;
  }
});

// ==================== START ====================
server.listen(PORT, '0.0.0.0', function() {
  console.log('\n===== \u9053 \u00b7 \u8fdc\u7a0b\u4e2d\u67a2 v3.0 =====');
  console.log('\u4e94\u611f:  http://localhost:' + PORT);
  console.log('\u5916\u7f51:  ' + HTTP_PROTO + PUBLIC_URL);
  console.log('\u5bc6\u7801:  ' + AUTH_PASSWORD.substring(0, 3) + '***');
  console.log('AgentKey: ' + AUTH_AGENT_KEY);
  console.log('==========================\n');
});
