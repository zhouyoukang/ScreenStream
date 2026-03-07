#!/usr/bin/env python3
"""
Git Pre-commit Hook — 阻止凭据泄露提交
灵感来源: gitleaks (17k★) + detect-secrets (4.4k★)

安装:
    # 方法1: 复制到.git/hooks/
    cp 密码管理/pre_commit_hook.py .git/hooks/pre-commit
    chmod +x .git/hooks/pre-commit

    # 方法2: git config
    git config core.hooksPath 密码管理/

功能:
    - 扫描git staged文件中的凭据值
    - 高熵字符串检测 (Base64/Hex entropy)
    - 常见密钥格式正则匹配 (AWS/GitHub/Private Key等)
    - 白名单机制 (# nosecret / allowlist)
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

# ── 高熵检测 (灵感: detect-secrets Base64HighEntropyString) ──

BASE64_CHARS = string.ascii_letters + string.digits + "+/="
HEX_CHARS = string.hexdigits

def shannon_entropy(s: str, charset: str) -> float:
    """计算Shannon信息熵"""
    if not s:
        return 0.0
    counts = Counter(c for c in s if c in charset)
    total = sum(counts.values())
    if total == 0:
        return 0.0
    return -sum((count / total) * math.log2(count / total) for count in counts.values())

def is_high_entropy(s: str, base64_limit: float = 4.5, hex_limit: float = 3.0) -> bool:
    """检测字符串是否为高熵(可能是密钥/Token)"""
    if len(s) < 16:
        return False
    b64_entropy = shannon_entropy(s, BASE64_CHARS)
    hex_entropy = shannon_entropy(s, HEX_CHARS)
    return b64_entropy > base64_limit or hex_entropy > hex_limit


# ── 正则模式检测 (灵感: gitleaks rules) ──

SECRET_PATTERNS = [
    (r'(?i)(password|passwd|pwd)\s*[=:]\s*["\']?([^"\'\s]{8,})', "密码赋值"),
    (r'(?i)(api[_-]?key|apikey)\s*[=:]\s*["\']?([^"\'\s]{16,})', "API Key"),
    (r'(?i)(secret|token)\s*[=:]\s*["\']?([^"\'\s]{16,})', "Secret/Token"),
    (r'AKIA[0-9A-Z]{16}', "AWS Access Key"),
    (r'ghp_[a-zA-Z0-9]{36}', "GitHub PAT"),
    (r'gho_[a-zA-Z0-9]{36}', "GitHub OAuth"),
    (r'glpat-[a-zA-Z0-9\-_]{20,}', "GitLab PAT"),
    (r'sk-[a-zA-Z0-9]{32,}', "OpenAI API Key"),
    (r'-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----', "私钥文件"),
    (r'eyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}', "JWT Token"),
]

# 白名单行标记
ALLOWLIST_MARKERS = {"# nosecret", "# allowlist", "# noqa: secret", "[见secrets.env"}


def load_secret_values():
    """加载secrets.env中的实际凭据值"""
    values = set()
    if not os.path.exists(SECRETS_ENV):
        return values
    non_secret = {
        "LAPTOP_IP", "LAPTOP_HOSTNAME", "DESKTOP_IP", "DESKTOP_HOSTNAME",
        "ALIYUN_IP", "ALIYUN_DOMAIN", "ALIYUN_SSH_USER",
        "HA_URL", "GIT_PROXY", "GIT_USER", "GIT_EMAIL",
        "SSL_EXPIRY", "GLASSES_WIFI_SSID", "GLASSES_WIFI_IP",
        "ALIYUN_CONSOLE_PHONE", "GO1_IP", "GO1_USER", "SUNLOGIN_ID",
        "GITHUB_USER", "HF_ENDPOINT",
        "LAPTOP_MAIN_USER", "LAPTOP_TEST_USER",
        "DESKTOP_USER", "DESKTOP_AI_USER", "DESKTOP_ZHOU_USER",
    }
    with open(SECRETS_ENV, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            if key.strip() in non_secret or key.strip().startswith("PORT_"):
                continue
            value = value.strip()
            if len(value) >= 8 and value not in ("true", "false"):
                values.add(value)
    return values


def get_staged_files():
    """获取git staged的文件列表"""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        capture_output=True, text=True, cwd=PROJECT_ROOT
    )
    if result.returncode != 0:
        return []
    return [f for f in result.stdout.strip().split("\n") if f]


def get_staged_content(filepath):
    """获取staged版本的文件内容"""
    result = subprocess.run(
        ["git", "show", f":{filepath}"],
        capture_output=True, text=True, cwd=PROJECT_ROOT, encoding="utf-8", errors="ignore"
    )
    return result.stdout if result.returncode == 0 else ""


def scan_content(content: str, filepath: str, secret_values: set):
    """扫描内容中的潜在泄露"""
    findings = []
    skip_ext = {".jar", ".png", ".jpg", ".gif", ".ico", ".svg", ".p12",
                ".woff", ".zip", ".gz", ".pdf", ".exe", ".mp3", ".mp4"}
    ext = os.path.splitext(filepath)[1].lower()
    if ext in skip_ext:
        return findings

    for i, line in enumerate(content.split("\n"), 1):
        # 白名单检查
        if any(marker in line for marker in ALLOWLIST_MARKERS):
            continue

        # 检查1: 实际凭据值匹配
        for sv in secret_values:
            if sv in line:
                findings.append((filepath, i, "凭据值泄露", sv[:4] + "..."))

        # 检查2: 正则模式匹配
        for pattern, desc in SECRET_PATTERNS:
            if re.search(pattern, line):
                findings.append((filepath, i, desc, line.strip()[:60]))

        # 检查3: 高熵字符串 (仅对赋值语句)
        assign_match = re.search(r'[=:]\s*["\']?([A-Za-z0-9+/=_-]{20,})["\']?', line)
        if assign_match:
            candidate = assign_match.group(1)
            if is_high_entropy(candidate) and not line.strip().startswith("#"):
                findings.append((filepath, i, "高熵字符串", candidate[:30] + "..."))

    return findings


def main():
    """Pre-commit hook 主入口"""
    staged = get_staged_files()
    if not staged:
        sys.exit(0)

    secret_values = load_secret_values()
    all_findings = []

    for filepath in staged:
        content = get_staged_content(filepath)
        if content:
            findings = scan_content(content, filepath, secret_values)
            all_findings.extend(findings)

    if all_findings:
        print("\n🔴 Pre-commit: 检测到潜在凭据泄露！提交已阻止。\n")
        for f, line, desc, preview in all_findings:
            print(f"  {f}:{line} — {desc}")
            print(f"    {preview}")
        print(f"\n共 {len(all_findings)} 处问题。")
        print("修复方法: 用 [见secrets.env KEY] 替代明文值")
        print("跳过检查: 在行尾添加 # nosecret")
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
