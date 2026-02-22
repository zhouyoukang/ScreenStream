"""Selenium精准操作腾讯滑块验证码"""
import time
import random
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains

DEBUG_PORT = 9333
SCREENSHOT_DIR = "E:/github/AIOT/ScreenStream_v2"

def human_drag(driver, slider, distance):
    """模拟人类拖拽：加速→匀速→减速+微抖动"""
    actions = ActionChains(driver)
    actions.click_and_hold(slider)
    actions.pause(0.1 + random.uniform(0, 0.1))
    
    moved = 0
    steps = random.randint(18, 25)
    for i in range(1, steps + 1):
        progress = i / steps
        # 先快后慢的缓动曲线
        eased = 1 - (1 - progress) ** 3
        target_x = int(distance * eased)
        delta = target_x - moved
        if delta <= 0:
            delta = 1
        y_jitter = random.randint(-2, 2)
        actions.move_by_offset(delta, y_jitter)
        actions.pause(random.uniform(0.005, 0.025))
        moved = target_x
    
    # 最后微调
    actions.pause(0.05 + random.uniform(0, 0.1))
    actions.release()
    actions.perform()

def main():
    opts = Options()
    opts.add_experimental_option("debuggerAddress", f"127.0.0.1:{DEBUG_PORT}")
    driver = webdriver.Chrome(options=opts)
    
    print(f"URL: {driver.current_url}")
    
    # 找到验证码iframe
    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    captcha_iframe = None
    for iframe in iframes:
        src = iframe.get_attribute("src") or ""
        if "captcha" in src:
            captcha_iframe = iframe
            print(f"Found captcha iframe: {src[:80]}")
            break
    
    if not captcha_iframe:
        print("ERROR: No captcha iframe found")
        driver.save_screenshot(f"{SCREENSHOT_DIR}/captcha_debug.png")
        return
    
    # 切入iframe
    driver.switch_to.frame(captcha_iframe)
    time.sleep(0.5)
    
    # 打印所有元素信息帮助调试
    print("\n--- Elements in captcha iframe ---")
    all_els = driver.find_elements(By.CSS_SELECTOR, "*")
    interactive = []
    for el in all_els:
        tag = el.tag_name
        cls = el.get_attribute("class") or ""
        eid = el.get_attribute("id") or ""
        if cls or eid:
            size = el.size
            loc = el.location
            if size['width'] > 0 and size['height'] > 0:
                info = f"  <{tag}> id='{eid}' class='{cls}' loc={loc} size={size}"
                if any(k in cls.lower() or k in eid.lower() for k in ['drag', 'slide', 'slider', 'thumb', 'track', 'btn']):
                    info += " *** SLIDER?"
                    interactive.append((el, cls, eid, loc, size))
                print(info)
    
    # 尝试多种选择器找滑块
    slider = None
    selectors = [
        "img[alt='slider']",
        "#tcaptcha_drag_thumb",
        ".tc-drag-thumb", 
        "[class*='drag'][class*='thumb']",
        "[class*='slide'][class*='btn']",
        "[class*='slider']",
        "#slide_btn",
    ]
    
    for sel in selectors:
        try:
            els = driver.find_elements(By.CSS_SELECTOR, sel)
            if els:
                slider = els[0]
                print(f"\nFound slider with: {sel}")
                print(f"  Location: {slider.location}, Size: {slider.size}")
                break
        except:
            pass
    
    if not slider and interactive:
        slider = interactive[0][0]
        print(f"\nUsing first interactive element as slider")
    
    if not slider:
        print("\nERROR: Cannot find slider element")
        # 截图iframe内容
        driver.save_screenshot(f"{SCREENSHOT_DIR}/captcha_iframe_debug.png")
        driver.switch_to.default_content()
        return
    
    # 获取滑块轨道宽度（估算拖拽距离）
    # 腾讯验证码轨道通常约280px宽，滑块约40px宽
    # 拼图缺口通常在50-70%位置
    track_width = 280  # 默认估算
    
    # 尝试找轨道元素获取真实宽度
    track_selectors = ["#tcaptcha_drag_track", ".tc-drag-track", "[class*='drag'][class*='track']", "[class*='slide'][class*='track']"]
    for sel in track_selectors:
        try:
            tracks = driver.find_elements(By.CSS_SELECTOR, sel)
            if tracks:
                track_width = tracks[0].size['width']
                print(f"Track width: {track_width}px (from {sel})")
                break
        except:
            pass
    
    # 多次尝试不同距离
    distances_to_try = [
        int(track_width * 0.55),
        int(track_width * 0.45),
        int(track_width * 0.65),
    ]
    
    for attempt, dist in enumerate(distances_to_try, 1):
        print(f"\n--- Attempt {attempt}: drag {dist}px ---")
        
        human_drag(driver, slider, dist)
        time.sleep(2)
        
        driver.switch_to.default_content()
        driver.save_screenshot(f"{SCREENSHOT_DIR}/captcha_attempt{attempt}.png")
        
        # 检查验证码是否还在
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        captcha_still = any("captcha" in (f.get_attribute("src") or "") for f in iframes)
        
        if not captcha_still:
            print(f"SUCCESS! Captcha solved on attempt {attempt}")
            return
        
        print(f"Captcha still present, trying next distance...")
        
        # 重新切入iframe
        for iframe in iframes:
            if "captcha" in (iframe.get_attribute("src") or ""):
                driver.switch_to.frame(iframe)
                time.sleep(1)
                # 点刷新按钮获取新验证码
                try:
                    refresh = driver.find_element(By.CSS_SELECTOR, "[class*='refresh'], button:last-child")
                    refresh.click()
                    time.sleep(2)
                except:
                    pass
                # 重新找滑块
                for sel in selectors:
                    try:
                        els = driver.find_elements(By.CSS_SELECTOR, sel)
                        if els:
                            slider = els[0]
                            break
                    except:
                        pass
                break
    
    print("\nAll attempts exhausted. Manual captcha solving needed.")
    driver.switch_to.default_content()

if __name__ == "__main__":
    main()
