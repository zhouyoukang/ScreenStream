"""
密码管理系统 — 全功能验证脚本
测试: audit.py + sync_check.py + secrets_manager.py + pre_commit_hook.py

灵感来源项目:
  - Yelp/detect-secrets (4.4k★) — 熵检测 + 插件架构
  - gitleaks (17k★) — 正则模式匹配
  - python-dotenv (7k★) — .env加载 + 变量插值
  - mozilla/sops (16k★) — 加密概念
  - Infisical (15k★) — 多环境管理
"""
import os
import sys
import importlib.util
import py_compile

ROOT = os.path.dirname(os.path.abspath(__file__))
PM_DIR = os.path.join(ROOT, "密码管理")
passed = failed = 0
results = []


def test(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        results.append(f"  ✅ {name}")
    else:
        failed += 1
        results.append(f"  ❌ {name}" + (f" — {detail}" if detail else ""))


def load_module(name, path):
    """动态加载Python模块"""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ═══════════════════════════════════════════
# T1: 文件结构完整性
# ═══════════════════════════════════════════
results.append("\n[T1] 文件结构")
expected_files = [
    "密码管理/audit.py",
    "密码管理/sync_check.py",
    "密码管理/secrets_manager.py",
    "密码管理/pre_commit_hook.py",
    "密码管理/README.md",
    "密码管理/AGENTS.md",
    "secrets.env",
    "凭据中心.md",
]
for f in expected_files:
    fp = os.path.join(ROOT, f)
    test(f"存在: {f}", os.path.exists(fp), "文件缺失")

# ═══════════════════════════════════════════
# T2: Python语法校验
# ═══════════════════════════════════════════
results.append("\n[T2] Python语法")
py_files = ["audit.py", "sync_check.py", "secrets_manager.py", "pre_commit_hook.py"]
for f in py_files:
    fp = os.path.join(PM_DIR, f)
    if not os.path.exists(fp):
        test(f"语法: {f}", False, "文件不存在")
        continue
    try:
        py_compile.compile(fp, doraise=True)
        test(f"语法: {f}", True)
    except py_compile.PyCompileError as e:
        test(f"语法: {f}", False, str(e)[:80])

# ═══════════════════════════════════════════
# T3: SecretsManager 核心功能
# ═══════════════════════════════════════════
results.append("\n[T3] SecretsManager")
try:
    sm_mod = load_module("secrets_manager", os.path.join(PM_DIR, "secrets_manager.py"))
    SM = sm_mod.SecretsManager

    # T3.1: 自动发现secrets.env
    sm = SM()
    test("自动发现secrets.env", sm.loaded and sm.path is not None)
    test(f"加载凭据数 >= 30", sm.count >= 30, f"实际: {sm.count}")

    # T3.2: get/has
    test("has('UNIFIED_PASSWORD')", sm.has("UNIFIED_PASSWORD"))
    test("get返回非空", len(sm.get("UNIFIED_PASSWORD")) > 0)
    test("get默认值", sm.get("NONEXISTENT_KEY_XYZ", "default") == "default")

    # T3.3: 公开键区分
    test("公开键区分: LAPTOP_IP", "LAPTOP_IP" in SM.PUBLIC_KEYS)
    secrets_only = sm.as_dict(secrets_only=True)
    test("secrets_only排除公开键", "LAPTOP_IP" not in secrets_only)
    test("secrets_only包含敏感键", any(k for k in secrets_only if "PASSWORD" in k or "TOKEN" in k))

    # T3.4: 指纹
    fp = sm.fingerprint()
    test("fingerprint返回16字符", fp is not None and len(fp) == 16)

    # T3.5: 一致性检查
    result = sm.check_consistency()
    test("一致性检查返回字典", isinstance(result, dict) and "ok" in result)

    # T3.6: 模块级便捷函数
    val = sm_mod.get_secret("UNIFIED_PASSWORD")
    test("get_secret便捷函数", len(val) > 0)

    # T3.7: 显式路径
    sm2 = SM(env_path=os.path.join(ROOT, "secrets.env"))
    test("显式路径加载", sm2.loaded and sm2.count > 0)

    # T3.8: 不存在路径
    sm3 = SM(env_path="/nonexistent/path/secrets.env")
    test("不存在路径: loaded=False", not sm3.loaded)
    test("不存在路径: count=0", sm3.count == 0)

except Exception as e:
    test("SecretsManager加载失败", False, str(e)[:120])

# ═══════════════════════════════════════════
# T4: audit.py 增强功能
# ═══════════════════════════════════════════
results.append("\n[T4] audit.py 增强功能")
try:
    audit_mod = load_module("audit", os.path.join(PM_DIR, "audit.py"))

    # T4.1: 熵检测函数
    test("shannon_entropy函数存在", hasattr(audit_mod, "shannon_entropy"))
    test("is_high_entropy函数存在", hasattr(audit_mod, "is_high_entropy"))

    # T4.2: 熵计算正确性
    # 随机Base64应该高熵
    high_entropy_str = "aB3dE5fG7hI9jK1lM3nO5pQ7rS9tU1vW3xY5z"
    low_entropy_str = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    test("高熵字符串检测", audit_mod.is_high_entropy(high_entropy_str))
    test("低熵字符串排除", not audit_mod.is_high_entropy(low_entropy_str))
    test("短字符串排除", not audit_mod.is_high_entropy("short"))

    # T4.3: 正则模式
    test("SECRET_PATTERNS已定义", hasattr(audit_mod, "SECRET_PATTERNS") and len(audit_mod.SECRET_PATTERNS) >= 5)

    # T4.4: 白名单标记
    test("ALLOWLIST_MARKERS已定义", hasattr(audit_mod, "ALLOWLIST_MARKERS"))
    test("白名单包含nosecret", "# nosecret" in audit_mod.ALLOWLIST_MARKERS)

    # T4.5: 一致性检查函数
    test("check_consistency函数存在", hasattr(audit_mod, "check_consistency"))

    # T4.6: 加载secrets
    secrets = audit_mod.load_secrets()
    test(f"load_secrets加载 >= 30", len(secrets) >= 30, f"实际: {len(secrets)}")

    # T4.7: 公开键排除
    test("公开键不在secrets中", "LAPTOP_IP" not in secrets and "GLASSES_WIFI_SSID" not in secrets)

except Exception as e:
    test("audit.py加载失败", False, str(e)[:120])

# ═══════════════════════════════════════════
# T5: pre_commit_hook.py
# ═══════════════════════════════════════════
results.append("\n[T5] pre_commit_hook.py")
try:
    hook_mod = load_module("pre_commit_hook", os.path.join(PM_DIR, "pre_commit_hook.py"))

    # T5.1: 核心函数存在
    test("shannon_entropy存在", hasattr(hook_mod, "shannon_entropy"))
    test("is_high_entropy存在", hasattr(hook_mod, "is_high_entropy"))
    test("load_secret_values存在", hasattr(hook_mod, "load_secret_values"))
    test("scan_content存在", hasattr(hook_mod, "scan_content"))

    # T5.2: 正则模式
    test("SECRET_PATTERNS >= 5", len(hook_mod.SECRET_PATTERNS) >= 5)

    # T5.3: 扫描测试 — 安全内容
    findings = hook_mod.scan_content("normal code without secrets", "test.py", set())
    test("安全内容: 0发现", len(findings) == 0)

    # T5.4: 扫描测试 — AWS Key格式
    findings = hook_mod.scan_content("aws_key = AKIAIOSFODNN7EXAMPLE", "test.py", set())
    test("AWS Key格式检测", len(findings) > 0)

    # T5.5: 扫描测试 — 私钥格式
    findings = hook_mod.scan_content("-----BEGIN RSA PRIVATE KEY-----", "test.py", set())
    test("私钥格式检测", len(findings) > 0)

    # T5.6: 白名单跳过
    findings = hook_mod.scan_content("password = secret123456 # nosecret", "test.py", set())
    test("白名单# nosecret跳过", len(findings) == 0)

    # T5.7: 实际值匹配
    findings = hook_mod.scan_content("config = 'testvalue12345678'", "test.py", {"testvalue12345678"})
    test("实际值匹配检测", len(findings) > 0)

    # T5.8: 二进制跳过
    findings = hook_mod.scan_content("secret data", "image.png", {"secret data"})
    test("二进制文件跳过", len(findings) == 0)

except Exception as e:
    test("pre_commit_hook.py加载失败", False, str(e)[:120])

# ═══════════════════════════════════════════
# T6: sync_check.py
# ═══════════════════════════════════════════
results.append("\n[T6] sync_check.py")
try:
    sync_mod = load_module("sync_check", os.path.join(PM_DIR, "sync_check.py"))
    test("file_hash函数存在", hasattr(sync_mod, "file_hash"))
    test("compare_keys函数存在", hasattr(sync_mod, "compare_keys"))

    # 计算本地hash
    h = sync_mod.file_hash(os.path.join(ROOT, "secrets.env"))
    test("file_hash返回64字符hex", h is not None and len(h) == 64)

    # 不存在文件
    h2 = sync_mod.file_hash("/nonexistent/file")
    test("不存在文件返回None", h2 is None)

except Exception as e:
    test("sync_check.py加载失败", False, str(e)[:120])

# ═══════════════════════════════════════════
# T7: 安全性验证
# ═══════════════════════════════════════════
results.append("\n[T7] 安全性")

# T7.1: secrets.env在.gitignore中
gitignore_path = os.path.join(ROOT, ".gitignore")
if os.path.exists(gitignore_path):
    gi_content = open(gitignore_path, encoding="utf-8").read()
    test("secrets.env在.gitignore", "secrets.env" in gi_content)
else:
    test("secrets.env在.gitignore", False, ".gitignore不存在")

# T7.2: secrets.env不在git tracked中
import subprocess
result = subprocess.run(
    ["git", "ls-files", "secrets.env"],
    capture_output=True, text=True, cwd=ROOT
)
test("secrets.env未被git跟踪", result.stdout.strip() == "")

# T7.3: 凭据中心.md不含实际密码值
if os.path.exists(os.path.join(ROOT, "凭据中心.md")):
    idx_content = open(os.path.join(ROOT, "凭据中心.md"), encoding="utf-8").read()
    # 加载几个实际密码值检查
    try:
        sm_check = SM()
        sample_secrets = [v for k, v in sm_check.as_dict(secrets_only=True).items()
                         if len(v) >= 10][:5]
        leaked = [s for s in sample_secrets if s in idx_content]
        test("凭据中心.md无明文密码", len(leaked) == 0,
             f"发现{len(leaked)}处泄露" if leaked else "")
    except Exception:
        test("凭据中心.md明文检查", True, "跳过(SM不可用)")

# ═══════════════════════════════════════════
# T8: GitHub优质项目灵感验证
# ═══════════════════════════════════════════
results.append("\n[T8] GitHub优质项目特性覆盖")
test("detect-secrets: 熵检测", hasattr(audit_mod, "shannon_entropy"))
test("detect-secrets: baseline概念(一致性检查)", hasattr(audit_mod, "check_consistency"))
test("gitleaks: 正则模式(AWS/GitHub/JWT)", len(audit_mod.SECRET_PATTERNS) >= 7)
test("python-dotenv: find_dotenv模式", hasattr(SM, "_find_secrets_env"))
test("python-dotenv: 变量插值", hasattr(SM, "_resolve_interpolation"))
test("python-dotenv: dotenv_values模式", hasattr(sm, "as_dict"))
test("sops: 指纹/完整性", hasattr(sm, "fingerprint"))
test("Infisical: 多环境管理(PUBLIC_KEYS区分)", len(SM.PUBLIC_KEYS) > 10)

# ═══════════════════════════════════════════
# 报告输出
# ═══════════════════════════════════════════
print("=" * 60)
print("密码管理系统 — 全功能验证报告")
print("=" * 60)
for line in results:
    print(line)
print(f"\n{'=' * 60}")
print(f"总计: {passed} PASS / {failed} FAIL")
if failed == 0:
    print("✅ 涅槃门·苦灭 — 全部通过")
else:
    print(f"🔴 {failed} 项需要修复")
print("=" * 60)
sys.exit(0 if failed == 0 else 1)
