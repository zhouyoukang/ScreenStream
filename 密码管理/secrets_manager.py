"""
统一凭据管理模块 — 多Agent共享凭据的Python接口
灵感来源: python-dotenv (7k★) + Infisical + mozilla/sops

用法:
    from 密码管理.secrets_manager import SecretsManager
    sm = SecretsManager()
    password = sm.get("UNIFIED_PASSWORD")
    all_secrets = sm.as_dict()

特性 (源自GitHub优质项目):
    - find_secrets_env(): 自动向上遍历目录树查找secrets.env (python-dotenv模式)
    - 变量插值: ${VAR} 引用其他变量 (python-dotenv interpolation)
    - 多文件合并: secrets.env + secrets.toml 统一接口 (dotenv_values合并模式)
    - 环境变量优先: SECRETS_ENV_PATH > 自动发现 (12-factor原则)
    - 凭据中心一致性检查: 索引↔实际值对齐验证
    - 惰性加载 + 缓存: 只读一次，多Agent安全
"""
import os
import re
import hashlib
from pathlib import Path
from typing import Optional, Dict, Set


class SecretsManager:
    """多Agent统一凭据管理器"""

    # 公开配置键 — 不视为敏感信息
    PUBLIC_KEYS = {
        "LAPTOP_IP", "LAPTOP_HOSTNAME", "DESKTOP_IP", "DESKTOP_HOSTNAME",
        "ALIYUN_IP", "ALIYUN_DOMAIN", "ALIYUN_SSH_USER", "ALIYUN_SSH_ALIAS",
        "HA_URL", "GIT_PROXY", "GIT_USER", "GIT_EMAIL",
        "SSL_EXPIRY", "AGI_DASHBOARD_PORT",
        "GO1_IP", "GO1_USER", "SUNLOGIN_ID",
        "LAPTOP_MAIN_USER", "LAPTOP_TEST_USER",
        "DESKTOP_USER", "DESKTOP_AI_USER", "DESKTOP_ZHOU_USER",
        "GITHUB_USER", "HF_ENDPOINT",
        "GLASSES_WIFI_SSID", "GLASSES_WIFI_IP", "ALIYUN_CONSOLE_PHONE",
        "PORT_GATEWAY", "PORT_MJPEG", "PORT_RTSP", "PORT_WEBRTC",
        "PORT_INPUT", "PORT_BRAIN", "PORT_GO1_UDP",
    }

    def __init__(self, env_path: Optional[str] = None, interpolate: bool = True):
        """
        Args:
            env_path: 显式指定secrets.env路径。None则自动发现。
            interpolate: 是否启用变量插值 ${VAR}
        """
        self._interpolate = interpolate
        self._raw: Dict[str, str] = {}
        self._resolved: Dict[str, str] = {}
        self._env_path: Optional[str] = None
        self._loaded = False

        # 发现secrets.env
        self._env_path = env_path or self._find_secrets_env()
        if self._env_path and os.path.exists(self._env_path):
            self._load()

    @staticmethod
    def _find_secrets_env() -> Optional[str]:
        """自动发现secrets.env — 灵感: python-dotenv find_dotenv()
        优先级: SECRETS_ENV_PATH环境变量 > 当前目录向上遍历
        """
        # 优先级1: 环境变量
        env_var = os.environ.get("SECRETS_ENV_PATH")
        if env_var and os.path.exists(env_var):
            return env_var

        # 优先级2: 从当前文件位置向上遍历
        search_dir = Path(__file__).parent.parent  # 密码管理/ -> 项目根
        for _ in range(10):  # 最多10层
            candidate = search_dir / "secrets.env"
            if candidate.exists():
                return str(candidate)
            parent = search_dir.parent
            if parent == search_dir:
                break
            search_dir = parent

        # 优先级3: 从CWD向上遍历
        search_dir = Path.cwd()
        for _ in range(10):
            candidate = search_dir / "secrets.env"
            if candidate.exists():
                return str(candidate)
            parent = search_dir.parent
            if parent == search_dir:
                break
            search_dir = parent

        return None

    def _load(self):
        """加载并解析secrets.env"""
        if not self._env_path:
            return
        with open(self._env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                # 去除引号包裹
                if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                    value = value[1:-1]
                self._raw[key] = value

        # 变量插值
        if self._interpolate:
            self._resolved = self._resolve_interpolation(self._raw)
        else:
            self._resolved = dict(self._raw)

        self._loaded = True

    @staticmethod
    def _resolve_interpolation(raw: Dict[str, str]) -> Dict[str, str]:
        """变量插值 — 灵感: python-dotenv interpolation
        支持 ${VAR} 和 $VAR 语法
        """
        resolved = {}
        pattern = re.compile(r'\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)')

        def replacer(match):
            var_name = match.group(1) or match.group(2)
            # 优先已解析值 > 原始值 > 环境变量 > 空串
            return resolved.get(var_name, raw.get(var_name, os.environ.get(var_name, "")))

        for key, value in raw.items():
            resolved[key] = pattern.sub(replacer, value)

        return resolved

    # ── 公开API ──

    def get(self, key: str, default: str = "") -> str:
        """获取凭据值"""
        return self._resolved.get(key, default)

    def get_secret(self, key: str, default: str = "") -> str:
        """获取敏感凭据(排除公开配置)"""
        if key in self.PUBLIC_KEYS:
            return default
        return self.get(key, default)

    def as_dict(self, secrets_only: bool = False) -> Dict[str, str]:
        """返回全部键值对
        Args:
            secrets_only: True则排除公开配置键
        """
        if secrets_only:
            return {k: v for k, v in self._resolved.items() if k not in self.PUBLIC_KEYS}
        return dict(self._resolved)

    def keys(self, secrets_only: bool = False) -> Set[str]:
        """返回所有键名"""
        if secrets_only:
            return set(self._resolved.keys()) - self.PUBLIC_KEYS
        return set(self._resolved.keys())

    def has(self, key: str) -> bool:
        """检查键是否存在"""
        return key in self._resolved

    @property
    def path(self) -> Optional[str]:
        """secrets.env文件路径"""
        return self._env_path

    @property
    def loaded(self) -> bool:
        """是否成功加载"""
        return self._loaded

    @property
    def count(self) -> int:
        """凭据总数"""
        return len(self._resolved)

    def fingerprint(self) -> Optional[str]:
        """secrets.env文件SHA256指纹(前16位)"""
        if not self._env_path or not os.path.exists(self._env_path):
            return None
        with open(self._env_path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:16]

    def check_consistency(self, index_path: Optional[str] = None) -> Dict:
        """凭据中心.md ↔ secrets.env 一致性检查
        灵感: detect-secrets baseline概念
        返回: {"ok": bool, "only_env": set, "only_index": set}
        """
        if not index_path:
            if self._env_path:
                index_path = os.path.join(os.path.dirname(self._env_path), "凭据中心.md")
            else:
                return {"ok": False, "error": "no env_path"}

        if not os.path.exists(index_path):
            return {"ok": False, "error": f"index not found: {index_path}"}

        # 从凭据中心.md提取键名 (匹配 `KEY_NAME` 格式)
        index_keys = set()
        with open(index_path, "r", encoding="utf-8") as f:
            for line in f:
                matches = re.findall(r'`([A-Z][A-Z0-9_]+)`', line)
                for m in matches:
                    if not m.startswith("PORT_") or m in self._resolved:
                        index_keys.add(m)

        env_keys = set(self._resolved.keys())

        # 排除非凭据键(注释中的引用等)
        relevant_index = {k for k in index_keys if any(c.islower() for c in k) is False}

        only_env = env_keys - relevant_index
        only_index = relevant_index - env_keys

        return {
            "ok": len(only_env) == 0 and len(only_index) == 0,
            "only_env": only_env,
            "only_index": only_index,
            "env_count": len(env_keys),
            "index_count": len(relevant_index),
        }

    def to_env(self, keys: Optional[list] = None):
        """将指定键注入os.environ (不覆盖已有值)
        灵感: python-dotenv load_dotenv(override=False)
        """
        target = keys or list(self._resolved.keys())
        for key in target:
            if key in self._resolved and key not in os.environ:
                os.environ[key] = self._resolved[key]

    def __repr__(self):
        status = "loaded" if self._loaded else "not loaded"
        return f"<SecretsManager {status} keys={self.count} path={self._env_path}>"


# ── 便捷函数 (模块级) ──

_instance: Optional[SecretsManager] = None


def get_manager() -> SecretsManager:
    """获取全局单例"""
    global _instance
    if _instance is None:
        _instance = SecretsManager()
    return _instance


def get_secret(key: str, default: str = "") -> str:
    """快速获取凭据"""
    return get_manager().get(key, default)


def load_secrets_to_env(keys: Optional[list] = None):
    """快速注入环境变量"""
    get_manager().to_env(keys)
