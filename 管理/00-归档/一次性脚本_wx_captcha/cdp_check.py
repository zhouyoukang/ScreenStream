"""CDP直连检查页面状态+处理验证码"""
import json, time, random, requests, websocket, base64, sys

CDP_PORT = 35937

# 1. 列出所有页面
targets = requests.get(f"http://localhost:{CDP_PORT}/json").json()
print("=== All pages ===")
for i, t in enumerate(targets):
    print(f"  [{i}] {t['type']} | {t['title'][:50]} | {t['url'][:80]}")

# 找微信相关页面
wx_targets = [t for t in targets if 'weixin' in t.get('url','') or 'mp.weixin' in t.get('url','')]
if not wx_targets:
    print("No WeChat page found!")
    sys.exit(1)

target = wx_targets[0]
print(f"\n=== Target: {target['title']} ===")
print(f"URL: {target['url']}")

# 2. 连接WebSocket
ws = websocket.create_connection(target['webSocketDebuggerUrl'], suppress_origin=True)
msg_id = 0

def cdp(method, params=None):
    global msg_id
    msg_id += 1
    ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
    while True:
        resp = json.loads(ws.recv())
        if resp.get("id") == msg_id:
            if "error" in resp:
                print(f"  CDP error: {resp['error'].get('message','')[:80]}")
            return resp.get("result", {})

# 3. 检查页面内容
result = cdp("Runtime.evaluate", {
    "expression": """
    (() => {
        const iframe = document.querySelector('iframe[src*="captcha"]');
        const hasCaptcha = !!iframe;
        const title = document.title;
        const url = location.href;
        const emailInput = document.querySelector('input[name="email"],#js_email');
        const email = emailInput ? emailInput.value : null;
        const verifyInput = document.querySelector('input[name="ticket"],#js_email_verifycode');
        const verifyVal = verifyInput ? verifyInput.value : null;
        const regBtn = document.querySelector('.js_btn_register,#js_btn_register,.btn_register');
        const regDisabled = regBtn ? regBtn.disabled || regBtn.classList.contains('btn_disabled') : null;
        const errorMsg = document.querySelector('.err_tip,.tips_err,.js_err');
        const errText = errorMsg ? errorMsg.textContent.trim() : null;

        // Check for success/next step indicators
        const stepItems = document.querySelectorAll('.step_item,.step_text,.timeline_item');
        const steps = Array.from(stepItems).map(s => s.textContent.trim()).filter(s => s);

        let iframeRect = null;
        if (iframe) {
            const r = iframe.getBoundingClientRect();
            iframeRect = {x: r.x, y: r.y, w: r.width, h: r.height};
        }

        return JSON.stringify({
            title, url, hasCaptcha, iframeRect,
            email, verifyVal, regDisabled, errText, steps
        });
    })()
    """,
    "returnByValue": True
})

state = json.loads(result["result"]["value"])
print(f"\n=== Page State ===")
for k, v in state.items():
    print(f"  {k}: {v}")

# 4. 如果有验证码，执行CDP拖拽
if state["hasCaptcha"] and state["iframeRect"]:
    ir = state["iframeRect"]
    print(f"\n=== Captcha found at ({ir['x']},{ir['y']}) {ir['w']}x{ir['h']} ===")

    # 截取验证码区域分析缺口
    ss = cdp("Page.captureScreenshot", {
        "format": "png",
        "clip": {"x": ir['x'], "y": ir['y'], "width": ir['w'], "height": ir['h'], "scale": 1}
    })
    if "data" in ss:
        img_data = base64.b64decode(ss["data"])
        with open("E:/github/AIOT/ScreenStream_v2/captcha_clip.png", "wb") as f:
            f.write(img_data)

        from PIL import Image
        import io
        img = Image.open(io.BytesIO(img_data))
        px = img.load()
        w, h = img.size
        print(f"  Captcha clip: {w}x{h}")

        # 图片区域 (排除标题和滑块)
        img_top = 50
        img_bot = h - 70
        img_left = 15
        img_right = w - 15

        # 逐列计算左右相邻像素差异 → 找垂直边缘
        col_edges = []
        for x in range(img_left + 2, img_right):
            edge_score = 0
            samples = 0
            for y in range(img_top, img_bot, 2):
                r1, g1, b1 = px[x, y][:3]
                r2, g2, b2 = px[x-2, y][:3]
                edge_score += abs(r1-r2) + abs(g1-g2) + abs(b1-b2)
                samples += 1
            col_edges.append((x, edge_score / samples if samples else 0))

        # 找高边缘分数的列（缺口边缘）
        avg_edge = sum(e[1] for e in col_edges) / len(col_edges)
        threshold = avg_edge * 2.5
        hot_cols = [e[0] for e in col_edges if e[1] > threshold]

        if hot_cols:
            # 聚类
            clusters = [[hot_cols[0]]]
            for c in hot_cols[1:]:
                if c - clusters[-1][-1] <= 15:
                    clusters[-1].append(c)
                else:
                    clusters.append([c])

            cluster_centers = [(min(c)+max(c))//2 for c in clusters]
            print(f"  Edge clusters at x: {cluster_centers}")

            # 跳过最左侧的（拼图块起始边缘），取后面的作为缺口
            # 缺口应在图片30%以后的位置
            gap_candidates = [c for c in cluster_centers if c > w * 0.25]
            if gap_candidates:
                gap_x = gap_candidates[0]  # 取最左的缺口候选
            else:
                gap_x = cluster_centers[-1]

            drag_distance = gap_x - 35  # 减去起始偏移和拼图块半宽
        else:
            print("  No clear edges found, using default")
            drag_distance = int(ir['w'] * 0.45)

        drag_distance = max(20, min(drag_distance, ir['w'] - 80))
        print(f"  Gap x in image: {gap_x if hot_cols else '?'}")
        print(f"  Drag distance: {drag_distance}px")
    else:
        drag_distance = int(ir['w'] * 0.45)
        print(f"  Screenshot failed, default drag: {drag_distance}px")

    # 滑块位置
    slider_x = ir['x'] + 45
    slider_y = ir['y'] + ir['h'] - 50

    print(f"\n=== Executing CDP drag ===")
    print(f"  From: ({slider_x:.0f}, {slider_y:.0f})")
    print(f"  To:   ({slider_x + drag_distance:.0f}, {slider_y:.0f})")

    # mousePressed
    cdp("Input.dispatchMouseEvent", {
        "type": "mousePressed",
        "x": slider_x, "y": slider_y,
        "button": "left", "clickCount": 1
    })
    time.sleep(0.1)

    # mouseMoved with human-like motion
    steps = 35
    for i in range(1, steps + 1):
        p = i / steps
        eased = 1 - (1 - p) ** 3
        x = slider_x + drag_distance * eased
        y = slider_y + random.uniform(-1.5, 1.5)
        cdp("Input.dispatchMouseEvent", {
            "type": "mouseMoved",
            "x": x, "y": y,
            "button": "left"
        })
        time.sleep(0.015 + random.uniform(0, 0.02))

    time.sleep(0.15)

    # mouseReleased
    cdp("Input.dispatchMouseEvent", {
        "type": "mouseReleased",
        "x": slider_x + drag_distance, "y": slider_y,
        "button": "left", "clickCount": 1
    })
    print("  Drag sent!")
    time.sleep(2)

    # 检查验证码是否消失
    check = cdp("Runtime.evaluate", {
        "expression": "!!document.querySelector('iframe[src*=\"captcha\"]')",
        "returnByValue": True
    })
    still_captcha = check.get("result", {}).get("value", True)
    print(f"  Captcha still visible: {still_captcha}")

    if still_captcha:
        print("  >>> Captcha NOT solved. Will retry with different distance.")
else:
    print("\n=== No captcha on page ===")
    if 'step' in state.get('url','').lower() or state.get('steps'):
        print("Page may have advanced to next step!")

# 截图保存
ss2 = cdp("Page.captureScreenshot", {"format": "png"})
if "data" in ss2:
    with open("E:/github/AIOT/ScreenStream_v2/cdp_result.png", "wb") as f:
        f.write(base64.b64decode(ss2["data"]))
    print("\nResult screenshot: cdp_result.png")

ws.close()
