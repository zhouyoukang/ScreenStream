"""通过CDP Input.dispatchMouseEvent拖拽验证码滑块
不移动物理鼠标，不需要Chrome在前台"""
import json
import time
import random
import requests
import websocket

CDP_PORT = 17592

# === 1. 连接Chrome CDP ===
targets = requests.get(f"http://localhost:{CDP_PORT}/json").json()
# 找到微信注册页面
page_ws = None
for t in targets:
    if 'weixin' in t.get('url', '') or '小程序' in t.get('title', ''):
        page_ws = t['webSocketDebuggerUrl']
        print(f"Found: {t['title'][:50]} | {t['url'][:80]}")
        break

if not page_ws:
    print("Available targets:")
    for t in targets:
        print(f"  {t.get('title','')[:40]} | {t.get('url','')[:60]}")
    exit(1)

ws = websocket.create_connection(page_ws, suppress_origin=True)
msg_id = 0

def cdp(method, params=None):
    global msg_id
    msg_id += 1
    msg = {"id": msg_id, "method": method, "params": params or {}}
    ws.send(json.dumps(msg))
    while True:
        resp = json.loads(ws.recv())
        if resp.get("id") == msg_id:
            if "error" in resp:
                print(f"CDP ERROR: {resp['error']}")
            return resp.get("result", {})

# === 2. 获取iframe位置 ===
# 在页面上下文中执行JS获取iframe rect
result = cdp("Runtime.evaluate", {
    "expression": """
    (() => {
        const iframe = document.querySelector('iframe[src*="captcha"]');
        if (!iframe) return JSON.stringify({error: 'no iframe'});
        const r = iframe.getBoundingClientRect();
        return JSON.stringify({x: r.x, y: r.y, w: r.width, h: r.height});
    })()
    """,
    "returnByValue": True
})
iframe_info = json.loads(result["result"]["value"])
print(f"Captcha iframe: {iframe_info}")

if "error" in iframe_info:
    print("Captcha iframe not found!")
    ws.close()
    exit(1)

ix = iframe_info["x"]
iy = iframe_info["y"]
iw = iframe_info["w"]
ih = iframe_info["h"]

# === 3. 计算滑块坐标 ===
# 验证码弹窗内部布局（典型Tencent captcha）:
# - 标题栏: ~40px
# - 图片区: ~200px
# - 滑块轨道: 在底部约 ih-55 处
# - 滑块handle: 在轨道左侧起始位

# 滑块在viewport中的坐标
slider_x = ix + 50  # 左侧padding + 滑块handle中心
slider_y = iy + ih - 55  # 底部轨道区域

# 轨道宽度（估算）
track_width = iw - 60  # 两侧各30px padding

print(f"Slider start: ({slider_x:.0f}, {slider_y:.0f})")
print(f"Track width: ~{track_width:.0f}px")

# === 4. 先刷新验证码获取新拼图 ===
print("Refreshing captcha...")
# 点击刷新按钮（在验证码右下角）
refresh_x = ix + iw - 30
refresh_y = iy + ih - 15
cdp("Input.dispatchMouseEvent", {
    "type": "mousePressed", "x": refresh_x, "y": refresh_y,
    "button": "left", "clickCount": 1
})
cdp("Input.dispatchMouseEvent", {
    "type": "mouseReleased", "x": refresh_x, "y": refresh_y,
    "button": "left", "clickCount": 1
})
time.sleep(2)  # 等待新图加载

# === 5. 截图分析缺口位置 ===
# 截取验证码区域
result = cdp("Page.captureScreenshot", {
    "format": "png",
    "clip": {"x": ix, "y": iy, "width": iw, "height": ih, "scale": 1}
})
if "data" in result:
    import base64
    with open("E:/github/AIOT/ScreenStream_v2/captcha_clip.png", "wb") as f:
        f.write(base64.b64decode(result["data"]))
    print("Captcha screenshot saved")

    # 分析图片找缺口位置
    from PIL import Image
    import io
    img = Image.open(io.BytesIO(base64.b64decode(result["data"])))
    pixels = img.load()
    w, h = img.size
    print(f"Captcha image: {w}x{h}")

    # 找缺口：缺口区域通常比周围暗（有阴影）
    # 扫描图片中间区域，找暗色边缘
    # 拼图区域大约在y=40到y=h-70（排除标题和滑块轨道）
    img_top = 45
    img_bottom = h - 65
    img_left = 10
    img_right = w - 10

    # 计算每列的平均亮度差异
    col_diffs = []
    for x in range(img_left + 1, img_right):
        diff_sum = 0
        count = 0
        for y in range(img_top, img_bottom, 3):
            r1, g1, b1 = pixels[x, y][:3]
            r2, g2, b2 = pixels[x-1, y][:3]
            diff = abs(r1-r2) + abs(g1-g2) + abs(b1-b2)
            diff_sum += diff
            count += 1
        avg_diff = diff_sum / count if count else 0
        col_diffs.append((x, avg_diff))

    # 找高差异的列（缺口边缘）
    sorted_diffs = sorted(col_diffs, key=lambda x: -x[1])
    # 取前20个高差异列，找到它们的聚类中心
    top_cols = [c[0] for c in sorted_diffs[:20]]
    # 找到最右侧的聚类（通常是缺口右边缘）
    top_cols.sort()

    # 简单聚类：找间距>20的断点
    clusters = []
    current = [top_cols[0]]
    for i in range(1, len(top_cols)):
        if top_cols[i] - top_cols[i-1] > 20:
            clusters.append(current)
            current = [top_cols[i]]
        else:
            current.append(top_cols[i])
    clusters.append(current)

    print(f"Edge clusters: {[f'x={min(c)}-{max(c)}' for c in clusters]}")

    # 缺口通常不在最左侧（那是拼图块起始位置）
    # 找第二个或更右侧的聚类作为缺口
    if len(clusters) >= 2:
        # 取第二个聚类（跳过最左侧的拼图块边缘）
        gap_cluster = clusters[1]
        gap_x = (min(gap_cluster) + max(gap_cluster)) // 2
    else:
        # 只有一个聚类，取其中心
        gap_x = (min(clusters[0]) + max(clusters[0])) // 2

    # gap_x是在captcha图片内的x坐标
    # 转换为滑块拖拽距离
    # 拼图块宽度约40px，缺口左边缘减去拼图块半宽 = 拖拽距离
    drag_target_in_image = gap_x - 20  # 减去拼图块半宽
    # 图片区域起始x约在captcha的15px处
    drag_distance = drag_target_in_image - 15  # 减去起始偏移

    print(f"Gap center in image: x={gap_x}")
    print(f"Calculated drag distance: {drag_distance}px")
else:
    print("Screenshot failed, using default distance")
    drag_distance = 100

# 限制合理范围
drag_distance = max(30, min(drag_distance, track_width - 20))
print(f"Final drag distance: {drag_distance}px")

# === 6. 执行CDP级别拖拽 ===
start_x = slider_x
start_y = slider_y
end_x = slider_x + drag_distance

print(f"CDP drag: ({start_x:.0f},{start_y:.0f}) -> ({end_x:.0f},{start_y:.0f})")

# mousePressed
cdp("Input.dispatchMouseEvent", {
    "type": "mousePressed",
    "x": start_x, "y": start_y,
    "button": "left", "clickCount": 1
})
time.sleep(0.1)

# mouseMoved - 分步模拟人类拖拽
steps = 30
for i in range(1, steps + 1):
    progress = i / steps
    # 缓动函数：先快后慢
    eased = 1 - (1 - progress) ** 3
    x = start_x + drag_distance * eased
    y = start_y + random.uniform(-1, 1)
    cdp("Input.dispatchMouseEvent", {
        "type": "mouseMoved",
        "x": x, "y": y,
        "button": "left"
    })
    time.sleep(0.02 + random.uniform(0, 0.02))

time.sleep(0.15)

# mouseReleased
cdp("Input.dispatchMouseEvent", {
    "type": "mouseReleased",
    "x": end_x, "y": start_y,
    "button": "left", "clickCount": 1
})

print("Drag completed via CDP!")
time.sleep(2)

# === 7. 检查结果 ===
result = cdp("Page.captureScreenshot", {"format": "png"})
if "data" in result:
    import base64
    with open("E:/github/AIOT/ScreenStream_v2/cdp_result.png", "wb") as f:
        f.write(base64.b64decode(result["data"]))
    print("Result screenshot saved to cdp_result.png")

ws.close()
print("Done!")
