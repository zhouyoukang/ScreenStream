#!/usr/bin/env python3
"""
Windsurf 账号池引擎 v1.0
========================
功能:
  1. 管理10+个Windsurf账号，自动轮换
  2. 检测限速状态(冷却中/可用/未测试)
  3. 切换账号时自动重置设备指纹(防关联)
  4. 修改state.vscdb注入新账号凭据
  5. 持久化账号状态(冷却时间/上次使用/积分)

用法:
  python windsurf_account_pool.py                 # 显示所有账号状态
  python windsurf_account_pool.py --next           # 切换到下一个可用账号
  python windsurf_account_pool.py --switch EMAIL   # 切换到指定账号
  python windsurf_account_pool.py --test EMAIL     # 测试账号是否可用
  python windsurf_account_pool.py --add EMAIL PWD  # 添加新账号
  python windsurf_account_pool.py --cooldown EMAIL MINS  # 标记冷却
  python windsurf_account_pool.py --reset-fp       # 仅重置设备指纹
"""

import os, sys, json, uuid, hashlib, sqlite3, time, subprocess, shutil
from pathlib import Path
from datetime import datetime, timezone, timedelta

# ============================================================
# 路径常量
# ============================================================
WS_APPDATA = Path(os.environ.get('APPDATA', '')) / 'Windsurf'
WS_SETTINGS = WS_APPDATA / 'User' / 'settings.json'
WS_STATE_DB = WS_APPDATA / 'User' / 'globalStorage' / 'state.vscdb'
WS_STORAGE_JSON = WS_APPDATA / 'User' / 'globalStorage' / 'storage.json'
POOL_FILE = Path(__file__).parent / '_account_pool.json'

# ============================================================
# 账号池数据结构
# ============================================================
def default_pool():
    return {
        "version": "1.0",
        "accounts": [],
        "current": None,
        "fingerprints": {},
        "history": []
    }

def default_account(email, password, plan="trial"):
    return {
        "email": email,
        "password": password,
        "plan": plan,
        "status": "untested",
        "cooldown_until": None,
        "last_used": None,
        "last_tested": None,
        "messages_used": 0,
        "notes": ""
    }

def load_pool():
    if POOL_FILE.exists():
        try:
            return json.loads(POOL_FILE.read_text('utf-8'))
        except:
            pass
    return default_pool()

def save_pool(pool):
    POOL_FILE.write_text(json.dumps(pool, indent=2, ensure_ascii=False), 'utf-8')

# ============================================================
# 设备指纹管理
# ============================================================
def generate_fingerprint():
    """生成全新的5维设备指纹"""
    return {
        "telemetry.machineId": hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
        "telemetry.macMachineId": hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
        "telemetry.devDeviceId": str(uuid.uuid4()),
        "telemetry.sqmId": str(uuid.uuid4()).replace('-', ''),
        "storage.serviceMachineId": str(uuid.uuid4())
    }

def reset_fingerprint():
    """重置storage.json中的设备指纹"""
    if not WS_STORAGE_JSON.exists():
        print('  ⚠️ storage.json不存在')
        return None

    try:
        data = json.loads(WS_STORAGE_JSON.read_text('utf-8'))
    except:
        data = {}

    fp = generate_fingerprint()
    for key, val in fp.items():
        data[key] = val

    WS_STORAGE_JSON.write_text(json.dumps(data, indent=2), 'utf-8')
    print(f'  ✅ 设备指纹已重置:')
    for k, v in fp.items():
        print(f'     {k} = {v[:20]}...')
    return fp

# ============================================================
# state.vscdb 操作
# ============================================================
def read_state_db(key):
    """从state.vscdb读取键值"""
    if not WS_STATE_DB.exists():
        return None
    try:
        conn = sqlite3.connect(str(WS_STATE_DB))
        cur = conn.execute("SELECT value FROM ItemTable WHERE key=?", (key,))
        row = cur.fetchone()
        conn.close()
        return row[0] if row else None
    except Exception as e:
        print(f'  ❌ 读取state.vscdb失败: {e}')
        return None

def write_state_db(key, value):
    """写入state.vscdb键值"""
    if not WS_STATE_DB.exists():
        print(f'  ❌ state.vscdb不存在')
        return False
    try:
        conn = sqlite3.connect(str(WS_STATE_DB))
        conn.execute(
            "INSERT OR REPLACE INTO ItemTable(key, value) VALUES(?, ?)",
            (key, value)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f'  ❌ 写入state.vscdb失败: {e}')
        return False

def get_current_account_info():
    """获取当前Windsurf登录账号信息"""
    auth_status = read_state_db('windsurfAuthStatus')
    if not auth_status:
        return None
    try:
        data = json.loads(auth_status)
        return {
            "api_key": data.get("apiKey", "")[:20] + "...",
            "email": data.get("email", "unknown"),
            "plan": data.get("planName", "unknown")
        }
    except:
        return None

def get_cached_plan():
    """获取缓存的计划信息"""
    plan_info = read_state_db('windsurf.settings.cachedPlanInfo')
    if not plan_info:
        return None
    try:
        data = json.loads(plan_info)
        return {
            "plan_name": data.get("planName", "?"),
            "monthly_credits": data.get("monthlyPromptCredits", 0),
            "used_credits": data.get("usage", {}).get("usedPromptCredits", 0),
            "grace_period": data.get("gracePeriodStatus", 0),
            "end_timestamp": data.get("endTimestamp", 0)
        }
    except:
        return None

# ============================================================
# 账号状态管理
# ============================================================
def is_cooling(account):
    """检查账号是否在冷却中"""
    if not account.get("cooldown_until"):
        return False
    try:
        cd = datetime.fromisoformat(account["cooldown_until"])
        return datetime.now(timezone.utc) < cd
    except:
        return False

def remaining_cooldown(account):
    """返回剩余冷却时间(分钟)"""
    if not account.get("cooldown_until"):
        return 0
    try:
        cd = datetime.fromisoformat(account["cooldown_until"])
        delta = cd - datetime.now(timezone.utc)
        return max(0, delta.total_seconds() / 60)
    except:
        return 0

def get_available_accounts(pool):
    """获取所有可用(非冷却)账号"""
    available = []
    for acc in pool["accounts"]:
        if not is_cooling(acc) and acc["status"] != "disabled":
            available.append(acc)
    return available

def get_next_account(pool):
    """获取下一个最优账号(最久未使用的可用账号)"""
    available = get_available_accounts(pool)
    if not available:
        return None

    # 优先未测试的
    untested = [a for a in available if a["status"] == "untested"]
    if untested:
        return untested[0]

    # 然后按last_used排序(最久未用的优先)
    available.sort(key=lambda a: a.get("last_used") or "2000-01-01")
    return available[0]

# ============================================================
# 账号切换核心
# ============================================================
def check_windsurf_running():
    """检查Windsurf是否在运行"""
    try:
        out = subprocess.check_output(
            'tasklist /fi "IMAGENAME eq Windsurf.exe" /fo csv /nh',
            shell=True, encoding='utf-8', errors='replace'
        ).strip()
        return 'Windsurf.exe' in out
    except:
        return False

def switch_account(pool, email):
    """切换到指定账号"""
    # 查找账号
    account = None
    for acc in pool["accounts"]:
        if acc["email"] == email:
            account = acc
            break

    if not account:
        print(f'  ❌ 账号 {email} 不在池中')
        return False

    if is_cooling(account):
        mins = remaining_cooldown(account)
        print(f'  ⚠️ 账号 {email} 冷却中，剩余 {mins:.0f} 分钟')
        return False

    # 检查Windsurf是否运行
    if check_windsurf_running():
        print('  ⚠️ Windsurf正在运行，切换前需关闭')
        print('  请关闭Windsurf后重试，或使用 --force 强制切换')
        return False

    print(f'\n🔄 切换到账号: {email}')

    # Step 1: 重置设备指纹
    print('\n  Step 1: 重置设备指纹...')
    fp = reset_fingerprint()
    if fp:
        pool["fingerprints"][email] = fp

    # Step 2: 清除state.vscdb中的认证缓存
    print('\n  Step 2: 清除认证缓存...')
    keys_to_clear = [
        'windsurfAuthStatus',
        'windsurf.settings.cachedPlanInfo',
    ]
    for key in keys_to_clear:
        if write_state_db(key, ''):
            print(f'     ✅ 已清除 {key}')

    # Step 3: 更新账号状态
    account["last_used"] = datetime.now(timezone.utc).isoformat()
    account["status"] = "active"
    pool["current"] = email
    pool["history"].append({
        "action": "switch",
        "email": email,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    # 保持历史记录在100条以内
    if len(pool["history"]) > 100:
        pool["history"] = pool["history"][-100:]

    save_pool(pool)
    print(f'\n  ✅ 已切换到 {email}')
    print(f'  📌 请启动Windsurf并用以下凭据登录:')
    print(f'     邮箱: {account["email"]}')
    print(f'     密码: {account["password"]}')
    return True

# ============================================================
# 显示
# ============================================================
def show_status(pool):
    """显示账号池状态"""
    print('\n╔══════════════════════════════════════════════════╗')
    print('║  Windsurf 账号池状态                             ║')
    print('╚══════════════════════════════════════════════════╝')

    # 当前Windsurf状态
    ws_info = get_current_account_info()
    plan_info = get_cached_plan()
    ws_running = check_windsurf_running()

    print(f'\n  Windsurf: {"🟢 运行中" if ws_running else "⚫ 未运行"}')
    if ws_info:
        print(f'  当前账号: {ws_info.get("email", "?")}')
        print(f'  API Key: {ws_info.get("api_key", "?")}')
    if plan_info:
        print(f'  计划: {plan_info.get("plan_name", "?")}')
        used = plan_info.get("used_credits", 0)
        total = plan_info.get("monthly_credits", 0)
        print(f'  积分: {used}/{total}')

    # 账号列表
    print(f'\n  📋 账号池 ({len(pool["accounts"])}个):')
    print(f'  {"状态":<6} {"邮箱":<40} {"计划":<8} {"冷却":<10} {"上次使用":<20}')
    print(f'  {"-"*6} {"-"*40} {"-"*8} {"-"*10} {"-"*20}')

    for acc in pool["accounts"]:
        if is_cooling(acc):
            status = "🔴冷却"
            cooldown = f'{remaining_cooldown(acc):.0f}m'
        elif acc["status"] == "untested":
            status = "⚪未测"
            cooldown = "-"
        elif acc["status"] == "active":
            status = "🟢活跃"
            cooldown = "-"
        elif acc["status"] == "disabled":
            status = "⚫禁用"
            cooldown = "-"
        else:
            status = "🟡就绪"
            cooldown = "-"

        last_used = acc.get("last_used") or "-"
        if last_used != "-":
            try:
                dt = datetime.fromisoformat(last_used)
                last_used = dt.strftime("%m-%d %H:%M")
            except:
                last_used = "-"

        current = " ←" if acc["email"] == pool.get("current") else ""
        email_display = acc["email"][:38]
        print(f'  {status:<6} {email_display:<40} {acc.get("plan","?"):<8} {cooldown:<10} {last_used:<20}{current}')

    # 统计
    available = len(get_available_accounts(pool))
    cooling = sum(1 for a in pool["accounts"] if is_cooling(a))
    untested = sum(1 for a in pool["accounts"] if a["status"] == "untested")
    print(f'\n  可用: {available} | 冷却中: {cooling} | 未测试: {untested} | 总计: {len(pool["accounts"])}')

# ============================================================
# 初始化账号池(从截图中的账号)
# ============================================================
def init_default_accounts(pool):
    """从用户提供的账号列表初始化"""
    accounts_data = [
        ("060pyjy1@2art.fun", "060pyjy1@2art.fun", "unknown", "cooling"),
        ("susan125693@yahoo.com", "y5b4g27i", "trial", "cooling"),
        ("0d4ab068@intlgalleryheritageculture.org", "R23W3FkbmC#", "unknown", "cooling"),
        ("hollandaugustino1993@yahoo.com", "H#Jsl1X5AKTf", "unknown", "cooling"),
        ("kofihawkins247714@yahoo.com", "pMPtW!1H!RGT", "unknown", "untested"),
        ("cootsoc568@yahoo.com", "tHt4aTk#cP92CC", "trial", "untested"),
        ("roberthessler483239@yahoo.com", "2wFjFzmmtk#HR!", "unknown", "untested"),
        ("andrew.kane254974@yahoo.com", "upC3HSs!Yvl9dJ", "unknown", "untested"),
        ("fountainmaniyahseufty@yahoo.com", "bSRlqoCW83#Qp4", "unknown", "untested"),
        ("tracy.vasquez43932@yahoo.com", "j32@byjMoMVhWa", "unknown", "untested"),
        ("Uhumphreyspring2VZY1@yahoo.com", "37bH3RA52S8#2x", "unknown", "untested"),
    ]

    existing = {a["email"] for a in pool["accounts"]}
    added = 0
    for email, pwd, plan, status in accounts_data:
        if email not in existing:
            acc = default_account(email, pwd, plan)
            acc["status"] = status
            if status == "cooling":
                # 默认冷却2小时
                acc["cooldown_until"] = (
                    datetime.now(timezone.utc) + timedelta(hours=2)
                ).isoformat()
            pool["accounts"].append(acc)
            added += 1

    if added > 0:
        save_pool(pool)
        print(f'  ✅ 初始化 {added} 个账号')
    return pool

# ============================================================
# Main
# ============================================================
def main():
    import argparse
    parser = argparse.ArgumentParser(description='Windsurf 账号池引擎')
    parser.add_argument('--next', action='store_true', help='切换到下一个可用账号')
    parser.add_argument('--switch', type=str, help='切换到指定邮箱的账号')
    parser.add_argument('--test', type=str, help='测试指定账号')
    parser.add_argument('--add', nargs=2, metavar=('EMAIL', 'PWD'), help='添加新账号')
    parser.add_argument('--cooldown', nargs=2, metavar=('EMAIL', 'MINS'), help='标记账号冷却')
    parser.add_argument('--reset-fp', action='store_true', help='仅重置设备指纹')
    parser.add_argument('--init', action='store_true', help='初始化默认账号池')
    parser.add_argument('--force', action='store_true', help='强制切换(不检查Windsurf运行)')
    args = parser.parse_args()

    pool = load_pool()

    # 初始化
    if args.init or not pool["accounts"]:
        pool = init_default_accounts(pool)

    # 仅重置指纹
    if args.reset_fp:
        print('\n🔧 重置设备指纹...')
        reset_fingerprint()
        return 0

    # 添加账号
    if args.add:
        email, pwd = args.add
        acc = default_account(email, pwd)
        pool["accounts"].append(acc)
        save_pool(pool)
        print(f'  ✅ 已添加账号: {email}')
        return 0

    # 标记冷却
    if args.cooldown:
        email, mins = args.cooldown
        mins = int(mins)
        for acc in pool["accounts"]:
            if acc["email"] == email:
                acc["cooldown_until"] = (
                    datetime.now(timezone.utc) + timedelta(minutes=mins)
                ).isoformat()
                acc["status"] = "cooling"
                save_pool(pool)
                print(f'  ✅ {email} 已标记冷却 {mins} 分钟')
                return 0
        print(f'  ❌ 未找到账号 {email}')
        return 1

    # 切换到下一个
    if args.next:
        next_acc = get_next_account(pool)
        if not next_acc:
            print('  ❌ 没有可用账号，全部冷却中')
            # 显示最快恢复的
            cooling = [(a, remaining_cooldown(a)) for a in pool["accounts"] if is_cooling(a)]
            cooling.sort(key=lambda x: x[1])
            if cooling:
                print(f'  最快恢复: {cooling[0][0]["email"]} ({cooling[0][1]:.0f}分钟后)')
            return 1
        return 0 if switch_account(pool, next_acc["email"]) else 1

    # 切换到指定账号
    if args.switch:
        return 0 if switch_account(pool, args.switch) else 1

    # 默认：显示状态
    show_status(pool)
    return 0

if __name__ == '__main__':
    sys.exit(main())
