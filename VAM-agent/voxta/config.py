"""
Voxta 统一配置中心 — Voxta AI对话引擎相关路径/常量/服务配置
"""
from pathlib import Path


class VoxtaConfig:
    """Voxta AI对话引擎配置"""

    # ── 根目录 ──
    VAM_ROOT = Path(r"F:\vam1.22")
    AGENT_ROOT = Path(__file__).resolve().parent.parent  # VAM-agent/

    # ── Voxta ──
    VOXTA_DIR = VAM_ROOT / "Voxta" / "Active"
    VOXTA_EXE = VOXTA_DIR / "Voxta.DesktopApp.exe"
    VOXTA_SERVER_EXE = VOXTA_DIR / "Voxta.Server.exe"
    VOXTA_DB = VOXTA_DIR / "Data" / "Voxta.sqlite.db"
    VOXTA_SETTINGS = VOXTA_DIR / "appsettings.json"
    VOXTA_MODULES_DIR = VOXTA_DIR / "Modules"
    VOXTA_RESOURCES = VOXTA_DIR / "Resources"
    VOXTA_MODELS = VOXTA_DIR / "Data" / "Models"

    # ── EdgeTTS (Voxta TTS依赖) ──
    EDGETTS_DIR = VAM_ROOT / "EdgeTTS"
    EDGETTS_SCRIPT = EDGETTS_DIR / "voxta_edge_tts_server.py"

    # ── TextGen (Voxta LLM依赖, 可选) ──
    TEXTGEN_DIR = VAM_ROOT / "text-generation-webui"
    TEXTGEN_BAT = TEXTGEN_DIR / "start_windows.bat"

    # ── 服务端口 ──
    SERVICES = {
        "voxta":      {"port": 5384, "name": "Voxta AI引擎",    "health": "/"},
        "edgetts":    {"port": 5050, "name": "EdgeTTS",         "health": "/health"},
        "textgen":    {"port": 7860, "name": "TextGen-WebUI",   "health": "/"},
        "textgen_api":{"port": 5000, "name": "TextGen API",     "health": "/v1/models"},
    }

    # ── Voxta角色ID ──
    CHARACTERS = {
        "香草":          "67e139a4-e30e-4603-a083-6e89719a9bb2",
        "香草_备用":     "575b8203-3d98-614a-9ef6-b1dcd4949cff",
        "小雅":          "d04c5d25-2788-4852-968b-8bb567d571c2",
        "Catherine":     "575b8203-3d98-614a-9ef6-b1dcd4949cfe",
        "George":        "6227dc38-f656-413f-bba8-773380bad9d9",
        "Voxta":         "35c74d75-e3e4-44af-9389-faade99cc419",
        "Male Narrator": "397f9094-fc15-4e36-9017-a3903a0b9575",
    }

    # ── Voxta场景ID ──
    SCENARIOS = {
        "Voxta UI": "53958F45-47BE-40D1-D2EB-DD5B476769FA",
    }

    # ── Voxta插件 (VaM中的Voxta Client插件storable ID) ──
    VOXTA_PLUGIN_ID = "plugin#0_AcidBubbles.Voxta.83:/Custom/Scripts/Voxta/VoxtaClient.cslist"

    # ── 模块分类 ──
    MODULE_CATEGORIES = {
        "LLM": ["OpenAICompatible", "OpenAI", "KoboldAI", "Oobabooga", "LlamaCpp",
                 "ExLlamaV2", "OpenRouter", "NovelAI", "TextGenerationInference"],
        "TTS": ["F5TTS", "Silero", "Coqui", "ElevenLabs", "TextToSpeechHttpApi",
                "WindowsSpeech", "Azure.SpeechService", "Kokoro"],
        "STT": ["Vosk", "WhisperLive", "Deepgram", "Azure.SpeechService", "WindowsSpeech"],
        "Memory": ["BuiltInSimpleMemory", "BuiltIn.SimpleMemory", "ChromaDb"],
        "Vision": ["BuiltIn.Vision", "Florence2", "FlashCap"],
        "Processing": ["BuiltInReplyPrefixing", "BuiltIn.ReplyPrefixing",
                        "BuiltInTextReplacements", "BuiltIn.TextReplacements",
                        "BuiltIn.ChainOfThought", "BuiltIn.Continuations"],
        "Audio": ["NAudio", "BuiltInAudioRms", "BuiltIn.AudioRms"],
    }

    def path_exists(self, path: Path) -> bool:
        return path.exists()

    def get_all_critical_paths(self) -> dict:
        """返回所有Voxta关键路径及其存在状态"""
        paths = {
            "Voxta桌面端": self.VOXTA_EXE,
            "Voxta服务端": self.VOXTA_SERVER_EXE,
            "Voxta数据库": self.VOXTA_DB,
            "Voxta配置": self.VOXTA_SETTINGS,
            "EdgeTTS脚本": self.EDGETTS_SCRIPT,
            "TextGen启动": self.TEXTGEN_BAT,
        }
        return {name: {"path": str(p), "exists": p.exists()} for name, p in paths.items()}


VOXTA_CONFIG = VoxtaConfig()
