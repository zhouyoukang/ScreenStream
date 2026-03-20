"""E2E注册流程测试 — 验证完整Pipeline可行性"""
import sys, json, time
sys.path.insert(0, '.')
from windsurf_farm import (
    GuerrillaMailProvider, TelemetryManager, AccountPool,
    _extract_verification_link, _extract_verification_code,
    _ps_http, PROXY_URL, detect_proxy
)

PROXY = detect_proxy()
print(f"[*] Proxy: {PROXY}")

# Step 1: 创建GuerrillaMail临时邮箱
print("\n=== Step 1: Create GuerrillaMail Inbox ===")
g = GuerrillaMailProvider()
inbox = g.create_inbox()
email = inbox["address"]
sid = inbox["mail_token"]
print(f"  Email: {email}")
print(f"  SID: {sid[:30]}...")

# Step 2: 检查Playwright可用性
print("\n=== Step 2: Check Playwright ===")
try:
    from playwright.sync_api import sync_playwright
    print("  Playwright: AVAILABLE")
    pw_available = True
except ImportError:
    print("  Playwright: NOT INSTALLED")
    print("  Run: pip install playwright && playwright install msedge")
    pw_available = False

# Step 3: 检查当前设备指纹
print("\n=== Step 3: Current Device State ===")
fp = TelemetryManager.get_current_fingerprint()
for k, v in fp.items():
    print(f"  {k}: {str(v)[:24]}...")
plan = TelemetryManager.get_current_plan()
if plan:
    usage = plan.get("usage", {})
    print(f"  Plan: {plan.get('planName','?')}")
    print(f"  Remaining: {usage.get('remainingMessages','?')}")
    print(f"  Grace: {plan.get('gracePeriodStatus','?')}")

# Step 4: 账号池状态
print("\n=== Step 4: Account Pool ===")
pool = AccountPool()
summary = pool.summary()
print(f"  Total: {summary['total_accounts']}")
print(f"  Credits: {summary['remaining_credits']}/{summary['total_credits']}")
print(f"  Status: {summary['by_status']}")

# Step 5: 尝试Playwright注册 (如果可用)
if pw_available:
    print("\n=== Step 5: Playwright Registration Test ===")
    import random, string
    first_names = ["Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley"]
    last_names = ["Anderson", "Brooks", "Carter", "Davis", "Edwards"]
    first_name = random.choice(first_names)
    last_name = random.choice(last_names)
    ws_password = ''.join(random.choices(string.ascii_letters + string.digits + "!@#", k=14))
    
    print(f"  Name: {first_name} {last_name}")
    print(f"  Email: {email}")
    print(f"  Password: {ws_password}")
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                channel="msedge",
                args=["--disable-blink-features=AutomationControlled"],
            )
            context = browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                proxy={"server": PROXY} if PROXY else None,
            )
            page = context.new_page()
            
            print("  [*] Navigating to register page...")
            page.goto("https://windsurf.com/account/register", wait_until="networkidle", timeout=30000)
            time.sleep(2)
            
            print("  [*] Filling form...")
            page.get_by_placeholder('Your first name').fill(first_name)
            time.sleep(0.5)
            page.get_by_placeholder('Your last name').fill(last_name)
            time.sleep(0.5)
            page.get_by_placeholder('Enter your email address').fill(email)
            time.sleep(0.5)
            
            # Check terms
            checkbox = page.locator('input[type="checkbox"]')
            if checkbox.count() > 0 and not checkbox.first.is_checked():
                checkbox.first.check()
            time.sleep(1)
            
            # Screenshot before clicking Continue
            page.screenshot(path="_e2e_before_continue.png")
            print("  [*] Screenshot: _e2e_before_continue.png")
            
            # Click Continue
            continue_btn = page.locator('button:has-text("Continue")')
            if continue_btn.count() > 0:
                is_disabled = continue_btn.first.get_attribute("disabled")
                print(f"  [*] Continue button disabled={is_disabled}")
                if not is_disabled:
                    continue_btn.first.click()
                    time.sleep(4)
                else:
                    print("  [!] Continue button is disabled - form may need additional input")
            
            # Screenshot after clicking Continue
            page.screenshot(path="_e2e_after_continue.png")
            print("  [*] Screenshot: _e2e_after_continue.png")
            
            # Check page content for next step indicators
            body_text = page.inner_text("body")
            
            # Detect password fields
            pw_fields = page.locator('input[type="password"]')
            pw_count = pw_fields.count()
            print(f"  [*] Password fields found: {pw_count}")
            
            if pw_count > 0:
                print("  [*] Password step detected! Filling password...")
                pw_fields.first.fill(ws_password)
                time.sleep(0.5)
                # Look for confirm password
                confirm_pw = page.locator('input[type="password"]').nth(1) if pw_count > 1 else None
                if confirm_pw:
                    try:
                        confirm_pw.fill(ws_password)
                        time.sleep(0.5)
                    except Exception:
                        pass
                
                # Submit
                submit = page.locator('button[type="submit"], button:has-text("Sign up"), button:has-text("Create"), button:has-text("Continue")')
                if submit.count() > 0:
                    submit.first.click()
                    time.sleep(4)
                
                page.screenshot(path="_e2e_after_password.png")
                print("  [*] Screenshot: _e2e_after_password.png")
            
            # Final page analysis
            final_url = page.url
            final_text = page.inner_text("body")[:1000]
            print(f"\n  [*] Final URL: {final_url}")
            
            # Detect result
            keywords = {
                "success": ["verify", "check your email", "confirmation", "sent", "code", "welcome", "dashboard"],
                "error": ["error", "already", "invalid", "blocked", "captcha", "rate limit"],
                "password": ["password", "create password", "set password"],
            }
            
            for category, kws in keywords.items():
                found = [kw for kw in kws if kw in final_text.lower()]
                if found:
                    print(f"  [{category.upper()}] Keywords: {found}")
            
            page.screenshot(path="_e2e_final.png")
            print(f"  [*] Final screenshot: _e2e_final.png")
            print(f"  [*] Body preview: {final_text[:300]}")
            
            browser.close()
            
    except Exception as e:
        print(f"  [ERROR] {e}")
        import traceback
        traceback.print_exc()

# Step 6: 检查GuerrillaMail收件箱 (即使注册未完成也检查)
print("\n=== Step 6: Check Inbox ===")
time.sleep(5)
msgs = g.get_messages()
print(f"  Messages: {len(msgs)}")
for msg in msgs[:5]:
    subj = msg.get("mail_subject", msg.get("subject", "no subject"))
    frm = msg.get("mail_from", msg.get("from", "unknown"))
    print(f"  - [{frm}] {subj}")

# Summary
print("\n" + "=" * 60)
print("E2E REGISTRATION TEST SUMMARY")
print("=" * 60)
print(f"Email created: {email}")
print(f"Playwright: {'AVAILABLE' if pw_available else 'NOT INSTALLED'}")
print(f"Registration attempted: {'YES' if pw_available else 'NO (install playwright)'}")
print(f"Messages received: {len(msgs)}")
print(f"Current plan: {plan.get('planName','?') if plan else 'unknown'}")
print(f"Remaining credits: {usage.get('remainingMessages','?') if plan else 'unknown'}")
