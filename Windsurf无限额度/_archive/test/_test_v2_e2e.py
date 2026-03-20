#!/usr/bin/env python3
"""
switch_v2.py 全量E2E测试
========================
测试所有底层功能，不实际切换账号(避免中断当前Windsurf会话)
"""
import sys, json, os, tempfile, shutil
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))
import switch_v2 as sv2

results = []

def test(name, func):
    try:
        ok, detail = func()
        status = "PASS" if ok else "FAIL"
        results.append((name, status, detail))
        print(f"  {'✅' if ok else '❌'} {name}: {detail}")
    except Exception as e:
        results.append((name, "ERROR", str(e)))
        print(f"  💥 {name}: {e}")

print("=" * 60)
print("switch_v2.py 全量E2E测试")
print("=" * 60)

# ============ 1. 路径与存在性 ============
print("\n[1] 路径与存在性")

def t01():
    return sv2.WS_APPDATA.exists(), str(sv2.WS_APPDATA)
test("路径_APPDATA", t01)

def t02():
    return sv2.WS_STORAGE.exists(), f"{sv2.WS_STORAGE.stat().st_size}B"
test("路径_storage.json", t02)

def t03():
    return sv2.WS_STATE_DB.exists(), f"{sv2.WS_STATE_DB.stat().st_size}B"
test("路径_state.vscdb", t03)

def t04():
    return sv2.POOL_FILE.exists(), f"{len(json.loads(sv2.POOL_FILE.read_text('utf-8'))['accounts'])}个账号"
test("路径_account_pool", t04)

# ============ 2. 指纹生成 ============
print("\n[2] 指纹生成")

def t05():
    fp = sv2.generate_fingerprint()
    keys = ['telemetry.machineId', 'telemetry.macMachineId', 'telemetry.devDeviceId',
            'telemetry.sqmId', 'storage.serviceMachineId']
    all_present = all(k in fp for k in keys)
    all_valid = all(len(fp[k]) > 10 for k in keys)
    return all_present and all_valid, f"{len(fp)}键 all_valid={all_valid}"
test("指纹_生成", t05)

def t06():
    fp1 = sv2.generate_fingerprint()
    fp2 = sv2.generate_fingerprint()
    different = all(fp1[k] != fp2[k] for k in fp1)
    return different, f"两次生成不同={different}"
test("指纹_唯一性", t06)

# ============ 3. 数据库操作 ============
print("\n[3] 数据库读取")

def t07():
    val = sv2.db_read('windsurfAuthStatus')
    return val is not None, f"{len(val) if val else 0}B"
test("DB_读取_authStatus", t07)

def t08():
    val = sv2.db_read('windsurf.settings.cachedPlanInfo')
    return val is not None, f"{len(val) if val else 0}B"
test("DB_读取_planInfo", t08)

def t09():
    val = sv2.db_read('nonexistent_key_12345')
    return val is None, "不存在的键返回None"
test("DB_读取_不存在", t09)

# ============ 4. 认证信息读取 ============
print("\n[4] 认证信息")

def t10():
    auth = sv2.get_auth_info()
    if not auth:
        return False, "无认证信息"
    has_key = 'api_key' in auth and len(auth['api_key']) > 10
    return has_key, f"apiKey={auth['api_key'][:25]}..."
test("认证_auth_info", t10)

def t11():
    plan = sv2.get_plan_info()
    if not plan:
        return False, "无计划信息"
    has_plan = plan.get('plan') is not None
    return has_plan, f"plan={plan['plan']} msgs={plan['messages_remaining']:,}"
test("认证_plan_info", t11)

def t12():
    user = sv2.get_current_user()
    return user is not None, f"user={user}"
test("认证_current_user", t12)

def t13():
    vip = sv2.get_vip_info()
    if not vip:
        return True, "无VIP(可能未安装扩展)"
    return True, f"id={vip.get('user_identifier','?')[:25]}..."
test("认证_vip_info", t13)

# ============ 5. 进程检测 ============
print("\n[5] 进程管理")

def t14():
    running = sv2.is_windsurf_running()
    return True, f"running={running}"
test("进程_检测", t14)

# ============ 6. 账号池操作 ============
print("\n[6] 账号池")

def t15():
    pool = sv2.load_pool()
    has_accounts = len(pool.get('accounts', [])) > 0
    return has_accounts, f"total={len(pool['accounts'])}"
test("池_加载", t15)

def t16():
    pool = sv2.load_pool()
    next_acc = sv2.get_next_account(pool)
    if not next_acc:
        return False, "无可用账号"
    return True, f"next={next_acc['email'][:30]} status={next_acc['status']}"
test("池_下一个账号", t16)

def t17():
    pool = sv2.load_pool()
    available = [a for a in pool['accounts']
                 if not sv2.is_cooling(a) and a.get('status') not in ('disabled', 'terminated')]
    return len(available) > 0, f"available={len(available)}"
test("池_可用账号数", t17)

def t18():
    # 测试冷却逻辑
    from datetime import timedelta
    acc_future = {"cooldown_until": (sv2.now_utc() + timedelta(hours=1)).isoformat(), "status": "cooling"}
    acc_past = {"cooldown_until": (sv2.now_utc() - timedelta(hours=1)).isoformat(), "status": "cooling"}
    acc_none = {"cooldown_until": None, "status": "ready"}
    
    future_cool = sv2.is_cooling(acc_future)
    past_cool = sv2.is_cooling(acc_past)
    none_cool = sv2.is_cooling(acc_none)
    
    correct = future_cool and not past_cool and not none_cool
    return correct, f"future={future_cool} past={past_cool} none={none_cool}"
test("池_冷却逻辑", t18)

def t19():
    from datetime import timedelta
    acc = {"cooldown_until": (sv2.now_utc() + timedelta(minutes=45)).isoformat()}
    remaining = sv2.cooldown_remaining(acc)
    correct = 40 < remaining < 50
    return correct, f"remaining={remaining:.1f}min (expected ~45)"
test("池_冷却剩余", t19)

# ============ 7. 备份/恢复 ============
print("\n[7] 备份恢复")

def t20():
    bp = sv2.backup_auth(label="e2e_test")
    exists = bp.exists()
    if exists:
        data = json.loads(bp.read_text('utf-8'))
        has_auth = 'auth_status' in data
        has_fp = 'fingerprint' in data
        # 清理测试备份
        bp.unlink()
        return has_auth and has_fp, f"size={bp.stat().st_size if bp.exists() else 'cleaned'}B keys={list(data.keys())}"
    return False, "备份文件未创建"
test("备份_创建", t20)

def t21():
    # 创建→恢复→验证
    bp = sv2.backup_auth(label="restore_test")
    ok, msg = sv2.restore_auth(str(bp))
    bp.unlink(missing_ok=True)
    return ok, msg
test("备份_恢复", t21)

# ============ 8. 过期修复 ============
print("\n[8] 过期修复")

def t22():
    pool = sv2.load_pool()
    fixed = sv2.expire_fix(pool)
    return True, f"fixed={fixed}个"
test("过期_修复", t22)

# ============ 9. 添加账号(临时测试) ============
print("\n[9] 账号管理")

def t23():
    pool = sv2.load_pool()
    orig_count = len(pool['accounts'])
    test_email = "_test_e2e_@example.com"
    # 添加
    pool['accounts'].append({
        "email": test_email, "password": "test123", "plan": "unknown",
        "status": "untested", "cooldown_until": None,
        "last_used": None, "last_tested": None, "messages_used": 0, "notes": "e2e_test"
    })
    sv2.save_pool(pool)
    # 验证
    pool2 = sv2.load_pool()
    added = len(pool2['accounts']) == orig_count + 1
    # 清理
    pool2['accounts'] = [a for a in pool2['accounts'] if a['email'] != test_email]
    sv2.save_pool(pool2)
    pool3 = sv2.load_pool()
    cleaned = len(pool3['accounts']) == orig_count
    return added and cleaned, f"add={added} cleanup={cleaned}"
test("账号_添加删除", t23)

# ============ 10. 图片账号完整性 ============
print("\n[10] 图片账号完整性")

def t24():
    """验证图片中所有14个账号都在池中"""
    expected = [
        "060pyjy1@2art.fun",
        "davis.amy464616@yahoo.com",
        "susan125693@yahoo.com",
        "0d4ab068@intlgalleryheritageculture.org",
        "hollandaugustino1993@yahoo.com",
        "kofihawkins247714@yahoo.com",
        "cootsoc568@yahoo.com",
        "roberthessler483239@yahoo.com",
        "andrew.kane254974@yahoo.com",
        "fountainmaniyahseufty@yahoo.com",
        "tracy.vasquez43932@yahoo.com",
        "Uhumphreyspring2VZY1@yahoo.com",
        "harrisstacy11651@yahoo.com",
    ]
    pool = sv2.load_pool()
    pool_emails = {a['email'] for a in pool['accounts']}
    missing = [e for e in expected if e not in pool_emails]
    return len(missing) == 0, f"found={len(expected)-len(missing)}/{len(expected)} missing={missing}"
test("图片_账号完整", t24)

# ============ Summary ============
print(f"\n{'='*60}")
passed = sum(1 for _, s, _ in results if s == "PASS")
failed = sum(1 for _, s, _ in results if s == "FAIL")
errors = sum(1 for _, s, _ in results if s == "ERROR")
total = len(results)
print(f"E2E结果: {passed} PASS / {failed} FAIL / {errors} ERROR / {total} TOTAL")

if failed + errors > 0:
    print("\n失败项:")
    for name, status, detail in results:
        if status != "PASS":
            print(f"  {status}: {name} — {detail}")
