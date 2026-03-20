"""验证已有账号池中untested账号的登录可用性"""
import json, time, sys

ACCOUNTS_FILE = "_farm_accounts.json"

with open(ACCOUNTS_FILE, 'r', encoding='utf-8') as f:
    accounts = json.load(f)

untested = [a for a in accounts if a.get("status") == "untested"]
print(f"=== Account Pool Validation ===")
print(f"Total: {len(accounts)} | Untested: {len(untested)}")

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Playwright not installed")
    sys.exit(1)

results = []
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, channel="msedge")
    
    for i, acct in enumerate(untested[:3]):  # Test first 3 to save time
        email = acct["email"]
        password = acct["password"]
        print(f"\n--- [{i+1}/{min(3,len(untested))}] Testing: {email} ---")
        
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = context.new_page()
        
        try:
            page.goto("https://windsurf.com/account/login", wait_until="networkidle", timeout=20000)
            time.sleep(2)
            
            # Fill login form
            email_field = page.get_by_placeholder("Enter your email address")
            if email_field.count() > 0:
                email_field.fill(email)
                time.sleep(0.5)
            
            # Look for Continue/Sign in button
            continue_btn = page.locator('button:has-text("Continue"), button:has-text("Sign in"), button:has-text("Log in")')
            if continue_btn.count() > 0:
                continue_btn.first.click()
                time.sleep(3)
            
            # Check for password field
            pw_field = page.locator('input[type="password"]')
            if pw_field.count() > 0:
                pw_field.first.fill(password)
                time.sleep(0.5)
                
                sign_in = page.locator('button:has-text("Sign in"), button:has-text("Log in"), button:has-text("Continue")')
                if sign_in.count() > 0:
                    sign_in.first.click()
                    time.sleep(4)
            
            # Check result
            final_url = page.url
            body = page.inner_text("body")[:500]
            
            if "dashboard" in final_url or "welcome" in body.lower() or "credits" in body.lower():
                status = "ACTIVE"
            elif "verify" in body.lower() or "turnstile" in body.lower():
                status = "CAPTCHA_BLOCKED"
            elif "invalid" in body.lower() or "incorrect" in body.lower():
                status = "INVALID_CREDENTIALS"
            elif "not found" in body.lower() or "no account" in body.lower():
                status = "NOT_REGISTERED"
            else:
                status = "UNKNOWN"
                page.screenshot(path=f"_login_test_{i}.png")
            
            print(f"  URL: {final_url}")
            print(f"  Status: {status}")
            print(f"  Body: {body[:200]}")
            results.append({"email": email, "status": status, "url": final_url})
            
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({"email": email, "status": "ERROR", "error": str(e)})
        
        context.close()
        time.sleep(2)
    
    browser.close()

print(f"\n=== RESULTS ===")
for r in results:
    print(f"  {r['email']}: {r['status']}")

with open("_account_validation_results.json", "w") as f:
    json.dump(results, f, indent=2)
