"""
Windsurf Credits Patch v3.1
===========================
逆向分析发现Windsurf额度控制是客户端侧(client-side)逻辑：
- U5e = Z => Z === -1  → monthlyPromptCredits === -1 表示无限额度
- W5e 计算剩余额度，当U5e返回true时返回 Number.MAX_SAFE_INTEGER
- CheckChatCapacity 是服务端容量检查(非额度)，hasCapacity=true时放行
- planName 随每次gRPC请求发送至服务器，影响服务端计费层级判断
- TeamsTier.ENTERPRISE_SAAS(=3) 决定Enterprise特权
- PlanInfo constructor 包含20+布尔特性开关，全部可客户端解锁
- Metadata.impersonateTier 字段可注入伪装层级到每个gRPC请求

本脚本修改 workbench.desktop.main.js 中的15个关键点：

== 核心额度/计费 (Patch 1-5, v2.0) ==
1.  U5e 永远返回 true (额度永远显示为无限)
2.  hasCapacity 检查永远通过 (容量检查旁路)
3.  额度不足提示永远预设为已关闭
4.  planName 元数据强制为 "Pro Ultimate" (服务端计费层级提升)
5.  isEnterprise + hasPaidFeatures 默认值强制为 true (解锁Enterprise特权)

== Pro/Enterprise 特性全解锁 (Patch 6-10, v3.0) ==
6.  Premium模型: hasAutocompleteFastMode + allowStickyPremiumModels + hasForgeAccess
7.  Premium命令模型: allowPremiumCommandModels + hasTabToJump
8.  Cascade Pro功能: webSearch + appIcon + autoRunCommands + commitMessages + knowledgeBase
9.  社交/共享: canShareConversations + canAllowCascadeInBackground
10. 浏览器功能: browserEnabled

== 服务端伪装 (Patch 11, v3.1 新增) ==
11. gRPC Metadata构造函数: planName="Pro Ultimate" + impersonateTier="ENTERPRISE_SAAS"

== Regex补丁 (Patch 12-15, 适配变量名变化) ==
12. hasCapacity regex旁路
13. 额度警告重置拦截
14. planName regex覆盖
15. isFreeTier bypass: teamsTier===UNSPECIFIED → always false

WindsurfPlanType: Free | Pro | Pro Ultimate | Trial | Teams | Teams Ultimate
TeamsTier: UNSPECIFIED=0 | TEAMS=1 | PRO=2 | ENTERPRISE_SAAS=3 | HYBRID=4 |
           ENTERPRISE_SELF_HOSTED=5 | TRIAL=9 | ENTERPRISE_SELF_SERVE=10

用法: python patch_windsurf.py [--restore | --verify]
"""

import sys
import os
import shutil
import time
import re
import json

TARGET_FILE = "workbench.desktop.main.js"
RELATIVE_PATH = r"resources\app\out\vs\workbench"

def find_windsurf_js():
    """搜索 workbench.desktop.main.js 的位置（快速候选路径，无递归扫描）"""
    candidates = [
        r"D:\Windsurf",
        r"C:\Windsurf",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Windsurf"),
        os.path.expandvars(r"%LOCALAPPDATA%\Windsurf"),
        os.path.expandvars(r"%ProgramFiles%\Windsurf"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Windsurf"),
        os.path.expandvars(r"%APPDATA%\Windsurf"),
    ]
    for base in candidates:
        p = os.path.join(base, RELATIVE_PATH, TARGET_FILE)
        if os.path.isfile(p):
            return p
    return None

def detect_version(filepath):
    """检测Windsurf版本号"""
    product_json = os.path.join(os.path.dirname(filepath), "..", "..", "..", "product.json")
    product_json = os.path.normpath(product_json)
    if os.path.isfile(product_json):
        try:
            import json
            with open(product_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get("version", "unknown")
        except Exception:
            pass
    return "unknown"

# 补丁定义: (原始字符串, 替换字符串, 描述, 全部替换)
# 注意: Windsurf每次更新会改变minified变量名(如 Ju→G1, C→Te)
# 因此某些补丁使用regex模式匹配
PATCHES = [
    # Patch 1: 额度检查 - U5e 永远返回 true (无限额度)
    (
        "const U5e=Z=>Z===-1,W5e=",
        "const U5e=Z=>!0,W5e=",
        "Credit check bypass: monthlyPromptCredits always treated as unlimited",
        False
    ),
    # Patch 2: 容量检查旁路 - hasCapacity 永远为 true (变量名随版本变化)
    (
        "if(!Ju.hasCapacity)return",
        "if(!1)return",
        "Capacity check bypass: hasCapacity always passes (var=Ju)",
        False
    ),
    # Patch 3: 额度不足提示预设为已关闭
    (
        "dismissedOutOfCredit:!1,dismissedStatusWarning:!1,dismissedCreditInsufficientError:!1,dismissedCreditUpgradeNeededError:!1",
        "dismissedOutOfCredit:!0,dismissedStatusWarning:!0,dismissedCreditInsufficientError:!0,dismissedCreditUpgradeNeededError:!0",
        "Credit warnings auto-dismissed",
        False
    ),
    # Patch 4: planName 元数据 → "Pro Ultimate" (gRPC Metadata随请求发送至服务端)
    (
        'planName:C?.planStatus?.planInfo?.planName??"Unset"',
        'planName:"Pro Ultimate"',
        "PlanName override: metadata reports Pro Ultimate to server",
        False
    ),
    # Patch 5: isEnterprise + hasPaidFeatures 默认值 → true (出现3次，全部替换)
    (
        "this.isEnterprise=!1,this.hasPaidFeatures=!1",
        "this.isEnterprise=!0,this.hasPaidFeatures=!0",
        "Enterprise flags: isEnterprise + hasPaidFeatures forced true",
        True
    ),
    # ============ v3.0 新增补丁 (Patch 6-11) ============
    # Patch 6: Premium模型访问 — 快速自动补全 + 粘性Premium模型 + Forge访问
    (
        "this.hasAutocompleteFastMode=!1,this.allowStickyPremiumModels=!1,this.hasForgeAccess=!1",
        "this.hasAutocompleteFastMode=!0,this.allowStickyPremiumModels=!0,this.hasForgeAccess=!0",
        "Premium model access: fastMode + stickyPremium + forgeAccess forced true",
        True
    ),
    # Patch 7: Premium命令模型 + Tab跳转
    (
        "this.allowPremiumCommandModels=!1,this.hasTabToJump=!1",
        "this.allowPremiumCommandModels=!0,this.hasTabToJump=!0",
        "Premium command models + tabToJump forced true",
        True
    ),
    # Patch 8: Cascade Pro功能 — Web搜索 + 自定义图标 + 自动运行命令 + 提交消息 + 知识库
    (
        "this.cascadeWebSearchEnabled=!1,this.canCustomizeAppIcon=!1,this.cascadeCanAutoRunCommands=!1,this.canGenerateCommitMessages=!1,this.knowledgeBaseEnabled=!1",
        "this.cascadeWebSearchEnabled=!0,this.canCustomizeAppIcon=!0,this.cascadeCanAutoRunCommands=!0,this.canGenerateCommitMessages=!0,this.knowledgeBaseEnabled=!0",
        "Cascade Pro features: webSearch + appIcon + autoRun + commitMsg + knowledgeBase",
        True
    ),
    # Patch 9: 社交/共享功能 — 分享对话 + 后台Cascade
    (
        "this.canShareConversations=!1,this.canAllowCascadeInBackground=!1",
        "this.canShareConversations=!0,this.canAllowCascadeInBackground=!0",
        "Social features: shareConversations + cascadeInBackground forced true",
        True
    ),
    # Patch 10: 浏览器功能 (保持isDevin=!1)
    (
        "this.browserEnabled=!1,this.isDevin=!1",
        "this.browserEnabled=!0,this.isDevin=!1",
        "Browser feature enabled (isDevin kept false)",
        True
    ),
    # Patch 11: gRPC Metadata构造函数 — impersonateTier注入
    # 每个gRPC请求都携带Metadata，impersonateTier字段告诉服务器要仿冒的层级
    # ENTERPRISE_SAAS=3 是最高特权等级
    (
        'this.planName="",this.id="",this.impersonateTier=""',
        'this.planName="Pro Ultimate",this.id="",this.impersonateTier="ENTERPRISE_SAAS"',
        "gRPC Metadata: planName=Pro Ultimate + impersonateTier=ENTERPRISE_SAAS injected",
        True
    ),
]

# Regex补丁: 处理变量名随版本变化的情况
# 格式: (regex_pattern, replacement_func_or_str, description)
REGEX_PATCHES = [
    # Patch 2b: 容量检查旁路 - 匹配任意变量名 (如 G1, Ju, Xx 等)
    (
        r'if\(!([A-Za-z]\w{0,2})\.hasCapacity\)return',
        'if(!1)return',
        "Capacity check bypass: hasCapacity (regex, any var name)",
    ),
    # Patch 3b: 状态重置拦截 - 阻止dismiss flags被重置回!1
    (
        r'(\w)\.dismissedOutOfCredit=!1,\1\.dismissedStatusWarning=!1,\1\.dismissedCreditInsufficientError=!1,\1\.dismissedCreditUpgradeNeededError=!1',
        lambda m: f'{m.group(1)}.dismissedOutOfCredit=!0,{m.group(1)}.dismissedStatusWarning=!0,{m.group(1)}.dismissedCreditInsufficientError=!0,{m.group(1)}.dismissedCreditUpgradeNeededError=!0',
        "Credit warning reset intercepted: prevent re-enabling warnings",
    ),
    # Patch 4b: planName - 匹配任意变量名
    (
        r'planName:(\w+)\?\.planStatus\?\.planInfo\?\.planName\?\?"Unset"',
        'planName:"Pro Ultimate"',
        "PlanName override (regex, any var name)",
    ),
    # Patch 12: isFreeTier旁路 — teamsTier===UNSPECIFIED判断 → 永远返回false
    # 原始: ai?.teamsTier!==void 0?ai.teamsTier===XX.UNSPECIFIED:void 0
    # 修改: ai?.teamsTier!==void 0?!1:void 0  (isFreeTier永远为false)
    (
        r'(\w+)\?\.teamsTier!==void 0\?\1\.teamsTier===(\w+)\.UNSPECIFIED:void 0',
        r'\1?.teamsTier!==void 0?!1:void 0',
        "isFreeTier bypass: teamsTier===UNSPECIFIED check always returns false",
    ),
]

def patch(filepath):
    """应用所有补丁"""
    backup = filepath + ".bak"
    
    # 读取文件
    print(f"[*] Reading: {filepath}")
    print(f"    Size: {os.path.getsize(filepath) / 1024 / 1024:.1f} MB")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 备份
    if not os.path.isfile(backup):
        print(f"[*] Creating backup: {backup}")
        shutil.copy2(filepath, backup)
    else:
        print(f"[*] Backup already exists: {backup}")
    
    # Phase 1: 应用静态补丁
    applied = 0
    for i, (old, new, desc, *flags) in enumerate(PATCHES, 1):
        replace_all = flags[0] if flags else False
        if old in content:
            if replace_all:
                count = content.count(old)
                content = content.replace(old, new)
                print(f"[✓] Patch {i}: {desc} ({count}x replaced)")
            else:
                content = content.replace(old, new, 1)
                print(f"[✓] Patch {i}: {desc}")
            applied += 1
        elif new in content:
            print(f"[=] Patch {i}: Already applied - {desc}")
        else:
            print(f"[-] Patch {i}: Static target not found - {desc}")
    
    # Phase 2: 应用Regex补丁 (处理变量名变化)
    for j, (pattern, repl, desc) in enumerate(REGEX_PATCHES, len(PATCHES) + 1):
        matches = list(re.finditer(pattern, content))
        if matches:
            if callable(repl):
                content = re.sub(pattern, repl, content)
            else:
                content = re.sub(pattern, repl, content)
            print(f"[✓] Patch {j}: {desc} ({len(matches)}x matched)")
            applied += 1
        else:
            # Check if already patched by checking the replacement text
            if isinstance(repl, str) and repl in content:
                print(f"[=] Patch {j}: Already applied - {desc}")
            else:
                print(f"[-] Patch {j}: No regex match - {desc}")
    
    if applied > 0:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"\n[✓] {applied} patch(es) applied successfully.")
        print(f"[!] Restart Windsurf to take effect.")
    else:
        print(f"\n[=] No new patches applied.")
    
    return True

def restore(filepath):
    """从备份恢复"""
    backup = filepath + ".bak"
    if not os.path.isfile(backup):
        print(f"[✗] No backup found at: {backup}")
        return False
    
    print(f"[*] Restoring from backup...")
    shutil.copy2(backup, filepath)
    print(f"[✓] Restored. Restart Windsurf to take effect.")
    return True

def verify(filepath):
    """验证补丁状态"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print(f"\n{'='*50}")
    print(f"Patch Status Report")
    print(f"{'='*50}")
    print(f"File: {filepath}")
    print(f"Size: {os.path.getsize(filepath) / 1024 / 1024:.1f} MB")
    print()
    
    all_ok = True
    # Static patches
    for i, (old, new, desc, *_) in enumerate(PATCHES, 1):
        if new in content:
            status = "✓ APPLIED"
        elif old in content:
            status = "✗ NOT APPLIED"
            all_ok = False
        else:
            status = "~ COVERED BY REGEX"
        print(f"  Patch {i}: [{status}] {desc}")
    
    # Regex patches
    for j, (pattern, repl, desc) in enumerate(REGEX_PATCHES, len(PATCHES) + 1):
        matches = list(re.finditer(pattern, content))
        if matches:
            status = "✗ NOT APPLIED"
            all_ok = False
        elif isinstance(repl, str) and repl in content:
            status = "✓ APPLIED"
        else:
            status = "✓ CLEAN"
        print(f"  Patch {j}: [{status}] {desc}")
    
    print()
    if all_ok:
        print("[✓] All patches active. Unlimited credits enabled.")
    else:
        print("[!] Some patches missing. Run without --restore to apply.")
    print(f"{'='*50}")
    return all_ok

def main():
    print("=" * 50)
    print("Windsurf Credits Patch v3.1")
    print("=" * 50)
    
    # 支持直接传入文件路径
    custom_path = None
    for arg in sys.argv[1:]:
        if not arg.startswith("--") and os.path.isfile(arg):
            custom_path = arg
            break
    
    # 查找文件
    filepath = custom_path or find_windsurf_js()
    if not filepath:
        print("[✗] workbench.desktop.main.js not found!")
        print("    Usage: python patch_windsurf.py [path] [--restore|--verify]")
        sys.exit(1)
    
    print(f"[*] Found: {filepath}")
    version = detect_version(filepath)
    print(f"[*] Windsurf version: {version}")
    
    # 解析参数
    if "--restore" in sys.argv:
        restore(filepath)
    elif "--verify" in sys.argv:
        verify(filepath)
    else:
        patch(filepath)
        verify(filepath)

if __name__ == "__main__":
    main()
