"""
远程操控一键启动 — 从零到五感全开
====================================
自动完成: 发现设备→建立连接→验证五感→启动心跳守护→输出Web UI链接

使用:
  python remote_setup.py                    # 自动发现
  python remote_setup.py --host 192.168.31.100  # 指定WiFi IP
  python remote_setup.py --tailscale        # 通过Tailscale
  python remote_setup.py --heartbeat 30     # 带心跳守护
"""

import argparse, json, sys, time
from phone_lib import Phone, discover, NegativeState, _adb, _get_phone_wifi_ip, _get_phone_tailscale_ip, _probe, log


def setup_adb_forward(serial=None):
    """确保ADB端口转发就绪"""
    args = ["devices"]
    out, ok = _adb(*args)
    if not ok:
        return None, "ADB不可用"

    devices = [l.split("\t")[0] for l in out.splitlines() if "\tdevice" in l]
    if not devices:
        return None, "无ADB设备"

    target = serial or devices[0]
    # 检查已有转发
    fwd_out, _ = _adb("forward", "--list")
    for port in range(8080, 8100):
        if f"tcp:{port}" in fwd_out and f"tcp:{port}" in fwd_out:
            if _probe(f"http://127.0.0.1:{port}"):
                return port, f"已有转发 :{port}"

    # 尝试建立新转发
    for port in range(8080, 8100):
        _adb("-s", target, "forward", f"tcp:{port}", f"tcp:{port}")
        time.sleep(0.5)
        if _probe(f"http://127.0.0.1:{port}"):
            return port, f"新建转发 :{port}"

    return None, "端口转发失败"


def setup_wifi_adb(serial=None):
    """启用WiFi ADB（断USB后仍可连）"""
    wifi_ip = _get_phone_wifi_ip()
    if not wifi_ip:
        return None, "无法获取手机WiFi IP"

    out, _ = _adb("devices")
    devices = [l.split("\t")[0] for l in out.splitlines() if "\tdevice" in l]
    target = serial or (devices[0] if devices else None)
    if not target:
        return None, "无ADB设备"

    _adb("-s", target, "tcpip", "5555")
    time.sleep(2)
    _adb("connect", f"{wifi_ip}:5555")
    time.sleep(1)

    return wifi_ip, f"WiFi ADB: {wifi_ip}:5555"


def verify_five_senses(phone):
    """验证五感全部可用，返回 {sense: (ok, detail)}"""
    results = {}

    # 👁 视觉
    try:
        texts, pkg = phone.read()
        results["vision"] = (True, f"前台:{pkg}, 文本:{len(texts)}条")
    except Exception as e:
        results["vision"] = (False, str(e))

    # 👂 听觉
    try:
        dev = phone.device()
        vol = dev.get("volumeMusic", -1)
        results["hearing"] = (vol >= 0, f"音量:{vol}")
    except Exception as e:
        results["hearing"] = (False, str(e))

    # 🖐 触觉
    try:
        s = phone.status()
        enabled = s.get("inputEnabled", False)
        results["touch"] = (enabled, f"inputEnabled={enabled}")
    except Exception as e:
        results["touch"] = (False, str(e))

    # 👃 嗅觉（通知）
    try:
        n = phone.notifications(5)
        count = n.get("total", 0)
        results["smell"] = (True, f"通知:{count}条")
    except Exception as e:
        results["smell"] = (False, str(e))

    # 👅 味觉（状态）
    try:
        dev = phone.device()
        battery = dev.get("batteryLevel", -1)
        net = dev.get("networkType", "?")
        results["taste"] = (battery >= 0, f"电量:{battery}%, 网络:{net}")
    except Exception as e:
        results["taste"] = (False, str(e))

    return results


def print_banner(phone, senses, wifi_ip=None):
    """输出连接信息面板"""
    from urllib.parse import urlparse
    parsed = urlparse(phone.base)
    host = parsed.hostname
    port = parsed.port

    print("\n" + "=" * 60)
    print("  📱 远程手机操控 — 连接成功")
    print("=" * 60)
    print(f"  连接模式: {phone._connection_mode}")
    print(f"  API地址:  {phone.base}")
    if wifi_ip:
        print(f"  WiFi IP:  {wifi_ip}")

    # Web UI 链接
    if host and host != "127.0.0.1":
        print(f"\n  🌐 Web UI (远程):")
        print(f"     http://{host}:8081")
    else:
        print(f"\n  🌐 Web UI (本地):")
        print(f"     http://127.0.0.1:8081")
        if wifi_ip:
            print(f"  🌐 Web UI (WiFi):")
            print(f"     http://{wifi_ip}:8081")

    print(f"\n  五感状态:")
    icons = {"vision": "👁", "hearing": "👂", "touch": "🖐", "smell": "👃", "taste": "👅"}
    names = {"vision": "视觉", "hearing": "听觉", "touch": "触觉", "smell": "嗅觉", "taste": "味觉"}
    all_ok = True
    for sense, (ok, detail) in senses.items():
        icon = icons.get(sense, "?")
        name = names.get(sense, sense)
        status = "✅" if ok else "❌"
        print(f"     {icon} {name}: {status} {detail}")
        if not ok:
            all_ok = False

    if all_ok:
        print(f"\n  ✅ 五感全开，远程操控就绪！")
    else:
        print(f"\n  ⚠️ 部分感官受限，请检查上述失败项")

    print("=" * 60)

    # Python使用示例
    print(f"\n  📝 Python使用:")
    if host and host != "127.0.0.1":
        print(f'     from phone_lib import Phone')
        print(f'     p = Phone(host="{host}", port={port})')
    else:
        print(f'     from phone_lib import Phone')
        print(f'     p = Phone(port={port})')
    print(f'     p.senses()       # 五感全采集')
    print(f'     p.ensure_alive() # 确保连接+自动恢复')
    print()


def main():
    parser = argparse.ArgumentParser(description="远程手机操控一键启动")
    parser.add_argument("--host", help="手机IP地址")
    parser.add_argument("--port", type=int, default=8086, help="ScreenStream端口")
    parser.add_argument("--url", help="完整URL (公网穿透)")
    parser.add_argument("--tailscale", action="store_true", help="通过Tailscale连接")
    parser.add_argument("--heartbeat", type=int, default=0, help="心跳间隔(秒)")
    parser.add_argument("--wifi-adb", action="store_true", help="启用WiFi ADB")
    parser.add_argument("--no-recover", action="store_true", help="跳过自动恢复")
    parser.add_argument("--json", action="store_true", help="JSON格式输出")
    args = parser.parse_args()

    wifi_ip = None

    # Phase 1: 建立连接
    if args.tailscale:
        ts_ip = _get_phone_tailscale_ip()
        if ts_ip:
            args.host = ts_ip
            log.info(f"Tailscale IP: {ts_ip}")
        else:
            print("❌ 未找到Tailscale IP")
            sys.exit(1)

    if args.wifi_adb:
        wifi_ip, msg = setup_wifi_adb()
        log.info(msg)

    if not args.host and not args.url:
        # 自动发现
        port, msg = setup_adb_forward()
        if port:
            log.info(msg)
        wifi_ip = _get_phone_wifi_ip()

    # Phase 2: 创建Phone实例
    phone = Phone(
        host=args.host,
        port=args.port,
        url=args.url,
        heartbeat_sec=args.heartbeat,
    )

    # Phase 3: 确保可用
    if not args.no_recover:
        alive, recovery_log = phone.ensure_alive()
        if recovery_log:
            for line in recovery_log:
                log.info(line)
        if not alive:
            print("❌ 手机不可达，自动恢复失败")
            if args.json:
                print(json.dumps({"ok": False, "log": recovery_log}, ensure_ascii=False))
            sys.exit(1)

    # Phase 4: 验证五感
    senses = verify_five_senses(phone)

    if args.json:
        output = {
            "ok": True,
            "base": phone.base,
            "mode": phone._connection_mode,
            "has_adb": phone._has_adb,
            "senses": {k: {"ok": v[0], "detail": v[1]} for k, v in senses.items()},
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print_banner(phone, senses, wifi_ip)

    # Phase 5: 交互模式（心跳守护时保持运行）
    if args.heartbeat > 0:
        print(f"  🔄 心跳守护运行中 (每{args.heartbeat}秒)，Ctrl+C退出")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n  👋 已停止")


if __name__ == "__main__":
    main()
