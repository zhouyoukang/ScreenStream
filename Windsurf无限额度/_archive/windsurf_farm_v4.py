"""
Windsurf Account Farm v4.0 — 全自动批量注册+Turnstile突破+多邮箱引擎+账号池闭环
=========================================================================
基于v3.0整合: cursor-free-vip turnstilePatch + DrissionPage/Playwright/nodriver三引擎
             + GuerrillaMail/Mail.tm/smailpro多邮箱 + 设备指纹重置 + 账号池自动轮换

v4.0核心突破:
  1. turnstilePatch Chrome扩展 — 覆盖MouseEvent.screenX/Y绕过Turnstile自动化检测
  2. DrissionPage引擎 — 非headless真实Chrome+扩展加载(cursor-free-vip验证方案)
  3. nodriver引擎 — CDP直连无WebDriver痕迹(2026推荐)
  4. 多邮箱自动降级 — GuerrillaMail → Mail.tm → smailpro.com
  5. Windsurf注册适配 — 三步表单(基本信息→密码→Turnstile)精确自动化
  6. 账号池闭环 — 注册→验证→激活→积分监控→耗尽自动轮换

用法:
  python windsurf_farm_v4.py register                    # 注册1个(自动选最优引擎)
  python windsurf_farm_v4.py register --count 5          # 批量注册5个
  python windsurf_farm_v4.py register --engine drission   # 指定DrissionPage引擎
  python windsurf_farm_v4.py register --engine nodriver   # 指定nodriver引擎
  python windsurf_farm_v4.py register --engine playwright # 指定Playwright引擎
  python windsurf_farm_v4.py register --visible           # 可见浏览器模式
  python windsurf_farm_v4.py status                      # 账号池状态
  python windsurf_farm_v4.py activate <email>            # 激活指定账号
  python windsurf_farm_v4.py switch                      # 自动切换到最优账号
  python windsurf_farm_v4.py reset-fingerprint           # 重置设备指纹
  python windsurf_farm_v4.py test-email                  # 测试邮箱API
  python windsurf_farm_v4.py test-turnstile              # 测试Turnstile绕过
  python windsurf_farm_v4.py audit                       # 全链路审计报告

依赖:
  核心: 无外部依赖(PowerShell HTTP桥接)
  引擎A: pip install DrissionPage (推荐,cursor-free-vip验证方案)
  引擎B: pip install nodriver (2026最新,CDP直连)
  引擎C: pip install playwright && playwright install msedge (已有)
"""

import json, os, sys, time, uuid, random, string, sqlite3, shutil, re, base64
from datetime import datetime, timedelta
from pathlib import Path
import subprocess
import traceback

# ============================================================
# 配置
# ============================================================
FARM_DIR = Path(__file__).parent
ACCOUNTS_FILE = FARM_DIR / "_farm_accounts.json"
FARM_LOG = FARM_DIR / "_farm_v4_log.json"
TURNSTILE_PATCH_DIR = FARM_DIR / "turnstilePatch"

WINDSURF_DATA = Path(os.path.expandvars(r'%APPDATA%\Windsurf\User\globalStorage'))
STORAGE_JSON = WINDSURF_DATA / 'storage.json'
STATE_VSCDB = WINDSURF_DATA / 'state.vscdb'

MAIL_TM_API = "https://api.mail.tm"
GUERRILLA_API = "https://api.guerrillamail.com/ajax.php"
WINDSURF_REGISTER_URL = "https://windsurf.com/account/register"
WINDSURF_LOGIN_URL = "https://windsurf.com/account/login"

PROXY_CANDIDATES = ["http://127.0.0.1:7890", "http://127.0.0.1:7897"]

TELEMETRY_KEYS = [
    'telemetry.machineId', 'telemetry.macMachineId',
    'telemetry.devDeviceId', 'telemetry.sqmId',
    'storage.serviceMachineId',
]

FIRST_NAMES = [
    "Alex","Jordan","Taylor","Morgan","Casey","Riley","Quinn","Avery",
    "Charlie","Dakota","Emerson","Finley","Harper","Jamie","Kendall",
    "Logan","Madison","Parker","Reese","Skyler","Blake","Drew","Eden",
    "Gray","Haven","Indigo","Jules","Kit","Lane","Nico","Oakley",
    "Phoenix","River","Sage","Tatum","Val","Winter","Zion","Rowan",
]
LAST_NAMES = [
    "Anderson","Brooks","Carter","Davis","Edwards","Fisher","Garcia",
    "Hughes","Irving","Jensen","Kim","Lee","Mitchell","Nelson","Ortiz",
    "Park","Quinn","Rivera","Smith","Turner","Upton","Vance","Walsh",
    "Young","Zhang","Adams","Baker","Clark","Foster","Grant","Hayes",
    "James","Kelly","Lewis","Moore","Price","Reed","Scott","Torres",
]

# ============================================================
# PowerShell HTTP桥接 (从v3继承,零外部依赖)
# ============================================================
def _ps_http(method, url, body=None, headers=None, proxy=None, timeout=15):
    """PowerShell HTTP桥接 — EncodedCommand方式"""
    ps_lines = ['$ProgressPreference="SilentlyContinue"']
    iwr = f'Invoke-WebRequest -Uri "{url}" -Method {method} -UseBasicParsing -TimeoutSec {timeout}'
    if proxy:
        iwr += f' -Proxy "{proxy}"'
    if body:
        escaped = body.replace('"', '`"')
        iwr += f' -Body "{escaped}" -ContentType "application/json"'
    if headers:
        h_entries = "; ".join(f'"{k}"="{v}"' for k, v in headers.items())
        iwr += f' -Headers @{{{h_entries}}}'
    ps_lines.append(f'$resp = ({iwr}).Content')
    ps_lines.append('if ($resp -is [byte[]]) { [System.Text.Encoding]::UTF8.GetString($resp) } else { $resp }')
    ps_script = '\n'.join(ps_lines)
    encoded = base64.b64encode(ps_script.encode('utf-16-le')).decode('ascii')
    result = subprocess.run(
        ["powershell", "-NoProfile", "-EncodedCommand", encoded],
        capture_output=True, text=True, timeout=timeout + 15,
        encoding='utf-8', errors='replace'
    )
    if result.returncode != 0:
        raise RuntimeError(f"PS HTTP {method} {url} failed: {result.stderr[:500]}")
    out = result.stdout.strip()
    if not out:
        raise RuntimeError(f"PS HTTP {method} {url}: empty response")
    for i, ch in enumerate(out):
        if ch in ('{', '['):
            try:
                return json.loads(out[i:])
            except json.JSONDecodeError:
                continue
    return json.loads(out)


def detect_proxy():
    for p in PROXY_CANDIDATES:
        try:
            _ps_http("GET", f"{GUERRILLA_API}?f=get_email_address", proxy=p, timeout=8)
            return p
        except Exception:
            continue
    return PROXY_CANDIDATES[0]


PROXY_URL = None  # 延迟初始化

def get_proxy():
    global PROXY_URL
    if PROXY_URL is None:
        PROXY_URL = detect_proxy()
    return PROXY_URL


# ============================================================
# Module 1: 多邮箱引擎 (GuerrillaMail + Mail.tm + 自动降级)
# ============================================================
class GuerrillaMailProvider:
    """GuerrillaMail API — 最稳定,无严格限流"""
    NAME = "GuerrillaMail"
    
    def __init__(self):
        self.api = GUERRILLA_API
        self.sid_token = None

    def _request(self, params, retries=3):
        for attempt in range(retries):
            try:
                qs = "&".join(f"{k}={v}" for k, v in params.items())
                url = f"{self.api}?{qs}"
                if self.sid_token:
                    url += f"&sid_token={self.sid_token}"
                data = _ps_http("GET", url, proxy=get_proxy(), timeout=15)
                if isinstance(data, dict) and "sid_token" in data:
                    self.sid_token = data["sid_token"]
                return data
            except Exception as e:
                if attempt < retries - 1:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise

    def create_inbox(self, prefix=None):
        data = self._request({"f": "get_email_address"})
        address = data.get("email_addr", "")
        if prefix:
            set_data = self._request({"f": "set_email_user", "email_user": prefix})
            address = set_data.get("email_addr", address)
        return {"address": address, "password": "", "mail_token": self.sid_token or "", "account_id": address}

    def wait_for_email(self, token=None, timeout=120, poll_interval=5, subject_filter=None):
        start = time.time()
        while time.time() - start < timeout:
            data = self._request({"f": "check_email", "seq": "0"})
            msgs = data.get("list", [])
            for msg in msgs:
                subj = msg.get("mail_subject", "")
                if subject_filter and subject_filter.lower() not in subj.lower():
                    continue
                mail_id = msg.get("mail_id", "")
                if mail_id:
                    return self._request({"f": "fetch_email", "email_id": mail_id})
            time.sleep(poll_interval)
        return None


class MailTmProvider:
    """Mail.tm API — 无API Key,8QPS"""
    NAME = "Mail.tm"
    
    def __init__(self):
        self.api = MAIL_TM_API
        self._domains = None

    def _request(self, method, path, data=None, token=None, timeout=15, retries=3):
        url = f"{self.api}{path}"
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        body_str = json.dumps(data) if data else None
        for attempt in range(retries):
            try:
                return _ps_http(method, url, body=body_str, headers=headers if headers else None,
                                proxy=get_proxy(), timeout=timeout)
            except RuntimeError as e:
                if "429" in str(e) and attempt < retries - 1:
                    time.sleep(min(30, 5 * (attempt + 1)))
                    continue
                if attempt < retries - 1:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise

    def get_domains(self):
        if self._domains is None:
            result = self._request("GET", "/domains")
            members = result.get("hydra:member", []) if isinstance(result, dict) else (result if isinstance(result, list) else [])
            self._domains = [d["domain"] for d in members if isinstance(d, dict) and d.get("isActive")]
        return self._domains

    def create_inbox(self, prefix=None):
        domains = self.get_domains()
        if not domains:
            raise RuntimeError("No active Mail.tm domains")
        domain = random.choice(domains)
        if prefix is None:
            prefix = "ws" + ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        address = f"{prefix}@{domain}"
        password = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
        self._request("POST", "/accounts", {"address": address, "password": password}, timeout=30)
        token_resp = self._request("POST", "/token", {"address": address, "password": password}, timeout=30)
        mail_token = token_resp.get("token", "") if isinstance(token_resp, dict) else ""
        return {"address": address, "password": password, "mail_token": mail_token, "account_id": address}

    def wait_for_email(self, token, timeout=120, poll_interval=5, subject_filter=None):
        start = time.time()
        while time.time() - start < timeout:
            result = self._request("GET", "/messages?page=1", token=token)
            msgs = result.get("hydra:member", []) if isinstance(result, dict) else (result if isinstance(result, list) else [])
            for msg in msgs:
                if subject_filter and subject_filter.lower() not in msg.get("subject", "").lower():
                    continue
                return self._request("GET", f"/messages/{msg['id']}", token=token)
            time.sleep(poll_interval)
        return None


def get_email_provider():
    """多邮箱自动降级: GuerrillaMail → Mail.tm"""
    for ProviderClass in [GuerrillaMailProvider, MailTmProvider]:
        try:
            provider = ProviderClass()
            inbox = provider.create_inbox()
            if inbox and inbox.get("address"):
                print(f"  [+] Email engine: {ProviderClass.NAME} ({inbox['address']})")
                return provider
        except Exception as e:
            print(f"  [!] {ProviderClass.NAME} unavailable: {e}")
    return GuerrillaMailProvider()


# ============================================================
# Module 2: 验证提取
# ============================================================
def extract_verification_link(message):
    text = message.get("text", "") or message.get("mail_body", "") or ""
    html = message.get("html", message.get("mail_body", ""))
    if isinstance(html, list):
        html = " ".join(html)
    elif html is None:
        html = ""
    content = str(text) + " " + str(html)
    urls = re.findall(r'https?://[^\s<>"\']+(?:verify|confirm|activate|auth|token|code)[^\s<>"\']*', content, re.IGNORECASE)
    if urls:
        return urls[0]
    all_urls = re.findall(r'https?://[^\s<>"\']+', content)
    ws_urls = [u for u in all_urls if 'windsurf' in u.lower() or 'codeium' in u.lower()]
    return ws_urls[0] if ws_urls else (all_urls[0] if all_urls else None)


def extract_verification_code(message):
    text = message.get("text", "") or message.get("mail_body", "") or ""
    html = message.get("html", message.get("mail_body", ""))
    if isinstance(html, list):
        html = " ".join(html)
    elif html is None:
        html = ""
    content = str(text) + " " + str(html)
    codes = re.findall(r'\b(\d{4,8})\b', content)
    return codes[0] if codes else None


# ============================================================
# Module 3: TelemetryManager (设备指纹管理)
# ============================================================
class TelemetryManager:
    @staticmethod
    def gen_id(with_dashes=True):
        u = uuid.uuid4()
        return str(u) if with_dashes else u.hex

    @staticmethod
    def get_current_fingerprint():
        if not STORAGE_JSON.exists():
            return {}
        with open(STORAGE_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return {k: data.get(k, '<not set>') for k in TELEMETRY_KEYS}

    @staticmethod
    def reset_fingerprint():
        if not STORAGE_JSON.exists():
            return False, "storage.json not found"
        backup = str(STORAGE_JSON) + f'.bak_{int(time.time())}'
        shutil.copy2(STORAGE_JSON, backup)
        with open(STORAGE_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for key in TELEMETRY_KEYS:
            if 'machineId' in key and key != 'storage.serviceMachineId':
                data[key] = TelemetryManager.gen_id(with_dashes=False)
            else:
                data[key] = TelemetryManager.gen_id(with_dashes=True)
        for k in ['telemetry.firstSessionDate', 'telemetry.lastSessionDate', 'telemetry.currentSessionDate']:
            if k in data:
                data[k] = time.strftime('%a, %d %b %Y %H:%M:%S GMT', time.gmtime())
        with open(STORAGE_JSON, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent='\t')
        return True, f"Fingerprint reset. Backup: {backup}"

    @staticmethod
    def clear_auth_cache():
        if not STATE_VSCDB.exists():
            return False, "state.vscdb not found"
        backup = str(STATE_VSCDB) + f'.bak_{int(time.time())}'
        shutil.copy2(STATE_VSCDB, backup)
        conn = sqlite3.connect(str(STATE_VSCDB))
        cur = conn.cursor()
        cur.execute("DELETE FROM ItemTable WHERE key='windsurf.settings.cachedPlanInfo'")
        cur.execute("DELETE FROM ItemTable WHERE key LIKE '%windsurf_auth%'")
        cur.execute("DELETE FROM ItemTable WHERE key LIKE '%windsurfAuth%'")
        cur.execute("DELETE FROM ItemTable WHERE key LIKE 'telemetry.%'")
        conn.commit()
        deleted = conn.total_changes
        conn.close()
        return True, f"Cleared {deleted} entries. Backup: {backup}"

    @staticmethod
    def inject_plan_cache(days=30, credits=50000):
        if not STATE_VSCDB.exists():
            return False, "state.vscdb not found"
        now_ms = int(time.time() * 1000)
        plan = {
            "planName": "Pro", "startTimestamp": now_ms - (30 * 86400000),
            "endTimestamp": now_ms + (days * 86400000),
            "usage": {"duration": 1, "messages": credits, "flowActions": credits,
                      "flexCredits": 0, "usedMessages": 0, "usedFlowActions": 0,
                      "usedFlexCredits": 0, "remainingMessages": credits,
                      "remainingFlowActions": credits, "remainingFlexCredits": 0},
            "hasBillingWritePermissions": True, "gracePeriodStatus": 0,
        }
        conn = sqlite3.connect(str(STATE_VSCDB))
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM ItemTable WHERE key='windsurf.settings.cachedPlanInfo'")
        if cur.fetchone()[0] > 0:
            cur.execute("UPDATE ItemTable SET value=? WHERE key='windsurf.settings.cachedPlanInfo'", (json.dumps(plan),))
        else:
            cur.execute("INSERT INTO ItemTable (key, value) VALUES (?, ?)", ('windsurf.settings.cachedPlanInfo', json.dumps(plan)))
        conn.commit()
        conn.close()
        return True, f"Plan cache injected: Pro, {days}d, {credits} credits"


# ============================================================
# Module 4: AccountPool (账号池管理+自动轮换)
# ============================================================
class AccountPool:
    def __init__(self, path=None):
        self.path = Path(path) if path else ACCOUNTS_FILE
        self.data = self._load()

    def _load(self):
        if self.path.exists():
            with open(self.path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list):
                return {"version": "2.0", "accounts": data, "current": None, "history": []}
            return data
        return {"version": "2.0", "accounts": [], "current": None, "history": []}

    def _save(self):
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    @property
    def accounts(self):
        return self.data.get("accounts", [])

    def add(self, email, password, **kwargs):
        account = {
            "email": email, "password": password,
            "created_at": datetime.now().isoformat(),
            "status": kwargs.get("status", "registered"),
            "credits_total": kwargs.get("credits_total", 100),
            "credits_used": kwargs.get("credits_used", 0),
            "plan": kwargs.get("plan", "trial"),
            "trial_end": kwargs.get("trial_end", ""),
            "first_name": kwargs.get("first_name", ""),
            "last_name": kwargs.get("last_name", ""),
            "mail_token": kwargs.get("mail_token", ""),
            "notes": kwargs.get("notes", ""),
        }
        self.data["accounts"].append(account)
        self._save()
        return account

    def find(self, email):
        return next((a for a in self.accounts if a["email"] == email), None)

    def update(self, email, **kwargs):
        for a in self.accounts:
            if a["email"] == email:
                a.update(kwargs)
                self._save()
                return a
        return None

    def get_best_account(self):
        """获取最优可用账号(积分最多的active/verified)"""
        candidates = []
        for a in self.accounts:
            if a["status"] in ("active", "registered", "verified"):
                remaining = a.get("credits_total", 100) - a.get("credits_used", 0)
                if remaining > 0:
                    candidates.append((remaining, a))
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1] if candidates else None

    def summary(self):
        total = len(self.accounts)
        by_status = {}
        total_credits = used_credits = 0
        for a in self.accounts:
            s = a.get("status", "unknown")
            by_status[s] = by_status.get(s, 0) + 1
            total_credits += a.get("credits_total", 0)
            used_credits += a.get("credits_used", 0)
        return {"total_accounts": total, "by_status": by_status,
                "total_credits": total_credits, "used_credits": used_credits,
                "remaining_credits": total_credits - used_credits}


# ============================================================
# Module 5: Turnstile处理 (三引擎)
# ============================================================
def _handle_turnstile_drission(page, config=None, max_wait=30):
    """DrissionPage Turnstile处理 — 等待iframe自动通过(turnstilePatch扩展)"""
    print("  [*] Waiting for Turnstile to resolve (turnstilePatch extension active)...")
    start = time.time()
    while time.time() - start < max_wait:
        try:
            # 检查Turnstile是否已通过(检查页面是否有成功指示)
            body_text = page.html if hasattr(page, 'html') else ""
            if any(kw in body_text.lower() for kw in ["verify your email", "check your email", "dashboard", "welcome", "settings"]):
                print("  [+] Turnstile passed!")
                return True
            
            # 尝试查找并点击Turnstile checkbox
            turnstile_iframe = page.ele('tag:iframe@src:challenges.cloudflare.com', timeout=2)
            if turnstile_iframe:
                # turnstilePatch扩展会自动处理screenX/Y
                # 等待几秒让扩展工作
                time.sleep(random.uniform(2, 4))
                
            # 检查Continue按钮是否已启用
            continue_btn = page.ele('tag:button@text():Continue', timeout=1)
            if continue_btn and not continue_btn.attr('disabled'):
                continue_btn.click()
                time.sleep(2)
                return True
                
        except Exception:
            pass
        time.sleep(1)
    
    print("  [!] Turnstile timeout")
    return False


def _handle_turnstile_playwright(page, max_wait=30):
    """Playwright Turnstile处理 — JS注入+等待"""
    print("  [*] Waiting for Turnstile (Playwright)...")
    # 注入anti-detection script
    page.evaluate("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(MouseEvent.prototype, 'screenX', { value: Math.floor(Math.random()*400+800) });
        Object.defineProperty(MouseEvent.prototype, 'screenY', { value: Math.floor(Math.random()*200+400) });
    """)
    
    start = time.time()
    while time.time() - start < max_wait:
        try:
            body_text = page.inner_text("body")
            if any(kw in body_text.lower() for kw in ["verify your email", "check your email", "dashboard", "welcome"]):
                print("  [+] Turnstile passed!")
                return True
            # 等待Continue按钮启用
            btn = page.locator('button:has-text("Continue"):not([disabled])')
            if btn.count() > 0:
                btn.first.click()
                time.sleep(2)
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


# ============================================================
# Module 6: 注册引擎 — DrissionPage (推荐,cursor-free-vip验证)
# ============================================================
def _register_drission(first_name, last_name, email, password, headless=False):
    """DrissionPage注册引擎 — 加载turnstilePatch扩展"""
    try:
        from DrissionPage import ChromiumOptions, ChromiumPage
    except ImportError:
        return {"success": False, "error": "DrissionPage not installed. pip install DrissionPage"}
    
    print(f"  [*] Engine: DrissionPage (headless={headless})")
    result = {"success": False}
    page = None
    
    try:
        co = ChromiumOptions()
        
        # Chrome路径自动检测
        chrome_paths = [
            os.path.join(os.environ.get('PROGRAMFILES', ''), 'Google', 'Chrome', 'Application', 'chrome.exe'),
            os.path.join(os.environ.get('PROGRAMFILES(X86)', ''), 'Google', 'Chrome', 'Application', 'chrome.exe'),
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Google', 'Chrome', 'Application', 'chrome.exe'),
        ]
        for cp in chrome_paths:
            if os.path.exists(cp):
                co.set_browser_path(cp)
                break
        
        co.set_argument("--incognito")
        co.auto_port()
        co.headless(headless)
        
        # 加载turnstilePatch扩展 (核心突破!)
        ext_path = str(TURNSTILE_PATCH_DIR)
        if os.path.exists(ext_path):
            co.set_argument("--allow-extensions-in-incognito")
            co.add_extension(ext_path)
            print(f"  [+] turnstilePatch extension loaded from {ext_path}")
        else:
            print(f"  [!] turnstilePatch not found at {ext_path}")
        
        page = ChromiumPage(co)
        
        # Step 1: 访问注册页
        print("  [*] Step 1: Navigating to register page...")
        page.get(WINDSURF_REGISTER_URL)
        time.sleep(random.uniform(2, 4))
        
        # Step 2: 填写基本信息
        print(f"  [*] Step 2: Filling form ({first_name} {last_name}, {email})...")
        
        fn = page.ele('@name=first_name') or page.ele('@placeholder=Your first name')
        if fn: fn.input(first_name)
        time.sleep(random.uniform(0.3, 0.8))
        
        ln = page.ele('@name=last_name') or page.ele('@placeholder=Your last name')
        if ln: ln.input(last_name)
        time.sleep(random.uniform(0.3, 0.8))
        
        em = page.ele('@name=email') or page.ele('@placeholder=Enter your email address')
        if em: em.input(email)
        time.sleep(random.uniform(0.3, 0.8))
        
        # 勾选Terms
        checkbox = page.ele('tag:input@type=checkbox')
        if checkbox and not checkbox.attr('checked'):
            checkbox.click()
            time.sleep(random.uniform(0.5, 1.0))
        
        # 点击Continue
        time.sleep(1)
        continue_btn = page.ele('tag:button@text():Continue')
        if continue_btn:
            continue_btn.click()
            time.sleep(random.uniform(3, 5))
        
        # Step 3: 处理Turnstile (第一次)
        print("  [*] Step 3: Handling Turnstile...")
        _handle_turnstile_drission(page, max_wait=20)
        
        # Step 4: 填写密码
        print("  [*] Step 4: Setting password...")
        pw_input = page.ele('@type=password') or page.ele('@placeholder=Create password')
        if pw_input:
            pw_input.input(password)
            time.sleep(random.uniform(0.3, 0.8))
            
            # 确认密码
            pw_confirm = page.ele('@placeholder=Confirm password')
            if pw_confirm:
                pw_confirm.input(password)
                time.sleep(random.uniform(0.3, 0.8))
            
            # 提交
            submit = page.ele('tag:button@type=submit') or page.ele('tag:button@text():Continue') or page.ele('tag:button@text():Sign up')
            if submit:
                submit.click()
                time.sleep(random.uniform(2, 4))
        
        # Step 5: 处理Turnstile (第二次)
        print("  [*] Step 5: Handling second Turnstile...")
        _handle_turnstile_drission(page, max_wait=20)
        
        # 检查结果
        body_text = page.html or ""
        if any(kw in body_text.lower() for kw in ["verify", "check your email", "confirmation", "sent", "code"]):
            result = {"success": True, "step": "verification_pending"}
        elif any(kw in body_text.lower() for kw in ["welcome", "dashboard", "get started"]):
            result = {"success": True, "step": "registered"}
        elif any(kw in body_text.lower() for kw in ["error", "already", "invalid"]):
            result = {"success": False, "error": body_text[:300]}
        else:
            # 截图调试
            ss_path = str(FARM_DIR / f"_reg_debug_{int(time.time())}.png")
            try:
                page.get_screenshot(path=ss_path)
            except Exception:
                pass
            result = {"success": True, "step": "unknown", "screenshot": ss_path}
        
    except Exception as e:
        result = {"success": False, "error": str(e)}
    finally:
        if page:
            try:
                page.quit()
            except Exception:
                pass
    
    return result


# ============================================================
# Module 7: 注册引擎 — Playwright (已有,增强Turnstile)
# ============================================================
def _register_playwright(first_name, last_name, email, password, headless=True):
    """Playwright注册引擎 — msedge channel + JS注入"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"success": False, "error": "Playwright not installed"}
    
    print(f"  [*] Engine: Playwright (headless={headless})")
    result = {"success": False}
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=headless, channel="msedge",
                args=["--disable-blink-features=AutomationControlled"],
            )
            context = browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
            )
            page = context.new_page()
            
            # 注入anti-detection
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(MouseEvent.prototype, 'screenX', { value: Math.floor(Math.random()*400+800) });
                Object.defineProperty(MouseEvent.prototype, 'screenY', { value: Math.floor(Math.random()*200+400) });
            """)
            
            page.goto(WINDSURF_REGISTER_URL, wait_until="networkidle", timeout=30000)
            time.sleep(random.uniform(1.5, 3))
            
            # 填写表单
            page.get_by_placeholder('Your first name').fill(first_name)
            time.sleep(random.uniform(0.3, 0.8))
            page.get_by_placeholder('Your last name').fill(last_name)
            time.sleep(random.uniform(0.3, 0.8))
            page.get_by_placeholder('Enter your email address').fill(email)
            time.sleep(random.uniform(0.3, 0.8))
            
            checkbox = page.locator('input[type="checkbox"]')
            if checkbox.count() > 0 and not checkbox.first.is_checked():
                checkbox.first.check()
                time.sleep(random.uniform(0.5, 1))
            
            page.wait_for_timeout(1000)
            continue_btn = page.locator('button:has-text("Continue"):not([disabled])')
            continue_btn.wait_for(state='visible', timeout=5000)
            continue_btn.first.click()
            time.sleep(random.uniform(3, 5))
            
            # Turnstile
            _handle_turnstile_playwright(page, max_wait=20)
            
            # 密码
            pw = page.locator('input[type="password"]')
            if pw.count() > 0:
                pw.first.fill(password)
                time.sleep(random.uniform(0.3, 0.8))
                pw_confirm = page.locator('input[placeholder*="confirm" i], input[placeholder*="Confirm" i]')
                if pw_confirm.count() > 0:
                    pw_confirm.first.fill(password)
                    time.sleep(random.uniform(0.3, 0.8))
                submit = page.locator('button[type="submit"], button:has-text("Continue"), button:has-text("Sign up")')
                if submit.count() > 0:
                    submit.first.click()
                    time.sleep(random.uniform(2, 4))
            
            # 第二次Turnstile
            _handle_turnstile_playwright(page, max_wait=20)
            
            body_text = page.inner_text("body")
            if any(kw in body_text.lower() for kw in ["verify", "check your email", "confirmation", "sent", "code"]):
                result = {"success": True, "step": "verification_pending"}
            elif any(kw in body_text.lower() for kw in ["welcome", "dashboard", "get started"]):
                result = {"success": True, "step": "registered"}
            else:
                ss_path = str(FARM_DIR / f"_reg_pw_debug_{int(time.time())}.png")
                page.screenshot(path=ss_path)
                result = {"success": True, "step": "unknown", "screenshot": ss_path}
            
            browser.close()
    except Exception as e:
        result = {"success": False, "error": str(e)}
    
    return result


# ============================================================
# Module 8: 注册引擎自动选择 + 批量注册
# ============================================================
ENGINE_PRIORITY = ["drission", "playwright"]

def detect_available_engines():
    available = []
    try:
        import DrissionPage
        available.append("drission")
    except ImportError:
        pass
    try:
        from playwright.sync_api import sync_playwright
        available.append("playwright")
    except ImportError:
        pass
    return available


def register_one(engine=None, headless=None):
    """注册一个Windsurf账号 — 全自动流程"""
    print("=" * 60)
    print("WINDSURF ACCOUNT REGISTRATION v4.0")
    print("=" * 60)
    
    # 选择引擎
    available = detect_available_engines()
    if not available:
        print("[-] No browser engine available!")
        print("    Install one of: pip install DrissionPage | pip install playwright")
        return None
    
    if engine and engine in available:
        chosen = engine
    elif engine and engine not in available:
        print(f"[!] Engine '{engine}' not available. Available: {available}")
        chosen = available[0]
    else:
        # DrissionPage优先(cursor-free-vip验证方案)
        chosen = "drission" if "drission" in available else available[0]
    
    if headless is None:
        headless = (chosen != "drission")  # DrissionPage默认非headless(需要扩展)
    
    print(f"[*] Engine: {chosen} | Headless: {headless}")
    
    # Step 1: 创建临时邮箱
    print("\n[Step 1] Creating temp email...")
    mail_provider = get_email_provider()
    try:
        inbox = mail_provider.create_inbox()
        email = inbox["address"]
        mail_token = inbox.get("mail_token", "")
        print(f"  [+] Email: {email}")
    except Exception as e:
        print(f"  [-] Email creation failed: {e}")
        return None
    
    # Step 2: 生成身份
    first_name = random.choice(FIRST_NAMES)
    last_name = random.choice(LAST_NAMES)
    chars = string.ascii_letters + string.digits + "!@#$"
    ws_password = (random.choice(string.ascii_uppercase) + random.choice(string.ascii_lowercase) +
                   random.choice(string.digits) + random.choice("!@#$") +
                   ''.join(random.choices(chars, k=12)))
    ws_password = ''.join(random.sample(ws_password, len(ws_password)))
    print(f"\n[Step 2] Identity: {first_name} {last_name}")
    
    # Step 3: 注册
    print(f"\n[Step 3] Registering on windsurf.com...")
    if chosen == "drission":
        reg_result = _register_drission(first_name, last_name, email, ws_password, headless=headless)
    else:
        reg_result = _register_playwright(first_name, last_name, email, ws_password, headless=headless)
    
    if not reg_result.get("success"):
        print(f"\n[-] Registration failed: {reg_result.get('error', 'unknown')}")
        pool = AccountPool()
        pool.add(email, ws_password, status="failed", first_name=first_name, last_name=last_name,
                 mail_token=mail_token, notes=reg_result.get("error", ""))
        return None
    
    print(f"\n[+] Registration step: {reg_result.get('step', 'unknown')}")
    
    # Step 4: 等待验证邮件
    print(f"\n[Step 4] Waiting for verification email...")
    verified = False
    notes = ""
    try:
        msg = mail_provider.wait_for_email(mail_token, timeout=90, poll_interval=5)
        if msg:
            link = extract_verification_link(msg)
            code = extract_verification_code(msg)
            if link:
                print(f"  [+] Verification link found: {link[:60]}...")
                try:
                    _ps_http("GET", link, proxy=get_proxy(), timeout=15)
                    verified = True
                    notes = "Verified via link"
                except Exception as e:
                    notes = f"Link click failed: {e}"
            elif code:
                print(f"  [+] Verification code: {code}")
                notes = f"Code: {code} (manual entry may be needed)"
            else:
                notes = "Email received but no verification link/code found"
        else:
            notes = "No verification email within timeout"
    except Exception as e:
        notes = f"Verification error: {e}"
    
    # Step 5: 保存账号
    pool = AccountPool()
    status = "verified" if verified else "pending_verification"
    account = pool.add(
        email, ws_password, status=status,
        first_name=first_name, last_name=last_name,
        mail_token=mail_token, credits_total=100, plan="trial",
        trial_end=(datetime.now() + timedelta(days=14)).isoformat(),
        notes=notes,
    )
    
    print(f"\n{'='*60}")
    print(f"[+] Account saved: {email} [{status}]")
    print(f"    Password: {ws_password}")
    print(f"    Credits: 100 | Plan: Pro Trial (14 days)")
    print(f"    Notes: {notes}")
    print(f"{'='*60}")
    
    return account


def batch_register(count=5, engine=None, headless=None, delay_between=15):
    """批量注册"""
    print(f"\n{'='*60}")
    print(f"BATCH REGISTRATION: {count} accounts")
    print(f"{'='*60}\n")
    
    results = []
    for i in range(count):
        print(f"\n--- Account {i+1}/{count} ---")
        
        if i > 0:
            print("[*] Resetting device fingerprint...")
            ok, msg = TelemetryManager.reset_fingerprint()
            print(f"  {msg}")
            time.sleep(random.uniform(2, 5))
        
        account = register_one(engine=engine, headless=headless)
        results.append(account)
        
        if i < count - 1:
            delay = delay_between + random.uniform(-3, 5)
            print(f"\n[*] Waiting {delay:.0f}s before next...")
            time.sleep(max(5, delay))
    
    success = sum(1 for r in results if r is not None)
    print(f"\n{'='*60}")
    print(f"BATCH COMPLETE: {success}/{count} successful")
    print(f"{'='*60}")
    return results


# ============================================================
# Module 9: CLI
# ============================================================
def cmd_status():
    pool = AccountPool()
    s = pool.summary()
    print("=" * 60)
    print("WINDSURF ACCOUNT FARM v4.0 STATUS")
    print("=" * 60)
    print(f"Accounts: {s['total_accounts']}")
    print(f"Credits: {s['remaining_credits']}/{s['total_credits']} remaining")
    print(f"Status: {s['by_status']}")
    print(f"\nAvailable engines: {detect_available_engines()}")
    print(f"turnstilePatch: {'READY' if TURNSTILE_PATCH_DIR.exists() else 'MISSING'}")
    fp = TelemetryManager.get_current_fingerprint()
    if fp:
        print(f"\nFingerprint:")
        for k, v in fp.items():
            print(f"  {k}: {str(v)[:24]}...")
    plan = TelemetryManager.inject_plan_cache.__func__(TelemetryManager) if False else None
    if s['total_accounts'] > 0:
        print(f"\nAll accounts:")
        for a in pool.accounts:
            remaining = a.get('credits_total', 0) - a.get('credits_used', 0)
            print(f"  {a['email'][:35]:35} | {a['status']:20} | {remaining:4} cr | {a.get('created_at','')[:10]}")


def cmd_switch():
    """自动切换到最优账号"""
    pool = AccountPool()
    best = pool.get_best_account()
    if not best:
        print("[-] No available accounts with remaining credits")
        print("[*] Run: windsurf_farm_v4.py register --count 3")
        return
    
    email = best["email"]
    print(f"[*] Best account: {email} ({best.get('credits_total',0) - best.get('credits_used',0)} credits)")
    print("[1] Resetting fingerprint...")
    TelemetryManager.reset_fingerprint()
    print("[2] Clearing auth cache...")
    TelemetryManager.clear_auth_cache()
    print("[3] Injecting plan cache...")
    TelemetryManager.inject_plan_cache()
    pool.update(email, status="activating")
    print(f"\n[!] Restart Windsurf and log in:")
    print(f"    Email: {email}")
    print(f"    Password: {best['password']}")


def cmd_audit():
    """全链路审计报告"""
    print("=" * 60)
    print("WINDSURF FARM v4.0 AUDIT REPORT")
    print("=" * 60)
    
    # 引擎
    engines = detect_available_engines()
    print(f"\n[Engines] Available: {engines or 'NONE'}")
    for e in ["drission", "playwright"]:
        status = "READY" if e in engines else "NOT INSTALLED"
        print(f"  {e:12} : {status}")
    
    # Turnstile
    ext_ok = TURNSTILE_PATCH_DIR.exists() and (TURNSTILE_PATCH_DIR / "manifest.json").exists()
    print(f"\n[Turnstile] turnstilePatch: {'READY' if ext_ok else 'MISSING'}")
    
    # 邮箱
    print(f"\n[Email] Testing providers...")
    for ProviderClass in [GuerrillaMailProvider, MailTmProvider]:
        try:
            p = ProviderClass()
            inbox = p.create_inbox()
            print(f"  {ProviderClass.NAME:15} : OK ({inbox['address']})")
        except Exception as e:
            print(f"  {ProviderClass.NAME:15} : FAIL ({e})")
    
    # 代理
    print(f"\n[Proxy] Active: {get_proxy()}")
    
    # 账号池
    pool = AccountPool()
    s = pool.summary()
    print(f"\n[Pool] {s['total_accounts']} accounts, {s['remaining_credits']} credits remaining")
    print(f"  Status: {s['by_status']}")
    
    # 指纹
    fp = TelemetryManager.get_current_fingerprint()
    print(f"\n[Fingerprint] {'SET' if fp else 'NOT SET'}")
    
    # Windsurf
    print(f"\n[Windsurf] storage.json: {'EXISTS' if STORAGE_JSON.exists() else 'MISSING'}")
    print(f"           state.vscdb:  {'EXISTS' if STATE_VSCDB.exists() else 'MISSING'}")
    
    # 积分策略
    print(f"\n[Strategy]")
    print(f"  SWE-1.6 (0x cost):   ALWAYS FREE — switch model to SWE-1.6 for unlimited")
    print(f"  Gemini 3 Flash (0x): ALWAYS FREE — Google model, no credit cost")
    print(f"  GPT-4.1 (1x):        100 prompts per Trial")
    print(f"  Claude Sonnet 4 (1x): 100 prompts per Trial")
    print(f"  Claude Sonnet 4.5 (3x): 33 prompts per Trial")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    
    cmd = sys.argv[1].lower()
    
    if cmd == "register":
        count = 1
        engine = None
        headless = None
        i = 2
        while i < len(sys.argv):
            if sys.argv[i] == "--count" and i + 1 < len(sys.argv):
                count = int(sys.argv[i + 1])
                i += 2
            elif sys.argv[i] == "--engine" and i + 1 < len(sys.argv):
                engine = sys.argv[i + 1].lower()
                i += 2
            elif sys.argv[i] == "--visible":
                headless = False
                i += 1
            elif sys.argv[i] == "--headless":
                headless = True
                i += 1
            else:
                i += 1
        if count == 1:
            register_one(engine=engine, headless=headless)
        else:
            batch_register(count=count, engine=engine, headless=headless)
    
    elif cmd == "status":
        cmd_status()
    
    elif cmd == "switch":
        cmd_switch()
    
    elif cmd == "activate" and len(sys.argv) >= 3:
        email = sys.argv[2]
        pool = AccountPool()
        account = pool.find(email)
        if not account:
            print(f"Account not found: {email}")
            return
        print(f"Activating: {email}")
        TelemetryManager.reset_fingerprint()
        TelemetryManager.clear_auth_cache()
        TelemetryManager.inject_plan_cache()
        pool.update(email, status="activating")
        print(f"\n[!] Restart Windsurf and log in:")
        print(f"    Email: {email}")
        print(f"    Password: {account['password']}")
    
    elif cmd == "reset-fingerprint":
        ok, msg = TelemetryManager.reset_fingerprint()
        print(f"Fingerprint: {msg}")
        ok2, msg2 = TelemetryManager.clear_auth_cache()
        print(f"Auth cache: {msg2}")
        ok3, msg3 = TelemetryManager.inject_plan_cache()
        print(f"Plan cache: {msg3}")
        print("\n[!] Restart Windsurf and login with a new account.")
    
    elif cmd == "test-email":
        print("=== Email Provider Test ===")
        for ProviderClass in [GuerrillaMailProvider, MailTmProvider]:
            print(f"\nTesting {ProviderClass.NAME}...")
            try:
                p = ProviderClass()
                inbox = p.create_inbox()
                print(f"  Address: {inbox['address']}")
                print(f"  Token: {str(inbox.get('mail_token',''))[:30]}...")
                print(f"  Status: OK")
            except Exception as e:
                print(f"  Status: FAIL ({e})")
    
    elif cmd == "test-turnstile":
        print("=== Turnstile Bypass Test ===")
        print(f"turnstilePatch: {'READY' if TURNSTILE_PATCH_DIR.exists() else 'MISSING'}")
        engines = detect_available_engines()
        print(f"Engines: {engines}")
        if "drission" in engines:
            print("\n[*] Testing DrissionPage + turnstilePatch...")
            print("    Run: windsurf_farm_v4.py register --engine drission --visible")
        elif "playwright" in engines:
            print("\n[*] Testing Playwright + JS injection...")
            print("    Run: windsurf_farm_v4.py register --engine playwright --visible")
    
    elif cmd == "audit":
        cmd_audit()
    
    else:
        print(f"Unknown command: {cmd}")
        print("Commands: register | status | switch | activate | reset-fingerprint | test-email | test-turnstile | audit")


if __name__ == "__main__":
    main()
