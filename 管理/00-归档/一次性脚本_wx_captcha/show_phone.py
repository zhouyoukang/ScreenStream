"""在主屏Chrome中打开手机投屏 + 继续注册流程"""
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

opts = Options()
opts.add_experimental_option("debuggerAddress", "127.0.0.1:9333")
driver = webdriver.Chrome(options=opts)

print(f"当前页: {driver.current_url}")
print(f"标签数: {len(driver.window_handles)}")

# 列出所有标签
for i, h in enumerate(driver.window_handles):
    driver.switch_to.window(h)
    print(f"  Tab {i}: {driver.title[:50]} | {driver.current_url[:60]}")

# 找到注册页标签
reg_tab = None
phone_tab = None
for h in driver.window_handles:
    driver.switch_to.window(h)
    if "waregister" in driver.current_url:
        reg_tab = h
    if "8086" in driver.current_url or "localhost:8086" in driver.current_url:
        phone_tab = h

# 如果没有投屏标签，打开一个
if not phone_tab:
    print("\n[1] 打开手机投屏标签...")
    driver.execute_script("window.open('http://localhost:8086', '_blank')")
    time.sleep(3)
    handles = driver.window_handles
    phone_tab = handles[-1]
    driver.switch_to.window(phone_tab)
    print(f"  投屏页: {driver.title} | {driver.current_url}")
    driver.save_screenshot("E:/github/AIOT/ScreenStream_v2/phone_screen.png")
    print("  截图: phone_screen.png")
else:
    print(f"\n[1] 投屏标签已存在")
    driver.switch_to.window(phone_tab)

# 切回注册页
if reg_tab:
    print("\n[2] 切回注册页...")
    driver.switch_to.window(reg_tab)
    print(f"  页面: {driver.title}")
    
    # 检查邮箱是否已填
    try:
        email_input = driver.find_element(By.CSS_SELECTOR, "input[type='email'], input.js_input")
        email_val = email_input.get_attribute("value")
        print(f"  邮箱: {email_val}")
    except Exception as e:
        print(f"  邮箱字段: {e}")
    
    # 检查验证码弹窗是否存在
    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    captcha_exists = any("captcha" in (f.get_attribute("src") or "") for f in iframes)
    print(f"  验证码弹窗: {'存在' if captcha_exists else '不存在'}")
    
    if not captcha_exists:
        # 验证码不存在，可能需要重新点击激活邮箱
        try:
            activate = driver.find_element(By.LINK_TEXT, "激活邮箱")
            if activate.is_displayed():
                print("  '激活邮箱'按钮可见，验证码已关闭或未触发")
                print("  准备重新点击'激活邮箱'...")
                activate.click()
                time.sleep(3)
                
                # 再次检查验证码
                iframes = driver.find_elements(By.TAG_NAME, "iframe")
                captcha_exists = any("captcha" in (f.get_attribute("src") or "") for f in iframes)
                print(f"  点击后验证码: {'出现' if captcha_exists else '未出现'}")
                
                driver.save_screenshot("E:/github/AIOT/ScreenStream_v2/after_activate.png")
        except Exception as e:
            print(f"  激活邮箱按钮: {e}")
    
    if captcha_exists:
        print("\n  ⚠️ 验证码弹窗出现 - 需要手动拖拽滑块")
        print("  请在主屏幕右侧Chrome中拖动滑块完成拼图")

print("\n=== 完成 ===")
print("标签列表:")
for i, h in enumerate(driver.window_handles):
    driver.switch_to.window(h)
    print(f"  Tab {i}: {driver.title[:50]}")
