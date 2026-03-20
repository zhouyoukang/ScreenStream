#!/usr/bin/env python3
"""
Windsurf 账号一键切换器 v1.0
==============================
关闭Windsurf → 重置设备指纹 → 清除认证缓存 → 提示登录新账号

用法:
  python switch_account.py                    # 自动切换到下一个可用账号
  python switch_account.py EMAIL              # 切换到指定账号
  python switch_account.py --status           # 查看当前状态
  python switch_account.py --mark-cool EMAIL  # 标记当前账号冷却
"""

import os, sys, json, uuid, hashlib, sqlite3, subprocess, time
from pathlib import Path
from datetime import datetime, timezone, timedelta

# 路径
WS_APPDATA = Path(os.environ.get('APPDATA', '')) / 'Windsurf'
WS_STORAGE = WS_APPDATA / 'User' / 'globalStorage' / 'storage.json'
WS_STATE_DB = WS_APPDATA / 'User' / 'globalStorage' / 'state.vscdb'
POOL_FILE = Path(__file__).parent / '_account_pool.json'

def load_pool():
    if POOL_FILE.exists():
        return json.loads(POOL_FILE.read_text('utf-8'))
    print('❌ 账号池不存在，先运行: python windsurf_account_pool.py --init')
    sys.exit(1)

def save_pool(pool):
    POOL_FILE.write_text(json.dumps(pool, indent=2, ensure_ascii=False), 'utf-8')

def kill_windsurf():
    """关闭所有Windsurf进程"""
    try:
        out = subprocess.check_output(
            'tasklist /fi "IMAGENAME eq Windsurf.exe" /fo csv /nh',
            shell=True, encoding='utf-8', errors='replace'
        )
        if 'Windsurf.exe' not in out:
            print('  ✅ Windsurf未运行')
            return True
        print('  🔄 正在关闭Windsurf...')
        subprocess.run('taskkill /F /IM Windsurf.exe', shell=True,
                       capture_output=True, timeout=10)
        time.sleep(2)
        # 验证
        out2 = subprocess.check_output(
            'tasklist /fi "IMAGENAME eq Windsurf.exe" /fo csv /nh',
            shell=True, encoding='utf-8', errors='replace'
        )
        if 'Windsurf.exe' not in out2:
            print('  ✅ Windsurf已关闭')
            return True
        print('  ⚠️ 部分进程仍在运行')
        return True
    except Exception as e:
        print(f'  ❌ 关闭失败: {e}')
        return False

def reset_fingerprint():
    """重置5维设备指纹"""
    if not WS_STORAGE.exists():
        print('  ⚠️ storage.json不存在，跳过指纹重置')
        return {}
    try:
        data = json.loads(WS_STORAGE.read_text('utf-8'))
    except:
        data = {}

    fp = {
        "telemetry.machineId": hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
        "telemetry.macMachineId": hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
        "telemetry.devDeviceId": str(uuid.uuid4()),
        "telemetry.sqmId": str(uuid.uuid4()).replace('-', ''),
        "storage.serviceMachineId": str(uuid.uuid4())
    }
    for k, v in fp.items():
        data[k] = v
    WS_STORAGE.write_text(json.dumps(data, indent=2), 'utf-8')
    print(f'  ✅ 5维指纹已重置')
    return fp

def clear_auth_cache():
    """清除state.vscdb认证缓存"""
    if not WS_STATE_DB.exists():
        print('  ⚠️ state.vscdb不存在')
        return
    try:
        conn = sqlite3.connect(str(WS_STATE_DB))
        keys = ['windsurfAuthStatus', 'windsurf.settings.cachedPlanInfo']
        for key in keys:
            conn.execute("DELETE FROM ItemTable WHERE key=?", (key,))
        conn.commit()
        conn.close()
        print(f'  ✅ 认证缓存已清除({len(keys)}个键)')
    except Exception as e:
        print(f'  ❌ 清除缓存失败: {e}')

def is_cooling(acc):
    if not acc.get("cooldown_until"):
        return False
    try:
        cd = datetime.fromisoformat(acc["cooldown_until"])
        return datetime.now(timezone.utc) < cd
    except:
        return False

def cooldown_mins(acc):
    if not acc.get("cooldown_until"):
        return 0
    try:
        cd = datetime.fromisoformat(acc["cooldown_until"])
        return max(0, (cd - datetime.now(timezone.utc)).total_seconds() / 60)
    except:
        return 0

def get_next(pool):
    """获取下一个可用账号"""
    available = [a for a in pool["accounts"]
                 if not is_cooling(a) and a["status"] != "disabled"]
    if not available:
        return None
    # 优先未测试
    untested = [a for a in available if a["status"] == "untested"]
    if untested:
        return untested[0]
    # 最久未用
    available.sort(key=lambda a: a.get("last_used") or "2000-01-01")
    return available[0]

def show_status(pool):
    """简洁显示当前状态"""
    current = pool.get("current", "无")
    available = sum(1 for a in pool["accounts"]
                    if not is_cooling(a) and a["status"] != "disabled")
    cooling = sum(1 for a in pool["accounts"] if is_cooling(a))
    total = len(pool["accounts"])

    print(f'\n📊 账号池: {available}可用 / {cooling}冷却 / {total}总计')
    print(f'   当前: {current}')

    # 检查Windsurf
    try:
        out = subprocess.check_output(
            'tasklist /fi "IMAGENAME eq Windsurf.exe" /fo csv /nh',
            shell=True, encoding='utf-8', errors='replace'
        )
        running = 'Windsurf.exe' in out
        print(f'   Windsurf: {"🟢运行中" if running else "⚫未运行"}')
    except:
        pass

    # 即将恢复的冷却账号
    cooling_accs = [(a, cooldown_mins(a)) for a in pool["accounts"] if is_cooling(a)]
    cooling_accs.sort(key=lambda x: x[1])
    if cooling_accs:
        print(f'\n   冷却中:')
        for acc, mins in cooling_accs[:5]:
            print(f'     🔴 {acc["email"][:35]} — {mins:.0f}分钟后恢复')

def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--status':
        pool = load_pool()
        show_status(pool)
        return 0

    if len(sys.argv) > 1 and sys.argv[1] == '--mark-cool':
        pool = load_pool()
        email = sys.argv[2] if len(sys.argv) > 2 else pool.get("current")
        mins = int(sys.argv[3]) if len(sys.argv) > 3 else 120
        if not email:
            print('❌ 请指定邮箱')
            return 1
        for acc in pool["accounts"]:
            if acc["email"] == email:
                acc["cooldown_until"] = (
                    datetime.now(timezone.utc) + timedelta(minutes=mins)
                ).isoformat()
                acc["status"] = "cooling"
                save_pool(pool)
                print(f'✅ {email} 已标记冷却 {mins} 分钟')
                return 0
        print(f'❌ 未找到 {email}')
        return 1

    pool = load_pool()

    # 确定目标账号
    if len(sys.argv) > 1 and not sys.argv[1].startswith('--'):
        target_email = sys.argv[1]
        target = None
        for acc in pool["accounts"]:
            if acc["email"] == target_email:
                target = acc
                break
        if not target:
            print(f'❌ 账号 {target_email} 不在池中')
            return 1
        if is_cooling(target):
            print(f'⚠️ {target_email} 冷却中，剩余 {cooldown_mins(target):.0f} 分钟')
            return 1
    else:
        target = get_next(pool)
        if not target:
            print('❌ 没有可用账号！全部冷却中')
            cooling_accs = [(a, cooldown_mins(a)) for a in pool["accounts"] if is_cooling(a)]
            cooling_accs.sort(key=lambda x: x[1])
            if cooling_accs:
                print(f'   最快恢复: {cooling_accs[0][0]["email"]} ({cooling_accs[0][1]:.0f}分钟后)')
            return 1

    # 标记当前账号冷却(如果有)
    current_email = pool.get("current")
    if current_email:
        for acc in pool["accounts"]:
            if acc["email"] == current_email and acc["status"] == "active":
                acc["cooldown_until"] = (
                    datetime.now(timezone.utc) + timedelta(hours=2)
                ).isoformat()
                acc["status"] = "cooling"
                print(f'  📌 旧账号 {current_email[:30]} 标记冷却2h')

    print(f'\n🔄 切换到: {target["email"]}')
    print('=' * 50)

    # Step 1: 关闭Windsurf
    print('\n[1/4] 关闭Windsurf')
    kill_windsurf()

    # Step 2: 重置指纹
    print('\n[2/4] 重置设备指纹')
    fp = reset_fingerprint()

    # Step 3: 清除缓存
    print('\n[3/4] 清除认证缓存')
    clear_auth_cache()

    # Step 4: 更新池状态
    print('\n[4/4] 更新账号池')
    target["last_used"] = datetime.now(timezone.utc).isoformat()
    target["status"] = "active"
    pool["current"] = target["email"]
    pool["history"] = pool.get("history", [])
    pool["history"].append({
        "action": "switch",
        "email": target["email"],
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    if len(pool["history"]) > 100:
        pool["history"] = pool["history"][-100:]
    save_pool(pool)

    print(f'\n{"=" * 50}')
    print(f'✅ 切换完成！请启动Windsurf并登录:')
    print(f'   邮箱: {target["email"]}')
    print(f'   密码: {target["password"]}')
    print(f'\n   提示: 登录后如遇限速，运行:')
    print(f'   python switch_account.py --mark-cool {target["email"]}')
    print(f'   python switch_account.py')
    return 0

if __name__ == '__main__':
    sys.exit(main())
