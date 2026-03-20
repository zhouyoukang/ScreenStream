#!/usr/bin/env python3
"""
Windsurf 账号切换引擎 v2.0
============================
整合逆向分析+开源方案精华，实现深度无感切换。

底层架构发现:
  - 认证层: windsurfAuthStatus(47KB) 含apiKey+protobuf用户状态
  - 计划缓存: windsurf.settings.cachedPlanInfo 含额度/用量
  - VIP层: windsurf-vip-official.windsurf-vip-v2 含user_identifier
  - Secret层: secret://windsurf_auth.sessions + apiServerUrl (加密Buffer)
  - 指纹层: storage.json 5维遥测ID
  - 用户记录: windsurf_auth-{Name}-usages 每个切换过的用户
  - 当前用户: codeium.windsurf-windsurf_auth 存用户名

切换步骤:
  1. 关闭Windsurf进程
  2. 备份当前认证状态
  3. 重置5维设备指纹(storage.json)
  4. 清除认证缓存(state.vscdb: 7类键)
  5. 清除secret凭据
  6. 可选: 保留VIP注入(不清除vip-v2键)
  7. 更新账号池状态
  8. 启动Windsurf

用法:
  python switch_v2.py                      # 自动切到下一个可用账号
  python switch_v2.py --status             # 显示完整状态(含底层认证)
  python switch_v2.py --switch EMAIL       # 切换到指定账号
  python switch_v2.py --deep-reset         # 深度重置(含VIP/secret/所有用户记录)
  python switch_v2.py --add EMAIL PWD      # 添加新账号
  python switch_v2.py --mark-cool EMAIL [MINS]  # 标记冷却
  python switch_v2.py --verify             # 验证当前认证状态
  python switch_v2.py --backup             # 备份当前认证快照
  python switch_v2.py --restore FILE       # 从快照恢复
  python switch_v2.py --expire-fix         # 清除过期冷却
  python switch_v2.py --launch             # 切换后自动启动Windsurf
"""

import os, sys, json, uuid, hashlib, sqlite3, subprocess, time, shutil, argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta

# ============================================================
# 路径常量
# ============================================================
WS_APPDATA = Path(os.environ.get('APPDATA', '')) / 'Windsurf'
WS_STORAGE = WS_APPDATA / 'User' / 'globalStorage' / 'storage.json'
WS_STATE_DB = WS_APPDATA / 'User' / 'globalStorage' / 'state.vscdb'
POOL_FILE = Path(__file__).parent / '_account_pool.json'
BACKUP_DIR = Path(__file__).parent / '_backups'
WS_EXE = Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Windsurf' / 'Windsurf.exe'

# 认证相关键(按清除深度分类)
AUTH_KEYS_L1 = [  # 基础清除: 足以触发重新登录
    'windsurfAuthStatus',
    'windsurf.settings.cachedPlanInfo',
]
AUTH_KEYS_L2 = [  # 深度清除: 清除所有用户记录
    'codeium.windsurf-windsurf_auth',  # 当前用户名
]
AUTH_KEYS_L3_PATTERN = [  # 模式匹配清除
    'windsurf_auth-%',      # 所有 windsurf_auth-{Name} 和 -usages
    'secret://%windsurf%',  # secret凭据
]
VIP_KEYS = [  # VIP层(默认不清除)
    'windsurf-vip-official.windsurf-vip-v2',
]

# ============================================================
# 工具函数
# ============================================================
def now_utc():
    return datetime.now(timezone.utc)

def load_pool():
    if POOL_FILE.exists():
        try:
            return json.loads(POOL_FILE.read_text('utf-8'))
        except:
            pass
    return {"version": "2.0", "accounts": [], "current": None, "fingerprints": {}, "history": []}

def save_pool(pool):
    POOL_FILE.write_text(json.dumps(pool, indent=2, ensure_ascii=False), 'utf-8')

def is_cooling(acc):
    cd = acc.get("cooldown_until")
    if not cd:
        return False
    try:
        return now_utc() < datetime.fromisoformat(cd)
    except:
        return False

def cooldown_remaining(acc):
    cd = acc.get("cooldown_until")
    if not cd:
        return 0
    try:
        delta = datetime.fromisoformat(cd) - now_utc()
        return max(0, delta.total_seconds() / 60)
    except:
        return 0

# ============================================================
# 进程管理
# ============================================================
def kill_windsurf(timeout=10):
    """关闭所有Windsurf进程"""
    try:
        out = subprocess.check_output(
            'tasklist /fi "IMAGENAME eq Windsurf.exe" /fo csv /nh',
            shell=True, encoding='utf-8', errors='replace'
        )
        if 'Windsurf.exe' not in out:
            return True, "未运行"
        
        subprocess.run('taskkill /F /IM Windsurf.exe', shell=True,
                       capture_output=True, timeout=timeout)
        time.sleep(2)
        
        out2 = subprocess.check_output(
            'tasklist /fi "IMAGENAME eq Windsurf.exe" /fo csv /nh',
            shell=True, encoding='utf-8', errors='replace'
        )
        if 'Windsurf.exe' not in out2:
            return True, "已关闭"
        return False, "部分进程仍在运行"
    except Exception as e:
        return False, str(e)

def launch_windsurf():
    """启动Windsurf"""
    # 尝试多个可能的路径
    candidates = [
        WS_EXE,
        Path('D:/Windsurf/Windsurf.exe'),
        Path(os.environ.get('LOCALAPPDATA', '')) / 'Windsurf' / 'Windsurf.exe',
    ]
    for exe in candidates:
        if exe.exists():
            subprocess.Popen([str(exe)], creationflags=subprocess.DETACHED_PROCESS)
            return True, str(exe)
    
    # 尝试PATH中的Windsurf
    try:
        subprocess.Popen(['Windsurf'], creationflags=subprocess.DETACHED_PROCESS)
        return True, "PATH"
    except:
        return False, "Windsurf.exe未找到"

def is_windsurf_running():
    try:
        out = subprocess.check_output(
            'tasklist /fi "IMAGENAME eq Windsurf.exe" /fo csv /nh',
            shell=True, encoding='utf-8', errors='replace'
        )
        return 'Windsurf.exe' in out
    except:
        return False

# ============================================================
# 指纹管理
# ============================================================
def generate_fingerprint():
    """生成全新5维设备指纹"""
    return {
        "telemetry.machineId": hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
        "telemetry.macMachineId": hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
        "telemetry.devDeviceId": str(uuid.uuid4()),
        "telemetry.sqmId": "{" + str(uuid.uuid4()).upper() + "}",
        "storage.serviceMachineId": str(uuid.uuid4()),
    }

def reset_fingerprint():
    """重置storage.json中的设备指纹"""
    if not WS_STORAGE.exists():
        return None, "storage.json不存在"
    
    try:
        data = json.loads(WS_STORAGE.read_text('utf-8'))
    except:
        data = {}
    
    fp = generate_fingerprint()
    for k, v in fp.items():
        data[k] = v
    
    # 重置会话日期(看起来像新安装)
    now_str = time.strftime('%a, %d %b %Y %H:%M:%S GMT', time.gmtime())
    for date_key in ['telemetry.firstSessionDate', 'telemetry.lastSessionDate', 'telemetry.currentSessionDate']:
        if date_key in data:
            data[date_key] = now_str
    
    WS_STORAGE.write_text(json.dumps(data, indent='\t'), 'utf-8')
    return fp, "5维指纹已重置"

# ============================================================
# state.vscdb 操作
# ============================================================
def db_read(key):
    if not WS_STATE_DB.exists():
        return None
    try:
        conn = sqlite3.connect(str(WS_STATE_DB))
        cur = conn.execute("SELECT value FROM ItemTable WHERE key=?", (key,))
        row = cur.fetchone()
        conn.close()
        return row[0] if row else None
    except:
        return None

def db_delete(key):
    if not WS_STATE_DB.exists():
        return 0
    try:
        conn = sqlite3.connect(str(WS_STATE_DB))
        conn.execute("DELETE FROM ItemTable WHERE key=?", (key,))
        conn.commit()
        changes = conn.total_changes
        conn.close()
        return changes
    except:
        return 0

def db_delete_pattern(pattern):
    if not WS_STATE_DB.exists():
        return 0
    try:
        conn = sqlite3.connect(str(WS_STATE_DB))
        conn.execute("DELETE FROM ItemTable WHERE key LIKE ?", (pattern,))
        conn.commit()
        changes = conn.total_changes
        conn.close()
        return changes
    except:
        return 0

def db_write(key, value):
    if not WS_STATE_DB.exists():
        return False
    try:
        conn = sqlite3.connect(str(WS_STATE_DB))
        conn.execute("INSERT OR REPLACE INTO ItemTable(key, value) VALUES(?, ?)", (key, value))
        conn.commit()
        conn.close()
        return True
    except:
        return False

# ============================================================
# 认证状态读取
# ============================================================
def get_auth_info():
    """获取当前认证信息"""
    raw = db_read('windsurfAuthStatus')
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return {
            "api_key": data.get("apiKey", "")[:30] + "...",
            "api_key_full": data.get("apiKey", ""),
            "raw_size": len(raw),
        }
    except:
        return None

def get_plan_info():
    """获取计划信息"""
    raw = db_read('windsurf.settings.cachedPlanInfo')
    if not raw:
        return None
    try:
        data = json.loads(raw)
        usage = data.get('usage', {})
        return {
            "plan": data.get('planName', '?'),
            "messages_total": usage.get('messages', 0),
            "messages_used": usage.get('usedMessages', 0),
            "messages_remaining": usage.get('remainingMessages', 0),
            "flow_actions": usage.get('flowActions', 0),
            "flow_used": usage.get('usedFlowActions', 0),
            "grace": data.get('gracePeriodStatus', 0),
            "start": data.get('startTimestamp', 0),
            "end": data.get('endTimestamp', 0),
        }
    except:
        return None

def get_current_user():
    """获取当前登录用户名"""
    raw = db_read('codeium.windsurf-windsurf_auth')
    return raw.strip() if raw else None

def get_vip_info():
    """获取VIP状态"""
    raw = db_read('windsurf-vip-official.windsurf-vip-v2')
    if not raw:
        return None
    try:
        return json.loads(raw)
    except:
        return None

# ============================================================
# 核心: 认证清除
# ============================================================
def clear_auth(deep=False, clear_vip=False):
    """清除认证缓存
    
    deep=False: L1基础清除(触发重新登录, 保留用户记录)
    deep=True:  L1+L2+L3完全清除(清除所有历史用户记录+secret)
    clear_vip:  同时清除VIP注入
    """
    cleared = 0
    
    # L1: 基础清除
    for key in AUTH_KEYS_L1:
        cleared += db_delete(key)
    
    if deep:
        # L2: 深度清除
        for key in AUTH_KEYS_L2:
            cleared += db_delete(key)
        
        # L3: 模式匹配清除
        for pattern in AUTH_KEYS_L3_PATTERN:
            cleared += db_delete_pattern(pattern)
    
    if clear_vip:
        for key in VIP_KEYS:
            cleared += db_delete(key)
    
    # VACUUM优化(从Cursor_Windsurf_Reset开源工具学到)
    if cleared > 0 and WS_STATE_DB.exists():
        try:
            conn = sqlite3.connect(str(WS_STATE_DB))
            conn.execute("VACUUM")
            conn.close()
        except:
            pass
    
    # Windows Credential Manager清理
    if deep:
        try:
            out = subprocess.check_output('cmdkey /list', shell=True, encoding='utf-8', errors='replace')
            for line in out.split('\n'):
                line_lower = line.lower().strip()
                if 'windsurf' in line_lower or 'codeium' in line_lower:
                    # 提取target名
                    if 'target:' in line_lower or '目标:' in line_lower:
                        target = line.split(':', 1)[-1].strip()
                        if target:
                            subprocess.run(f'cmdkey /delete:{target}', shell=True, capture_output=True)
                            cleared += 1
        except:
            pass
    
    return cleared

# ============================================================
# 备份/恢复
# ============================================================
def backup_auth(label=""):
    """备份当前认证状态"""
    BACKUP_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    name = f"auth_{label}_{ts}" if label else f"auth_{ts}"
    backup_path = BACKUP_DIR / f"{name}.json"
    
    snapshot = {
        "timestamp": now_utc().isoformat(),
        "label": label,
        "user": get_current_user(),
        "auth_status": db_read('windsurfAuthStatus'),
        "plan_info": db_read('windsurf.settings.cachedPlanInfo'),
        "vip_info": db_read('windsurf-vip-official.windsurf-vip-v2'),
        "current_auth_ref": db_read('codeium.windsurf-windsurf_auth'),
    }
    
    # 也备份storage.json指纹
    if WS_STORAGE.exists():
        storage_data = json.loads(WS_STORAGE.read_text('utf-8'))
        snapshot["fingerprint"] = {k: storage_data.get(k) for k in [
            'telemetry.machineId', 'telemetry.macMachineId',
            'telemetry.devDeviceId', 'telemetry.sqmId', 'storage.serviceMachineId'
        ]}
    
    backup_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), 'utf-8')
    return backup_path

def restore_auth(backup_file):
    """从备份恢复认证状态"""
    bp = Path(backup_file)
    if not bp.exists():
        # 尝试在BACKUP_DIR中查找
        bp = BACKUP_DIR / backup_file
    if not bp.exists():
        return False, f"备份文件不存在: {backup_file}"
    
    snapshot = json.loads(bp.read_text('utf-8'))
    restored = 0
    
    if snapshot.get('auth_status'):
        db_write('windsurfAuthStatus', snapshot['auth_status'])
        restored += 1
    if snapshot.get('plan_info'):
        db_write('windsurf.settings.cachedPlanInfo', snapshot['plan_info'])
        restored += 1
    if snapshot.get('vip_info'):
        db_write('windsurf-vip-official.windsurf-vip-v2', snapshot['vip_info'])
        restored += 1
    if snapshot.get('current_auth_ref'):
        db_write('codeium.windsurf-windsurf_auth', snapshot['current_auth_ref'])
        restored += 1
    
    # 恢复指纹
    if snapshot.get('fingerprint') and WS_STORAGE.exists():
        data = json.loads(WS_STORAGE.read_text('utf-8'))
        for k, v in snapshot['fingerprint'].items():
            if v:
                data[k] = v
        WS_STORAGE.write_text(json.dumps(data, indent='\t'), 'utf-8')
        restored += 1
    
    return True, f"恢复{restored}项 (来自 {snapshot.get('label', '?')} @ {snapshot.get('timestamp', '?')[:19]})"

# ============================================================
# 核心: 账号切换
# ============================================================
def switch_to(pool, email=None, deep=False, auto_launch=False, dry_run=False):
    """切换到指定或下一个可用账号。dry_run=True时模拟流程但不实际修改"""
    
    # 确定目标账号
    if email:
        target = None
        for acc in pool["accounts"]:
            if acc["email"] == email:
                target = acc
                break
        if not target:
            print(f'  ❌ 账号 {email} 不在池中')
            return False
        if is_cooling(target):
            print(f'  ⚠️ {email} 冷却中，剩余 {cooldown_remaining(target):.0f} 分钟')
            return False
        if target.get("status") == "terminated":
            print(f'  ⚠️ {email} 已终止')
            return False
    else:
        target = get_next_account(pool)
        if not target:
            print('  ❌ 没有可用账号')
            show_cooling_eta(pool)
            return False
    
    mode_tag = "[DRY-RUN] " if dry_run else ""
    print(f'\n{mode_tag}🔄 切换到: {target["email"]}')
    print('=' * 55)
    
    # Step 0: 备份当前状态
    print(f'\n  [0/5] {mode_tag}备份当前认证...')
    current_user = get_current_user()
    if not dry_run:
        bp = backup_auth(label=current_user or "unknown")
        print(f'        ✅ 已备份到 {bp.name}')
    else:
        print(f'        🔵 模拟备份 (当前用户: {current_user})')
    
    # Step 1: 关闭Windsurf
    print(f'\n  [1/5] {mode_tag}关闭Windsurf...')
    if not dry_run:
        ok, msg = kill_windsurf()
        print(f'        {"✅" if ok else "⚠️"} {msg}')
        if not ok:
            time.sleep(3)
    else:
        running = is_windsurf_running()
        print(f'        🔵 模拟关闭 (当前{"运行中" if running else "未运行"})')
    
    # Step 2: 重置指纹
    print(f'\n  [2/5] {mode_tag}重置设备指纹...')
    if not dry_run:
        fp, msg = reset_fingerprint()
        print(f'        ✅ {msg}')
    else:
        fp = generate_fingerprint()
        print(f'        🔵 模拟指纹: {list(fp.values())[0][:20]}...')
    
    # Step 3: 清除认证
    print(f'\n  [3/5] {mode_tag}清除认证缓存({"深度" if deep else "基础"})...')
    if not dry_run:
        cleared = clear_auth(deep=deep, clear_vip=False)
        print(f'        ✅ 已清除 {cleared} 个键')
    else:
        keys_count = len(AUTH_KEYS_L1) + (len(AUTH_KEYS_L2) + len(AUTH_KEYS_L3_PATTERN) if deep else 0)
        print(f'        🔵 模拟清除 ~{keys_count} 类键')
    
    # Step 4: 更新账号池
    print(f'\n  [4/5] {mode_tag}更新账号池...')
    old_email = pool.get("current")
    if not dry_run:
        if old_email and old_email != target["email"]:
            for acc in pool["accounts"]:
                if acc["email"] == old_email and acc["status"] == "active":
                    acc["cooldown_until"] = (now_utc() + timedelta(hours=2)).isoformat()
                    acc["status"] = "cooling"
                    print(f'        📌 {old_email[:35]} → 冷却2h')
        
        target["last_used"] = now_utc().isoformat()
        target["status"] = "active"
        pool["current"] = target["email"]
        pool["history"] = pool.get("history", [])
        pool["history"].append({
            "action": "switch",
            "email": target["email"],
            "from": old_email,
            "timestamp": now_utc().isoformat(),
            "deep": deep,
        })
        if len(pool["history"]) > 200:
            pool["history"] = pool["history"][-200:]
        
        if fp:
            pool["fingerprints"] = pool.get("fingerprints", {})
            pool["fingerprints"][target["email"]] = fp
        
        save_pool(pool)
        print(f'        ✅ 池已更新')
    else:
        print(f'        🔵 模拟: {old_email or "无"} → {target["email"]}')
    
    # Step 5: 可选启动
    if auto_launch and not dry_run:
        print(f'\n  [5/5] {mode_tag}启动Windsurf...')
        ok, msg = launch_windsurf()
        print(f'        {"✅" if ok else "❌"} {msg}')
    else:
        print(f'\n  [5/5] {mode_tag}跳过启动')
    
    print(f'\n{"=" * 55}')
    if dry_run:
        print(f'🔵 DRY-RUN完成！以上操作未实际执行')
        print(f'   目标邮箱: {target["email"]}')
        print(f'   目标密码: {target["password"]}')
        print(f'\n   确认切换请运行: python switch_v2.py')
    else:
        print(f'✅ 切换完成！')
        print(f'   邮箱: {target["email"]}')
        print(f'   密码: {target["password"]}')
        if not auto_launch:
            print(f'\n   请手动启动Windsurf并登录上述账号')
        print(f'   限速后: python switch_v2.py')
    return True

def get_next_account(pool):
    """获取下一个最优账号"""
    available = [a for a in pool["accounts"]
                 if not is_cooling(a) 
                 and a.get("status") not in ("disabled", "terminated")]
    if not available:
        return None
    # 优先未测试
    untested = [a for a in available if a["status"] == "untested"]
    if untested:
        return untested[0]
    # 最久未使用
    available.sort(key=lambda a: a.get("last_used") or "2000-01-01")
    return available[0]

def show_cooling_eta(pool):
    cooling = [(a, cooldown_remaining(a)) for a in pool["accounts"] if is_cooling(a)]
    cooling.sort(key=lambda x: x[1])
    if cooling:
        print(f'   最快恢复: {cooling[0][0]["email"][:35]} ({cooling[0][1]:.0f}分钟后)')

# ============================================================
# 显示
# ============================================================
def show_status(pool, verbose=False):
    """显示完整状态"""
    print('\n╔══════════════════════════════════════════════════════════╗')
    print('║  Windsurf 账号切换引擎 v2.0                              ║')
    print('╚══════════════════════════════════════════════════════════╝')
    
    # 当前认证
    user = get_current_user()
    auth = get_auth_info()
    plan = get_plan_info()
    vip = get_vip_info()
    running = is_windsurf_running()
    
    print(f'\n  🖥️  Windsurf: {"🟢运行中" if running else "⚫未运行"}')
    print(f'  👤 当前用户: {user or "未登录"}')
    if auth:
        print(f'  🔑 API Key: {auth["api_key"]}')
    if plan:
        pct = (plan["messages_used"] / max(plan["messages_total"], 1)) * 100
        print(f'  📊 计划: {plan["plan"]}')
        print(f'  💬 消息: {plan["messages_used"]:,}/{plan["messages_total"]:,} ({pct:.1f}% 已用)')
        print(f'  ⚡ Flow: {plan["flow_used"]:,}/{plan["flow_actions"]:,}')
        if plan["start"]:
            from datetime import datetime as dt
            start = dt.fromtimestamp(plan["start"]/1000).strftime('%Y-%m-%d')
            end = dt.fromtimestamp(plan["end"]/1000).strftime('%Y-%m-%d')
            print(f'  📅 有效期: {start} → {end}')
    if vip:
        print(f'  👑 VIP: {vip.get("user_identifier", "?")[:30]}...')
    
    # 账号池
    print(f'\n  📋 账号池 ({len(pool["accounts"])}个):')
    header = f'  {"状态":<6} {"邮箱":<42} {"密码":<16} {"冷却":<8}'
    print(header)
    print(f'  {"-"*72}')
    
    for acc in pool["accounts"]:
        if is_cooling(acc):
            remain = cooldown_remaining(acc)
            if remain <= 0:  # 冷却已过期
                status = "🟡就绪"
                cd_str = "-"
            else:
                status = "🔴冷却"
                cd_str = f"{remain:.0f}m"
        elif acc["status"] == "untested":
            status = "⚪未测"
            cd_str = "-"
        elif acc["status"] == "active":
            status = "🟢活跃"
            cd_str = "-"
        elif acc["status"] in ("disabled", "terminated"):
            status = "⚫终止"
            cd_str = "-"
        else:
            status = "🟡就绪"
            cd_str = "-"
        
        current_mark = " ←" if acc["email"] == pool.get("current") else ""
        email_d = acc["email"][:40]
        pwd_d = acc["password"][:14]
        print(f'  {status:<6} {email_d:<42} {pwd_d:<16} {cd_str:<8}{current_mark}')
    
    # 统计
    available = sum(1 for a in pool["accounts"]
                    if not is_cooling(a) and a.get("status") not in ("disabled", "terminated"))
    expired_cool = sum(1 for a in pool["accounts"] 
                       if is_cooling(a) and cooldown_remaining(a) <= 0)
    cooling_active = sum(1 for a in pool["accounts"]
                         if is_cooling(a) and cooldown_remaining(a) > 0)
    terminated = sum(1 for a in pool["accounts"] if a.get("status") in ("disabled", "terminated"))
    
    print(f'\n  可用: {available} | 冷却中: {cooling_active} | 冷却过期: {expired_cool} | 终止: {terminated} | 总计: {len(pool["accounts"])}')
    
    # 备份列表
    if BACKUP_DIR.exists():
        backups = sorted(BACKUP_DIR.glob('auth_*.json'))
        print(f'\n  📂 备份: {len(backups)}个 ({BACKUP_DIR})')

def expire_fix(pool):
    """修复过期冷却状态"""
    fixed = 0
    for acc in pool["accounts"]:
        if is_cooling(acc) and cooldown_remaining(acc) <= 0:
            acc["cooldown_until"] = None
            if acc["status"] == "cooling":
                acc["status"] = "ready"
            fixed += 1
    if fixed:
        save_pool(pool)
    return fixed

def verify_auth():
    """验证当前认证完整性"""
    print('\n🔍 认证完整性验证')
    checks = []
    
    # 1. storage.json
    if WS_STORAGE.exists():
        data = json.loads(WS_STORAGE.read_text('utf-8'))
        fp_count = sum(1 for k in ['telemetry.machineId', 'telemetry.macMachineId',
                                     'telemetry.devDeviceId', 'telemetry.sqmId',
                                     'storage.serviceMachineId'] if data.get(k))
        checks.append(("指纹", fp_count >= 3, f"{fp_count}/5 键已设置"))
    else:
        checks.append(("指纹", False, "storage.json不存在"))
    
    # 2. 认证状态
    auth = get_auth_info()
    checks.append(("认证", auth is not None, f"apiKey={auth['api_key']}" if auth else "未认证"))
    
    # 3. 计划缓存
    plan = get_plan_info()
    if plan:
        checks.append(("计划", True, f"{plan['plan']} 剩余{plan['messages_remaining']:,}消息"))
    else:
        checks.append(("计划", False, "无缓存计划"))
    
    # 4. VIP
    vip = get_vip_info()
    checks.append(("VIP", vip is not None, f"id={vip['user_identifier'][:20]}..." if vip else "无VIP"))
    
    # 5. 用户记录
    user = get_current_user()
    checks.append(("用户", user is not None, user or "未设置"))
    
    # 6. 文件可写
    checks.append(("存储可写", os.access(str(WS_STORAGE), os.W_OK), ""))
    checks.append(("数据库可写", os.access(str(WS_STATE_DB), os.W_OK), ""))
    
    for name, ok, detail in checks:
        print(f'  {"✅" if ok else "❌"} {name}: {detail}')
    
    passed = sum(1 for _, ok, _ in checks if ok)
    print(f'\n  结果: {passed}/{len(checks)} 通过')
    return passed == len(checks)

# ============================================================
# Main
# ============================================================
def main():
    parser = argparse.ArgumentParser(description='Windsurf 账号切换引擎 v2.0')
    parser.add_argument('--status', action='store_true', help='显示完整状态')
    parser.add_argument('--switch', type=str, metavar='EMAIL', help='切换到指定账号')
    parser.add_argument('--deep-reset', action='store_true', help='深度重置(清除所有用户记录)')
    parser.add_argument('--add', nargs=2, metavar=('EMAIL', 'PWD'), help='添加新账号')
    parser.add_argument('--mark-cool', nargs='+', metavar='EMAIL', help='标记冷却 EMAIL [MINS]')
    parser.add_argument('--verify', action='store_true', help='验证认证完整性')
    parser.add_argument('--backup', action='store_true', help='备份当前认证')
    parser.add_argument('--restore', type=str, metavar='FILE', help='从备份恢复')
    parser.add_argument('--expire-fix', action='store_true', help='修复过期冷却')
    parser.add_argument('--launch', action='store_true', help='切换后自动启动Windsurf')
    parser.add_argument('--dry-run', action='store_true', help='模拟切换(不实际修改任何文件)')
    parser.add_argument('--verbose', '-v', action='store_true', help='详细输出')
    args = parser.parse_args()
    
    pool = load_pool()
    
    if args.status:
        show_status(pool, verbose=args.verbose)
        return 0
    
    if args.verify:
        return 0 if verify_auth() else 1
    
    if args.backup:
        user = get_current_user()
        bp = backup_auth(label=user or "manual")
        print(f'✅ 已备份到 {bp}')
        return 0
    
    if args.restore:
        ok, msg = restore_auth(args.restore)
        print(f'{"✅" if ok else "❌"} {msg}')
        return 0 if ok else 1
    
    if args.expire_fix:
        fixed = expire_fix(pool)
        print(f'✅ 修复 {fixed} 个过期冷却')
        return 0
    
    if args.add:
        email, pwd = args.add
        existing = {a["email"] for a in pool["accounts"]}
        if email in existing:
            print(f'⚠️ {email} 已存在')
            return 1
        pool["accounts"].append({
            "email": email, "password": pwd, "plan": "unknown",
            "status": "untested", "cooldown_until": None,
            "last_used": None, "last_tested": None,
            "messages_used": 0, "notes": ""
        })
        save_pool(pool)
        print(f'✅ 已添加 {email}')
        return 0
    
    if args.mark_cool:
        parts = args.mark_cool
        email = parts[0]
        mins = int(parts[1]) if len(parts) > 1 else 120
        for acc in pool["accounts"]:
            if acc["email"] == email:
                acc["cooldown_until"] = (now_utc() + timedelta(minutes=mins)).isoformat()
                acc["status"] = "cooling"
                save_pool(pool)
                print(f'✅ {email} 冷却 {mins}分钟')
                return 0
        print(f'❌ 未找到 {email}')
        return 1
    
    if args.deep_reset:
        print('\n⚠️ 深度重置: 将清除所有认证数据(保留VIP)')
        user = get_current_user()
        bp = backup_auth(label=f"deep_reset_{user or 'unknown'}")
        print(f'  📂 备份: {bp.name}')
        ok, msg = kill_windsurf()
        print(f'  进程: {msg}')
        fp, msg = reset_fingerprint()
        print(f'  指纹: {msg}')
        cleared = clear_auth(deep=True, clear_vip=False)
        print(f'  清除: {cleared}个键')
        print(f'✅ 深度重置完成，请启动Windsurf登录新账号')
        return 0
    
    # 默认: 自动切换到下一个可用账号
    if args.switch:
        return 0 if switch_to(pool, email=args.switch, auto_launch=args.launch, dry_run=args.dry_run) else 1
    else:
        # 先修复过期冷却
        fixed = expire_fix(pool)
        if fixed:
            print(f'  🔧 修复 {fixed} 个过期冷却')
        return 0 if switch_to(pool, auto_launch=args.launch, dry_run=args.dry_run) else 1

if __name__ == '__main__':
    sys.exit(main())
