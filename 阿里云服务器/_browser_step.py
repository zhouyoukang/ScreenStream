"""阿里云控制台浏览器自动化 — 逐步执行"""
import sys, json, time, os
from playwright.sync_api import sync_playwright

SCREENSHOTS_DIR = os.path.join(os.path.dirname(__file__), "_screenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

STATE_FILE = os.path.join(os.path.dirname(__file__), "_browser_state.json")

def screenshot(page, name):
    path = os.path.join(SCREENSHOTS_DIR, f"{name}.png")
    page.screenshot(path=path, full_page=False)
    return path

def get_page_info(page):
    return {
        "url": page.url,
        "title": page.title(),
    }

def step_explore(page):
    """Step 1: 打开阿里云轻量控制台，观察状态"""
    page.goto("https://swas.console.aliyun.com/", wait_until="networkidle", timeout=30000)
    time.sleep(2)
    info = get_page_info(page)
    ss = screenshot(page, "01_initial")
    # 获取页面文本摘要
    text = page.inner_text("body")[:2000]
    return {"info": info, "screenshot": ss, "text_preview": text}

def step_login_check(page):
    """检查是否在登录页"""
    url = page.url
    if "login" in url or "signin" in url or "passport" in url:
        return {"status": "need_login", "url": url}
    else:
        return {"status": "logged_in", "url": url}

def main():
    step = sys.argv[1] if len(sys.argv) > 1 else "explore"

    with sync_playwright() as p:
        # 尝试用用户Chrome的cookies（如果存在用户数据目录）
        chrome_user_data = os.path.expanduser("~") + r"\AppData\Local\Google\Chrome\User Data"

        # 绕过系统代理直连（阿里云是国内站点，Clash未运行）
        browser = p.chromium.launch(
            headless=True,
            args=["--no-proxy-server"]
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="zh-CN",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            if step == "explore":
                result = step_explore(page)
                login_status = step_login_check(page)
                result["login"] = login_status
                print(json.dumps(result, ensure_ascii=False, indent=2))
            elif step == "screenshot":
                page.goto(sys.argv[2] if len(sys.argv) > 2 else "https://swas.console.aliyun.com/", timeout=30000)
                time.sleep(2)
                ss = screenshot(page, "manual")
                print(json.dumps({"screenshot": ss, "info": get_page_info(page)}, ensure_ascii=False))
        finally:
            context.close()
            browser.close()

if __name__ == "__main__":
    main()
