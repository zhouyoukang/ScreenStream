/**
 * 号池仪表盘 v6.9.0 — 官方对齐 · 计划感知 · 号池总值统计
 *
 * 核心: 用户看到的是号池，不是单个账号。
 * - 统一额度视图: 顶部显示所有账号的D%·W%总值(非均值)
 * - 号池健康指标 (可用/耗尽/限流/过期)
 * - 活跃账号信息: 1:1官方Plan显示(重置倒计时+计划过期+额外余额)
 * - 账号详情折叠 (默认打开)
 * - 添加账号 + 高级设置折叠
 *
 * v6.9: 1:1官方对齐 — 每账号显示计划过期/重置时间 + 过期视觉标记 + 智能管理
 */
const vscode = (global.__wamHot && global.__wamHot.vscode) || require('vscode');
const fs = require('fs');
const path = require('path');
const _e = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');


class AccountViewProvider {
  constructor(extensionUri, accountManager, authService, onAction) {
    this._extensionUri = extensionUri;
    this._am = accountManager;
    this._auth = authService;
    this._onAction = onAction;
    this._view = null;
    this._detailExpanded = true; // default open — user wants to see accounts
    this._msgDisposable = null; // onDidReceiveMessage disposable
    this._changeUnsub = null;   // onChange unsubscribe
    this._initialized = false;  // true after first HTML set
    this._renderTimer = null;     // debounce timer
    this._lastDataHash = '';      // dedup — lightweight hash to skip identical pushes
  }

  resolveWebviewView(webviewView) {
    // Dispose previous handlers to prevent accumulation across hot-reloads
    if (this._msgDisposable) { try { this._msgDisposable.dispose(); } catch {} this._msgDisposable = null; }
    if (this._changeUnsub) { try { this._changeUnsub(); } catch {} this._changeUnsub = null; }

    this._view = webviewView;
    this._initialized = false; // new webview → must set HTML fresh
    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [vscode.Uri.joinPath(this._extensionUri, 'media')]
    };
    // Defer render to ensure webview is fully initialized
    if (typeof setTimeout !== 'undefined') setTimeout(() => this._render(), 0);
    else this._render();

    this._msgDisposable = webviewView.webview.onDidReceiveMessage(async (msg) => {
      try { await this._handleMessage(msg); } catch (e) {
        console.error('WAM webview error:', e.message);
        this._toast(`错误: ${e.message}`, true);
      }
    });

    const renderFn = () => this._scheduleRender();
    this._am.onChange(renderFn);
    this._changeUnsub = () => this._am.offChange ? this._am.offChange(renderFn) : null;
  }

  async _handleMessage(msg) {
    const act = this._onAction;
    switch (msg.type) {
      case 'remove':
        if (msg.index !== undefined) { this._am.remove(msg.index); this._scheduleRender(); }
        break;
      case 'login':
        if (msg.index !== undefined && act) {
          this._setLoading(true);
          await act('login', msg.index);
          this._setLoading(false);
          this._scheduleRender();
        }
        break;
      case 'preview':
        if (msg.text) {
          const { AccountManager } = require('./accountManager');
          const accounts = AccountManager.parseAccounts(msg.text);
          if (this._view) this._view.webview.postMessage({ type: 'previewResult', accounts });
        }
        break;
      case 'batchAdd':
        if (msg.text && act) {
          this._setLoading(true);
          const result = await act('batchAdd', msg.text);
          if (result && result.added > 0) {
            this._toast(`+${result.added} 账号，验证中...`);
            this._scheduleRender();
            await act('refreshAll');
            this._toast('验证完成');
          } else if (result && result.skipped > 0) {
            this._toast(`${result.skipped} 个已存在`, true);
          } else {
            this._toast('未识别到有效账号', true);
          }
          this._setLoading(false);
          this._scheduleRender();
        }
        break;
      case 'refresh':
      case 'refreshAllAndRotate':
        if (act) { this._setLoading(true); await act('refreshAll'); this._setLoading(false); this._toast('刷新完成'); this._scheduleRender(); }
        break;
      case 'smartRotate':
        if (act) { this._setLoading(true); await act('smartRotate'); this._setLoading(false); this._scheduleRender(); }
        break;
      case 'panicSwitch':
        if (act) { this._setLoading(true); await act('panicSwitch'); this._setLoading(false); this._scheduleRender(); }
        break;
      case 'setMode':
        if (msg.mode && act) { act('setMode', msg.mode); this._initialized = false; this._render(); }
        break;
      case 'setPoolSource':
        if (msg.mode && act) { act('setPoolSource', msg.mode); this._initialized = false; this._render(); }
        break;
      case 'reprobeProxy':
        if (act) { this._setLoading(true); await act('reprobeProxy'); this._setLoading(false); this._scheduleRender(); }
        break;
      case 'resetFingerprint':
        if (act) act('resetFingerprint');
        break;
      case 'clearAllRateLimits':
        if (act) { this._setLoading(true); await act('clearAllRateLimits'); this._setLoading(false); this._toast('已清除所有限流标记'); this._scheduleRender(); }
        break;
      case 'removeEmpty':
        this._removeEmpty(); this._scheduleRender();
        break;
      case 'toggleDetail':
        this._detailExpanded = !this._detailExpanded;
        break; // state only — DOM already toggled client-side, no re-render
      case 'setProxyPort':
        if (msg.port !== undefined) { const p = parseInt(msg.port); if (p > 0 && p < 65536 && act) act('setProxyPort', p); }
        break;
      case 'setAutoRotate':
        if (act) act('setAutoRotate', msg.value);
        break;
      case 'setCreditThreshold':
        if (act) act('setCreditThreshold', msg.value);
        break;
      case 'exportAccounts':
        if (act) act('exportAccounts');
        break;
      case 'cloudActivate':
        if (act) {
          this._setLoading(true);
          const ar = await act('cloudActivate', msg.machineCode);
          this._setLoading(false);
          this._toast(ar && ar.ok ? '✅ 激活成功！W额度已到账' : `激活: ${(ar && ar.reason) || '发送给管理员处理'}`, !!(ar && !ar.ok));
        }
        break;
      // cloudRemote removed — migrated to admin side (号池管理端)
      case 'importAccounts':
        if (act) { await act('importAccounts'); this._scheduleRender(); }
        break;
      case 'copyPwd':
        if (msg.index !== undefined) {
          const account = this._am.get(msg.index);
          if (account && this._view) this._view.webview.postMessage({ type: 'pwdResult', index: msg.index, pwd: account.password });
        }
        break;
    }
  }

  _removeEmpty() {
    const accounts = this._am.getAll();
    let removed = 0;
    for (let i = accounts.length - 1; i >= 0; i--) {
      const a = accounts[i];
      if (/test|x\.com|example/i.test(a.email) || (a.credits !== undefined && a.credits <= 0)) {
        this._am.remove(i); removed++;
      }
    }
    this._toast(`已清理 ${removed} 个无效账号`);
  }

  refresh() { this._initialized = false; this._render(); }
  _toast(msg, isError) { if (this._view) this._view.webview.postMessage({ type: 'toast', msg, isError: !!isError }); }
  _setLoading(on) { if (this._view) this._view.webview.postMessage({ type: 'loading', on }); }

  /** Debounced render — collapses rapid successive calls into one */
  _scheduleRender() {
    if (this._renderTimer) clearTimeout(this._renderTimer);
    this._renderTimer = setTimeout(() => { this._renderTimer = null; this._render(); }, 300);
  }

  _render() {
    if (!this._view) return;
    if (this._renderTimer) { clearTimeout(this._renderTimer); this._renderTimer = null; }
    try {
      const data = this._computeData();
      if (!this._initialized) {
        // First render: set full HTML (only once)
        this._lastDataHash = '';
        this._view.webview.html = this._buildHtml(data);
        this._initialized = true;
      } else {
        // Subsequent renders: push data via postMessage (no page reload)
        // Lightweight dedup: hash key fields instead of full JSON.stringify
        const h = '' + (data.poolSource||'') + (data.pool?.total||0) + (data.pool?.available||0) +
          (data.pool?.sumDaily??'') + (data.pool?.sumWeekly??'') + (data.active?.index??-1) +
          (data.active?.quotaTag||'') + (data.switchCount||0) + (data.cloud?.online??false) +
          (data.accounts?.length||0) + (data.accounts?.[data.active?.index]?.label||'');
        if (h === this._lastDataHash) return;
        this._lastDataHash = h;
        this._view.webview.postMessage({ type: 'dataUpdate', data });
      }
    } catch (e) {
      console.error('WAM _render error:', e);
      try { this._view.webview.html = `<!DOCTYPE html><html><head><meta charset="UTF-8"></head><body style="background:#1a1b2e;color:#f87171;font:12px system-ui;padding:12px"><b>WAM Error</b><pre style="color:#e2e8f0;white-space:pre-wrap">${String(e.stack||e.message||e).replace(/</g,'&lt;')}</pre></body></html>`; } catch {}
    }
  }

  _getNonce() {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    let nonce = '';
    for (let i = 0; i < 32; i++) nonce += chars.charAt(Math.floor(Math.random() * chars.length));
    return nonce;
  }

  _computeData() {
    const accounts = this._am.getAll();
    const currentIndex = this._onAction ? this._onAction('getCurrentIndex') : -1;
    const cfg = vscode.workspace.getConfiguration('wam');
    const threshold = cfg.get('creditThreshold', 5);
    const poolSource = this._onAction ? (this._onAction('getPoolSource') || 'local') : 'local';
    const cloudSt = this._onAction ? (this._onAction('getCloudStatus') || {}) : {};
    const total = accounts.length;
    const pool = this._am.getPoolStats ? this._am.getPoolStats(threshold) : { total, available: 0, depleted: 0, rateLimited: 0, health: 0, avgDaily: null, avgWeekly: null };
    const switchCount = this._onAction ? (this._onAction('getSwitchCount') || 0) : 0;

    // Active account
    const activeQuota = this._am.getActiveQuota ? this._am.getActiveQuota(currentIndex) : null;
    let active = { index: currentIndex, label: '', planTag: '', quotaTag: '', resetInfo: '', expiryHtml: '' };
    if (currentIndex >= 0 && accounts[currentIndex]) {
      const a = accounts[currentIndex];
      const u = a.usage || {};
      active.label = a.email.split('@')[0];
      const dPct = u.daily ? u.daily.remaining : null;
      const wPct = u.weekly ? u.weekly.remaining : null;
      if (dPct !== null) active.quotaTag = `D${dPct}%${wPct !== null ? `·W${wPct}%` : ''}`;
      if (activeQuota) {
        if (activeQuota.plan) active.planTag = activeQuota.plan;
        if (activeQuota.resetCountdown) active.resetInfo += `D重置:${activeQuota.resetCountdown}`;
        if (activeQuota.weeklyResetCountdown) active.resetInfo += `${active.resetInfo ? ' · ' : ''}W重置:${activeQuota.weeklyResetCountdown}`;
        if (activeQuota.planDays !== null) {
          const aUrg = this._am.getExpiryUrgency ? this._am.getExpiryUrgency(currentIndex) : -1;
          const urgColor = aUrg === 0 ? 'var(--d)' : aUrg === 1 ? 'var(--w)' : aUrg === 3 ? 'var(--d)' : 'var(--ok)';
          active.expiryHtml = activeQuota.planDays > 0 ? `<span style="color:${urgColor}">${activeQuota.planDays}d剩余</span>` : '<span style="color:var(--d)">已过期</span>';
        }
      }
    }

    // Bar metrics
    const poolAvgD = pool.avgDaily, poolAvgW = pool.avgWeekly;
    const barEffective = pool.avgEffective !== null ? pool.avgEffective : ((poolAvgD !== null && poolAvgW !== null) ? Math.min(poolAvgD, poolAvgW) : (poolAvgD ?? poolAvgW));
    const barPct = barEffective !== null ? barEffective : (pool.avgCredits !== null ? Math.min(100, pool.avgCredits) : (pool.health || 0));
    const barColor = barPct > 30 ? 'var(--ok)' : barPct > 10 ? 'var(--w)' : 'var(--d)';
    const poolSumD = pool.sumDaily, poolSumW = pool.sumWeekly;
    const quotaLine = poolSumD !== null ? `D${poolSumD}%\u00b7W${poolSumW !== null ? poolSumW : '?'}%` : pool.sumCredits !== null ? `总${pool.sumCredits}分` : `${pool.health}%`;
    const wBottleneck = pool.weeklyBottleneckRatio > 50;

    // Machine code
    const machineCode = this._onAction ? (this._onAction('getMachineCode') || cloudSt.deviceId || '--') : (cloudSt.deviceId || '--');

    // Account rows data
    const acctData = accounts.map((a, i) => {
      const cur = i === currentIndex;
      const u = a.usage || {};
      const rem = this._am.effectiveRemaining(i);
      const d = u.daily?.remaining, w = u.weekly?.remaining;
      const isQuota = u.mode === 'quota';
      const label = (d !== null && d !== undefined)
        ? (w !== null && w !== undefined ? `D${d}%·W${w}%` : `D${d}%`)
        : (w !== null && w !== undefined) ? `W${w}%`
        : (rem !== null && rem !== undefined ? `${rem}${isQuota ? '%' : '分'}` : '--');
      const isExpired = this._am.isExpired ? this._am.isExpired(i) : false;
      const planDays = this._am.getPlanDaysRemaining ? this._am.getPlanDaysRemaining(i) : null;
      const urgency = this._am.getExpiryUrgency ? this._am.getExpiryUrgency(i) : -1;
      return { email: a.email, name: a.email.split('@')[0], d, w, effective: rem, isQuota, isExpired,
        rl: !!(a.rateLimit && a.rateLimit.until > Date.now()), planDays, urgency, isCurrent: cur, label };
    });

    return {
      poolSource,
      pool: { total: pool.total || 0, available: pool.available || 0, depleted: pool.depleted || 0,
        rateLimited: pool.rateLimited || 0, expired: pool.expired || 0,
        urgentCount: pool.urgentCount || 0, soonCount: pool.soonCount || 0,
        preResetWasteCount: pool.preResetWasteCount || 0,
        sumDaily: pool.sumDaily, sumWeekly: pool.sumWeekly,
        avgDaily: pool.avgDaily, avgWeekly: pool.avgWeekly, avgEffective: pool.avgEffective,
        weeklyBottleneckRatio: pool.weeklyBottleneckRatio || 0,
        nextReset: pool.nextReset || null, health: pool.health || 0,
        avgCredits: pool.avgCredits, sumCredits: pool.sumCredits },
      bar: { pct: barPct, color: barColor, line: quotaLine, bottleneck: wBottleneck },
      active, switchCount, detailExpanded: this._detailExpanded,
      cloud: { online: !!cloudSt.online, poolW: cloudSt.poolW || null, availW: cloudSt.availW || null,
        devices: cloudSt.devices || null, url: cloudSt.url || '', initialBonus: cloudSt.initialBonus || 100,
        machineCode, deviceId: cloudSt.deviceId || '',
        device_activated: !!cloudSt.device_activated,
        my_w: cloudSt.my_w || 0,
        my_w_available: cloudSt.my_w_available || 0,
        machine_code: cloudSt.machine_code || machineCode || '' },
      accounts: acctData,
    };
  }

  _buildHtml(data) {
    const scriptUri = this._view.webview.asWebviewUri(vscode.Uri.joinPath(this._extensionUri, 'media', 'panel.js'));
    const nonce = this._getNonce();
    const cspSource = this._view.webview.cspSource;
    const tplPath = path.join(this._extensionUri.fsPath, 'media', 'panel.html');
    if (fs.existsSync(tplPath)) {
      let html = fs.readFileSync(tplPath, 'utf-8');
      html = html.replace(/\$\{nonce\}/g, nonce);
      html = html.replace(/\$\{scriptUri\}/g, scriptUri.toString());
      html = html.replace(/\$\{cspSource\}/g, cspSource);
      const safeJson = JSON.stringify(data).replace(/<\/script>/gi, '<\\/script>');
      html = html.replace(/\$\{INIT_DATA\}/g, safeJson);
      return html;
    }
    // Fallback minimal HTML
    const safeJson2 = JSON.stringify(data).replace(/<\/script>/gi, '<\\/script>');
    return `<!DOCTYPE html><html><head><meta charset="UTF-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'nonce-${nonce}' ${cspSource};"><style>:root{--bg:#1a1b2e;--t:#e2e8f0;--m:#94a3b8;--p:#7c3aed;--b:#374151}*{margin:0;padding:0;box-sizing:border-box}body{font:13px system-ui;background:var(--bg);color:var(--t);padding:10px}</style></head><body><div id="app"></div><div id="toast"></div><script nonce="${nonce}">window.__INIT=${safeJson2};</script><script nonce="${nonce}" src="${scriptUri}"></script></body></html>`;
  }

  dispose() {
    if (this._renderTimer) { clearTimeout(this._renderTimer); this._renderTimer = null; }
    if (this._msgDisposable) { try { this._msgDisposable.dispose(); } catch {} this._msgDisposable = null; }
    if (this._changeUnsub) { try { this._changeUnsub(); } catch {} this._changeUnsub = null; }
    this._view = null;
  }
}

/** 在编辑器区域打开管理面板 */
function openAccountPanel(context, am, auth, onAction, existingPanel) {
  if (existingPanel) {
    try { existingPanel.reveal(vscode.ViewColumn.One); return null; } catch {}
  }
  const panel = vscode.window.createWebviewPanel(
    'wam.panel', '无感切号 · 账号管理', vscode.ViewColumn.One,
    { enableScripts: true, retainContextWhenHidden: true, localResourceRoots: [vscode.Uri.joinPath(context.extensionUri, 'media')] }
  );
  const provider = new AccountViewProvider(
    context.extensionUri, am, auth, onAction
  );
  const fakeView = { webview: panel.webview };
  Object.defineProperty(fakeView.webview, 'options', { set() {}, get() { return { enableScripts: true }; } });
  provider.resolveWebviewView(fakeView);
  panel.onDidDispose(() => { provider._view = null; });
  return { panel, provider };
}

module.exports = { AccountViewProvider, openAccountPanel };
