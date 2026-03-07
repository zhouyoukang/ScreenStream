"""
AI中枢能力测试 — 测试手机上所有AI App作为中枢的能力
=================================================
通过phone_lib逐一打开每个AI App，发送测试问题，读取响应，评估能力。

使用: python tests/ai_hub_test.py [--host 192.168.31.32] [--port 8084]
"""

import sys, os, time, json, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from phone_lib import Phone

# ============================================================
# AI App 注册表
# ============================================================

# === 可用App（已登录/免登录可交互）===
AI_APPS_USABLE = [
    {
        "name": "小布助手",
        "package": "com.heytap.speechassist",
        "type": "assistant",
        "input_method": "tap_bottom",  # 小布输入框在底部，"按住说话"旁的文字输入区
        "input_hints": ["说话", "输入", "发送"],
        "send_hints": ["发送", "➤"],
        "new_chat_hints": [],
        "notes": "OPPO内置，DeepSeek满血版，无需登录",
    },
    {
        "name": "夸克AI",
        "package": "com.quark.browser",
        "type": "browser",
        "input_method": "findclick",
        "input_hints": ["把问题和任务告诉我", "搜索框", "搜索"],
        "send_hints": ["搜索", "发送", "千问"],
        "new_chat_hints": [],
        "ai_entry": "千问",  # 夸克内千问AI入口
        "notes": "已登录，内置通义千问AI",
    },
    {
        "name": "通义千问",
        "package": "com.aliyun.tongyi",
        "type": "chat",
        "input_method": "findclick",
        "input_hints": ["发消息", "说话", "输入", "深度思考"],
        "send_hints": ["发送", "➤", "↑"],
        "new_chat_hints": ["新对话", "+"],
        "notes": "免登录有输入框，可能功能受限",
    },
]

# === 需要登录的App（记录但不测试交互）===
AI_APPS_LOGIN_REQUIRED = [
    {
        "name": "DeepSeek",
        "package": "com.deepseek.chat",
        "type": "chat",
        "login_screen": "微信登录/手机验证码登录/密码登录",
    },
    {
        "name": "Kimi",
        "package": "com.moonshot.kimichat",
        "type": "chat",
        "login_screen": "隐私政策同意页（需滚动到底部同意）",
    },
    {
        "name": "腾讯混元",
        "package": "com.tencent.hunyuan.app.chat",
        "type": "chat",
        "login_screen": "微信登录/QQ登录",
    },
]

AI_APPS = AI_APPS_USABLE  # 默认只测试可用的

TEST_PROMPT = "今天星期几"  # 简短无害的测试问题，所有AI都能秒回

# ============================================================
# 测试引擎
# ============================================================

class AIHubTester:
    def __init__(self, phone: Phone):
        self.p = phone
        self.results = []

    def test_all(self):
        """逐一测试所有AI App"""
        print(f"\n{'='*60}")
        print(f"  AI中枢能力测试 — {len(AI_APPS)} 个AI App")
        print(f"  设备: {self.p.base}")
        print(f"  测试问题: '{TEST_PROMPT}'")
        print(f"{'='*60}\n")

        # 先回到桌面
        self.p.home()
        time.sleep(1)

        for i, app in enumerate(AI_APPS):
            print(f"\n{'─'*50}")
            print(f"[{i+1}/{len(AI_APPS)}] 测试: {app['name']} ({app['package']})")
            print(f"{'─'*50}")
            result = self._test_one(app)
            self.results.append(result)
            # 回桌面准备下一个
            self.p.home()
            time.sleep(1.5)

        self._print_summary()
        return self.results

    def _test_one(self, app: dict) -> dict:
        """测试单个AI App，返回结果字典"""
        result = {
            "name": app["name"],
            "package": app["package"],
            "type": app["type"],
            "steps": {},
            "score": 0,
            "max_score": 5,
        }

        # Step 1: 启动APP
        print(f"  [1/5] 启动 {app['name']}...")
        ok = self._step_launch(app)
        result["steps"]["launch"] = ok
        if not ok:
            print(f"  ❌ 启动失败，跳过")
            return result
        result["score"] += 1
        print(f"  ✅ 启动成功")

        # Step 2: 识别界面（读取屏幕内容）
        print(f"  [2/5] 识别界面...")
        texts, pkg = self.p.read()
        on_target = app["package"].split(".")[-1].lower() in (pkg or "").lower() or app["package"] in (pkg or "")
        result["steps"]["identify"] = on_target
        result["screen_texts"] = texts[:15]
        result["foreground"] = pkg
        if on_target:
            result["score"] += 1
            print(f"  ✅ 在目标APP内 (pkg={pkg})")
        else:
            print(f"  ⚠️ 前台APP: {pkg}，可能有弹窗")
            # 尝试dismiss弹窗
            self.p._dismiss_oppo()
            time.sleep(1)
            pkg = self.p.foreground()
            if app["package"] in (pkg or ""):
                result["score"] += 1
                result["steps"]["identify"] = True
                print(f"  ✅ 弹窗处理后成功进入")

        # Step 3: 找到输入框
        print(f"  [3/5] 寻找输入框...")
        input_found = self._step_find_input(app, texts)
        result["steps"]["find_input"] = input_found
        if input_found:
            result["score"] += 1
            print(f"  ✅ 找到输入框")
        else:
            print(f"  ❌ 未找到输入框")
            return result

        # Step 4: 输入测试问题并发送
        print(f"  [4/5] 输入 '{TEST_PROMPT}' 并发送...")
        sent = self._step_send_prompt(app)
        result["steps"]["send"] = sent
        if sent:
            result["score"] += 1
            print(f"  ✅ 已发送")
        else:
            print(f"  ❌ 发送失败")
            return result

        # Step 5: 等待并读取AI回复
        print(f"  [5/5] 等待AI回复 (最长15秒)...")
        reply = self._step_read_reply(app)
        result["steps"]["reply"] = bool(reply)
        result["ai_reply"] = reply
        if reply:
            result["score"] += 1
            # 截取前100字
            short = reply[:100] + ("..." if len(reply) > 100 else "")
            print(f"  ✅ AI回复: {short}")
        else:
            print(f"  ⚠️ 未检测到明确回复")

        print(f"  📊 得分: {result['score']}/{result['max_score']}")
        return result

    def _dismiss_all_dialogs(self):
        """处理各种弹窗：更新/权限/隐私/引导"""
        dismiss_texts = [
            "取消", "跳过", "以后再说", "关闭", "暂不更新", "稍后",
            "下次再说", "我知道了", "不再提醒", "暂不升级",
            "允许", "始终允许", "确定",  # OPPO权限
        ]
        for text in dismiss_texts:
            r = self.p.click(text)
            if r and r.get("ok"):
                time.sleep(0.5)

    def _step_launch(self, app: dict) -> bool:
        """启动APP"""
        pkg = app["package"]
        try:
            # openapp API（ScreenStream内部处理Intent+启动）
            self.p.post("/openapp", {"packageName": pkg})
            time.sleep(4)
            # 处理弹窗（更新/权限/隐私）
            self._dismiss_all_dialogs()
            time.sleep(1)
            fg = self.p.foreground()
            if pkg in (fg or ""):
                return True
            # 回退: Intent方式
            self.p.intent("android.intent.action.MAIN", package=pkg,
                         categories=["android.intent.category.LAUNCHER"])
            time.sleep(3)
            self._dismiss_all_dialogs()
            time.sleep(1)
            fg = self.p.foreground()
            if pkg in (fg or ""):
                return True
            # 最后回退: monkey
            self.p.monkey_open(pkg, wait_sec=3)
            self._dismiss_all_dialogs()
            time.sleep(1)
            fg = self.p.foreground()
            return pkg in (fg or "")
        except Exception as e:
            print(f"    启动异常: {e}")
            return False

    def _step_find_input(self, app: dict, screen_texts: list) -> bool:
        """找到并聚焦输入框"""
        # 策略0: 小布助手特殊 — 底部有"按住说话"，旁边是文字输入切换
        if app.get("input_method") == "tap_bottom":
            # 小布: 先点击底部输入区域切换到文字模式
            self.p.tap(0.5, 0.95)  # 底部中央
            time.sleep(1)
            # 检查是否出现输入框
            for hint in app["input_hints"]:
                r = self.p.click(hint)
                if r and r.get("ok"):
                    time.sleep(0.5)
                    return True
            # 直接tap输入区域
            self.p.tap(0.4, 0.93)
            time.sleep(0.8)
            return True  # 小布总是有输入区域

        # 策略1: 夸克浏览器 — 先进AI入口
        if app.get("ai_entry"):
            r = self.p.click(app["ai_entry"])
            if r and r.get("ok"):
                time.sleep(2)
                self._dismiss_all_dialogs()
                time.sleep(1)

        # 策略2: 根据hint关键词找输入框
        for hint in app["input_hints"]:
            r = self.p.click(hint)
            if r and r.get("ok"):
                time.sleep(0.8)
                return True

        # 策略3: tap底部输入区域（大多数Chat APP输入框在底部）
        self.p.tap(0.5, 0.92)
        time.sleep(1)
        new_texts, _ = self.p.read()
        if len(new_texts) != len(screen_texts):
            return True

        # 策略4: 处理引导页后重试
        for skip_text in ["跳过", "我知道了", "开始", "同意", "确定", "允许"]:
            self.p.click(skip_text)
            time.sleep(0.5)
        for hint in app["input_hints"][:3]:
            r = self.p.click(hint)
            if r and r.get("ok"):
                time.sleep(0.8)
                return True

        return False

    def _step_send_prompt(self, app: dict) -> bool:
        """输入文本并发送"""
        try:
            # 输入文本
            self.p.post("/text", {"text": TEST_PROMPT})
            time.sleep(0.8)

            # 尝试点击发送按钮
            for hint in app["send_hints"]:
                r = self.p.click(hint)
                if r and r.get("ok"):
                    time.sleep(0.5)
                    return True

            # 回退: 按回车键
            self.p.post("/key", {"keysym": 0xFF0D, "down": True})
            self.p.post("/key", {"keysym": 0xFF0D, "down": False})
            time.sleep(0.5)
            return True
        except Exception as e:
            print(f"    发送异常: {e}")
            return False

    def _step_read_reply(self, app: dict) -> str:
        """等待并读取AI回复"""
        # 记录发送前的文本快照
        pre_texts, _ = self.p.read()
        pre_set = set(pre_texts)

        # 轮询等待新内容出现（AI正在生成回复）
        for wait_round in range(6):  # 最多等15秒
            time.sleep(2.5)
            cur_texts, _ = self.p.read()
            cur_set = set(cur_texts)
            new_texts = cur_set - pre_set

            # 过滤掉太短/无意义的文本
            meaningful = [t for t in new_texts if len(t) > 2
                         and t not in (TEST_PROMPT, "发送", "语音", "更多", "复制", "重试")]

            if meaningful:
                # 找最长的一段作为回复
                reply = max(meaningful, key=len)
                return reply

        # 最后尝试: 读取全部文本找可能的回复
        final_texts, _ = self.p.read()
        # 在包含"星期"或日期的文本中找回复
        for t in final_texts:
            if any(k in t for k in ["星期", "周", "Monday", "Tuesday", "Wednesday",
                                     "Thursday", "Friday", "Saturday", "Sunday",
                                     "一", "二", "三", "四", "五", "六", "日"]):
                if t != TEST_PROMPT and len(t) > 3:
                    return t

        return ""

    def _print_summary(self):
        """打印汇总报告"""
        print(f"\n{'='*60}")
        print(f"  AI中枢能力测试报告")
        print(f"{'='*60}\n")

        # 按得分排序
        sorted_results = sorted(self.results, key=lambda x: x["score"], reverse=True)

        print(f"{'App':<16} {'类型':<10} {'启动':<6} {'识别':<6} {'输入':<6} {'发送':<6} {'回复':<6} {'总分':<8}")
        print("─" * 76)

        for r in sorted_results:
            steps = r["steps"]
            def icon(k): return "✅" if steps.get(k) else "❌"
            score_bar = "★" * r["score"] + "☆" * (r["max_score"] - r["score"])
            print(f"{r['name']:<14} {r['type']:<8} {icon('launch'):<4} {icon('identify'):<4} "
                  f"{icon('find_input'):<4} {icon('send'):<4} {icon('reply'):<4} "
                  f"{r['score']}/{r['max_score']} {score_bar}")

        # 统计
        total = len(self.results)
        full_pass = sum(1 for r in self.results if r["score"] == r["max_score"])
        launchable = sum(1 for r in self.results if r["steps"].get("launch"))
        interactive = sum(1 for r in self.results if r["steps"].get("send"))

        print(f"\n📊 汇总:")
        print(f"  可启动: {launchable}/{total}")
        print(f"  可交互: {interactive}/{total}")
        print(f"  全通过: {full_pass}/{total}")

        # AI回复展示
        print(f"\n💬 AI回复摘要:")
        for r in sorted_results:
            reply = r.get("ai_reply", "")
            if reply:
                print(f"  {r['name']}: {reply[:80]}")
            else:
                status = "未启动" if not r["steps"].get("launch") else "未获得回复"
                print(f"  {r['name']}: ({status})")

        # 保存JSON报告
        report_path = os.path.join(os.path.dirname(__file__), "..", "ai_hub_report.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "device": self.p.base,
                "test_prompt": TEST_PROMPT,
                "results": self.results,
                "summary": {
                    "total": total,
                    "launchable": launchable,
                    "interactive": interactive,
                    "full_pass": full_pass,
                }
            }, f, ensure_ascii=False, indent=2)
        print(f"\n📄 详细报告已保存: {report_path}")


# ============================================================
# 单App快速测试
# ============================================================

def test_single(phone: Phone, app_name: str):
    """测试单个指定的AI App"""
    for app in AI_APPS:
        if app_name.lower() in app["name"].lower() or app_name.lower() in app["package"].lower():
            tester = AIHubTester(phone)
            result = tester._test_one(app)
            phone.home()
            return result
    print(f"未找到匹配 '{app_name}' 的AI App")
    print(f"可用: {', '.join(a['name'] for a in AI_APPS)}")
    return None


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI中枢能力测试")
    parser.add_argument("--host", default="192.168.31.32", help="手机IP")
    parser.add_argument("--port", type=int, default=8084, help="ScreenStream端口")
    parser.add_argument("--app", default=None, help="只测试指定APP (如 deepseek/kimi/混元)")
    parser.add_argument("--list", action="store_true", help="列出所有AI App")
    args = parser.parse_args()

    if args.list:
        print("已注册的AI App:")
        for a in AI_APPS:
            print(f"  {a['name']:<16} {a['package']:<40} {a['type']}")
        sys.exit(0)

    print(f"连接手机: {args.host}:{args.port}")
    p = Phone(host=args.host, port=args.port, auto_discover=False)

    # 健康检查
    h = p.health()
    if not h.get("healthy"):
        print(f"⚠️ 手机状态异常: {h}")
        print("尝试自动恢复...")
        ok, log = p.ensure_alive()
        if not ok:
            print(f"❌ 恢复失败: {log}")
            sys.exit(1)

    print(f"✅ 手机健康: 电量{h.get('battery',0)}% 网络{h.get('network','?')}")

    if args.app:
        test_single(p, args.app)
    else:
        tester = AIHubTester(p)
        tester.test_all()

        # 附加：列出需要登录的App
        if AI_APPS_LOGIN_REQUIRED:
            print(f"\n📋 需要登录才能测试的AI App ({len(AI_APPS_LOGIN_REQUIRED)}个):")
            for app in AI_APPS_LOGIN_REQUIRED:
                print(f"  ❌ {app['name']} ({app['package']}) — {app.get('login_screen', '')}")
