"""
手机自闭环进化系统
实践 → 找问题 → 改进 → 继续实践 → 永不停止

道之闭环：官知止而神欲行，归根曰静，知常曰明。
每一轮失败都是肥料，每一轮成功都是积累。
"""
import requests, json, time, datetime, os, sys
from pathlib import Path

BASE = "http://192.168.31.32:8084"
LOG_FILE = Path(__file__).parent / "loop_log.jsonl"

# ═══ 自适应策略 ═══
STRATEGY = {
    "wake_wait":      0.6,
    "unlock_ny":      0.85,
    "swipe_duration": 300,
    "app_load_wait":  2.0,
    "text_wait":      0.5,
    "ai_apps": [
        ("Kimi",   "com.moonshot.kimichat"),
        ("通义",    "com.aliyun.tongyi"),
        ("文心",    "com.baidu.newapp"),
        ("ChatGPT","com.openai.chatgpt"),
    ],
    "native_apps": [
        ("设置",   "com.android.settings"),
        ("浏览器", "com.heytap.browser"),
        ("计算器", "com.coloros.calculator"),
    ],
    "input_candidates": [0.91, 0.88, 0.85, 0.78],
}

# 成功率记录（跨迭代累积）
STATS = {}

# ═══ 工具函数 ═══
def api(method, path, data=None, timeout=6):
    try:
        url = BASE + path
        r = (requests.get(url, timeout=timeout) if method == "GET"
             else requests.post(url, json=data, timeout=timeout))
        return r.json() if r.text.strip() else {"ok": True}
    except Exception as e:
        return {"error": str(e)}

def record(name, result):
    ok = bool(result.get("ok", False) or (isinstance(result, dict) and "error" not in result and result))
    STATS.setdefault(name, {"ok": 0, "fail": 0})
    if ok:
        STATS[name]["ok"] += 1
    else:
        STATS[name]["fail"] += 1
    return ok, result

def success_rate(name):
    s = STATS.get(name, {"ok": 0, "fail": 0})
    total = s["ok"] + s["fail"]
    return s["ok"] / total if total else 0.0

def c(text, code=""):
    codes = {"green": "\033[92m", "red": "\033[91m", "yellow": "\033[93m",
             "cyan": "\033[96m", "bold": "\033[1m", "": ""}
    return f"{codes[code]}{text}\033[0m"

def log_jsonl(data):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")

# ═══ 六大场景 ═══

def scenario_感知():
    """感知万物 — 五感信息采集"""
    results = {}
    dev = api("GET", "/deviceinfo")
    ok, _ = record("感知/deviceinfo", dev)
    results["device"] = {
        "battery": dev.get("batteryLevel"),
        "wifi": dev.get("wifiRSSI"),
        "screen": dev.get("isScreenOn"),
        "ok": ok,
    }
    win = api("GET", "/windowinfo")
    ok2, _ = record("感知/windowinfo", win)
    results["window"] = {"pkg": win.get("package"), "nodes": win.get("totalNodes"), "ok": ok2}
    return results, ok and ok2

def scenario_唤醒解锁():
    """唤醒·归根 — 每轮必做的状态重置"""
    dev = api("GET", "/deviceinfo")
    if not dev.get("isScreenOn", True):
        r = api("POST", "/wake")
        record("控制/wake", r)
        time.sleep(STRATEGY["wake_wait"])

    # 根据历史成功率选最优 unlock_ny
    r = api("POST", "/swipe", {
        "nx1": 0.5, "ny1": STRATEGY["unlock_ny"],
        "nx2": 0.5, "ny2": 0.2,
        "duration": STRATEGY["swipe_duration"]
    })
    ok, _ = record("控制/swipe_unlock", r)
    time.sleep(0.6)

    # 归根 — 回主屏
    r2 = api("POST", "/home")
    ok2, _ = record("控制/home", r2)
    time.sleep(0.4)

    win = api("GET", "/windowinfo")
    on_launcher = "launcher" in win.get("package", "")
    if not on_launcher:
        api("POST", "/home"); time.sleep(0.5)
        win = api("GET", "/windowinfo")
        on_launcher = "launcher" in win.get("package", "")

    return {"unlock": ok, "home": ok2, "on_launcher": on_launcher}, on_launcher

def scenario_AI连接():
    """召唤AI — 手机×AI归位"""
    # 按历史成功率排序AI App
    ranked = sorted(
        STRATEGY["ai_apps"],
        key=lambda x: success_rate(f"app/{x[1]}"),
        reverse=True
    )
    for name, pkg in ranked:
        r = api("POST", "/openapp", {"packageName": pkg})
        ok, _ = record(f"app/{pkg}", r)
        if ok:
            time.sleep(STRATEGY["app_load_wait"])
            win = api("GET", "/windowinfo")
            actually_open = pkg in win.get("package", "")
            record(f"app_open/{pkg}", {"ok": actually_open})
            if actually_open:
                api("POST", "/home"); time.sleep(0.4)
                return {"name": name, "pkg": pkg, "ok": True}, True
    return {"ok": False, "tried": len(ranked)}, False

def scenario_文字输入():
    """文字输入 — 官知止·神欲行"""
    # 打开原生Settings（稳定支持set_text）
    r = api("POST", "/openapp", {"packageName": "com.android.settings"})
    record("app/settings", r)
    time.sleep(1.5)

    # 找搜索框
    r2 = api("POST", "/findclick", {"text": "搜索"})
    ok_find, _ = record("input/findclick搜索", r2)
    time.sleep(0.5)

    if ok_find:
        r3 = api("POST", "/text", {"text": "WLAN"})
        ok_text, _ = record("input/text", r3)
        time.sleep(0.4)
        api("POST", "/back"); time.sleep(0.3)
        api("POST", "/home"); time.sleep(0.4)
        return {"findclick": ok_find, "text": ok_text, "method": r3.get("method")}, ok_text
    else:
        # 改进：尝试坐标tap找到搜索框
        for ny in STRATEGY["input_candidates"]:
            tap_r = api("POST", "/tap", {"nx": 0.5, "ny": ny})
            time.sleep(0.4)
            t_r = api("POST", "/text", {"text": "WiFi"})
            if t_r.get("ok"):
                record("input/text", t_r)
                STRATEGY["input_candidates"].insert(0, STRATEGY["input_candidates"].pop(
                    STRATEGY["input_candidates"].index(ny)))
                api("POST", "/home"); time.sleep(0.4)
                return {"tap_ny": ny, "text": True}, True
        api("POST", "/home"); time.sleep(0.3)
        return {"findclick": False, "text": False}, False

def scenario_宏自动化():
    """宏系统 — 无为而无不为"""
    # 检查已有宏列表
    macro_list = api("GET", "/macro/list")
    existing = macro_list if isinstance(macro_list, list) else []

    # 创建"感知快照"宏（幂等：名字相同不重复创建）
    if not any(m.get("name") == "感知快照" for m in existing):
        macro = {
            "name": "感知快照",
            "actions": [
                {"type": "api", "endpoint": "/wake"},
                {"type": "wait", "ms": 400},
                {"type": "api", "endpoint": "/screenshot"},
                {"type": "wait", "ms": 300},
                {"type": "api", "endpoint": "/home"},
            ]
        }
        r = api("POST", "/macro/create", macro)
        record("macro/create", r)
        macro_id = r.get("id")
    else:
        macro_id = next((m["id"] for m in existing if m.get("name") == "感知快照"), None)

    if macro_id:
        r2 = api("POST", f"/macro/run/{macro_id}")
        ok, _ = record("macro/run", r2)
        time.sleep(3.0)
        log = api("GET", f"/macro/log/{macro_id}")
        steps = len(log) if isinstance(log, list) else 0
        return {"macro_id": macro_id, "run": ok, "steps": steps}, ok
    return {"ok": False}, False

def scenario_万物连接():
    """万物连之 — 浏览器·URL·外部服务"""
    r = api("POST", "/openurl", {"url": "https://kimi.moonshot.cn"})
    ok, _ = record("connect/openurl", r)
    time.sleep(2.5)
    win = api("GET", "/windowinfo")
    in_browser = "browser" in win.get("package", "") or "chrome" in win.get("package", "")
    record("connect/browser_opened", {"ok": in_browser})
    api("POST", "/home"); time.sleep(0.4)
    return {"url_ok": ok, "browser": in_browser, "pkg": win.get("package")}, ok

# ═══ 改进引擎 ═══
def improve(iteration, scores, iter_results):
    """根据本轮结果自动调整策略 — 损之又损·知常曰明"""
    improvements = []

    # 改进1：解锁坐标自适应（仅在解锁失败时调整）
    if not scores.get("唤醒解锁", True):
        unlock_rate = success_rate("控制/swipe_unlock")
        if unlock_rate < 0.7:
            old = STRATEGY["unlock_ny"]
            candidates = [0.85, 0.88, 0.80, 0.83, 0.90]
            idx = candidates.index(old) if old in candidates else 0
            STRATEGY["unlock_ny"] = candidates[(idx + 1) % len(candidates)]
            improvements.append(f"unlock_ny: {old:.2f}→{STRATEGY['unlock_ny']:.2f}")

    # 改进2：app_load_wait — 仅在AI连接失败时增大，成功时缓慢减小（趋向精简）
    if not scores.get("AI连接", True):
        if STRATEGY["app_load_wait"] < 5.0:
            old = STRATEGY["app_load_wait"]
            STRATEGY["app_load_wait"] = min(5.0, old + 0.5)
            improvements.append(f"app_load_wait↑: {old:.1f}→{STRATEGY['app_load_wait']:.1f}s")
    elif scores.get("AI连接", False) and iteration > 5:
        ai_rate = success_rate("感知/AI连接_streak") if "感知/AI连接_streak" in STATS else 1.0
        if STRATEGY["app_load_wait"] > 1.5:
            old = STRATEGY["app_load_wait"]
            STRATEGY["app_load_wait"] = max(1.5, old - 0.2)
            improvements.append(f"app_load_wait↓: {old:.1f}→{STRATEGY['app_load_wait']:.1f}s")

    # 改进3：AI App按成功率排序（知常·让最可靠的排最前）
    tried = [(n, p) for n, p in STRATEGY["ai_apps"]
             if success_rate(f"app/{p}") + success_rate(f"app_open/{p}") > 0]
    if tried:
        STRATEGY["ai_apps"] = sorted(
            STRATEGY["ai_apps"],
            key=lambda x: success_rate(f"app_open/{x[1]}") * 2 + success_rate(f"app/{x[1]}"),
            reverse=True
        )

    # 改进4：wake_wait自适应（连续5轮全部成功才减少，稳中求精）
    all_ok = all(scores.values())
    if all_ok and iteration % 5 == 0 and STRATEGY["wake_wait"] > 0.3:
        old = STRATEGY["wake_wait"]
        STRATEGY["wake_wait"] = max(0.3, old - 0.05)
        improvements.append(f"wake_wait↓: {old:.2f}→{STRATEGY['wake_wait']:.2f}s")

    # 改进5：场景扩展 — 连续满分5轮后解锁更难场景
    consecutive = STATS.get("_consecutive_perfect", {}).get("ok", 0)
    if all_ok:
        STATS.setdefault("_consecutive_perfect", {"ok": 0, "fail": 0})
        STATS["_consecutive_perfect"]["ok"] += 1
    else:
        STATS["_consecutive_perfect"] = {"ok": 0, "fail": 0}

    cp = STATS.get("_consecutive_perfect", {}).get("ok", 0)
    if cp == 5:
        improvements.append("★解锁扩展：加入多App轮换测试")
        STRATEGY["expand_multi_app"] = True
    if cp == 10:
        improvements.append("★解锁扩展：加入网络压力测试")
        STRATEGY["expand_network"] = True
    if cp == 20:
        improvements.append("★解锁扩展：加入宏链式自动化")
        STRATEGY["expand_macro_chain"] = True

    return improvements

# ═══ 主循环 ═══
def run_loop():
    print(c("\n" + "═"*60, "cyan"))
    print(c("  手机自闭环进化系统 · 永不停止", "bold"))
    print(c("  道之闭环：实践→找问题→改进→循环", "cyan"))
    print(c("═"*60 + "\n", "cyan"))
    print(f"  目标设备: {BASE}")
    print(f"  日志文件: {LOG_FILE}")
    print(f"  停止方式: Ctrl+C\n")

    iteration = 0
    best_score = 0.0
    consecutive_perfect = 0

    try:
        while True:
            iteration += 1
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            print(c(f"\n{'─'*55}", "cyan"))
            print(c(f"  迭代 #{iteration:03d}  [{ts}]", "bold"))
            print(c(f"{'─'*55}", "cyan"))

            iter_results = {}
            iter_scores = {}

            # ── 场景1：感知 ──
            print(f"  {c('①感知', 'yellow')} ", end="", flush=True)
            res, ok = scenario_感知()
            iter_scores["感知"] = ok
            dev_info = res.get("device", {})
            print(c(f"✅ 电量{dev_info.get('battery')}% WiFi{dev_info.get('wifi')}dBm", "green") if ok
                  else c(f"❌ {res}", "red"))
            iter_results["感知"] = res

            # ── 场景2：唤醒解锁 ──
            print(f"  {c('②唤醒解锁', 'yellow')} ", end="", flush=True)
            res, ok = scenario_唤醒解锁()
            iter_scores["唤醒解锁"] = ok
            print(c(f"✅ launcher就绪", "green") if ok else c(f"❌ {res}", "red"))
            iter_results["唤醒解锁"] = res

            # ── 场景3：AI连接 ──
            print(f"  {c('③AI归位', 'yellow')} ", end="", flush=True)
            res, ok = scenario_AI连接()
            iter_scores["AI连接"] = ok
            print(c(f"✅ {res.get('name','?')}已开", "green") if ok
                  else c(f"❌ 所有AI App失败", "red"))
            iter_results["AI连接"] = res

            # ── 场景4：文字输入 ──
            print(f"  {c('④文字输入', 'yellow')} ", end="", flush=True)
            res, ok = scenario_文字输入()
            iter_scores["文字输入"] = ok
            method = res.get("method", "?") if ok else "fail"
            print(c(f"✅ method:{method}", "green") if ok else c(f"❌ {res}", "red"))
            iter_results["文字输入"] = res

            # ── 场景5：宏自动化 ──
            print(f"  {c('⑤宏自动化', 'yellow')} ", end="", flush=True)
            res, ok = scenario_宏自动化()
            iter_scores["宏"] = ok
            print(c(f"✅ steps:{res.get('steps','?')}", "green") if ok
                  else c(f"❌ {res}", "red"))
            iter_results["宏"] = res

            # ── 场景6：万物连接 ──
            print(f"  {c('⑥万物连接', 'yellow')} ", end="", flush=True)
            res, ok = scenario_万物连接()
            iter_scores["万物连接"] = ok
            print(c(f"✅ browser:{res.get('pkg','?').split('.')[-1]}", "green") if ok
                  else c(f"❌ {res}", "red"))
            iter_results["万物连接"] = res

            # ── 评分 ──
            score = sum(iter_scores.values()) / len(iter_scores)
            if score > best_score:
                best_score = score

            if score >= 1.0:
                consecutive_perfect += 1
            else:
                consecutive_perfect = 0

            bar_filled = int(score * 20)
            bar = "█" * bar_filled + "░" * (20 - bar_filled)
            score_color = "green" if score >= 0.8 else "yellow" if score >= 0.5 else "red"
            print(f"\n  本轮得分: {c(f'{score:.0%}', score_color)} [{bar}]  历史最高: {best_score:.0%}")

            # ── 改进 ──
            improvements = improve(iteration, iter_scores, iter_results)
            if improvements:
                print(c(f"  ★ 策略改进: {' | '.join(improvements)}", "cyan"))

            # ── 全局成功率展示（每5轮）──
            if iteration % 5 == 0:
                print(c(f"\n  ── 累积成功率（迭代#{iteration}） ──", "bold"))
                for k, v in sorted(STATS.items()):
                    total = v["ok"] + v["fail"]
                    rate = v["ok"] / total
                    bar2 = "█" * int(rate * 10) + "░" * (10 - int(rate * 10))
                    col = "green" if rate >= 0.8 else "yellow" if rate >= 0.5 else "red"
                    print(f"    {k:<30} {c(f'{rate:.0%}', col)} [{bar2}] ({v['ok']}/{total})")

            # ── 记录日志 ──
            log_entry = {
                "ts": ts, "iter": iteration, "score": score,
                "scores": iter_scores, "strategy": {
                    "unlock_ny": STRATEGY["unlock_ny"],
                    "app_load_wait": STRATEGY["app_load_wait"],
                    "wake_wait": STRATEGY["wake_wait"],
                },
                "improvements": improvements,
                "results": {k: str(v)[:200] for k, v in iter_results.items()}
            }
            log_jsonl(log_entry)

            # ── 连续满分提示 ──
            if consecutive_perfect >= 3:
                print(c(f"\n  ✦ 连续{consecutive_perfect}轮满分！策略已收敛，继续守护...", "green"))

            # ── 间隔（按当前状态自适应）──
            wait = 8 if score >= 0.8 else 5 if score >= 0.5 else 3
            print(c(f"\n  [{ts}] 下轮将在 {wait}s 后开始...  [Ctrl+C 停止]", "cyan"))
            time.sleep(wait)

    except KeyboardInterrupt:
        print(c("\n\n" + "═"*55, "cyan"))
        print(c("  闭环停止 · 道统蒸馏 · 归根复命", "bold"))
        print(c("═"*55, "cyan"))
        print(f"\n  完成迭代: {iteration}  历史最高得分: {best_score:.0%}")
        print(f"  策略收敛状态:")
        print(f"    unlock_ny    = {STRATEGY['unlock_ny']:.2f}")
        print(f"    app_load_wait= {STRATEGY['app_load_wait']:.1f}s")
        print(f"    wake_wait    = {STRATEGY['wake_wait']:.1f}s")
        print(f"    AI优先级     = {[n for n,_ in STRATEGY['ai_apps']]}")
        print(f"\n  累积统计（前10项）:")
        top = sorted(STATS.items(), key=lambda x: x[1]["ok"] + x[1]["fail"], reverse=True)[:10]
        for k, v in top:
            total = v["ok"] + v["fail"]
            print(f"    {k:<30} {v['ok']}/{total} ({v['ok']/total:.0%})")
        print(c(f"\n  日志已保存: {LOG_FILE}", "cyan"))
        print(c("\n  彼且恶乎待电脑之呼哉！\n", "bold"))


if __name__ == "__main__":
    run_loop()
