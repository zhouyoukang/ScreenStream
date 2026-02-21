"""
手机操控统一库 — 零AI基础设施
==============================
所有深度操控脚本的公共库。提供标准化的APP操控原语。
导入后一行代码即可完成复杂操作。

使用:
  from phone_lib import Phone
  p = Phone(port=8086)
  p.open_app("com.eg.android.AlipayGphone")
  p.alipay("10000007")  # 扫一扫
  texts = p.read()
  p.click("我的")
  p.clipboard_write("hello from PC")
  p.home()
"""

import json, time, os, shutil
from urllib.request import Request, urlopen
from urllib.error import HTTPError

# ADB路径自动检测：PATH > 项目内SDK > 环境变量
_PROJECT_ADB = os.path.join(os.path.dirname(__file__), "..", "..",
    "090-构建与部署_Build", "android-sdk", "platform-tools",
    "adb.exe" if os.name == "nt" else "adb")

def _find_adb():
    return (shutil.which("adb")
            or (os.path.abspath(_PROJECT_ADB) if os.path.isfile(_PROJECT_ADB) else None)
            or os.environ.get("ADB_PATH")
            or "adb")


class Phone:
    def __init__(self, port=8086):
        self.base = f"http://127.0.0.1:{port}"

    def _http(self, method, path, body=None, timeout=15):
        url = self.base + path
        data = json.dumps(body).encode() if body else None
        headers = {"Content-Type": "application/json"} if data else {}
        req = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode()
                try:
                    return json.loads(raw)
                except:
                    return {"_raw": raw}
        except HTTPError as e:
            return {"_error": e.code}
        except Exception as e:
            return {"_error": -1, "_msg": str(e)}

    # === 基础操作 ===
    def get(self, path): return self._http("GET", path)
    def post(self, path, body=None): return self._http("POST", path, body)
    def wait(self, sec): time.sleep(sec)
    def home(self): self.post("/home"); self.wait(0.8)
    def back(self): self.post("/back"); self.wait(0.3)

    # === 感知 ===
    def status(self): return self.get("/status")
    def device(self): return self.get("/deviceinfo")
    def foreground(self): return self.get("/foreground").get("packageName", "")
    def notifications(self, limit=10): return self.get(f"/notifications/read?limit={limit}")

    def read(self):
        """读取屏幕文本，返回(texts_list, package)"""
        r = self.get("/screen/text")
        return [t.get("text", "") for t in r.get("texts", [])], r.get("package", "")

    def read_count(self):
        """快速获取文本/可点击数量"""
        r = self.get("/screen/text")
        return r.get("textCount", 0), r.get("clickableCount", 0)

    # === 导航 ===
    def tap(self, nx, ny): return self.post("/tap", {"nx": nx, "ny": ny})
    def click(self, text): return self.post("/findclick", {"text": text})
    def swipe(self, direction="up", distance=500):
        if direction == "up":
            return self.post("/swipe", {"nx1": 0.5, "ny1": 0.7, "nx2": 0.5, "ny2": 0.3, "duration": 300})
        elif direction == "down":
            return self.post("/swipe", {"nx1": 0.5, "ny1": 0.3, "nx2": 0.5, "ny2": 0.7, "duration": 300})

    # === 系统 ===
    def wake(self): return self.post("/wake")
    def lock(self): return self.post("/lock")
    def screenshot(self): return self.post("/screenshot")
    def volume(self, level): return self.post("/volume", {"stream": "music", "level": level})
    def brightness(self, level): return self.post(f"/brightness/{level}")

    # === 剪贴板 ===
    def clipboard_read(self): return self.get("/clipboard").get("text")
    def clipboard_write(self, text): return self.post("/clipboard", {"text": text})

    # === APP启动 ===
    def open_app(self, pkg, wait_sec=2):
        """启动APP，自动处理OPPO弹窗"""
        self.post("/openapp", {"packageName": pkg})
        self.wait(wait_sec)
        self._dismiss_oppo()
        if pkg.split('.')[-1].lower() not in self.foreground().lower():
            self.intent("android.intent.action.MAIN", package=pkg,
                       categories=["android.intent.category.LAUNCHER"])
            self.wait(2)
            self._dismiss_oppo()

    def intent(self, action, data=None, package=None, categories=None, extras=None):
        """发送Intent"""
        body = {"action": action, "flags": ["FLAG_ACTIVITY_NEW_TASK"]}
        if data: body["data"] = data
        if package: body["package"] = package
        if categories: body["categories"] = categories
        if extras: body["extras"] = extras
        return self.post("/intent", body)

    def monkey_open(self, pkg, wait_sec=3):
        """用monkey命令启动APP（绕过OPPO弹窗拦截，最可靠）"""
        import subprocess
        adb = _find_adb()
        subprocess.run([adb, "shell", "monkey", "-p", pkg, "-c",
                       "android.intent.category.LAUNCHER", "1"],
                       capture_output=True, timeout=10)
        self.wait(wait_sec)

    def search_in_app(self, search_text, search_btn="搜索", wait_sec=3):
        """APP内搜索：多策略点击搜索栏→输入→回车。
        策略1: findclick"搜索栏"(淘宝等)
        策略2: ADB tap顶部搜索区域(京东/拼多多等搜索栏不可findclick的APP)
        然后: 清空→输入→回车"""
        import subprocess
        adb = _find_adb()
        # 策略1: findclick"搜索栏"(仅尝试搜索栏，不尝试"搜索"避免误触底部Tab)
        r = self.click("搜索栏")
        if r.get("ok"):
            self.wait(1)
        else:
            # 策略2: ADB直接tap屏幕顶部搜索区域(京东EditText~y186, 拼多多~y170)
            subprocess.run([adb, "shell", "input", "tap", "570", "170"],
                           capture_output=True, timeout=5)
            self.wait(1)
        # 清空搜索框：triple-tap全选 → 用空文本替换
        # 方法: 先通过ScreenStream的/settext清空，如果失败则手动清空
        r_clear = self.post("/settext", {"search": "", "value": ""})
        if not r_clear or not r_clear.get("ok"):
            # 手动清空：长按选全部 → 删除
            subprocess.run([adb, "shell", "input", "keyevent", "123"],  # MOVE_END
                           capture_output=True, timeout=5)
            subprocess.run([adb, "shell", "input", "keyevent", "67", "67", "67", "67", "67",
                           "67", "67", "67", "67", "67", "67", "67", "67", "67", "67",
                           "67", "67", "67", "67", "67"],  # 20x DEL in one command
                           capture_output=True, timeout=5)
        self.wait(0.3)
        # 输入搜索文本
        self.post("/text", {"text": search_text})
        self.wait(0.5)
        # 按回车搜索
        subprocess.run([adb, "shell", "input", "keyevent", "66"],
                       capture_output=True, timeout=5)
        self.wait(wait_sec)
        return self.read()

    def _dismiss_oppo(self):
        """处理OPPO安全弹窗"""
        for _ in range(2):
            if "permission" not in self.foreground().lower():
                return
            for btn in ["允许", "始终允许", "打开", "确定"]:
                self.click(btn); self.wait(0.2)
            self.back(); self.wait(0.5)

    # === Scheme快捷方式 ===
    def alipay(self, app_id, wait_sec=2.5):
        """支付宝scheme直跳"""
        self.intent("android.intent.action.VIEW",
                   data=f"alipays://platformapi/startapp?appId={app_id}")
        self.wait(wait_sec)

    def amap_navi(self, lat, lon):
        """高德导航"""
        self.intent("android.intent.action.VIEW",
                   data=f"androidamap://navi?sourceApplication=test&lat={lat}&lon={lon}&dev=0&style=2")
        self.wait(3)

    def amap_search(self, keyword):
        """高德POI搜索"""
        self.intent("android.intent.action.VIEW",
                   data=f"androidamap://poi?sourceApplication=test&keywords={keyword}&dev=0")
        self.wait(3)

    def bili(self, path, wait_sec=2.5):
        """B站scheme直跳"""
        self.intent("android.intent.action.VIEW", data=f"bilibili://{path}")
        self.wait(wait_sec)

    def baidumap(self, destination):
        """百度地图导航"""
        self.intent("android.intent.action.VIEW",
                   data=f"baidumap://map/direction?destination={destination}")
        self.wait(3)

    # === 验证 ===
    def is_app(self, keyword):
        """检查当前前台APP是否包含关键词"""
        return keyword.lower() in self.foreground().lower()

    def has_text(self, *keywords):
        """检查屏幕是否包含任一关键词"""
        texts, _ = self.read()
        combined = " ".join(texts)
        return any(k in combined for k in keywords)

    # === 高级组合 ===
    def collect_status(self):
        """一键采集设备全状态"""
        d = self.device()
        n = self.notifications(5)
        return {
            "battery": d.get("batteryLevel", -1),
            "charging": d.get("isCharging", False),
            "network": d.get("networkType", "?"),
            "net_ok": d.get("networkConnected", False),
            "model": f"{d.get('manufacturer','')} {d.get('model','')}",
            "storage_free_gb": round(d.get("storageAvailableMB", 0) / 1024, 1),
            "notif_count": n.get("total", 0),
            "fg_app": self.foreground().split(".")[-1],
        }

    def report_to_clipboard(self, prefix=""):
        """采集状态并写入剪贴板"""
        s = self.collect_status()
        text = (f"{prefix}"
                f"电量:{s['battery']}%{'⚡' if s['charging'] else ''} "
                f"网络:{s['network']} "
                f"存储:{s['storage_free_gb']}GB "
                f"通知:{s['notif_count']}条")
        self.clipboard_write(text)
        return text

    # === 高频日常场景（基于QuestMobile 2025数据） ===

    def check_notifications_smart(self):
        """智能通知检查：分类统计+识别重要通知"""
        n = self.notifications(20)
        items = n.get("notifications", [])
        cats = {"social": [], "shopping": [], "finance": [], "system": [], "other": []}
        social_keys = ["tencent", "weixin", "qq", "whatsapp", "telegram"]
        shop_keys = ["taobao", "jingdong", "pinduoduo", "meituan", "ele"]
        finance_keys = ["alipay", "bank", "wechat"]
        for item in items:
            pkg = str(item.get("package", "")).lower()
            title = str(item.get("title", ""))
            entry = {"title": title, "pkg": pkg.split(".")[-1]}
            if any(k in pkg for k in social_keys): cats["social"].append(entry)
            elif any(k in pkg for k in shop_keys): cats["shopping"].append(entry)
            elif any(k in pkg for k in finance_keys): cats["finance"].append(entry)
            elif "android" in pkg: cats["system"].append(entry)
            else: cats["other"].append(entry)
        return {"total": n.get("total", 0), "categories": cats}

    def quick_pay_scan(self):
        """一键支付宝扫码"""
        self.alipay("10000007")
        return self.is_app("alipay") or self.is_app("eg.android")

    def quick_pay_code(self):
        """一键出示付款码"""
        self.alipay("20000056")
        return self.is_app("alipay") or self.is_app("eg.android")

    def quick_express(self):
        """一键查快递"""
        self.alipay("20000754")
        return self.is_app("alipay") or self.is_app("eg.android")

    def quick_navigate(self, destination):
        """一键导航到目的地（高德）"""
        self.amap_search(destination)
        return self.is_app("autonavi")

    def quick_search_video(self, keyword):
        """一键搜索B站视频"""
        self.bili(f"search?keyword={keyword}")
        return self.is_app("bili") or self.is_app("danmaku")

    def quick_bill(self):
        """一键查看支付宝账单"""
        self.alipay("20000003")
        return self.is_app("alipay") or self.is_app("eg.android")

    def daily_check(self):
        """每日巡检：设备+通知+快递"""
        results = {}
        results["device"] = self.collect_status()
        results["notifications"] = self.check_notifications_smart()
        self.alipay("20000754"); self.wait(2)
        texts, _ = self.read()
        results["express"] = [t for t in texts if any(k in t for k in ["快递", "物流", "签收", "派送"])]
        self.home()
        return results
