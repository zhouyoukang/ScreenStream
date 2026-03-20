"""E2E注册诊断: 每步截图+页面内容dump, 精确定位失败点"""
import time, random, os, json, string
from pathlib import Path
from datetime import datetime

FARM_DIR = Path(__file__).parent.parent
DEBUG_DIR = FARM_DIR / "test" / "_debug_screenshots"
os.makedirs(DEBUG_DIR, exist_ok=True)

WINDSURF_REGISTER_URL = "https://windsurf.com/account/register"
TURNSTILE_PATCH_DIR = FARM_DIR / "turnstilePatch"

def save_debug(page, step_name, idx):
    """保存截图+页面文本"""
    ts = datetime.now().strftime("%H%M%S")
    ss_path = str(DEBUG_DIR / f"{idx:02d}_{step_name}_{ts}.png")
    txt_path = str(DEBUG_DIR / f"{idx:02d}_{step_name}_{ts}.txt")
    try:
        page.get_screenshot(path=ss_path)
        print(f"  [screenshot] {ss_path}")
    except Exception as e:
        print(f"  [screenshot FAIL] {e}")
    try:
        body = page.html[:3000] if hasattr(page, 'html') else ""
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(body)
    except: pass

def main():
    try:
        from DrissionPage import ChromiumOptions, ChromiumPage
    except ImportError:
        print("pip install DrissionPage"); return

    print("=" * 60)
    print("E2E REGISTER DEBUG (DrissionPage + turnstilePatch)")
    print(f"Screenshots: {DEBUG_DIR}")
    print("=" * 60)

    # 用固定测试邮箱(不会真验证)
    email = f"test{random.randint(10000,99999)}@guerrillamailblock.com"
    fn, ln = "TestUser", "Debug"
    pw = "Abc123!@#debug"
    print(f"\nEmail: {email}")
    print(f"Name: {fn} {ln}")

    co = ChromiumOptions()
    for cp in [os.path.join(os.environ.get('PROGRAMFILES',''),'Google','Chrome','Application','chrome.exe'),
               os.path.join(os.environ.get('LOCALAPPDATA',''),'Google','Chrome','Application','chrome.exe')]:
        if os.path.exists(cp): co.set_browser_path(cp); break
    co.set_argument("--incognito")
    co.auto_port()
    co.headless(False)
    ext = str(TURNSTILE_PATCH_DIR)
    if os.path.exists(ext):
        co.set_argument("--allow-extensions-in-incognito")
        co.add_extension(ext)
        print(f"[+] turnstilePatch loaded from {ext}")

    page = ChromiumPage(co)

    try:
        # Step 0: Navigate
        print("\n[Step 0] Navigating...")
        page.get(WINDSURF_REGISTER_URL)
        time.sleep(3)
        save_debug(page, "00_loaded", 0)

        # 检查页面内容
        body = page.html.lower() if hasattr(page, 'html') else ""
        print(f"  Page title: {page.title if hasattr(page,'title') else '?'}")
        has_form = 'first_name' in body or 'first name' in body
        has_login = 'sign in' in body or 'log in' in body
        has_register = 'create' in body or 'sign up' in body or 'register' in body
        print(f"  Has registration form: {has_form}")
        print(f"  Has login: {has_login}")
        print(f"  Has register/signup: {has_register}")

        # Step 1: Fill first name
        print("\n[Step 1] Filling first name...")
        fn_el = page.ele('@name=first_name') or page.ele('@placeholder=Your first name') or page.ele('tag:input@type=text')
        if fn_el:
            fn_el.input(fn)
            print(f"  [+] First name filled: {fn}")
        else:
            print("  [-] First name input NOT FOUND")
            # 尝试列出所有input
            inputs = page.eles('tag:input')
            print(f"  Found {len(inputs)} inputs:")
            for inp in inputs[:10]:
                print(f"    type={inp.attr('type')} name={inp.attr('name')} placeholder={inp.attr('placeholder')}")
        time.sleep(0.5)

        # Step 2: Fill last name
        print("\n[Step 2] Filling last name...")
        ln_el = page.ele('@name=last_name') or page.ele('@placeholder=Your last name')
        if ln_el:
            ln_el.input(ln)
            print(f"  [+] Last name filled: {ln}")
        else:
            print("  [-] Last name input NOT FOUND")
        time.sleep(0.5)

        # Step 3: Fill email
        print("\n[Step 3] Filling email...")
        em_el = page.ele('@name=email') or page.ele('@placeholder=Enter your email address') or page.ele('@type=email')
        if em_el:
            em_el.input(email)
            print(f"  [+] Email filled: {email}")
        else:
            print("  [-] Email input NOT FOUND")
        time.sleep(0.5)

        # Step 4: Checkbox
        print("\n[Step 4] Terms checkbox...")
        cb = page.ele('tag:input@type=checkbox')
        if cb:
            if not cb.attr('checked'):
                cb.click()
                print("  [+] Checkbox checked")
            else:
                print("  [+] Already checked")
        else:
            print("  [-] Checkbox NOT FOUND")
        time.sleep(1)
        save_debug(page, "04_form_filled", 4)

        # Step 5: Click Continue
        print("\n[Step 5] Clicking Continue...")
        btns = page.eles('tag:button')
        print(f"  Found {len(btns)} buttons:")
        for b in btns[:8]:
            txt = b.text[:50] if hasattr(b, 'text') else '?'
            disabled = b.attr('disabled')
            print(f"    [{txt}] disabled={disabled}")

        continue_btn = page.ele('tag:button@text():Continue')
        if continue_btn:
            disabled = continue_btn.attr('disabled')
            print(f"  Continue button found, disabled={disabled}")
            if not disabled:
                continue_btn.click()
                print("  [+] Clicked Continue")
            else:
                print("  [-] Continue is DISABLED - form validation failed?")
        else:
            # 尝试其他按钮名称
            for txt in ['Sign up', 'Create account', 'Submit', 'Next']:
                alt = page.ele(f'tag:button@text():{txt}')
                if alt:
                    alt.click()
                    print(f"  [+] Clicked alt button: {txt}")
                    break
            else:
                print("  [-] No clickable button found!")
        
        time.sleep(4)
        save_debug(page, "05_after_continue", 5)

        # Step 6: Check what happened
        print("\n[Step 6] Checking page state after Continue...")
        body2 = page.html.lower() if hasattr(page, 'html') else ""
        url2 = page.url if hasattr(page, 'url') else "?"
        print(f"  URL: {url2}")
        has_password = 'password' in body2 or 'create password' in body2
        has_turnstile = 'challenges.cloudflare.com' in body2
        has_verify = 'verify' in body2 or 'check your email' in body2
        has_error = 'error' in body2 or 'invalid' in body2 or 'already exists' in body2
        print(f"  Has password field: {has_password}")
        print(f"  Has Turnstile: {has_turnstile}")
        print(f"  Has verify msg: {has_verify}")
        print(f"  Has error: {has_error}")

        # Step 7: Wait for Turnstile if present
        if has_turnstile:
            print("\n[Step 7] Turnstile detected, waiting...")
            for w in range(20):
                time.sleep(1)
                b3 = page.html.lower() if hasattr(page, 'html') else ""
                if 'password' in b3 or 'create password' in b3:
                    print(f"  [+] Turnstile passed after {w+1}s!")
                    break
                btn2 = page.ele('tag:button@text():Continue', timeout=1)
                if btn2 and not btn2.attr('disabled'):
                    btn2.click()
                    print(f"  [+] Clicked Continue after {w+1}s")
                    time.sleep(2)
                    break
            save_debug(page, "07_after_turnstile", 7)
        
        # Step 8: Fill password if visible
        body3 = page.html.lower() if hasattr(page, 'html') else ""
        if 'password' in body3:
            print("\n[Step 8] Password page detected!")
            pw_els = page.eles('@type=password')
            print(f"  Found {len(pw_els)} password inputs")
            if len(pw_els) >= 1:
                pw_els[0].input(pw)
                print("  [+] Password filled")
                time.sleep(0.5)
            if len(pw_els) >= 2:
                pw_els[1].input(pw)
                print("  [+] Confirm password filled")
                time.sleep(0.5)
            
            submit = page.ele('tag:button@type=submit') or page.ele('tag:button@text():Continue') or page.ele('tag:button@text():Sign up')
            if submit:
                submit.click()
                print("  [+] Submitted password")
                time.sleep(4)
            save_debug(page, "08_after_password", 8)
            
            # Step 9: Second Turnstile
            body4 = page.html.lower() if hasattr(page, 'html') else ""
            if 'challenges.cloudflare.com' in body4:
                print("\n[Step 9] Second Turnstile...")
                for w2 in range(20):
                    time.sleep(1)
                    b5 = page.html.lower() if hasattr(page, 'html') else ""
                    if 'verify' in b5 or 'check your email' in b5 or 'welcome' in b5:
                        print(f"  [+] Second Turnstile passed after {w2+1}s!")
                        break
                save_debug(page, "09_after_turnstile2", 9)
        
        # Final state
        print("\n[FINAL] Page state:")
        final_body = page.html[:2000] if hasattr(page, 'html') else ""
        final_url = page.url if hasattr(page, 'url') else "?"
        print(f"  URL: {final_url}")
        print(f"  Body preview: {final_body[:500]}")
        save_debug(page, "99_final", 99)

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback; traceback.print_exc()
        save_debug(page, "XX_error", 99)
    finally:
        input("\n[Press Enter to close browser]")
        page.quit()

if __name__ == "__main__":
    main()
