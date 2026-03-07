"""
VaM 插件管理 — BepInEx/Custom Scripts/AddonPackages
"""
from pathlib import Path

from .config import VAM_CONFIG


# ── BepInEx插件 ──

def list_bepinex_plugins() -> list:
    """列出所有BepInEx插件"""
    base = VAM_CONFIG.BEPINEX_PLUGINS
    if not base.exists():
        return []

    plugins = []
    for item in base.iterdir():
        desc = VAM_CONFIG.BEPINEX_KNOWN.get(item.name, "")
        if item.is_dir():
            file_count = sum(1 for _ in item.rglob("*") if _.is_file())
            plugins.append({
                "name": item.name,
                "type": "directory",
                "description": desc,
                "files": file_count,
                "path": str(item),
            })
        elif item.suffix == ".dll":
            plugins.append({
                "name": item.name,
                "type": "dll",
                "description": desc,
                "size_kb": round(item.stat().st_size / 1024, 1),
                "path": str(item),
            })
    return plugins


def check_bepinex_config() -> dict:
    """检查BepInEx配置"""
    cfg_path = VAM_CONFIG.BEPINEX_DIR / "config" / "BepInEx.cfg"
    result = {"config_exists": cfg_path.exists()}

    if cfg_path.exists():
        content = cfg_path.read_text(encoding="utf-8", errors="ignore")
        result["console_enabled"] = "true" in content.lower() and "console" in content.lower()
        result["logging_enabled"] = "[Logging]" in content
        result["size_kb"] = round(cfg_path.stat().st_size / 1024, 1)

    doorstop = VAM_CONFIG.VAM_INSTALL / "doorstop_config.ini"
    if doorstop.exists():
        ds_content = doorstop.read_text(encoding="utf-8", errors="ignore")
        result["doorstop_enabled"] = "enabled=true" in ds_content.lower()
    else:
        result["doorstop_enabled"] = False

    return result


# ── Custom Scripts ──

def list_custom_scripts() -> list:
    """列出Custom/Scripts中的所有脚本"""
    base = VAM_CONFIG.SCRIPTS_DIR
    if not base.exists():
        return []

    scripts = []
    for item in base.iterdir():
        if item.is_dir():
            cs_files = list(item.rglob("*.cs"))
            js_files = list(item.rglob("*.js"))
            cslist_files = list(item.rglob("*.cslist"))
            scripts.append({
                "name": item.name,
                "type": "directory",
                "cs_count": len(cs_files),
                "js_count": len(js_files),
                "cslist_count": len(cslist_files),
                "path": str(item),
            })
        elif item.suffix in VAM_CONFIG.SCRIPT_EXTENSIONS:
            scripts.append({
                "name": item.name,
                "type": item.suffix,
                "size_kb": round(item.stat().st_size / 1024, 1),
                "path": str(item),
            })
    return scripts


def read_script(path: str) -> str:
    """读取脚本内容"""
    return Path(path).read_text(encoding="utf-8", errors="ignore")


def deploy_script(name: str, code: str, subdir: str = "Agent") -> str:
    """部署新脚本到Custom/Scripts"""
    target = VAM_CONFIG.SCRIPTS_DIR / subdir / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(code, encoding="utf-8")
    return str(target)


# ── PluginData ──

def list_plugin_data() -> list:
    """列出Saves/PluginData内容"""
    base = VAM_CONFIG.PLUGIN_DATA
    if not base.exists():
        return []

    items = []
    for d in base.iterdir():
        if d.is_dir():
            file_count = sum(1 for _ in d.rglob("*") if _.is_file())
            items.append({
                "name": d.name,
                "files": file_count,
                "path": str(d),
            })
    return items


# ── PluginPresets ──

def list_plugin_presets() -> list:
    """列出Custom/PluginPresets"""
    base = VAM_CONFIG.PLUGIN_PRESETS
    if not base.exists():
        return []

    presets = []
    for f in base.rglob("*.json"):
        presets.append({
            "name": f.stem,
            "plugin": f.parent.name,
            "path": str(f),
            "size_kb": round(f.stat().st_size / 1024, 1),
        })
    return presets


# ── 综合 ──

def plugin_dashboard() -> dict:
    """插件综合仪表板"""
    return {
        "bepinex_plugins": list_bepinex_plugins(),
        "bepinex_config": check_bepinex_config(),
        "custom_scripts": list_custom_scripts(),
        "plugin_data": list_plugin_data(),
        "plugin_presets": list_plugin_presets(),
    }
