"""
密码管理审计脚本 — 检测git tracked文件中的凭据泄露
用法: python audit.py [--entropy] [--patterns] [--consistency]

灵感来源:
  - Yelp/detect-secrets (4.4k★) — 熵检测 + 插件架构 + baseline概念
  - gitleaks (17k★) — 正则模式匹配
  - python-dotenv (7k★) — .env加载模式
"""
import subprocess
import sys
import os
import re
import math
import string
from collections import Counter

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRETS_ENV = os.path.join(PROJECT_ROOT, "secrets.env")


# Keys whose values are PUBLIC config (IPs, domains, ports, dates) — safe in tracked files
NON_SECRET_KEYS = {
    "LAPTOP_IP", "LAPTOP_HOSTNAME", "DESKTOP_IP", "DESKTOP_HOSTNAME",
    "ALIYUN_IP", "ALIYUN_DOMAIN", "ALIYUN_SSH_USER",
    "HA_URL", "GIT_PROXY", "GIT_USER", "GIT_EMAIL",
    "SSL_EXPIRY", "AGI_DASHBOARD_PORT",
    "GO1_IP", "GO1_USER",
    "SUNLOGIN_ID",  # not a credential, just a device ID
    "GITHUB_USER", "HF_ENDPOINT",
    "LAPTOP_MAIN_USER", "LAPTOP_TEST_USER",
    "DESKTOP_USER", "DESKTOP_AI_USER", "DESKTOP_ZHOU_USER",
    "GLASSES_WIFI_SSID", "GLASSES_WIFI_IP",
    "ALIYUN_CONSOLE_PHONE",
    # Port assignments
    "PORT_GATEWAY", "PORT_MJPEG", "PORT_RTSP", "PORT_WEBRTC",
    "PORT_INPUT", "PORT_BRAIN", "PORT_GO1_UDP",
}


# ── 高熵检测 (detect-secrets Base64HighEntropyString/HexHighEntropyString) ──

BASE64_CHARS = string.ascii_letters + string.digits + "+/="
HEX_CHARS = string.hexdigits

def shannon_entropy(s: str, charset: str) -> float:
    """Shannon信息熵"""
    if not s:
        return 0.0
    counts = Counter(c for c in s if c in charset)
    total = sum(counts.values())
    if total == 0:
        return 0.0
    return -sum((count / total) * math.log2(count / total) for count in counts.values())

def is_high_entropy(s: str, b64_limit: float = 4.5, hex_limit: float = 3.0) -> bool:
    """detect-secrets模式: 检测字符串是否为高熵(可能是密钥/Token)"""
    if len(s) < 16:
        return False
    return (shannon_entropy(s, BASE64_CHARS) > b64_limit or
            shannon_entropy(s, HEX_CHARS) > hex_limit)

# ── 正则模式检测 (gitleaks rules) ──

SECRET_PATTERNS = [
    (re.compile(r'AKIA[0-9A-Z]{16}'), "AWS Access Key"),
    (re.compile(r'ghp_[a-zA-Z0-9]{36}'), "GitHub PAT"),
    (re.compile(r'gho_[a-zA-Z0-9]{36}'), "GitHub OAuth"),
    (re.compile(r'glpat-[a-zA-Z0-9\-_]{20,}'), "GitLab PAT"),
    (re.compile(r'sk-[a-zA-Z0-9]{32,}'), "OpenAI API Key"),
    (re.compile(r'-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----'), "私钥文件"),
    (re.compile(r'eyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}'), "JWT Token"),
]

ALLOWLIST_MARKERS = {"# nosecret", "# allowlist", "[见secrets.env"}

# 高熵误报过滤 (detect-secrets filter模式)
ENTROPY_FALSE_POSITIVE_PATTERNS = [
    re.compile(r'ABCDEFGHIJKLMNOP'),  # Base64/Hex alphabet definitions
    re.compile(r'abcdefghijklmnop'),  # lowercase alphabet
    re.compile(r'0123456789'),        # digit sequences
    re.compile(r'pub[0-9a-f]{20,}'),  # AdMob publisher IDs (public)
    re.compile(r'ca-app-pub-'),       # AdMob app IDs
    re.compile(r'sha256/'),           # Certificate pinning hashes
    re.compile(r'[0-9a-f]{64}'),      # SHA256 hex hashes (fingerprints)
]


def load_secrets():
    """从secrets.env加载敏感凭据值（排除公开配置如IP/域名/端口）"""
    secrets = {}
    if not os.path.exists(SECRETS_ENV):
        print(f"[WARN] secrets.env not found: {SECRETS_ENV}")
        return secrets
    with open(SECRETS_ENV, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if key in NON_SECRET_KEYS:
                continue
            if len(value) >= 8 and not value.startswith("[") and value not in ("true", "false"):
                secrets[key] = value
    return secrets


def get_tracked_files():
    """获取所有git tracked文件"""
    result = subprocess.run(
        ["git", "ls-files"],
        capture_output=True, text=True, cwd=PROJECT_ROOT, encoding="utf-8"
    )
    if result.returncode != 0:
        print(f"[ERROR] git ls-files failed: {result.stderr}")
        return []
    return [f for f in result.stdout.strip().split("\n") if f]


def scan_for_leaks(secrets, tracked_files, enable_entropy=False, enable_patterns=False):
    """扫描tracked文件中的凭据泄露
    三层检测 (detect-secrets + gitleaks 融合):
      1. 实际值匹配: secrets.env中的值是否出现在tracked文件
      2. 正则模式: AWS Key/GitHub PAT/JWT等常见格式
      3. 高熵检测: Shannon熵超过阈值的字符串
    """
    leaks = []
    skip_extensions = {".jar", ".png", ".jpg", ".gif", ".ico", ".svg", ".p12",
                       ".woff", ".woff2", ".ttf", ".eot", ".zip", ".gz", ".pdf",
                       ".docx", ".xlsx", ".pptx", ".msi", ".exe", ".mp3", ".mp4"}
    
    for filepath in tracked_files:
        ext = os.path.splitext(filepath)[1].lower()
        if ext in skip_extensions:
            continue
        
        full_path = os.path.join(PROJECT_ROOT, filepath)
        if not os.path.exists(full_path):
            continue
        
        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except (OSError, UnicodeDecodeError):
            continue
        
        # 层级1: 实际值匹配
        for key, value in secrets.items():
            if value in content:
                if filepath in ("secrets.env",):
                    continue
                leaks.append({
                    "file": filepath,
                    "key": key,
                    "type": "凭据值泄露",
                    "value_preview": value[:4] + "..." + value[-4:] if len(value) > 12 else "***"
                })
        
        # 层级2: 正则模式匹配 (gitleaks模式)
        if enable_patterns:
            for line_num, line in enumerate(content.split("\n"), 1):
                if any(m in line for m in ALLOWLIST_MARKERS):
                    continue
                for pattern, desc in SECRET_PATTERNS:
                    if pattern.search(line):
                        leaks.append({
                            "file": filepath,
                            "key": f"L{line_num}",
                            "type": desc,
                            "value_preview": line.strip()[:50]
                        })
        
        # 层级3: 高熵检测 (detect-secrets模式)
        if enable_entropy:
            for line_num, line in enumerate(content.split("\n"), 1):
                if any(m in line for m in ALLOWLIST_MARKERS):
                    continue
                assign = re.search(r'[=:]\s*["\']?([A-Za-z0-9+/=_-]{20,})["\']?', line)
                if assign and not line.strip().startswith("#"):
                    candidate = assign.group(1)
                    # 误报过滤 (detect-secrets filter模式)
                    if any(p.search(candidate) for p in ENTROPY_FALSE_POSITIVE_PATTERNS):
                        continue
                    if is_high_entropy(candidate):
                        leaks.append({
                            "file": filepath,
                            "key": f"L{line_num}",
                            "type": "高熵字符串",
                            "value_preview": candidate[:30] + "..."
                        })
    
    return leaks


def check_consistency():
    """检查凭据中心.md ↔ secrets.env 一致性 (detect-secrets baseline概念)"""
    index_path = os.path.join(PROJECT_ROOT, "凭据中心.md")
    if not os.path.exists(index_path):
        print("[WARN] 凭据中心.md 不存在")
        return True

    # 从secrets.env提取键
    env_keys = set()
    if os.path.exists(SECRETS_ENV):
        with open(SECRETS_ENV, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    env_keys.add(line.split("=", 1)[0].strip())

    # 从凭据中心.md提取 `KEY` 格式的键名
    index_keys = set()
    with open(index_path, "r", encoding="utf-8") as f:
        for line in f:
            for m in re.findall(r'`([A-Z][A-Z0-9_]+)`', line):
                if m in env_keys:  # 只统计实际存在的键
                    index_keys.add(m)

    only_env = env_keys - index_keys
    only_index = index_keys - env_keys

    ok = True
    if only_env:
        print(f"\n⚠️  仅secrets.env有 ({len(only_env)}): {', '.join(sorted(only_env))}")
        ok = False
    if only_index:
        print(f"\n⚠️  仅凭据中心.md有 ({len(only_index)}): {', '.join(sorted(only_index))}")
        ok = False
    if ok:
        print(f"\n✅ 凭据中心.md ↔ secrets.env 一致 ({len(env_keys)}键)")
    return ok


def main():
    print("=" * 60)
    print("密码管理审计 — 凭据泄露扫描")
    print("=" * 60)
    
    enable_entropy = "--entropy" in sys.argv
    enable_patterns = "--patterns" in sys.argv
    enable_consistency = "--consistency" in sys.argv
    enable_all = "--all" in sys.argv
    if enable_all:
        enable_entropy = enable_patterns = enable_consistency = True
    
    secrets = load_secrets()
    print(f"\n[INFO] 从secrets.env加载了 {len(secrets)} 个凭据")
    
    tracked_files = get_tracked_files()
    print(f"[INFO] 扫描 {len(tracked_files)} 个git tracked文件")
    
    modes = ["实际值匹配"]
    if enable_patterns:
        modes.append("正则模式")
    if enable_entropy:
        modes.append("熵检测")
    print(f"[INFO] 检测模式: {' + '.join(modes)}")
    
    leaks = scan_for_leaks(secrets, tracked_files, enable_entropy, enable_patterns)
    
    exit_code = 0
    if leaks:
        print(f"\n🔴 发现 {len(leaks)} 处泄露:")
        for leak in leaks:
            t = leak.get('type', '凭据值')
            print(f"  - [{t}] {leak['file']}: {leak['key']} ({leak['value_preview']})")
        print("\n建议: 用 [见secrets.env KEY] 替换明文值")
        exit_code = 1
    else:
        print(f"\n✅ 未发现凭据泄露 — 涅槃门·苦灭 ✓")
    
    if enable_consistency:
        print("\n" + "-" * 40)
        print("一致性检查:")
        if not check_consistency():
            exit_code = 1
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
