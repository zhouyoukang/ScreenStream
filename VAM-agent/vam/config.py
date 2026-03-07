"""
VaM 配置中心 — VaM 3D引擎相关路径/常量配置

Voxta相关配置已迁移至 voxta/config.py
"""
from pathlib import Path


class VaMConfig:
    """VaM 3D引擎配置"""

    # ── 根目录 ──
    VAM_ROOT = Path(r"F:\vam1.22")
    VAM_INSTALL = VAM_ROOT / "VAM版本" / "vam1.22.1.0"
    VAM2_INSTALL = VAM_ROOT / "VAM版本" / "VAM2 Beta1.0"
    AGENT_ROOT = Path(__file__).resolve().parent.parent  # VAM-agent/

    # ── VaM 主程序 ──
    VAM_EXE = VAM_INSTALL / "VaM.exe"
    VAM_PREFS = VAM_INSTALL / "prefs.json"
    VAM_CONFIG_FILE = VAM_INSTALL / "config"
    VAM_LOG = VAM_INSTALL / "VaM_Data" / "output_log.txt"
    VAM_VERSION = "1.22.1.0"
    VAM_BOX_PASS = None  # [见secrets.env VAM_BOX_PASS]

    # ── VaM 目录结构 ──
    SCENES_DIR = VAM_INSTALL / "Saves" / "scene"
    SCENES_GENERATED = SCENES_DIR / "Generated"
    CUSTOM_DIR = VAM_INSTALL / "Custom"
    SCRIPTS_DIR = CUSTOM_DIR / "Scripts"
    ADDON_PACKAGES = VAM_INSTALL / "AddonPackages"
    PLUGIN_DATA = VAM_INSTALL / "Saves" / "PluginData"
    APPEARANCES_DIR = CUSTOM_DIR / "Atom" / "Person" / "Appearance"
    CLOTHING_DIR = CUSTOM_DIR / "Clothing"
    HAIR_DIR = CUSTOM_DIR / "Hair"
    ASSETS_DIR = CUSTOM_DIR / "Assets"
    SUBSCENE_DIR = CUSTOM_DIR / "SubScene"
    PLUGIN_PRESETS = CUSTOM_DIR / "PluginPresets"
    IMAGES_DIR = CUSTOM_DIR / "Images"
    SOUNDS_DIR = CUSTOM_DIR / "Sounds"
    CACHE_DIR = VAM_INSTALL / "Cache"
    BEPINEX_DIR = VAM_INSTALL / "BepInEx"
    BEPINEX_PLUGINS = BEPINEX_DIR / "plugins"

    # ── Scripter ──
    SCRIPTER_DIR = VAM_ROOT / "scripter.github"
    SCRIPTER_VAR = SCRIPTER_DIR / "AcidBubbles.Scripter1.21.var"

    # ── 资源文件 ──
    RESOURCES_DIR = VAM_ROOT / "资源文件"
    BROWSER_ASSIST = VAM_ROOT / "BrowserAssist付费版"
    DOCUMENTATION = VAM_ROOT / "Documentation"

    # ── VaM Box (可选，不存在则跳过) ──
    VAMBOX_EXE = Path(r"E:\浏览器下载\vambox-v0.9.2\vambox-win32-x64\vambox.exe")

    # ── BepInEx插件 ──
    BEPINEX_KNOWN = {
        "FasterVaM.dll":     "性能优化",
        "MMDPlayer.dll":     "MMD动画播放",
        "RenderToMovie.dll": "视频录制",
        "RenderToVR.dll":    "VR渲染",
        "SuperMode.dll":     "超级模式",
        "DAZClothingMod.dll":"服装修改",
        "XUnity.AutoTranslator": "自动翻译(中文化)",
        "Console":           "IronPython控制台(VNGE)",
    }

    # ── 文件类型 ──
    SCENE_EXTENSIONS = {".json"}
    SCRIPT_EXTENSIONS = {".cs", ".cslist", ".js"}
    VAR_EXTENSION = ".var"
    APPEARANCE_EXTENSIONS = {".json", ".vap"}

    def path_exists(self, path: Path) -> bool:
        return path.exists()

    def get_all_critical_paths(self) -> dict:
        """返回所有VaM关键路径及其存在状态"""
        paths = {
            "VaM主程序": self.VAM_EXE,
            "VaM日志": self.VAM_LOG,
            "场景目录": self.SCENES_DIR,
            "脚本目录": self.SCRIPTS_DIR,
            "插件包目录": self.ADDON_PACKAGES,
            "Scripter插件": self.SCRIPTER_VAR,
        }
        return {name: {"path": str(p), "exists": p.exists()} for name, p in paths.items()}


VAM_CONFIG = VaMConfig()
