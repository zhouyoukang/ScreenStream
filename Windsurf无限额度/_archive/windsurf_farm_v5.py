"""
Windsurf Account Farm v5.0 — Camoufox突破+四引擎+全链路自动化
=========================================================================
v5.0核心突破 (基于v4.0 + 2026-03全网调研):
  1. Camoufox引擎 — Firefox反检测,C++级指纹伪造,Turnstile ~90%+通过率
  2. 四引擎自动降级 — Camoufox → DrissionPage → Playwright
  3. 邮箱Bug修复 — 验证链接提取+HTML解码+多模式匹配
  4. 域名封禁检测 — 自动跳过已知被封域名
  5. v4账号池自动迁移 — 无损继承12账号

用法:
  python windsurf_farm_v5.py register                     # 注册1个(Camoufox优先)
  python windsurf_farm_v5.py register --count 5            # 批量注册5个
  python windsurf_farm_v5.py register --engine camoufox    # 指定Camoufox
  python windsurf_farm_v5.py register --engine drission    # 指定DrissionPage
  python windsurf_farm_v5.py status                        # 账号池状态
  python windsurf_farm_v5.py switch                        # 自动切换最优账号
  python windsurf_farm_v5.py audit                         # 全链路审计
  python windsurf_farm_v5.py deep-report                   # 深度研究报告

依赖: pip install camoufox[geoip] (推荐) | DrissionPage | playwright
"""

import json, os, sys, time, uuid, random, string, sqlite3, shutil, re, base64, html as html_mod
from datetime import datetime, timedelta
from pathlib import Path
import subprocess

FARM_DIR = Path(__file__).parent
ACCOUNTS_FILE = FARM_DIR / "_farm_accounts_v5.json"
TURNSTILE_PATCH_DIR = FARM_DIR / "turnstilePatch"

WINDSURF_DATA = Path(os.path.expandvars(r'%APPDATA%\Windsurf\User\globalStorage'))
STORAGE_JSON = WINDSURF_DATA / 'storage.json'
STATE_VSCDB = WINDSURF_DATA / 'state.vscdb'

GUERRILLA_API = "https://api.guerrillamail.com/ajax.php"
MAIL_TM_API = "https://api.mail.tm"
WINDSURF_REGISTER_URL = "https://windsurf.com/account/register"
PROXY_CANDIDATES = ["http://127.0.0.1:7890", "http://127.0.0.1:7897"]
TELEMETRY_KEYS = [
    'telemetry.machineId', 'telemetry.macMachineId',
    'telemetry.devDeviceId', 'telemetry.sqmId', 'storage.serviceMachineId',
]

FIRST_NAMES = ["Alex","Jordan","Taylor","Morgan","Casey","Riley","Quinn","Avery",
    "Charlie","Dakota","Emerson","Finley","Harper","Jamie","Kendall","Logan",
    "Madison","Parker","Reese","Skyler","Blake","Drew","Eden","Gray",
    "Haven","Jules","Kit","Lane","Nico","Oakley","Phoenix","River",
    "Sage","Tatum","Val","Winter","Zion","Rowan","Hayden","Spencer"]
LAST_NAMES = ["Anderson","Brooks","Carter","Davis","Edwards","Fisher","Garcia",
    "Hughes","Irving","Jensen","Kim","Lee","Mitchell","Nelson","Ortiz",
    "Park","Quinn","Rivera","Smith","Turner","Upton","Vance","Walsh",
    "Young","Zhang","Adams","Baker","Clark","Foster","Grant","Hayes",
    "James","Kelly","Lewis","Moore","Price","Reed","Scott","Torres"]

BLOCKED_DOMAINS = ["tempmail.com","throwaway.email","guerrillamail.info","sharklasers.com"]
CREDIT_TABLE = {"SWE-1":0,"SWE-1.5":0,"SWE-1.6":0,"Gemini 3 Flash":0,
    "GPT-4.1":0.25,"o4-mini":0.25,"Claude Sonnet 4":1,"GPT-5.x":1,
    "Claude Sonnet 4.5":3,"Claude Opus":3}

# === PowerShell HTTP桥接 ===
def _ps_http(method, url, body=None, headers=None, proxy=None, timeout=15):
    ps = ['$ProgressPreference="SilentlyContinue"']
    iwr = f'Invoke-WebRequest -Uri "{url}" -Method {method} -UseBasicParsing -TimeoutSec {timeout}'
    if proxy: iwr += f' -Proxy "{proxy}"'
    if body:
        escaped = body.replace('"', '`"')
        iwr += f' -Body "{escaped}" -ContentType "application/json"'
    if headers:
        h = "; ".join(f'"{k}"="{v}"' for k,v in headers.items())
        iwr += f' -Headers @{{{h}}}'
    ps.append(f'$r = ({iwr}).Content')
    ps.append('if($r -is [byte[]]){[System.Text.Encoding]::UTF8.GetString($r)}else{$r}')
    enc = base64.b64encode('\n'.join(ps).encode('utf-16-le')).decode()
    r = subprocess.run(["powershell","-NoProfile","-EncodedCommand",enc],
        capture_output=True, text=True, timeout=timeout+15, encoding='utf-8', errors='replace')
    if r.returncode != 0: raise RuntimeError(f"PS {method} {url}: {r.stderr[:300]}")
    out = r.stdout.strip()
    if not out: raise RuntimeError(f"PS {method} {url}: empty")
    for i,ch in enumerate(out):
        if ch in ('{','['):
            try: return json.loads(out[i:])
            except: continue
    return json.loads(out)

PROXY_URL = None
def get_proxy():
    global PROXY_URL
    if PROXY_URL is None:
        for p in PROXY_CANDIDATES:
            try:
                _ps_http("GET", f"{GUERRILLA_API}?f=get_email_address", proxy=p, timeout=8)
                PROXY_URL = p; return p
            except: continue
        PROXY_URL = PROXY_CANDIDATES[0]
    return PROXY_URL

# === 邮箱引擎 ===
class GuerrillaMailProvider:
    NAME = "GuerrillaMail"
    def __init__(self): self.api = GUERRILLA_API; self.sid = None
    def _req(self, params, retries=3):
        for a in range(retries):
            try:
                qs = "&".join(f"{k}={v}" for k,v in params.items())
                url = f"{self.api}?{qs}" + (f"&sid_token={self.sid}" if self.sid else "")
                d = _ps_http("GET", url, proxy=get_proxy(), timeout=15)
                if isinstance(d,dict) and "sid_token" in d: self.sid = d["sid_token"]
                return d
            except Exception as e:
                if a < retries-1: time.sleep(2*(a+1)); continue
                raise
    def create_inbox(self, prefix=None):
        d = self._req({"f":"get_email_address"})
        addr = d.get("email_addr","")
        if prefix:
            d2 = self._req({"f":"set_email_user","email_user":prefix})
            addr = d2.get("email_addr", addr)
        return {"address":addr,"password":"","mail_token":self.sid or "","account_id":addr}
    def wait_for_email(self, token=None, timeout=120, poll_interval=5, subject_filter=None):
        start = time.time()
        while time.time()-start < timeout:
            d = self._req({"f":"check_email","seq":"0"})
            for m in d.get("list",[]):
                if subject_filter and subject_filter.lower() not in m.get("mail_subject","").lower(): continue
                mid = m.get("mail_id","")
                if mid: return self._req({"f":"fetch_email","email_id":mid})
            time.sleep(poll_interval)
        return None

class MailTmProvider:
    NAME = "Mail.tm"
    def __init__(self): self.api = MAIL_TM_API; self._doms = None
    def _req(self, method, path, data=None, token=None, timeout=15, retries=3):
        url = f"{self.api}{path}"
        hdrs = {"Authorization":f"Bearer {token}"} if token else None
        body = json.dumps(data) if data else None
        for a in range(retries):
            try: return _ps_http(method, url, body=body, headers=hdrs, proxy=get_proxy(), timeout=timeout)
            except Exception as e:
                if a < retries-1: time.sleep(2*(a+1)); continue
                raise
    def get_domains(self):
        if self._doms is None:
            r = self._req("GET","/domains")
            ms = r.get("hydra:member",[]) if isinstance(r,dict) else (r if isinstance(r,list) else [])
            self._doms = [d["domain"] for d in ms if isinstance(d,dict) and d.get("isActive")]
        return self._doms
    def create_inbox(self, prefix=None):
        doms = self.get_domains()
        if not doms: raise RuntimeError("No Mail.tm domains")
        dom = random.choice(doms)
        pfx = prefix or ("ws"+''.join(random.choices(string.ascii_lowercase+string.digits,k=8)))
        addr = f"{pfx}@{dom}"
        pw = ''.join(random.choices(string.ascii_letters+string.digits,k=16))
        self._req("POST","/accounts",{"address":addr,"password":pw},timeout=30)
        tr = self._req("POST","/token",{"address":addr,"password":pw},timeout=30)
        tk = tr.get("token","") if isinstance(tr,dict) else ""
        return {"address":addr,"password":pw,"mail_token":tk,"account_id":addr}
    def wait_for_email(self, token, timeout=120, poll_interval=5, subject_filter=None):
        start = time.time()
        while time.time()-start < timeout:
            r = self._req("GET","/messages?page=1",token=token)
            ms = r.get("hydra:member",[]) if isinstance(r,dict) else (r if isinstance(r,list) else [])
            for m in ms:
                if subject_filter and subject_filter.lower() not in m.get("subject","").lower(): continue
                return self._req("GET",f"/messages/{m['id']}",token=token)
            time.sleep(poll_interval)
        return None

def get_email_provider():
    for PC in [GuerrillaMailProvider, MailTmProvider]:
        try:
            p = PC(); inbox = p.create_inbox()
            if inbox and inbox.get("address"):
                dom = inbox['address'].split('@')[-1] if '@' in inbox['address'] else ''
                if dom in BLOCKED_DOMAINS:
                    print(f"  [!] {PC.NAME} domain {dom} blocked, next..."); continue
                print(f"  [+] Email: {PC.NAME} ({inbox['address']})"); return p
        except Exception as e: print(f"  [!] {PC.NAME}: {e}")
    return GuerrillaMailProvider()

# === 验证提取 (v5.1修复: 过滤邮箱服务URL+优先windsurf域) ===
MAIL_SERVICE_DOMAINS = ['guerrillamail','grr.la','sharklasers','mail.tm','dollicons']

def _clean_url(u):
    u = re.sub(r'["\'>;\s]+$','',u.rstrip('.'))
    u = html_mod.unescape(u)
    return u

def _is_mail_service_url(u):
    ul = u.lower()
    return any(d in ul for d in MAIL_SERVICE_DOMAINS)

def extract_verification_link(msg):
    text = msg.get("text","") or msg.get("mail_body","") or ""
    h = msg.get("html", msg.get("mail_body",""))
    if isinstance(h,list): h = " ".join(str(x) for x in h)
    elif h is None: h = ""
    content = html_mod.unescape(str(text)+" "+str(h))
    all_urls = re.findall(r'https?://[^\s<>"\']+', content)
    all_urls = [_clean_url(u) for u in all_urls]
    ext_urls = [u for u in all_urls if not _is_mail_service_url(u)]
    ws_verify = [u for u in ext_urls if ('windsurf' in u.lower() or 'codeium' in u.lower())
                 and any(k in u.lower() for k in ['verify','confirm','activate','auth','token','code','callback','magic'])]
    if ws_verify: return ws_verify[0]
    ws_any = [u for u in ext_urls if 'windsurf' in u.lower() or 'codeium' in u.lower()]
    if ws_any: return ws_any[0]
    verify_any = [u for u in ext_urls if any(k in u.lower() for k in ['verify','confirm','activate','auth','token','code','callback'])]
    if verify_any: return verify_any[0]
    return ext_urls[0] if ext_urls else None

def extract_verification_code(msg):
    text = msg.get("text","") or msg.get("mail_body","") or ""
    h = msg.get("html", msg.get("mail_body",""))
    if isinstance(h,list): h = " ".join(str(x) for x in h)
    elif h is None: h = ""
    content = html_mod.unescape(str(text)+" "+str(h))
    codes = re.findall(r'\b(\d{4,8})\b', content)
    return codes[0] if codes else None

# === TelemetryManager ===
class TelemetryManager:
    @staticmethod
    def gen_id(dashes=True): u=uuid.uuid4(); return str(u) if dashes else u.hex
    @staticmethod
    def get_fp():
        if not STORAGE_JSON.exists(): return {}
        with open(STORAGE_JSON,'r',encoding='utf-8') as f: d=json.load(f)
        return {k:d.get(k,'<not set>') for k in TELEMETRY_KEYS}
    @staticmethod
    def reset_fp():
        if not STORAGE_JSON.exists(): return False,"storage.json not found"
        bk = str(STORAGE_JSON)+f'.bak_{int(time.time())}'
        shutil.copy2(STORAGE_JSON,bk)
        with open(STORAGE_JSON,'r',encoding='utf-8') as f: d=json.load(f)
        for k in TELEMETRY_KEYS:
            d[k] = TelemetryManager.gen_id(dashes=('serviceMachineId' in k or 'devDeviceId' in k))
        for k in ['telemetry.firstSessionDate','telemetry.lastSessionDate','telemetry.currentSessionDate']:
            if k in d: d[k] = time.strftime('%a, %d %b %Y %H:%M:%S GMT', time.gmtime())
        with open(STORAGE_JSON,'w',encoding='utf-8') as f: json.dump(d,f,indent='\t')
        return True,f"Reset. Backup: {bk}"
    @staticmethod
    def clear_auth():
        if not STATE_VSCDB.exists(): return False,"state.vscdb not found"
        bk = str(STATE_VSCDB)+f'.bak_{int(time.time())}'
        shutil.copy2(STATE_VSCDB,bk)
        conn = sqlite3.connect(str(STATE_VSCDB)); cur = conn.cursor()
        cur.execute("DELETE FROM ItemTable WHERE key='windsurf.settings.cachedPlanInfo'")
        cur.execute("DELETE FROM ItemTable WHERE key LIKE '%windsurf_auth%'")
        cur.execute("DELETE FROM ItemTable WHERE key LIKE '%windsurfAuth%'")
        cur.execute("DELETE FROM ItemTable WHERE key LIKE 'telemetry.%'")
        conn.commit(); n=conn.total_changes; conn.close()
        return True,f"Cleared {n}. Backup: {bk}"
    @staticmethod
    def inject_plan(days=30, credits=50000):
        if not STATE_VSCDB.exists(): return False,"state.vscdb not found"
        now_ms = int(time.time()*1000)
        plan = {"planName":"Pro","startTimestamp":now_ms-(30*86400000),"endTimestamp":now_ms+(days*86400000),
            "usage":{"duration":1,"messages":credits,"flowActions":credits,"flexCredits":0,
                "usedMessages":0,"usedFlowActions":0,"usedFlexCredits":0,
                "remainingMessages":credits,"remainingFlowActions":credits,"remainingFlexCredits":0},
            "hasBillingWritePermissions":True,"gracePeriodStatus":0}
        conn = sqlite3.connect(str(STATE_VSCDB)); cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM ItemTable WHERE key='windsurf.settings.cachedPlanInfo'")
        if cur.fetchone()[0]>0:
            cur.execute("UPDATE ItemTable SET value=? WHERE key='windsurf.settings.cachedPlanInfo'",(json.dumps(plan),))
        else:
            cur.execute("INSERT INTO ItemTable(key,value)VALUES(?,?)",('windsurf.settings.cachedPlanInfo',json.dumps(plan)))
        conn.commit(); conn.close()
        return True,f"Injected Pro {days}d {credits}cr"

# === AccountPool (自动迁移v4) ===
class AccountPool:
    def __init__(self, path=None):
        self.path = Path(path) if path else ACCOUNTS_FILE
        self.data = self._load()
    def _load(self):
        if self.path.exists():
            with open(self.path,'r',encoding='utf-8') as f: d=json.load(f)
            return d if isinstance(d,dict) else {"version":"5.0","accounts":d,"current":None}
        v4 = FARM_DIR/"_farm_accounts.json"
        if v4.exists():
            with open(v4,'r',encoding='utf-8') as f: d4=json.load(f)
            if isinstance(d4,list):
                print(f"  [*] Migrated {len(d4)} accounts from v4")
                return {"version":"5.0","accounts":d4,"current":None}
        return {"version":"5.0","accounts":[],"current":None}
    def _save(self):
        with open(self.path,'w',encoding='utf-8') as f: json.dump(self.data,f,indent=2,ensure_ascii=False)
    @property
    def accounts(self): return self.data.get("accounts",[])
    def add(self, email, pw, **kw):
        a = {"email":email,"password":pw,"created_at":datetime.now().isoformat(),
            "status":kw.get("status","registered"),"credits_total":kw.get("credits_total",100),
            "credits_used":kw.get("credits_used",0),"plan":kw.get("plan","trial"),
            "trial_end":kw.get("trial_end",""),"first_name":kw.get("first_name",""),
            "last_name":kw.get("last_name",""),"mail_token":kw.get("mail_token",""),
            "notes":kw.get("notes",""),"engine":kw.get("engine","")}
        self.data["accounts"].append(a); self._save(); return a
    def find(self, email): return next((a for a in self.accounts if a["email"]==email),None)
    def update(self, email, **kw):
        for a in self.accounts:
            if a["email"]==email: a.update(kw); self._save(); return a
        return None
    def get_best(self):
        cs = [(a.get("credits_total",100)-a.get("credits_used",0),a) for a in self.accounts
              if a["status"] in ("active","registered","verified") and a.get("credits_total",100)-a.get("credits_used",0)>0]
        cs.sort(key=lambda x:x[0],reverse=True)
        return cs[0][1] if cs else None
    def summary(self):
        t=len(self.accounts); bs={}; tc=uc=0
        for a in self.accounts:
            s=a.get("status","?"); bs[s]=bs.get(s,0)+1
            tc+=a.get("credits_total",0); uc+=a.get("credits_used",0)
        return {"total":t,"by_status":bs,"total_credits":tc,"used":uc,"remaining":tc-uc}

# === Turnstile处理 ===
def _turnstile_camoufox(page, max_wait=30):
    print("  [*] Turnstile (Camoufox humanize)...")
    start = time.time()
    while time.time()-start < max_wait:
        try:
            body = page.content()
            if any(k in body.lower() for k in ["verify your email","check your email","dashboard","welcome back"]):
                print("  [+] Page transitioned!"); return True
            iframes = page.locator('iframe[src*="challenges.cloudflare.com"]')
            if iframes.count()>0:
                time.sleep(random.uniform(2,4))
                try:
                    box = iframes.first.bounding_box()
                    if box: page.mouse.click(box['x']+box['width']/2, box['y']+box['height']/2)
                    time.sleep(random.uniform(2,4))
                except: pass
            # Check if Turnstile resolved (green checkmark / 成功)
            if '成功' in body or 'Success' in body or 'success' in body:
                btn = page.locator('button:has-text("Continue"):not([disabled])')
                if btn.count()>0:
                    print("  [+] Turnstile success! Clicking Continue...")
                    btn.first.click(); time.sleep(3); return True
            btn = page.locator('button:has-text("Continue"):not([disabled])')
            if btn.count()>0: btn.first.click(); time.sleep(2); return True
        except: pass
        time.sleep(1)
    print("  [!] Turnstile timeout"); return False

def _turnstile_drission(page, max_wait=30):
    print("  [*] Turnstile (DrissionPage+turnstilePatch)...")
    start = time.time()
    while time.time()-start < max_wait:
        try:
            body = page.html if hasattr(page,'html') else ""
            if any(k in body.lower() for k in ["verify your email","check your email","dashboard","welcome back"]):
                print("  [+] Page transitioned!"); return True
            # Wait for Turnstile iframe to resolve
            page.ele('tag:iframe@src:challenges.cloudflare.com', timeout=2)
            time.sleep(random.uniform(2,4))
            # Always try clicking Continue if available (Turnstile may have auto-resolved)
            btn = page.ele('tag:button@text():Continue', timeout=1)
            if btn and not btn.attr('disabled'):
                print("  [+] Continue enabled, clicking...")
                btn.click(); time.sleep(3); return True
        except: pass
        time.sleep(1)
    # Final attempt: just click Continue if it exists
    try:
        btn = page.ele('tag:button@text():Continue', timeout=2)
        if btn and not btn.attr('disabled'): btn.click(); time.sleep(3); return True
    except: pass
    print("  [!] Turnstile timeout"); return False

def _turnstile_playwright(page, max_wait=30):
    print("  [*] Turnstile (Playwright JS)...")
    page.evaluate("""
        Object.defineProperty(navigator,'webdriver',{get:()=>undefined});
        Object.defineProperty(MouseEvent.prototype,'screenX',{value:Math.floor(Math.random()*400+800)});
        Object.defineProperty(MouseEvent.prototype,'screenY',{value:Math.floor(Math.random()*200+400)});
    """)
    start = time.time()
    while time.time()-start < max_wait:
        try:
            body = page.inner_text("body")
            if any(k in body.lower() for k in ["verify your email","check your email","dashboard","welcome","password"]):
                print("  [+] Turnstile passed!"); return True
            btn = page.locator('button:has-text("Continue"):not([disabled])')
            if btn.count()>0: btn.first.click(); time.sleep(2); return True
        except: pass
        time.sleep(1)
    return False

# === 注册引擎: Camoufox (★v5推荐) ===
def _reg_camoufox(fn, ln, email, pw, headless=False):
    try:
        from camoufox.sync_api import Camoufox
    except ImportError:
        return {"success":False,"error":"pip install camoufox[geoip]"}
    print(f"  [*] Engine: Camoufox (headless={headless})")
    result = {"success":False}
    try:
        with Camoufox(headless=headless, humanize=True, os="windows", window=(1280,800)) as browser:
            page = browser.new_page()
            print("  [*] Step 1: Navigate...")
            page.goto(WINDSURF_REGISTER_URL, wait_until="networkidle", timeout=30000)
            time.sleep(random.uniform(2,4))
            print(f"  [*] Step 2: Fill ({fn} {ln}, {email})...")
            for sel,val in [('input[name="first_name"]',fn),('input[name="last_name"]',ln),('input[name="email"]',email)]:
                el = page.locator(sel)
                if el.count()>0: el.first.fill(val); time.sleep(random.uniform(0.3,0.8))
            cb = page.locator('input[type="checkbox"]')
            if cb.count()>0 and not cb.first.is_checked(): cb.first.check(); time.sleep(0.5)
            time.sleep(1)
            btn = page.locator('button:has-text("Continue"):not([disabled])')
            if btn.count()>0: btn.first.click(); time.sleep(random.uniform(3,5))
            print("  [*] Step 3: Turnstile...")
            _turnstile_camoufox(page, 25)
            print("  [*] Step 4: Password...")
            pws = page.locator('input[type="password"]')
            if pws.count()>0:
                pws.first.fill(pw); time.sleep(0.5)
                if pws.count()>1: pws.nth(1).fill(pw); time.sleep(0.5)
                sub = page.locator('button[type="submit"],button:has-text("Continue"),button:has-text("Sign up")')
                if sub.count()>0: sub.first.click(); time.sleep(random.uniform(2,4))
            print("  [*] Step 5: Second Turnstile...")
            _turnstile_camoufox(page, 25)
            body = page.content()
            if any(k in body.lower() for k in ["verify","check your email","confirmation","sent","code"]):
                result = {"success":True,"step":"verification_pending"}
            elif any(k in body.lower() for k in ["welcome","dashboard","get started"]):
                result = {"success":True,"step":"registered"}
            elif any(k in body.lower() for k in ["error","already","invalid"]):
                result = {"success":False,"error":body[:300]}
            else:
                ss = str(FARM_DIR/f"_cfox_{int(time.time())}.png")
                try: page.screenshot(path=ss)
                except: pass
                result = {"success":True,"step":"unknown","screenshot":ss}
    except Exception as e:
        result = {"success":False,"error":str(e)}
    return result

# === 注册引擎: DrissionPage ===
def _reg_drission(fn, ln, email, pw, headless=False):
    try:
        from DrissionPage import ChromiumOptions, ChromiumPage
    except ImportError:
        return {"success":False,"error":"pip install DrissionPage"}
    print(f"  [*] Engine: DrissionPage (headless={headless})")
    result = {"success":False}; page = None
    try:
        co = ChromiumOptions()
        for cp in [os.path.join(os.environ.get('PROGRAMFILES',''),'Google','Chrome','Application','chrome.exe'),
                   os.path.join(os.environ.get('LOCALAPPDATA',''),'Google','Chrome','Application','chrome.exe')]:
            if os.path.exists(cp): co.set_browser_path(cp); break
        co.set_argument("--incognito"); co.auto_port(); co.headless(headless)
        ext = str(TURNSTILE_PATCH_DIR)
        if os.path.exists(ext):
            co.set_argument("--allow-extensions-in-incognito"); co.add_extension(ext)
            print("  [+] turnstilePatch loaded")
        page = ChromiumPage(co)
        page.get(WINDSURF_REGISTER_URL); time.sleep(random.uniform(2,4))
        for sel,val in [('@name=first_name',fn),('@name=last_name',ln),('@name=email',email)]:
            el = page.ele(sel)
            if el: el.input(val); time.sleep(random.uniform(0.3,0.8))
        cb = page.ele('tag:input@type=checkbox')
        if cb and not cb.attr('checked'): cb.click(); time.sleep(0.5)
        btn = page.ele('tag:button@text():Continue')
        if btn: btn.click(); time.sleep(random.uniform(3,5))
        _turnstile_drission(page, 20)
        pi = page.ele('@type=password')
        if pi:
            pi.input(pw); time.sleep(0.5)
            pc = page.ele('@placeholder=Confirm password')
            if pc: pc.input(pw); time.sleep(0.5)
            sub = page.ele('tag:button@type=submit') or page.ele('tag:button@text():Continue')
            if sub: sub.click(); time.sleep(random.uniform(2,4))
        _turnstile_drission(page, 20)
        body = page.html or ""
        if any(k in body.lower() for k in ["verify","check your email","confirmation"]):
            result = {"success":True,"step":"verification_pending"}
        elif any(k in body.lower() for k in ["welcome","dashboard"]):
            result = {"success":True,"step":"registered"}
        else:
            result = {"success":True,"step":"unknown"}
    except Exception as e: result = {"success":False,"error":str(e)}
    finally:
        if page:
            try: page.quit()
            except: pass
    return result

# === 注册引擎: Playwright ===
def _reg_playwright(fn, ln, email, pw, headless=True):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"success":False,"error":"pip install playwright"}
    print(f"  [*] Engine: Playwright (headless={headless})")
    result = {"success":False}
    try:
        with sync_playwright() as p:
            br = p.chromium.launch(headless=headless,channel="msedge",args=["--disable-blink-features=AutomationControlled"])
            ctx = br.new_context(viewport={"width":1280,"height":800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36")
            page = ctx.new_page()
            page.add_init_script("""
                Object.defineProperty(navigator,'webdriver',{get:()=>undefined});
                Object.defineProperty(MouseEvent.prototype,'screenX',{value:Math.floor(Math.random()*400+800)});
                Object.defineProperty(MouseEvent.prototype,'screenY',{value:Math.floor(Math.random()*200+400)});
            """)
            page.goto(WINDSURF_REGISTER_URL,wait_until="networkidle",timeout=30000)
            time.sleep(random.uniform(1.5,3))
            page.get_by_placeholder('Your first name').fill(fn); time.sleep(0.5)
            page.get_by_placeholder('Your last name').fill(ln); time.sleep(0.5)
            page.get_by_placeholder('Enter your email address').fill(email); time.sleep(0.5)
            cb = page.locator('input[type="checkbox"]')
            if cb.count()>0 and not cb.first.is_checked(): cb.first.check(); time.sleep(0.5)
            page.wait_for_timeout(1000)
            page.locator('button:has-text("Continue"):not([disabled])').first.click()
            time.sleep(random.uniform(3,5))
            _turnstile_playwright(page, 20)
            pws = page.locator('input[type="password"]')
            if pws.count()>0:
                pws.first.fill(pw); time.sleep(0.5)
                pc = page.locator('input[placeholder*="confirm" i]')
                if pc.count()>0: pc.first.fill(pw); time.sleep(0.5)
                sub = page.locator('button[type="submit"],button:has-text("Continue")')
                if sub.count()>0: sub.first.click(); time.sleep(random.uniform(2,4))
            _turnstile_playwright(page, 20)
            body = page.inner_text("body")
            if any(k in body.lower() for k in ["verify","check your email"]): result={"success":True,"step":"verification_pending"}
            elif any(k in body.lower() for k in ["welcome","dashboard"]): result={"success":True,"step":"registered"}
            else: result={"success":True,"step":"unknown"}
            br.close()
    except Exception as e: result={"success":False,"error":str(e)}
    return result

# === 引擎选择+注册+批量 ===
ENGINE_PRIORITY = ["camoufox","drission","playwright"]

def detect_engines():
    avail = []
    try: from camoufox.sync_api import Camoufox; avail.append("camoufox")
    except: pass
    try: import DrissionPage; avail.append("drission")
    except: pass
    try: from playwright.sync_api import sync_playwright; avail.append("playwright")
    except: pass
    return avail

def register_one(engine=None, headless=None):
    print("="*60); print("WINDSURF ACCOUNT FARM v5.0"); print("="*60)
    avail = detect_engines()
    if not avail: print("[-] No engine! pip install camoufox[geoip]"); return None
    chosen = engine if engine in avail else next((e for e in ENGINE_PRIORITY if e in avail), avail[0])
    if headless is None: headless = (chosen == "playwright")
    print(f"[*] Engine: {chosen} | Headless: {headless}")

    print("\n[Step 1] Creating temp email...")
    mp = get_email_provider()
    try:
        inbox = mp.create_inbox(); email = inbox["address"]; mtk = inbox.get("mail_token","")
        print(f"  [+] Email: {email}")
    except Exception as e: print(f"  [-] Email failed: {e}"); return None

    fn = random.choice(FIRST_NAMES); ln = random.choice(LAST_NAMES)
    chars = string.ascii_letters+string.digits+"!@#$"
    pw = (random.choice(string.ascii_uppercase)+random.choice(string.ascii_lowercase)+
          random.choice(string.digits)+random.choice("!@#$")+''.join(random.choices(chars,k=12)))
    pw = ''.join(random.sample(pw,len(pw)))
    print(f"\n[Step 2] Identity: {fn} {ln}")

    print(f"\n[Step 3] Registering...")
    reg = {"camoufox":_reg_camoufox,"drission":_reg_drission,"playwright":_reg_playwright}[chosen](fn,ln,email,pw,headless=headless)

    if not reg.get("success"):
        print(f"\n[-] Failed: {reg.get('error','?')}")
        AccountPool().add(email,pw,status="failed",first_name=fn,last_name=ln,mail_token=mtk,notes=reg.get("error",""),engine=chosen)
        return None
    print(f"\n[+] Step: {reg.get('step','?')}")

    print(f"\n[Step 4] Waiting verification email...")
    verified = False; notes = ""
    try:
        msg = mp.wait_for_email(mtk, timeout=90, poll_interval=5)
        if msg:
            link = extract_verification_link(msg); code = extract_verification_code(msg)
            if link:
                print(f"  [+] Link: {link[:60]}...")
                try: _ps_http("GET",link,proxy=get_proxy(),timeout=15); verified=True; notes="Verified via link"
                except Exception as e: notes=f"Link failed: {e}"
            elif code: print(f"  [+] Code: {code}"); notes=f"Code: {code}"
            else: notes="No link/code found in email"
        else: notes="No email within timeout"
    except Exception as e: notes=f"Verify error: {e}"

    pool = AccountPool()
    status = "verified" if verified else "pending_verification"
    acct = pool.add(email,pw,status=status,first_name=fn,last_name=ln,mail_token=mtk,
        credits_total=100,plan="trial",trial_end=(datetime.now()+timedelta(days=14)).isoformat(),
        notes=notes,engine=chosen)
    print(f"\n{'='*60}")
    print(f"[+] {email} [{status}] | {pw} | 100cr | {chosen}")
    print(f"    {notes}")
    print(f"{'='*60}")
    return acct

def batch_register(count=5, engine=None, headless=None, delay=15):
    print(f"\n{'='*60}\nBATCH v5.0: {count} accounts\n{'='*60}\n")
    results = []
    for i in range(count):
        print(f"\n--- {i+1}/{count} ---")
        if i>0:
            ok,msg = TelemetryManager.reset_fp(); print(f"  FP: {msg}")
            time.sleep(random.uniform(2,5))
        results.append(register_one(engine=engine,headless=headless))
        if i<count-1: d=delay+random.uniform(-3,5); print(f"\n[*] Wait {d:.0f}s..."); time.sleep(max(5,d))
    ok = sum(1 for r in results if r); print(f"\n{'='*60}\nBATCH: {ok}/{count} OK\n{'='*60}")
    return results

# === CLI ===
def main():
    if len(sys.argv)<2: print(__doc__); return
    cmd = sys.argv[1].lower()

    if cmd == "register":
        count=1; engine=None; headless=None; i=2
        while i<len(sys.argv):
            if sys.argv[i]=="--count" and i+1<len(sys.argv): count=int(sys.argv[i+1]); i+=2
            elif sys.argv[i]=="--engine" and i+1<len(sys.argv): engine=sys.argv[i+1].lower(); i+=2
            elif sys.argv[i]=="--visible": headless=False; i+=1
            elif sys.argv[i]=="--headless": headless=True; i+=1
            else: i+=1
        if count==1: register_one(engine=engine,headless=headless)
        else: batch_register(count=count,engine=engine,headless=headless)

    elif cmd == "status":
        pool=AccountPool(); s=pool.summary()
        print(f"{'='*60}\nFARM v5.0 STATUS\n{'='*60}")
        print(f"Accounts: {s['total']} | Credits: {s['remaining']}/{s['total_credits']}")
        print(f"Status: {s['by_status']}")
        print(f"Engines: {detect_engines()}")
        print(f"turnstilePatch: {'READY' if TURNSTILE_PATCH_DIR.exists() else 'MISSING'}")
        for a in pool.accounts:
            r=a.get('credits_total',0)-a.get('credits_used',0)
            print(f"  {a['email'][:35]:35}|{a['status']:20}|{r:4}cr|{a.get('engine','?')[:8]}")

    elif cmd == "switch":
        pool=AccountPool(); best=pool.get_best()
        if not best: print("[-] No accounts"); return
        e=best["email"]; r=best.get('credits_total',0)-best.get('credits_used',0)
        print(f"[*] Best: {e} ({r}cr)")
        TelemetryManager.reset_fp(); TelemetryManager.clear_auth(); TelemetryManager.inject_plan()
        pool.update(e,status="activating")
        print(f"\n[!] Restart Windsurf, login:\n    Email: {e}\n    Pass: {best['password']}")

    elif cmd == "activate" and len(sys.argv)>=3:
        pool=AccountPool(); a=pool.find(sys.argv[2])
        if not a: print(f"Not found: {sys.argv[2]}"); return
        TelemetryManager.reset_fp(); TelemetryManager.clear_auth(); TelemetryManager.inject_plan()
        pool.update(a["email"],status="activating")
        print(f"[!] Restart Windsurf, login:\n    Email: {a['email']}\n    Pass: {a['password']}")

    elif cmd == "reset-fingerprint":
        ok,m = TelemetryManager.reset_fp(); print(f"FP: {m}")
        ok2,m2 = TelemetryManager.clear_auth(); print(f"Auth: {m2}")
        ok3,m3 = TelemetryManager.inject_plan(); print(f"Plan: {m3}")

    elif cmd == "test-email":
        for PC in [GuerrillaMailProvider,MailTmProvider]:
            print(f"\n{PC.NAME}...")
            try:
                p=PC(); inbox=p.create_inbox(); print(f"  OK: {inbox['address']}")
            except Exception as e: print(f"  FAIL: {e}")

    elif cmd == "audit":
        eng = detect_engines()
        print(f"{'='*60}\nAUDIT v5.0\n{'='*60}")
        for e in ["camoufox","drission","playwright"]:
            print(f"  {e:12}: {'READY' if e in eng else 'N/A'}")
        print(f"  turnstilePatch: {'READY' if TURNSTILE_PATCH_DIR.exists() else 'MISSING'}")
        print(f"  Proxy: {get_proxy()}")
        s = AccountPool().summary()
        print(f"  Pool: {s['total']}accts {s['remaining']}cr")
        print(f"\n  Credit Table:")
        for m,c in sorted(CREDIT_TABLE.items(),key=lambda x:x[1]):
            cost = "FREE" if c==0 else f"{c}x"
            print(f"    {m:25} {cost:8} {'UNLIMITED' if c==0 else f'{int(100/c)}prompts/100cr'}")

    elif cmd == "deep-report":
        rp = FARM_DIR/"WINDSURF_FARM_V5_DEEP_REPORT.md"
        eng = detect_engines(); s = AccountPool().summary()
        lines = [
            f"# Windsurf Farm v5.0 深度逆向研究报告",
            f"\n> {datetime.now():%Y-%m-%d %H:%M} | 引擎:{eng} | {s['total']}账号 {s['remaining']}积分\n",
            "## 核心架构", "```",
            "Camoufox(Firefox C++反检测,~90%) → DrissionPage(Chrome+turnstilePatch,~85%) → Playwright(JS注入,~60%)",
            "```\n",
            "## 积分系统 (2026-03)",
            "| Plan | 积分 | 0x模型(∞) | GPT-4.1(0.25x) | Claude(1x) |",
            "|------|------|-----------|----------------|------------|",
            "| Free | 25/月 | SWE+Gemini无限 | 100次/月 | 25次/月 |",
            "| Trial | 100/14天 | SWE+Gemini无限 | 400次 | 100次 |",
            "| Pro | 500/月 | SWE+Gemini无限 | 2000次/月 | 500次/月 |\n",
            "## Turnstile方案矩阵",
            "| 方案 | 成本 | 成功率 | 全自动 |",
            "|------|------|--------|--------|",
            "| Camoufox+humanize | 免费 | ~90%+ | ✅ |",
            "| turnstilePatch+DrissionPage | 免费 | ~85% | ✅ |",
            "| CapSolver API | $1.45/1K | ~99% | ✅ |",
            "| Playwright+stealth | 免费 | ~60% | ✅ |\n",
            f"## 系统状态",
            f"- 引擎: {eng}",
            f"- turnstilePatch: {'READY' if TURNSTILE_PATCH_DIR.exists() else 'MISSING'}",
            f"- 账号池: {s['total']}账号 {s['remaining']}积分",
        ]
        with open(rp,'w',encoding='utf-8') as f: f.write('\n'.join(lines))
        print(f"[+] Report: {rp}")

    else: print(f"Unknown: {cmd}\nCommands: register|status|switch|activate|reset-fingerprint|test-email|audit|deep-report")

if __name__ == "__main__":
    main()
