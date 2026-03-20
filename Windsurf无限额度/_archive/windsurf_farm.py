"""
Windsurf Account Farm v3.0 — 全自动批量注册+管理管线
=====================================================
整合: GuerrillaMail/Mail.tm多引擎 + Playwright注册自动化 + 设备指纹重置 + 账号池管理

架构:
  道生一(Mail.tm API) → 一生二(+Playwright注册) → 二生三(+指纹管理) → 三生万物(账号池)

用法:
  python windsurf_farm.py register          # 注册1个新账号
  python windsurf_farm.py register --count 5  # 批量注册5个
  python windsurf_farm.py status            # 查看账号池状态
  python windsurf_farm.py activate <email>  # 激活指定账号到本地Windsurf
  python windsurf_farm.py check             # 检查所有账号积分余额
  python windsurf_farm.py reset-fingerprint # 重置设备指纹
  python windsurf_farm.py test-email        # 测试Mail.tm API

依赖: 无外部依赖(使用PowerShell HTTP桥接解决Python SSL兼容性)
可选: playwright (pip install playwright && playwright install msedge)

基于已有资源:
  - telemetry_reset.py (设备指纹重置)
  - cache_refresh.py (本地缓存操控)
  - ai-auto-free (GitHub 456★, 注册流程参考)
  - token_processor.py (gRPC protobuf通信参考)
"""

import json, os, sys, time, uuid, random, string, sqlite3, shutil, re
from datetime import datetime, timedelta
from pathlib import Path

import subprocess

def _ps_http(method, url, body=None, headers=None, proxy=None, timeout=15):
    """PowerShell HTTP桥接 — EncodedCommand方式，彻底解决引号/编码问题"""
    import base64
    
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
    
    # .Content可能返回byte[]或string，用try/catch兼容
    ps_lines.append(f'$resp = ({iwr}).Content')
    ps_lines.append('if ($resp -is [byte[]]) { [System.Text.Encoding]::UTF8.GetString($resp) } else { $resp }')
    ps_script = '\n'.join(ps_lines)
    
    # 用EncodedCommand: UTF-16LE编码→Base64，PowerShell原生支持
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
    
    # 找到JSON起始位置(跳过PS警告行)
    for i, ch in enumerate(out):
        if ch in ('{', '['):
            try:
                return json.loads(out[i:])
            except json.JSONDecodeError:
                continue
    return json.loads(out)

# ============================================================
# 配置
# ============================================================
FARM_DIR = Path(__file__).parent
ACCOUNTS_FILE = FARM_DIR / "_farm_accounts.json"
FARM_LOG = FARM_DIR / "_farm_log.json"

WINDSURF_DATA = Path(os.path.expandvars(r'%APPDATA%\Windsurf\User\globalStorage'))
STORAGE_JSON = WINDSURF_DATA / 'storage.json'
STATE_VSCDB = WINDSURF_DATA / 'state.vscdb'

MAIL_TM_API = "https://api.mail.tm"
GUERRILLA_API = "https://api.guerrillamail.com/ajax.php"
WINDSURF_REGISTER_URL = "https://windsurf.com/account/register"
WINDSURF_LOGIN_URL = "https://windsurf.com/account/login"
EMAIL_PROVIDER = os.environ.get("WS_FARM_EMAIL", "auto")  # "auto" / "guerrilla" / "mailtm"

# 代理配置 (mail.tm/guerrillamail在中国需代理)
PROXY_CANDIDATES = ["http://127.0.0.1:7890", "http://127.0.0.1:7897"]

def detect_proxy():
    """自动探测可用代理 — PowerShell方式"""
    for p in PROXY_CANDIDATES:
        try:
            _ps_http("GET", f"{GUERRILLA_API}?f=get_email_address", proxy=p, timeout=8)
            return p
        except Exception:
            continue
    return PROXY_CANDIDATES[0]  # fallback

PROXY_URL = detect_proxy()

TELEMETRY_KEYS = [
    'telemetry.machineId',
    'telemetry.macMachineId',
    'telemetry.devDeviceId',
    'telemetry.sqmId',
    'storage.serviceMachineId',
]

# 随机名字池 (避免明显假名)
FIRST_NAMES = [
    "Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Quinn", "Avery",
    "Charlie", "Dakota", "Emerson", "Finley", "Harper", "Jamie", "Kendall",
    "Logan", "Madison", "Parker", "Reese", "Skyler", "Blake", "Drew", "Eden",
    "Gray", "Haven", "Indigo", "Jules", "Kit", "Lane", "Nico", "Oakley",
    "Phoenix", "River", "Sage", "Tatum", "Val", "Winter", "Zion", "Rowan",
]
LAST_NAMES = [
    "Anderson", "Brooks", "Carter", "Davis", "Edwards", "Fisher", "Garcia",
    "Hughes", "Irving", "Jensen", "Kim", "Lee", "Mitchell", "Nelson", "Ortiz",
    "Park", "Quinn", "Rivera", "Smith", "Turner", "Upton", "Vance", "Walsh",
    "Young", "Zhang", "Adams", "Baker", "Clark", "Foster", "Grant", "Hayes",
    "James", "Kelly", "Lewis", "Moore", "Price", "Reed", "Scott", "Torres",
]


# ============================================================
# Module 1: TempMailProvider (Mail.tm API)
# ============================================================
class TempMailProvider:
    """Mail.tm免费临时邮箱API封装 — 无需API Key, 8 QPS限制"""

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
                                proxy=PROXY_URL, timeout=timeout)
            except RuntimeError as e:
                err = str(e)
                if "429" in err:
                    wait = min(30, 5 * (attempt + 1))
                    if attempt < retries - 1:
                        time.sleep(wait)
                        continue
                    raise
                if attempt < retries - 1:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise

    def get_domains(self):
        if self._domains is None:
            result = self._request("GET", "/domains")
            # Handle both hydra:Collection format and plain list format
            if isinstance(result, dict):
                members = result.get("hydra:member", [])
            elif isinstance(result, list):
                members = result
            else:
                members = []
            self._domains = [d["domain"] for d in members if isinstance(d, dict) and d.get("isActive")]
        return self._domains

    def create_inbox(self, prefix=None):
        domains = self.get_domains()
        if not domains:
            raise RuntimeError("No active Mail.tm domains available")
        domain = random.choice(domains)
        if prefix is None:
            prefix = "ws" + ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        address = f"{prefix}@{domain}"
        password = ''.join(random.choices(string.ascii_letters + string.digits, k=16))

        account = self._request("POST", "/accounts", {"address": address, "password": password}, timeout=30)
        acct_id = account.get("id", "") if isinstance(account, dict) else str(account)

        token_resp = self._request("POST", "/token", {"address": address, "password": password}, timeout=30)
        mail_token = token_resp.get("token", "") if isinstance(token_resp, dict) else str(token_resp)

        return {
            "address": address,
            "password": password,
            "mail_token": mail_token,
            "account_id": acct_id,
        }

    def _hydra_members(self, result):
        """Extract members from hydra:Collection or plain list"""
        if isinstance(result, dict):
            return result.get("hydra:member", [])
        elif isinstance(result, list):
            return result
        return []

    def get_messages(self, token, page=1):
        result = self._request("GET", f"/messages?page={page}", token=token)
        return self._hydra_members(result)

    def get_message(self, token, message_id):
        return self._request("GET", f"/messages/{message_id}", token=token)

    def wait_for_email(self, token, timeout=120, poll_interval=5, subject_filter=None):
        start = time.time()
        while time.time() - start < timeout:
            messages = self.get_messages(token)
            for msg in messages:
                if subject_filter and subject_filter.lower() not in msg.get("subject", "").lower():
                    continue
                full = self.get_message(token, msg["id"])
                return full
            time.sleep(poll_interval)
        return None


# ============================================================
# Module 1b: GuerrillaMailProvider (备选邮箱，无限流限制)
# ============================================================
class GuerrillaMailProvider:
    """Guerrilla Mail API — 无需创建账号,无严格限流,更适合批量"""

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
                data = _ps_http("GET", url, proxy=PROXY_URL, timeout=15)
                if isinstance(data, dict) and "sid_token" in data:
                    self.sid_token = data["sid_token"]
                return data
            except Exception as e:
                if attempt < retries - 1:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise RuntimeError(f"GuerrillaMail error after {retries} retries: {e}")

    def create_inbox(self, prefix=None):
        data = self._request({"f": "get_email_address"})
        address = data.get("email_addr", "")
        if prefix:
            set_data = self._request({"f": "set_email_user", "email_user": prefix})
            address = set_data.get("email_addr", address)
        return {
            "address": address,
            "password": "",
            "mail_token": self.sid_token or "",
            "account_id": data.get("email_addr", ""),
        }

    def get_messages(self, token=None):
        data = self._request({"f": "check_email", "seq": "0"})
        return data.get("list", [])

    def wait_for_email(self, token=None, timeout=120, poll_interval=5, subject_filter=None):
        start = time.time()
        while time.time() - start < timeout:
            msgs = self.get_messages()
            for msg in msgs:
                subj = msg.get("mail_subject", "")
                if subject_filter and subject_filter.lower() not in subj.lower():
                    continue
                mail_id = msg.get("mail_id", "")
                if mail_id:
                    full = self._request({"f": "fetch_email", "email_id": mail_id})
                    return full
            time.sleep(poll_interval)
        return None


def _extract_verification_link(message):
    """通用验证链接提取 — 兼容Mail.tm和GuerrillaMail格式"""
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
    windsurf_urls = [u for u in all_urls if 'windsurf' in u.lower() or 'codeium' in u.lower()]
    return windsurf_urls[0] if windsurf_urls else (all_urls[0] if all_urls else None)


def _extract_verification_code(message):
    """通用验证码提取"""
    text = message.get("text", "") or message.get("mail_body", "") or ""
    html = message.get("html", message.get("mail_body", ""))
    if isinstance(html, list):
        html = " ".join(html)
    elif html is None:
        html = ""
    content = str(text) + " " + str(html)
    codes = re.findall(r'\b(\d{4,8})\b', content)
    return codes[0] if codes else None


def get_email_provider():
    """根据配置选择邮箱提供商 — auto模式自动探测最佳可用"""
    if EMAIL_PROVIDER == "mailtm":
        return TempMailProvider(), "Mail.tm"
    elif EMAIL_PROVIDER == "guerrilla":
        return GuerrillaMailProvider(), "GuerrillaMail"
    else:
        # Auto mode: try GuerrillaMail first (most reliable), then Mail.tm
        for ProviderClass, name in [(GuerrillaMailProvider, "GuerrillaMail"), (TempMailProvider, "Mail.tm")]:
            try:
                provider = ProviderClass()
                inbox = provider.create_inbox()
                if inbox and inbox.get("address"):
                    print(f"[*] Auto-selected email provider: {name} ({inbox['address']})")
                    return provider, name
            except Exception as e:
                print(f"[!] {name} unavailable: {e}")
                continue
        # Fallback to GuerrillaMail
        return GuerrillaMailProvider(), "GuerrillaMail"


# ============================================================
# Module 2: TelemetryManager (设备指纹管理)
# ============================================================
class TelemetryManager:
    """设备指纹重置+本地缓存管理 — 基于telemetry_reset.py"""

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

        old_ids = {}
        for key in TELEMETRY_KEYS:
            old_ids[key] = data.get(key, '')
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
    def get_current_plan():
        if not STATE_VSCDB.exists():
            return None
        try:
            conn = sqlite3.connect(str(STATE_VSCDB))
            cur = conn.cursor()
            cur.execute("SELECT value FROM ItemTable WHERE key='windsurf.settings.cachedPlanInfo'")
            row = cur.fetchone()
            conn.close()
            return json.loads(row[0]) if row else None
        except Exception:
            return None

    @staticmethod
    def inject_plan_cache(days=30, credits=50000):
        if not STATE_VSCDB.exists():
            return False, "state.vscdb not found"

        now_ms = int(time.time() * 1000)
        plan = {
            "planName": "Pro",
            "startTimestamp": now_ms - (30 * 86400000),
            "endTimestamp": now_ms + (days * 86400000),
            "usage": {
                "duration": 1,
                "messages": credits,
                "flowActions": credits,
                "flexCredits": 0,
                "usedMessages": 0,
                "usedFlowActions": 0,
                "usedFlexCredits": 0,
                "remainingMessages": credits,
                "remainingFlowActions": credits,
                "remainingFlexCredits": 0,
            },
            "hasBillingWritePermissions": True,
            "gracePeriodStatus": 0,
        }

        conn = sqlite3.connect(str(STATE_VSCDB))
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM ItemTable WHERE key='windsurf.settings.cachedPlanInfo'")
        exists = cur.fetchone()[0] > 0
        if exists:
            cur.execute("UPDATE ItemTable SET value=? WHERE key='windsurf.settings.cachedPlanInfo'",
                        (json.dumps(plan),))
        else:
            cur.execute("INSERT INTO ItemTable (key, value) VALUES (?, ?)",
                        ('windsurf.settings.cachedPlanInfo', json.dumps(plan)))
        conn.commit()
        conn.close()
        return True, f"Plan cache injected: Pro, {days} days, {credits} credits"


# ============================================================
# Module 3: AccountPool (账号池管理)
# ============================================================
class AccountPool:
    """管理注册的Windsurf账号池"""

    def __init__(self, path=None):
        self.path = Path(path) if path else ACCOUNTS_FILE
        self.accounts = self._load()

    def _load(self):
        if self.path.exists():
            with open(self.path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []

    def _save(self):
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump(self.accounts, f, indent=2, ensure_ascii=False)

    def add(self, email, password, **kwargs):
        account = {
            "email": email,
            "password": password,
            "created_at": datetime.now().isoformat(),
            "status": kwargs.get("status", "registered"),
            "credits_total": kwargs.get("credits_total", 100),
            "credits_used": kwargs.get("credits_used", 0),
            "plan": kwargs.get("plan", "trial"),
            "trial_end": kwargs.get("trial_end", ""),
            "auth_token": kwargs.get("auth_token", ""),
            "mail_token": kwargs.get("mail_token", ""),
            "mail_address": kwargs.get("mail_address", email),
            "first_name": kwargs.get("first_name", ""),
            "last_name": kwargs.get("last_name", ""),
            "notes": kwargs.get("notes", ""),
        }
        self.accounts.append(account)
        self._save()
        return account

    def find(self, email):
        for a in self.accounts:
            if a["email"] == email:
                return a
        return None

    def update(self, email, **kwargs):
        for a in self.accounts:
            if a["email"] == email:
                a.update(kwargs)
                self._save()
                return a
        return None

    def get_active(self):
        for a in self.accounts:
            if a["status"] in ("active", "registered", "verified"):
                remaining = a.get("credits_total", 100) - a.get("credits_used", 0)
                if remaining > 0:
                    return a
        return None

    def list_all(self):
        return self.accounts

    def summary(self):
        total = len(self.accounts)
        by_status = {}
        total_credits = 0
        used_credits = 0
        for a in self.accounts:
            s = a.get("status", "unknown")
            by_status[s] = by_status.get(s, 0) + 1
            total_credits += a.get("credits_total", 0)
            used_credits += a.get("credits_used", 0)
        return {
            "total_accounts": total,
            "by_status": by_status,
            "total_credits": total_credits,
            "used_credits": used_credits,
            "remaining_credits": total_credits - used_credits,
        }


# ============================================================
# Module 4: WindsurfRegistrar (注册自动化)
# ============================================================
class WindsurfRegistrar:
    """Windsurf账号注册自动化 — Playwright驱动"""

    def __init__(self, mail_provider=None, account_pool=None, headless=True):
        if mail_provider:
            self.mail = mail_provider
            self._provider_name = "custom"
        else:
            self.mail, self._provider_name = get_email_provider()
        self.pool = account_pool or AccountPool()
        self.headless = headless
        self.log_entries = []

    def _log(self, msg, level="info"):
        entry = {"time": datetime.now().isoformat(), "level": level, "msg": msg}
        self.log_entries.append(entry)
        prefix = {"info": "[*]", "ok": "[+]", "error": "[-]", "warn": "[!]"}.get(level, "[?]")
        print(f"{prefix} {msg}")

    def _random_name(self):
        return random.choice(FIRST_NAMES), random.choice(LAST_NAMES)

    def _random_password(self, length=16):
        chars = string.ascii_letters + string.digits + "!@#$%"
        pwd = (
            random.choice(string.ascii_uppercase) +
            random.choice(string.ascii_lowercase) +
            random.choice(string.digits) +
            random.choice("!@#$%") +
            ''.join(random.choices(chars, k=length - 4))
        )
        return ''.join(random.sample(pwd, len(pwd)))

    def _random_delay(self, min_s=1.0, max_s=3.0):
        time.sleep(random.uniform(min_s, max_s))

    def register_one(self):
        """注册一个新Windsurf账号 — 全自动流程"""
        self._log("=" * 50)
        self._log("Starting new account registration...")

        # Step 1: 创建临时邮箱
        self._log(f"[*] Step 1: Creating temp email ({self._provider_name})...")
        try:
            inbox = self.mail.create_inbox()
            email = inbox["address"]
            mail_token = inbox["mail_token"]
            self._log(f"  Email: {email}", "ok")
        except Exception as e:
            self._log(f"  Failed to create email: {e}", "error")
            return None

        # Step 2: 生成注册信息
        first_name, last_name = self._random_name()
        ws_password = self._random_password()
        self._log(f"Step 2: Identity: {first_name} {last_name}")

        # Step 3: Playwright注册
        self._log("Step 3: Registering on windsurf.com via Playwright...")
        reg_result = self._playwright_register(first_name, last_name, email, ws_password)

        if not reg_result.get("success"):
            self._log(f"  Registration failed: {reg_result.get('error', 'unknown')}", "error")
            self.pool.add(email, ws_password,
                          status="failed",
                          first_name=first_name, last_name=last_name,
                          mail_token=mail_token,
                          notes=reg_result.get("error", ""))
            return None

        # Step 4: 等待验证邮件
        self._log("Step 4: Waiting for verification email...")
        verification = self._wait_and_verify(mail_token, email, ws_password)

        # Step 5: 保存账号
        status = "verified" if verification.get("verified") else "pending_verification"
        account = self.pool.add(
            email, ws_password,
            status=status,
            first_name=first_name, last_name=last_name,
            mail_token=mail_token,
            credits_total=100,
            plan="trial",
            trial_end=(datetime.now() + timedelta(days=14)).isoformat(),
            notes=verification.get("notes", ""),
        )

        self._log(f"Account saved: {email} [{status}]", "ok")
        self._log(f"  Credits: 100 | Plan: Pro Trial (14 days)")
        return account

    def _playwright_register(self, first_name, last_name, email, password):
        """使用Playwright自动填写注册表单"""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self._log("Playwright not installed. Using fallback method.", "warn")
            return self._api_register_fallback(first_name, last_name, email, password)

        result = {"success": False}
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=self.headless,
                    channel="msedge",
                    args=["--disable-blink-features=AutomationControlled"],
                )
                context = browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                )
                page = context.new_page()

                # Navigate to register page
                page.goto(WINDSURF_REGISTER_URL, wait_until="networkidle", timeout=30000)
                self._random_delay(1.5, 3.0)

                # Fill first name (confirmed selector from Playwright MCP snapshot)
                fn_input = page.get_by_placeholder('Your first name')
                fn_input.fill(first_name)
                self._random_delay(0.5, 1.2)

                # Fill last name
                ln_input = page.get_by_placeholder('Your last name')
                ln_input.fill(last_name)
                self._random_delay(0.5, 1.2)

                # Fill email
                email_input = page.get_by_placeholder('Enter your email address')
                email_input.fill(email)
                self._random_delay(0.5, 1.2)

                # Accept terms checkbox
                checkbox = page.locator('input[type="checkbox"]')
                if checkbox.count() > 0 and not checkbox.first.is_checked():
                    checkbox.first.check()
                    self._random_delay(0.8, 1.5)

                # Wait for Continue button to become enabled
                page.wait_for_timeout(1000)
                continue_btn = page.locator('button:has-text("Continue"):not([disabled])')
                continue_btn.wait_for(state='visible', timeout=5000)
                continue_btn.first.click()
                self._random_delay(3.0, 5.0)

                # Check for password fields (may appear after email step)
                pw_input = page.locator('input[type="password"], #password')
                if pw_input.count() > 0:
                    pw_input.first.fill(password)
                    self._random_delay(0.3, 0.8)

                    pw_confirm = page.locator('#passwordConfirmation, input[placeholder*="confirm" i]')
                    if pw_confirm.count() > 0:
                        pw_confirm.first.fill(password)
                        self._random_delay(0.3, 0.8)

                    # Submit password
                    submit_btn = page.locator('button[type="submit"], button:has-text("Sign up"), button:has-text("Create"), button:has-text("Continue")')
                    if submit_btn.count() > 0:
                        submit_btn.first.click()
                        self._random_delay(2.0, 4.0)

                # Check result
                page_text = page.inner_text("body")
                if any(kw in page_text.lower() for kw in ["verify", "check your email", "confirmation", "sent", "code"]):
                    result = {"success": True, "step": "verification_pending"}
                elif any(kw in page_text.lower() for kw in ["welcome", "dashboard", "get started"]):
                    result = {"success": True, "step": "registered"}
                elif any(kw in page_text.lower() for kw in ["error", "already", "invalid", "blocked"]):
                    error_text = page_text[:500]
                    result = {"success": False, "error": error_text}
                else:
                    # Take screenshot for debugging
                    screenshot_path = str(FARM_DIR / f"_reg_debug_{int(time.time())}.png")
                    page.screenshot(path=screenshot_path)
                    result = {"success": True, "step": "unknown", "screenshot": screenshot_path}

                browser.close()

        except Exception as e:
            result = {"success": False, "error": str(e)}

        return result

    def _api_register_fallback(self, first_name, last_name, email, password):
        """API直接注册 (如果Playwright不可用)"""
        self._log("Attempting direct API registration...", "info")
        # Windsurf可能使用Firebase Auth或自定义auth
        # 尝试常见的注册API端点
        endpoints = [
            "https://server.codeium.com/exa.seat_management_pb.SeatManagementService/RegisterUser",
            "https://server.self-serve.windsurf.com/register_user",
        ]
        for endpoint in endpoints:
            try:
                data = json.dumps({
                    "email": email,
                    "password": password,
                    "first_name": first_name,
                    "last_name": last_name,
                }).encode()
                req = urllib.request.Request(endpoint, data=data, 
                                            headers={"Content-Type": "application/json"},
                                            method="POST")
                with urllib.request.urlopen(req, timeout=15) as resp:
                    body = resp.read().decode()
                    self._log(f"  API response: {body[:200]}", "ok")
                    return {"success": True, "step": "api_registered", "response": body}
            except Exception as e:
                self._log(f"  {endpoint}: {e}", "warn")
                continue

        return {"success": False, "error": "All API endpoints failed. Install Playwright for web automation."}

    def _wait_and_verify(self, mail_token, email, password):
        """等待验证邮件并自动验证"""
        self._log("  Polling inbox for verification email...")
        result = {"verified": False, "notes": ""}

        try:
            msg = self.mail.wait_for_email(
                mail_token, timeout=90, poll_interval=5,
                subject_filter=None  # Accept any email from Windsurf
            )
            if not msg:
                self._log("  No verification email received within timeout", "warn")
                result["notes"] = "No verification email received"
                return result

            self._log(f"  Email received: {msg.get('subject', msg.get('mail_subject', 'no subject'))}", "ok")

            # Try to extract verification link (use standalone functions)
            link = _extract_verification_link(msg)
            code = _extract_verification_code(msg)

            if link:
                self._log(f"  Verification link: {link[:80]}...", "ok")
                # Click the verification link
                try:
                    vdata = _ps_http("GET", link, proxy=PROXY_URL, timeout=15)
                    self._log(f"  Verification response: OK", "ok")
                    result["verified"] = True
                    result["notes"] = "Verified via link (HTTP 200)"
                except Exception as e:
                    self._log(f"  Verification link error: {e}", "warn")
                    result["notes"] = f"Link click failed: {e}"

            elif code:
                self._log(f"  Verification code: {code}", "ok")
                result["notes"] = f"Code: {code} (manual entry may be needed)"

            else:
                # Save full email for debugging
                debug_path = str(FARM_DIR / f"_email_debug_{int(time.time())}.json")
                with open(debug_path, 'w', encoding='utf-8') as f:
                    json.dump(msg, f, indent=2, ensure_ascii=False)
                self._log(f"  Could not extract verification. Email saved: {debug_path}", "warn")
                result["notes"] = f"Email saved for manual review: {debug_path}"

        except Exception as e:
            self._log(f"  Verification error: {e}", "error")
            result["notes"] = str(e)

        return result

    def batch_register(self, count=5, delay_between=10):
        """批量注册多个账号"""
        self._log(f"\n{'='*60}")
        self._log(f"BATCH REGISTRATION: {count} accounts")
        self._log(f"{'='*60}\n")

        results = []
        for i in range(count):
            self._log(f"\n--- Account {i+1}/{count} ---")

            # Reset fingerprint between registrations
            if i > 0:
                self._log("Resetting device fingerprint...")
                ok, msg = TelemetryManager.reset_fingerprint()
                self._log(f"  {msg}")
                self._random_delay(2, 5)

            account = self.register_one()
            results.append(account)

            if i < count - 1:
                delay = delay_between + random.uniform(-3, 3)
                self._log(f"Waiting {delay:.0f}s before next registration...")
                time.sleep(max(5, delay))

        # Summary
        success = sum(1 for r in results if r is not None)
        self._log(f"\n{'='*60}")
        self._log(f"BATCH COMPLETE: {success}/{count} successful")
        self._log(f"{'='*60}")

        # Save log
        self._save_log()
        return results

    def _save_log(self):
        with open(FARM_LOG, 'w', encoding='utf-8') as f:
            json.dump(self.log_entries, f, indent=2, ensure_ascii=False)


# ============================================================
# Module 5: CLI Interface
# ============================================================
def cmd_test_email():
    """测试Mail.tm API"""
    print("=== Mail.tm API Test ===")
    mail = TempMailProvider()

    print("1. Getting domains...")
    domains = mail.get_domains()
    print(f"   Available: {domains}")

    print("2. Creating inbox...")
    inbox = mail.create_inbox()
    print(f"   Address: {inbox['address']}")
    print(f"   Token: {inbox['mail_token'][:30]}...")

    print("3. Checking inbox...")
    msgs = mail.get_messages(inbox["mail_token"])
    print(f"   Messages: {len(msgs)}")

    print("\n[OK] Mail.tm API fully functional!")
    return True


def cmd_status():
    """显示账号池状态"""
    pool = AccountPool()
    summary = pool.summary()

    print("=" * 50)
    print("WINDSURF ACCOUNT FARM STATUS")
    print("=" * 50)
    print(f"Total accounts: {summary['total_accounts']}")
    print(f"Credits: {summary['remaining_credits']}/{summary['total_credits']} remaining")
    print(f"\nBy status:")
    for status, count in summary['by_status'].items():
        print(f"  {status}: {count}")

    print(f"\nLocal Windsurf fingerprint:")
    fp = TelemetryManager.get_current_fingerprint()
    for k, v in fp.items():
        print(f"  {k}: {str(v)[:20]}...")

    plan = TelemetryManager.get_current_plan()
    if plan:
        usage = plan.get("usage", {})
        print(f"\nCached plan: {plan.get('planName', '?')}")
        print(f"  Remaining: {usage.get('remainingMessages', '?')}")
        print(f"  Grace: {plan.get('gracePeriodStatus', '?')}")

    if summary['total_accounts'] > 0:
        print(f"\nAll accounts:")
        for a in pool.list_all():
            remaining = a.get('credits_total', 0) - a.get('credits_used', 0)
            print(f"  {a['email']} | {a['status']} | {remaining} credits | {a.get('created_at','')[:10]}")


def cmd_register(count=1, headless=True):
    """注册新账号"""
    registrar = WindsurfRegistrar(headless=headless)
    if count == 1:
        return registrar.register_one()
    else:
        return registrar.batch_register(count=count)


def cmd_reset_fingerprint():
    """重置设备指纹"""
    print("=== Reset Device Fingerprint ===")
    ok, msg = TelemetryManager.reset_fingerprint()
    print(f"  Fingerprint: {msg}")
    ok2, msg2 = TelemetryManager.clear_auth_cache()
    print(f"  Auth cache: {msg2}")
    ok3, msg3 = TelemetryManager.inject_plan_cache()
    print(f"  Plan cache: {msg3}")
    print("\n[!] Restart Windsurf and login with a new account to activate trial.")


def cmd_activate(email):
    """激活指定账号到本地Windsurf"""
    pool = AccountPool()
    account = pool.find(email)
    if not account:
        print(f"Account not found: {email}")
        return

    print(f"Activating: {email}")
    print("1. Resetting fingerprint...")
    TelemetryManager.reset_fingerprint()
    print("2. Clearing auth cache...")
    TelemetryManager.clear_auth_cache()
    print("3. Injecting plan cache...")
    TelemetryManager.inject_plan_cache()

    pool.update(email, status="activating")
    print(f"\n[!] Now restart Windsurf and log in with:")
    print(f"    Email: {email}")
    print(f"    Password: {account['password']}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1].lower()

    if cmd == "test-email":
        cmd_test_email()

    elif cmd == "status":
        cmd_status()

    elif cmd == "register":
        count = 1
        headless = True
        for i, arg in enumerate(sys.argv[2:], 2):
            if arg == "--count" and i + 1 < len(sys.argv):
                count = int(sys.argv[i + 1])
            if arg == "--visible":
                headless = False
        cmd_register(count=count, headless=headless)

    elif cmd == "reset-fingerprint":
        cmd_reset_fingerprint()

    elif cmd == "activate":
        if len(sys.argv) < 3:
            print("Usage: windsurf_farm.py activate <email>")
            return
        cmd_activate(sys.argv[2])

    elif cmd == "check":
        cmd_status()

    else:
        print(f"Unknown command: {cmd}")
        print("Commands: test-email | status | register | reset-fingerprint | activate | check")


if __name__ == "__main__":
    main()
