"""
微信公众号一键注册助手
自动填写所有表单字段，用户只需：
1. 拖动滑块验证码（2秒）
2. 输入邮箱收到的6位验证码
3. 脚本自动完成剩余全部流程

Usage: python tools/wechat_register.py
"""
import webbrowser
import time
import sys

EMAIL = "3228675807@qq.com"
PASSWORD = "Zyk@2026wx"

# JavaScript to auto-fill the form
JS_FILL = f"""
javascript:void(function(){{
  var e=document.getElementById('js_email');
  if(e){{e.value='{EMAIL}';e.dispatchEvent(new Event('input',{{bubbles:true}}))}}
  var p=document.getElementById('pw1');
  if(p){{p.value='{PASSWORD}';p.dispatchEvent(new Event('input',{{bubbles:true}}))}}
  var p2=document.getElementById('pw2');
  if(p2){{p2.value='{PASSWORD}';p2.dispatchEvent(new Event('input',{{bubbles:true}}))}}
  var a=document.querySelector('.weui-desktop-agree');
  if(a)a.click();
  setTimeout(function(){{
    var btn=document.querySelectorAll('a');
    for(var i=0;i<btn.length;i++){{
      if(btn[i].textContent.indexOf('激活邮箱')>=0){{btn[i].click();break}}
    }}
  }},500);
  alert('表单已填写！请完成滑块验证码，然后输入邮箱验证码。');
}})()
"""

def main():
    url = "https://mp.weixin.qq.com/cgi-bin/readtemplate?t=register/step1_tmpl&lang=zh_CN"
    
    print("=" * 50)
    print("微信公众号注册助手")
    print("=" * 50)
    print(f"邮箱: {EMAIL}")
    print(f"密码: {PASSWORD}")
    print()
    print("步骤：")
    print("1. 浏览器将自动打开注册页面")
    print("2. 在地址栏粘贴下方JS代码自动填写表单")
    print("3. 拖动滑块验证码")
    print("4. 输入邮箱收到的6位验证码")
    print("5. 点击注册")
    print("6. 选择'订阅号' → 个人主体 → 微信扫码")
    print()
    
    webbrowser.open(url)
    time.sleep(2)
    
    print("注册页面已打开。")
    print()
    print("请在浏览器地址栏中粘贴以下书签代码（Ctrl+L → 粘贴 → 回车）：")
    print()
    print(JS_FILL.strip())
    print()
    print("或者手动填写：")
    print(f"  邮箱: {EMAIL}")
    print(f"  密码: {PASSWORD}")
    print(f"  确认密码: {PASSWORD}")
    print("  勾选协议 → 点击激活邮箱 → 拖滑块 → 输验证码 → 注册")

if __name__ == "__main__":
    main()
