"""极简滚动dump v2：逐屏增量写入，崩溃不丢数据。Agent做大脑。"""
import json, time, os, subprocess, sys
from urllib.request import Request, urlopen
from urllib.error import URLError

BASE = "http://127.0.0.1:8086"
ADB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..",
                   "构建部署", "android-sdk", "platform-tools", "adb.exe")
SERIAL = "158377ff"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                   "原始数据", "taobao_agent_full.txt")

def api(path, retries=2):
    for attempt in range(retries + 1):
        try:
            r = urlopen(Request(f"{BASE}{path}"), timeout=8)
            return json.loads(r.read())
        except Exception as e:
            if attempt < retries:
                time.sleep(1)
            else:
                print(f"    API {path} failed: {e}")
                return {}

def read_screen():
    r = api("/screen/text")
    return [t.get("text","") for t in r.get("texts",[]) if t.get("text","").strip()]

def swipe_up():
    try:
        subprocess.run([ADB, "-s", SERIAL, "shell", "input swipe 540 1800 540 600 500"],
                       capture_output=True, timeout=10)
    except Exception as e:
        print(f"    swipe failed: {e}")

# UI噪声
NOISE = {
    "返回", "跳往搜索页", "筛选", "订单管理", "···", "全部订单已选中",
    "购物未选中", "闪购未选中", "飞猪未选中", "待付款", "待发货", "待收货",
    "退款/售后", "全部", "待付款未选中", "待发货未选中", "待收货未选中",
    "退款/售后未选中", "全部已选中", "暂无进行中订单", "查看全部",
    "更多", "更多操作",
}
ICON_PREFIXES = ("ꈝ", "ꁽ", "끺", "ꄪ", "ꁊ")

def is_noise(t):
    return (t in NOISE or len(t) <= 1 or
            any(t.startswith(p) for p in ICON_PREFIXES) or
            t.startswith("消息") and "按钮" in t)

# 增量写入
f = open(OUT, "w", encoding="utf-8")
total_lines = 0
last_sig = ""
empty = 0

print("开始采集...")
try:
    for s in range(1, 55):
        texts = read_screen()
        if not texts:  # API完全失败
            empty += 1
            print(f"  [{s:2d}] API returned empty ({empty}/5)")
            if empty >= 5:
                break
            time.sleep(2)
            continue

        content = [t for t in texts if not is_noise(t)]

        # 签名
        sig = "|".join([t for t in content if len(t) > 3][:6])

        # 终止检测
        page = " ".join(content)
        hit_bottom = ("回到顶部" in page or "没有更多" in page) and s > 3

        if sig == last_sig or len(content) == 0:
            empty += 1
            print(f"  [{s:2d}] same/empty ({empty}/5){' [BOTTOM]' if hit_bottom else ''}")
            if empty >= 5 or hit_bottom:
                print(f"=== BOTTOM at screen {s} ===")
                break
        else:
            empty = 0
            header = f"\n=== SCREEN {s} ({len(content)} items) ==="
            f.write(header + "\n")
            for line in content:
                f.write(line + "\n")
            f.flush()  # 立即刷盘
            total_lines += len(content) + 1
            print(f"  [{s:2d}] +{len(content)} items (total ~{total_lines} lines)")

        last_sig = sig
        swipe_up()
        time.sleep(2.0)

except KeyboardInterrupt:
    print("\n用户中断")
except Exception as e:
    print(f"\n异常: {e}")
finally:
    f.close()
    print(f"\nDone: ~{total_lines} lines → {OUT}")
