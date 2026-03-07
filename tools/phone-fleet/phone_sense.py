"""手机五感探针 — Agent 直连入口
================================
台式机本地运行，无需 Z: 盘。自动发现 OPPO PEAM00，五感全采集，输出结构化状态。
ADB路径自动检测 D:\\scrcpy\\scrcpy-win64-v3.1\\adb.exe

用法:
  python phone_sense.py                # 五感全采集（人类可读）
  python phone_sense.py --json         # JSON输出（供Agent读取）
  python phone_sense.py --heal         # 检查+自动修复所有负面状态
  python phone_sense.py --wake         # 唤醒屏幕
  python phone_sense.py --connect      # 仅做连接验证
  python phone_sense.py --forward      # 建立端口转发（USB模式）
"""
import sys, os, json, argparse, subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from phone_lib import Phone, discover, NegativeState, _find_adb, _adb

ADB = _find_adb() or "adb"
SERIAL = "KBVSEI4XZDQOKFFE"  # OPPO PEAM00


def do_forward():
    """建立端口转发 — USB直连必须"""
    print("🔌 建立端口转发...", flush=True)
    r1 = subprocess.run([ADB, "-s", SERIAL, "forward", "tcp:8084", "tcp:8084"],
                        capture_output=True, text=True)
    r2 = subprocess.run([ADB, "-s", SERIAL, "forward", "tcp:18080", "tcp:8080"],
                        capture_output=True, text=True)
    if r1.returncode == 0:
        print("  ✅ tcp:8084↔8084 (InputService API)")
        print("  ✅ tcp:18080↔8080 (投屏Web)")
    else:
        print(f"  ⚠️  转发失败: {r1.stderr.strip()}")


def main():
    parser = argparse.ArgumentParser(description="手机五感探针")
    parser.add_argument("--json", action="store_true", help="JSON输出(供Agent读取)")
    parser.add_argument("--heal", action="store_true", help="检查+自动修复负面状态")
    parser.add_argument("--wake", action="store_true", help="唤醒屏幕")
    parser.add_argument("--connect", action="store_true", help="仅连接验证")
    parser.add_argument("--forward", action="store_true", help="建立ADB端口转发")
    args = parser.parse_args()

    if args.forward:
        do_forward()

    print("🔍 发现手机...", flush=True)
    p = Phone(auto_discover=True)
    print(f"✅ 连接: {p.base}  模式: {p._connection_mode}  ADB: {'有' if p._has_adb else '无'}")

    if args.connect:
        s = p.status()
        print(f"📱 /status: connected={s.get('connected')}  inputEnabled={s.get('inputEnabled')}")
        return

    if args.wake:
        p.wake()
        print("⚡ 已唤醒屏幕")

    if args.heal:
        print("🩺 检查 + 自动修复所有负面状态...")
        ok, recovery_log = p.ensure_alive()
        for line in recovery_log:
            print(f"  {line}")
        if not ok:
            print("❌ 无法恢复，请检查手机连接")
            sys.exit(1)
        print("✅ 手机状态健康")
        if not args.json:
            return

    # ── 五感采集 ──────────────────────────────────────────
    print("\n🖐️  五感采集中...", flush=True)
    s = p.senses()

    if args.json:
        print(json.dumps(s, ensure_ascii=False, indent=2))
        return

    # 人类可读输出
    v  = s.get("vision", {})
    h  = s.get("hearing", {})
    t  = s.get("touch", {})
    sm = s.get("smell", {})
    ta = s.get("taste", {})

    print(f"\n{'='*55}")
    print(f"  📱 OPPO PEAM00  五感报告")
    print(f"{'='*55}")

    fg_short = v.get("foreground_app", "?").split(".")[-1]
    print(f"👁  视觉  前台={fg_short}  文本={v.get('text_count',0)}条  "
          f"可点击={v.get('clickable_count',0)}个")
    texts = v.get("screen_texts", [])
    if texts:
        print(f"   文本摘要: {' | '.join(str(x) for x in texts[:6])}")

    print(f"👂 听觉  媒体音量={h.get('volume_music','?')}  "
          f"响铃={h.get('volume_ring','?')}  "
          f"免打扰={'开' if h.get('dnd') else '关'}")

    a11y_ok = t.get("input_enabled", False)
    print(f"🖐  触觉  无障碍={'✅启用' if a11y_ok else '❌断开'}  "
          f"息屏={'是' if t.get('screen_off') else '否'}")

    notif_count = sm.get("notification_count", 0)
    print(f"👃 嗅觉  通知={notif_count}条")
    for n in sm.get("recent", [])[:3]:
        print(f"   [{n.get('app','?')}] {n.get('title','')}")

    bat = ta.get("battery", "?")
    charging = ta.get("charging", False)
    print(f"👅 味觉  电量={bat}%{'⚡' if charging else ''}  "
          f"网络={ta.get('network','?')}  "
          f"存储剩余={ta.get('storage_free_gb','?')}GB")
    print(f"   型号={ta.get('model','?')}  WiFi={ta.get('wifi_ssid','?')}")

    print(f"{'='*55}")
    status_ok = s.get("_ok", False)
    print(f"总状态: {'✅ 健康' if status_ok else '⚠️  异常，建议 --heal'}")

    if not a11y_ok:
        print("\n⚠️  无障碍服务断开！运行以下命令恢复：")
        print(f"  python phone_sense.py --heal")

    print(f"\n💡 Agent快捷调用:")
    print(f"  from phone_lib import Phone")
    print(f"  p = Phone()  # 自动发现 {p.base}")
    print(f"  texts, pkg = p.read()   # 读屏幕")
    print(f"  p.click('目标文字')      # 点击")
    print(f"  p.senses()              # 五感全采集")


if __name__ == "__main__":
    main()
