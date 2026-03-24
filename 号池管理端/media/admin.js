/**
 * 号池管理端 — 前端交互 (三模式: 本地/云端/混合)
 * Webview内运行, 通过postMessage与extension通信
 * 道法自然 · 水善利万物而不争
 */
(function () {
  const vscode = acquireVsCodeApi();
  let _mode = 'cloud';   // local | cloud | hybrid
  let _subTab = '';       // per-mode sub tab
  let _cache = {};
  let _machineCode = '';

  // ── API ──
  function send(command, data) { vscode.postMessage({ command, data }); }

  window.addEventListener('message', function (e) {
    var msg = e.data;
    if (!msg || !msg.command) return;
    if (msg.command.endsWith('_result')) {
      var key = msg.command.replace('_result', '');
      _cache[key] = msg.data;
      var d = msg.data;
      if (key === 'addPool') { toast(d && d.ok ? '✅ 已添加云池' : ('❌ 添加失败: ' + ((d && d.error) || '')), !(d && d.ok)); send('pools'); send('overview'); }
      if (key === 'removePool') { toast(d && d.ok ? '✅ 已删除' : ('❌ 删除失败: ' + ((d && d.error) || '')), !(d && d.ok)); send('pools'); send('overview'); }
      if (key === 'syncAccounts') { toast(d && d.ok ? '✅ 同步完成' : ('❌ 同步失败: ' + ((d && d.error) || '')), !(d && d.ok)); send('overview'); }
      if (key === 'revokeDevice') { toast(d && d.ok ? '✅ 设备已撤销' : ('❌ 撤销失败: ' + ((d && d.error) || '')), !(d && d.ok)); send('devices'); }
      if (key === 'confirmPayment') { toast(d && d.ok ? '✅ 支付已确认' : ('❌ 确认失败: ' + ((d && d.error) || '')), !(d && d.ok)); delete _cache._paymentsLoaded; delete _cache._cloudDevLoaded; send('overview'); }
      if (key === 'rejectPayment') { toast(d && d.ok ? '✅ 已拒绝订单' : ('❌ 拒绝失败: ' + ((d && d.error) || '')), !(d && d.ok)); delete _cache._paymentsLoaded; send('overview'); }
      if (key === 'confirmP2P') { toast(d && d.ok ? '✅ P2P订单已确认 +' + (d.w_credits_added || 0) + 'W' : ('❌ 确认失败: ' + ((d && d.error) || '')), !(d && d.ok)); delete _cache._paymentsLoaded; delete _cache._cloudDevLoaded; delete _cache._statsLoaded; send('overview'); }
      if (key === 'rejectP2P') { toast(d && d.ok ? '✅ P2P订单已拒绝' : ('❌ 拒绝失败: ' + ((d && d.error) || '')), !(d && d.ok)); delete _cache._paymentsLoaded; delete _cache._statsLoaded; send('overview'); }
      if (key === 'createP2P') { toast(d && d.ok ? '✅ 订单已创建: ' + (d.order_id || '') + ' ' + (d.w_credits || 0) + 'W' : ('❌ 创建失败: ' + ((d && d.error) || '')), !(d && d.ok)); delete _cache._paymentsLoaded; delete _cache._statsLoaded; send('overview'); }
      if (key === 'paymentStats') { if (d && d.ok) { _cache._paymentStatsData = d; render(); } }
      if (key === 'activateDevice') { toast(d && d.ok ? '✅ 激活成功' : ('❌ 激活失败: ' + ((d && d.error) || '')), !(d && d.ok)); send('cloudStatus'); }
      if (key === 'poolDetail') { if (d && d.ok) { _cache._poolDetailData = d; render(); } else { toast('加载失败: ' + ((d && d.error) || ''), true); } }
      if (key === 'poolAccounts') { if (d && d.ok) { _cache._poolAccountsData = d; render(); } }
      if (key === 'poolUsers') { if (d && d.ok) { _cache._poolUsersData = d; render(); } }
      if (key === 'poolPayments') { if (d && d.ok) { _cache._poolPaymentsData = d; render(); } }
      if (key === 'rateLimitStatus') { _cache.rateLimitStatus = d; render(); }
      if (key === 'rateLimitConfig') { toast(d && d.ok ? '✅ 配置已保存' : ('❌ 保存失败: ' + ((d && d.error) || '')), !(d && d.ok)); delete _cache._rlLoaded; send('rateLimitStatus'); }
      if (key === 'rateLimitClear') { toast(d && d.ok ? '✅ 冷却已清除' : ('❌ 清除失败: ' + ((d && d.error) || '')), !(d && d.ok)); delete _cache._rlLoaded; send('rateLimitStatus'); }
      if (key === 'rateLimitTrigger') { toast(d && d.ok ? '✅ 切换触发: ' + (d.action || '') : ('❌ 切换失败: ' + ((d && d.error) || '')), !(d && d.ok)); delete _cache._rlLoaded; send('rateLimitStatus'); }
      if (key === 'pushCreate') { toast(d && d.ok ? '✅ 推送已发送: ' + (d.directive_id || '') : ('❌ 推送失败: ' + ((d && d.error) || '')), !(d && d.ok)); delete _cache._pushLoaded; send('pushList'); }
      if (key === 'pushRevoke') { toast(d && d.ok ? '✅ 已撤销' : ('❌ 撤销失败: ' + ((d && d.error) || '')), !(d && d.ok)); delete _cache._pushLoaded; send('pushList'); }
      if (key === 'securityBlock') { toast(d && d.ok ? '✅ ' + (d.action || '') + ': ' + (d.ip || '') : ('❌ 操作失败: ' + ((d && d.error) || '')), !(d && d.ok)); delete _cache._threatsLoaded; send('securityEvents'); }
      render();
    }
  });

  // ── Mode Switch ──
  window.switchMode = function (mode) {
    _mode = mode;
    _subTab = '';
    delete _cache._paymentsLoaded;
    delete _cache._cloudDevLoaded;
    delete _cache._pushLoaded;
    delete _cache._threatsLoaded;
    delete _cache._usersLoaded;
    delete _cache._remoteDevLoaded;
    delete _cache._rlLoaded;
    delete _cache.rateLimitStatus;
    delete _cache._poolDetailView;
    delete _cache._poolDetailData;
    delete _cache._poolAccountsData;
    delete _cache._poolUsersData;
    delete _cache._poolPaymentsData;
    document.querySelectorAll('.mode-tab').forEach(function (t) {
      t.classList.toggle('active', t.getAttribute('data-mode') === mode);
    });
    loadMode();
    render();
  };

  window.refresh = function () { loadMode(); };

  window.switchSubTab = function (tab) {
    if (tab === 'payments') delete _cache._paymentsLoaded;
    if (tab === 'devices') delete _cache._cloudDevLoaded;
    _subTab = tab;
    render();
  };

  function loadMode() {
    send('overview');
    send('lanStatus');
    send('machineInfo');
    send('cloudStatus');
    send('pools');
    send('devices');
    send('audit');
  }

  // ── Render Dispatcher ──
  function render() {
    updateSummary();
    updateSecurityBar();
    renderModeIndicator();
    renderSubTabs();
    var el = document.getElementById('content');
    if (!el) return;
    switch (_mode) {
      case 'local': el.innerHTML = renderLocal(); break;
      case 'cloud': el.innerHTML = renderCloud(); break;
      case 'hybrid': el.innerHTML = renderHybrid(); break;
    }
  }

  // ── Summary Bar ──
  function updateSummary() {
    var ov = _cache.overview;
    var cs = _cache.cloudStatus;
    var dEl = document.getElementById('sum-d');
    var wEl = document.getElementById('sum-w');
    var metaEl = document.getElementById('pool-meta');
    var barEl = document.getElementById('pool-bar');
    if (!dEl) return;

    var dTotal = 0, wTotal = 0, totalAcct = 0, availAcct = 0, urgent = 0, expiring = 0;
    if (ov && ov.ok && ov.pools) {
      ov.pools.forEach(function (p) {
        if (p.ok && p.pool) {
          totalAcct += p.pool.total || 0;
          availAcct += p.pool.available || 0;
        }
      });
    }
    // Parse D/W from cloud status or overview
    if (cs && cs.ok) {
      dTotal = cs.d_percent || 0;
      wTotal = cs.w_percent || 0;
      urgent = cs.urgent || 0;
      expiring = cs.expiring || 0;
    }
    // Fallback: use pool data
    if (!dTotal && ov && ov.ok && ov.pools) {
      dTotal = 100; wTotal = 100; // defaults
    }

    dEl.textContent = 'D' + dTotal + '%';
    wEl.textContent = 'W' + wTotal + '%';

    var metaParts = [];
    metaParts.push('<b>' + availAcct + '</b>可用');
    metaParts.push('<b>' + totalAcct + '</b>总计');
    if (urgent) metaParts.push('<b style="color:var(--d2)">' + urgent + '</b>紧急(≤3d)');
    if (expiring) metaParts.push('<b style="color:var(--w2)">' + expiring + '</b>将到期');
    metaEl.innerHTML = metaParts.join(' &nbsp; ');

    barEl.innerHTML = '<div class="pool-bar-d" style="width:' + Math.min(dTotal, 100) + '%"></div>' +
      '<div class="pool-bar-w" style="width:' + Math.min(wTotal, 100) * 0.5 + '%"></div>';
  }

  function updateSecurityBar() {
    var lan = _cache.lanStatus;
    if (!lan) return;
    var ipEl = document.getElementById('lan-ip');
    var devEl = document.getElementById('devices-count');
    var sessEl = document.getElementById('sessions-count');
    var mcEl = document.getElementById('machine-short');
    if (ipEl) ipEl.textContent = 'IP:' + (lan.lanIp || '--');
    if (devEl) devEl.textContent = '设备:' + (lan.enrolledDevices || 0);
    if (sessEl) sessEl.textContent = '会话:' + (lan.activeSessions || 0);
    if (mcEl && lan.machineId) mcEl.textContent = lan.machineId;
    if (lan.machineId) _machineCode = lan.machineId;

    // Get full machine code from machineInfo
    var mi = _cache.machineInfo;
    if (mi && mi.ok && mi.fullMachineId) _machineCode = mi.fullMachineId;
  }

  // ── Mode Indicator ──
  function renderModeIndicator() {
    var el = document.getElementById('mode-indicator');
    if (!el) return;
    var colors = { cloud: 'var(--p)', local: 'var(--ok)', hybrid: 'var(--blue)' };
    var labels = { cloud: '云池管理 · 账号/用户/支付', local: '设备管理 · LAN设备/云池配置', hybrid: '安全审计 · 哈希链日志/安全状态' };
    var online = _cache.cloudStatus && _cache.cloudStatus.ok ? '在线' : '离线';
    var onlineColor = _cache.cloudStatus && _cache.cloudStatus.ok ? 'var(--ok)' : 'var(--d)';
    el.innerHTML = '<span class="mode-dot" style="background:' + colors[_mode] + '"></span>' +
      '<span style="color:' + colors[_mode] + '">' + labels[_mode] + '</span>' +
      (_mode !== 'local' ? '<span style="margin-left:auto;color:' + onlineColor + '">● ' + online + '</span>' : '');
  }

  // ── Sub Tabs ──
  function renderSubTabs() {
    var el = document.getElementById('sub-tabs');
    if (!el) return;
    var tabs = [];
    var colorCls = 'st-' + _mode;
    switch (_mode) {
      case 'cloud':
        tabs = [['accounts', '账号'], ['users', '用户'], ['payments', '支付'], ['devices', '云设备'], ['remote', '远程管理'], ['push', '推送'], ['ratelimit', '限流防护'], ['pools', '云池']];
        break;
      case 'local':
        tabs = [['landevices', 'LAN设备'], ['pools', '云池配置']];
        break;
      case 'hybrid':
        tabs = [['audit', '审计日志'], ['threats', '威胁'], ['security', '安全状态']];
        break;
    }
    if (!_subTab && tabs.length) _subTab = tabs[0][0];
    el.innerHTML = tabs.map(function (t) {
      return '<button class="sub-tab ' + colorCls + (t[0] === _subTab ? ' active' : '') +
        '" data-subtab="' + t[0] + '">' + t[1] + '</button>';
    }).join('');
  }

  // ══════════════════════════════════════
  //  LOCAL MODE — 本地模式
  // ══════════════════════════════════════
  function renderLocal() {
    switch (_subTab) {
      case 'landevices': return renderLocalDevices();
      case 'pools': return renderLocalPools();
      default: return renderLocalDevices();
    }
  }

  function renderLocalAccounts() {
    var ov = _cache.overview;
    if (!ov || !ov.ok) return loading(ov);
    var pools = ov.pools || [];
    var html = '';

    // Local D stats
    html += '<div class="card card-glow-local"><div class="card-title"><span class="icon">&#x1F4BB;</span> 本地D额度</div>';
    var totalD = 0, availD = 0;
    pools.forEach(function (p) {
      if (p.ok && p.pool) { totalD += p.pool.total || 0; availD += p.pool.available || 0; }
    });
    html += '<div class="grid">';
    html += stat(availD, '可用账号', 'c-ok');
    html += stat(totalD, '总账号', '');
    html += stat(totalD - availD, '已分配', 'c-w');
    html += '</div>';
    html += quotaBar('D额度', availD, totalD, 'quota-fill-d');
    html += '</div>';

    // Per-pool accounts
    pools.forEach(function (p) {
      var stBadge = p.ok ? '<span class="badge badge-online">online</span>' : '<span class="badge badge-offline">offline</span>';
      html += '<div class="card"><div class="card-title">' + esc(p.name) + ' ' + stBadge + '</div>';
      if (p.ok && p.pool) {
        html += '<div class="grid">';
        html += stat(p.pool.total, '账号', '');
        html += stat(p.pool.available, '可用', 'c-ok');
        html += stat(p.pool.allocated, '分配', 'c-w');
        html += '</div>';
      } else if (p.error) {
        html += '<div style="color:var(--d2);font-size:11px">' + esc(p.error) + '</div>';
      }
      html += '<div class="btn-group">';
      html += '<button class="btn btn-success btn-sm" data-action="viewPool" data-param="' + esc(p.id) + '">详情</button>';
      html += '<button class="btn btn-ghost btn-sm" data-action="syncPool" data-param="' + esc(p.id) + '">同步</button>';
      html += '</div></div>';
    });
    return html;
  }

  function renderLocalPools() {
    var d = _cache.pools;
    if (!d || !d.ok) return loading(d);
    var pools = d.pools || [];
    var html = '<div class="card card-glow-local">';
    html += '<div class="btn-group" style="margin-top:0;margin-bottom:8px"><button class="btn btn-success" data-action="addPool">+ 添加云池</button></div>';
    if (!pools.length) return html + '<div class="empty">尚无云池, 点击上方按钮添加</div></div>';
    html += '<table><tr><th>名称</th><th>URL</th><th>Admin</th><th>HMAC</th><th></th></tr>';
    pools.forEach(function (p) {
      html += '<tr><td>' + esc(p.name) + '</td><td style="font-size:10px;font-family:monospace">' + esc(p.url) + '</td>';
      html += '<td>' + (p.hasAdmin ? '&#x2705;' : '&#x274C;') + '</td>';
      html += '<td>' + (p.hasHmac ? '&#x2705;' : '&#x274C;') + '</td>';
      html += '<td><button class="btn btn-danger btn-sm" data-action="removePool" data-param="' + esc(p.id) + '">删除</button></td></tr>';
    });
    html += '</table></div>';
    return html;
  }

  function renderLocalDevices() {
    var devData = _cache.devices;
    if (!devData || !devData.ok) return loading(devData);
    var devs = devData.devices || [];
    var html = '<div class="card card-glow-local"><div class="card-title"><span class="icon">&#x1F4F1;</span> 已注册设备 (' + devs.length + ')</div>';
    html += '<table><tr><th>名称</th><th>指纹</th><th>IP</th><th>最后在线</th><th></th></tr>';
    devs.forEach(function (d) {
      html += '<tr><td>' + esc(d.name) + '</td>';
      html += '<td style="font-family:monospace;font-size:10px">' + esc((d.fingerprint || '').slice(0, 12)) + '...</td>';
      html += '<td>' + esc(d.ip) + '</td>';
      html += '<td style="font-size:10px">' + esc((d.lastSeen || '').slice(0, 16)) + '</td>';
      html += '<td><button class="btn btn-danger btn-sm" data-action="revokeDevice" data-param="' + esc(d.fingerprint) + '">撤销</button></td></tr>';
    });
    html += '</table></div>';
    return html;
  }

  function renderLocalAudit() {
    var d = _cache.audit;
    if (!d || !d.ok) return loading(d);
    var entries = d.entries || [];
    var html = '<div class="card card-glow-local"><div class="card-title"><span class="icon">&#x1F512;</span> 安全审计 (' + entries.length + ')</div>';
    html += '<table><tr><th>时间</th><th>动作</th><th>IP</th><th>详情</th></tr>';
    entries.slice().reverse().slice(0, 50).forEach(function (e) {
      var ac = e.action === 'BLOCK' || e.action === 'REJECT' ? 'var(--d2)' :
        e.action === 'ENROLL' || e.action === 'SESSION' ? 'var(--ok2)' : 'var(--t)';
      html += '<tr><td style="font-size:10px;white-space:nowrap">' + esc((e.ts || '').slice(11, 19)) + '</td>';
      html += '<td style="color:' + ac + ';font-weight:600">' + esc(e.action) + '</td>';
      html += '<td>' + esc(e.ip) + '</td>';
      html += '<td style="font-size:10px">' + esc(e.detail) + '</td></tr>';
    });
    html += '</table></div>';
    return html;
  }

  // ══════════════════════════════════════
  //  CLOUD MODE — 云端模式 (和而不同)
  // ══════════════════════════════════════
  function renderCloud() {
    switch (_subTab) {
      case 'accounts': return renderCloudAccounts();
      case 'users': return renderCloudUsers();
      case 'payments': return renderCloudPayments();
      case 'devices': return renderCloudDevices();
      case 'remote': return renderRemoteManagement();
      case 'push': return renderPushManagement();
      case 'ratelimit': return renderRateLimitGuard();
      case 'pools': return renderLocalPools();
      default: return renderCloudAccounts();
    }
  }

  function renderCloudAccounts() {
    // If a pool detail view is active, show it
    if (_cache._poolDetailView) return renderPoolDetail();

    var ov = _cache.overview;
    if (!ov || !ov.ok) return loading(ov);
    var pools = ov.pools || [];
    var html = '<div class="card card-glow-cloud"><div class="card-title"><span class="icon">&#x1F465;</span> 云端账号管理</div>';
    var totalAcct = 0, availAcct = 0;
    pools.forEach(function (p) {
      if (p.ok && p.pool) { totalAcct += p.pool.total || 0; availAcct += p.pool.available || 0; }
    });
    html += '<div class="grid">';
    html += stat(availAcct, '可用账号', 'c-ok');
    html += stat(totalAcct, '总账号', '');
    html += stat(totalAcct - availAcct, '已分配', 'c-w');
    html += '</div>';
    html += quotaBar('账号可用率', availAcct, totalAcct, 'quota-fill-d');
    pools.forEach(function (p) {
      var stBadge = p.ok ? '<span class="badge badge-online">online</span>' : '<span class="badge badge-offline">offline</span>';
      html += '<div class="card" style="margin-top:6px"><div class="card-title">' + esc(p.name) + ' ' + stBadge + '</div>';
      if (p.ok && p.pool) {
        html += '<div class="grid">';
        html += stat(p.pool.total, '账号', '');
        html += stat(p.pool.available, '可用', 'c-ok');
        html += stat(p.pool.allocated || 0, '分配', 'c-w');
        html += '</div>';
      } else if (p.error) {
        html += '<div style="color:var(--d2);font-size:11px">' + esc(p.error) + '</div>';
      }
      html += '<div class="btn-group"><button class="btn btn-success btn-sm" data-action="viewPool" data-param="' + esc(p.id) + '">详情</button>';
      html += '<button class="btn btn-ghost btn-sm" data-action="syncPool" data-param="' + esc(p.id) + '">同步</button></div></div>';
    });
    html += '</div>';
    return html;
  }

  function renderPoolDetail() {
    var pid = _cache._poolDetailView;
    var pd = _cache._poolDetailData;
    var pa = _cache._poolAccountsData;
    var pu = _cache._poolUsersData;
    var html = '<div class="card card-glow-cloud">';
    html += '<div class="btn-group" style="margin-top:0;margin-bottom:8px">';
    html += '<button class="btn btn-ghost btn-sm" data-action="backToList">← 返回列表</button></div>';

    // Pool overview
    if (pd && pd.ok && pd.pool) {
      var p = pd.pool;
      html += '<div class="card-title"><span class="icon">&#x2601;</span> ' + esc(p.name || '云池详情') + '</div>';
      html += '<div class="grid">';
      html += stat(p.total || 0, '总账号', '');
      html += stat(p.available || 0, '可用', 'c-ok');
      html += stat(p.allocated || 0, '已分配', 'c-w');
      if (p.urgent) html += stat(p.urgent, '紧急', 'c-d');
      if (p.expiring) html += stat(p.expiring, '将过期', 'c-gold');
      html += '</div>';
      html += quotaBar('可用率', p.available || 0, p.total || 1, 'quota-fill-d');
    } else if (!pd) {
      html += loading();
    } else {
      html += '<div class="empty">无法获取池详情</div>';
    }
    html += '</div>';

    // Accounts list
    html += '<div class="card card-glow-cloud"><div class="card-title"><span class="icon">&#x1F465;</span> 账号列表</div>';
    if (pa && pa.ok && pa.accounts && pa.accounts.length) {
      html += '<table><tr><th>#</th><th>邮箱</th><th>状态</th><th>D</th><th>W</th><th>到期</th></tr>';
      pa.accounts.forEach(function (a, i) {
        var stColor = a.status === 'available' ? 'var(--ok2)' : a.status === 'allocated' ? 'var(--w2)' : 'var(--m)';
        html += '<tr><td style="font-size:10px">' + (i + 1) + '</td>';
        html += '<td style="font-family:monospace;font-size:10px">' + esc((a.email || '').slice(0, 20)) + '</td>';
        html += '<td style="color:' + stColor + ';font-weight:600;font-size:10px">' + esc(a.status || '--') + '</td>';
        html += '<td style="color:var(--ok2);font-weight:700;font-size:10px">D' + (a.d_percent != null ? a.d_percent : '100') + '%</td>';
        html += '<td style="color:var(--p2);font-weight:700;font-size:10px">W' + (a.w_percent != null ? a.w_percent : '100') + '%</td>';
        html += '<td style="font-size:9px">' + esc((a.expires_at || a.trial_end || '').slice(0, 10)) + '</td></tr>';
      });
      html += '</table>';
    } else if (!pa) {
      html += loading();
    } else {
      html += '<div class="empty">无账号数据</div>';
    }
    html += '</div>';

    // Users for this pool
    html += '<div class="card card-glow-cloud"><div class="card-title"><span class="icon">&#x1F464;</span> 用户列表</div>';
    if (pu && pu.ok && pu.users && pu.users.length) {
      html += '<table><tr><th>设备</th><th>邮箱</th><th>D</th><th>W</th></tr>';
      pu.users.slice(0, 30).forEach(function (u) {
        html += '<tr><td style="font-family:monospace;font-size:9px">' + esc((u.device_id || u.hwid || '').slice(0, 12)) + '</td>';
        html += '<td style="font-size:10px">' + esc(u.email || u.current_email || '--') + '</td>';
        html += '<td style="color:var(--ok2);font-weight:700">' + (u.d_percent != null ? u.d_percent + '%' : '--') + '</td>';
        html += '<td style="color:var(--p2);font-weight:700">' + (u.w_percent != null ? u.w_percent + '%' : '--') + '</td></tr>';
      });
      html += '</table>';
    } else if (!pu) {
      html += loading();
    } else {
      html += '<div class="empty">无用户</div>';
    }
    html += '</div>';

    return html;
  }

  window.backToList = function () {
    delete _cache._poolDetailView;
    delete _cache._poolDetailData;
    delete _cache._poolAccountsData;
    delete _cache._poolUsersData;
    delete _cache._poolPaymentsData;
    render();
  };

  function renderCloudUsers() {
    var ov = _cache.overview;
    var cs = _cache.cloudStatus;
    var firstPoolId = null;
    if (ov && ov.ok && ov.pools) {
      ov.pools.forEach(function (p) { if (!firstPoolId && p.id) firstPoolId = p.id; });
    }
    if (firstPoolId && !_cache._usersLoaded) {
      _cache._usersLoaded = true;
      send('poolUsers', { poolId: firstPoolId });
    }
    var html = '<div class="card card-glow-cloud"><div class="card-title"><span class="icon">&#x1F464;</span> 用户管理</div>';
    if (cs && cs.ok) {
      html += '<div class="grid">';
      html += stat(cs.total_users || 0, '总用户', 'c-blue');
      html += stat(cs.active_users || 0, '活跃', 'c-ok');
      html += stat(cs.today_calls || 0, '今日调用', 'c-cyan');
      html += '</div>';
    }
    // Real user list
    var ud = _cache._poolUsersData;
    if (ud && ud.ok && ud.users && ud.users.length) {
      html += '<table style="margin-top:8px"><tr><th>设备ID</th><th>邮箱</th><th>D</th><th>W</th><th>最后心跳</th></tr>';
      ud.users.slice(0, 50).forEach(function (u) {
        html += '<tr><td style="font-family:monospace;font-size:9px">' + esc((u.device_id || u.hwid || '').slice(0, 12)) + '...</td>';
        html += '<td style="font-size:10px">' + esc(u.email || u.current_email || '--') + '</td>';
        html += '<td style="color:var(--ok2);font-weight:700">' + (u.d_percent != null ? u.d_percent + '%' : '--') + '</td>';
        html += '<td style="color:var(--p2);font-weight:700">' + (u.w_percent != null ? u.w_percent + '%' : '--') + '</td>';
        html += '<td style="font-size:9px">' + esc((u.last_heartbeat || u.last_seen || '').slice(0, 16)) + '</td></tr>';
      });
      html += '</table>';
    } else if (!ud) {
      html += loading();
    } else {
      html += '<div class="empty">暂无用户数据</div>';
    }
    html += '</div>';
    return html;
  }

  function renderCloudPayments() {
    var ov = _cache.overview;
    var firstPoolId = null;
    if (ov && ov.ok && ov.pools) {
      ov.pools.forEach(function (p) { if (!firstPoolId && p.id) firstPoolId = p.id; });
    }
    if (firstPoolId && !_cache._paymentsLoaded) {
      _cache._paymentsLoaded = true;
      send('cloudP2P', { poolId: firstPoolId });
    }
    if (firstPoolId && !_cache._statsLoaded) {
      _cache._statsLoaded = true;
      send('paymentStats', { poolId: firstPoolId });
    }
    var html = '';

    // Payment Stats Card
    var stats = _cache._paymentStatsData;
    if (stats && stats.ok) {
      var p = stats.p2p || {};
      var w = stats.w_pool || {};
      html += '<div class="card card-glow-cloud" style="border-left:3px solid var(--p)">';
      html += '<div class="card-title"><span class="icon">&#x1F4CA;</span> 支付统计</div>';
      html += '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;text-align:center">';
      html += '<div><div style="font-size:20px;font-weight:700;color:var(--ok2)">' + (p.confirmed || 0) + '</div><div style="color:var(--m);font-size:11px">已确认</div></div>';
      html += '<div><div style="font-size:20px;font-weight:700;color:var(--w2)">' + (p.pending || 0) + '</div><div style="color:var(--m);font-size:11px">待处理</div></div>';
      html += '<div><div style="font-size:20px;font-weight:700;color:var(--p2)">&yen;' + ((p.revenue_yuan || 0)).toFixed(2) + '</div><div style="color:var(--m);font-size:11px">总收入</div></div>';
      html += '<div><div style="font-size:20px;font-weight:700;color:var(--blue,#60a5fa)">' + (w.available || 0) + 'W</div><div style="color:var(--m);font-size:11px">W可用/' + (w.total || 0) + '</div></div>';
      html += '</div></div>';
    }

    // Create Order Card
    html += '<div class="card card-glow-cloud" style="border-left:3px solid var(--ok)">';
    html += '<div class="card-title"><span class="icon">&#x2795;</span> 创建订单</div>';
    html += '<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">';
    html += '<input id="p2p-device-id" type="text" placeholder="设备ID或HWID" style="flex:1;min-width:120px;padding:6px 10px;border-radius:6px;border:1px solid var(--b);background:var(--bg);color:var(--t);font-size:12px">';
    html += '<input id="p2p-w-credits" type="number" value="100" min="1" style="width:80px;padding:6px 10px;border-radius:6px;border:1px solid var(--b);background:var(--bg);color:var(--t);font-size:12px" placeholder="W积分">';
    html += '<select id="p2p-method" style="padding:6px 10px;border-radius:6px;border:1px solid var(--b);background:var(--bg);color:var(--t);font-size:12px"><option value="admin">管理员发放</option><option value="alipay">支付宝</option><option value="wechat">微信</option><option value="gift">赠送</option></select>';
    html += '<label style="display:flex;align-items:center;gap:4px;font-size:12px;color:var(--m)"><input id="p2p-auto-confirm" type="checkbox" checked>自动确认</label>';
    html += '<button class="btn btn-success btn-sm" onclick="createP2POrder()">创建</button>';
    html += '</div></div>';

    // Orders Table
    var p2p = _cache.cloudP2P;
    html += '<div class="card card-glow-cloud"><div class="card-title"><span class="icon">&#x1F4B2;</span> 支付订单</div>';
    if (p2p && p2p.ok && p2p.orders && p2p.orders.length) {
      html += '<table><tr><th>订单号</th><th>金额</th><th>W</th><th>方式</th><th>设备</th><th>状态</th><th>时间</th><th>操作</th></tr>';
      p2p.orders.forEach(function (o) {
        var sc = o.status === 'confirmed' ? 'var(--ok2)' : o.status === 'pending' ? 'var(--w2)' : o.status === 'rejected' ? 'var(--d)' : 'var(--m)';
        var statusLabel = o.status === 'confirmed' ? '已确认' : o.status === 'pending' ? '待确认' : o.status === 'rejected' ? '已拒绝' : esc(o.status);
        html += '<tr><td style="font-size:10px;font-family:monospace">' + esc(o.id || '') + '</td>';
        html += '<td>&yen;' + ((o.amount_cents || 0) / 100).toFixed(2) + '</td>';
        html += '<td style="color:var(--p2);font-weight:700">' + (o.w_credits || 0) + 'W</td>';
        html += '<td>' + esc(o.method || '') + '</td>';
        html += '<td style="font-size:10px;font-family:monospace">' + esc((o.device_id || '').slice(0, 12)) + '</td>';
        html += '<td style="color:' + sc + ';font-weight:600">' + statusLabel + '</td>';
        html += '<td style="font-size:10px;color:var(--m)">' + esc((o.created_at || '').slice(0, 16)) + '</td>';
        html += '<td>';
        if (o.status === 'pending') {
          html += '<button class="btn btn-success btn-sm" onclick="confirmP2POrder(\'' + esc(o.id) + '\',\'' + esc(firstPoolId || '') + '\')">确认</button> ';
          html += '<button class="btn btn-danger btn-sm" onclick="rejectP2POrder(\'' + esc(o.id) + '\',\'' + esc(firstPoolId || '') + '\')">拒绝</button>';
        } else if (o.status === 'confirmed') {
          html += '<span style="color:var(--ok2);font-size:11px">&#x2705;</span>';
        }
        html += '</td></tr>';
      });
      html += '</table>';
    } else {
      html += '<div class="empty">无支付记录</div>';
    }
    html += '</div>';
    return html;
  }

  function renderCloudInfo() {
    var cs = _cache.cloudStatus;
    var html = '';

    // W Resource overview
    html += '<div class="card card-glow-cloud">';
    html += '<div class="card-title"><span class="icon">&#x26A1;</span> W资源 · 和而不同</div>';
    html += '<div style="font-size:11px;color:var(--m);margin-bottom:10px">';
    html += '每位用户拥有独立的W额度空间, 和而不同 — 共享池资源, 独享个人配额</div>';

    if (cs && cs.ok) {
      html += '<div class="grid">';
      html += stat('W' + (cs.w_percent || 0) + '%', '池总W', 'c-p');
      html += stat((cs.w_available || 0) + '%', '可用W', 'c-ok');
      html += stat(cs.total_devices || 0, '激活设备', 'c-cyan');
      html += stat(cs.total_users || 0, '总用户', 'c-blue');
      html += '</div>';
      html += quotaBar('W额度', cs.w_available || 0, 100, 'quota-fill-w');
    } else {
      html += '<div class="empty">云端未连接, 请先添加云池</div>';
    }
    html += '</div>';

    // W info details
    html += '<div class="card card-glow-cloud">';
    html += '<div class="card-title"><span class="icon">&#x1F4CA;</span> W详细信息</div>';
    var info = [
      ['W配额模型', '用户级独立额度, 互不影响'],
      ['新用户赠送', '100% W免费额度'],
      ['消耗规则', '按调用量线性消耗'],
      ['刷新周期', '月度自动补充'],
      ['超额策略', '降速不停服'],
    ];
    if (cs && cs.ok) {
      info.push(['池总W值', 'W' + (cs.w_percent || 0) + '%']);
      info.push(['活跃用户', (cs.active_users || 0) + '人']);
      info.push(['今日调用', (cs.today_calls || 0) + '次']);
    }
    info.forEach(function (r) {
      html += '<div class="w-info-row"><span class="w-info-key">' + r[0] + '</span><span class="w-info-val">' + r[1] + '</span></div>';
    });
    html += '</div>';

    return html;
  }

  function renderCloudActivate() {
    var mi = _cache.machineInfo;
    var cs = _cache.cloudStatus;
    var html = '';

    // Machine code display
    html += '<div class="machine-box">';
    html += '<div class="machine-label">&#x1F5A5; 本机机器码</div>';
    var code = (mi && mi.ok && mi.fullMachineId) ? mi.fullMachineId : (_machineCode || '获取中...');
    html += '<div class="machine-code" data-action="copyMachineCode" title="\u70b9\u51fb\u590d\u5236">' + esc(code) + '</div>';
    html += '<div style="font-size:10px;color:var(--m)">点击复制 · 凭此机器码可远程直连本机</div>';
    html += '</div>';

    // Activation
    var isActivated = cs && cs.ok && cs.device_activated;
    html += '<div class="activate-box">';
    if (isActivated) {
      html += '<h3>&#x2705; 已激活</h3>';
      html += '<p>本机已激活云端W资源, 享有完整配额</p>';
      html += '<div class="grid">';
      html += stat('W' + (cs.my_w || 100) + '%', '我的W额度', 'c-p');
      html += stat((cs.my_w_used || 0) + '%', '已使用', 'c-w');
      html += stat((cs.my_w || 100) - (cs.my_w_used || 0) + '%', '剩余', 'c-ok');
      html += '</div>';
    } else {
      html += '<h3>&#x1F381; 新用户激活</h3>';
      html += '<p>激活后即可使用云端W资源, 新用户专享:</p>';
      html += '<div class="activate-bonus">100%<small> W免费额度</small></div>';
      html += '<button class="btn btn-gold btn-lg btn-block" data-action="activateDevice">';
      html += '&#x26A1; 立即激活</button>';
      html += '<div style="margin-top:8px;font-size:10px;color:var(--m)">激活将使用上方机器码注册到云端</div>';
    }
    html += '</div>';

    return html;
  }

  function renderCloudRemote() {
    var mi = _cache.machineInfo;
    var html = '';

    html += '<div class="remote-panel">';
    html += '<h3>&#x1F310; 公网远程直连</h3>';
    html += '<div style="font-size:11px;color:var(--m);margin-bottom:10px">';
    html += '通过机器码, 管理员可从公网直连到对应机器, 远程排查Windsurf配置问题</div>';

    // Machine code
    var code = (mi && mi.ok && mi.fullMachineId) ? mi.fullMachineId : (_machineCode || '--');
    html += '<div style="background:var(--bg);border-radius:8px;padding:10px;margin-bottom:10px">';
    html += '<div style="font-size:10px;color:var(--m);margin-bottom:4px">目标机器码</div>';
    html += '<div style="font-family:monospace;font-size:13px;color:var(--cyan2);word-break:break-all">' + esc(code) + '</div>';
    html += '</div>';

    // Remote connect input
    html += '<div style="margin-bottom:10px">';
    html += '<input id="remote-target" placeholder="输入目标机器码 (远程连接其他机器)" />';
    html += '<div class="btn-group" style="margin-top:4px">';
    html += '<button class="btn btn-blue" data-action="remoteConnect">&#x1F517; 连接</button>';
    html += '<button class="btn btn-ghost" data-action="remoteProbe">&#x1F50D; 探测</button>';
    html += '</div></div>';

    // Capabilities
    html += '<div style="font-size:11px;color:var(--m)">';
    html += '<div style="margin-bottom:4px;color:var(--t);font-weight:600">远程可执行操作:</div>';
    var caps = [
      '&#x2022; 查看/修复 Windsurf 配置文件',
      '&#x2022; 检查插件安装状态',
      '&#x2022; 重置账号绑定',
      '&#x2022; 清理缓存/日志',
      '&#x2022; 诊断网络连通性',
    ];
    html += caps.join('<br>');
    html += '</div>';

    html += '</div>';
    return html;
  }

  function renderCloudDevices() {
    var ov = _cache.overview;
    var firstPoolId = null;
    if (ov && ov.ok && ov.pools) {
      ov.pools.forEach(function (p) { if (!firstPoolId && p.id) firstPoolId = p.id; });
    }
    if (firstPoolId && !_cache._cloudDevLoaded) {
      _cache._cloudDevLoaded = true;
      send('cloudDevices', { poolId: firstPoolId });
      send('cloudP2P', { poolId: firstPoolId });
    }

    var cd = _cache.cloudDevices;
    var html = '';

    html += '<div class="card card-glow-cloud"><div class="card-title"><span class="icon">&#x2601;</span> 云端设备</div>';
    if (cd && cd.ok && cd.devices && cd.devices.length) {
      html += '<table><tr><th>ID</th><th>HWID</th><th>名称</th><th>W总</th><th>W可用</th></tr>';
      cd.devices.slice(0, 30).forEach(function (dv) {
        html += '<tr><td style="font-size:10px">' + esc(dv.id) + '</td>';
        html += '<td style="font-family:monospace;font-size:9px">' + esc((dv.hwid || '').slice(0, 12)) + '...</td>';
        html += '<td>' + esc(dv.name) + '</td>';
        html += '<td style="color:var(--p2);font-weight:700">' + (dv.w_total || 0) + '%</td>';
        html += '<td style="color:var(--ok2);font-weight:700">' + (dv.w_available || 0) + '%</td></tr>';
      });
      html += '</table>';
    } else {
      html += '<div class="empty">无云端设备</div>';
    }
    html += '</div>';

    // P2P orders
    var p2p = _cache.cloudP2P;
    if (p2p && p2p.ok && p2p.orders && p2p.orders.length) {
      html += '<div class="card card-glow-cloud"><div class="card-title"><span class="icon">&#x1F4B2;</span> P2P订单 (' + p2p.orders.length + ')</div>';
      html += '<table><tr><th>金额</th><th>W</th><th>方式</th><th>状态</th></tr>';
      p2p.orders.slice(0, 20).forEach(function (o) {
        var sc = o.status === 'confirmed' ? 'var(--ok2)' : o.status === 'pending' ? 'var(--w2)' : 'var(--m)';
        html += '<tr><td>¥' + ((o.amount_cents || 0) / 100).toFixed(2) + '</td>';
        html += '<td style="color:var(--p2);font-weight:700">' + (o.w_credits || 0) + 'W</td>';
        html += '<td>' + esc(o.method) + '</td>';
        html += '<td style="color:' + sc + ';font-weight:600">' + esc(o.status) + '</td></tr>';
      });
      html += '</table></div>';
    }

    return html;
  }

  // ══════════════════════════════════════
  //  HYBRID MODE — 混合模式
  // ══════════════════════════════════════
  function renderHybrid() {
    switch (_subTab) {
      case 'audit': return renderLocalAudit();
      case 'threats': return renderThreats();
      case 'security': return renderSecurityStatus();
      default: return renderLocalAudit();
    }
  }

  function renderSecurityStatus() {
    var lan = _cache.lanStatus;
    var mi = _cache.machineInfo;
    var html = '<div class="card card-glow-hybrid"><div class="card-title"><span class="icon">&#x1F6E1;</span> 安全状态</div>';
    if (lan) {
      html += '<div class="w-info-row"><span class="w-info-key">LAN IP</span><span class="w-info-val">' + esc(lan.lanIp || '--') + '</span></div>';
      html += '<div class="w-info-row"><span class="w-info-key">注册设备</span><span class="w-info-val">' + (lan.enrolledDevices || 0) + '</span></div>';
      html += '<div class="w-info-row"><span class="w-info-key">活跃会话</span><span class="w-info-val">' + (lan.activeSessions || 0) + '</span></div>';
    }
    if (mi && mi.ok) {
      html += '<div class="w-info-row"><span class="w-info-key">主机名</span><span class="w-info-val">' + esc(mi.hostname) + '</span></div>';
      html += '<div class="w-info-row"><span class="w-info-key">机器码</span><span class="w-info-val" style="font-family:monospace;font-size:10px">' + esc((mi.fullMachineId || '').slice(0, 16)) + '...</span></div>';
    }
    html += '</div>';
    return html;
  }

  function renderHybridQuota() {
    var cs = _cache.cloudStatus;
    var ov = _cache.overview;
    var html = '';

    // Dual quota display
    html += '<div class="card card-glow-hybrid">';
    html += '<div class="card-title"><span class="icon">&#x267E;</span> 双额度总览</div>';
    html += '<div style="font-size:11px;color:var(--m);margin-bottom:10px">';
    html += '水善利万物而不争 — 本地优先消耗, 云端自然兜底</div>';

    // Calculate local D
    var localTotal = 0, localAvail = 0;
    if (ov && ov.ok && ov.pools) {
      ov.pools.forEach(function (p) {
        if (p.ok && p.pool) { localTotal += p.pool.total || 0; localAvail += p.pool.available || 0; }
      });
    }
    var localPct = localTotal ? Math.round(localAvail / localTotal * 100) : 0;

    // Cloud W
    var cloudW = cs && cs.ok ? (cs.my_w || cs.w_available || 100) : 0;
    var cloudWUsed = cs && cs.ok ? (cs.my_w_used || 0) : 0;

    html += '<div class="dual-quota">';
    html += '<div class="dual-quota-half" style="border:1px solid rgba(16,185,129,.2)">';
    html += '<div class="dual-quota-val" style="color:var(--ok2)">D' + localPct + '%</div>';
    html += '<div class="dual-quota-label">本地额度</div>';
    html += '<div class="dual-quota-priority priority-active">&#x25B6; 优先消耗</div>';
    html += '</div>';

    html += '<div class="consumption-arrow">&#x2192;</div>';

    html += '<div class="dual-quota-half" style="border:1px solid rgba(124,58,237,.2)">';
    html += '<div class="dual-quota-val" style="color:var(--p2)">W' + (cloudW - cloudWUsed) + '%</div>';
    html += '<div class="dual-quota-label">云端额度</div>';
    html += '<div class="dual-quota-priority priority-standby">&#x23F8; 备用兜底</div>';
    html += '</div>';
    html += '</div>';

    // Combined bar
    html += '<div style="margin-bottom:6px">';
    html += '<div style="display:flex;justify-content:space-between;font-size:10px;margin-bottom:3px">';
    html += '<span style="color:var(--ok2)">D本地 ' + localPct + '%</span>';
    html += '<span style="color:var(--p2)">W云端 ' + (cloudW - cloudWUsed) + '%</span>';
    html += '</div>';
    html += '<div style="height:10px;border-radius:5px;background:var(--bg);overflow:hidden;display:flex">';
    html += '<div style="width:' + localPct * 0.6 + '%;background:linear-gradient(90deg,var(--ok),var(--ok2));border-radius:5px 0 0 5px"></div>';
    html += '<div style="width:2px;background:var(--b)"></div>';
    html += '<div style="width:' + (cloudW - cloudWUsed) * 0.4 + '%;background:linear-gradient(90deg,var(--p),var(--p2));border-radius:0 5px 5px 0"></div>';
    html += '</div>';
    html += '<div style="text-align:center;font-size:9px;color:var(--m);margin-top:3px">消耗方向: 本地D &#x27A1; 云端W</div>';
    html += '</div>';

    html += '</div>';

    // Consumption waterfall
    html += '<div class="card card-glow-hybrid">';
    html += '<div class="card-title"><span class="icon">&#x1F4A7;</span> 消耗瀑布流</div>';
    var steps = [
      { label: '1. 请求到达', color: 'var(--t)', desc: '用户发起API请求' },
      { label: '2. 检查本地D', color: 'var(--ok2)', desc: localAvail > 0 ? '本地有 ' + localAvail + ' 可用 → 消耗D' : '本地已耗尽 → 跳转云端' },
      { label: '3. 回退云端W', color: 'var(--p2)', desc: localAvail > 0 ? '暂不启用(本地充足)' : '消耗云端W额度' },
      { label: '4. 响应返回', color: 'var(--cyan2)', desc: '无感切换, 用户无感知' },
    ];
    steps.forEach(function (s) {
      html += '<div style="display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid rgba(255,255,255,.04)">';
      html += '<span style="color:' + s.color + ';font-weight:700;font-size:11px;white-space:nowrap">' + s.label + '</span>';
      html += '<span style="font-size:11px;color:var(--m)">' + s.desc + '</span>';
      html += '</div>';
    });
    html += '</div>';

    return html;
  }

  function renderHybridAccounts() {
    var ov = _cache.overview;
    if (!ov || !ov.ok) return loading(ov);
    var pools = ov.pools || [];
    var html = '';

    html += '<div class="card card-glow-hybrid"><div class="card-title"><span class="icon">&#x267E;</span> 混合账号池</div>';
    var idx = 0;
    pools.forEach(function (p) {
      if (!p.ok || !p.pool) return;
      html += '<div style="margin-bottom:6px;font-size:11px;color:var(--m);font-weight:600">' + esc(p.name) + '</div>';
      for (var i = 0; i < Math.min(p.pool.total || 0, 20); i++) {
        idx++;
        html += '<div class="acct-row">';
        html += '<span class="acct-idx">' + idx + '</span>';
        html += '<span class="acct-name">' + esc(p.name) + '_acct_' + i + '</span>';
        html += '<span class="acct-quota acct-d">D100%</span>';
        html += '<span class="acct-quota acct-w">·W100%</span>';
        html += '</div>';
      }
    });
    if (!idx) html += '<div class="empty">无账号</div>';
    html += '</div>';
    return html;
  }

  function renderHybridStrategy() {
    var html = '';
    html += '<div class="card card-glow-hybrid">';
    html += '<div class="card-title"><span class="icon">&#x2699;</span> 混合消耗策略</div>';

    var strategies = [
      { name: '本地优先 (推荐)', desc: '优先消耗本地D额度, 耗尽后自动切换云端W', active: true },
      { name: '云端优先', desc: '优先消耗云端W额度, 保留本地D作为备用', active: false },
      { name: '均衡分配', desc: '按比例同时消耗本地D和云端W', active: false },
      { name: '纯本地', desc: '仅消耗本地D, 不使用云端W', active: false },
    ];

    strategies.forEach(function (s) {
      html += '<div style="display:flex;align-items:center;gap:10px;padding:10px;margin-bottom:4px;';
      html += 'background:' + (s.active ? 'rgba(59,130,246,.1)' : 'var(--bg)') + ';';
      html += 'border:1px solid ' + (s.active ? 'rgba(59,130,246,.3)' : 'transparent') + ';';
      html += 'border-radius:8px;cursor:pointer" data-action="setStrategy" data-param="' + esc(s.name) + '">';
      html += '<div style="width:16px;height:16px;border-radius:50%;border:2px solid ' +
        (s.active ? 'var(--blue2)' : 'var(--b)') + ';display:flex;align-items:center;justify-content:center">';
      if (s.active) html += '<div style="width:8px;height:8px;border-radius:50%;background:var(--blue2)"></div>';
      html += '</div>';
      html += '<div><div style="font-weight:600;font-size:12px;color:' + (s.active ? 'var(--blue2)' : 'var(--t)') + '">' + s.name + '</div>';
      html += '<div style="font-size:10px;color:var(--m)">' + s.desc + '</div></div>';
      html += '</div>';
    });

    html += '</div>';

    // Explanation
    html += '<div class="card card-glow-hybrid">';
    html += '<div class="card-title"><span class="icon">&#x1F4D6;</span> 道法自然</div>';
    html += '<div style="font-size:11px;color:var(--m);line-height:1.7">';
    html += '水善利万物而不争, 处众人之所恶, 故几于道。<br><br>';
    html += '混合模式如水之性 — 本地资源如近水, 优先取用; 云端资源如远水, 自然兜底。';
    html += '不强求, 不浪费, 唯变所适。<br><br>';
    html += '当本地D额度充足时, 不消耗云端W; 当本地D耗尽, 云端W自然接续, 用户无感知切换。</div>';
    html += '</div>';

    return html;
  }

  // ══════════════════════════════════════
  //  REMOTE MANAGEMENT — 道之安全·远程管理
  // ══════════════════════════════════════
  function renderRemoteManagement() {
    if (!_cache._remoteDevLoaded) {
      _cache._remoteDevLoaded = true;
      send('remoteDevices');
    }
    var rd = _cache.remoteDevices;
    var mi = _cache.machineInfo;
    var html = '';

    // Header card
    html += '<div class="card card-glow-cloud">';
    html += '<div class="card-title"><span class="icon">&#x1F310;</span> 远程设备管理 · 道之安全</div>';
    html += '<div style="font-size:11px;color:var(--m);margin-bottom:10px">';
    html += '通过机器码远程管理使用此插件的电脑。<b style="color:var(--w2)">所有操作需客户端用户确认授权</b>，防止一切恶意访问。</div>';

    // Admin machine code
    var adminCode = (mi && mi.ok && mi.fullMachineId) ? mi.fullMachineId : (_machineCode || '--');
    html += '<div style="background:var(--bg);border-radius:8px;padding:8px;margin-bottom:10px">';
    html += '<div style="font-size:10px;color:var(--m);margin-bottom:2px">管理端机器码</div>';
    html += '<div style="font-family:monospace;font-size:11px;color:var(--cyan2);cursor:pointer" data-action="copyMachineCode">' + esc(adminCode) + '</div>';
    html += '</div>';

    // Security notice
    html += '<div style="background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.2);border-radius:8px;padding:10px;margin-bottom:10px">';
    html += '<div style="font-size:11px;color:var(--w2);font-weight:600;margin-bottom:4px">&#x1F6E1; 安全机制</div>';
    html += '<div style="font-size:10px;color:var(--m);line-height:1.6">';
    html += '&#x2022; 远程请求发送后，目标设备用户会收到<b>弹窗通知</b><br>';
    html += '&#x2022; 用户必须<b>明确点击允许</b>才会执行操作<br>';
    html += '&#x2022; 请求<b>5分钟</b>内未响应自动过期<br>';
    html += '&#x2022; 所有操作记入<b>审计日志</b>，不可篡改</div>';
    html += '</div></div>';

    // Remote request form
    html += '<div class="card card-glow-cloud">';
    html += '<div class="card-title"><span class="icon">&#x1F517;</span> 发起远程请求</div>';
    html += '<input id="remote-target-id" placeholder="输入目标设备机器码 (HWID)" style="margin-bottom:6px" />';
    html += '<select id="remote-action" style="margin-bottom:6px">';
    html += '<option value="diagnose">&#x1F50D; 诊断 — 检查Windsurf配置状态</option>';
    html += '<option value="config_check">&#x2699; 配置检查 — 查看配置文件</option>';
    html += '<option value="plugin_status">&#x1F4E6; 插件状态 — 检查安装版本</option>';
    html += '<option value="cache_clear">&#x1F9F9; 清理缓存 — 清除临时文件</option>';
    html += '<option value="network_test">&#x1F310; 网络测试 — 检查连通性</option>';
    html += '<option value="reset_binding">&#x1F504; 重置绑定 — 清除账号绑定</option>';
    html += '<option value="custom">&#x1F4DD; 自定义操作</option>';
    html += '</select>';
    html += '<textarea id="remote-payload" rows="2" placeholder=\'自定义数据 (JSON, 可选)\' style="display:none"></textarea>';
    html += '<div class="btn-group">';
    html += '<button class="btn btn-blue" data-action="sendRemoteRequest">&#x1F680; 发送请求</button>';
    html += '<button class="btn btn-ghost" data-action="refreshRemote">&#x1F504; 刷新</button>';
    html += '</div></div>';

    // Pending request status
    if (_cache._lastRemoteRequestId) {
      var rs = _cache.remoteStatus;
      html += '<div class="card card-glow-cloud">';
      html += '<div class="card-title"><span class="icon">&#x23F3;</span> 请求状态</div>';
      if (rs && rs.ok && rs.request) {
        var r = rs.request;
        var stColor = r.status === 'approved' ? 'var(--ok2)' : r.status === 'denied' ? 'var(--d2)' : 'var(--w2)';
        var stText = r.status === 'approved' ? '✅ 已授权' : r.status === 'denied' ? '❌ 已拒绝' : '⏳ 等待用户确认...';
        html += '<div style="display:flex;align-items:center;gap:10px;padding:10px;background:var(--bg);border-radius:8px">';
        html += '<div style="color:' + stColor + ';font-weight:700;font-size:14px">' + stText + '</div>';
        html += '</div>';
        if (r.status === 'pending') {
          html += '<div style="font-size:10px;color:var(--m);margin-top:6px">请求ID: ' + esc(r.id) + ' · 等待客户端用户授权中...</div>';
          html += '<div style="font-size:10px;color:var(--w2);margin-top:2px">提示: 目标设备的Windsurf会弹出授权对话框，用户需点击"允许"</div>';
        }
        if (r.response) {
          html += '<div style="font-size:10px;color:var(--m);margin-top:6px">';
          html += '响应时间: ' + new Date(r.response.respondedAt).toLocaleTimeString();
          if (r.response.reason) html += ' · 原因: ' + esc(r.response.reason);
          html += '</div>';
        }
      } else {
        html += '<div class="empty">查询中...</div>';
      }
      html += '</div>';
    }

    // Device list
    html += '<div class="card card-glow-cloud"><div class="card-title"><span class="icon">&#x1F4F1;</span> 可管理设备</div>';
    if (rd && rd.ok && rd.devices && rd.devices.length) {
      html += '<table><tr><th>名称</th><th>HWID</th><th>W可用</th><th>待审</th><th>操作</th></tr>';
      rd.devices.forEach(function (dv) {
        var hwid = dv.hwid || '';
        html += '<tr><td>' + esc(dv.name || '--') + '</td>';
        html += '<td style="font-family:monospace;font-size:9px;cursor:pointer" data-action="fillRemoteTarget" data-param="' + esc(hwid) + '">' + esc(hwid.slice(0, 12)) + '...</td>';
        html += '<td style="color:var(--ok2);font-weight:700">' + (dv.w_available || 0) + '%</td>';
        html += '<td>' + (dv.remotePending || 0) + '</td>';
        html += '<td><button class="btn btn-blue btn-sm" data-action="quickRemote" data-param="' + esc(hwid) + '">管理</button></td></tr>';
      });
      html += '</table>';
    } else if (rd && rd.ok) {
      html += '<div class="empty">暂无已激活设备</div>';
    } else {
      html += loading(rd);
    }
    html += '</div>';

    // Capabilities reference
    html += '<div class="card card-glow-cloud">';
    html += '<div class="card-title"><span class="icon">&#x1F4D6;</span> 远程操作说明</div>';
    html += '<div style="font-size:11px;color:var(--m);line-height:1.8">';
    html += '<b style="color:var(--t)">诊断</b> — 采集Windsurf版本、配置、插件状态等诊断信息<br>';
    html += '<b style="color:var(--t)">配置检查</b> — 读取并返回关键配置文件内容<br>';
    html += '<b style="color:var(--t)">插件状态</b> — 列出已安装插件及版本信息<br>';
    html += '<b style="color:var(--t)">清理缓存</b> — 清除临时文件和过期缓存<br>';
    html += '<b style="color:var(--t)">网络测试</b> — 测试到关键服务器的连通性<br>';
    html += '<b style="color:var(--t)">重置绑定</b> — 清除设备上的账号绑定状态<br>';
    html += '</div></div>';

    return html;
  }

  // ══════════════════════════════════════
  //  PUSH MANAGEMENT — 道之推·万法归宗
  // ══════════════════════════════════════
  function renderPushManagement() {
    if (!_cache._pushLoaded) {
      _cache._pushLoaded = true;
      send('pushList');
    }
    var pl = _cache.pushList;
    var html = '';

    // Create push directive
    html += '<div class="card card-glow-cloud push-card">';
    html += '<div class="card-title"><span class="icon">&#x1F4E1;</span> 云端推送管理</div>';
    html += '<div style="font-size:11px;color:var(--m);margin-bottom:10px">';
    html += '一推到底 · 向所有已安装插件的公网用户推送管理指令</div>';

    // Quick push buttons
    html += '<div class="push-quick">';
    html += '<button class="btn btn-primary btn-sm" data-action="quickPush" data-param="force_refresh">&#x1F504; 强制刷新</button>';
    html += '<button class="btn btn-blue btn-sm" data-action="quickPush" data-param="announcement">&#x1F4E2; 公告</button>';
    html += '<button class="btn btn-success btn-sm" data-action="quickPush" data-param="config_update">&#x2699; 配置更新</button>';
    html += '<button class="btn btn-gold btn-sm" data-action="quickPush" data-param="security_patch">&#x1F6E1; 安全补丁</button>';
    html += '<button class="btn btn-danger btn-sm" data-action="quickPush" data-param="kill_switch">&#x26D4; 紧急停止</button>';
    html += '</div>';

    // Custom push form
    html += '<div class="push-form" id="push-form" style="display:none">';
    html += '<select id="push-type"><option value="config_update">配置更新</option>';
    html += '<option value="announcement">公告通知</option>';
    html += '<option value="force_refresh">强制刷新</option>';
    html += '<option value="version_gate">版本门控</option>';
    html += '<option value="security_patch">安全补丁</option>';
    html += '<option value="kill_switch">紧急停止</option>';
    html += '<option value="custom">自定义</option></select>';
    html += '<input id="push-target" placeholder="目标: all / 设备ID / version:1.0.0" value="all" />';
    html += '<textarea id="push-payload" rows="3" placeholder=\'{"message":"推送内容","key":"value"}\'></textarea>';
    html += '<select id="push-priority"><option value="normal">普通</option>';
    html += '<option value="high">高优先</option>';
    html += '<option value="critical">紧急</option></select>';
    html += '<input id="push-ttl" type="number" value="24" placeholder="有效期(小时)" />';
    html += '<div class="btn-group">';
    html += '<button class="btn btn-primary" data-action="submitPush">&#x1F680; 发送推送</button>';
    html += '<button class="btn btn-ghost" data-action="cancelPush">取消</button>';
    html += '</div></div>';
    html += '</div>';

    // Active directives
    html += '<div class="card card-glow-cloud">';
    html += '<div class="card-title"><span class="icon">&#x1F4CB;</span> 活跃推送指令';
    if (pl && pl.ok) html += ' <span class="badge badge-info">' + (pl.active_count || 0) + ' 活跃</span>';
    html += '</div>';
    if (pl && pl.ok && pl.directives && pl.directives.length) {
      html += '<table><tr><th>ID</th><th>类型</th><th>目标</th><th>优先</th><th>送达</th><th>状态</th><th></th></tr>';
      pl.directives.forEach(function (d) {
        var stColor = d.active ? 'var(--ok2)' : d.revoked ? 'var(--d2)' : 'var(--m)';
        var stText = d.active ? '活跃' : d.revoked ? '已撤销' : '已过期';
        var prColor = d.priority === 'critical' ? 'var(--d2)' : d.priority === 'high' ? 'var(--w2)' : 'var(--m)';
        html += '<tr><td style="font-family:monospace;font-size:9px">' + esc((d.id || '').slice(0, 12)) + '</td>';
        html += '<td><span class="badge badge-info">' + esc(d.type) + '</span></td>';
        html += '<td style="font-size:10px">' + esc(d.target) + '</td>';
        html += '<td style="color:' + prColor + ';font-weight:600;font-size:10px">' + esc(d.priority) + '</td>';
        html += '<td style="font-size:10px">' + (d.acked_count || 0) + '</td>';
        html += '<td style="color:' + stColor + ';font-weight:600;font-size:10px">' + stText + '</td>';
        html += '<td>';
        if (d.active) html += '<button class="btn btn-danger btn-sm" data-action="revokePush" data-param="' + esc(d.id) + '">撤销</button>';
        html += '</td></tr>';
      });
      html += '</table>';
    } else if (pl && pl.ok) {
      html += '<div class="empty">暂无推送指令</div>';
    } else {
      html += loading(pl);
    }
    html += '</div>';

    // Push stats
    html += '<div class="card card-glow-cloud">';
    html += '<div class="card-title"><span class="icon">&#x1F4CA;</span> 推送统计</div>';
    var totalPush = pl && pl.ok ? (pl.total || 0) : 0;
    var activePush = pl && pl.ok ? (pl.active_count || 0) : 0;
    var totalAcked = 0;
    if (pl && pl.ok && pl.directives) {
      pl.directives.forEach(function (d) { totalAcked += d.acked_count || 0; });
    }
    html += '<div class="grid">';
    html += stat(totalPush, '总指令', 'c-blue');
    html += stat(activePush, '活跃', 'c-ok');
    html += stat(totalAcked, '总送达', 'c-cyan');
    html += '</div>';
    html += '<div style="margin-top:8px;font-size:10px;color:var(--m)">';
    html += '推送通过心跳机制自动分发 · 所有用户下次心跳即收到指令</div>';
    html += '</div>';

    return html;
  }



  // ══════════════════════════════════════
  //  RATE LIMIT GUARD — 道之防·限流防护
  // ══════════════════════════════════════
  function renderRateLimitGuard() {
    if (!_cache._rlLoaded) {
      _cache._rlLoaded = true;
      send('rateLimitStatus');
    }
    var rl = _cache.rateLimitStatus;
    var cfg = rl && rl.config ? rl.config : {};
    var stats = rl && rl.stats ? rl.stats : {};
    var cooling = rl && rl.cooling ? rl.cooling : [];
    var events = rl && rl.events ? rl.events : [];
    var html = '';

    html += '<div class="card card-glow-cloud">';
    html += '<div class="card-title"><span class="icon">&#x26A1;</span> \u9650\u6d41\u9632\u62a4 \u00b7 \u9053\u6cd5\u81ea\u7136</div>';
    html += '<div style="font-size:11px;color:var(--m);margin-bottom:10px">Rate Limit\u51fa\u73b0\u65f6\u81ea\u52a8\u5207\u6362\u8d26\u53f7\uff0c\u4ece\u6839\u672c\u4e0a\u6d88\u9664\u7b49\u5f85</div>';
    if (rl && rl.ok) {
      html += '<div class="grid">';
      html += stat(stats.total24h || 0, '24h\u9650\u6d41', 'c-d');
      html += stat(stats.autoSwitched || 0, '\u81ea\u52a8\u5207\u6362', 'c-ok');
      html += stat(stats.switchFailed || 0, '\u5207\u6362\u5931\u8d25', 'c-w');
      html += stat(cooling.length || 0, '\u51b7\u5374\u4e2d', 'c-p');
      html += '</div>';
    }
    var guardOn = cfg.autoSwitch !== false;
    html += '<div style="display:flex;align-items:center;gap:12px;padding:10px;background:var(--bg);border-radius:8px;margin-top:8px">';
    html += '<div style="flex:1"><div style="font-weight:600;font-size:12px">\u81ea\u52a8\u5207\u6362\u9632\u62a4</div>';
    html += '<div style="font-size:10px;color:var(--m)">\u68c0\u6d4b\u5230Rate Limit\u7acb\u5373\u5207\u6362\u65b0\u8d26\u53f7\uff0c\u62d2\u7edd\u7b49\u5f851\u5c0f\u65f6</div></div>';
    html += '<button class="btn btn-' + (guardOn ? 'danger' : 'success') + ' btn-sm" data-action="rlToggleAutoSwitch" data-param="' + (guardOn ? '0' : '1') + '">';
    html += guardOn ? '&#x2705; \u5df2\u5f00\u542f' : '&#x25B6; \u5df2\u5173\u95ed';
    html += '</button></div></div>';

    html += '<div class="card card-glow-cloud">';
    html += '<div class="card-title"><span class="icon">&#x2699;</span> \u9632\u62a4\u914d\u7f6e</div>';
    html += '<div style="display:flex;gap:10px;align-items:flex-end;flex-wrap:wrap">';
    html += '<div style="flex:1;min-width:120px"><div style="font-size:10px;color:var(--m);margin-bottom:3px">\u51b7\u5374\u65f6\u957f (\u5206\u949f)</div>';
    html += '<input id="rl-cooldown" type="number" value="' + (cfg.cooldownMinutes || 65) + '" min="10" max="1440" /></div>';
    html += '<div style="flex:1;min-width:120px"><div style="font-size:10px;color:var(--m);margin-bottom:3px">\u9884\u8b66\u9608\u503c (D%\u5269\u4f59\u4f4e\u4e8e\u6b64\u5207\u6362)</div>';
    html += '<input id="rl-threshold" type="number" value="' + (cfg.preemptThreshold || 85) + '" min="10" max="100" /></div>';
    html += '<button class="btn btn-primary btn-sm" data-action="rlSaveConfig">\u4fdd\u5b58</button>';
    html += '</div></div>';

    if (cooling.length > 0) {
      html += '<div class="card card-glow-cloud">';
      html += '<div class="card-title"><span class="icon">&#x2744;</span> \u51b7\u5374\u4e2d\u8d26\u53f7 (' + cooling.length + ')</div>';
      html += '<table><tr><th>\u90ae\u7b71</th><th>\u89e6\u53d1</th><th>\u5269\u4f59</th><th>\u6b21\u6570</th><th></th></tr>';
      cooling.forEach(function (ac) {
        html += '<tr><td style="font-family:monospace;font-size:10px">' + esc(ac.email || '--') + '</td>';
        html += '<td style="font-size:9px">' + esc((ac.hitAt || '').slice(11, 19)) + '</td>';
        html += '<td style="color:var(--w2);font-weight:700">' + ac.remainingMin + 'min</td>';
        html += '<td style="color:var(--d2)">\xd7' + (ac.hitCount || 1) + '</td>';
        html += '<td><button class="btn btn-ghost btn-sm" data-action="rlClearCooldown" data-param="' + esc(ac.email) + '">\u89e3\u9664</button></td></tr>';
      });
      html += '</table>';
      html += '<div class="btn-group" style="margin-top:6px">';
      html += '<button class="btn btn-danger btn-sm" data-action="rlClearCooldown" data-param="all">\u6e05\u9664\u5168\u90e8\u51b7\u5374</button></div></div>';
    }

    html += '<div class="card card-glow-cloud">';
    html += '<div class="card-title"><span class="icon">&#x1F504;</span> \u624b\u52a8\u89e6\u53d1\u5207\u6362</div>';
    html += '<div style="font-size:11px;color:var(--m);margin-bottom:8px">\u5f53\u524d\u8d26\u53f7\u89e6\u53d1\u9650\u6d41\u4f46\u672a\u81ea\u52a8\u4e0a\u62a5\u65f6\uff0c\u624b\u52a8\u5f3a\u5236\u5207\u6362</div>';
    html += '<input id="rl-email" placeholder="\u89e6\u53d1\u9650\u6d41\u7684\u8d26\u53f7\u90ae\u7b71 (\u53ef\u7559\u7a7a)" />';
    html += '<div class="btn-group" style="margin-top:6px">';
    html += '<button class="btn btn-gold" data-action="rlManualSwitch">&#x26A1; \u7acb\u5373\u5207\u6362\u8d26\u53f7</button>';
    html += '<button class="btn btn-ghost btn-sm" data-action="rlRefresh">&#x1F504; \u5237\u65b0\u72b6\u6001</button></div></div>';

    html += '<div class="card card-glow-cloud">';
    html += '<div class="card-title"><span class="icon">&#x1F4DC;</span> \u9650\u6d41\u4e8b\u4ef6\u65e5\u5fd7</div>';
    if (events.length > 0) {
      html += '<table><tr><th>\u65f6\u95f4</th><th>\u8d26\u53f7</th><th>\u8bbe\u5907</th><th>\u7ed3\u679c</th><th>D%</th></tr>';
      events.slice(0, 30).forEach(function (ev) {
        var ac = ev.action === 'auto_switched' ? 'var(--ok2)' : ev.action === 'switch_failed' ? 'var(--d2)' : 'var(--m)';
        var label = ev.action === 'auto_switched' ? '&#x2705;\u5df2\u5207\u6362' : ev.action === 'switch_failed' ? '&#x274C;\u5207\u6362\u5931\u8d25' : '&#x23FA;\u8bb0\u5f55';
        html += '<tr><td style="font-size:9px;white-space:nowrap">' + esc((ev.ts || '').slice(11, 19)) + '</td>';
        html += '<td style="font-family:monospace;font-size:9px">' + esc((ev.email || '').slice(0, 20)) + '</td>';
        html += '<td style="font-family:monospace;font-size:9px">' + esc((ev.deviceId || '').slice(0, 10)) + '</td>';
        html += '<td style="color:' + ac + ';font-weight:600;font-size:10px">' + label + '</td>';
        html += '<td style="color:var(--ok2)">' + (ev.dPercent || 0) + '%</td></tr>';
      });
      html += '</table>';
    } else if (!rl) {
      html += loading(rl);
    } else {
      html += '<div class="empty">\u6682\u65e0\u9650\u6d41\u4e8b\u4ef6 \u2014 \u9632\u62a4\u6b63\u5e38\u8fd0\u884c\u4e2d</div>';
    }
    html += '</div>';
    return html;
  }

  // ══════════════════════════════════════
  //  THREATS — 道之防·威胁情报
  // ══════════════════════════════════════
  function renderThreats() {
    if (!_cache._threatsLoaded) {
      _cache._threatsLoaded = true;
      send('securityEvents');
    }
    var se = _cache.securityEvents;
    var html = '';

    // Threat stats
    html += '<div class="card card-glow-hybrid">';
    html += '<div class="card-title"><span class="icon">&#x1F6E1;</span> 威胁情报中心</div>';
    if (se && se.ok && se.stats) {
      html += '<div class="grid">';
      html += stat(se.stats.total_events || 0, '总事件', 'c-blue');
      html += stat(se.stats.critical || 0, '严重', 'c-d');
      html += stat(se.stats.high || 0, '高危', 'c-w');
      html += stat(se.stats.warn || 0, '警告', 'c-gold');
      html += stat(se.stats.blocked_ips || 0, '封禁IP', 'c-d');
      html += '</div>';
    }
    html += '</div>';

    // Blocked IPs
    if (se && se.ok && se.bad_ips && se.bad_ips.length) {
      html += '<div class="card card-glow-hybrid">';
      html += '<div class="card-title"><span class="icon">&#x1F6AB;</span> 低信誉IP (' + se.bad_ips.length + ')</div>';
      html += '<table><tr><th>IP</th><th>信誉</th><th>请求数</th><th>封禁次</th><th></th></tr>';
      se.bad_ips.forEach(function (ip) {
        var scoreColor = ip.score <= 10 ? 'var(--d2)' : ip.score <= 30 ? 'var(--w2)' : 'var(--m)';
        html += '<tr><td style="font-family:monospace;font-size:11px">' + esc(ip.ip) + '</td>';
        html += '<td style="color:' + scoreColor + ';font-weight:700">' + ip.score + '</td>';
        html += '<td>' + (ip.total_requests || 0) + '</td>';
        html += '<td>' + (ip.blocked_count || 0) + '</td>';
        html += '<td>';
        if (ip.score <= 0 && (ip.tags || '').indexOf('manual') >= 0) {
          html += '<button class="btn btn-ghost btn-sm" data-action="unblockIp" data-param="' + esc(ip.ip) + '">解封</button>';
        } else {
          html += '<button class="btn btn-danger btn-sm" data-action="blockIp" data-param="' + esc(ip.ip) + '">封禁</button>';
        }
        html += '</td></tr>';
      });
      html += '</table></div>';
    }

    // Manual block
    html += '<div class="card card-glow-hybrid">';
    html += '<div class="card-title"><span class="icon">&#x1F512;</span> IP管控</div>';
    html += '<input id="block-ip" placeholder="输入要封禁/解封的IP地址" />';
    html += '<div class="btn-group">';
    html += '<button class="btn btn-danger btn-sm" data-action="blockIpManual">&#x26D4; 封禁</button>';
    html += '<button class="btn btn-success btn-sm" data-action="unblockIpManual">&#x2705; 解封</button>';
    html += '</div></div>';

    // Recent events
    html += '<div class="card card-glow-hybrid">';
    html += '<div class="card-title"><span class="icon">&#x1F4DC;</span> 最近安全事件</div>';
    if (se && se.ok && se.events && se.events.length) {
      html += '<table><tr><th>时间</th><th>类型</th><th>级别</th><th>IP</th><th>详情</th></tr>';
      se.events.slice(0, 30).forEach(function (ev) {
        var sevColor = ev.severity === 'critical' ? 'var(--d2)' :
          ev.severity === 'high' ? 'var(--w2)' :
          ev.severity === 'warn' ? 'var(--gold2)' : 'var(--m)';
        html += '<tr><td style="font-size:9px;white-space:nowrap">' + esc((ev.created_at || '').slice(11, 19)) + '</td>';
        html += '<td style="font-size:10px">' + esc(ev.event_type) + '</td>';
        html += '<td style="color:' + sevColor + ';font-weight:600;font-size:10px">' + esc(ev.severity) + '</td>';
        html += '<td style="font-family:monospace;font-size:9px">' + esc(ev.ip) + '</td>';
        html += '<td style="font-size:9px;max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + esc(ev.detail) + '</td></tr>';
      });
      html += '</table>';
    } else {
      html += '<div class="empty">暂无安全事件</div>';
    }
    html += '</div>';

    return html;
  }

  // ══════════════════════════════════════
  //  Actions
  // ══════════════════════════════════════
  window.addPool = function () {
    var el = document.getElementById('content');
    if (!el) return;
    el.innerHTML = '<div class="card card-glow-local">' +
      '<div class="card-title"><span class="icon">&#x2601;</span> 添加云池</div>' +
      '<input id="np-name" placeholder="云池名称 (例: 阿里云主池)" />' +
      '<input id="np-url" placeholder="云池URL (https://...)" />' +
      '<input id="np-key" placeholder="Admin Key 半密钥 (可留空)" type="password" />' +
      '<input id="np-hmac" placeholder="HMAC Secret (可留空)" type="password" />' +
      '<div class="btn-group">' +
      '<button class="btn btn-success" data-action="submitAddPool">&#x2713; 确认添加</button>' +
      '<button class="btn btn-ghost" data-action="cancelAddPool">取消</button>' +
      '</div></div>';
  };
  window.submitAddPool = function () {
    var name = (document.getElementById('np-name') || {}).value || '';
    var url = (document.getElementById('np-url') || {}).value || '';
    var key = (document.getElementById('np-key') || {}).value || '';
    var hmac = (document.getElementById('np-hmac') || {}).value || '';
    name = name.trim(); url = url.trim();
    if (!name || !url) { toast('名称和URL为必填项'); return; }
    send('addPool', { name: name, url: url, adminKeyHalf: key, hmacSecret: hmac });
    toast('正在添加: ' + name);
    render();
  };
  window.cancelAddPool = function () { render(); };
  window.removePool = function (id) {
    if (!confirm('❗ 确认删除该云池？\n删除后需重新添加才能恢复连接。')) return;
    send('removePool', { poolId: id }); toast('删除中...');
  };
  window.viewPool = function (id) {
    _cache._poolDetailView = id;
    delete _cache._poolDetailData;
    delete _cache._poolAccountsData;
    delete _cache._poolUsersData;
    delete _cache._poolPaymentsData;
    send('poolDetail', { poolId: id });
    send('poolAccounts', { poolId: id });
    send('poolUsers', { poolId: id });
    render();
  };
  window.syncPool = function (id) { send('syncAccounts', { poolId: id }); toast('同步中...'); };
  window.revokeDevice = function (fp) {
    if (!confirm('❗ 确认撤销该设备？\n撤销后该设备将无法访问管理端。')) return;
    send('revokeDevice', { fingerprint: fp }); toast('撤销中...');
  };
  window.confirmPayment = function (id, poolId) { send('confirmPayment', { paymentId: id, poolId: poolId || '' }); toast('确认中...'); };
  window.rejectPayment = function (id, poolId) { send('rejectPayment', { paymentId: id, poolId: poolId || '' }); toast('拒绝中...'); };
  window.confirmP2POrder = function (id, poolId) {
    if (!confirm('确认此P2P订单？将自动充值W积分到对应设备。')) return;
    send('confirmP2P', { orderId: id, poolId: poolId || '' }); toast('确认中...');
  };
  window.rejectP2POrder = function (id, poolId) {
    if (!confirm('拒绝此P2P订单？')) return;
    send('rejectP2P', { orderId: id, poolId: poolId || '' }); toast('拒绝中...');
  };
  window.createP2POrder = function () {
    var deviceId = (document.getElementById('p2p-device-id') || {}).value || '';
    var wCredits = parseInt((document.getElementById('p2p-w-credits') || {}).value || '100', 10);
    var method = (document.getElementById('p2p-method') || {}).value || 'admin';
    var autoConfirm = (document.getElementById('p2p-auto-confirm') || {}).checked;
    if (!deviceId) { toast('请输入设备ID', true); return; }
    if (wCredits < 1) { toast('W积分必须大于0', true); return; }
    var ov = _cache.overview;
    var poolId = '';
    if (ov && ov.ok && ov.pools) { ov.pools.forEach(function (p) { if (!poolId && p.id) poolId = p.id; }); }
    send('createP2P', { device_id: deviceId, w_credits: wCredits, method: method, auto_confirm: autoConfirm, poolId: poolId });
    toast('创建中...');
  };

  window.activateDevice = function () {
    send('activateDevice', { machineCode: _machineCode });
  };

  window.copyMachineCode = function () {
    var code = _machineCode || '';
    if (!code) return;
    // Use clipboard fallback
    var ta = document.createElement('textarea');
    ta.value = code; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select();
    try { document.execCommand('copy'); toast('已复制机器码'); } catch (e) { /* */ }
    document.body.removeChild(ta);
  };

  window.remoteConnect = function () {
    var input = document.getElementById('remote-target');
    var target = input ? input.value.trim() : '';
    if (!target) { toast('请输入目标机器码'); return; }
    send('remoteConnect', { targetMachineCode: target });
    toast('正在连接...');
  };

  window.remoteProbe = function () {
    var input = document.getElementById('remote-target');
    var target = input ? input.value.trim() : '';
    if (!target) { toast('请输入目标机器码'); return; }
    send('remoteProbe', { targetMachineCode: target });
    toast('正在探测...');
  };

  window.setStrategy = function (name) {
    send('setStrategy', { strategy: name });
    toast('策略已设置: ' + name);
  };

  // ── Remote Management Actions ──
  window.sendRemoteRequest = function () {
    var target = (document.getElementById('remote-target-id') || {}).value || '';
    var action = (document.getElementById('remote-action') || {}).value || 'diagnose';
    if (!target.trim()) { toast('请输入目标设备机器码', true); return; }
    var payloadStr = (document.getElementById('remote-payload') || {}).value || '{}';
    var payload;
    try { payload = payloadStr.trim() ? JSON.parse(payloadStr) : {}; } catch (e) { payload = {}; }
    send('remoteRequest', { targetDeviceId: target.trim(), action: action, payload: payload });
    toast('正在发送远程请求...');
  };
  window.refreshRemote = function () {
    delete _cache._remoteDevLoaded;
    delete _cache.remoteDevices;
    send('remoteDevices');
    if (_cache._lastRemoteRequestId) {
      send('remoteStatus', { requestId: _cache._lastRemoteRequestId });
    }
    render();
  };
  window.fillRemoteTarget = function (hwid) {
    var el = document.getElementById('remote-target-id');
    if (el) el.value = hwid;
    toast('已填入机器码');
  };
  window.quickRemote = function (hwid) {
    var el = document.getElementById('remote-target-id');
    if (el) el.value = hwid;
    toast('已选择设备, 选择操作后点击发送');
  };

  // ── Push Actions ──
  window.quickPush = function (type) {
    if (type === 'kill_switch') {
      if (!confirm('⚠️ 紧急停止将影响所有用户！\n确认发送紧急停止指令？')) return;
    }
    var form = document.getElementById('push-form');
    if (form) {
      form.style.display = 'block';
      var typeEl = document.getElementById('push-type');
      if (typeEl) typeEl.value = type;
      var payloadEl = document.getElementById('push-payload');
      if (payloadEl) {
        var defaults = {
          'force_refresh': '{"message":"管理员要求刷新配置"}',
          'announcement': '{"message":"系统公告内容","title":"公告标题"}',
          'config_update': '{"key":"value","description":"配置更新说明"}',
          'security_patch': '{"min_version":"1.0.0","action":"update"}',
          'kill_switch': '{"target":"all","reason":"紧急维护"}',
        };
        payloadEl.value = defaults[type] || '{}';
      }
    }
  };
  window.submitPush = function () {
    var type = (document.getElementById('push-type') || {}).value || 'custom';
    var target = (document.getElementById('push-target') || {}).value || 'all';
    var payloadStr = (document.getElementById('push-payload') || {}).value || '{}';
    var priority = (document.getElementById('push-priority') || {}).value || 'normal';
    var ttl = (document.getElementById('push-ttl') || {}).value || '24';
    var payload;
    try { payload = JSON.parse(payloadStr); } catch (e) { toast('JSON格式错误: ' + e.message); return; }
    send('pushCreate', { type: type, target: target, payload: payload, priority: priority, ttl_hours: parseInt(ttl) });
    toast('正在推送: ' + type);
    var form = document.getElementById('push-form');
    if (form) form.style.display = 'none';
    delete _cache._pushLoaded;
  };
  window.cancelPush = function () {
    var form = document.getElementById('push-form');
    if (form) form.style.display = 'none';
  };
  window.revokePush = function (id) {
    if (!confirm('确认撤销该推送指令？')) return;
    send('pushRevoke', { directiveId: id });
    toast('撤销中...');
    delete _cache._pushLoaded;
  };



  window.rlToggleAutoSwitch = function (val) {
    send('rateLimitConfig', { autoSwitch: val === '1' });
    delete _cache._rlLoaded; delete _cache.rateLimitStatus;
    toast(val === '1' ? '\u5f00\u542f\u81ea\u52a8\u5207\u6362' : '\u5df2\u5173\u95ed\u81ea\u52a8\u5207\u6362');
  };
  window.rlSaveConfig = function () {
    var cooldown = parseInt((document.getElementById('rl-cooldown') || {}).value || '65', 10);
    var threshold = parseInt((document.getElementById('rl-threshold') || {}).value || '85', 10);
    send('rateLimitConfig', { cooldownMinutes: cooldown, preemptThreshold: threshold });
    delete _cache._rlLoaded;
    toast('\u4fdd\u5b58\u4e2d...');
  };
  window.rlClearCooldown = function (email) {
    if (email === 'all' && !confirm('\u786e\u8ba4\u6e05\u9664\u5168\u90e8\u8d26\u53f7\u51b7\u5374\uff1f')) return;
    send('rateLimitClear', { email: email });
    delete _cache._rlLoaded;
  };
  window.rlManualSwitch = function () {
    var email = (document.getElementById('rl-email') || {}).value || '';
    send('rateLimitTrigger', { email: email.trim(), deviceId: 'admin-manual', dPercent: 0 });
    toast('\u6b63\u5728\u89e6\u53d1\u5207\u6362...');
    delete _cache._rlLoaded;
  };
  window.rlRefresh = function () {
    delete _cache._rlLoaded; delete _cache.rateLimitStatus;
    send('rateLimitStatus'); render();
  };

  // ── Security Actions ──
  window.blockIp = function (ip) {
    send('securityBlock', { ip: ip, action: 'block' });
    toast('封禁: ' + ip);
    delete _cache._threatsLoaded;
  };
  window.unblockIp = function (ip) {
    send('securityBlock', { ip: ip, action: 'unblock' });
    toast('解封: ' + ip);
    delete _cache._threatsLoaded;
  };
  window.blockIpManual = function () {
    var ip = (document.getElementById('block-ip') || {}).value || '';
    if (!ip.trim()) { toast('请输入IP地址'); return; }
    send('securityBlock', { ip: ip.trim(), action: 'block' });
    toast('封禁: ' + ip);
    delete _cache._threatsLoaded;
  };
  window.unblockIpManual = function () {
    var ip = (document.getElementById('block-ip') || {}).value || '';
    if (!ip.trim()) { toast('请输入IP地址'); return; }
    send('securityBlock', { ip: ip.trim(), action: 'unblock' });
    toast('解封: ' + ip);
    delete _cache._threatsLoaded;
  };

  // ── Helpers ──
  function stat(val, label, cls) {
    return '<div class="stat"><div class="stat-value ' + (cls || '') + '">' + val + '</div><div class="stat-label">' + label + '</div></div>';
  }
  function esc(s) { return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
  function toast(msg, isError) {
    var el = document.getElementById('toast');
    if (el) {
      el.textContent = msg;
      el.style.display = 'block';
      el.style.background = isError ? 'var(--d)' : 'var(--ok)';
      setTimeout(function () { el.style.display = 'none'; }, 3000);
    }
  }
  function loading(d) {
    return '<div class="loading"><div class="spin"></div><div style="margin-top:8px">' + (d && d.error ? esc(d.error) : '加载中...') + '</div></div>';
  }
  function quotaBar(label, val, max, cls) {
    var pct = max ? Math.round(val / max * 100) : 0;
    var fillCls = pct < 20 ? 'quota-fill-low' : cls;
    return '<div class="quota-bar-wrap"><div class="quota-bar-label"><span>' + label + '</span><span>' + pct + '%</span></div>' +
      '<div class="quota-bar"><div class="quota-fill ' + fillCls + '" style="width:' + pct + '%"></div></div></div>';
  }

  // ── Remote action select change (show/hide custom payload) ──
  document.addEventListener('change', function (e) {
    if (e.target && e.target.id === 'remote-action') {
      var payload = document.getElementById('remote-payload');
      if (payload) payload.style.display = e.target.value === 'custom' ? 'block' : 'none';
    }
  });

  // ── Event Delegation (CSP-safe · 替代所有inline onclick) ──
  document.addEventListener('click', function (e) {
    var el = e.target;
    while (el && el !== document.body) {
      if (el.getAttribute) {
        // data-action dispatch
        var action = el.getAttribute('data-action');
        if (action) {
          var p1 = el.getAttribute('data-param') || '';
          var p2 = el.getAttribute('data-param2') || '';
          var fn = window[action];
          if (typeof fn === 'function') { p2 ? fn(p1, p2) : fn(p1); }
          return;
        }
        // Sub-tab click
        var subtab = el.getAttribute('data-subtab');
        if (subtab) { window.switchSubTab(subtab); return; }
        // Mode tab click
        if (el.classList && el.classList.contains('mode-tab')) {
          var modeVal = el.getAttribute('data-mode');
          if (modeVal) { window.switchMode(modeVal); return; }
        }
        // Refresh button
        if (el.id === 'btn-refresh') { window.refresh(); return; }
      }
      el = el.parentElement;
    }
  });

  // ── Init ──
  loadMode();
})();

