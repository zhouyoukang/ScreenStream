/**
 * 无感号池引擎 v3.11.0
 */
const vscode = require("vscode");
const { AccountManager } = require("./accountManager");
const { AuthService } = require("./authService");
const { openAccountPanel, AccountViewProvider } = require("./webviewProvider");
const {
  readFingerprint,
  resetFingerprint,
  ensureComplete: ensureFingerprintComplete,
  hotVerify,
} = require("./fingerprintManager");
const { CloudPoolClient } = require("./cloudPool");
const fs = require("fs");
const path = require("path");
const os = require("os");
const http = require("http");
const { execSync } = require("child_process");

// 核心: global对象跨require.cache清除持久化, 命令代理注册一次handler可变
const _G = global.__wamHot = global.__wamHot || {
  handlers: new Map(),     // commandId → handler function (可变引用)
  registered: new Set(),   // 已真注册的commandId (不可重复)
  viewRegistered: false,   // webviewProvider已注册?
  viewDelegate: null,      // 当前webview provider delegate
  cachedView: null,        // 缓存的webview view引用
  ctx: null,               // 真context引用 (跨reload持久化)
  vscode: null,            // vscode模块引用 (热重载时Extension Host无法解析外部路径的require('vscode'))
  watcher: null,           // fs.watch handle
  debounce: null,          // 防抖定时器
  reloadCount: 0,          // 热重载计数
  lastReloadSignal: 0,     // 上次热重载信号时间戳 (防过期信号)
};
_G.vscode = _G.vscode || vscode; // 首次加载时持久化, 热重载不覆盖
_G.snapshot = _G.snapshot || null;       // 状态快照 (热重载跨模块传递)
// v3.11.3: 版本守卫 — 升级时关闭旧服务器(防端口泄漏), 然后让_startHubServer重建
if (_G.hubHandlerVersion !== '3.11.3') {
  if (_G.hubServerRef) { try { _G.hubServerRef.close(); } catch {} }
  _G.hubServerRef = null;
  _G.hubHandlerVersion = '3.11.3';
}
_G.hubVersion = '3.11.0';
// v3.11.2: always update mutable handler on every load
_G.hubHandlerFn = _hubRequestHandler;

_G.hubServerRef = _G.hubServerRef || null; // Hub server引用 (跨reload复用, 无端口冲突)
_G.isHotReloading = false;               // 热重载进行中标志 (deactivate软模式)

/** 代理注册命令 — 首次真注册(handler为可变引用), 后续仅更新handler */
function _proxyCmd(context, id, handler) {
  _G.handlers.set(id, handler);
  if (_G.registered.has(id)) return;
  _G.registered.add(id);
  context.subscriptions.push(
    vscode.commands.registerCommand(id, (...args) => {
      const h = _G.handlers.get(id);
      return h ? h(...args) : undefined;
    })
  );
}

/** 代理注册WebviewProvider — 首次真注册(delegate可变), 后续仅更新delegate */
function _proxyView(context, viewId, provider) {
  _G.viewDelegate = provider;
  if (_G.viewRegistered) return;
  _G.viewRegistered = true;
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(viewId, {
      resolveWebviewView(view, ctx, tok) {
        _G.cachedView = view;
        if (_G.viewDelegate) return _G.viewDelegate.resolveWebviewView(view, ctx, tok);
      }
    }, { webviewOptions: { retainContextWhenHidden: true } })
  );
}

let statusBar, am, auth, _panelProvider, _panel, cloudPool;
let _activeIndex = -1; // 当前活跃账号
let _switching = false; // 切换锁
let _lastQuotaDropTs = 0;   // v3.2: 生成守卫 — 上次配额下降时间戳(=正在生成)
let _pendingSwitch = null;  // v3.2: 生成守卫 — 延迟切换 { context, targetIndex, reason }
const GENERATION_GUARD_MS = 40000; // v3.2: 40s内配额稳定=生成结束,可安全切号
let _poolTimer = null; // 号池引擎定时器
let _lastQuota = null; // 上次活跃账号额度(变化检测)
let _lastCheckTs = 0; // 上次检查时间戳
let _boostUntil = 0; // 加速模式截止
let _switchCount = 0; // 本会话切换次数
let _discoveredAuthCmd = null; // 缓存发现的注入命令
let _outputChannel = null; // 结构化日志输出通道
let _eventLog = []; // 事件日志缓冲 [{ts, level, msg}]
const MAX_EVENT_LOG = 200; // 最大日志条数
let _routingMode = 'hybrid'; // 'local'=代理路由 | 'cloud'=WAM切号 | 'hybrid'=代理优先
const PROXY_HEALTH_PORT = 19443;
let _proxyOnline = false;
let _proxyIntercepting = false; // 代理是否实际拦截LS流量(requests>0 OR 刚上线宽限期内)
let _proxyOnlineSince = 0;      // 代理上线时间戳(宽限期计算)
const PROXY_INTERCEPT_GRACE = 120000; // 2min宽限期: 刚上线可能HTTPS_PROXY刚生效,requests尚为0
let _proxyLastCheck = 0;
const PROXY_CHECK_INTERVAL = 15000;
const PROXY_CHECK_BACKOFF = 300000; // 离线时5min检查一次(省240次/小时无用探测)
let _proxyOfflineCount = 0; // 连续离线次数(用于backoff)

let _poolSourceMode = 'local'; // 'local'=本地文件 | 'cloud'=阿里云 | 'hybrid'=本地优先+云端补充
let _cloudSyncTimer = null;
const CLOUD_SYNC_INTERVAL = 300000;
let _cloudPullCount = 0;
let _remoteApprovalTimer = null;
const REMOTE_POLL_INTERVAL = 15000; // 15s poll for remote requests
let _proxyProcess = null;
let _proxySpawnAttempts = 0;
const PROXY_MAX_SPAWN_ATTEMPTS = 3;
let _proxyScriptMissing = false;
let _proxyCheckTimer = null; // 定期代理检查定时器(deactivate时清理) // 脚本不存在则不再尝试(止于当止)
let _qwCtxTimer = null;       // L1 context key检测
let _qwAdaptiveTimer = null;  // L1 自适应调频
let _qwCacheTimer = null;     // L3 cachedPlanInfo检测
let _qwL5Timer = null;        // L5 初始延迟
let _qwL5Interval = null;     // L5 容量探测周期

/** 检查透明代理(:19443)是否在线 — 轻量HTTP探测 */
function _checkProxyHealth() {
  return new Promise(resolve => {
    const req = http.get(`http://127.0.0.1:${PROXY_HEALTH_PORT}/`, (res) => {
      let buf = ''; res.on('data', c => buf += c);
      res.on('end', () => {
        try {
          const d = JSON.parse(buf);
          const wasOnline = _proxyOnline;
          _proxyOnline = d.status === 'ok';
          if (_proxyOnline && !wasOnline) _proxyOnlineSince = Date.now(); // 记录上线时刻
          if (!_proxyOnline) { _proxyIntercepting = false; _proxyOnlineSince = 0; }
          else {
            // 判断是否真正拦截LS流量: requests>0 OR 在2min宽限期内(HTTPS_PROXY可能刚生效)
            const grace = _proxyOnlineSince > 0 && (Date.now() - _proxyOnlineSince) < PROXY_INTERCEPT_GRACE;
            _proxyIntercepting = (d.requests > 0) || grace;
          }
        } catch { _proxyOnline = false; _proxyIntercepting = false; _proxyOnlineSince = 0; }
        _proxyLastCheck = Date.now();
        if (_proxyOnline) { _proxySpawnAttempts = 0; _proxyOfflineCount = 0; }
        else { _proxyOfflineCount++; }
        resolve(_proxyOnline);
      });
    });
    req.on('error', () => { _proxyOnline = false; _proxyOfflineCount++; _proxyLastCheck = Date.now(); resolve(false); });
    req.setTimeout(2000, () => { req.destroy(); _proxyOnline = false; _proxyOfflineCount++; _proxyLastCheck = Date.now(); resolve(false); });
  });
}

/** 自动启动透明代理 v3.0 — 道法自然·水到渠成 */
function _autoSpawnProxy() {
  if (_proxyProcess || _proxyOnline) return;
  if (_proxySpawnAttempts >= PROXY_MAX_SPAWN_ATTEMPTS) return;
  if (_proxyScriptMissing) return; // 脚本已确认不存在，止于当止
  _proxySpawnAttempts++;
  const proxyScript = _findProxyScript();
  if (!proxyScript) { _proxyScriptMissing = true; _logInfo("PROXY", "透明代理脚本未找到, 不再尝试"); return; }
  const keypoolFile = path.join(path.dirname(proxyScript), '..', 'data', 'keypool.json');
  if (!fs.existsSync(keypoolFile)) { _logWarn("PROXY", "keypool.json不存在, 请先运行warmup"); return; }
  try {
    const { spawn } = require('child_process');
    _proxyProcess = spawn('node', [proxyScript, 'serve'], {
      detached: true, stdio: 'ignore',
      env: { ...process.env, NODE_TLS_REJECT_UNAUTHORIZED: '0' },
    });
    _proxyProcess.unref();
    _proxyProcess.on('exit', (code) => {
      _logWarn("PROXY", `透明代理进程退出 code=${code}`);
      _proxyProcess = null; _proxyOnline = false;
    });
    _proxyProcess.on('error', (e) => {
      _logWarn("PROXY", `透明代理启动失败: ${e.message}`);
      _proxyProcess = null;
    });
    _logInfo("PROXY", `透明代理v3.0自动启动 (attempt ${_proxySpawnAttempts}/${PROXY_MAX_SPAWN_ATTEMPTS})`);
    setTimeout(() => _checkProxyHealth().then(ok => {
      _logInfo("PROXY", `自动启动结果: ${ok ? '✅在线' : '⚠未就绪(稍后重试)'}`);
      _updatePoolBar();
    }), 4000);
  } catch (e) { _logWarn("PROXY", `spawn失败: ${e.message}`); _proxyProcess = null; }
}

/** 寻找transparent_proxy.js脚本路径 */
function _findProxyScript() {
  const candidates = [
    path.join(__dirname, '..', 'scripts', 'transparent_proxy.js'),
    path.join(__dirname, 'scripts', 'transparent_proxy.js'),
    'D:\\wam-proxy\\transparent_proxy.js',
  ];
  for (const p of candidates) { if (fs.existsSync(p)) return p; }
  return null;
}

/** 转发请求到透明代理API — 通用Helper */
function _proxyApiForward(apiPath) {
  return new Promise((resolve, reject) => {
    const r = http.get(`http://127.0.0.1:${PROXY_HEALTH_PORT}${apiPath}`, (resp) => {
      let buf = ''; resp.on('data', c => buf += c);
      resp.on('end', () => { try { resolve(JSON.parse(buf)); } catch { resolve({ error: 'parse failed' }); } });
    });
    r.on('error', e => reject(e));
    r.setTimeout(3000, () => { r.destroy(); reject(new Error('timeout')); });
  });
}

/** 当前是否由透明代理处理路由(local模式或hybrid+代理在线) */
function _isProxyRouting() {
  // v3.11.1: 必须proxy真正拦截LS流量(requests>0 OR 宽限期内), 否则回退WAM切号+autoRetry
  if (_routingMode === 'local') return _proxyOnline && _proxyIntercepting;
  if (_routingMode === 'hybrid') return _proxyOnline && _proxyIntercepting;
  return false; // cloud模式不走代理
}

/** v3.2: 生成守卫 — Cascade是否正在生成响应
 *  依据: 配额在GENERATION_GUARD_MS内有下降 = 正在被消耗 = 可能生成中
 *  保守策略: 宁延迟切换,不打断正在进行的对话流 */
function _isGenerationActive() {
  return Date.now() - _lastQuotaDropTs < GENERATION_GUARD_MS;
}

const TIER_RL_RE = /rate\s*limit\s*exceeded[\s\S]*?no\s*credits\s*were\s*used/i;
const UPGRADE_PRO_RE = /upgrade\s*to\s*a?\s*pro/i;
const ABOUT_HOUR_RE = /try\s*again\s*in\s*about\s*an?\s*hour/i;
const MODEL_UNREACHABLE_RE = /model\s*provider\s*unreachable/i;
const PROVIDER_ERROR_RE = /provider.*(?:error|unavailable|unreachable)|(?:error|unavailable|unreachable).*provider/i;
const HOUR_WINDOW = 3600000; // 1小时滑动窗口
const TIER_MSG_CAP_ESTIMATE = 15; // Trial账号预估小时消息上限
const TIER_CAP_WARN_RATIO = 0.5; // 达到上限50%即预防
let _hourlyMsgLog = []; // [{ts}] 每小时消息追踪(用于Gate 4预测)
let _tierRateLimitCount = 0; // 本会话Gate 4触发次数

const WATCHDOG_TIMEOUT = 90000;
let _lastSuccessfulProbe = Date.now();
let _watchdogSwitchCount = 0;

let _accountActiveSince = Date.now();
const BLIND_MAX_ACTIVE_MS = 900000; // 15min×Tab数→切号
let _cumulativeDropSinceActivation = 0; // v14.0: 累积额度降幅(自账号激活起, 不依赖消息计数)
const CUMULATIVE_DROP_ROTATE_THRESHOLD = 20; // 累积降幅超20%即预防性切号(≈8条消息, 15msg/h的53%)

const _sessionPool = new Map(); // accountIndex → { idToken, apiKey, expireTime, capacity, lastProbe, lastRefresh, healthy }
let _poolInitialized = false;
let _poolInitializing = false;
let _sessionPoolTimer = null; // token刷新定时器
let _capacityMatrixTimer = null; // 并行探测定时器
const SESSION_REFRESH_MS = 2400000; // 40min刷新token(Firebase TTL=50min)
const SESSION_INIT_BATCH = 3; // 初始化并发数(控制API压力)
let _sessionPoolAuthCount = 0; // 成功认证数
let _sessionPoolFailCount = 0; // 认证失败数

const MATRIX_PROBE_INTERVAL = 20000; // 20s全池探测周期
const MATRIX_PROBE_FAST = 8000; // 加速模式8s(活跃使用时)
const MATRIX_PROBE_BATCH = 5; // 并行探测并发数
let _capacityMatrix = new Map(); // accountIndex → { hasCapacity, messagesRemaining, maxMessages, resetsInSeconds, probedAt }
let _matrixProbeCount = 0; // 总探测次数
let _matrixProbeErrors = 0; // 连续错误

let _unifiedPool = {
  totalRemaining: 0, // 全池消息剩余总量
  totalMax: 0, // 全池消息上限总量
  availableCount: 0, // 可用账号数(有容量)
  limitedCount: 0, // 限流账号数
  totalCount: 0, // 总账号数
  utilization: 0, // 利用率 %
  throughput: 0, // 理论吞吐(消息/小时)
  updatedAt: 0,
};

let _nextBestIndex = -1; // 预计算下一最优账号(随时就绪)
let _nextBestScore = -1; // 下一最优评分
let _zerodelaySwitchCount = 0; // 零延迟切换次数
let _fullLoginSwitchCount = 0; // 回退完整登录次数

const WINDOW_STATE_FILE = "wam-window-state.json";
const WINDOW_HEARTBEAT_MS = 30000; // 30s心跳
const WINDOW_DEAD_MS = 90000; // 90s无心跳=死亡
let _windowId = null; // 本窗口唯一ID
let _windowTimer = null; // 心跳定时器

const POLL_NORMAL = 45000; // 正常轮询 45s
const POLL_BOOST = 8000; // 加速轮询 8s (v6.2: 从12s降至8s)
const POLL_BURST = 3000; // 并发burst轮询 3s (v6.4: 多Tab场景)
const BOOST_DURATION = 300000; // 加速持续 5min (v6.2: 从3min延至5min)
const PREEMPTIVE_THRESHOLD = 15; // 预防性切换底线: daily%≤15即切(硬编码，不受用户配置影响)
const SLOPE_WINDOW = 5; // 斜率预测窗口(样本数)
const SLOPE_HORIZON = 300000; // 预测视野5min(ms)
let _quotaHistory = []; // [{ts, remaining}] 用于斜率预测

const CONCURRENT_TAB_SAFE = 2; // 安全并发Tab数(超过即进入burst防护)
const MSG_RATE_WINDOW = 60000; // 消息速率统计窗口 60s
const MSG_RATE_LIMIT = 12; // 预估消息速率上限(条/分钟, 保守估计)
const BURST_DETECT_THRESHOLD = 0.7; // 速率达到上限的70%即触发预防
let _cascadeTabCount = 0; // 当前检测到的Cascade Tab数
let _msgRateLog = []; // [{ts}] 消息速率追踪(每次quota变化≈1次消息)
let _lastTabCheck = 0; // 上次Tab检测时间
const TAB_CHECK_INTERVAL = 10000; // Tab检测间隔 10s
let _burstMode = false; // 是否处于burst防护模式

let _allQuotaSnapshot = new Map(); // index → {remaining, checkedAt} 全池额度快照
let _lastFullScanTs = 0; // 上次全池扫描时间戳
let _lastReactiveSwitchTs = 0; // 上次响应式切换时间戳
const FULL_SCAN_INTERVAL = 300000; // 全池扫描间隔 300s (v6.8: 从90s放宽，减少API压力)
const REACTIVE_SWITCH_CD = 10000; // 响应式切换冷却 10s (v7.4: 从30s收紧，加速响应)
const REACTIVE_DROP_MIN = 2; // 响应式切换最小降幅阈值

// 如果在注入BEFORE轮转指纹, LS重启自然拿到新ID = 热重置, 无需重启Windsurf
// 旧流程(v6.9): 注入 → LS重启(读旧ID) → 轮转指纹(写新ID到磁盘, 但LS已用旧ID)
// 新流程(v7.0): 轮转指纹(写新ID) → 注入 → LS重启(读新ID!) → 验证 = 热重置完成
let _lastRotatedIds = null; // 最近一次轮转生成的新ID (用于热验证)
let _hotResetCount = 0; // 本会话热重置成功次数
let _hotResetVerified = 0; // 本会话热重置已验证次数
// 积分速度追踪器 (v7.0: 检测高速消耗 → 主动触发热重置+切号)
const VELOCITY_WINDOW = 120000; // 速度计算窗口 120s
const VELOCITY_THRESHOLD = 10; // 速度阈值: 120s内降>10% = 高速消耗
let _velocityLog = []; // [{ts, remaining}] 速度追踪样本

// Thinking模型分级预算 — 根据模型tier动态调整budget
const OPUS_VARIANTS = [
  'claude-opus-4-6-thinking-1m',
  'claude-opus-4-6-thinking',
  'claude-opus-4-6-1m',
  'claude-opus-4-6',
  'claude-opus-4-6-thinking-fast',
  'claude-opus-4-6-fast',
];
const SONNET_FALLBACK = 'claude-sonnet-4-6-thinking-1m';
let _currentModelUid = null; // 当前活跃模型UID (从windsurfConfigurations读取)
let _retryCmd = undefined;   // v16.0: auto-retry command (lazy-discovered)
let _modelRateLimitCount = 0; // 本会话per-model rate limit触发次数
let _lastModelSwitch = 0; // 上次模型切换时间戳

// v15.0实测: claude-opus-4.6 服务端Opus桶窗口已升至~40min (实测"Resets in: 39m2s"=2342s)
//   v14.0假设: ~10min窗口("Resets in: 9m22s"=562s) → v15.0实测: ~40min窗口("Resets in: 39m2s"=2342s)
//   根本修复: 所有Opus预算=1(每条即切!) + 窗口39min + 冷却40min
const MODEL_BUDGET = 1; // 所有高ACU模型: 每条即切
const OPUS_BUDGET_WINDOW = 2340000; // 39分钟滑动窗口(ms) — v15.0: 720000ms(12min)→2340000ms(39min), 匹配实测"Resets in: 39m2s"
const OPUS_COOLDOWN_DEFAULT = 2400; // Opus per-model默认冷却2400s(40min) — v15.0: 720s→2400s, 匹配实测"Resets in: 39m2s"=2342s+余量
const CAPACITY_CHECK_THINKING = 3000; // Thinking模型L5探测间隔3s(更快检测hasCapacity=false)
let _modelMsgLog = new Map(); // accountIndex → [{ts, family}]
let _modelGuardSwitchCount = 0;
const SONNET_VARIANTS = [
  'claude-sonnet-4-6-thinking-1m',
  'claude-sonnet-4-6-thinking',
  'claude-sonnet-4-6-1m',
  'claude-sonnet-4-6',
];

/** 读取当前活跃模型UID (从state.vscdb windsurfConfigurations/codeium.windsurf) */
function _readCurrentModelUid() {
  try {
    if (!auth) return _currentModelUid;
    const cw = auth.readCachedValue && auth.readCachedValue('codeium.windsurf');
    if (cw) {
      const d = JSON.parse(cw);
      const uids = d['windsurf.state.lastSelectedCascadeModelUids'];
      if (Array.isArray(uids) && uids.length > 0) {
        _currentModelUid = uids[0];
        return _currentModelUid;
      }
    }
  } catch {}
  // 防止_currentModelUid为null导致Gate 3 handler被跳过
  return _currentModelUid || 'claude-opus-4-6-thinking-1m'; // 默认假设Opus(保守策略)
}

/** 检测modelUid是否属于Opus家族 */
function _isOpusModel(uid) {
  return uid && uid.toLowerCase().includes('opus');
}

/** 检测是否为Thinking模型(更高token成本, 更低rate limit) */
function _isThinkingModel(uid) {
  return uid && uid.toLowerCase().includes('thinking');
}

/** 检测是否为Thinking 1M模型(最高成本, 最低rate limit) */
function _isThinking1MModel(uid) {
  if (!uid) return false;
  const u = uid.toLowerCase();
  return u.includes('thinking') && u.includes('1m');
}

/** 检测是否为Sonnet Thinking 1M模型(v3.5.0: 需独立守卫, ACU=12, 桶≈3/20min) */
function _isSonnetThinking1MModel(uid) {
  if (!uid) return false;
  const u = uid.toLowerCase();
  return u.includes('sonnet') && u.includes('thinking') && u.includes('1m');
}

function _getModelBudget() { return MODEL_BUDGET; }

/** 追踪模型消息(Opus/Sonnet统一) */
function _trackModelMsg(accountIndex, family) {
  if (accountIndex < 0) return;
  if (!_modelMsgLog.has(accountIndex)) _modelMsgLog.set(accountIndex, []);
  _modelMsgLog.get(accountIndex).push({ ts: Date.now(), family });
  const cutoff = Date.now() - OPUS_BUDGET_WINDOW;
  _modelMsgLog.set(accountIndex, _modelMsgLog.get(accountIndex).filter(m => m.ts > cutoff));
}
function _getModelMsgCount(accountIndex, family) {
  if (accountIndex < 0 || !_modelMsgLog.has(accountIndex)) return 0;
  const cutoff = Date.now() - OPUS_BUDGET_WINDOW;
  return _modelMsgLog.get(accountIndex).filter(m => m.ts > cutoff && (!family || m.family === family)).length;
}
function _isNearModelBudget(accountIndex) {
  const uid = _currentModelUid || _readCurrentModelUid();
  const family = _isSonnetThinking1MModel(uid) ? 'sonnet' : _isOpusModel(uid) ? 'opus' : null;
  return family ? _getModelMsgCount(accountIndex, family) >= MODEL_BUDGET : false;
}
function _resetModelMsgLog(accountIndex) { _modelMsgLog.delete(accountIndex); }

// 道法自然·万法归宗·额度归一·速率归一·上善若水任方圆

/** v2.0: 初始化Session Pool — 所有账号同步登录
 *  批量Firebase认证 + RegisterUser获取apiKey → 全池预热 */
async function _initSessionPool() {
  if (_poolInitializing || !am || !auth) return;
  _poolInitializing = true;
  const accounts = am.getAll();
  if (accounts.length === 0) { _poolInitializing = false; return; }

  _logInfo('SESSION_POOL', `═══ 初始化: ${accounts.length}账号同步登录 ═══`);
  const t0 = Date.now();
  _sessionPoolAuthCount = 0;
  _sessionPoolFailCount = 0;

  for (let i = 0; i < accounts.length; i += SESSION_INIT_BATCH) {
    const batch = [];
    for (let j = 0; j < SESSION_INIT_BATCH && i + j < accounts.length; j++) {
      batch.push(_authOneForPool(i + j));
    }
    await Promise.allSettled(batch);
  }

  _poolInitialized = true;
  _poolInitializing = false;
  const dt = Date.now() - t0;
  _logInfo('SESSION_POOL', `═══ 初始化完成: ${_sessionPoolAuthCount}/${accounts.length}成功, ${_sessionPoolFailCount}失败, ${dt}ms ═══`);

  // 立即执行首次全池容量探测
  _probeAllCapacity();
}

/** v2.0: 认证单个账号到Session Pool */
async function _authOneForPool(index) {
  const account = am.get(index);
  if (!account || !account.email || !account.password) return;
  if (am.isExpired(index)) {
    _sessionPool.set(index, { idToken: null, apiKey: null, expireTime: 0, capacity: null, lastProbe: 0, lastRefresh: 0, healthy: false, error: 'expired' });
    return;
  }

  try {
    // Firebase login → idToken
    const idToken = await auth.getFreshIdToken(account.email, account.password);
    if (!idToken) {
      _sessionPoolFailCount++;
      _sessionPool.set(index, { idToken: null, apiKey: null, expireTime: 0, capacity: null, lastProbe: 0, lastRefresh: Date.now(), healthy: false, error: 'login_failed' });
      return;
    }

    // RegisterUser → apiKey (for L5 capacity probing)
    let apiKey = null;
    try {
      const reg = await auth.registerUser(account.email, account.password);
      if (reg && reg.apiKey) apiKey = reg.apiKey;
    } catch {}

    _sessionPool.set(index, {
      idToken,
      apiKey,
      expireTime: Date.now() + SESSION_REFRESH_MS,
      capacity: null,
      lastProbe: 0,
      lastRefresh: Date.now(),
      healthy: true,
      error: null,
    });
    _sessionPoolAuthCount++;
  } catch (e) {
    _sessionPoolFailCount++;
    _sessionPool.set(index, { idToken: null, apiKey: null, expireTime: 0, capacity: null, lastProbe: 0, lastRefresh: Date.now(), healthy: false, error: e.message });
    _logWarn('SESSION_POOL', `#${index + 1} 认证失败: ${e.message}`);
  }
}

/** v2.0: 刷新即将过期的token (定时器回调) */
async function _refreshSessionTokens() {
  if (!_poolInitialized || !am || !auth) return;
  const now = Date.now();
  const refreshThreshold = now + 600000; // 10min内过期的刷新

  for (const [index, session] of _sessionPool.entries()) {
    if (!session.healthy && session.error === 'expired') continue;
    if (session.expireTime > 0 && session.expireTime < refreshThreshold) {
      try {
        await _authOneForPool(index);
        _logInfo('SESSION_POOL', `#${index + 1} token已刷新`);
      } catch {}
    }
  }
}

/** v2.0: 并行L5容量探测 — 用每个账号的apiKey同时探测所有账号的容量
 *  这是v2.0的核心突破: 不只探测当前账号, 而是ALL accounts同时探测 */
async function _probeAllCapacity() {
  if (!_poolInitialized || _sessionPool.size === 0 || !auth) return;

  const modelUid = _readCurrentModelUid();
  if (!modelUid) return;

  const entries = Array.from(_sessionPool.entries()).filter(([_, s]) => s.apiKey && s.healthy);
  if (entries.length === 0) return;

  _matrixProbeCount++;
  const t0 = Date.now();
  let probed = 0, failed = 0;

  for (let i = 0; i < entries.length; i += MATRIX_PROBE_BATCH) {
    const batch = entries.slice(i, i + MATRIX_PROBE_BATCH);
    const promises = batch.map(([idx, session]) => {
      return auth.checkRateLimitCapacity(session.apiKey, modelUid)
        .then(result => {
          if (result) {
            const hasUseful = result.messagesRemaining >= 0 || result.maxMessages >= 0 || !result.hasCapacity;
            _capacityMatrix.set(idx, {
              hasCapacity: result.hasCapacity,
              messagesRemaining: result.messagesRemaining,
              maxMessages: result.maxMessages,
              resetsInSeconds: result.resetsInSeconds,
              probedAt: Date.now(),
              hasUsefulData: hasUseful,
            });
            session.capacity = result;
            session.lastProbe = Date.now();
            probed++;

            // 自动标记/解除限流 (v3.1双向: 耗尽→标记 / 恢复→解除)
            if (!result.hasCapacity && !am.isRateLimited(idx)) {
              am.markRateLimited(idx, result.resetsInSeconds || 600, { trigger: 'capacity_matrix', type: 'tier_cap' });
              _logWarn('MATRIX', `#${idx + 1} 容量耗尽 → 自动标记限流(${result.resetsInSeconds}s)`);
            } else if (result.hasCapacity && am.isRateLimited(idx)) {
              const _mxRl = am.getRateLimitInfo(idx);
              if (_mxRl && (_mxRl.trigger === 'capacity_matrix' || _mxRl.type === 'tier_cap' || _mxRl.type === 'capacity_matrix')) {
                am.clearRateLimit(idx);
                _logInfo('MATRIX', `#${idx + 1} 容量已恢复 → 自动解除限流`);
              }
            }
            // 更新真实消息上限
            if (result.maxMessages > 0) _realMaxMessages = result.maxMessages;
          } else {
            failed++;
          }
        })
        .catch(() => { failed++; });
    });
    await Promise.allSettled(promises);
  }

  _matrixProbeErrors = failed > entries.length / 2 ? _matrixProbeErrors + 1 : 0;
  const dt = Date.now() - t0;

  // 每5次或有变化时记录日志
  if (_matrixProbeCount % 5 === 0 || failed > 0) {
    _logInfo('MATRIX', `probe #${_matrixProbeCount}: ${probed}/${entries.length}成功, ${failed}失败, ${dt}ms`);
  }

  // 更新统一容量池
  _updateUnifiedPool();
  // 预计算下一最优
  _precomputeNextBest();
}

/** v2.0: 更新统一容量池 — 额度归一 */
function _updateUnifiedPool() {
  let totalRemaining = 0, totalMax = 0;
  let availableCount = 0, limitedCount = 0;
  const accounts = am ? am.getAll() : [];

  for (let i = 0; i < accounts.length; i++) {
    if (am.isExpired(i)) continue;

    if (am.isRateLimited(i)) {
      limitedCount++;
      continue;
    }

    const cap = _capacityMatrix.get(i);
    if (cap && cap.hasUsefulData) {
      if (cap.hasCapacity) {
        availableCount++;
        if (cap.messagesRemaining >= 0) totalRemaining += cap.messagesRemaining;
        if (cap.maxMessages >= 0) totalMax += cap.maxMessages;
      } else {
        limitedCount++;
      }
    } else {
      // 无L5数据, 用quota%评估
      const rem = am.effectiveRemaining(i);
      if (rem !== null && rem > PREEMPTIVE_THRESHOLD) {
        availableCount++;
        // 估算: quota%转消息数 (假设maxMessages=25 per account)
        const estMax = _realMaxMessages > 0 ? _realMaxMessages : TIER_MSG_CAP_ESTIMATE;
        totalRemaining += Math.round(estMax * rem / 100);
        totalMax += estMax;
      } else if (rem !== null && rem <= PREEMPTIVE_THRESHOLD) {
        limitedCount++;
      }
    }
  }

  // 计算吞吐量: 每个可用账号每小时约25条消息
  const estPerHour = _realMaxMessages > 0 ? _realMaxMessages : TIER_MSG_CAP_ESTIMATE;
  const throughput = availableCount * estPerHour;

  _unifiedPool = {
    totalRemaining,
    totalMax,
    availableCount,
    limitedCount,
    totalCount: accounts.length,
    utilization: totalMax > 0 ? Math.round((1 - totalRemaining / totalMax) * 100) : 0,
    throughput,
    updatedAt: Date.now(),
  };
}

/** v2.0: 预计算下一最优账号 — 随时就绪, 零延迟切换 */
function _precomputeNextBest() {
  let bestIdx = -1, bestScore = -Infinity;
  const otherClaimed = new Set(_getOtherWindowAccounts());
  const accounts = am ? am.getAll() : [];

  for (let i = 0; i < accounts.length; i++) {
    if (i === _activeIndex) continue;
    if (am.isRateLimited(i) || am.isExpired(i)) continue;
    if (otherClaimed.has(i)) continue;

    // Session Pool中没有有效session的跳过
    const session = _sessionPool.get(i);
    const hasValidSession = session && session.healthy && session.idToken && Date.now() < session.expireTime;

    let score = 0;

    // L5容量数据 = 最高置信度
    const cap = _capacityMatrix.get(i);
    if (cap && cap.hasUsefulData && cap.hasCapacity && cap.messagesRemaining >= 0) {
      score = cap.messagesRemaining * 1000; // 高权重
    } else {
      const rem = am.effectiveRemaining(i);
      if (rem !== null) score = rem * 10;
    }

    // 有效session加分(零延迟可切)
    if (hasValidSession) score += 5000;

    // 紧急过期优先使用(UFEF)
    const urg = am.getExpiryUrgency(i);
    if (urg === 0) score += 3000; // 即将过期=优先消耗

    // Opus预算未满加分
    if (!_isNearModelBudget(i)) score += 1000;

    if (score > bestScore) {
      bestScore = score;
      bestIdx = i;
    }
  }

  _nextBestIndex = bestIdx;
  _nextBestScore = bestScore;
}

/** v2.0: 零延迟注入 — 使用Session Pool中的缓存token直接注入
 *  跳过Firebase登录(已缓存) → 指纹轮转 → 命令注入 → 会话过渡
 *  延迟: 约0.5-1s (vs 旧版2-5s) */
async function _injectCachedSession(context, index, session) {
  const t0 = Date.now();
  _activeIndex = index;
  context.globalState.update("wam-current-index", index);

  // 指纹轮转 (~50ms磁盘写入)
  const config = vscode.workspace.getConfiguration("wam");
  if (config.get("rotateFingerprint", true)) {
    _rotateFingerprintForSwitch();
    _hotResetCount++;
    await new Promise(r => setTimeout(r, 300)); // 等待磁盘写入
  }

  // 直接注入缓存的idToken (跳过Firebase登录!)
  let injected = false;
  try {
    const result = await vscode.commands.executeCommand(
      "windsurf.provideAuthTokenToAuthProvider",
      session.idToken,
    );
    if (!result?.error) {
      injected = true;
      _logInfo("ZERO_DELAY", `[CACHED_S0] #${index + 1} 注入成功 (${Date.now() - t0}ms)`);
    }
  } catch {}

  // 降级: discovered commands
  if (!injected) {
    const cmds = await _discoverAuthCommand();
    for (const cmd of cmds || []) {
      if (injected) break;
      try {
        const r = await vscode.commands.executeCommand(cmd, session.idToken);
        if (!r?.error) {
          injected = true;
          _logInfo("ZERO_DELAY", `[CACHED_S0_D] #${index + 1} via ${cmd} (${Date.now() - t0}ms)`);
        }
      } catch {}
    }
  }

  if (injected) {
    _zerodelaySwitchCount++;
    await _postInjectionRefresh();
    await _waitForSessionTransition();
    // 更新Session Pool中的apiKey(注入后Windsurf生成新apiKey)
    try {
      const newKey = auth?.readCurrentApiKey();
      if (newKey && newKey.length > 10) {
        session.apiKey = newKey;
        _cachedApiKey = newKey;
        _cachedApiKeyTs = Date.now();
      }
    } catch {}
    am.incrementLoginCount(index);
    _logInfo("ZERO_DELAY", `#${index + 1} 完成 (总${Date.now() - t0}ms, 零延迟#${_zerodelaySwitchCount})`);
  } else {
    // 完全回退: 走完整登录流程
    _fullLoginSwitchCount++;
    _logWarn("ZERO_DELAY", `#${index + 1} 缓存注入失败 → 回退完整登录`);
    await _loginToAccount(context, index);
  }
}

/** v2.0: 启动Session Pool引擎 — 定时刷新token + 定时并行探测 */
function _startSessionPoolEngine(context) {
  // 延迟5s初始化(等待proxy探测+基本启动完成)
  setTimeout(async () => {
    await _initSessionPool();

    // 定时刷新token (40min)
    _sessionPoolTimer = setInterval(() => {
      _refreshSessionTokens().catch(() => {});
    }, SESSION_REFRESH_MS);

    // 定时并行容量探测 (20s/8s)
    const scheduleMatrixProbe = () => {
      const ms = (_isBoost() || _burstMode) ? MATRIX_PROBE_FAST : MATRIX_PROBE_INTERVAL;
      _capacityMatrixTimer = setTimeout(async () => {
        try { await _probeAllCapacity(); } catch {}
        scheduleMatrixProbe();
      }, ms);
    };
    scheduleMatrixProbe();
  }, 5000);

  context.subscriptions.push({
    dispose: () => {
      if (_sessionPoolTimer) { clearInterval(_sessionPoolTimer); _sessionPoolTimer = null; }
      if (_capacityMatrixTimer) { clearTimeout(_capacityMatrixTimer); _capacityMatrixTimer = null; }
    }
  });
  _logInfo('SESSION_POOL', 'v2.0引擎已注册 (5s后初始化)');
}

/** v2.0: 获取统一容量字符串 (状态栏显示用) */
function _getUnifiedCapacityDisplay() {
  const u = _unifiedPool;
  if (u.totalCount === 0) return '?';
  if (u.totalRemaining > 0) {
    return `${u.totalRemaining}msg ${u.availableCount}/${u.totalCount}`;
  }
  return `${u.availableCount}/${u.totalCount}可用`;
}

/** v2.0: 全池是否还有可用容量 */
function _hasPoolCapacity() {
  return _unifiedPool.availableCount > 0 || _nextBestIndex >= 0;
}

// 根因突破: Windsurf workbench的rate limit分类器是死代码(GZt=Z=>!1)
const CAPACITY_CHECK_INTERVAL = 20000; // 正常容量检查间隔 20s
const CAPACITY_CHECK_FAST = 8000; // 活跃使用时快速检查 8s
const CAPACITY_PREEMPT_REMAINING = 2; // 剩余≤2条消息时提前切号
let _cachedApiKey = null; // 缓存当前session apiKey
let _cachedApiKeyTs = 0; // apiKey缓存时间戳
const APIKEY_CACHE_TTL = 120000; // apiKey缓存2min(注入后刷新)
let _lastCapacityCheck = 0; // 上次容量检查时间戳
let _lastCapacityResult = null; // 上次容量检查结果
let _capacityProbeCount = 0; // 本会话容量探测次数
let _capacityProbeFailCount = 0; // 连续失败次数(用于backoff)
let _capacitySwitchCount = 0; // 本会话因容量不足触发的切号次数
let _realMaxMessages = -1; // 服务端返回的真实消息上限(替代TIER_MSG_CAP_ESTIMATE)

/** 分类限流类型 — 四重闸门路由
 *  Gate 1/2: quota (D%/W%耗尽) → 账号切换 + 等日/周重置
 *  Gate 3: per_model (单模型桶满) → 模型变体轮转 → 账号切换 → 降级
 *  Gate 4: tier_cap (层级硬限) → 跳过模型轮转, 直接账号切换 + 3600s
 */
function _classifyRateLimit(errorText, contextKey) {
  if (!errorText && !contextKey) return 'unknown';
  const text = (errorText || '') + ' ' + (contextKey || '');
  // "Model provider unreachable" → 立即切号(可能是账号被封或模型访问受限)
  if (MODEL_UNREACHABLE_RE.test(text) || PROVIDER_ERROR_RE.test(text)) {
    return 'tier_cap'; // 当作tier_cap处理：直接换号
  }
  // Gate 4 特征: "no credits were used" + "upgrade to Pro" 或 "about an hour"
  if (TIER_RL_RE.test(text) || (UPGRADE_PRO_RE.test(text) && /rate\s*limit/i.test(text))) {
    return 'tier_cap';
  }
  if (ABOUT_HOUR_RE.test(text)) return 'tier_cap';
  // Gate 3 特征: "for this model" 或 模型级context key
  if (/for\s*this\s*model/i.test(text) || /model.*rate.*limit/i.test(text)) {
    return 'per_model';
  }
  if (contextKey && (contextKey.includes('modelRateLimited') || contextKey.includes('messageRateLimited'))) {
    return 'per_model';
  }
  // Gate 0: "Failed precondition" — 日配额耗尽 (gRPC code 9, 非code 8的rate limit)
  if (/failed\s*precondition/i.test(text)) return 'quota';
  // Gate 1/2 特征: "quota" 相关
  if (/quota/i.test(text) && /exhaust|exceed|exhausted/i.test(text)) return 'quota';
  if (contextKey && contextKey.includes('quota')) return 'quota';
  // 高概率为per-model rate limit(Opus桶容量最小,最容易触发)
  // 防止这些通用key落入'unknown'导致Gate 3 handler被跳过
  if (contextKey && (contextKey.includes('permissionDenied') || contextKey.includes('rateLimited'))) {
    const model = _currentModelUid || _readCurrentModelUid();
    if (_isOpusModel(model) || _isSonnetThinking1MModel(model)) return 'per_model'; // v3.5.0
  }
  return 'unknown';
}

/** 追踪每小时消息数(用于Gate 4预测) */
function _trackHourlyMsg() {
  _hourlyMsgLog.push({ ts: Date.now() });
  const cutoff = Date.now() - HOUR_WINDOW;
  _hourlyMsgLog = _hourlyMsgLog.filter(m => m.ts > cutoff);
}

/** 获取当前小时消息数 */
function _getHourlyMsgCount() {
  const cutoff = Date.now() - HOUR_WINDOW;
  return _hourlyMsgLog.filter(m => m.ts > cutoff).length;
}

/** 判断是否接近Gate 4层级上限 */
function _isNearTierCap() {
  return _getHourlyMsgCount() >= TIER_MSG_CAP_ESTIMATE * TIER_CAP_WARN_RATIO;
}

/** v7.5 Gate 4: 账号层级硬限处理 — 跳过模型轮转, 直接账号切换
 *  与_handlePerModelRateLimit的关键区别: Gate 4是账号级, 换模型无效 */
async function _handleTierRateLimit(context, resetSeconds) {
  _tierRateLimitCount++;
  const logPrefix = `[TIER_RL #${_tierRateLimitCount}]`;
  _logWarn('TIER_RL', `${logPrefix} Gate 4 账号层级硬限! hourly=${_getHourlyMsgCount()}, reset=${resetSeconds}s`);
  // 标记当前账号 — 3600s冷却("about an hour")
  const cooldown = resetSeconds || 3600;
  am.markRateLimited(_activeIndex, cooldown, {
    model: 'all',
    trigger: 'tier_rate_limit',
    type: 'tier_cap',
  });
  _pushRateLimitEvent({ type: 'tier_cap', trigger: 'tier_rate_limit', cooldown, hourlyMsgs: _getHourlyMsgCount() });
  // 直接账号轮转(跳过模型变体轮转 — 对Gate 4无效)
  _activateBoost();
  await _doPoolRotate(context, true);
  _scheduleAutoRetry(); // v3.9.0: Gate 4切号后自动重试(根因修复)
  // 重置小时计数器(新账号从0开始)
  _hourlyMsgLog = [];
  return { action: 'tier_account_switch', cooldown };
}

/** v8.0 核心: Per-model rate limit 三级突破 (Opus优化版)
 *  Opus路径(v8.0): 跳过L1变体轮转(同桶无效) → 直接L2账号切换 → L3降级Sonnet
 *  非Opus路径: L1变体轮转 → L2账号切换 → L3降级
 *  核心洞察: Opus 6变体共享同一服务端rate limit桶(同底层API) → L1变体轮转=浪费5+秒
 */
async function _handlePerModelRateLimit(context, modelUid, resetSeconds) {
  _modelRateLimitCount++;
  const logPrefix = `[MODEL_RL #${_modelRateLimitCount}]`;
  // Opus使用专用冷却时间(2400s/40min)，匹配实测"Resets in: 39m2s"(2342s)+安全余量
  const effectiveCooldown = _isOpusModel(modelUid) ? Math.max(resetSeconds || 0, OPUS_COOLDOWN_DEFAULT) : _isSonnetThinking1MModel(modelUid) ? Math.max(resetSeconds || 0, OPUS_COOLDOWN_DEFAULT) : (resetSeconds || 1200); // v3.5.0
  _logWarn('MODEL_RL', `${logPrefix} 检测到per-model rate limit: model=${modelUid}, resets=${resetSeconds}s, effectiveCooldown=${effectiveCooldown}s`);

  // 保存当前账号信息用于后台精化探测(Layer1默认冷却时后台gRPC更新实际重置时间)
  const _prevRLIdx = _activeIndex;
  const _prevRLKey = _getCachedApiKey();

  // 标记当前(account, model)为limited — Opus时标记所有变体(共享桶)
  if (_isOpusModel(modelUid)) {
    for (const variant of OPUS_VARIANTS) {
      am.markModelRateLimited(_activeIndex, variant, effectiveCooldown, { trigger: 'per_model_rate_limit' });
    }
    // 重置该账号的Opus消息计数(已触发限流,计数器已失效)
    _resetModelMsgLog(_activeIndex);
  } else if (_isSonnetThinking1MModel(modelUid)) {
    // 0: Sonnet Thinking 1M变体共享桶 → 标记所有变体
    for (const variant of SONNET_VARIANTS) {
      am.markModelRateLimited(_activeIndex, variant, effectiveCooldown, { trigger: 'per_model_rate_limit' });
    }
    _resetModelMsgLog(_activeIndex);
  } else {
    am.markModelRateLimited(_activeIndex, modelUid, effectiveCooldown, { trigger: 'per_model_rate_limit' });
  }

  // 后台精化 — 2s后gRPC探测实际重置时间并更新冷却(Layer1用默认值时尤为重要)
  if (_isOpusModel(modelUid) && _prevRLKey && auth && resetSeconds <= OPUS_COOLDOWN_DEFAULT) {
    setTimeout(async () => {
      try {
        const probe = await auth.checkRateLimitCapacity(_prevRLKey, modelUid);
        if (probe && probe.resetsInSeconds > effectiveCooldown) {
          for (const v of OPUS_VARIANTS) {
            am.markModelRateLimited(_prevRLIdx, v, probe.resetsInSeconds, { trigger: 'opus_rl_bg_refine' });
          }
          _logInfo('MODEL_RL', `[BG_REFINE] #${_prevRLIdx+1} 冷却精化: ${effectiveCooldown}s → ${probe.resetsInSeconds}s (gRPC实测)`);
        }
      } catch {}
    }, 2000);
  }

  // === L1 跳过: 锚定本源模型不变 · 直接L2账号切换 (v17.1 热修复) ===
  // 道法自然: 变体切换 = 模型变化 = 偏离本源需求, 不可为

  // === L2: 换账号继续用同模型 (核心: 不同apiKey = 不同rate limit桶) ===
  const bestForModel = am.findBestForModel(modelUid, _activeIndex, PREEMPTIVE_THRESHOLD);
  if (bestForModel) {
    _logInfo('MODEL_RL', `${logPrefix} L2: 切换到账号#${bestForModel.index + 1}继续用${modelUid} (rem=${bestForModel.remaining})`);
    // 代理路由时跳过WAM切号(代理已处理per-model路由,无需切Windsurf会话)
    if (_isProxyRouting()) { _logInfo('MODEL_RL', '代理路由中, 跳过WAM per-model切号'); return { action: 'proxy_skip' }; }
    await _seamlessSwitch(context, bestForModel.index);
    _scheduleAutoRetry(); // v16.0: 切号后自动重试
    _pushRateLimitEvent({ type: 'per_model', trigger: 'opus_guard_reactive', model: modelUid, cooldown: effectiveCooldown, switchTo: bestForModel.index + 1 });
    return { action: 'account_switch', to: bestForModel.index, model: modelUid };
  }
  _logInfo('MODEL_RL', `${logPrefix} L2: 所有账号的${modelUid}都已限流,尝试L3`);

  // === L3: 锚定本源模型·纯账号轮转 (v17.0 热修复: 去除模型降级偏离) ===
  // 道法自然: 模型是本源需求, 不可因限流而偏离
  if (_isOpusModel(modelUid)) {
    _logWarn('MODEL_RL', `${logPrefix} L3: 锚定模型·纯账号轮转(不降级)`);
    await _doPoolRotate(context, true);
    _scheduleAutoRetry();
    return { action: 'account_rotate_anchored', model: modelUid };
  }

  // 非Opus模型: 直接账号轮转
  await _doPoolRotate(context, true);
  return { action: 'account_rotate', model: modelUid };
}

/** 切换Windsurf当前模型UID (写入state.vscdb windsurfConfigurations) */
async function _switchModelUid(targetUid) {
  if (!targetUid || Date.now() - _lastModelSwitch < 5000) return false;
  _lastModelSwitch = Date.now();
  try {
    // 通过VS Code命令切换模型
    await vscode.commands.executeCommand('windsurf.cascadeSetModel', targetUid);
    _currentModelUid = targetUid;
    _logInfo('MODEL_RL', `模型已切换到: ${targetUid}`);
    return true;
  } catch (e1) {
    // 备用: 直接写state.vscdb
    try {
      if (auth && auth.writeModelSelection) {
        auth.writeModelSelection(targetUid);
        _currentModelUid = targetUid;
        _logInfo('MODEL_RL', `模型已切换(DB直写): ${targetUid}`);
        return true;
      }
    } catch {}
    _logWarn('MODEL_RL', `模型切换失败: ${targetUid}`, e1.message);
    return false;
  }
}

// v3.9.0: 增强命令发现 + 缓存刷新(首次失败后重新扫描)
let _retryCmdDiscoveredAt = 0;
async function _discoverRetryCmd() {
  // 缓存有效期5min — 命令列表可能因扩展加载而变化
  if (_retryCmd !== undefined && _retryCmd !== null && (Date.now() - _retryCmdDiscoveredAt < 300000)) return _retryCmd;
  // 首次发现null → 强制重新扫描(命令可能延迟注册)
  if (_retryCmd === null && (Date.now() - _retryCmdDiscoveredAt < 10000)) return _retryCmd;
  try {
    const allCmds = await vscode.commands.getCommands(true);
    const candidates = [
      // v3.12: 已验证存在的Windsurf命令(workbench.js逆向扫描确认)
      ...allCmds.filter(c => c === 'windsurf.sendTextToChat'),
      ...allCmds.filter(c => c === 'windsurf.executeCascadeAction'),
      ...allCmds.filter(c => c === 'windsurf.sendChatActionMessage'),
      // Windsurf Cascade 重试/重发命令
      ...allCmds.filter(c => /cascade/i.test(c) && /re(?:try|send|generat|submit|run)/i.test(c)),
      ...allCmds.filter(c => /windsurf/i.test(c) && /re(?:try|send|generat|submit|run)/i.test(c)),
      ...allCmds.filter(c => /chat/i.test(c) && /re(?:try|send|generat|submit|run)/i.test(c)),
      // 更宽松: 任何含retry的命令
      ...allCmds.filter(c => /retry/i.test(c)),
    ];
    const seen = new Set();
    const unique = candidates.filter(c => { if (seen.has(c)) return false; seen.add(c); return true; });
    _retryCmd = unique[0] || null;
    _retryCmdDiscoveredAt = Date.now();
    _logInfo('RETRY', 'v3.9.0 retry cmd: found=' + _retryCmd + ' (all=' + unique.join(',') + ')');
  } catch (e) {
    _retryCmd = null;
    _retryCmdDiscoveredAt = Date.now();
    _logWarn('RETRY', 'retry command discovery failed', e.message);
  }
  return _retryCmd;
}

// v3.9.0 无感续传引擎 — 多重重试 + UI错误清除 + 验证闭环
let _autoRetryInFlight = false; // 防重入
let _autoRetrySuccessCount = 0; // 本会话成功重试次数
let _autoRetryFailCount = 0; // 本会话失败重试次数
let _lastSwitchTs = 0; // 最近一次切号时间戳(用于无感续传时间窗口)

/** v3.9.0 清除UI层rate limit错误残留
 *  道: 用户于无为 → 错误痕迹不应存留于五感
 *  解构: Windsurf对话框错误通过context key+Zustand状态双通道展现
 *    - context key: windsurf.messageRateLimited → Cascade面板内联错误横幅
 *    - Zustand: quota_exhausted → 面板底部配额警告条
 *    - 清除方式: setContext(key, false) + 触发UI刷新 */
async function _clearRateLimitUI() {
  const CLEAR_KEYS = [
    'chatQuotaExceeded', 'rateLimitExceeded', 'windsurf.quotaExceeded',
    'windsurf.rateLimited', 'cascade.rateLimited', 'windsurf.messageRateLimited',
    'windsurf.modelRateLimited', 'windsurf.permissionDenied',
  ];
  for (const key of CLEAR_KEYS) {
    try { await vscode.commands.executeCommand("setContext", key, false); } catch {}
  }
  // 尝试清除通知栏残留
  try { await vscode.commands.executeCommand("notifications.clearAll"); } catch {}
  _logInfo('RETRY', 'UI rate limit indicators cleared');
}

/** v3.9.0 多重重试引擎
 *  策略: 3次退避重试(1.5s→3s→6s) + 每次重试前清除UI错误 + 验证闭环
 *  道: 水遇石则绕 → 第一次不通则换路再试 */
function _scheduleAutoRetry(delayMs = 1500) {
  if (_autoRetryInFlight) { _logInfo("RETRY", "重试已在进行中, 跳过"); return; }
  _autoRetryInFlight = true;
  _lastSwitchTs = Date.now();
  const MAX_ATTEMPTS = 3;
  const BACKOFF = [delayMs, delayMs * 2, delayMs * 4];

  const attemptRetry = async (attempt) => {
    try {
      // Step 1: 清除UI层错误残留(让用户看不到错误)
      await _clearRateLimitUI();

      // Step 2: 发现重试命令
      const cmd = await _discoverRetryCmd();
      if (!cmd) {
        // 降级: 尝试直接发送空消息触发重新生成
        try {
          await vscode.commands.executeCommand("windsurf.sendTextToChat", "继续");
          _logInfo('RETRY', 'fallback: windsurf.cascade.resend executed');
          _autoRetrySuccessCount++;
          _autoRetryInFlight = false;
          return;
        } catch {}
        _logInfo('RETRY', 'no retry command found after ' + attempt + ' attempts');
        _autoRetryInFlight = false;
        _autoRetryFailCount++;
        return;
      }

      // Step 3: 执行重试 (v3.12: sendTextToChat需传参数)
      _logInfo('RETRY', `v3.12 attempt ${attempt}/${MAX_ATTEMPTS}: executing ${cmd}`);
      if (cmd === 'windsurf.sendTextToChat') {
        await vscode.commands.executeCommand(cmd, "继续");
      } else {
        await vscode.commands.executeCommand(cmd);
      }

      // Step 4: 验证 — 2s后检查context key是否已清除
      setTimeout(async () => {
        let stillLimited = false;
        try {
          stillLimited = await vscode.commands.executeCommand("getContext", "windsurf.messageRateLimited") || await vscode.commands.executeCommand("getContext", "windsurf.quotaExceeded") || await vscode.commands.executeCommand("getContext", "chatQuotaExceeded");
        } catch {}
        if (stillLimited && attempt < MAX_ATTEMPTS) {
          _logWarn('RETRY', `attempt ${attempt} 重试后仍限流, 退避重试 ${BACKOFF[attempt]}ms`);
          setTimeout(() => attemptRetry(attempt + 1), BACKOFF[attempt]);
        } else {
          _autoRetryInFlight = false;
          if (!stillLimited) {
            _autoRetrySuccessCount++;
            _logInfo('RETRY', `✅ 无感续传成功! attempt=${attempt} total_success=${_autoRetrySuccessCount}`);
          } else {
            _autoRetryFailCount++;
            _logWarn('RETRY', `❌ ${MAX_ATTEMPTS}次重试后仍限流, fail_count=${_autoRetryFailCount}`);
          }
        }
      }, 2000);

    } catch (e) {
      if (attempt < MAX_ATTEMPTS) {
        _logInfo('RETRY', `attempt ${attempt} failed: ${e.message}, retrying in ${BACKOFF[attempt]}ms`);
        setTimeout(() => attemptRetry(attempt + 1), BACKOFF[attempt]);
      } else {
        _autoRetryInFlight = false;
        _autoRetryFailCount++;
        _logInfo('RETRY', `all ${MAX_ATTEMPTS} attempts failed: ${e.message}`);
      }
    }
  };

  setTimeout(() => attemptRetry(1), BACKOFF[0]);
}
const HUB_PORT = 9870;
let _hubServer = null;

// v3.9.0 无感续传状态(暴露给Hub API /api/seamless-stats)
function _getSeamlessStats() {
  return {
    autoRetrySuccess: _autoRetrySuccessCount,
    autoRetryFail: _autoRetryFailCount,
    autoRetryInFlight: _autoRetryInFlight,
    lastSwitchTs: _lastSwitchTs,
    lastSwitchAgo: _lastSwitchTs ? Math.round((Date.now() - _lastSwitchTs) / 1000) + 's' : null,
    retryCmd: _retryCmd || 'not_discovered',
    tierRateLimitCount: _tierRateLimitCount,
    modelRateLimitCount: _modelRateLimitCount,
    zerodelaySwitchCount: _zerodelaySwitchCount,
    fullLoginSwitchCount: _fullLoginSwitchCount,
  };
}
const _ANTHROPIC = {
  "Claude Opus 4.6": { i: 5, o: 25 },
  "Claude Opus 4.6 1M": { i: 10, o: 37.5 },
  "Claude Opus 4.6 Thinking": { i: 5, o: 25 },
  "Claude Opus 4.6 Fast": { i: 5, o: 25 },
  "Claude Sonnet 4.6": { i: 3, o: 15 },
  "Claude Sonnet 4.6 1M": { i: 6, o: 22.5 },
  "Claude Sonnet 4.6 Thinking": { i: 3, o: 15 },
  "Claude Sonnet 4.6 Thinking 1M": { i: 6, o: 22.5 },
  "Claude Opus 4.5": { i: 5, o: 25 },
  "Claude Sonnet 4.5": { i: 3, o: 15 },
  "Claude Sonnet 4": { i: 3, o: 15 },
  "Claude Haiku 4.5": { i: 1, o: 5 },
  "Claude Opus 4.1": { i: 15, o: 75 },
};
const _ACU = {
  "Claude Opus 4.6": 6,
  "Claude Opus 4.6 1M": 10,
  "Claude Opus 4.6 Thinking": 8,
  "Claude Opus 4.6 Fast": 24,
  "Claude Sonnet 4.6": 4,
  "Claude Sonnet 4.6 1M": 12,
  "Claude Sonnet 4.6 Thinking": 6,
  "Claude Sonnet 4.6 Thinking 1M": 12,
  "Claude Opus 4.5": 4,
  "Claude Sonnet 4.5": 2,
  "Claude Sonnet 4": 2,
  "Claude Haiku 4.5": 1,
  "SWE-1.5": 0,
  "SWE-1.5 Fast": 0.5,
};
const _CNY = 7.25,
  _XIANYU = 4.5;

function _tokenCost(model, inTok, outTok) {
  const p = _ANTHROPIC[model] || _ANTHROPIC["Claude Sonnet 4.6"];
  const ic = (inTok / 1e6) * p.i,
    oc = (outTok / 1e6) * p.o;
  return {
    model,
    input_cost: +ic.toFixed(4),
    output_cost: +oc.toFixed(4),
    total_usd: +(ic + oc).toFixed(4),
    total_cny: +((ic + oc) * _CNY).toFixed(2),
  };
}

function _startHubServer() {
  // v3.11.2: hot-reload架构 — 每次加载更新可变handler引用，复用服务器时替换监听器
  _G.hubHandlerFn = _hubRequestHandler;
  if (_G.hubServerRef) {
    _hubServer = _G.hubServerRef;
    _G.hubServerRef = null;
    _hubServer.removeAllListeners('request');
    _hubServer.on('request', (req, res) => (_G.hubHandlerFn || _hubRequestHandler)(req, res));
    _logInfo('HUB', `Hub server reused (hot-reload) — :${HUB_PORT}`);
    return;
  }
  _doStartHubServer(0);
}
let _hubRetryTimer = null;

function _hubRequestHandler(req, res) {
      const url = new URL(req.url, `http://127.0.0.1:${HUB_PORT}`);
      const p = url.pathname.replace(/\/$/, "") || "/";
      const qs = Object.fromEntries(url.searchParams);
      const cors = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
      };
      const json = (data, code = 200) => {
        const b = JSON.stringify(data);
        res.writeHead(code, { "Content-Type": "application/json", ...cors });
        res.end(b);
      };

      if (req.method === "OPTIONS") {
        res.writeHead(204, cors);
        return res.end();
      }

      if (p === "/health")
        return json({
          status: "ok",
          version: "3.11.0",
          port: HUB_PORT,
          accounts: am ? am.getAll().length : 0,
          activeIndex: _activeIndex,
          routingMode: _routingMode,
          poolSource: _poolSourceMode,
          proxyOnline: _proxyOnline,
          proxyRouting: _isProxyRouting(),
          cloudPool: cloudPool ? cloudPool.getStatus() : null,
        });

      // v3.9.0
      if (p === "/api/seamless-stats") return json(_getSeamlessStats());
      if (p === "/api/conversation-map") return json(_getConversationMap());

      if (p === '/api/pool/clear-rate-limits') {
        if (am) {
          const _n = am.getAll().length;
          for (let _i = 0; _i < _n; _i++) am.clearRateLimit(_i);
          _logInfo('API', `clear-rate-limits: ${_n} accounts`);
          _updatePoolBar(); _refreshPanel();
          return json({ ok: true, cleared: _n });
        }
        return json({ ok: false, error: 'not ready' });
      }
      if (p === "/api/pool/status") {
        const pool = am ? am.getPoolStats(PREEMPTIVE_THRESHOLD) : {};
        pool.activeIndex = _activeIndex;
        pool.switchCount = _switchCount;
        const _hubModel = _currentModelUid || _readCurrentModelUid();
        const _hubBudget = _getModelBudget(_hubModel);
        pool.modelGuard = {
          switchCount: _modelGuardSwitchCount,
          currentModel: _hubModel,
          isOpus: _isOpusModel(_hubModel),
          isSonnetT1M: _isSonnetThinking1MModel(_hubModel),
          msgsInWindow: _activeIndex >= 0 ? _getModelMsgCount(_activeIndex) : 0,
          budget: MODEL_BUDGET,
          windowMs: OPUS_BUDGET_WINDOW,
          cooldownDefault: OPUS_COOLDOWN_DEFAULT,
        };
        if (am && _activeIndex >= 0) {
          const a = am.get(_activeIndex);
          pool.activeEmail = a?.email;
          pool.activeRemaining = am.effectiveRemaining(_activeIndex);
          pool.activePlanDays = am.getPlanDaysRemaining(_activeIndex);
          pool.activeUrgency = am.getExpiryUrgency(_activeIndex);
        }
        // Window-account binding map
        const winState = _readWindowState();
        const windowMap = {};
        const now = Date.now();
        for (const [id, w] of Object.entries(winState.windows || {})) {
          if (now - w.lastHeartbeat <= WINDOW_DEAD_MS) {
            windowMap[id] = { accountIndex: w.accountIndex, email: w.accountEmail, pid: w.pid, isSelf: id === _windowId };
          }
        }
        pool.windows = windowMap;
        pool.windowCount = Object.keys(windowMap).length;
        // Effective pool metrics (本源推万法)
        pool.effectiveMetrics = {
          sumEffective: pool.sumEffective,
          avgEffective: pool.avgEffective,
          weeklyBottleneckCount: pool.weeklyBottleneckCount,
          weeklyBottleneckRatio: pool.weeklyBottleneckRatio,
          preResetWasteCount: pool.preResetWasteCount,
          preResetWasteTotal: pool.preResetWasteTotal,
        };
        // Layer 5 容量探测数据
        pool.capacityProbe = {
          lastResult: _lastCapacityResult,
          probeCount: _capacityProbeCount,
          failCount: _capacityProbeFailCount,
          switchCount: _capacitySwitchCount,
          realMaxMessages: _realMaxMessages,
          lastCheckTs: _lastCapacityCheck,
          intervalMs: (_isBoost() || _burstMode) ? CAPACITY_CHECK_FAST : CAPACITY_CHECK_INTERVAL,
        };
        // Watchdog stats
        pool.watchdog = {
          lastSuccessfulProbe: _lastSuccessfulProbe,
          timeSinceProbe: Math.round((Date.now() - _lastSuccessfulProbe) / 1000),
          timeout: WATCHDOG_TIMEOUT / 1000,
          switchCount: _watchdogSwitchCount,
          isArmed: (Date.now() - _lastSuccessfulProbe) > WATCHDOG_TIMEOUT && _capacityProbeFailCount >= 3,
        };
        return json(pool);
      }

      if (p === "/api/pool/accounts") {
        const all = am ? am.getAll() : [];
        const safe = all.map((a, i) => ({
          index: i,
          email: a.email,
          credits: a.credits,
          usage: a.usage,
          effective: am.effectiveRemaining(i),
          rateLimited: am.isRateLimited(i),
          expired: am.isExpired(i),
          planDays: am.getPlanDaysRemaining(i),
          urgency: am.getExpiryUrgency(i),
        }));
        return json({
          accounts: safe,
          total: safe.length,
          activeIndex: _activeIndex,
        });
      }

      if (p === "/api/quota/cached") {
        try {
          const c = auth?.readCachedQuota();
          return json(c || { error: "no cached quota" });
        } catch {
          return json({ error: "read failed" });
        }
      }

      if (p === "/api/token/cost") {
        const model = qs.model || "Claude Sonnet 4.6";
        const msgs = parseInt(qs.msgs || "30");
        const avgIn = parseInt(qs.input || "4000"),
          avgOut = parseInt(qs.output || "2000");
        const daily = _tokenCost(model, msgs * avgIn, msgs * avgOut);
        const mo = +(daily.total_usd * 30).toFixed(2);
        const xCny = +(mo * _CNY).toFixed(2);
        const ratio = +(xCny / _XIANYU).toFixed(1);
        return json({
          model,
          acu: _ACU[model] || 1,
          msgs_per_day: msgs,
          avg_input: avgIn,
          avg_output: avgOut,
          daily,
          monthly_usd: mo,
          monthly_cny: xCny,
          per_msg: +(daily.total_usd / msgs).toFixed(4),
          xianyu: {
            api_cny: xCny,
            xianyu_cny: _XIANYU,
            ratio,
            savings_pct:
              xCny > 0 ? +((1 - _XIANYU / xCny) * 100).toFixed(1) : 0,
          },
        });
      }

      if (p === "/api/token/pricing")
        return json({ pricing: _ANTHROPIC, acu: _ACU });
      if (p === "/api/token/xianyu") {
        const mo = parseFloat(qs.monthly_usd || "37.80"),
          xy = parseFloat(qs.xianyu_cny || String(_XIANYU));
        const ac = +(mo * _CNY).toFixed(2),
          r = +(ac / xy).toFixed(1);
        return json({
          api_usd: mo,
          api_cny: ac,
          xianyu_cny: xy,
          ratio: r,
          savings_cny: +(ac - xy).toFixed(2),
          savings_pct: ac > 0 ? +((1 - xy / ac) * 100).toFixed(1) : 0,
        });
      }

      if (p === "/api/logs") {
        const limit = parseInt(qs.limit || "50");
        return json({ logs: _eventLog.slice(-limit), total: _eventLog.length });
      }

      const _pb = () => new Promise(r => { let b=''; req.on('data',c=>b+=c); req.on('end',()=>{ try{r(JSON.parse(b||'{}'))}catch{r({})} }); });

      if (p === "/api/v2/unified") {
        const matrix = [];
        for (const [idx, cap] of _capacityMatrix.entries()) {
          const session = _sessionPool.get(idx);
          const account = am ? am.get(idx) : null;
          matrix.push({
            index: idx,
            email: account?.email,
            hasCapacity: cap.hasCapacity,
            messagesRemaining: cap.messagesRemaining,
            maxMessages: cap.maxMessages,
            resetsInSeconds: cap.resetsInSeconds,
            probedAt: cap.probedAt,
            hasSession: !!(session && session.healthy),
            rateLimited: am ? am.isRateLimited(idx) : false,
            expired: am ? am.isExpired(idx) : false,
            effective: am ? am.effectiveRemaining(idx) : null,
          });
        }
        return json({
          ok: true,
          unified: _unifiedPool,
          matrix,
          nextBest: { index: _nextBestIndex, score: _nextBestScore },
          sessionPool: {
            size: _sessionPool.size,
            initialized: _poolInitialized,
            authCount: _sessionPoolAuthCount,
            failCount: _sessionPoolFailCount,
          },
          matrixProbe: {
            count: _matrixProbeCount,
            errors: _matrixProbeErrors,
            interval: (_isBoost() || _burstMode) ? MATRIX_PROBE_FAST : MATRIX_PROBE_INTERVAL,
          },
          dispatch: {
            zerodelaySwitches: _zerodelaySwitchCount,
            fullLoginSwitches: _fullLoginSwitchCount,
            totalSwitches: _switchCount,
          },
          activeIndex: _activeIndex,
        });
      }

      if (p === "/api/v2/sessions") {
        const sessions = [];
        for (const [idx, session] of _sessionPool.entries()) {
          const account = am ? am.get(idx) : null;
          sessions.push({
            index: idx,
            email: account?.email,
            healthy: session.healthy,
            hasIdToken: !!session.idToken,
            hasApiKey: !!session.apiKey,
            expireTime: session.expireTime,
            expiresIn: session.expireTime > 0 ? Math.round((session.expireTime - Date.now()) / 1000) : -1,
            lastRefresh: session.lastRefresh,
            lastProbe: session.lastProbe,
            error: session.error,
            isActive: idx === _activeIndex,
          });
        }
        return json({ ok: true, sessions, poolInitialized: _poolInitialized, total: sessions.length });
      }

      if (req.method === "POST" && p === "/api/v2/reinit") {
        _poolInitialized = false;
        _sessionPool.clear();
        _capacityMatrix.clear();
        _initSessionPool().then(() => {
          json({ ok: true, poolSize: _sessionPool.size, matrixSize: _capacityMatrix.size });
        }).catch(e => json({ ok: false, error: e.message }, 500));
        return;
      }

      if (p === "/api/pool/active") {
        if (_activeIndex < 0 || !am) return json({ error: "no active" }, 404);
        const a = am.get(_activeIndex); const q = am.getActiveQuota ? am.getActiveQuota(_activeIndex) : null;
        return json({ ok: true, index: _activeIndex, email: a?.email, quota: q, plan: am.getPlanSummary ? am.getPlanSummary(_activeIndex) : null });
      }
      if (p === "/api/proxy/status") return json(auth ? { ok: true, ...auth.getProxyStatus() } : { ok: false, mode: "unknown" });
      if (p === "/api/proxy/deep") {
        // 查询透明代理底层状态 (v3.0 活水永续)
        _proxyApiForward('/api/deep').then(proxyResp => {
          json({ ok: true, engine: 'transparent-proxy-v3', ...proxyResp });
        }).catch(e => {
          json({ ok: false, engine: 'offline', error: e.message, hint: 'node scripts/transparent_proxy.js serve' });
        });
        return;
      }
      if (p === "/api/proxy/quota") {
        // 实时配额全景
        _proxyApiForward('/api/quota').then(proxyResp => {
          json({ ok: true, ...proxyResp });
        }).catch(e => {
          json({ ok: false, error: e.message });
        });
        return;
      }
      if (p === "/api/proxy/buckets") {
        _proxyApiForward('/api/buckets').then(r => json({ ok: true, ...r })).catch(e => json({ ok: false, error: e.message }));
        return;
      }
      if (p === "/api/proxy/routes") {
        _proxyApiForward('/api/routes').then(r => json({ ok: true, ...r })).catch(e => json({ ok: false, error: e.message }));
        return;
      }
      if (p === "/api/fingerprint") { try { return json({ ok: true, ids: readFingerprint() }); } catch (e) { return json({ ok: false, ids: {}, error: e.message }); } }
      if (p === "/api/window/state") return json({ ok: true, windowId: _windowId, ..._readWindowState() });
      if (p === "/api/account/export") return json({ version: 1, exportedAt: new Date().toISOString(), count: am ? am.count() : 0, accounts: am ? am.exportAll() : [] });

      if (req.method === "POST" && p === "/api/account/add") { _pb().then(d => {
        if (!d.email || !d.password) return json({ error: "email and password required" }, 400);
        if (am && am.findByEmail(d.email)) return json({ error: "duplicate", email: d.email }, 409);
        const ok = am ? am.add(d.email, d.password) : false;
        json({ ok, email: d.email });
      }); return; }

      if (req.method === "POST" && p === "/api/account/batch") { _pb().then(d => {
        if (!d.text) return json({ error: "text required" }, 400);
        const r = am ? am.addBatch(d.text) : { added: 0, skipped: 0, total: 0 };
        json({ ok: true, ...r });
      }); return; }

      if (req.method === "POST" && p === "/api/pool/set_active") { _pb().then(d => {
        if (d.index === undefined || d.index < 0) return json({ error: "index required" }, 400);
        _activeIndex = d.index;
        json({ ok: true, activeIndex: _activeIndex });
      }); return; }

      if (req.method === "POST" && p === "/api/proxy/reprobe") {
        if (!auth) return json({ error: "no auth" }, 500);
        auth.reprobeProxy().then(r => json({ ok: true, ...r })).catch(e => json({ error: e.message }, 500));
        return;
      }

      if (req.method === "POST" && p === "/api/proxy/mode") { _pb().then(d => {
        if (!d.mode || !['local','relay'].includes(d.mode)) return json({ error: "invalid mode, use 'local' or 'relay'" }, 400);
        if (auth) auth.setMode(d.mode);
        json({ ok: true, mode: d.mode });
      }); return; }

      if (req.method === "POST" && p === "/api/account/mark_rate_limited") { _pb().then(d => {
        const idx = d.index ?? _activeIndex;
        if (am) am.markRateLimited(idx, d.seconds || 3600, { trigger: 'hub_api' });
        json({ ok: true, index: idx });
      }); return; }

      if (req.method === "POST" && p === "/api/account/clear_rate_limit") { _pb().then(d => {
        const idx = d.index ?? _activeIndex;
        if (am) am.clearRateLimit(idx);
        json({ ok: true, index: idx });
      }); return; }

      if (req.method === "POST" && p === "/api/pool/refresh") { _pb().then(async d => {
        try {
          const limit = d.limit || 0;
          if (limit > 0) { for (let i = 0; i < Math.min(limit, am ? am.count() : 0); i++) { try { await _refreshOne(i); } catch {} } }
          else { await _refreshAll(); }
          json({ ok: true, stats: am ? am.getPoolStats(PREEMPTIVE_THRESHOLD) : {} });
        } catch (e) { json({ ok: false, error: e.message }, 500); }
      }); return; }

      if (req.method === "POST" && p === "/api/pool/rotate") { _pb().then(async () => {
        if (!am) return json({ ok: false, error: "no account manager" });
        const best = am.selectOptimal(_activeIndex, PREEMPTIVE_THRESHOLD, _getOtherWindowAccounts());
        if (best) {
          // Full seamless switch
          const prev = _activeIndex;
          try {
            await _seamlessSwitch(_G.ctx, best.index);
            json({ ok: true, from: prev, to: best.index, remaining: best.remaining, method: 'seamless' });
          } catch (e) {
            // Fallback to index-only if seamless fails
            _activeIndex = best.index;
            json({ ok: true, from: prev, to: best.index, remaining: best.remaining, method: 'index_only', warning: 'seamless failed: ' + e.message });
          }
        }
        else json({ ok: false, error: "no better account" });
      }); return; }

      // Dashboard
      if (p === "/" || p === "/dashboard") {
        const html = _hubDashboardHtml();
        res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
        return res.end(html);
      }

      if (p === "/api/hot/status") {
        return json({
          reloadCount: _G.reloadCount,
          registered: Array.from(_G.registered),
          viewRegistered: _G.viewRegistered,
          watcherActive: !!_G.watcher,
          hotDir: path.join(os.homedir(), '.wam-hot'),
          hotExists: fs.existsSync(path.join(os.homedir(), '.wam-hot', 'extension.js')),
        });
      }
      if (p === "/api/hot/reload") {
        try { _hotReload(); return json({ ok: true, reloadCount: _G.reloadCount }); }
        catch (e) { return json({ ok: false, error: e.message }, 500); }
      }
      if (req.method === "POST" && p === "/api/v1/pay-init") {
        _pb().then(async d => {
          if (!d || !cloudPool) return json({ ok: false, error: "pool not ready" });
          const r = await cloudPool.payInit(d.amount, d.note);
          return json(r);
        }).catch(e => json({ ok: false, error: e.message }));
        return;
      }
      if (p === "/api/v1/pay-status") {
        const qs2 = new URLSearchParams(url.search);
        const orderId = qs2.get("orderId") || "";
        if (!cloudPool) return json({ ok: false, error: "pool not ready" });
        cloudPool.payStatus(orderId).then(r => json(r)).catch(e => json({ ok: false, error: e.message }));
        return;
      }
      if (p === "/api/hot/snapshot") {
        return json({
          reloadCount: _G.reloadCount,
          hasSnapshot: !!_G.snapshot,
          snapshotAge: _G.snapshot ? Math.round((Date.now() - _G.snapshot.ts) / 1000) : null,
          hubServerReused: !_G.hubServerRef,
          sessionPoolSize: _sessionPool.size,
          capacityMatrixSize: _capacityMatrix.size,
          poolInitialized: _poolInitialized,
          activeIndex: _activeIndex,
          switchCount: _switchCount,
          statePreservation: {
            sessions: _sessionPool.size,
            matrix: _capacityMatrix.size,
            eventLog: _eventLog.length,
            windowId: _windowId,
            proxyOnline: _proxyOnline,
          },
        });
      }

      json({ error: "not found" }, 404);
}

function _doStartHubServer() {
  try {
    _hubServer = http.createServer(_hubRequestHandler);
    _hubServer.on("error", (e) => {
      if (e.code === "EADDRINUSE") {
        _logWarn("HUB", `port ${HUB_PORT} in use, retry in 3s...`);
        _hubServer = null;
        if (_hubRetryTimer) clearTimeout(_hubRetryTimer);
        _hubRetryTimer = setTimeout(() => _doStartHubServer(), 3000);
      } else _logError("HUB", "server error", e.message);
    });
    _hubServer.listen(HUB_PORT, "127.0.0.1", () => {
      _logInfo("HUB", `Hub API ready — http://127.0.0.1:${HUB_PORT}/`);
      if (_hubRetryTimer) { clearTimeout(_hubRetryTimer); _hubRetryTimer = null; }
    });
  } catch (e) {
    _logWarn("HUB", "start failed, retry in 3s", e.message);
    if (_hubRetryTimer) clearTimeout(_hubRetryTimer);
    _hubRetryTimer = setTimeout(() => _doStartHubServer(), 3000);
  }
}

function _hubDashboardHtml() {
  return `<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>WAM Hub</title><style>
*{margin:0;padding:0;box-sizing:border-box}body{font-family:system-ui,sans-serif;background:#0a0a1a;color:#e0e0e0;min-height:100vh}
.hd{background:linear-gradient(135deg,#1a1a3e,#2d1b69);padding:16px 24px;border-bottom:1px solid #333}
.hd h1{font-size:1.3em;background:linear-gradient(90deg,#00d4ff,#7b68ee);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.hd .s{color:#888;font-size:.8em;margin-top:2px}
.g{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px;padding:16px 24px}
.c{background:#12122a;border:1px solid #2a2a4a;border-radius:10px;padding:14px}
.c h3{color:#7b68ee;font-size:.8em;margin-bottom:8px;text-transform:uppercase;letter-spacing:1px}
.m{font-size:1.8em;font-weight:700;color:#00d4ff}.m.ok{color:#00ff88}.m.w{color:#ffa500}.m.d{color:#ff4444}
.sm{color:#888;font-size:.78em;margin-top:3px}
.bar{background:#1a1a3e;border-radius:4px;height:6px;margin:6px 0;overflow:hidden}
.bf{height:100%;border-radius:4px}.bf.g{background:linear-gradient(90deg,#00ff88,#00d4ff)}.bf.y{background:linear-gradient(90deg,#ffa500,#ffcc00)}.bf.r{background:linear-gradient(90deg,#ff4444,#ff6666)}
table{width:100%;border-collapse:collapse;font-size:.78em;margin-top:6px}th{color:#7b68ee;font-size:.75em;text-transform:uppercase;text-align:left;padding:4px 6px;border-bottom:1px solid #2a2a4a}td{padding:4px 6px;border-bottom:1px solid #151525}
.b{display:inline-block;padding:1px 6px;border-radius:3px;font-size:.7em;font-weight:600}.b.ok{background:#00ff8822;color:#00ff88}.b.w{background:#ffa50022;color:#ffa500}.b.e{background:#ff444422;color:#ff4444}.b.i{background:#00d4ff22;color:#00d4ff}
.fl{grid-column:1/-1}
.vd{text-align:center;padding:6px;margin-top:6px;border-radius:6px;background:#00ff8815;color:#00ff88;font-weight:700;font-size:.85em}
</style></head><body>
<div class="hd"><h1>WAM v2.0 \u2014 \u9053\u6cd5\u81ea\u7136\u00b7\u989d\u5ea6\u5f52\u4e00</h1><div class="s">Session Pool + Capacity Matrix + Unified Pool + Zero-Delay \u00b7 :${HUB_PORT}</div></div>
<div class="g" id="a"></div>
<script>
const P=${JSON.stringify(_ANTHROPIC)};
const A=${JSON.stringify(_ACU)};
const CN=7.25,XY=4.5;
function f$(v){return v<0.01?'<$0.01':'$'+v.toFixed(v<1?4:2)}
function fY(v){return v<0.01?'<\\u00a50.01':'\\u00a5'+v.toFixed(2)}
function fK(v){return v>=1e6?(v/1e6).toFixed(1)+'M':v>=1e3?(v/1e3).toFixed(1)+'K':v.toString()}
async function ld(){
  const[s,ac,q,tc,v2]=await Promise.all([
    fetch('/api/pool/status').then(r=>r.json()).catch(()=>({})),
    fetch('/api/pool/accounts').then(r=>r.json()).catch(()=>({accounts:[]})),
    fetch('/api/quota/cached').then(r=>r.json()).catch(()=>({})),
    fetch('/api/token/cost').then(r=>r.json()).catch(()=>({})),
    fetch('/api/v2/unified').then(r=>r.json()).catch(()=>({unified:{},matrix:[],sessionPool:{},dispatch:{}})),
  ]);
  const u=v2.unified||{},sp=v2.sessionPool||{},dp=v2.dispatch||{},nb=v2.nextBest||{};
  const mx=v2.matrix||[];
  let html='';

  // Unified Capacity Pool (hero card)
  const uRem=u.totalRemaining||0,uMax=u.totalMax||1,uPct=uMax>0?Math.round(uRem/uMax*100):0;
  const uC=uPct>50?'ok':uPct>20?'w':'d';
  html+='<div class="c fl" style="background:linear-gradient(135deg,#0d1117,#1a1040);border:1px solid #7b68ee44"><h3>\\ud83d\\udd2e Unified Capacity Pool</h3>';
  html+='<div style="display:flex;gap:20px;align-items:center"><div style="flex:1">';
  html+='<div class="m '+uC+'" style="font-size:2.2em">'+uRem+'<span style="font-size:.4em;color:#888"> msg</span></div>';
  html+='<div class="bar" style="height:8px"><div class="bf '+(uPct>50?'g':uPct>20?'y':'r')+'" style="width:'+uPct+'%"></div></div>';
  html+='<div class="sm">'+uRem+'/'+uMax+' messages | '+(u.availableCount||0)+' avail / '+(u.limitedCount||0)+' limited / '+(u.totalCount||0)+' total</div>';
  html+='</div><div style="text-align:center;min-width:120px">';
  html+='<div style="font-size:2em;font-weight:700;color:#7b68ee">'+(u.throughput||0)+'</div><div class="sm">msg/hour throughput</div>';
  html+='<div style="font-size:1.4em;font-weight:700;color:#00d4ff;margin-top:4px">'+(u.utilization||0)+'%</div><div class="sm">utilization</div>';
  html+='</div></div></div>';

  // Session Pool + Dispatch
  html+='<div class="c"><h3>Session Pool</h3><div class="m ok">'+(sp.size||0)+'</div>';
  html+='<div class="sm">'+(sp.authCount||0)+' auth / '+(sp.failCount||0)+' fail</div>';
  html+='<div class="sm" style="margin-top:4px">Initialized: '+(sp.initialized?'\\u2705':'\\u23f3')+'</div></div>';

  html+='<div class="c"><h3>Zero-Delay Dispatch</h3><div class="m" style="color:#7b68ee">'+(dp.zerodelaySwitches||0)+'</div>';
  html+='<div class="sm">zero-delay / '+(dp.fullLoginSwitches||0)+' full-login / '+(dp.totalSwitches||0)+' total</div>';
  if(nb.index>=0){html+='<div class="sm" style="margin-top:4px;color:#00ff88">Next: #'+(nb.index+1)+' (score:'+nb.score+')</div>';}
  html+='</div>';

  // Pool Health
  const h=s.health||0,hc=h>70?'ok':h>30?'w':'d';
  html+='<div class="c"><h3>Pool Health</h3><div class="m '+hc+'">'+h+'%</div>';
  html+='<div class="bar"><div class="bf '+(h>70?'g':h>30?'y':'r')+'" style="width:'+h+'%"></div></div>';
  html+='<div class="sm">'+(s.available||0)+' avail / '+(s.total||0)+' total | Switches: '+(s.switchCount||0)+'</div></div>';

  // Active Account
  html+='<div class="c"><h3>Active</h3><div class="m">#'+((s.activeIndex>=0?s.activeIndex+1:'?'))+'</div>';
  html+='<div class="sm">'+(s.activeEmail||'-')+' | rem: '+(s.activeRemaining!=null?s.activeRemaining:'?')+'</div></div>';

  // Capacity Matrix (per-account L5 data)
  if(mx.length>0){
    html+='<div class="c fl"><h3>\\ud83d\\udcca Capacity Matrix ('+mx.length+' accounts)</h3>';
    html+='<table><tr><th>#</th><th>Email</th><th>Capacity</th><th>Remaining</th><th>Session</th><th>Status</th></tr>';
    mx.forEach(function(m){
      var capIcon=m.hasCapacity?'\\u2705':'\\ud83d\\udeab';
      var remStr=m.messagesRemaining>=0?m.messagesRemaining+'/'+m.maxMessages:'?';
      var sessIcon=m.hasSession?'\\ud83d\\udd11':'\\u274c';
      var st=m.rateLimited?'<span class=\"b e\">Limited</span>':m.expired?'<span class=\"b e\">Expired</span>':m.hasCapacity?'<span class=\"b ok\">Ready</span>':'<span class=\"b w\">Empty</span>';
      html+='<tr><td>'+(m.index+1)+'</td><td>'+(m.email||'?').split('@')[0]+'</td><td>'+capIcon+'</td><td>'+remStr+'</td><td>'+sessIcon+'</td><td>'+st+'</td></tr>';
    });
    html+='</table></div>';
  }

  // Account list (fallback if no matrix)
  const al=ac.accounts||[];
  if(al.length>0 && mx.length===0){
    html+='<div class="c fl"><h3>Accounts ('+al.length+')</h3><table><tr><th>#</th><th>Email</th><th>Quota</th><th>Status</th></tr>';
    al.forEach(function(a){
      var r=a.effective!=null?a.effective:'?',ia=a.index===s.activeIndex,rl=a.rateLimited;
      var bg=ia?'<span class="b ok">Active</span>':rl?'<span class="b e">Limited</span>':(r!=='?'&&r<=15?'<span class="b w">Low</span>':'<span class="b i">Ready</span>');
      html+='<tr><td>'+(a.index+1)+'</td><td>'+a.email+'</td><td>'+r+'</td><td>'+bg+'</td></tr>';
    });
    html+='</table></div>';
  }
  document.getElementById('a').innerHTML=html;
}
ld();setInterval(ld,10000);
</script></body></html>`;
}

function _log(level, tag, msg, data) {
  const ts = new Date().toLocaleTimeString();
  const prefix = `[${ts}] [${level}] [${tag}]`;
  const full =
    data !== undefined
      ? `${prefix} ${msg} ${JSON.stringify(data)}`
      : `${prefix} ${msg}`;
  // OutputChannel (用户可见)
  if (_outputChannel) _outputChannel.appendLine(full);
  // Console (开发者工具)
  if (level === "ERROR") console.error(`WAM: ${full}`);
  else console.log(`WAM: ${full}`);
  // 事件缓冲 (诊断用)
  _eventLog.push({
    ts: Date.now(),
    level,
    tag,
    msg: data !== undefined ? `${msg} ${JSON.stringify(data)}` : msg,
  });
  if (_eventLog.length > MAX_EVENT_LOG)
    _eventLog = _eventLog.slice(-MAX_EVENT_LOG);
}
function _logInfo(tag, msg, data) {
  _log("INFO", tag, msg, data);
}
function _logWarn(tag, msg, data) {
  _log("WARN", tag, msg, data);
}
function _logError(tag, msg, data) {
  _log("ERROR", tag, msg, data);
}

function _isBoost() {
  return Date.now() < _boostUntil;
}
function _activateBoost() {
  _boostUntil = Date.now() + BOOST_DURATION;
}

// 原理: 每个Windsurf窗口是独立VS Code进程，号池引擎各自独立运行。
// 若不协调，所有窗口选同一"最优"账号 → N窗口×1账号 = N倍消耗 → rate limit命中加速。

function _getWindowStatePath() {
  const appdata =
    process.env.APPDATA || path.join(os.homedir(), "AppData", "Roaming");
  return path.join(
    appdata,
    "Windsurf",
    "User",
    "globalStorage",
    WINDOW_STATE_FILE,
  );
}

let _cachedWindowState = null; // 内存缓存，减少磁盘读取
let _cacheTs = 0;
const CACHE_TTL = 5000; // 缓存5s有效

function _readWindowState(forceRefresh = false) {
  if (
    !forceRefresh &&
    _cachedWindowState &&
    Date.now() - _cacheTs < CACHE_TTL
  ) {
    return JSON.parse(JSON.stringify(_cachedWindowState)); // 返回深拷贝防止外部修改
  }
  try {
    const p = _getWindowStatePath();
    if (!fs.existsSync(p)) return { windows: {} };
    const state = JSON.parse(fs.readFileSync(p, "utf8"));
    _cachedWindowState = state;
    _cacheTs = Date.now();
    return JSON.parse(JSON.stringify(state));
  } catch {
    return { windows: {} };
  }
}

function _writeWindowState(state) {
  try {
    const p = _getWindowStatePath();
    // 原子写入: 写临时文件 → rename，防止并发写入导致JSON损坏
    const tmp = p + ".tmp." + process.pid;
    fs.writeFileSync(tmp, JSON.stringify(state, null, 2), "utf8");
    fs.renameSync(tmp, p);
    _cachedWindowState = state;
    _cacheTs = Date.now();
  } catch (e) {
    // rename失败时降级为直写
    try {
      fs.writeFileSync(
        _getWindowStatePath(),
        JSON.stringify(state, null, 2),
        "utf8",
      );
    } catch {}
    _logWarn("WINDOW", "atomic write failed, used fallback", e.message);
  }
}

function _registerWindow(accountIndex) {
  _windowId = `w${process.pid}-${Date.now().toString(36)}`;
  const state = _readWindowState(true);
  const account = am ? am.get(accountIndex) : null;
  state.windows[_windowId] = {
    accountIndex,
    accountEmail: account?.email || null,
    lastHeartbeat: Date.now(),
    pid: process.pid,
    startedAt: Date.now(),
  };
  _writeWindowState(state);
  _logInfo("WINDOW", `registered ${_windowId} → #${accountIndex + 1} (${account?.email?.split('@')[0] || '?'})`);
}

function _heartbeatWindow() {
  if (!_windowId) return;
  const state = _readWindowState();
  if (!state.windows[_windowId]) {
    state.windows[_windowId] = { pid: process.pid, startedAt: Date.now() };
  }
  state.windows[_windowId].accountIndex = _activeIndex;
  state.windows[_windowId].accountEmail = am?.get(_activeIndex)?.email || null;
  state.windows[_windowId].lastHeartbeat = Date.now();
  const now = Date.now();
  for (const [id, w] of Object.entries(state.windows)) {
    if (now - w.lastHeartbeat > WINDOW_DEAD_MS) delete state.windows[id];
  }
  _writeWindowState(state);
}

function _deregisterWindow() {
  if (!_windowId) return;
  try {
    const state = _readWindowState(true); // 注销时强制刷新
    delete state.windows[_windowId];
    _writeWindowState(state);
    _logInfo("WINDOW", `deregistered ${_windowId}`);
  } catch {}
}

/** 获取其他活跃窗口占用的账号索引 */
function _getOtherWindowAccounts() {
  if (!_windowId) return [];
  const state = _readWindowState();
  const now = Date.now();
  const claimed = [];
  for (const [id, w] of Object.entries(state.windows)) {
    if (id === _windowId) continue;
    if (now - w.lastHeartbeat > WINDOW_DEAD_MS) continue;
    if (w.accountIndex >= 0) claimed.push(w.accountIndex);
  }
  return claimed;
}

/** 获取活跃窗口数(含自身) */
function _getActiveWindowCount() {
  const state = _readWindowState();
  const now = Date.now();
  return Object.values(state.windows).filter(
    (w) => now - w.lastHeartbeat <= WINDOW_DEAD_MS,
  ).length;
}

function _startWindowCoordinator(context) {
  _registerWindow(_activeIndex);
  _windowTimer = setInterval(() => _heartbeatWindow(), WINDOW_HEARTBEAT_MS);
  context.subscriptions.push({
    dispose: () => {
      if (_windowTimer) {
        clearInterval(_windowTimer);
        _windowTimer = null;
      }
      _deregisterWindow();
    },
  });
  const winCount = _getActiveWindowCount();
  _logInfo("WINDOW", `coordinator started — ${winCount} active window(s)`);
  if (winCount > 1) {
    const others = _getOtherWindowAccounts();
    _logInfo(
      "WINDOW",
      `other windows claim accounts: [${others.map((i) => "#" + (i + 1)).join(", ")}]`,
    );
  }
}

/** 探测当前窗口活跃Cascade对话数
 *  策略: 多层探测，取最高值
 */
function _detectCascadeTabs() {
  const now = Date.now();
  if (now - _lastTabCheck < TAB_CHECK_INTERVAL) return _cascadeTabCount;
  _lastTabCheck = now;

  let count = 0;
  try {
    // L1: tabGroups API — 精确枚举所有打开的tab
    if (vscode.window.tabGroups) {
      for (const group of vscode.window.tabGroups.all) {
        for (const tab of group.tabs) {
          // Cascade tabs have specific viewType or label patterns
          const label = (tab.label || "").toLowerCase();
          const inputUri =
            tab.input && tab.input.uri ? tab.input.uri.toString() : "";
          if (
            label.includes("cascade") ||
            label.includes("chat") ||
            inputUri.includes("cascade") ||
            inputUri.includes("chat") ||
            (tab.input &&
              tab.input.viewType &&
              /cascade|chat|copilot/i.test(tab.input.viewType))
          ) {
            count++;
          }
        }
      }
    }
  } catch {}

  // L2: 如果tabGroups检测不到，用活跃编辑器数做保守估计
  // (用户通常每个Tab对应一个并行任务，多个可见编辑器≈多个并行对话)
  if (count === 0) {
    try {
      const visibleEditors = vscode.window.visibleTextEditors.length;
      // 保守估计: 至少有1个cascade tab (我们知道有因为检测到了rate limit)
      if (visibleEditors > 1)
        count = Math.max(1, Math.floor(visibleEditors / 2));
    } catch {}
  }

  // L3: context key探测 — 如果任何quota/rate context key为true，至少1个活跃对话
  if (count === 0) count = 1; // 至少1个(插件本身在运行)

  const prev = _cascadeTabCount;
  _cascadeTabCount = count;
  if (count !== prev) {
    _logInfo(
      "TABS",
      `Cascade tab count: ${prev} → ${count}${count > CONCURRENT_TAB_SAFE ? " ⚠️ BURST RISK" : ""}`,
    );
    // 进入/退出burst防护模式
    if (count > CONCURRENT_TAB_SAFE && !_burstMode) {
      _burstMode = true;
      _activateBoost(); // 立即加速轮询
      _logWarn(
        "TABS",
        `BURST MODE ON — ${count} concurrent tabs detected, accelerating poll & preemptive rotation`,
      );
    } else if (count <= CONCURRENT_TAB_SAFE && _burstMode) {
      _burstMode = false;
      _logInfo("TABS", "BURST MODE OFF — safe concurrency level");
    }
  }
  return count;
}

/** 记录一次消息/请求事件(每次quota变化≈一次API消息) */
function _trackMessageRate() {
  _msgRateLog.push({ ts: Date.now() });
  // 清理过期记录
  const cutoff = Date.now() - MSG_RATE_WINDOW;
  _msgRateLog = _msgRateLog.filter((m) => m.ts > cutoff);
}

/** 获取当前消息速率(条/分钟) */
function _getCurrentMsgRate() {
  const cutoff = Date.now() - MSG_RATE_WINDOW;
  const recent = _msgRateLog.filter((m) => m.ts > cutoff);
  return recent.length; // 直接等于条/分钟(窗口是60s)
}

/** 判断是否接近消息速率上限 */
function _isNearMsgRateLimit() {
  const rate = _getCurrentMsgRate();
  const tabAdjustedLimit = Math.max(
    3,
    MSG_RATE_LIMIT / Math.max(1, _cascadeTabCount),
  );
  return rate >= tabAdjustedLimit * BURST_DETECT_THRESHOLD;
}

/** 获取当前最优轮询间隔(自适应: 正常→加速→burst) */
function _getAdaptivePollMs() {
  if (_burstMode) return POLL_BURST;
  if (_isBoost()) return POLL_BOOST;
  return POLL_NORMAL;
}

function activate(context) {
  try {
    _activate(context);
  } catch (e) {
    _logError("ACTIVATE", "activation failed", e.message);
  }
}

function _activate(context) {
  const isHotRestart = _G.reloadCount > 0 && _G.snapshot;
  if (isHotRestart) {
    _restoreState(); // 从_G.snapshot恢复所有运行时变量
  }

  _outputChannel = vscode.window.createOutputChannel("WAM 号池引擎");
  context.subscriptions.push(_outputChannel);
  _logInfo(
    "BOOT",
    isHotRestart
      ? `无感号池引擎 v3.11.0 热重载恢复 (hot#${_G.reloadCount}, 状态已恢复, ${_sessionPool.size}sessions, ${_capacityMatrix.size}matrix)`
      : "无感号池引擎 v3.11.0 启动 (道法自然·万法归宗 · Session Pool · Capacity Matrix · 零延迟切换 · 状态不灭热重载)",
  );

  // v5.1 道法自然: 自动检测 workbench.js 补丁，异步应用 (消除手动 python ws_repatch.py)
  // RC-FIX: config file 自发现路径 + exec异步不阻塞activation
  if (!isHotRestart) {
    setTimeout(() => {
      try {
        const wbPath = 'D:\\Windsurf\\resources\\app\\out\\vs\\workbench\\workbench.desktop.main.js';
        if (!fs.existsSync(wbPath)) return;
        const wb = fs.readFileSync(wbPath, 'utf8');
        const needsBase = !wb.includes('globalThis.__wamRateLimit');
        const needsP7 = !wb.includes('failed.precondition|quota.exhaust');
        if (!needsBase && !needsP7) {
          _logInfo('PATCH', 'workbench.js patches OK (incl. Patch7 quota exhausted)');
          return;
        }
        const reason = needsBase ? 'GBe interceptor' : 'Patch7(quota regex)';
        _logWarn('PATCH', 'workbench.js needs: ' + reason + ' — locating ws_repatch.py...');
        // 路径自发现: 1)看门狗写入的config file 2)常用候选路径
        const cfgPath = path.join(os.homedir(), '.wam-hot', 'patch_info.json');
        let patchPy = null;
        if (fs.existsSync(cfgPath)) {
          try { patchPy = JSON.parse(fs.readFileSync(cfgPath, 'utf8')).patchScript; } catch (_e) {}
        }
        if (!patchPy || !fs.existsSync(patchPy)) {
          // 确定路径候选 (本机绝对路径 + homedir fallback)
          const fixed = 'e:\\' + '\u9053\\\u9053\u751f\u4e00\\\u4e00\u751f\u4e8c\\Windsurf\u65e0\u9650\u989d\u5ea6\\ws_repatch.py';
          const candidates = [fixed, path.join(os.homedir(), '.wam-hot', 'ws_repatch.py')];
          patchPy = candidates.find(p => fs.existsSync(p)) || null;
        }
        if (!patchPy) {
          _logWarn('PATCH', 'ws_repatch.py not found — run manually: python ws_repatch.py --force');
          return;
        }
        _logInfo('PATCH', 'auto-patching via ' + patchPy);
        const { exec } = require('child_process');
        exec('python "' + patchPy + '" --force', { timeout: 60000 }, (err) => {
          if (err) _logWarn('PATCH', 'auto-patch failed: ' + String(err.message).slice(0, 80));
          else {
            _logInfo('PATCH', 'workbench.js auto-patched. Showing reload notification...');
            vscode.window.showInformationMessage(
              'WAM: workbench.js 补丁已应用。需要重载WindowReload生效。',
              '立即重载'
            ).then(sel => { if (sel) vscode.commands.executeCommand('workbench.action.reloadWindow'); });
          }
        });
      } catch (e) {
        _logWarn('PATCH', 'auto-patch check error: ' + e.message);
      }
    }, 5000);
  }

  // 指纹完整性
  if (!isHotRestart) {
    try {
      const r = ensureFingerprintComplete();
      if (r.fixed.length > 0) _logInfo("FP", `completed: ${r.fixed.join(", ")}`);
    } catch (e) {
      _logWarn("FP", "ensureComplete skipped", e.message);
    }
  }

  const storagePath = context.globalStorageUri.fsPath;
  am = new AccountManager(storagePath);
  auth = new AuthService(storagePath);
  am.startWatching();

  statusBar = vscode.window.createStatusBarItem(
    vscode.StatusBarAlignment.Right,
    100,
  );
  statusBar.command = "wam.openPanel";
  statusBar.tooltip = "号池管理 · 点击查看";
  context.subscriptions.push(statusBar);

  // 恢复状态 (热重载时已由_restoreState恢复, 跳过globalState读取)
  if (!isHotRestart) {
    const savedIndex = context.globalState.get("wam-current-index", -1);
    const accounts = am.getAll();
    if (savedIndex >= 0 && savedIndex < accounts.length)
      _activeIndex = savedIndex;
  }
  _updatePoolBar();
  statusBar.show();

  // 恢复代理模式
  const savedMode = context.globalState.get("wam-proxy-mode", null);
  if (savedMode) auth.setMode(savedMode);

  // 恢复路由模式 (热重载时已恢复, 但仍从globalState兜底)
  if (!isHotRestart) {
    const savedRouting = context.globalState.get("wam-routing-mode", null);
    if (savedRouting && ['local', 'cloud', 'hybrid'].includes(savedRouting)) {
      _routingMode = savedRouting;
    }
  }

  const cfg3 = vscode.workspace.getConfiguration("wam");
  if (!isHotRestart) {
    _poolSourceMode = cfg3.get("poolSource", "local");
  }
  cloudPool = new CloudPoolClient();
  _logInfo("MODE", `号池来源: ${_poolSourceMode} | 路由: ${_routingMode}${isHotRestart ? ' (hot-restored)' : ''}`);

  // 后台云端健康检查 + 空池自动拉取(非阻塞) — 热重载时也检查(恢复云端状态)
  if (_poolSourceMode !== 'local' || isHotRestart) {
    setTimeout(async () => {
      try {
        const h = await cloudPool.checkHealth();
        _logInfo("CLOUD", `云端号池: ${h.online ? '✅在线' : '⚠离线'} ${h.online ? `(${h.available}/${h.accounts}可用)` : (h.error || '')}`);
        _updatePoolBar(); _refreshPanel();
        // cloud/hybrid模式 + 本地号池为空 → 自动从云端拉取账号
        if (h.online && am && am.count() === 0) {
          _logInfo("CLOUD", "本地号池为空，自动从云端拉取账号...");
          const pull = await _cloudPullFallback();
          if (pull.ok) {
            _logInfo("CLOUD", `启动拉取成功: ${pull.email?.split('@')[0]}***`);
            _updatePoolBar();
            _refreshPanel();
          }
        }
      } catch {}
    }, 3000);
  }

  // 定期云端同步(hybrid/cloud模式)
  if (_poolSourceMode !== 'local') {
    _cloudSyncTimer = setInterval(() => _cloudSyncHealth().catch(() => {}), CLOUD_SYNC_INTERVAL);
    context.subscriptions.push({ dispose: () => { if (_cloudSyncTimer) { clearInterval(_cloudSyncTimer); _cloudSyncTimer = null; } } });
  }

  // 远程管理请求轮询 (道之安全 · 客户端审批)
  if (cloudPool) {
    _remoteApprovalTimer = setInterval(() => _pollRemoteApproval().catch(() => {}), REMOTE_POLL_INTERVAL);
    context.subscriptions.push({ dispose: () => { if (_remoteApprovalTimer) { clearInterval(_remoteApprovalTimer); _remoteApprovalTimer = null; } } });
  }

  // 后台代理探测 + 透明代理健康检查
  setTimeout(() => {
    if (!auth) return;
    auth
      .reprobeProxy()
      .then((r) => {
        if (r.port > 0) context.globalState.update("wam-proxy-mode", r.mode);
        _logInfo("PROXY", `网络代理探测 → ${r.mode}:${r.port}`);
      })
      .catch((e) => { _logWarn("PROXY", "探测失败", e.message); });
    // 透明代理健康检查 + 自动启动 (v3.0)
    if (_routingMode !== 'cloud') {
      _checkProxyHealth().then(ok => {
        _logInfo("PROXY", `透明代理(:${PROXY_HEALTH_PORT}) ${ok ? '✅在线' : '⚠离线'} | 路由: ${_routingMode}`);
        if (!ok && _routingMode !== 'cloud') {
          _logInfo("PROXY", "尝试自动启动透明代理v3.0...");
          _autoSpawnProxy();
        }
        _updatePoolBar();
      });
    }
  }, 1200);

  // 定期检查透明代理健康 + 自动恢复(local/hybrid模式) — 自适应退避
  if (_proxyCheckTimer) clearInterval(_proxyCheckTimer);
  _proxyCheckTimer = setInterval(() => {
    const adaptiveInterval = _proxyOnline ? PROXY_CHECK_INTERVAL : PROXY_CHECK_BACKOFF;
    if (_routingMode !== 'cloud' && Date.now() - _proxyLastCheck > adaptiveInterval) {
      _checkProxyHealth().then(ok => {
        if (!ok && !_proxyProcess) _autoSpawnProxy();
        _updatePoolBar();
      });
    }
  }, PROXY_CHECK_INTERVAL);

  const sidebarProvider = new AccountViewProvider(
    context.extensionUri,
    am,
    auth,
    (action, arg) => { const s = _syncGet(action, arg); return s !== undefined ? s : _handleAction(context, action, arg); },
  );
  _proxyView(context, "windsurf-assistant.assistantView", sidebarProvider);
  _panelProvider = sidebarProvider;

  _proxyCmd(context, "wam.switchAccount", () => _doPoolRotate(context));
  _proxyCmd(context, "wam.refreshCredits", () => _doRefreshPool(context));
  _proxyCmd(context, "wam.openPanel", () => {
    const result = openAccountPanel(
      context, am, auth,
      (a, b) => { const s = _syncGet(a, b); return s !== undefined ? s : _handleAction(context, a, b); },
      _panel,
    );
    if (result) _panel = result.panel;
  });
  _proxyCmd(context, "wam.switchMode", () => _doSwitchMode(context));
  _proxyCmd(context, "wam.reprobeProxy", async () => {
    const r = await auth.reprobeProxy();
    context.globalState.update("wam-proxy-mode", r.mode);
    _updatePoolBar();
  });
  _proxyCmd(context, "wam.resetFingerprint", () => _doResetFingerprint());
  _proxyCmd(context, "wam.panicSwitch", () => _doPoolRotate(context, true));
  _proxyCmd(context, "wam.batchAdd", () => _doBatchAdd());
  _proxyCmd(context, "wam.refreshAllCredits", () => _doRefreshPool(context));
  _proxyCmd(context, "wam.smartRotate", () => _doPoolRotate(context));
  _proxyCmd(context, "wam.importAccounts", () => _doImport(context));
  _proxyCmd(context, "wam.initWorkspace", () => _doInitWorkspace(context));
  _proxyCmd(context, "wam.poolSource", () => _doSwitchPoolSource(context));
  _proxyCmd(context, "wam.hotReload", () => _hotReload());
  _proxyCmd(context, "wam.hotStatus", () => {
    const src = fs.existsSync(path.join(os.homedir(), '.wam-hot', 'extension.js')) ? 'hot' : 'bundled';
    vscode.window.showInformationMessage(`WAM Hot: reloads=${_G.reloadCount}, cmds=${_G.registered.size}, src=${src}`);
  });

  context.subscriptions.push(vscode.workspace.onDidChangeConfiguration(e => {
    if (e.affectsConfiguration('wam.poolSource')) {
      _poolSourceMode = vscode.workspace.getConfiguration('wam').get('poolSource', 'local');
      _logInfo('CONFIG', `号池来源已切换: ${_poolSourceMode}`);
      _updatePoolBar();
    }
  }));

  _startPoolEngine(context);
  if (isHotRestart && _poolInitialized && _sessionPool.size > 0) {
    _logInfo('SESSION_POOL', `热重载恢复: ${_sessionPool.size}sessions已恢复, 跳过重新认证, 仅重启定时器`);
    // 仅重启定时器, 不重新认证(sessions已从快照恢复)
    _sessionPoolTimer = setInterval(() => { _refreshSessionTokens().catch(() => {}); }, SESSION_REFRESH_MS);
    const scheduleMatrixProbe = () => {
      const ms = (_isBoost() || _burstMode) ? MATRIX_PROBE_FAST : MATRIX_PROBE_INTERVAL;
      _capacityMatrixTimer = setTimeout(async () => {
        try { await _probeAllCapacity(); } catch {}
        scheduleMatrixProbe();
      }, ms);
    };
    scheduleMatrixProbe();
    context.subscriptions.push({
      dispose: () => {
        if (_sessionPoolTimer) { clearInterval(_sessionPoolTimer); _sessionPoolTimer = null; }
        if (_capacityMatrixTimer) { clearTimeout(_capacityMatrixTimer); _capacityMatrixTimer = null; }
      }
    });
  } else {
    _startSessionPoolEngine(context);
  }
  if (isHotRestart && _windowId) {
    _windowTimer = setInterval(() => _heartbeatWindow(), WINDOW_HEARTBEAT_MS);
    context.subscriptions.push({ dispose: () => { if (_windowTimer) { clearInterval(_windowTimer); _windowTimer = null; } _deregisterWindow(); } });
    _logInfo('WINDOW', `热重载恢复: windowId=${_windowId}, 仅重启心跳`);
  } else {
    _startWindowCoordinator(context);
  }
  _detectCascadeTabs();
  _startHubServer();
  _G.ctx = context;
  _setupHotWatcher();

  const accounts = am.getAll();
  _logInfo(
    "BOOT",
    `号池引擎就绪 v3.11.0 — ${accounts.length}账号, poolSrc=${_poolSourceMode}, proxy=${auth.getProxyStatus().mode}, route=${_routingMode}, win=${_getActiveWindowCount()}, tabs=${_cascadeTabCount}${_burstMode ? " BURST" : ""}, hub=:${HUB_PORT}, gates=4, hot=${_G.reloadCount}, ${isHotRestart ? '状态已恢复·'+_sessionPool.size+'sessions' : '全新启动'}`,
  );
}

// ========== Refresh Helpers (deduplicated from 8 call sites) ==========

/** Refresh one account's usage/credits. Returns { credits, usageInfo }
 *  v5.11.0: Supplements QUOTA data from cachedPlanInfo when API doesn't return daily% */
async function _refreshOne(index) {
  const account = am.get(index);
  if (!account) return { credits: undefined };
  try {
    const usageInfo = await auth.getUsageInfo(account.email, account.password);
    if (usageInfo) {
      // 0: If billingStrategy=quota but no daily% from API, supplement from cachedPlanInfo
      if (
        usageInfo.billingStrategy === "quota" &&
        !usageInfo.daily &&
        index === _activeIndex &&
        auth
      ) {
        try {
          const cached = auth.readCachedQuota();
          if (cached && cached.daily !== null) {
            usageInfo.daily = {
              used: Math.max(0, 100 - cached.daily),
              total: 100,
              remaining: cached.daily,
            };
            if (cached.weekly !== null)
              usageInfo.weekly = {
                used: Math.max(0, 100 - cached.weekly),
                total: 100,
                remaining: cached.weekly,
              };
            if (cached.resetTime) usageInfo.resetTime = cached.resetTime;
            if (cached.weeklyReset) usageInfo.weeklyReset = cached.weeklyReset;
            if (cached.extraBalance)
              usageInfo.extraBalance = cached.extraBalance;
            usageInfo.mode = "quota";
            _logInfo(
              "SUPPLEMENT",
              `#${index + 1} quota from cachedPlanInfo: D${cached.daily}% W${cached.weekly}%`,
            );
          }
          // Supplement plan dates from cachedPlanInfo (official alignment)
          if (cached) {
            if (cached.planStart && !usageInfo.planStart)
              usageInfo.planStart = cached.planStart;
            if (cached.planEnd && !usageInfo.planEnd)
              usageInfo.planEnd = cached.planEnd;
            if (cached.plan && !usageInfo.plan) usageInfo.plan = cached.plan;
          }
        } catch {}
      }
      // For active account, always try to supplement plan dates even if daily is present
      if (index === _activeIndex && auth && !usageInfo.planEnd) {
        try {
          const cached = auth.readCachedQuota();
          if (cached) {
            if (cached.planStart && !usageInfo.planStart)
              usageInfo.planStart = cached.planStart;
            if (cached.planEnd && !usageInfo.planEnd)
              usageInfo.planEnd = cached.planEnd;
            if (cached.plan && !usageInfo.plan) usageInfo.plan = cached.plan;
          }
        } catch {}
      }
      am.updateUsage(index, usageInfo);
      return { credits: usageInfo.credits, usageInfo };
    }
  } catch {}
  try {
    const credits = await auth.getCredits(account.email, account.password);
    if (credits !== undefined) am.updateCredits(index, credits);
    return { credits };
  } catch {}
  return { credits: undefined };
}

/** Refresh all accounts with parallel batching. Optional progress callback(i, total).
 *  Concurrency=3 balances speed vs API rate limits. ~3x faster than sequential. */
async function _refreshAll(progressFn) {
  if (!am) return;
  const accounts = am.getAll();
  const CONCURRENCY = 3;
  let completed = 0;
  for (let batch = 0; batch < accounts.length; batch += CONCURRENCY) {
    const slice = accounts.slice(batch, batch + CONCURRENCY);
    const promises = slice.map((_, j) => {
      const idx = batch + j;
      return _refreshOne(idx).then(() => {
        completed++;
        if (progressFn) progressFn(completed - 1, accounts.length);
      });
    });
    await Promise.allSettled(promises);
  }
}

// ========== 号池引擎 (v6.0 核心) ==========

/** 启动号池引擎 — 自适应轮询 + 自动选号 + 实时监控 + 并发Tab感知(v6.4) */
function _startPoolEngine(context) {
  const scheduleNext = () => {
    const ms = _getAdaptivePollMs(); // v6.4: 三级自适应(normal→boost→burst)
    _poolTimer = setTimeout(async () => {
      try {
        await _poolTick(context);
      } catch (e) {
        _logError("POOL", "tick error", e.message);
      }
      scheduleNext();
    }, ms);
  };
  // 首次启动延迟3s，等待代理探测完成
  setTimeout(async () => {
    await _poolTick(context);
    scheduleNext();
  }, 3000);
  // 同时启动限流检测
  _startQuotaWatcher(context);
  // v3.9.0 无感续传拦截器 — 在context key轮询之外建立第二感知通道
  _startSeamlessInterceptor(context);
}

/** 号池心跳 — 每次tick检查活跃账号，必要时自动轮转
 *  v6.7: + 全池实时监控 + 响应式切换(额度变动即切) + 并发Tab感知 */
async function _poolTick(context) {
  if (!am) return;
  const accounts = am.getAll();
  if (accounts.length === 0) return;

  // 每次tick探测并发Tab数
  _detectCascadeTabs();

  const autoRotate = vscode.workspace
    .getConfiguration("wam")
    .get("autoRotate", true);
  const threshold = PREEMPTIVE_THRESHOLD;

  // 无活跃账号 → 自动选择最优
  if (_activeIndex < 0 || _activeIndex >= accounts.length) {
    let best = am.selectOptimal(-1, threshold, _getOtherWindowAccounts());
    if (!best) best = am.selectOptimal(-1, threshold); // 降级: 忽略窗口隔离
    if (best) {
      _logInfo("POOL", `无活跃账号，自动选择 #${best.index + 1}`);
      await _seamlessSwitch(context, best.index);
    } else {
      _logWarn("POOL", "无活跃账号且无可用账号");
    }
    return;
  }

  // check expired active before wasting API call on refresh
  if (am.isExpired(_activeIndex)) {
    _logWarn("POOL", `活跃账号 #${_activeIndex + 1} 已过期 → 立即轮转`);
    if (autoRotate && !_isProxyRouting()) { // v3.2: 代理路由时跳过WAM过期切号
      let best = am.selectOptimal(_activeIndex, threshold, _getOtherWindowAccounts());
      if (!best) best = am.selectOptimal(_activeIndex, threshold);
      if (best) await _seamlessSwitch(context, best.index);
    }
    return;
  }

  // 刷新活跃账号额度
  const prevQuota = _lastQuota;
  const { credits, usageInfo } = await _refreshOne(_activeIndex);
  const curQuota = am.effectiveRemaining(_activeIndex);
  _lastQuota = curQuota;
  _lastCheckTs = Date.now();

  // v3.10 RC4根因修复: 低额自适应加速 — 配额<20%时自动激活boost缩短轮询间隔(45s→8s)
  // 根因: 正常轮询45s，在两次检查之间配额从低到0，用户先于系统看到错误
  if (curQuota !== null && curQuota > 0 && curQuota <= 20 && !_isBoost()) {
    _activateBoost();
    _logInfo("POOL", "v3.10 低额加速: quota=" + curQuota + "% → boost模式(8s轮询)");
  }

  // 记录斜率历史
  if (curQuota !== null && curQuota !== undefined) {
    _quotaHistory.push({ ts: Date.now(), remaining: curQuota });
    if (_quotaHistory.length > SLOPE_WINDOW * 2)
      _quotaHistory = _quotaHistory.slice(-SLOPE_WINDOW);
  }

  // 额度变化检测 + 消息速率追踪(v6.4) + 速度追踪(v7.0) + 小时消息追踪(v7.5)
  const quotaChanged =
    prevQuota !== null && prevQuota !== undefined && curQuota !== prevQuota;
  if (curQuota !== null) _trackVelocity(curQuota); // v7.0: 每次刷新都追踪速度
  if (quotaChanged) {
    _trackMessageRate(); // v6.4: 额度变化≈一次API消息
    if (curQuota < prevQuota) {
      const _drop = prevQuota - curQuota;
      _cumulativeDropSinceActivation += _drop; // v14.0: 累积降幅追踪(独立于消息估算)
      _lastQuotaDropTs = Date.now(); // v3.2: 记录下降时间戳(生成守卫依据)
      const _estMsgs = Math.max(1, Math.round(_drop / 2)); // 每条消息约消耗2-3%额度
      for (let _m = 0; _m < _estMsgs; _m++) _trackHourlyMsg();
    } else {
      _trackHourlyMsg(); // 非降幅变化(重置等)计一次
    }
    // 修复: floor(_drop/4) → 1msg@6%drop→1计, 2msg@12%→3计, 3msg@18%→4计 — 宁多计不漏计
    if (curQuota < prevQuota) {
      const currentModel = _readCurrentModelUid();
      if (_isOpusModel(currentModel)) {
        const _drop = prevQuota - curQuota;
        const _estMsgs = Math.max(1, Math.floor(_drop / 4));
        for (let _m = 0; _m < _estMsgs; _m++) _trackModelMsg(_activeIndex, 'opus');
        const opusCount = _getModelMsgCount(_activeIndex, 'opus');
        const _tierBudget = _getModelBudget(currentModel);
        _logInfo('OPUS_GUARD', `Opus追踪v9: #${_activeIndex+1} ${opusCount}/${_tierBudget}条 drop=${_drop.toFixed(1)}% est=${_estMsgs} model=${currentModel} tier=${_isThinking1MModel(currentModel)?'T1M':_isThinkingModel(currentModel)?'T':'R'}${opusCount >= _tierBudget ? ' → WILL SWITCH!' : ''}`);
      }
      // 0: Sonnet Thinking 1M消息追踪(同等逻辑, ACU=12同级防护)
      if (_isSonnetThinking1MModel(currentModel)) {
        const _drop = prevQuota - curQuota;
        const _estMsgs = Math.max(1, Math.floor(_drop / 4));
        for (let _m = 0; _m < _estMsgs; _m++) _trackModelMsg(_activeIndex, 'sonnet');
        const sonnetCount = _getModelMsgCount(_activeIndex, 'sonnet');
        _logInfo('SONNET_GUARD', `Sonnet T1M追踪v3.5: #${_activeIndex+1} ${sonnetCount}/${MODEL_BUDGET}条 drop=${_drop.toFixed(1)}% est=${_estMsgs}${sonnetCount >= MODEL_BUDGET ? ' → WILL SWITCH!' : ''}`);
      }
    }
    const vel = _getVelocity();
    _logInfo(
      "POOL",
      `额度变化: ${prevQuota} → ${curQuota} (rate=${_getCurrentMsgRate()}/min, tabs=${_cascadeTabCount}, velocity=${vel.toFixed(1)}%/min)`,
    );
    _activateBoost(); // 加速轮询
    _updatePoolBar();
    _refreshPanel();
  }

  const quotaDrop =
    prevQuota !== null && curQuota !== null ? prevQuota - curQuota : 0;
  if (
    quotaChanged &&
    curQuota < prevQuota &&
    quotaDrop >= REACTIVE_DROP_MIN &&
    autoRotate &&
    Date.now() - _lastReactiveSwitchTs > REACTIVE_SWITCH_CD
  ) {
    const stableCandidates = [];
    for (let i = 0; i < accounts.length; i++) {
      if (i === _activeIndex) continue;
      if (am.isRateLimited(i)) continue;
      if (am.isExpired(i)) continue; // 跳过已过期账号
      const rem = am.effectiveRemaining(i);
      if (rem === null || rem === undefined || rem <= threshold) continue;
      // "静止" = 快照中额度与当前一致(未被其他窗口消耗)
      const snap = _allQuotaSnapshot.get(i);
      if (snap && snap.remaining !== null && snap.remaining === rem) {
        stableCandidates.push({ index: i, remaining: rem });
      } else if (!snap) {
        // 无快照 = 从未扫描过，也可作为候选(额度充足即可)
        stableCandidates.push({ index: i, remaining: rem });
      }
    }
    if (stableCandidates.length > 0) {
      const _reactiveModel = _readCurrentModelUid();
      if (_isOpusModel(_reactiveModel) && _isNearModelBudget(_activeIndex)) {
        _logInfo('REACTIVE', `Opus budget guard联动: #${_activeIndex+1} ${_getModelMsgCount(_activeIndex, 'opus')}/${_getModelBudget(_reactiveModel)}条 → 标记model limited`);
        _modelGuardSwitchCount++;
        for (const variant of OPUS_VARIANTS) {
          am.markModelRateLimited(_activeIndex, variant, OPUS_COOLDOWN_DEFAULT, { trigger: 'reactive_opus_guard' });
        }
      }
      // 0: Sonnet Thinking 1M 响应式预算守卫
      if (_isSonnetThinking1MModel(_reactiveModel) && _isNearModelBudget(_activeIndex)) {
        _logInfo('REACTIVE', `Sonnet T1M budget guard联动: #${_activeIndex+1} ${_getModelMsgCount(_activeIndex, 'sonnet')}/${MODEL_BUDGET}条 → 标记model limited`);
        _modelGuardSwitchCount++;
        for (const variant of SONNET_VARIANTS) {
          am.markModelRateLimited(_activeIndex, variant, OPUS_COOLDOWN_DEFAULT, { trigger: 'reactive_sonnet_guard' });
        }
      }
      // 排除其他窗口占用 + v14.0: 排除Opus model-rate-limited的账号
      const otherClaimed = new Set(_getOtherWindowAccounts());
      const filtered = stableCandidates.filter((c) => {
        if (otherClaimed.has(c.index)) return false;
        if ((_isOpusModel(_reactiveModel) || _isSonnetThinking1MModel(_reactiveModel)) && am.isModelRateLimited(c.index, _reactiveModel)) return false; // v3.5.0
        return true;
      });
      const pool = filtered.length > 0 ? filtered : stableCandidates; // 降级: 忽略窗口隔离
      // UFEF-aware sort: 紧急过期账号优先使用
      pool.sort((a, b) => {
        const aU = am.getExpiryUrgency(a.index), bU = am.getExpiryUrgency(b.index);
        const aUrg = aU < 0 ? 2 : aU, bUrg = bU < 0 ? 2 : bU;
        if (aUrg !== bUrg) return aUrg - bUrg; // urgent first
        return b.remaining - a.remaining; // then highest remaining
      });
      _lastReactiveSwitchTs = Date.now();
      _logInfo(
        "REACTIVE",
        `活跃账号额度下降 ${prevQuota}→${curQuota}, 响应式切换到静止账号 #${pool[0].index + 1} (rem=${pool[0].remaining}, candidates=${pool.length})`,
      );
      // 代理路由时跳过WAM切号(代理已在网络层处理apiKey替换,无需切Windsurf会话)
      if (_isProxyRouting()) {
        _logInfo("REACTIVE", "代理路由中, 跳过WAM响应式切换 — 代理已处理路由");
        return;
      }
      // 生成守卫 — 配额刚下降=Cascade正在生成响应,不切号打断对话流
      if (_isGenerationActive()) {
        _pendingSwitch = { context, targetIndex: pool[0].index, reason: 'reactive_deferred' };
        _logInfo("REACTIVE", `生成守卫: 延迟响应式切换 → #${pool[0].index + 1} (配额下降${Date.now()-_lastQuotaDropTs}ms前)`);
        return;
      }
      await _seamlessSwitch(context, pool[0].index);
      return; // 已切换，跳过后续预防性判断
    }
  }

  if (Date.now() - _lastFullScanTs > FULL_SCAN_INTERVAL) {
    _lastFullScanTs = Date.now();
    _logInfo("SCAN", `全池扫描启动 (${accounts.length}账号)`);
    await _refreshAll();
    // 更新全池快照
    for (let i = 0; i < accounts.length; i++) {
      const rem = am.effectiveRemaining(i);
      const prev = _allQuotaSnapshot.get(i);
      if (prev && prev.remaining !== rem) {
        _logInfo("SCAN", `#${i + 1} 额度变化: ${prev.remaining} → ${rem}`);
      }
      _allQuotaSnapshot.set(i, { remaining: rem, checkedAt: Date.now() });
    }
    _refreshPanel();
  }

  // 归宗: 三层结构 — 本(L5 gRPC)→辅(配额阈值)→备(启发式降级)
  // L5 gRPC容量探测返回服务端真值(hasCapacity/messagesRemaining/maxMessages/resetsInSeconds)
  // 当L5有效时，L2斜率/L4 burst/L5 Tab压力/L6速度/L7小时追踪皆为冗余启发式，跳过
  if (autoRotate) {
    let shouldRotate = false;
    let reason = "";
    const _l5Valid = _lastCapacityResult && _lastCapacityResult.messagesRemaining >= 0
      && (Date.now() - _lastCapacityCheck < 120000); // L5数据2min内有效

    // L5-A: 容量耗尽 — hasCapacity=false → 用户下条消息必败 → 立即切
    if (!shouldRotate && _l5Valid && !_lastCapacityResult.hasCapacity) {
      shouldRotate = true;
      reason = `L5_no_capacity(remaining=${_lastCapacityResult.messagesRemaining}/${_lastCapacityResult.maxMessages},resets=${_lastCapacityResult.resetsInSeconds}s)`;
      _logWarn('POOL', `L5容量耗尽: 0容量 → 立即切号`);
      _invalidateApiKeyCache();
    }

    // L5-B: 容量预警 — 剩余≤3条或≤20%上限 → 提前切
    if (!shouldRotate && _l5Valid && _lastCapacityResult.hasCapacity) {
      const capMax = _lastCapacityResult.maxMessages > 0 ? _lastCapacityResult.maxMessages : TIER_MSG_CAP_ESTIMATE;
      const capRem = _lastCapacityResult.messagesRemaining;
      if (capRem <= CAPACITY_PREEMPT_REMAINING || (capMax > 0 && capRem <= capMax * 0.2)) {
        shouldRotate = true;
        reason = `L5_capacity_low(remaining=${capRem}/${capMax},resets=${_lastCapacityResult.resetsInSeconds}s)`;
        _logWarn('POOL', `L5容量预警: 剩余${capRem}/${capMax}条 → 提前切号`);
        _hourlyMsgLog = [];
        _invalidateApiKeyCache();
      }
    }

    // T2-A: 直接阈值判断 (effectiveRemaining ≤ 预防线15%)
    if (!shouldRotate) {
      const decision = am.shouldSwitch(_activeIndex, threshold);
      if (decision.switch) {
        shouldRotate = true;
        reason = decision.reason;
      }
    }

    // T2-B: rate limited状态(已标记的账号直接跳过)
    if (!shouldRotate && am.isRateLimited(_activeIndex)) {
      shouldRotate = true;
      reason = "rate_limited";
    }

    // T2-C: L8 Opus消息预算守卫 — per-model维度,L5可能未区分模型
    if (!shouldRotate && curQuota !== null && curQuota > threshold) {
      const currentModel = _readCurrentModelUid();
      if (_isOpusModel(currentModel) && _isNearModelBudget(_activeIndex)) {
        const opusCount = _getModelMsgCount(_activeIndex, 'opus');
        shouldRotate = true;
        const tierBudget = _getModelBudget(currentModel);
        reason = `opus_budget_guard(model=${currentModel},msgs=${opusCount}/${tierBudget},tier=${_isThinking1MModel(currentModel)?'T1M':_isThinkingModel(currentModel)?'T':'R'})`;
        _logWarn('OPUS_GUARD', `Opus预算守卫v10: #${_activeIndex+1} 窗口内${opusCount}/${tierBudget}条 (tier=${_isThinking1MModel(currentModel)?'Thinking1M':'Thinking'}) → 主动切号`);
        _modelGuardSwitchCount++;
        for (const variant of OPUS_VARIANTS) {
          am.markModelRateLimited(_activeIndex, variant, OPUS_COOLDOWN_DEFAULT, { trigger: 'opus_budget_guard' });
        }
        _pushRateLimitEvent({ type: 'per_model', trigger: 'opus_budget_guard', model: currentModel, msgs: opusCount, budget: tierBudget, tier: _isThinking1MModel(currentModel)?'T1M':_isThinkingModel(currentModel)?'T':'R' });
      }
    }

    // T2-C2: Sonnet Thinking 1M消息预算守卫 (v3.5.0)
    if (!shouldRotate && curQuota !== null && curQuota > threshold) {
      const _sonnetModel = _readCurrentModelUid();
      if (_isSonnetThinking1MModel(_sonnetModel) && _isNearModelBudget(_activeIndex)) {
        const sonnetCount = _getModelMsgCount(_activeIndex, 'sonnet');
        shouldRotate = true;
        reason = `sonnet_budget_guard(model=${_sonnetModel},msgs=${sonnetCount}/${MODEL_BUDGET})`;
        _logWarn('SONNET_GUARD', `Sonnet T1M预算守卫v3.5: #${_activeIndex+1} 窗口内${sonnetCount}/${MODEL_BUDGET}条 → 主动切号`);
        _modelGuardSwitchCount++;
        for (const variant of SONNET_VARIANTS) {
          am.markModelRateLimited(_activeIndex, variant, OPUS_COOLDOWN_DEFAULT, { trigger: 'sonnet_budget_guard' });
        }
        _pushRateLimitEvent({ type: 'per_model', trigger: 'sonnet_budget_guard', model: _sonnetModel, msgs: sonnetCount, budget: MODEL_BUDGET });
      }
    }

    // T2-D: UFEF过期紧急 — 当前账号安全但有紧急账号额度充足 → 切到紧急账号避免浪费
    if (!shouldRotate && curQuota !== null && curQuota > threshold) {
      const activeUrg = am.getExpiryUrgency(_activeIndex);
      if (activeUrg >= 2 || activeUrg < 0) {
        for (let i = 0; i < accounts.length; i++) {
          if (i === _activeIndex) continue;
          if (am.isRateLimited(i) || am.isExpired(i)) continue;
          const iUrg = am.getExpiryUrgency(i);
          if (iUrg === 0) {
            const iRem = am.effectiveRemaining(i);
            if (iRem !== null && iRem > threshold) {
              shouldRotate = true;
              reason = `ufef_urgent(active_urg=${activeUrg},#${i+1}_urg=${iUrg},#${i+1}_rem=${iRem},#${i+1}_days=${am.getPlanDaysRemaining(i)})`;
              _logInfo('POOL', `UFEF: #${i+1}紧急(${am.getPlanDaysRemaining(i)}d) → 切到紧急账号避免浪费`);
              break;
            }
          }
        }
      }
    }

    // T2-E: 累积额度降幅防线(v14.0) — 不依赖消息计数/L5, 直接追踪总消耗量
    if (!shouldRotate && _cumulativeDropSinceActivation >= CUMULATIVE_DROP_ROTATE_THRESHOLD) {
      shouldRotate = true;
      reason = `cumulative_drop(total=${_cumulativeDropSinceActivation.toFixed(1)}%,threshold=${CUMULATIVE_DROP_ROTATE_THRESHOLD})`;
      _logWarn('POOL', `T2-E累积额度: ${_cumulativeDropSinceActivation.toFixed(1)}% ≥ ${CUMULATIVE_DROP_ROTATE_THRESHOLD}% → 主动切号`);
    }

    if (!shouldRotate && !_l5Valid) {
      // L2: 斜率预测 — 5分钟内跌穿预防线
      if (curQuota !== null && curQuota > threshold) {
        const predicted = _slopePredict();
        if (predicted !== null && predicted <= threshold) {
          shouldRotate = true;
          reason = `fallback_slope(cur=${curQuota},pred=${predicted})`;
        }
      }

      // L4: 并发burst预测
      if (!shouldRotate && _burstMode && _isNearMsgRateLimit()) {
        shouldRotate = true;
        reason = `fallback_burst(tabs=${_cascadeTabCount},rate=${_getCurrentMsgRate()}/${MSG_RATE_LIMIT})`;
      }

      // L5-Tab: 并发Tab高压
      if (!shouldRotate && _cascadeTabCount > CONCURRENT_TAB_SAFE && curQuota !== null) {
        const dynamicThreshold = threshold + (_cascadeTabCount - CONCURRENT_TAB_SAFE) * 5;
        if (curQuota <= dynamicThreshold && curQuota > threshold) {
          shouldRotate = true;
          reason = `fallback_tab_pressure(tabs=${_cascadeTabCount},cur=${curQuota},dyn=${dynamicThreshold})`;
        }
      }

      // L6: 高速消耗检测
      if (!shouldRotate && _isHighVelocity() && curQuota !== null && curQuota > threshold) {
        const vel = _getVelocity();
        shouldRotate = true;
        reason = `fallback_velocity(vel=${vel.toFixed(1)}%/min,cur=${curQuota})`;
        _logWarn('POOL', `高速消耗(降级): ${vel.toFixed(1)}%/min → 主动切号`);
      }

      // L7: Gate 4层级上限(小时消息追踪降级)
      if (!shouldRotate && curQuota !== null && curQuota > threshold && _isNearTierCap()) {
        const effectiveCap = _realMaxMessages > 0 ? _realMaxMessages : TIER_MSG_CAP_ESTIMATE;
        shouldRotate = true;
        reason = `fallback_tier_cap(hourly=${_getHourlyMsgCount()}/${effectiveCap})`;
        _hourlyMsgLog = [];
      }

      // L9: 盲模式时间轮转 (v12.0) — 所有检测层失效时的最后防线
      if (!shouldRotate) {
        const _activeMs = Date.now() - _accountActiveSince;
        const _tabFactor = Math.max(1, _cascadeTabCount);
        const _effectiveMs = _activeMs * _tabFactor;
        if (_effectiveMs > BLIND_MAX_ACTIVE_MS) {
          shouldRotate = true;
          reason = `blind_timeout(active=${Math.round(_activeMs/60000)}min,tabs=${_tabFactor},effective=${Math.round(_effectiveMs/60000)}min,hourly=${_getHourlyMsgCount()})`;
          _hourlyMsgLog = [];
          _logWarn('POOL', `L9盲模式超时: ${Math.round(_activeMs/60000)}min×${_tabFactor}tabs=${Math.round(_effectiveMs/60000)}min > ${Math.round(BLIND_MAX_ACTIVE_MS/60000)}min → 主动切号`);
        }
      }
    }

    if (shouldRotate) {
      _logInfo("POOL", `预防性轮转: ${reason}`);
      // Opus budget guard触发时使用模型感知选号 — 排除model-rate-limited的账号
      const _rotateModel = _readCurrentModelUid();
      let best = null;
      if (_isOpusModel(_rotateModel) && reason.startsWith('opus_budget_guard')) {
        best = am.findBestForModel(_rotateModel, _activeIndex, threshold);
        if (!best) best = am.findBestForModel(_rotateModel, _activeIndex, 0); // 降级: 忽略阈值
      }
      if (!best) {
        best = am.selectOptimal(_activeIndex, threshold, _getOtherWindowAccounts());
      }
      if (!best) best = am.selectOptimal(_activeIndex, threshold); // 降级: 忽略窗口隔离
      if (best) {
        // 代理路由时跳过WAM切号 | 生成守卫: 延迟非紧急预防性切换
        if (_isProxyRouting()) {
          _logInfo("POOL", `代理路由中, 跳过WAM预防性轮转(${reason})`);
        } else if (_isGenerationActive() && !reason.startsWith('opus_budget') && !reason.includes('quota') && !reason.includes('rate')) {
          _pendingSwitch = { context, targetIndex: best.index, reason: `deferred_${reason}` };
          _logInfo("POOL", `生成守卫: 延迟预防性轮转 (${reason}) → #${best.index + 1}`);
        } else {
          await _seamlessSwitch(context, best.index);
        }
      } else {
        _updatePoolBar();
        _logWarn("POOL", "预防性轮转失败: 所有账号额度不足");
      }
    }
  }

  // 执行延迟切换 (生成守卫解除后 — 道法自然·不强制打断生成)
  if (_pendingSwitch && !_isGenerationActive() && !_switching) {
    const ps = _pendingSwitch; _pendingSwitch = null;
    _logInfo("POOL", `执行延迟切换: #${ps.targetIndex + 1} (${ps.reason})`);
    await _seamlessSwitch(ps.context, ps.targetIndex);
  }
  _updatePoolBar();
}

/** 全感知限流检测 (v6.4: + 并发Tab感知 + 动态冷却 + burst加速检测) */
function _startQuotaWatcher(context) {
  const CONTEXTS = [
    "chatQuotaExceeded", // 对话配额耗尽
    "rateLimitExceeded", // 通用限流
    "windsurf.quotaExceeded", // Windsurf配额耗尽
    "windsurf.rateLimited", // Windsurf限流
    "cascade.rateLimited", // Cascade限流
    "windsurf.messageRateLimited", // 消息级限流(截图中的错误类型)
    "windsurf.modelRateLimited", // 模型级限流
    "windsurf.permissionDenied", // 权限拒绝
    "windsurf.modelProviderUnreachable", // 模型不可达
    "cascade.modelProviderUnreachable", // 模型不可达
    "windsurf.connectionError", // 连接错误
    "cascade.error", // 通用cascade错误
  ];
  let _lastTriggered = 0;

  // 服务端有3级限流: burst_rate(<120s) / session_rate(120-3600s) / quota(>3600s)
  // 修复: 默认1200s(20min)匹配观测值，优先从state.vscdb或错误文本提取精确值
  const _smartCooldown = (rlType, serverResetSec) => {
    // 优先级1: 服务端报告的精确重置时间
    if (serverResetSec && serverResetSec > 0) return serverResetSec;
    // 优先级2: 从state.vscdb读取限流状态
    if (auth) {
      try {
        const cached = auth.readCachedRateLimit();
        if (cached && cached.resetsInSec && cached.resetsInSec > 0) {
          _logInfo(
            "COOLDOWN",
            `从state.vscdb获取实际冷却: ${cached.resetsInSec}s (type=${cached.type})`,
          );
          return cached.resetsInSec;
        }
      } catch {}
    }
    // 优先级3: 基于类型的默认值
    if (rlType === "message_rate") return 2400; // 40min — v15.0: 匹配实测"Resets in: 39m2s"(2342s)+安全余量
    if (rlType === "quota") return 3600; // 1h — 等待日重置
    return 600; // unknown default 10min (保守)
  };

  // v6.8→v7.5: 从错误文本提取服务端重置时间
  // 支持: "Resets in: 19m27s" → 1167 | "about an hour" → 3600 | "Xh" → X*3600
  const _extractResetSeconds = (text) => {
    if (!text) return null;
    // Pattern 1: "Resets in: 19m27s"
    const m = text.match(/resets?\s*in:?\s*(\d+)m(?:(\d+)s)?/i);
    if (m) return parseInt(m[1]) * 60 + (parseInt(m[2]) || 0);
    // Pattern 2: "Resets in: 45s"
    const s = text.match(/resets?\s*in:?\s*(\d+)s/i);
    if (s) return parseInt(s[1]);
    // Pattern 3: "try again in about an hour" → 3600
    if (ABOUT_HOUR_RE.test(text)) return 3600;
    // Pattern 4: "try again in Xh" or "resets in Xh"
    const h = text.match(/(?:resets?|try\s*again)\s*in:?\s*(\d+)\s*h/i);
    if (h) return parseInt(h[1]) * 3600;
    return null;
  };

  // 动态防抖 — 紧缩以快速响应(burst=2s, 正常=5s)
  const _getDebounce = () => (_burstMode ? 2000 : 5000);

  const checkContextKeys = async () => {
    if (_activeIndex < 0 || _switching) return;
    for (const ctx of CONTEXTS) {
      try {
        const exceeded = await vscode.commands.executeCommand(
          "getContext",
          ctx,
        );
        if (
          exceeded &&
          !_switching &&
          Date.now() - _lastTriggered > _getDebounce()
        ) {
          _lastTriggered = Date.now();
          const rlType =
            ctx.includes("quota") || ctx.includes("Quota")
              ? "quota"
              : "message_rate";
          const cooldown = _smartCooldown(rlType);
          _trackMessageRate(); // v6.4: 限流事件也计入消息速率
          _logWarn(
            "QUOTA",
            `检测到限流 context: ${ctx} (type=${rlType}, cooldown=${cooldown}s, tabs=${_cascadeTabCount}) → 立即轮转`,
          );
          // 四重闸门路由 — 根据context key分类限流类型
          const currentModel = _readCurrentModelUid();
          const gateType = _classifyRateLimit(null, ctx);
          // Gate 4: 账号层级硬限 → 跳过模型轮转, 直接账号切换
          if (gateType === 'tier_cap') {
            _logWarn('QUOTA', `[L1→TIER_RL] Gate 4 账号层级硬限 via context: ${ctx}`);
            await _handleTierRateLimit(context, cooldown);
            return;
          }
          // Gate 3: per-model rate limit → 模型变体轮转策略
          if (gateType === 'per_model' && currentModel) {
            _logWarn('QUOTA', `[L1→MODEL_RL] Gate 3 per-model rate limit via context: ${ctx}, model=${currentModel}`);
            // 立即将当前账号opus计数推至上限, 防止budget guard在切号后误判为可继续用
            if (_isOpusModel(currentModel) && _activeIndex >= 0) {
              const _budget = _getModelBudget(currentModel);
              for (let _f = 0; _f < _budget + 1; _f++) _trackModelMsg(_activeIndex, 'opus');
            }
            // 0: 同步推高Sonnet计数
            if (_isSonnetThinking1MModel(currentModel) && _activeIndex >= 0) {
              for (let _f = 0; _f < MODEL_BUDGET + 1; _f++) _trackModelMsg(_activeIndex, 'sonnet');
            }
            await _handlePerModelRateLimit(context, currentModel, cooldown);
            return;
          }
          // Gate 1/2: quota exhaustion → 标准账号切换
          am.markRateLimited(_activeIndex, cooldown, {
            model: currentModel || "current",
            trigger: ctx,
            type: rlType,
          });
          // 推送限流事件到安全中枢(非阻塞)
          _pushRateLimitEvent({
            type: rlType,
            trigger: ctx,
            cooldown,
            tabs: _cascadeTabCount,
          });
          _activateBoost();
          await _doPoolRotate(context, true);
          _scheduleAutoRetry(); // v3.9.0: G1/G2切号后自动重试
          return;
        }
      } catch (e) {
        // Suppress known harmless errors (getContext not found, Unknown context)
        // These flood logs every 2s × 12 keys = 360 noise events/min when command doesn't exist
        if (e.message && !e.message.includes("Unknown context") && !e.message.includes("not found")) {
          _logWarn("QUOTA", `context key ${ctx} 检测异常`, e.message);
        }
      }
    }
  };
  _qwCtxTimer = setInterval(checkContextKeys, 2000);
  _qwAdaptiveTimer = setInterval(() => {
    const targetMs = _burstMode ? 1500 : 2000;
    clearInterval(_qwCtxTimer);
    _qwCtxTimer = setInterval(checkContextKeys, targetMs);
  }, 30000);
  context.subscriptions.push({
    dispose: () => {
      if (_qwCtxTimer) { clearInterval(_qwCtxTimer); _qwCtxTimer = null; }
      if (_qwAdaptiveTimer) { clearInterval(_qwAdaptiveTimer); _qwAdaptiveTimer = null; }
    },
  });

  const RATE_LIMIT_PATTERNS = [
    /rate\s*limit/i,
    /quota\s*exceed/i,
    /permission\s*denied.*rate/i,
    /reached.*message.*rate.*limit/i,
    /try\s*again\s*later.*resets?\s*in/i,
    /额度.*耗尽/,
    /限流/,
    /rate limit for this model/i,
    /message rate limit for this model/i,
    /no\s*credits\s*were\s*used/i,  // v7.5: Gate 4 tier cap indicator
    /upgrade\s*to\s*a?\s*pro/i,     // v7.5: Gate 4 tier cap indicator
    /try\s*again\s*in\s*about\s*an?\s*hour/i, // v7.5: Gate 4 ~1h recovery
    /model\s*provider\s*unreachable/i, // model availability error
    /provider.*(?:error|unavailable|unreachable)/i, // provider errors
    /incomplete\s*envelope/i, // gRPC framing error (broken session)
    /failed\s*precondition/i, // v3.10: gRPC FAILED_PRECONDITION (daily quota exhausted)
    /quota.*exhausted/i,      // v3.10: "daily usage quota has been exhausted"
    /daily.*usage.*quota/i,   // v3.10: "Your daily usage quota has been exhausted"
  ];
  const RESETS_IN_RE = /resets?\s*in:?\s*(\d+)m(?:(\d+)s)?/i;
  const PER_MODEL_RL_RE = /reached.*message.*rate.*limit.*for this model/i;
  const TRACE_ID_RE = /trace\s*(?:ID|id):?\s*([a-f0-9]+)/i;

  // VS Code API无法hook其他扩展的showMessage，故依赖Layer 1+3自动检测

  const checkCachedQuota = async () => {
    if (_activeIndex < 0 || _switching || !auth) return;
    try {
      const cached = auth.readCachedQuota();
      if (
        cached &&
        cached.exhausted &&
        !_switching &&
        Date.now() - _lastTriggered > _getDebounce()
      ) {
        _lastTriggered = Date.now();
        const cooldown = _smartCooldown("quota");
        _logWarn(
          "QUOTA",
          `cachedPlanInfo显示额度耗尽 (daily=${cached.daily}% weekly=${cached.weekly}%, cooldown=${cooldown}s) → 立即轮转`,
        );
        am.markRateLimited(_activeIndex, cooldown, {
          model: "current",
          trigger: "cachedPlanInfo_exhausted",
          type: "quota",
        });
        _pushRateLimitEvent({
          type: "quota",
          trigger: "cachedPlanInfo_exhausted",
          cooldown,
          daily: cached.daily,
          weekly: cached.weekly,
        });
        _activateBoost();
        await _doPoolRotate(context, true);
        _scheduleAutoRetry(); // v3.9.0: cachedPlanInfo切号后自动重试
      }
    } catch (e) {
      _logWarn("QUOTA", "cachedPlanInfo检查异常", e.message);
    }
  };
  // 加速 cachedPlanInfo 轮询(5s/10s)
  _qwCacheTimer = setInterval(checkCachedQuota, _burstMode ? 5000 : 10000);
  context.subscriptions.push({ dispose: () => { if (_qwCacheTimer) { clearInterval(_qwCacheTimer); _qwCacheTimer = null; } } });

  // L1(context key) + L3(cachedPlanInfo) + L5(gRPC probe) 已足够覆盖所有场景

  // Windsurf 在发送每条消息前调用此端点预检，我们也调用它获取精确容量数据
  // 当 hasCapacity=false 或 messagesRemaining<=2 → 立即切号，在用户消息失败前
  const checkCapacityProbe = async () => {
    if (_activeIndex < 0 || _switching || !auth) return;
    // 自适应间隔 — Thinking模型3s(最快), v9.0所有Opus15s, boost/burst 15s, 正常45s
    const modelUid = _currentModelUid || _readCurrentModelUid();
    const isOpus = _isOpusModel(modelUid);
    const isThinking = isOpus && _isThinkingModel(modelUid);
    const interval = isThinking ? CAPACITY_CHECK_THINKING
      : (isOpus || _isBoost() || _burstMode) ? CAPACITY_CHECK_FAST : CAPACITY_CHECK_INTERVAL;
    if (Date.now() - _lastCapacityCheck < interval) return;

    try {
      const capacity = await _probeCapacity();
      if (!capacity) return;

      // 🚫 容量已耗尽 → 立即切号(在用户下一条消息失败前!)
      if (!capacity.hasCapacity) {
        if (!_switching && Date.now() - _lastTriggered > _getDebounce()) {
          _lastTriggered = Date.now();
          _logWarn('CAPACITY', `[L5] 🚫 容量探测: hasCapacity=false → 立即切号`);
          await _handleCapacityExhausted(context, capacity);
          return;
        }
      }

      // ⚠️ 容量即将耗尽(剩余≤CAPACITY_PREEMPT_REMAINING) → 提前切号
      if (capacity.messagesRemaining >= 0 && capacity.messagesRemaining <= CAPACITY_PREEMPT_REMAINING) {
        if (!_switching && Date.now() - _lastTriggered > _getDebounce()) {
          _lastTriggered = Date.now();
          _logWarn('CAPACITY', `[L5] ⚠️ 容量预警: 剩余${capacity.messagesRemaining}/${capacity.maxMessages}条 → 提前切号`);
          await _handleCapacityExhausted(context, capacity);
          return;
        }
      }
    } catch (e) {
      // 非关键，静默处理
    }
  };
  _qwL5Timer = setTimeout(() => {
    checkCapacityProbe(); // 首次探测
    _qwL5Interval = setInterval(checkCapacityProbe, 3000);
    context.subscriptions.push({ dispose: () => { if (_qwL5Interval) { clearInterval(_qwL5Interval); _qwL5Interval = null; } } });
  }, 10000);
  context.subscriptions.push({ dispose: () => { if (_qwL5Timer) { clearTimeout(_qwL5Timer); _qwL5Timer = null; } } });

  // L1+L3+L5+Opus预算守卫 已足够覆盖: quota耗尽/rate limit/per-model limit/tier cap

  _logInfo(
    "WATCHER",
    `检测就绪v3.6: L1=${CONTEXTS.length}keys(2s) + L3=cachedPlanInfo(10s) + L5=gRPC(T=${CAPACITY_CHECK_THINKING/1000}s/Opus=${CAPACITY_CHECK_FAST/1000}s/base=${CAPACITY_CHECK_INTERVAL/1000}s) + 防抖(${_burstMode ? '2' : '5'}s) + 四重闸门(G1-G4) + 统一预算(ALL_OPUS=${MODEL_BUDGET}条即切) + 窗口=${OPUS_BUDGET_WINDOW/60000}min + 冷却=${OPUS_COOLDOWN_DEFAULT}s`,
  );
}

// Windsurf 在发送每条消息前调用此端点预检，我们也调用它获取精确容量数据
// 当 hasCapacity=false 或 messagesRemaining<=2 → 立即切号，在用户消息失败前

/** 获取缓存的apiKey(自动刷新) */
function _getCachedApiKey() {
  if (_cachedApiKey && Date.now() - _cachedApiKeyTs < APIKEY_CACHE_TTL) {
    return _cachedApiKey;
  }
  try {
    const key = auth?.readCurrentApiKey();
    if (key && key.length > 10) {
      _cachedApiKey = key;
      _cachedApiKeyTs = Date.now();
      return key;
    }
  } catch {}
  return _cachedApiKey; // 返回可能过期的缓存值(比null好)
}

/** 切号后使apiKey缓存失效(新账号有新apiKey) */
function _invalidateApiKeyCache() {
  _cachedApiKey = null;
  _cachedApiKeyTs = 0;
}

/** Layer 5: 主动容量探测 — 调用CheckUserMessageRateLimit获取精确容量
 *  返回: capacity result 或 null (失败时) */
async function _probeCapacity() {
  if (!auth || _activeIndex < 0) return null;

  // Reduced backoff: max 60s
  if (_capacityProbeFailCount >= 5) {
    if (Date.now() - _lastCapacityCheck < 60000) return _lastCapacityResult;
  }

  const apiKey = _getCachedApiKey();
  if (!apiKey) {
    _logWarn('CAPACITY', 'apiKey未获取，跳过容量探测');
    return null;
  }

  const modelUid = _readCurrentModelUid();
  if (!modelUid) return null;

  _lastCapacityCheck = Date.now();
  _capacityProbeCount++;

  try {
    const result = await auth.checkRateLimitCapacity(apiKey, modelUid);
    if (result) {
      // -1/-1 means server returned empty/useless data — don't count as success
      const hasUsefulData = result.messagesRemaining >= 0 || result.maxMessages >= 0 || !result.hasCapacity;
      if (hasUsefulData) {
        _capacityProbeFailCount = 0; // 重置失败计数
        _lastSuccessfulProbe = Date.now(); // 更新看门狗时间戳
      } else {
        // Got response but no useful data — increment fail count for watchdog
        _capacityProbeFailCount++;
      }
      _lastCapacityResult = result;

      // 更新真实消息上限(服务端权威数据)
      if (result.maxMessages > 0 && result.maxMessages !== _realMaxMessages) {
        const old = _realMaxMessages;
        _realMaxMessages = result.maxMessages;
        _logInfo('CAPACITY', `服务端消息上限更新: ${old} → ${_realMaxMessages} (model=${modelUid})`);
      }

      // Log capacity status (reduce noise: only log every 5th probe or on state change)
      if (_capacityProbeCount % 5 === 0 || !result.hasCapacity || !hasUsefulData) {
        const statusIcon = result.hasCapacity ? '✅' : '🚫';
        _logInfo('CAPACITY', `${statusIcon} probe #${_capacityProbeCount}: capacity=${result.hasCapacity} remaining=${result.messagesRemaining}/${result.maxMessages} resets=${result.resetsInSeconds}s model=${modelUid}${hasUsefulData ? '' : ' (NO_DATA)'}`);
      }

      return result;
    }
    _capacityProbeFailCount++;
    return null;
  } catch (e) {
    _capacityProbeFailCount++;
    _logWarn('CAPACITY', `探测失败 (#${_capacityProbeFailCount}): ${e.message}`);
    return null;
  }
}

/** 处理容量不足 — 立即切号 */
async function _handleCapacityExhausted(context, capacityResult) {
  _capacitySwitchCount++;
  const logPrefix = `[CAPACITY_RL #${_capacitySwitchCount}]`;
  const cooldown = capacityResult.resetsInSeconds || 3600;
  const model = _readCurrentModelUid();

  _logWarn('CAPACITY', `${logPrefix} 容量不足! hasCapacity=${capacityResult.hasCapacity} remaining=${capacityResult.messagesRemaining}/${capacityResult.maxMessages} resets=${cooldown}s msg="${capacityResult.message}"`);

  // 根据容量探测结果精确分类
  const gateType = _classifyRateLimit(capacityResult.message, null);

  // 标记当前账号限流
  am.markRateLimited(_activeIndex, cooldown, {
    model: model || 'current',
    trigger: 'capacity_probe',
    type: gateType || 'tier_cap',
    capacityData: {
      remaining: capacityResult.messagesRemaining,
      max: capacityResult.maxMessages,
      resets: capacityResult.resetsInSeconds,
    },
  });

  _pushRateLimitEvent({
    type: gateType || 'tier_cap',
    trigger: 'capacity_probe_L5',
    cooldown,
    model,
    messagesRemaining: capacityResult.messagesRemaining,
    maxMessages: capacityResult.maxMessages,
    resetsInSeconds: capacityResult.resetsInSeconds,
    message: capacityResult.message,
  });

  // Gate 4 or unknown → 直接账号切换
  if (gateType === 'tier_cap' || gateType === 'unknown') {
    _hourlyMsgLog = []; // 新账号从0开始
    _invalidateApiKeyCache(); // 切号后apiKey变化
    _activateBoost();
    await _doPoolRotate(context, true);
    _scheduleAutoRetry(); // v3.9.0: L5 G4切号后自动重试
    return { action: 'capacity_account_switch', cooldown };
  }

  // Gate 3 (per-model) → 走模型级处理链
  if (gateType === 'per_model' && model) {
    _invalidateApiKeyCache();
    return await _handlePerModelRateLimit(context, model, cooldown);
  }

  // Default: 账号切换
  _invalidateApiKeyCache();
  _activateBoost();
  await _doPoolRotate(context, true);
  _scheduleAutoRetry(); // v3.9.0: 默认容量切号后自动重试
  return { action: 'capacity_rotate', cooldown };
}

/** 推送限流事件到安全中枢 :9877 (非阻塞, 失败静默) */
function _pushRateLimitEvent(eventData) {
  try {
    const payload = JSON.stringify({
      event: "rate_limit",
      timestamp: Date.now(),
      activeIndex: _activeIndex,
      activeEmail: am?.get(_activeIndex)?.email?.split("@")[0] || "?",
      windowId: _windowId,
      cascadeTabs: _cascadeTabCount,
      burstMode: _burstMode,
      switchCount: _switchCount,
      poolStats: am?.getPoolStats(PREEMPTIVE_THRESHOLD) || {},
      ...eventData,
    });
    const req = http.request({
      hostname: "127.0.0.1",
      port: 9877,
      method: "POST",
      path: "/api/wam/rate_limit_event",
      headers: {
        "Content-Type": "application/json",
        "Content-Length": Buffer.byteLength(payload),
      },
      timeout: 3000,
    });
    req.on("error", () => {}); // 静默失败
    req.on("timeout", () => req.destroy());
    req.write(payload);
    req.end();
    _logInfo(
      "HUB",
      `限流事件已推送 (type=${eventData.type}, trigger=${eventData.trigger})`,
    );
  } catch {}
}

// ========== 号池状态栏 ==========

// 与斜率预测(slopePredict)不同: 速度检测器关注短期突变(2min内降>10%)
// 斜率预测关注长期趋势(5样本线性外推), 速度检测器关注即时危险

/** 追踪积分速度样本 */
function _trackVelocity(remaining) {
  if (remaining === null || remaining === undefined) return;
  _velocityLog.push({ ts: Date.now(), remaining });
  // 只保留窗口内的样本
  const cutoff = Date.now() - VELOCITY_WINDOW;
  _velocityLog = _velocityLog.filter((s) => s.ts >= cutoff);
}

/** 计算当前积分消耗速度 (%/min), 正值=消耗中 */
function _getVelocity() {
  if (_velocityLog.length < 2) return 0;
  const first = _velocityLog[0],
    last = _velocityLog[_velocityLog.length - 1];
  const dtMin = (last.ts - first.ts) / 60000;
  if (dtMin <= 0) return 0;
  const drop = first.remaining - last.remaining; // 正值=额度在降
  return drop / dtMin; // %/min
}

/** 检测是否处于高速消耗模式 (120s内降>VELOCITY_THRESHOLD%) */
function _isHighVelocity() {
  if (_velocityLog.length < 2) return false;
  const first = _velocityLog[0],
    last = _velocityLog[_velocityLog.length - 1];
  const drop = first.remaining - last.remaining;
  return drop >= VELOCITY_THRESHOLD;
}

/** 斜率预测: 基于最近N个quota样本，线性外推SLOPE_HORIZON后的剩余额度 */
function _slopePredict() {
  if (_quotaHistory.length < 2) return null;
  const recent = _quotaHistory.slice(-SLOPE_WINDOW);
  if (recent.length < 2) return null;
  const first = recent[0],
    last = recent[recent.length - 1];
  const dt = last.ts - first.ts;
  if (dt <= 0) return null;
  const rate = (last.remaining - first.remaining) / dt; // per ms (负值=消耗中)
  if (rate >= 0) return null; // 额度在增加或不变，无需预测
  const predicted = last.remaining + rate * SLOPE_HORIZON;
  return Math.round(predicted);
}

function _updatePoolBar() {
  if (!statusBar || !am) return;
  const accounts = am.getAll();
  if (accounts.length === 0) {
    statusBar.text = "$(add) 添加账号";
    statusBar.color = new vscode.ThemeColor("disabledForeground");
    statusBar.tooltip = "号池为空，点击添加账号";
    return;
  }

  const pool = am.getPoolStats(PREEMPTIVE_THRESHOLD);
  const modeIcons = { local: '🔒', cloud: '☁', hybrid: '⚡' };
  const modeIcon = _isProxyRouting() ? '🔒' : (modeIcons[_routingMode] || '⚡');
  const srcIcons = { local: '💾', cloud: '☁', hybrid: '🔀' };
  const srcIcon = srcIcons[_poolSourceMode] || '💾';

  // 统一容量显示 — 额度归一
  let quotaDisplay = "?";
  let isLow = false;
  const u = _unifiedPool;
  if (u.totalRemaining > 0 && u.updatedAt > 0) {
    // 显示统一消息池
    quotaDisplay = `${u.totalRemaining}msg`;
    isLow = u.availableCount <= 1;
  } else if (pool.avgDaily !== null) {
    quotaDisplay =
      pool.avgWeekly !== null
        ? `D${pool.avgDaily}%·W${pool.avgWeekly}%`
        : `D${pool.avgDaily}%`;
    const poolEffective =
      pool.avgWeekly !== null
        ? Math.min(pool.avgDaily, pool.avgWeekly)
        : pool.avgDaily;
    isLow = poolEffective <= 10;
  } else if (pool.avgCredits !== null) {
    quotaDisplay = `均${pool.avgCredits}分`;
    isLow = pool.avgCredits <= PREEMPTIVE_THRESHOLD;
  } else {
    quotaDisplay = `${pool.health}%`;
    isLow = pool.health <= 10;
  }

  // 号池统一视图 — 可用/总计 + session pool状态
  const poolTag = _poolInitialized
    ? `${u.availableCount || pool.available}/${u.totalCount || pool.total}`
    : `${pool.available}/${pool.total}`;
  const spTag = _poolInitialized ? `S${_sessionPool.size}` : ''; // Session Pool size
  const boost = _isBoost() ? "⚡" : "";
  const burst = _burstMode ? "🔥" : ""; // v6.4: burst模式标识
  const auto = vscode.workspace.getConfiguration("wam").get("autoRotate", true)
    ? ""
    : "⏸";

  const winCount = _getActiveWindowCount();
  const winTag = winCount > 1 ? ` W${winCount}` : "";
  const tabTag =
    _cascadeTabCount > CONCURRENT_TAB_SAFE ? ` T${_cascadeTabCount}` : ""; // v6.4: 高并发Tab数
  statusBar.text = `${srcIcon}${modeIcon} ${quotaDisplay} ${poolTag}${spTag ? ' ' + spTag : ''}${winTag}${tabTag}${burst}${boost}${auto}`;
  statusBar.color = isLow
    ? new vscode.ThemeColor("errorForeground")
    : pool.available === 0
      ? new vscode.ThemeColor("errorForeground")
      : _burstMode
        ? new vscode.ThemeColor("editorWarning.foreground") // v6.4: burst模式黄色警示
        : new vscode.ThemeColor("testing.iconPassed");

  // 丰富tooltip (统一容量池 + session pool + capacity matrix)
  const lines = [];
  // 统一容量池头部
  if (_poolInitialized && u.updatedAt > 0) {
    lines.push(`🔮 统一容量池: ${u.totalRemaining}msg剩余 | ${u.availableCount}可用/${u.limitedCount}限流/${u.totalCount}总计`);
    if (u.throughput > 0) lines.push(`理论吞吐: ${u.throughput}msg/h | 利用率: ${u.utilization}%`);
    lines.push(`Session Pool: ${_sessionPool.size}认证 | 容量矩阵: ${_capacityMatrix.size}探测`);
    if (_nextBestIndex >= 0) {
      const nextEmail = am.get(_nextBestIndex)?.email?.split("@")[0] || "?";
      lines.push(`下一最优: #${_nextBestIndex + 1}(${nextEmail}) 评分${_nextBestScore}`);
    }
    lines.push(`零延迟切换: ${_zerodelaySwitchCount}次 | 完整登录: ${_fullLoginSwitchCount}次`);
    lines.push('─'.repeat(30));
  }
  lines.push(`号池: ${pool.available}可用/${pool.total}总计`);
  if (pool.depleted > 0) lines.push(`${pool.depleted}耗尽`);
  if (pool.rateLimited > 0) lines.push(`${pool.rateLimited}限流`);
  if (pool.expired > 0) lines.push(`${pool.expired}过期`);
  if (pool.urgentCount > 0) lines.push(`${pool.urgentCount}紧急(≤3d) — UFEF优先使用`);
  if (pool.soonCount > 0) lines.push(`${pool.soonCount}将到期(3-7d)`);
  // Effective pool metrics + weekly bottleneck + pre-reset waste
  if (pool.avgEffective !== null) lines.push(`有效均值: ${pool.avgEffective}% (min(D,W)真实容量)`);
  if (pool.weeklyBottleneckRatio > 50) lines.push(`ℹ️ W为瓶颈: ${pool.weeklyBottleneckCount}/${pool.effectiveCount}个账号W<D`);
  if (pool.preResetWasteCount > 0) lines.push(`⚠️ ${pool.preResetWasteCount}个账号周重置即将浪费${pool.preResetWasteTotal}%额度`);
  if (_switchCount > 0) lines.push(`已切换${_switchCount}次`);
  // Active account detail — 1:1 official Plan display
  if (_activeIndex >= 0) {
    const q = am.getActiveQuota(_activeIndex);
    if (q) {
      const aName = am.get(_activeIndex)?.email?.split("@")[0] || "?";
      const aQuota =
        q.daily !== null
          ? q.weekly !== null
            ? `D${q.daily}%·W${q.weekly}%`
            : `D${q.daily}%`
          : q.credits !== null
            ? `${q.credits}分`
            : "?";
      const planTag = q.plan ? ` [${q.plan}]` : "";
      const expiryTag =
        q.planDays !== null
          ? q.planDays > 0
            ? ` ${q.planDays}d剩余`
            : " 已过期"
          : "";
      lines.push(
        `活跃: #${_activeIndex + 1} ${aName} ${aQuota}${planTag}${expiryTag}`,
      );
      if (q.resetCountdown)
        lines.push(
          `日重置: ${q.resetCountdown}${q.dailyResetRaw ? " (" + new Date(q.dailyResetRaw).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) + ")" : ""}`,
        );
      if (q.weeklyResetCountdown)
        lines.push(
          `周重置: ${q.weeklyResetCountdown}${q.weeklyReset ? " (" + new Date(q.weeklyReset).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) + ")" : ""}`,
        );
      if (q.extraBalance !== null && q.extraBalance > 0)
        lines.push(`额外余额: $${q.extraBalance.toFixed(2)}`);
    }
  }
  if (pool.nextReset)
    lines.push(`下次刷新: ${new Date(pool.nextReset).toLocaleTimeString()}`);
  const slopeInfo = _slopePredict();
  if (winCount > 1)
    lines.push(
      `${winCount}个窗口活跃 | 其他窗口占用: [${_getOtherWindowAccounts()
        .map((i) => "#" + (i + 1))
        .join(",")}]`,
    );
  if (_cascadeTabCount > 1)
    lines.push(
      `${_cascadeTabCount}个Cascade对话 | 消息速率: ${_getCurrentMsgRate()}/${MSG_RATE_LIMIT}/min`,
    );
  if (_burstMode) lines.push("BURST防护模式");
  // 热重置+速度感知信息
  const vel = _getVelocity();
  if (vel > 0)
    lines.push(
      `消耗速度: ${vel.toFixed(1)}%/min${_isHighVelocity() ? " ⚡高速" : ""}`,
    );
  // Gate 4 小时消息计数
  const hourlyCount = _getHourlyMsgCount();
  if (hourlyCount > 0) lines.push(`小时消息: ${hourlyCount}/${TIER_MSG_CAP_ESTIMATE}${_isNearTierCap() ? ' ⚠️接近层级上限' : ''}`);
  if (_cumulativeDropSinceActivation > 0) lines.push(`累积降幅: ${_cumulativeDropSinceActivation.toFixed(1)}%/${CUMULATIVE_DROP_ROTATE_THRESHOLD}%${_cumulativeDropSinceActivation >= CUMULATIVE_DROP_ROTATE_THRESHOLD ? ' ⚠️将切号' : ''}`);
  if (_tierRateLimitCount > 0) lines.push(`层级限流(G4): ${_tierRateLimitCount}次`);
  if (_hotResetCount > 0)
    lines.push(`热重置: ${_hotResetVerified}/${_hotResetCount}次验证`);
  // Opus Guard stats
  const currentModel = _currentModelUid || _readCurrentModelUid();
  if (_isOpusModel(currentModel) && _activeIndex >= 0) {
    const opusCount = _getModelMsgCount(_activeIndex, 'opus');
    const tierBudget = _getModelBudget(currentModel);
    const tierLabel = _isThinking1MModel(currentModel) ? 'T1M' : _isThinkingModel(currentModel) ? 'T' : 'R';
    lines.push(`Opus预算: ${opusCount}/${tierBudget}条 (tier=${tierLabel}, model=${currentModel})`);
  }
  if (_modelGuardSwitchCount > 0) lines.push(`Opus守卫: ${_modelGuardSwitchCount}次主动切号`);
  if (_modelGuardSwitchCount > 0) lines.push(`Sonnet T1M守卫: ${_modelGuardSwitchCount}次主动切号`); // v3.5.0
  if (_modelRateLimitCount > 0) lines.push(`模型限流(G3): ${_modelRateLimitCount}次`);
  // L5容量探测数据
  if (_lastCapacityResult) {
    const cap = _lastCapacityResult;
    const capIcon = cap.hasCapacity ? '✅' : '🚫';
    lines.push(`L5容量: ${capIcon} ${cap.messagesRemaining >= 0 ? cap.messagesRemaining : '?'}/${cap.maxMessages >= 0 ? cap.maxMessages : '?'}条 (probe#${_capacityProbeCount})`);
    if (cap.resetsInSeconds > 0) lines.push(`重置: ${Math.ceil(cap.resetsInSeconds / 60)}min`);
  }
  if (_capacitySwitchCount > 0) lines.push(`容量切号(L5): ${_capacitySwitchCount}次`);
  if (_capacityProbeFailCount > 0) lines.push(`L5探测失败: ${_capacityProbeFailCount}次连续`);
  // Watchdog status
  const wdAge = Math.round((Date.now() - _lastSuccessfulProbe) / 1000);
  const wdArmed = wdAge > WATCHDOG_TIMEOUT / 1000 && _capacityProbeFailCount >= 3;
  if (_watchdogSwitchCount > 0 || wdArmed) {
    lines.push(`看门狗: ${wdArmed ? '⚠️已待命' : '✅正常'} | ${wdAge}s自上次探测 | 切号${_watchdogSwitchCount}次`);
  }
  lines.push(
    `预防线: ${PREEMPTIVE_THRESHOLD}%${slopeInfo !== null ? " | 预测:" + slopeInfo + "%" : ""} | ${auth ? auth.getProxyStatus().mode : '?'}/${_routingMode}/${_poolSourceMode} | 10层防御`,
  );
  statusBar.tooltip = lines.join("\n");
}

// ========== 号池轮转 (无感切换) ==========

/** 无感切换 — 用户无需任何操作
 *  v2.0: 优先使用Session Pool缓存(零延迟), 降级到完整登录 */
async function _seamlessSwitch(context, targetIndex) {
  if (_switching || targetIndex === _activeIndex) return;
  _switching = true;
  const prevBar = statusBar.text;
  statusBar.text = "$(sync~spin) ...";
  const prevIndex = _activeIndex;

  try {
    _invalidateApiKeyCache(); // 切号后apiKey变化
    _accountActiveSince = Date.now(); // v12.0: 重置盲模式计时器

    // 零延迟路径 — Session Pool中有缓存token则直接注入
    const cachedSession = _sessionPool.get(targetIndex);
    const hasValidCache = cachedSession && cachedSession.healthy && cachedSession.idToken && Date.now() < cachedSession.expireTime;

    if (hasValidCache) {
      await _injectCachedSession(context, targetIndex, cachedSession);
    } else {
      // 降级: 完整登录流程
      _fullLoginSwitchCount++;
      await _loginToAccount(context, targetIndex);
    }

    _switchCount++;
    // reset tracking state — old account's data corrupts new account's predictions
    _quotaHistory = [];
    _velocityLog = [];
    _lastQuota = null;
    _cumulativeDropSinceActivation = 0; // v14.0: 新账号重置累积降幅
    _hourlyMsgLog = []; // v2.0: 新账号重置小时计数
    _resetModelMsgLog(prevIndex); // v2.0: 重置旧账号Opus计数
    _resetModelMsgLog(prevIndex); // v3.11.0: 重置旧账号Sonnet T1M计数
    _heartbeatWindow();

    // Post-switch quota verification — 切后立即验证，防止落入耗尽账号
    const _cachedPostRem = am.effectiveRemaining(targetIndex);
    if (_cachedPostRem !== null && _cachedPostRem <= 0) {
      _logWarn("SWITCH", `#${targetIndex + 1} 已知耗尽(cached=${_cachedPostRem}) → 即时重轮转`);
      am.markRateLimited(targetIndex, 720, { type: 'quota', trigger: 'post_switch_cached_depleted' });
      const _reCtx = context;
      setTimeout(() => _doPoolRotate(_reCtx, true).catch(() => {}), 100);
      return;
    }
    // Post-switch Opus model rate limit check — 防止切到Opus被标记的账号
    const _postModel = _readCurrentModelUid();
    if ((_isOpusModel(_postModel) || _isSonnetThinking1MModel(_postModel)) && am.isModelRateLimited(targetIndex, _postModel)) {
      _logWarn("SWITCH", `#${targetIndex + 1} model ${_postModel} 已标记limited → 即时重轮转`); // v3.5.0
      const _reCtx = context;
      setTimeout(() => _doPoolRotate(_reCtx, true).catch(() => {}), 100);
      return;
    }
    try {
      await _refreshOne(targetIndex);
      const _postRem = am.effectiveRemaining(targetIndex);
      if (_postRem !== null && _postRem <= 0) {
        _logWarn("SWITCH", `#${targetIndex + 1} 切后验证额度=${_postRem} → 标记+重轮转`);
        am.markRateLimited(targetIndex, 1800, { type: 'quota', trigger: 'post_switch_depleted' });
        const _reCtx = context;
        setTimeout(() => _doPoolRotate(_reCtx, true).catch(() => {}), 200);
        return;
      }
      if (_postRem !== null) _lastQuota = _postRem;
    } catch {}

    // 切号后立即更新容量矩阵(新apiKey → 重新探测)
    if (_poolInitialized) {
      setTimeout(() => {
        try {
          const newKey = _getCachedApiKey();
          const session = _sessionPool.get(targetIndex);
          if (session && newKey) session.apiKey = newKey;
          _precomputeNextBest();
        } catch {}
      }, 3000);
    }

    _logInfo(
      "SWITCH",
      `无感切换 #${prevIndex + 1}→#${targetIndex + 1} (第${_switchCount}次, ${hasValidCache ? '零延迟' : '完整登录'}, pool=${_sessionPool.size}, next=#${_nextBestIndex + 1})`,
    );
  } catch (e) {
    _logError("SWITCH", `切换失败 #${targetIndex + 1}`, e.message);
    statusBar.text = prevBar;
  } finally {
    _switching = false;
    _updatePoolBar();
    _refreshPanel();
  }
}

/** 号池轮转命令 (用户触发或自动触发)
 *  v11.0: isPanic=true跳过_refreshAll(用缓存直切)，但注入始终完整验证 */
async function _doPoolRotate(context, isPanic = false) {
  if (_switching) return;

  // 三模式路由: 代理在线时跳过WAM切号(代理已在网络层处理)
  if (_isProxyRouting() && !isPanic) {
    _logInfo("ROUTE", `代理在线(${_routingMode}模式), 跳过WAM切号 — 由透明代理处理路由`);
    _updatePoolBar();
    return;
  }

  if (!am) return;
  const accounts = am.getAll();
  if (accounts.length === 0) {
    vscode.commands.executeCommand("wam.openPanel");
    return;
  }

  const threshold = PREEMPTIVE_THRESHOLD;

  if (isPanic && _activeIndex >= 0) {
    statusBar.text = "$(zap) 即时切换...";
    const t0 = Date.now();
    _logWarn("ROTATE", `紧急切换: 标记 #${_activeIndex + 1} 限流 → 用缓存选最优`);
    if (!am.isRateLimited(_activeIndex)) {
      am.markRateLimited(_activeIndex, 300, { model: "unknown", trigger: "panic_rotate" });
    }
    let best = am.selectOptimal(_activeIndex, threshold, _getOtherWindowAccounts());
    if (!best) best = am.selectOptimal(_activeIndex, threshold);
    if (!best) best = am.selectOptimal(_activeIndex, 0);
    if (best) {
      await _seamlessSwitch(context, best.index);
      _logInfo("ROTATE", `紧急切换完成: #${best.index + 1} (耗时${Date.now() - t0}ms)`);
      _updatePoolBar();
      _refreshPanel();
      setTimeout(() => _refreshAll().then(() => { _updatePoolBar(); _refreshPanel(); }).catch(() => {}), 5000);
      return;
    }
    if (accounts.length > 1) {
      let next = -1;
      for (let r = 1; r < accounts.length; r++) {
        const ci = (_activeIndex + r) % accounts.length;
        if (am.isRateLimited(ci) || am.isExpired(ci)) continue;
        const ciRem = am.effectiveRemaining(ci);
        if (ciRem !== null && ciRem <= 0) continue; // v13.0: skip known-depleted
        next = ci; break;
      }
      if (next >= 0) {
        await _seamlessSwitch(context, next);
        _logInfo("ROTATE", `紧急round-robin切换: #${next + 1} (耗时${Date.now() - t0}ms)`);
      } else {
        _logWarn("ROTATE", "紧急round-robin: 所有账号不可用/已耗尽");
      }
    }
    _updatePoolBar();
    _refreshPanel();
    return;
  }

  statusBar.text = "$(sync~spin) 轮转中...";
  await _refreshAll();

  let best = am.selectOptimal(
    _activeIndex,
    threshold,
    _getOtherWindowAccounts(),
  );
  if (!best) best = am.selectOptimal(_activeIndex, threshold);
  if (best) {
    await _seamlessSwitch(context, best.index);
  } else if (am.allDepleted(threshold)) {
    if (_poolSourceMode !== 'local') {
      _logInfo("CLOUD", "本地号池耗尽 → 尝试从云端拉取账号...");
      statusBar.text = "$(cloud) 云端拉取中...";
      const pull = await _cloudPullFallback();
      if (pull.ok) {
        // 云端账号已自动添加到本地池，现在刷新并切换
        await _refreshAll();
        const cloudBest = am.selectOptimal(_activeIndex, 0);
        if (cloudBest) {
          await _seamlessSwitch(context, cloudBest.index);
          _logInfo("CLOUD", `云端降级成功: 切换到 #${cloudBest.index + 1}`);
          _updatePoolBar();
          _refreshPanel();
          return;
        }
      } else {
        _logWarn("CLOUD", `云端拉取失败: ${pull.reason}`);
      }
    }
    statusBar.text = "$(warning) 号池耗尽";
    statusBar.color = new vscode.ThemeColor("errorForeground");
    vscode.window.showWarningMessage(
      "WAM: 所有账号额度不足。SWE-1.5模型免费无限使用。",
      "确定",
    );
  } else {
    // Round-robin fallback (跳过不可用账号 + v13.0: 跳过已知耗尽)
    if (accounts.length > 1) {
      let next = -1;
      for (let r = 1; r < accounts.length; r++) {
        const ci = (_activeIndex + r) % accounts.length;
        if (am.isRateLimited(ci) || am.isExpired(ci)) continue;
        const ciRem = am.effectiveRemaining(ci);
        if (ciRem !== null && ciRem <= 0) continue; // v13.0: skip known-depleted
        next = ci; break;
      }
      if (next >= 0) {
        await _seamlessSwitch(context, next);
      } else {
        _logWarn("ROTATE", "round-robin: 所有账号不可用/已耗尽");
        statusBar.text = "$(warning) 号池耗尽";
        statusBar.color = new vscode.ThemeColor("errorForeground");
      }
    }
  }
  _updatePoolBar();
  _refreshPanel();
}

// ========== Core: Auth Infrastructure (battle-tested, kept intact) ==========

/** Discover the correct auth injection command at runtime */
async function _discoverAuthCommand() {
  if (_discoveredAuthCmd) return _discoveredAuthCmd;
  const allCmds = await vscode.commands.getCommands(true);
  const candidates = [
    ...allCmds.filter(
      (c) => /provideAuthToken.*AuthProvider/i.test(c) && !/Shit/i.test(c),
    ),
    ...allCmds.filter((c) => /provideAuthToken.*Shit/i.test(c)),
    ...allCmds.filter(
      (c) =>
        /windsurf/i.test(c) &&
        /auth/i.test(c) &&
        /token/i.test(c) &&
        c !== "windsurf.loginWithAuthToken",
    ),
  ];
  const seen = new Set();
  const unique = candidates.filter((c) => {
    if (seen.has(c)) return false;
    seen.add(c);
    return true;
  });
  _logInfo(
    "AUTH",
    `discovered ${unique.length} auth commands: [${unique.join(", ")}]`,
  );
  if (unique.length > 0) _discoveredAuthCmd = unique;
  return unique;
}

function _resetDiscoveredCommands() {
  _discoveredAuthCmd = null;
}

// 根因修正: provideAuthTokenToAuthProvider → handleAuthToken → registerUser → restartLS
// 是Windsurf内部自动完成的。旧版错误地重启TypeScript LS(无关)和清理.vscode-server(远程开发)。
// 真正需要的只是等待Windsurf内部的auth handler完成会话切换。

/**
 * 等待Windsurf内部会话过渡完成
 * provideAuthTokenToAuthProvider触发的内部链: handleAuthToken → registerUser → new session
 * 我们只需等待这个过程完成，不需要重启任何LS
 */
async function _waitForSessionTransition() {
  _logInfo("SESSION", "等待Windsurf会话过渡...");
  // Windsurf内部registerUser + session创建需要1-3秒
  await new Promise((resolve) => setTimeout(resolve, 2000));
  _logInfo("SESSION", "会话过渡等待完成");
  return true;
}

/**
 * v7.1.0 热重置验证
 * 验证新机器码是否真的被LS读取
 */
async function _verifyHotResetSuccess() {
  if (!_lastRotatedIds) {
    _logWarn("HOT_RESET", "无轮转记录可验证");
    return false;
  }

  try {
    // 等待LS完全启动并读取新机器码
    await new Promise((resolve) => setTimeout(resolve, 5000));

    // 验证新机器码是否生效
    const verify = hotVerify(_lastRotatedIds);
    if (verify.verified) {
      _hotResetVerified++;
      _logInfo(
        "HOT_RESET",
        `✅ 热重置验证成功 (#${_hotResetVerified}/${_hotResetCount})`,
      );
      return true;
    } else {
      _logWarn(
        "HOT_RESET",
        `❌ 热重置验证失败: ${verify.mismatches.join(", ")}`,
      );
      return false;
    }
  } catch (e) {
    _logError("HOT_RESET", "验证过程出错", e.message);
    return false;
  }
}

// Root cause of "breaks Cascade": provideAuthTokenToAuthProvider switches the

/**
 * SAFE: Check account credentials and refresh credits.
 * Does Firebase login + GetPlanStatus only. Does NOT touch Windsurf auth.
 * Returns { ok, credits, usageInfo }
 */
async function _checkAccount(context, index) {
  const account = am.get(index);
  if (!account) return { ok: false };

  const result = await _refreshOne(index);
  _activeIndex = index;
  context.globalState.update("wam-current-index", index);
  _updatePoolBar();

  return { ok: true, credits: result.credits, usageInfo: result.usageInfo };
}

/**
 * DISRUPTIVE: Inject auth token into Windsurf to switch active account.
 */
async function injectAuth(context, index) {
  const account = am.get(index);
  if (!account) return { ok: false };

  // 根因修正: provideAuthTokenToAuthProvider内部自动触发registerUser→restartLS
  // 不再手动重启LS(旧版错误地重启TypeScript LS)
  // 只需: 轮转指纹(写磁盘) → 等待 → 注入(Windsurf内部完成LS重启+读新ID)
  const config = vscode.workspace.getConfiguration("wam");
  if (config.get("rotateFingerprint", true)) {
    _rotateFingerprintForSwitch();
    _hotResetCount++;
    _logInfo("HOT_RESET", `fingerprint rotated (#${_hotResetCount})`);
    // 等待指纹写入磁盘完成(Windsurf注入后内部重启LS时会读取新指纹)
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }

  let injected = false;
  let method = "none";
  const discoveredCmds = await _discoverAuthCommand();

  // Strategy 0 (PRIMARY — Windsurf 1.108.2+): idToken direct
  // PROVIDE_AUTH_TOKEN_TO_AUTH_PROVIDER accepts firebase idToken,
  // internally calls registerUser(idToken) → {apiKey, name} → session
  try {
    const idToken = await auth.getFreshIdToken(account.email, account.password);
    if (idToken) {
      // Try well-known command name first
      try {
        const result = await vscode.commands.executeCommand(
          "windsurf.provideAuthTokenToAuthProvider",
          idToken,
        );
        // FIX: Check return value — command returns {session, error}, not throwing on auth failure
        if (result && result.error) {
          _logWarn(
            "INJECT",
            `[S0] command returned error: ${JSON.stringify(result.error)}`,
          );
        } else {
          injected = true;
          method = "S0-provideAuth-idToken";
          _logInfo(
            "INJECT",
            `[S0] injected idToken via provideAuthTokenToAuthProvider → session: ${result?.session?.account?.label || "unknown"}`,
          );
        }
      } catch (e) {
        _logWarn("INJECT", `[S0] primary command failed: ${e.message}`);
      }
      // Try discovered commands with idToken
      if (!injected) {
        for (const cmd of discoveredCmds || []) {
          if (injected) break;
          try {
            const result = await vscode.commands.executeCommand(cmd, idToken);
            if (result && result.error) {
              _logWarn(
                "INJECT",
                `[S0-discovered] ${cmd} returned error: ${JSON.stringify(result.error)}`,
              );
            } else {
              injected = true;
              method = `S0-${cmd}-idToken`;
              _logInfo("INJECT", `[S0-discovered] injected idToken via ${cmd}`);
            }
          } catch {}
        }
      }
    }
  } catch (e) {
    _logWarn("INJECT", "[S0] idToken injection failed", e.message);
  }

  // Strategy 1 (FALLBACK): OneTimeAuthToken via relay
  if (!injected) {
    try {
      const authToken = await auth.getOneTimeAuthToken(
        account.email,
        account.password,
      );
      if (authToken && authToken.length >= 30 && authToken.length <= 200) {
        try {
          await vscode.commands.executeCommand(
            "windsurf.provideAuthTokenToAuthProvider",
            authToken,
          );
          injected = true;
          method = "S1-provideAuth-otat";
          _logInfo(
            "INJECT",
            "[S1] injected OneTimeAuthToken via provideAuthTokenToAuthProvider",
          );
        } catch {}
        if (!injected) {
          for (const cmd of discoveredCmds || []) {
            if (injected) break;
            try {
              await vscode.commands.executeCommand(cmd, authToken);
              injected = true;
              method = `S1-${cmd}-otat`;
              _logInfo(
                "INJECT",
                `[S1-discovered] injected OneTimeAuthToken via ${cmd}`,
              );
            } catch {}
          }
        }
        if (injected) _writeAuthFilesCompat(authToken);
      }
    } catch (e) {
      _logWarn("INJECT", "[S1] OneTimeAuthToken fallback failed", e.message);
    }
  }

  // Strategy 2: registerUser apiKey via command
  if (!injected) {
    try {
      const regResult = await auth.registerUser(
        account.email,
        account.password,
      );
      if (regResult && regResult.apiKey) {
        for (const cmd of discoveredCmds || []) {
          if (injected) break;
          try {
            const s2result = await vscode.commands.executeCommand(cmd, regResult.apiKey);
            if (s2result && s2result.error) {
              _logWarn("INJECT", `[S2] ${cmd} returned error: ${JSON.stringify(s2result.error)}`);
            } else {
              injected = true;
              method = `S2-${cmd}-apiKey`;
              _logInfo("INJECT", `[S2] injected apiKey via ${cmd}`);
            }
          } catch (e) {
            _logError("INJECT", `[S2] ${cmd} failed`, e.message);
          }
        }
        // Strategy 3 (DB DIRECT-WRITE — bypasses command system):
        if (!injected) {
          const dbResult = _dbInjectApiKey(regResult.apiKey);
          if (dbResult.ok) {
            injected = true;
            method = "S3-db-inject";
            _logInfo(
              "INJECT",
              `[S3] DB direct-write: ${dbResult.oldPrefix}→${dbResult.newPrefix}`,
            );
            // DB injection requires window reload to take effect (encrypted session unchanged)
            // Auto-reload after brief delay — 无感切号核心: 用户零操作
            _logInfo("INJECT", "[S3] DB inject success, auto-reloading window in 2s...");
            setTimeout(() => {
              vscode.commands.executeCommand("workbench.action.reloadWindow");
            }, 2000);
          } else {
            _logWarn("INJECT", `[S3] DB inject failed: ${dbResult.error}`);
          }
        }
      }
    } catch (e) {
      _logWarn("INJECT", "[S2/S3] registerUser+DB fallback failed", e.message);
    }
  }

  // Root cause chain (reverse-engineered 2026-03-20):
  if (injected) {
    await _postInjectionRefresh();
  }

  return { ok: injected, injected, method };
}

/** Login to account: check credits → inject auth → verify
 *  v11.0: 始终验证会话建立，不跳过(杜绝"Invalid argument"错误的根源) */
async function _loginToAccount(context, index) {
  const account = am.get(index);
  if (!account) return;

  // 始终设置activeIndex(即使后续注入失败，也有正确的目标)
  _activeIndex = index;
  context.globalState.update("wam-current-index", index);

  // 快速路径: 只做Firebase登录验证(不调GetPlanStatus，省1-2s)
  // 确保账号凭据有效，避免注入无效token
  try {
    const idToken = await auth.getFreshIdToken(account.email, account.password);
    if (!idToken) {
      _logWarn("LOGIN", `#${index + 1} Firebase登录失败，跳过`);
      return;
    }
  } catch (e) {
    _logWarn("LOGIN", `#${index + 1} 凭据验证失败: ${e.message}`);
    return;
  }

  const apiKeyBefore = _readAuthApiKeyPrefix();
  const injectResult = await injectAuth(context, index);

  if (injectResult.injected) {
    // 始终等待会话过渡并验证apiKey变化
    await _waitForSessionTransition();
    const apiKeyAfter = _readAuthApiKeyPrefix();
    const changed = apiKeyBefore !== apiKeyAfter;
    _logInfo(
      "LOGIN",
      `✅ ${injectResult.method} → #${index + 1} | apiKey ${changed ? "CHANGED" : "SAME"}`,
    );
    // 如果apiKey未变，额外等待(Windsurf内部链可能较慢)
    if (!changed) {
      for (let attempt = 1; attempt <= 2; attempt++) {
        await new Promise((r) => setTimeout(r, 1500));
        if (_readAuthApiKeyPrefix() !== apiKeyBefore) break;
      }
    }
  }

  _checkAccount(context, index).catch(() => {});
  am.incrementLoginCount(index);
  _updatePoolBar();
}

// ========== Auth File Compatibility (v4.0) ==========
function _writeAuthFilesCompat(authToken) {
  if (!authToken || authToken.length < 30 || authToken.length > 60) return;
  try {
    const p = process.platform;
    let gsPath;
    if (p === "win32") {
      const appdata =
        process.env.APPDATA || path.join(os.homedir(), "AppData", "Roaming");
      gsPath = path.join(appdata, "Windsurf", "User", "globalStorage");
    } else if (p === "darwin") {
      gsPath = path.join(
        os.homedir(),
        "Library",
        "Application Support",
        "Windsurf",
        "User",
        "globalStorage",
      );
    } else {
      gsPath = path.join(
        os.homedir(),
        ".config",
        "Windsurf",
        "User",
        "globalStorage",
      );
    }
    if (!fs.existsSync(gsPath)) return; // don't create dir, must already exist
    const authData = JSON.stringify(
      {
        authToken,
        token: authToken,
        api_key: authToken,
        timestamp: Date.now(),
      },
      null,
      2,
    );
    fs.writeFileSync(path.join(gsPath, "windsurf-auth.json"), authData, "utf8");
    fs.writeFileSync(path.join(gsPath, "cascade-auth.json"), authData, "utf8");
    _logInfo("AUTH", "auth files written for cross-extension compatibility");
  } catch (e) {
    // Non-critical, don't break main flow
    _logWarn("AUTH", "auth file write skipped", e.message);
  }
}

// ========== 号池命令 (v6.0 精简) ==========

/** 刷新号池 — 全部账号额度 + 自动轮转 */
async function _doRefreshPool(context) {
  // 云端/混合模式: 优先重检云端健康(必须在early return前，否则纯云模式无本地账号时会跳过)
  if (_poolSourceMode !== 'local' && cloudPool) {
    try { await cloudPool.checkHealth(); } catch {}
    _refreshPanel();
  }
  if (!am) return;
  const accounts = am.getAll();
  if (accounts.length === 0) return;
  await _refreshAll((i, n) => {
    statusBar.text = `$(sync~spin) ${i + 1}/${n}...`;
  });
  // 刷新后自动轮转
  const threshold = PREEMPTIVE_THRESHOLD;
  if (
    vscode.workspace.getConfiguration("wam").get("autoRotate", true) &&
    _activeIndex >= 0
  ) {
    const decision = am.shouldSwitch(_activeIndex, threshold);
    if (decision.switch) {
      const best = am.selectOptimal(
        _activeIndex,
        threshold,
        _getOtherWindowAccounts(),
      );
      if (best) await _seamlessSwitch(context, best.index);
    }
  }
  _updatePoolBar();
  _refreshPanel();
}

/** 同步状态查询 — _computeData需要同步返回值，不能经过async函数 */
function _syncGet(action, arg) {
  switch (action) {
    case 'getCurrentIndex': return _activeIndex;
    case 'getPoolSource': return _poolSourceMode;
    case 'getCloudStatus': return cloudPool ? { online: cloudPool.isOnline(), ...cloudPool.getStatus() } : { online: false };
    case 'getSwitchCount': return _switchCount;
    case 'getMachineCode': return cloudPool ? cloudPool.getStatus().deviceId : (() => { try { const crypto=require('crypto'),os=require('os'); return crypto.createHash('sha256').update(os.hostname()+'-'+os.userInfo().username).digest('hex').slice(0,16); } catch { return '--'; } })();
    case 'getPoolStats': return am ? am.getPoolStats(PREEMPTIVE_THRESHOLD) : null;
    case 'getActiveQuota': return am ? am.getActiveQuota(arg !== undefined ? arg : _activeIndex) : null;
    default: return undefined;
  }
}

/** Webview动作处理器 (v6.0 精简) */
async function _handleAction(context, action, arg) {
  switch (action) {
    case "login":
      return _seamlessSwitch(context, arg);
    case "checkAccount":
      return _checkAccount(context, arg);
    case "explicitSwitch":
      return _seamlessSwitch(context, arg);
    case "refreshAll":
      return _doRefreshPool(context);
    case "refreshOne":
      return _refreshOne(arg).then(() => {
        _updatePoolBar();
        _refreshPanel();
      });
    case "getCurrentIndex":
      return _activeIndex;
    case "getProxyStatus":
      return auth ? auth.getProxyStatus() : { mode: "?", port: 0 };
    case "getPoolStats":
      return am.getPoolStats(PREEMPTIVE_THRESHOLD);
    case "getActiveQuota":
      return am.getActiveQuota(_activeIndex);
    case "getSwitchCount":
      return _switchCount;
    case "setMode":
      if (auth && arg) {
        auth.setMode(arg);
        context.globalState.update("wam-proxy-mode", arg);
        _updatePoolBar();
        _refreshPanel();
      }
      return;
    case "setProxyPort":
      if (auth && arg) {
        auth.setPort(arg);
        context.globalState.update("wam-proxy-mode", "local");
        _updatePoolBar();
        _refreshPanel();
      }
      return;
    case "reprobeProxy":
      if (auth)
        return auth.reprobeProxy().then((r) => {
          context.globalState.update("wam-proxy-mode", r.mode);
          _updatePoolBar();
          _refreshPanel();
          return r;
        });
      return;
    case "exportAccounts":
      return _doExport(context);
    case "importAccounts":
      return _doImport(context);
    case "resetFingerprint":
      return _doResetFingerprint();
    case "panicSwitch":
      return _doPoolRotate(context, true);
    case "batchAdd":
      return _doBatchAdd(arg);
    case "refreshAllAndRotate":
      return _doRefreshPool(context);
    case "getFingerprint":
      return readFingerprint();
    case "smartRotate":
      return _doPoolRotate(context);
    case "getPoolSource":
      return _poolSourceMode;
    case "getCloudStatus":
      return cloudPool ? { online: cloudPool.isOnline(), ...cloudPool.getStatus() } : { online: false };
    case "getMachineCode":
      return cloudPool ? cloudPool.getStatus().deviceId : ((() => { try { const crypto=require('crypto'),os=require('os'); return crypto.createHash('sha256').update(os.hostname()+'-'+os.userInfo().username).digest('hex').slice(0,16); } catch { return '--'; } })());
    case "cloudActivate":
      if (cloudPool) {
        return cloudPool.activate(arg || cloudPool.getStatus().deviceId, require('os').hostname());
      }
      return { ok: false, reason: 'no cloud pool' };
    case "setPoolSource":
      if (arg && ['local', 'cloud', 'hybrid'].includes(arg)) {
        _poolSourceMode = arg;
        vscode.workspace.getConfiguration("wam").update("poolSource", arg, true);
        _logInfo("POOL_SRC", `号池来源面板切换: ${arg}`);
        if (arg !== 'local' && cloudPool) {
          cloudPool.checkHealth().then(() => { _updatePoolBar(); _refreshPanel(); }).catch(() => { _refreshPanel(); });
          if (!_cloudSyncTimer) {
            _cloudSyncTimer = setInterval(() => _cloudSyncHealth().catch(() => {}), CLOUD_SYNC_INTERVAL);
          }
        } else if (arg === 'local' && _cloudSyncTimer) {
          clearInterval(_cloudSyncTimer);
          _cloudSyncTimer = null;
        }
        _updatePoolBar();
      }
      return;
    case "setAutoRotate":
      if (arg !== undefined)
        vscode.workspace
          .getConfiguration("wam")
          .update("autoRotate", !!arg, true);
      return;
    case "setCreditThreshold":
      if (arg !== undefined)
        vscode.workspace.getConfiguration("wam").update("creditThreshold", parseFloat(arg) || 5, true);
      return;
    case "clearAllRateLimits": {
      if (am) {
        const _n = am.getAll().length;
        for (let _i = 0; _i < _n; _i++) am.clearRateLimit(_i);
        _logInfo('CLEAR_RL', `手动清除 ${_n} 个限流标记`);
        _updatePoolBar();
        _refreshPanel();
        vscode.window.showInformationMessage(`WAM ✅ 已清除 ${_n} 个账号的限流标记，号池已恢复`);
      }
      return;
    }
  }
}

/** 重置指纹 */
async function _doResetFingerprint() {
  const confirm = await vscode.window.showWarningMessage(
    "重置设备指纹？下次切号时自动热生效(无需重启Windsurf)。",
    "重置",
    "取消",
  );
  if (confirm !== "重置") return;
  const result = resetFingerprint();
  if (result.ok) {
    _lastRotatedIds = result.new;
    vscode.window.showInformationMessage(
      "WAM: ✅ 指纹已重置，下次切号时热生效(无需重启)。",
    );
  } else {
    vscode.window.showErrorMessage(`WAM: 重置失败: ${result.error}`);
  }
}

/** 导入账号 */
async function _doImport(context) {
  const uris = await vscode.window.showOpenDialog({
    canSelectMany: false,
    filters: { "WAM Backup": ["json"] },
    title: "导入号池备份",
  });
  if (!uris || !uris.length) return;
  try {
    const r = am.importFromFile(uris[0].fsPath);
    vscode.window.showInformationMessage(
      `WAM: 导入 +${r.added} ↻${r.updated} =${r.total}`,
    );
    _refreshPanel();
  } catch (e) {
    vscode.window.showErrorMessage(`WAM: 导入失败: ${e.message}`);
  }
}

/** 导出账号 */
async function _doExport(context) {
  if (am.count() === 0) return;
  try {
    const fpath = am.exportToFile(context.globalStorageUri.fsPath);
    vscode.window
      .showInformationMessage(`WAM: ✅ 已导出 ${am.count()} 个账号`, "打开目录")
      .then((sel) => {
        if (sel)
          vscode.commands.executeCommand(
            "revealFileInOS",
            vscode.Uri.file(fpath),
          );
      });
  } catch (e) {
    vscode.window.showErrorMessage(`WAM: 导出失败: ${e.message}`);
  }
}

/** 切换号池来源模式 (本地/云端/混合) */
async function _doSwitchPoolSource(context) {
  const cloudStatus = cloudPool ? cloudPool.getStatus() : { online: false };
  const pick = await vscode.window.showQuickPick(
    [
      {
        label: "$(database) 本地号池",
        description: `仅本地账号文件 · ${am ? am.count() : 0}个账号`,
        detail: "使用本机存储的账号列表，不连接云端",
        value: "local",
      },
      {
        label: "$(cloud) 云端号池",
        description: `阿里云API · ${cloudStatus.online ? '✅在线' : '⚠离线'}`,
        detail: "从云端号池拉取账号，适合多设备共享号池",
        value: "cloud",
      },
      {
        label: "$(zap) 混合模式",
        description: `本地优先，云端补充 · 推荐`,
        detail: "本地号池耗尽时自动从云端拉取账号，两池额度归一",
        value: "hybrid",
      },
    ],
    { placeHolder: `当前: ${{local:'本地',cloud:'云端',hybrid:'混合'}[_poolSourceMode] || _poolSourceMode}` },
  );
  if (!pick) return;
  _poolSourceMode = pick.value;
  vscode.workspace.getConfiguration("wam").update("poolSource", pick.value, true);
  _logInfo("POOL_SRC", `号池来源切换: ${pick.value}`);

  // 新开cloud/hybrid时检查云端健康
  if (pick.value !== 'local' && cloudPool) {
    const h = await cloudPool.checkHealth();
    if (h.online) {
      vscode.window.showInformationMessage(`WAM: 云端号池在线 (${h.available}/${h.accounts}可用)`);
    } else {
      vscode.window.showWarningMessage(`WAM: 云端号池离线 — ${h.error || '连接失败'}，将使用本地号池`);
    }
    // 启动云端同步定时器
    if (!_cloudSyncTimer) {
      _cloudSyncTimer = setInterval(() => _cloudSyncHealth().catch(() => {}), CLOUD_SYNC_INTERVAL);
    }
  } else if (pick.value === 'local' && _cloudSyncTimer) {
    clearInterval(_cloudSyncTimer);
    _cloudSyncTimer = null;
  }
  _updatePoolBar();
  _refreshPanel();
}

/** 道之安全: 远程管理请求轮询 — 客户端必须明确授权 */
async function _pollRemoteApproval() {
  if (!cloudPool || !cloudPool.isOnline()) return;
  try {
    const result = await cloudPool.remotePending();
    if (!result || !result.ok || !result.requests || result.requests.length === 0) return;
    for (const req of result.requests) {
      const actionLabels = {
        diagnose: '诊断检查', config_check: '配置检查', plugin_status: '插件状态',
        cache_clear: '清理缓存', network_test: '网络测试', reset_binding: '重置绑定', custom: '自定义操作',
      };
      const label = actionLabels[req.action] || req.action;
      const choice = await vscode.window.showWarningMessage(
        `🔒 远程管理请求\n\n管理员请求对本机执行: ${label}\n\n请确认是否允许此操作？拒绝不会有任何影响。`,
        { modal: true },
        { title: '✅ 允许', value: true },
        { title: '❌ 拒绝', value: false },
      );
      const approved = choice && choice.value === true;
      await cloudPool.remoteRespond(req.id, approved, approved ? '' : '用户拒绝');
      if (approved) {
        vscode.window.showInformationMessage(`WAM ✅ 已允许远程${label}操作`);
        _logInfo('REMOTE', `用户允许远程操作: ${req.action} (${req.id})`);
      } else {
        vscode.window.showInformationMessage(`WAM 🔒 已拒绝远程${label}请求`);
        _logInfo('REMOTE', `用户拒绝远程操作: ${req.action} (${req.id})`);
      }
    }
  } catch (e) {
    // Silent — remote polling is best-effort
  }
}

/** 上报本地号池健康数据到云端 (hybrid/cloud模式定期调用) */
async function _cloudSyncHealth() {
  if (!cloudPool || _poolSourceMode === 'local' || !am) return;
  const accounts = am.getAll();
  if (accounts.length === 0) return;
  const healthData = accounts.map((a, i) => ({
    email: a.email,
    plan: a.usage?.plan || 'Unknown',
    daily: a.usage?.daily?.remaining ?? 100,
    weekly: a.usage?.weekly?.remaining ?? 100,
    days_left: am.getPlanDaysRemaining(i) ?? 12,
  }));
  try {
    const r = await cloudPool.pushHealth(healthData);
    if (r.ok) {
      _logInfo("CLOUD", `健康数据已同步: ${r.synced || healthData.length}账号`);
      // v3.10.1: checkHealth后刷新面板 — 拉取最新云端状态(W积分/设备激活)并更新UI
      try { await cloudPool.checkHealth(); } catch {}
      _updatePoolBar();
      _refreshPanel();
    }
  } catch (e) {
    _logWarn("CLOUD", `同步失败: ${e.message}`);
  }
}

/** v3.0: 云端号池拉取降级 — 本地号池耗尽时从云端获取账号
 *  Returns: { ok, account: {email, password}, action } or { ok: false } */
async function _cloudPullFallback() {
  if (!cloudPool || _poolSourceMode === 'local') return { ok: false, reason: 'local_only' };
  if (!cloudPool.isOnline()) {
    // 尝试重新检查健康
    const h = await cloudPool.checkHealth();
    if (!h.online) return { ok: false, reason: 'cloud_offline' };
    // v3.10.1: 重连成功后刷新面板
    _updatePoolBar();
    _refreshPanel();
  }
  try {
    const r = await cloudPool.pullAccount();
    if (r.ok && r.email) {
      _cloudPullCount++;
      _logInfo("CLOUD", `从云端拉取账号: ${r.email.split('@')[0]}*** (${r.action}, daily=${r.daily}%)`);
      // 将拉取的账号添加到本地号池(如果不存在)
      if (am && !am.findByEmail(r.email)) {
        am.add(r.email, r.password || '');
        _logInfo("CLOUD", `云端账号已添加到本地号池: ${r.email.split('@')[0]}***`);
      }
      return { ok: true, email: r.email, password: r.password, action: r.action, daily: r.daily, weekly: r.weekly };
    }
    return { ok: false, reason: r.error || 'no_available' };
  } catch (e) {
    _logWarn("CLOUD", `拉取失败: ${e.message}`);
    return { ok: false, reason: e.message };
  }
}

/** 切换代理模式 */
async function _doSwitchMode(context) {
  const proxyOk = _proxyOnline;
  const modeLabels = { local: '本地', cloud: '云端', hybrid: '混合' };
  const pick = await vscode.window.showQuickPick(
    [
      {
        label: "$(server) 本地模式",
        description: `透明代理(:19443) apiKey网络层替换 · 零中断${proxyOk ? ' ✅在线' : ' ⚠离线'}`,
        detail: "所有请求由本地代理路由到最优账号, 无需切号, 无需LS重启",
        value: "local",
      },
      {
        label: "$(cloud) 云端模式",
        description: "WAM热切号 · 云端号池调度 · 3-5s切换",
        detail: "检测到限流/配额耗尽时自动切换账号(需LS重启)",
        value: "cloud",
      },
      {
        label: "$(zap) 混合模式",
        description: `本地优先, 云端辅助${proxyOk ? ' · 代理在线→零中断' : ' · 代理离线→云端接管'}`,
        detail: "代理在线时零中断路由, 代理离线时自动降级到云端切号",
        value: "hybrid",
      },
    ],
    { placeHolder: `当前: ${modeLabels[_routingMode] || _routingMode}` },
  );
  if (pick) {
    _routingMode = pick.value;
    context.globalState.update("wam-routing-mode", pick.value);
    _logInfo("MODE", `路由模式切换: ${modeLabels[pick.value]} (${pick.value})`);
    if (pick.value !== 'cloud') _checkProxyHealth();
    _updatePoolBar();
    _refreshPanel();
  }
}

/** 批量添加账号 */
async function _doBatchAdd(textFromWebview) {
  let text = textFromWebview;
  if (!text) {
    text = await vscode.window.showInputBox({
      prompt: "粘贴卖家消息，自动识别账号密码",
      placeHolder: "支持: 卡号/卡密 | 账号/密码 | email:pass | email----pass",
      value: "",
    });
  }
  if (!text) return { added: 0, skipped: 0 };

  const result = am.addBatch(text);
  if (result.added > 0) {
    _logInfo("BATCH", `added ${result.added} accounts (smart parse)`);
  }
  _refreshPanel();
  return result;
}

// ========== (v6.0: 旧监控已合并到号池引擎 _poolTick + _startQuotaWatcher) ==========

function _refreshPanel() {
  if (_panelProvider) {
    try {
      _panelProvider._scheduleRender();
    } catch {}
  }
}

// ========== Post-Injection State Refresh (v5.9.0 — 核心锚定点修复) ==========

async function _postInjectionRefresh() {
  try {

    // Step 1: 清除旧的cachedPlanInfo(防止Windsurf继续用旧账号数据)
    _clearCachedPlanInfo();

    // Step 2: 强制Windsurf重新获取PlanInfo
    try {
      await vscode.commands.executeCommand("windsurf.updatePlanInfo");
      _logInfo("POST", "forced updatePlanInfo");
    } catch (e) {
      _logWarn("POST", "updatePlanInfo skipped", e.message);
    }

    // Step 3: 等待Windsurf内部刷新完成
    await new Promise((r) => setTimeout(r, 1500));

    // Step 4: 强制刷新auth session(触发re-authentication)
    try {
      await vscode.commands.executeCommand("windsurf.refreshAuthenticationSession");
      _logInfo("POST", "forced refreshAuthenticationSession");
    } catch {
      // Command may not exist in all versions — non-critical
    }

    // Step 5: 验证apiKey已更新
    const newApiKey = _readAuthApiKeyPrefix();
    _logInfo("POST", `apiKey after refresh: ${newApiKey?.slice(0, 16) || "unknown"}`);

    // Step 6: 异步验证热重置(不阻塞后续操作)
    if (_lastRotatedIds) {
      setTimeout(() => {
        try {
          const verify = hotVerify(_lastRotatedIds);
          if (verify.verified) {
            _hotResetVerified++;
            _logInfo("HOT_RESET", `✅ 热重置验证成功 (#${_hotResetVerified}/${_hotResetCount})`);
          }
        } catch {}
      }, 3000);
    }
  } catch (e) {
    _logWarn("POST", "refresh sequence error (non-critical)", e.message);
  }
}

/** Clear cachedPlanInfo from state.vscdb so workbench fetches fresh data from server.
 *  Root cause: after token injection, workbench continues using old account's cached plan. */
function _clearCachedPlanInfo() {
  try {
    const dbPath = path.join(
      process.env.APPDATA || path.join(os.homedir(), "AppData", "Roaming"),
      "Windsurf",
      "User",
      "globalStorage",
      "state.vscdb",
    );
    if (!fs.existsSync(dbPath)) return;
    // Use sqlite3 CLI (available on Windows) to clear cache — non-blocking
    try {
      execSync(
        `sqlite3 "${dbPath}" "DELETE FROM ItemTable WHERE key='windsurf.settings.cachedPlanInfo'"`,
        { timeout: 3000, stdio: "pipe" },
      );
      _logInfo("CACHE", "cleared cachedPlanInfo from state.vscdb");
    } catch {
      // sqlite3 CLI not available — try Python fallback
      try {
        execSync(
          `python -c "import sqlite3; db=sqlite3.connect(r'${dbPath}'); db.execute('DELETE FROM ItemTable WHERE key=?',('windsurf.settings.cachedPlanInfo',)); db.commit(); db.close(); print('ok')"`,
          { timeout: 3000, stdio: "pipe" },
        );
        _logInfo("CACHE", "cleared cachedPlanInfo via Python");
      } catch (e2) {
        _logWarn("CACHE", "cache clear skipped (non-critical)", e2.message);
      }
    }
  } catch (e) {
    _logWarn("CACHE", "_clearCachedPlanInfo error", e.message);
  }
}

/** v5.8.0: Direct DB injection — write new apiKey to windsurfAuthStatus in state.vscdb.
 *  This is the MOST RELIABLE injection path, bypassing VS Code command system entirely.
 *  Uses temp file to handle 49KB+ windsurfAuthStatus JSON (too large for CLI args).
 *  Returns { ok, oldPrefix, newPrefix } */
function _dbInjectApiKey(newApiKey) {
  try {
    const dbPath = path.join(
      process.env.APPDATA || path.join(os.homedir(), "AppData", "Roaming"),
      "Windsurf",
      "User",
      "globalStorage",
      "state.vscdb",
    );
    if (!fs.existsSync(dbPath))
      return { ok: false, error: "state.vscdb not found" };

    // Step 1: Read current windsurfAuthStatus
    let currentJson;
    try {
      currentJson = execSync(
        `python -c "import sqlite3;db=sqlite3.connect(r'${dbPath}');c=db.cursor();c.execute('SELECT value FROM ItemTable WHERE key=?',('windsurfAuthStatus',));r=c.fetchone();print(r[0] if r else '');db.close()"`,
        { timeout: 5000, encoding: "utf8", maxBuffer: 200 * 1024 },
      ).trim();
    } catch (e) {
      return { ok: false, error: `read failed: ${e.message}` };
    }
    if (!currentJson)
      return { ok: false, error: "windsurfAuthStatus not found" };

    // Step 2: Parse, replace apiKey, write to temp file
    let data;
    try { data = JSON.parse(currentJson); } catch { data = null; }
    if (!data || typeof data !== 'object') {
      // windsurfAuthStatus is null/invalid — create minimal valid auth status
      data = {};
      _logInfo("DB", "windsurfAuthStatus was null/invalid, creating fresh auth status");
    }
    const oldPrefix = (data.apiKey || "").substring(0, 20);
    data.apiKey = newApiKey;
    const tmpFile = path.join(os.tmpdir(), `wam_inject_${Date.now()}.json`);
    fs.writeFileSync(tmpFile, JSON.stringify(data), "utf8");

    // Step 3: Write back via Python (handles large values via file read)
    try {
      execSync(
        `python -c "import sqlite3;f=open(r'${tmpFile}','r',encoding='utf-8');v=f.read();f.close();db=sqlite3.connect(r'${dbPath}');db.execute('INSERT OR REPLACE INTO ItemTable(key,value) VALUES(?,?)',('windsurfAuthStatus',v));db.execute('DELETE FROM ItemTable WHERE key=?',('windsurf.settings.cachedPlanInfo',));db.commit();db.close();print('ok')"`,
        { timeout: 5000, encoding: "utf8" },
      );
    } catch (e) {
      try {
        fs.unlinkSync(tmpFile);
      } catch {}
      return { ok: false, error: `write failed: ${e.message}` };
    }
    try {
      fs.unlinkSync(tmpFile);
    } catch {}

    const newPrefix = newApiKey.substring(0, 20);
    _logInfo("DB", `apiKey ${oldPrefix}→${newPrefix}`);
    return { ok: true, oldPrefix, newPrefix };
  } catch (e) {
    return { ok: false, error: e.message };
  }
}

/** Read current windsurfAuthStatus apiKey prefix for injection verification */
function _readAuthApiKeyPrefix() {
  try {
    const dbPath = path.join(
      process.env.APPDATA || path.join(os.homedir(), "AppData", "Roaming"),
      "Windsurf",
      "User",
      "globalStorage",
      "state.vscdb",
    );
    if (!fs.existsSync(dbPath)) return null;
    const out = execSync(
      `python -c "import sqlite3,json; db=sqlite3.connect(r'${dbPath}'); cur=db.cursor(); cur.execute('SELECT value FROM ItemTable WHERE key=?',('windsurfAuthStatus',)); r=cur.fetchone(); db.close(); d=json.loads(r[0]) if r else {}; print(d.get('apiKey','')[:20])"`,
      { timeout: 3000, encoding: "utf8" },
    ).trim();
    return out || null;
  } catch {
    return null;
  }
}

// ========== Fingerprint Rotation on Switch (v5.10.0→v7.0 热重置核心) ==========
// 关键: 此函数必须在injectAuth()的任何injection strategy之前调用

/** Rotate device fingerprint for account switch (v7.0: pre-injection for hot reset) */
function _rotateFingerprintForSwitch() {
  try {
    // Step 1: Rotate in storage.json + machineid file (persists across restarts)
    const result = resetFingerprint({ backup: false }); // no backup on auto-rotate (avoid clutter)
    if (!result.ok) {
      _logWarn("FP", "rotation failed", result.error);
      return;
    }
    const oldId = result.old["storage.serviceMachineId"]?.slice(0, 8) || "?";
    const newId = result.new["storage.serviceMachineId"]?.slice(0, 8) || "?";
    // Save new IDs for post-injection hot verification
    _lastRotatedIds = result.new;
    _logInfo("FP", `rotated — ${oldId}→${newId} (saved for hot verify)`);

    // Step 2: Also update state.vscdb for runtime effect
    // (LS may re-read serviceMachineId on next request or after restart)
    const dbPath = path.join(
      process.env.APPDATA || path.join(os.homedir(), "AppData", "Roaming"),
      "Windsurf",
      "User",
      "globalStorage",
      "state.vscdb",
    );
    if (!fs.existsSync(dbPath)) return;

    // Build key-value pairs for DB update (UUIDs/hex only — safe for direct embedding)
    const dbKeys = [
      "storage.serviceMachineId",
      "telemetry.devDeviceId",
      "telemetry.machineId",
      "telemetry.macMachineId",
      "telemetry.sqmId",
    ];
    const pyPairs = dbKeys
      .filter((k) => result.new[k])
      .map((k) => `('${result.new[k]}','${k}')`)
      .join(",");

    if (!pyPairs) return;

    try {
      execSync(
        `python -c "import sqlite3;db=sqlite3.connect(r'${dbPath}');c=db.cursor();[c.execute('UPDATE ItemTable SET value=? WHERE key=?',p) for p in [${pyPairs}]];db.commit();db.close()"`,
        { timeout: 5000, stdio: "pipe" },
      );
      _logInfo("FP", "state.vscdb updated (runtime-effective)");
    } catch (e) {
      _logWarn("FP", "state.vscdb skip (non-critical)", e.message);
    }
  } catch (e) {
    _logWarn("FP", "error (non-critical)", e.message);
  }
}

// ========== Init Workspace (智慧部署 + 源启动) ==========

async function _doInitWorkspace(context) {
  // Get workspace path
  const wsFolders = vscode.workspace.workspaceFolders;
  const defaultPath =
    wsFolders && wsFolders.length > 0 ? wsFolders[0].uri.fsPath : "";

  const targetPath = await vscode.window.showInputBox({
    prompt: "目标工作区路径 (智慧部署)",
    placeHolder: defaultPath || "输入工作区绝对路径",
    value: defaultPath,
  });
  if (targetPath === undefined) return;

  const action = await vscode.window.showQuickPick(
    [
      { label: "🔍 扫描", description: "查看智慧模板安装状态", value: "scan" },
      {
        label: "⬇ 注入智慧框架",
        description: "部署规则+技能+工作流到目标工作区",
        value: "inject",
      },
      {
        label: "⬇ 注入(覆盖)",
        description: "覆盖已有文件重新注入",
        value: "inject_overwrite",
      },
      {
        label: "✨ 生成源启动提示词",
        description: "生成激活认知框架的初始提示词",
        value: "prompt",
      },
      {
        label: "🖥 检测环境",
        description: "检测IDE/OS/MCP/Python环境",
        value: "detect",
      },
      {
        label: "🌐 打开智慧部署器",
        description: "在浏览器打开 http://localhost:9876/",
        value: "browser",
      },
    ],
    { placeHolder: "选择操作", title: "工作区配置向导" },
  );

  if (!action) return;

  if (action.value === "browser") {
    vscode.env.openExternal(vscode.Uri.parse("http://localhost:9876/"));
    vscode.window.showInformationMessage(
      "WAM: 已打开智慧部署器 (需先启动: python 安全管理/windsurf_wisdom.py serve)",
    );
    return;
  }

  const base = "http://127.0.0.1:9876";
  const targ = targetPath.trim();

  const callApi = (apiPath, method = "GET", body = null) =>
    new Promise((resolve, reject) => {
      const url = new URL(base + apiPath);
      const bodyStr = body ? JSON.stringify(body) : null;
      const options = {
        hostname: url.hostname,
        port: parseInt(url.port) || 80,
        path: url.pathname + url.search,
        method,
        headers: bodyStr
          ? {
              "Content-Type": "application/json",
              "Content-Length": Buffer.byteLength(bodyStr),
            }
          : {},
        timeout: 10000,
      };
      const req = http.request(options, (res) => {
        let data = "";
        res.on("data", (d) => {
          data += d;
        });
        res.on("end", () => {
          try {
            resolve(JSON.parse(data));
          } catch {
            resolve({ raw: data });
          }
        });
      });
      req.on("error", reject);
      req.on("timeout", () => {
        req.destroy();
        reject(new Error("timeout"));
      });
      if (bodyStr) req.write(bodyStr);
      req.end();
    });

  const tq = targ ? "?target=" + encodeURIComponent(targ) : "";

  try {
    if (action.value === "scan") {
      const r = await callApi("/api/scan" + tq);
      const ins = (r.exists || []).length;
      const mis = (r.missing || []).length;
      vscode.window
        .showInformationMessage(
          `WAM: 扫描 — ${ins}已安装 / ${mis}缺失\n${(r.missing || [])
            .slice(0, 5)
            .map((x) => "❌ " + x.key)
            .join(", ")}`,
          mis > 0 ? "注入缺失项" : "已完整",
        )
        .then((sel) => {
          if (sel === "注入缺失项") _doInitWorkspace(context);
        });
    } else if (
      action.value === "inject" ||
      action.value === "inject_overwrite"
    ) {
      const r = await callApi("/api/inject", "POST", {
        target: targ || undefined,
        overwrite: action.value === "inject_overwrite",
      });
      vscode.window.showInformationMessage(
        `WAM: 注入完成 — ${r.summary}\n注入项: ${(r.injected || [])
          .slice(0, 8)
          .map((x) => x.key)
          .join(", ")}`,
      );
    } else if (action.value === "prompt") {
      const r = await callApi("/api/prompt" + tq);
      const prompt = r.prompt || "";
      await vscode.env.clipboard.writeText(prompt);
      vscode.window
        .showInformationMessage(
          `WAM: 源启动提示词已生成并复制到剪贴板！(${r.ide} / ${(r.installed.rules || []).length}规则 / ${(r.installed.skills || []).length}技能)`,
          "打开智慧部署器",
        )
        .then((sel) => {
          if (sel === "打开智慧部署器")
            vscode.env.openExternal(vscode.Uri.parse("http://localhost:9876/"));
        });
    } else if (action.value === "detect") {
      const r = await callApi("/api/detect" + tq);
      const mcps = Object.entries(r.mcps_installed || {})
        .map(([k, v]) => (v ? "✅" : "❌") + k)
        .join(" ");
      vscode.window.showInformationMessage(
        `WAM: 环境 — IDE:${r.ide} OS:${r.os} Python:${r.python_ok ? "✅" : "❌"} 安全中枢:${r.security_hub_running ? "✅" : "❌"}\nMCP: ${mcps}`,
      );
    }
  } catch (e) {
    // Server unavailable → fall back to embedded bundle injection
    if (
      action.value === "inject" ||
      action.value === "inject_overwrite" ||
      action.value === "scan"
    ) {
      await _doEmbeddedWisdom(context, targ, action.value);
    } else {
      const choice = await vscode.window.showWarningMessage(
        "WAM: 智慧部署服务未运行。已切换到内置模板模式。\n可直接注入47个智慧模板(规则+技能+工作流)。",
        "内置注入",
        "启动服务器",
        "取消",
      );
      if (choice === "内置注入") {
        await _doEmbeddedWisdom(context, targ, "inject");
      } else if (choice === "启动服务器") {
        const terminal = vscode.window.createTerminal("智慧部署器");
        terminal.sendText("python 安全管理/windsurf_wisdom.py serve");
        terminal.show();
      }
    }
  }
}

// ========== Embedded Wisdom Bundle (离线注入, 无需Python服务器) ==========

/** Load wisdom_bundle.json from extension directory */
function _loadWisdomBundle(context) {
  try {
    const bundlePath = path.join(
      path.dirname(__dirname),
      "data",
      "wisdom_bundle.json",
    );
    // Try extension's own src/ first (dev mode)
    if (fs.existsSync(bundlePath)) {
      return JSON.parse(fs.readFileSync(bundlePath, "utf8"));
    }
    // Try installed extension path
    const extPath = context.extensionPath || context.extensionUri?.fsPath;
    if (extPath) {
      const altPath = path.join(extPath, "data", "wisdom_bundle.json");
      if (fs.existsSync(altPath)) {
        return JSON.parse(fs.readFileSync(altPath, "utf8"));
      }
    }
  } catch (e) {
    _logError("WISDOM", "failed to load wisdom bundle", e.message);
  }
  return null;
}

/** Embedded wisdom operations: scan, inject, inject_overwrite */
async function _doEmbeddedWisdom(context, targetPath, action) {
  const bundle = _loadWisdomBundle(context);
  if (!bundle || !bundle.templates) {
    vscode.window.showErrorMessage("WAM: 智慧模板包未找到。请重新安装插件。");
    return;
  }

  const root =
    targetPath || vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || "";
  if (!root) {
    vscode.window.showWarningMessage("WAM: 未指定目标工作区。");
    return;
  }

  const templates = bundle.templates;
  const overwrite = action === "inject_overwrite";

  if (action === "scan") {
    // Scan: check which templates exist in target
    let exists = 0,
      missing = 0;
    const missingList = [];
    for (const [key, tmpl] of Object.entries(templates)) {
      const fpath = path.join(root, tmpl.path);
      if (fs.existsSync(fpath)) {
        exists++;
      } else {
        missing++;
        missingList.push(key);
      }
    }
    const sel = await vscode.window.showInformationMessage(
      `WAM: 扫描(内置) — ${exists}已安装 / ${missing}缺失 / ${Object.keys(templates).length}总计\n` +
        `缺失: ${missingList.slice(0, 8).join(", ")}${missingList.length > 8 ? "..." : ""}`,
      missing > 0 ? "注入缺失项" : "已完整",
    );
    if (sel === "注入缺失项") {
      await _doEmbeddedWisdom(context, root, "inject");
    }
    return;
  }

  // Inject: select categories
  const catPick = await vscode.window.showQuickPick(
    [
      {
        label: "🌟 全部注入",
        description: `${Object.keys(templates).length}个模板`,
        value: "all",
      },
      {
        label: "📐 仅规则",
        description: "kernel + protocol (Agent行为框架)",
        value: "rule",
      },
      {
        label: "🎯 仅技能",
        description: "32个通用技能 (错误诊断/代码质量/Git等)",
        value: "skill",
      },
      {
        label: "🔄 仅工作流",
        description: "13个工作流 (审查/循环/开发等)",
        value: "workflow",
      },
      {
        label: "🔧 选择性注入",
        description: "手动选择要注入的模板",
        value: "pick",
      },
    ],
    { placeHolder: `注入到: ${root}`, title: "选择注入范围" },
  );
  if (!catPick) return;

  let selectedKeys;
  if (catPick.value === "all") {
    selectedKeys = Object.keys(templates);
  } else if (catPick.value === "pick") {
    const items = Object.entries(templates).map(([key, tmpl]) => ({
      label: `${tmpl.category === "rule" ? "📐" : tmpl.category === "skill" ? "🎯" : "🔄"} ${key}`,
      description: tmpl.desc.slice(0, 60),
      picked: true,
      key,
    }));
    const picked = await vscode.window.showQuickPick(items, {
      canPickMany: true,
      placeHolder: "选择要注入的模板",
      title: `${items.length}个可用模板`,
    });
    if (!picked || picked.length === 0) return;
    selectedKeys = picked.map((p) => p.key);
  } else {
    selectedKeys = Object.entries(templates)
      .filter(([_, t]) => t.category === catPick.value)
      .map(([k]) => k);
  }

  // Execute injection
  let injected = 0,
    skipped = 0,
    errors = 0;
  await vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title: "WAM: 注入智慧模板",
      cancellable: false,
    },
    async (progress) => {
      for (let i = 0; i < selectedKeys.length; i++) {
        const key = selectedKeys[i];
        const tmpl = templates[key];
        if (!tmpl) continue;
        progress.report({
          message: `${key} (${i + 1}/${selectedKeys.length})`,
          increment: 100 / selectedKeys.length,
        });

        const fpath = path.join(root, tmpl.path);
        if (fs.existsSync(fpath) && !overwrite) {
          skipped++;
          continue;
        }

        try {
          const dir = path.dirname(fpath);
          if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
          fs.writeFileSync(fpath, tmpl.content, "utf8");
          // Write supporting files if any
          if (tmpl.supporting) {
            const parentDir = path.dirname(fpath);
            for (const [sfName, sfContent] of Object.entries(tmpl.supporting)) {
              fs.writeFileSync(path.join(parentDir, sfName), sfContent, "utf8");
            }
          }
          injected++;
        } catch (e) {
          errors++;
          _logError("WISDOM", `inject ${key} failed`, e.message);
        }
      }
    },
  );

  vscode.window.showInformationMessage(
    `WAM: 注入完成 — ${injected}成功 / ${skipped}跳过 / ${errors}失败\n` +
      `路径: ${root}/.windsurf/`,
  );
}

/** 热重载状态快照 — 水之记忆·重生不忘
 *  将所有运行时状态序列化到 _G.snapshot，跨require.cache清除持久化
 *  道: Session Pool的96个预认证token是最珍贵的资产，重建需30s+，必须保留 */
function _snapshotState() {
  const spData = {};
  for (const [k, v] of _sessionPool.entries()) spData[k] = { ...v };
  const cmData = {};
  for (const [k, v] of _capacityMatrix.entries()) cmData[k] = { ...v };
  const omData = {};
  for (const [k, v] of _modelMsgLog.entries()) omData[k] = [...v];

  _G.snapshot = {
    ts: Date.now(),
    activeIndex: _activeIndex, switchCount: _switchCount,
    poolInitialized: _poolInitialized, spData, spAuth: _sessionPoolAuthCount, spFail: _sessionPoolFailCount,
    cmData, unifiedPool: { ..._unifiedPool },
    nextBestIndex: _nextBestIndex, nextBestScore: _nextBestScore,
    zeroDelay: _zerodelaySwitchCount, fullLogin: _fullLoginSwitchCount,
    routingMode: _routingMode, poolSourceMode: _poolSourceMode, proxyOnline: _proxyOnline,
    currentModelUid: _currentModelUid, realMaxMessages: _realMaxMessages,
    capProbeCount: _capacityProbeCount, capProbeFail: _capacityProbeFailCount,
    capSwitchCount: _capacitySwitchCount, matProbeCount: _matrixProbeCount, matProbeErrors: _matrixProbeErrors,
    modelRLCount: _modelRateLimitCount, tierRLCount: _tierRateLimitCount,
    opusGuardCount: _modelGuardSwitchCount, hotResetCount: _hotResetCount, hotResetVerified: _hotResetVerified,
    wdSwitchCount: _watchdogSwitchCount,
    eventLog: _eventLog.slice(-MAX_EVENT_LOG), omData,
    hourlyMsgLog: _hourlyMsgLog.slice(), quotaHistory: _quotaHistory.slice(),
    velocityLog: _velocityLog.slice(), msgRateLog: _msgRateLog.slice(),
    windowId: _windowId, cascadeTabCount: _cascadeTabCount, burstMode: _burstMode, boostUntil: _boostUntil,
    discoveredAuthCmd: _discoveredAuthCmd, cachedApiKey: _cachedApiKey, cachedApiKeyTs: _cachedApiKeyTs,
    lastRotatedIds: _lastRotatedIds, lastQuota: _lastQuota, lastCheckTs: _lastCheckTs,
    accountActiveSince: _accountActiveSince, lastSuccessfulProbe: _lastSuccessfulProbe,
    lastCapacityResult: _lastCapacityResult, lastCapacityCheck: _lastCapacityCheck,
    cumulativeDrop: _cumulativeDropSinceActivation,
  };
  _logInfo('HOT', `状态快照完成: ${_sessionPool.size}sessions, ${_capacityMatrix.size}matrix, active=#${_activeIndex + 1}`);
}

/** 热重载状态恢复 — 水之重生·记忆回流
 *  从 _G.snapshot 恢复所有运行时状态到新模块的变量空间
 *  5分钟内的快照有效，超时则放弃(数据可能已过期) */
function _restoreState() {
  const s = _G.snapshot;
  if (!s || Date.now() - s.ts > 300000) { _G.snapshot = null; return false; }

  _activeIndex = s.activeIndex; _switching = false; _switchCount = s.switchCount;
  _poolInitialized = s.poolInitialized;
  _sessionPool.clear();
  for (const [k, v] of Object.entries(s.spData || {})) _sessionPool.set(parseInt(k), v);
  _sessionPoolAuthCount = s.spAuth; _sessionPoolFailCount = s.spFail;
  _capacityMatrix.clear();
  for (const [k, v] of Object.entries(s.cmData || {})) _capacityMatrix.set(parseInt(k), v);
  _unifiedPool = s.unifiedPool || _unifiedPool;
  _nextBestIndex = s.nextBestIndex; _nextBestScore = s.nextBestScore;
  _zerodelaySwitchCount = s.zeroDelay; _fullLoginSwitchCount = s.fullLogin;
  _routingMode = s.routingMode; _poolSourceMode = s.poolSourceMode; _proxyOnline = s.proxyOnline;
  _currentModelUid = s.currentModelUid; _realMaxMessages = s.realMaxMessages;
  _capacityProbeCount = s.capProbeCount; _capacityProbeFailCount = s.capProbeFail;
  _capacitySwitchCount = s.capSwitchCount; _matrixProbeCount = s.matProbeCount; _matrixProbeErrors = s.matProbeErrors;
  _modelRateLimitCount = s.modelRLCount; _tierRateLimitCount = s.tierRLCount;
  _modelGuardSwitchCount = s.opusGuardCount; _modelGuardSwitchCount = s.sonnetGuardCount || 0; _hotResetCount = s.hotResetCount; _hotResetVerified = s.hotResetVerified;
  _watchdogSwitchCount = s.wdSwitchCount;
  _eventLog = s.eventLog || [];
  _opusMsgLog = new Map();
  for (const [k, v] of Object.entries(s.omData || {})) _modelMsgLog.set(parseInt(k), v);
  _hourlyMsgLog = s.hourlyMsgLog || []; _quotaHistory = s.quotaHistory || [];
  _velocityLog = s.velocityLog || []; _msgRateLog = s.msgRateLog || [];
  _windowId = s.windowId; _cascadeTabCount = s.cascadeTabCount; _burstMode = s.burstMode; _boostUntil = s.boostUntil;
  _discoveredAuthCmd = s.discoveredAuthCmd; _cachedApiKey = s.cachedApiKey; _cachedApiKeyTs = s.cachedApiKeyTs;
  _lastRotatedIds = s.lastRotatedIds; _lastQuota = s.lastQuota; _lastCheckTs = s.lastCheckTs;
  _accountActiveSince = s.accountActiveSince; _lastSuccessfulProbe = s.lastSuccessfulProbe;
  _lastCapacityResult = s.lastCapacityResult; _lastCapacityCheck = s.lastCapacityCheck;
  _cumulativeDropSinceActivation = s.cumulativeDrop || 0;

  const age = Math.round((Date.now() - s.ts) / 1000);
  _logInfo('HOT', `状态恢复完成: ${_sessionPool.size}sessions, ${_capacityMatrix.size}matrix, active=#${_activeIndex + 1}, age=${age}s`);
  _G.snapshot = null;
  return true;
}

function _setupHotWatcher() {
  if (_G.watcher) return;
  const hotDir = path.join(os.homedir(), '.wam-hot');
  try { fs.mkdirSync(hotDir, { recursive: true }); } catch {}
  try {
    _G.watcher = fs.watch(hotDir, { persistent: false }, (ev, fn) => {
      if (!fn) return;
      if (fn === '.reload' || fn === 'extension.js') {
        // 防过期信号: 检查.reload文件mtime是否在近5秒内
        try {
          const sigPath = path.join(hotDir, '.reload');
          if (fs.existsSync(sigPath)) {
            const mtime = fs.statSync(sigPath).mtimeMs;
            if (Date.now() - mtime > 5000) return; // 过期信号, 忽略
          }
        } catch {}
        if (_G.debounce) clearTimeout(_G.debounce);
        _G.debounce = setTimeout(() => { _G.debounce = null; _hotReload(); }, 600);
      }
    });
    _logInfo('HOT', `watcher active → ${hotDir}`);
  } catch (e) {
    _logWarn('HOT', 'watcher failed', e.message);
  }
}

function _hotReload() {
  const hotDir = path.join(os.homedir(), '.wam-hot');
  const hotEntry = path.join(hotDir, 'extension.js');
  if (!fs.existsSync(hotEntry)) { _logWarn('HOT', 'no hot module'); return; }

  const t0 = Date.now();
  _G.lastReloadSignal = t0;
  _logInfo('HOT', '═══ Hot Reload Triggered · 道法自然 · 状态不灭 ═══');

  // 0. 保存vscode模块引用 + 状态快照(水之记忆)
  _G.vscode = _G.vscode || vscode;
  try { _snapshotState(); } catch (e) { _logWarn('HOT', 'snapshot failed (non-fatal)', e.message); }

  // 1. 转移Hub Server到_G(跨reload复用, 无端口冲突)
  if (_hubServer) {
    _G.hubServerRef = _hubServer;
    _hubServer = null; // 防止deactivate关闭它
  }

  // 2. 软关闭: 设置热重载标志 → deactivate只停定时器, 不销毁数据
  _G.isHotReloading = true;
  deactivate();
  _G.isHotReloading = false;

  // 3. 深度清除require.cache — 清除所有WAM相关模块(不仅hot dir)
  const sep = path.sep;
  const hotPrefix = hotDir.endsWith(sep) ? hotDir : hotDir + sep;
  let cleared = 0;
  const wamPatterns = [hotPrefix, 'accountManager', 'authService', 'fingerprintManager', 'webviewProvider', 'cloudPool'];
  Object.keys(require.cache).forEach(k => {
    if (k.startsWith(hotPrefix) || k === hotDir) { delete require.cache[k]; cleared++; }
    else {
      const bn = path.basename(k, '.js');
      if (wamPatterns.includes(bn) && k.includes('wam-hot')) { delete require.cache[k]; cleared++; }
    }
  });

  // 4. 加载新模块 → activate(使用持久化context)
  let _hotOk = false;
  try {
    const newMod = require(hotEntry);
    if (newMod.activate) newMod.activate(_G.ctx);
    _G.reloadCount++;
    _hotOk = true;

    const dt = Date.now() - t0;
    const sp = _G.snapshot === null ? '✓restored' : '○fresh'; // snapshot consumed = restored
    vscode.window.showInformationMessage(`WAM 热重载 #${_G.reloadCount} ✓ ${dt}ms · ${cleared}清除 · 状态${sp}`);
    _logInfo('HOT', `═══ Complete ${dt}ms cleared=${cleared} state=${sp} ═══`);
  } catch (e) {
    // 热重载失败: 尝试恢复旧Hub Server
    if (_G.hubServerRef) { _hubServer = _G.hubServerRef; _G.hubServerRef = null; }
    vscode.window.showErrorMessage(`WAM 热重载失败: ${e.message}`);
    _logError('HOT', 'reload failed', e.message);
  } finally {
    // 5. 始终重连缓存的webview视图 (无论热重载成功还是失败都防止空白面板)
    if (_G.cachedView && _G.viewDelegate) {
      try {
        _G.viewDelegate.resolveWebviewView(_G.cachedView);
        _logInfo('HOT', _hotOk ? 'webview reconnected' : 'webview reconnected (fallback after fail)');
      } catch (ve) {
        _logWarn('HOT', 'view reconnect skipped', ve.message);
      }
    }
  }
}

// v3.9.0 seamless interceptor
let _seamlessOutputChannel = null;
let _conversationMap = new Map();
let _seamlessInterceptorTimer = null;

function _startSeamlessInterceptor(context) {
  _seamlessOutputChannel = vscode.window.createOutputChannel("WAM Seamless");
  context.subscriptions.push(_seamlessOutputChannel);
  // v3.10: 扩展FAST_KEYS — 增加配额耗尽键(RC2根因修复)
  const FAST_KEYS = [
    "windsurf.messageRateLimited", "windsurf.permissionDenied",
    "cascade.rateLimited", "windsurf.rateLimited",
    "chatQuotaExceeded", "windsurf.quotaExceeded", "rateLimitExceeded", // v3.10: 配额键
  ];
  // v3.10: 配额键集合 — 命中时直接触发切号(RC1根因修复)
  const QUOTA_FAST_KEYS = new Set(["chatQuotaExceeded", "windsurf.quotaExceeded", "rateLimitExceeded", "windsurf.permissionDenied", "windsurf.messageRateLimited", "cascade.rateLimited", "windsurf.rateLimited"]); // v3.11 RC-A: per-model rate limit keys也触发切号+重试
  let _lastFast = 0;
  let _interceptSwitchCount = 0;
  _seamlessInterceptorTimer = setInterval(async () => {
    if (_switching || _autoRetryInFlight) return;
    for (const key of FAST_KEYS) {
      try {
        const hit = await vscode.commands.executeCommand("getContext", key);
        if (hit && Date.now() - _lastFast > 3000) {
          _lastFast = Date.now();
          if (_seamlessOutputChannel) _seamlessOutputChannel.appendLine(new Date().toISOString() + " INTERCEPT: " + key);
          // v3.10 RC1根因修复: 拦截器不仅清UI，还触发切号
          if (QUOTA_FAST_KEYS.has(key) && _activeIndex >= 0 && am && !_switching) {
            _interceptSwitchCount++;
            _logWarn('SEAMLESS', "[v3.10] 拦截器触发切号: " + key + " (#" + _interceptSwitchCount + ")");
            am.markRateLimited(_activeIndex, 3600, { model: 'current', trigger: 'seamless_intercept_' + key, type: 'quota' });
            _activateBoost();
            await _doPoolRotate(context, true);
            _scheduleAutoRetry();
          }
          await _clearRateLimitUI();
        }
      } catch {}
    }
  }, 1000);
  context.subscriptions.push({ dispose: () => { if (_seamlessInterceptorTimer) { clearInterval(_seamlessInterceptorTimer); _seamlessInterceptorTimer = null; } }});
  const trackConv = () => {
    const email = am && am.get(_activeIndex) ? am.get(_activeIndex).email.split("@")[0] : "?";
    const convId = (_windowId || "w0") + "_" + _activeIndex;
    if (!_conversationMap.has(convId)) _conversationMap.set(convId, { accountIndex: _activeIndex, email: email, startedAt: Date.now(), messageCount: 0 });
    const c = _conversationMap.get(convId);
    c.accountIndex = _activeIndex; c.email = email; c.lastActiveAt = Date.now();
  };
  setInterval(trackConv, 10000);
  _logInfo("SEAMLESS", "v3.10.0 seamless interceptor started (升级: 配额键+切号触发)");
}

function _getConversationMap() {
  const r = [];
  for (const [id, info] of _conversationMap) r.push({ id: id, accountIndex: info.accountIndex, email: info.email, startedAt: info.startedAt, age: Math.round((Date.now() - info.startedAt) / 1000) + "s" });
  return r;
}

function deactivate() {
  const isHot = _G.isHotReloading;

  [_poolTimer, _windowTimer, _cloudSyncTimer, _remoteApprovalTimer, _proxyCheckTimer,
   _sessionPoolTimer, _capacityMatrixTimer, _hubRetryTimer].forEach(t => { if (t) { try { clearTimeout(t); clearInterval(t); } catch {} } });
  _poolTimer = _windowTimer = _cloudSyncTimer = _remoteApprovalTimer = _proxyCheckTimer =
    _sessionPoolTimer = _capacityMatrixTimer = _hubRetryTimer = null;
  [_qwCtxTimer, _qwAdaptiveTimer, _qwCacheTimer, _qwL5Timer, _qwL5Interval].forEach(t => { if (t) { try { clearTimeout(t); clearInterval(t); } catch {} } });
  _qwCtxTimer = _qwAdaptiveTimer = _qwCacheTimer = _qwL5Timer = _qwL5Interval = null;

  if (isHot) {
    // Session Pool、Capacity Matrix、AM、Auth等数据已由_snapshotState保存到_G
    if (am) { try { am.dispose(); } catch {} } am = null;
    if (auth) { try { auth.dispose(); } catch {} } auth = null;
    if (cloudPool) { try { cloudPool.dispose(); } catch {} } cloudPool = null;
    _panelProvider = null;
    return;
  }

  _deregisterWindow();
  _sessionPool.clear();
  _capacityMatrix.clear();
  _poolInitialized = false;
  if (_hubServer) { try { _hubServer.close(); } catch {} _hubServer = null; }
  if (_proxyProcess) { try { _proxyProcess.kill(); } catch {} _proxyProcess = null; }
  if (am) { try { am.dispose(); } catch {} }
  if (auth) { try { auth.dispose(); } catch {} }
  if (cloudPool) { try { cloudPool.dispose(); } catch {} cloudPool = null; }
  if (statusBar) { statusBar.dispose(); statusBar = null; }
  if (_outputChannel) { _outputChannel.dispose(); _outputChannel = null; }
  if (_panel) { try { _panel.dispose(); } catch {} _panel = null; }
  _panelProvider = null;
}

module.exports = { activate, deactivate };
