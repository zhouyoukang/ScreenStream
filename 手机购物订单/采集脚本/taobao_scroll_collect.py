"""淘宝订单列表滚动采集 - Agent模式自动化"""
import subprocess, os, json, time, re
from xml.etree import ElementTree as ET

ADB = r"e:\道\道生一\一生二\构建部署\android-sdk\platform-tools\adb.exe"
SN = os.environ.get("ADB_SERIAL", "10.172.236.90:43253")
OUT = r"e:\道\道生一\一生二\手机购物订单\原始数据\dumps\taobao_raw.json"
TMP = os.path.join(os.environ.get("TEMP", "/tmp"), "ui.xml")

def adb(*a):
    try:
        return subprocess.run([ADB, "-s", SN] + list(a),
                              capture_output=True, text=True, timeout=15,
                              encoding='utf-8', errors='replace').stdout.strip()
    except:
        return ""

def dump_screen():
    adb("shell", "uiautomator dump /sdcard/ui.xml")
    adb("pull", "/sdcard/ui.xml", TMP)
    texts = []
    try:
        tree = ET.parse(TMP)
        for node in tree.iter("node"):
            t = node.get("text", "").strip()
            cd = node.get("content-desc", "").strip()
            b = node.get("bounds", "")
            # 优先text，其次content-desc
            val = t or cd
            if val:
                texts.append({"text": val, "bounds": b, "src": "text" if t else "cd"})
    except:
        pass
    return texts

def scroll_down():
    adb("shell", "input swipe 540 1800 540 600 500")
    time.sleep(2)

def texts_signature(texts):
    """用店铺名+价格组合作为去重签名"""
    key_texts = []
    for item in texts:
        t = item["text"]
        if re.search(r'[¥￥]\d', t) or "店" in t or any(k in t for k in ["已发货", "交易成功", "待收货", "待发货", "已签收", "已关闭", "待评价"]):
            key_texts.append(t)
    # 用前8个关键文本做签名，避免完全相同才判重
    return "|".join(key_texts[:8])

def main():
    all_screens = []
    seen_sigs = set()
    no_new_count = 0
    max_screens = 40

    print(f"开始淘宝订单滚动采集...")

    for i in range(max_screens):
        texts = dump_screen()
        sig = texts_signature(texts)

        # 检测是否有新内容
        if sig in seen_sigs:
            no_new_count += 1
            print(f"  屏幕{i+1}: 无新内容 ({no_new_count}/3)")
            if no_new_count >= 3:
                print("连续3屏无新内容，采集结束")
                break
        else:
            no_new_count = 0
            seen_sigs.add(sig)
            plain = [item["text"] for item in texts]
            all_screens.append({"screen": i+1, "texts": plain, "raw": texts})

            # 统计本屏订单数
            store_count = sum(1 for item in texts if "店" in item["text"] and
                            any(s in "|".join(t["text"] for t in texts) for s in ["¥"]))
            print(f"  屏幕{i+1}: {len(texts)}个元素, ~{store_count}个店铺")

        # 检测"没有更多订单"
        all_text = " ".join(item["text"] for item in texts)
        if "没有更多" in all_text or "已经到底" in all_text or "到底了" in all_text:
            print("检测到底部标记，采集结束")
            # 仍保存当前屏
            break

        scroll_down()

    # 保存结果
    result = {"platform": "taobao", "screens": all_screens, "total_screens": len(all_screens)}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n采集完成: {len(all_screens)}屏数据 → {OUT}")

if __name__ == "__main__":
    main()
