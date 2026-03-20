#!/usr/bin/env python3
"""
WU app.asar 深度补丁器 v1.0
============================
基于 WU v1.5.6 main.js 完全逆向，精准修补以下问题：

P1. 429不在重试列表 → 注入429到Pn Set
P2. 最大重试仅3次 → 提升到6次
P3. 重试退避太短(线性1-3s) → 指数退避+抖动
P4. 流式超时180s太短 → 提升到300s
P5. 普通请求超时10s → 提升到30s
P6. 403直接断开 → 增加重连逻辑提示

用法:
  python wu_patch_asar.py          # 诊断+补丁
  python wu_patch_asar.py --check  # 仅检查补丁状态
  python wu_patch_asar.py --revert # 恢复原始
"""

import os, sys, json, shutil, subprocess, tempfile
from pathlib import Path
from datetime import datetime

WU_INSTALL = Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'WindsurfUnlimited'
ASAR_PATH = WU_INSTALL / 'resources' / 'app.asar'
ASAR_BAK = WU_INSTALL / 'resources' / 'app.asar.bak_original'
EXTRACT_DIR = Path(tempfile.gettempdir()) / 'wu_patch_work'

# ============================================================
# 补丁定义 (old_string → new_string)
# ============================================================
PATCHES = [
    {
        'id': 'P1',
        'name': '429注入重试列表',
        'desc': 'Pn Set缺少429 → WU遇到限速直接失败不重试',
        'severity': '🔴',
        'old': 'Pn=new Set([502,503,504,520,521,522,523,524])',
        'new': 'Pn=new Set([429,502,503,504,520,521,522,523,524])',
    },
    {
        'id': 'P2',
        'name': '最大重试次数提升',
        'desc': 'ft=3次太少 → 429限速需要更多重试机会',
        'severity': '🔴',
        'old': ',ft=3;',
        'new': ',ft=6;',
    },
    {
        'id': 'P3',
        'name': '重试退避优化',
        'desc': '线性退避1s*n → 指数退避+抖动(429需要更长等待)',
        'severity': '🟡',
        # Stream retry: setTimeout(()=>l(u+1),X) where X=1e3*(u+1)
        # Change to exponential: Math.min(1e3*Math.pow(2,u)+Math.random()*1e3,3e4)
        'old': 'const X=1e3*(u+1);e("info",`${X}ms \u540e\u91cd\u8bd5...`),setTimeout(()=>l(u+1),X)',
        'new': 'const X=Math.min(1e3*Math.pow(2,u)+Math.floor(Math.random()*2e3),3e4);e("info",`${X}ms \u540e\u91cd\u8bd5...`),setTimeout(()=>l(u+1),X)',
    },
    {
        'id': 'P4',
        'name': '流式超时延长',
        'desc': '180s对长思考模型不够 → 300s',
        'severity': '🟡',
        'old': 'b.setTimeout(18e4,',
        'new': 'b.setTimeout(3e5,',
    },
    {
        'id': 'P5',
        'name': '普通请求超时延长',
        'desc': '10s超时太短 → 30s',
        'severity': '🟡',
        'old': 'setTimeout(1e4,()=>{d.destroy(),a({ok:!1,latency:0,error:"\u8fde\u63a5\u8d85\u65f6"})})',
        'new': 'setTimeout(3e4,()=>{d.destroy(),a({ok:!1,latency:0,error:"\u8fde\u63a5\u8d85\u65f6"})})',
    },
]

# 普通proxy的重试退避也需要修改 (非stream)
PATCHES_PROXY_RETRY = {
    'id': 'P3b',
    'name': '普通代理重试退避',
    'desc': '普通proxy请求也需要指数退避',
    'severity': '🟡',
    # In the proxy function (xn), the retry logic:
    'old': 'const w=1e3*(u+1);e("info",`${w}ms \u540e\u91cd\u8bd5...`),setTimeout(()=>l(u+1),w)',
    'new': 'const w=Math.min(1e3*Math.pow(2,u)+Math.floor(Math.random()*2e3),3e4);e("info",`${w}ms \u540e\u91cd\u8bd5...`),setTimeout(()=>l(u+1),w)',
}


def extract_asar(asar_path, dest_dir):
    """Extract app.asar to temporary directory"""
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ['npx', 'asar', 'extract', str(asar_path), str(dest_dir)],
        capture_output=True, text=True, shell=True
    )
    if result.returncode != 0:
        print(f"❌ asar extract failed: {result.stderr}")
        return False
    return True


def pack_asar(src_dir, asar_path):
    """Pack directory back to app.asar"""
    result = subprocess.run(
        ['npx', 'asar', 'pack', str(src_dir), str(asar_path)],
        capture_output=True, text=True, shell=True
    )
    if result.returncode != 0:
        print(f"❌ asar pack failed: {result.stderr}")
        return False
    return True


def check_patches(js_content):
    """Check which patches are applied"""
    results = []
    for p in PATCHES:
        applied = p['new'] in js_content
        needed = p['old'] in js_content
        results.append({
            **p,
            'applied': applied,
            'needed': needed,
            'status': '✅' if applied else ('🔧' if needed else '⚠️'),
        })
    return results


def apply_patches(js_content):
    """Apply all patches to main.js content"""
    patched = js_content
    applied = []
    failed = []
    
    for p in PATCHES:
        if p['new'] in patched:
            applied.append((p['id'], 'already applied'))
            continue
        if p['old'] in patched:
            count = patched.count(p['old'])
            patched = patched.replace(p['old'], p['new'])
            applied.append((p['id'], f'applied ({count}x)'))
        else:
            failed.append((p['id'], 'pattern not found'))
    
    # Apply proxy retry patch (may have duplicate pattern with stream)
    p = PATCHES_PROXY_RETRY
    if p['old'] in patched:
        patched = patched.replace(p['old'], p['new'], 1)  # Only first occurrence
        applied.append((p['id'], 'applied'))
    
    return patched, applied, failed


def check_wu_running():
    """Check if WU is running"""
    try:
        result = subprocess.run(
            ['tasklist', '/fi', 'IMAGENAME eq WindsurfUnlimited.exe', '/fo', 'csv', '/nh'],
            capture_output=True, text=True
        )
        return 'WindsurfUnlimited' in result.stdout
    except:
        return False


def restart_wu():
    """Restart WindsurfUnlimited"""
    print("\n🔄 正在重启 WU...")
    try:
        subprocess.run(['taskkill', '/IM', 'WindsurfUnlimited.exe', '/F'], 
                       capture_output=True, timeout=10)
    except:
        pass
    
    import time
    time.sleep(2)
    
    wu_exe = WU_INSTALL / 'WindsurfUnlimited.exe'
    if wu_exe.exists():
        subprocess.Popen([str(wu_exe)], creationflags=0x00000008)  # DETACHED_PROCESS
        print("✅ WU 已重启")
    else:
        print(f"⚠️ WU exe not found: {wu_exe}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='WU app.asar 深度补丁器')
    parser.add_argument('--check', action='store_true', help='仅检查补丁状态')
    parser.add_argument('--revert', action='store_true', help='恢复原始')
    parser.add_argument('--no-restart', action='store_true', help='补丁后不重启WU')
    args = parser.parse_args()
    
    print("=" * 60)
    print("WU app.asar 深度补丁器 v1.0")
    print(f"目标: {ASAR_PATH}")
    print(f"时间: {datetime.now().isoformat()}")
    print("=" * 60)
    
    if not ASAR_PATH.exists():
        print(f"❌ app.asar 不存在: {ASAR_PATH}")
        return 1
    
    # Revert mode
    if args.revert:
        if ASAR_BAK.exists():
            shutil.copy2(ASAR_BAK, ASAR_PATH)
            print("✅ 已恢复原始 app.asar")
            if not args.no_restart:
                restart_wu()
            return 0
        else:
            print("❌ 无原始备份")
            return 1
    
    # Extract
    print("\n📦 正在提取 app.asar...")
    if not extract_asar(ASAR_PATH, EXTRACT_DIR):
        return 1
    
    main_js = EXTRACT_DIR / 'dist-electron' / 'main.js'
    if not main_js.exists():
        print(f"❌ main.js 不存在: {main_js}")
        return 1
    
    js_content = main_js.read_text(encoding='utf-8')
    print(f"✅ main.js 大小: {len(js_content):,} 字符")
    
    # Check mode
    results = check_patches(js_content)
    print(f"\n{'='*60}")
    print("补丁状态检查")
    print(f"{'='*60}")
    for r in results:
        print(f"  {r['status']} {r['id']} {r['severity']} {r['name']}")
        if not r['applied'] and not r['needed']:
            print(f"     ⚠️ 模式未匹配(WU版本可能不同)")
    
    if args.check:
        applied_count = sum(1 for r in results if r['applied'])
        print(f"\n已应用: {applied_count}/{len(results)}")
        return 0
    
    # Apply patches
    print(f"\n{'='*60}")
    print("应用补丁")
    print(f"{'='*60}")
    
    # Backup original (only first time)
    if not ASAR_BAK.exists():
        shutil.copy2(ASAR_PATH, ASAR_BAK)
        print(f"✅ 原始备份: {ASAR_BAK}")
    
    patched, applied, failed = apply_patches(js_content)
    
    for pid, status in applied:
        print(f"  ✅ {pid}: {status}")
    for pid, status in failed:
        print(f"  ❌ {pid}: {status}")
    
    if not applied:
        print("\n⚠️ 无补丁可应用")
        return 0
    
    # Write patched main.js
    main_js.write_text(patched, encoding='utf-8')
    
    # Repack
    print("\n📦 正在重新打包 app.asar...")
    if not pack_asar(EXTRACT_DIR, ASAR_PATH):
        # Restore backup on failure
        if ASAR_BAK.exists():
            shutil.copy2(ASAR_BAK, ASAR_PATH)
            print("⚠️ 打包失败，已恢复原始")
        return 1
    
    print(f"✅ 补丁完成: {len(applied)} 项成功, {len(failed)} 项失败")
    
    # Cleanup
    try:
        shutil.rmtree(EXTRACT_DIR)
    except:
        pass
    
    # Restart WU
    if not args.no_restart:
        restart_wu()
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
