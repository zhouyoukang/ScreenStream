"""
CosyVoice TTS 模块 — 阿里云百炼语音合成
用法: python cosyvoice_tts.py --key sk-xxx --text "你好" --output test.mp3
或作为模块导入: from cosyvoice_tts import synthesize
"""
import os, sys

# CosyVoice 配置
MODEL = "cosyvoice-v3-plus"
VOICE = "longanyang"  # 龙安洋: 阳光大男孩, 20-30岁, 支持旁白+情感
INSTRUCT = "你现在说话的角色是一个旁白，你说话的情感是neutral。"


def synthesize(text: str, output_path: str, api_key: str = None,
               voice: str = VOICE, speech_rate: float = 0.9,
               pitch_rate: float = 1.0) -> bool:
    """
    用 CosyVoice 合成语音，保存为 MP3
    返回 True=成功, False=失败(应降级到 edge-tts)
    speech_rate: 0.5~2.0, 默认0.9(略慢,适合旁白)
    pitch_rate: 0.5~2.0, 默认1.0
    """
    key = api_key or os.environ.get("DASHSCOPE_API_KEY")
    if not key:
        print("  [CosyVoice] 无 API key，降级到 edge-tts")
        return False

    try:
        import dashscope
        from dashscope.audio.tts_v2 import SpeechSynthesizer
    except ImportError:
        print("  [CosyVoice] dashscope SDK 未安装，降级到 edge-tts")
        return False

    dashscope.api_key = key
    dashscope.base_websocket_api_url = 'wss://dashscope.aliyuncs.com/api-ws/v1/inference'

    try:
        synthesizer = SpeechSynthesizer(
            model=MODEL,
            voice=voice,
            speech_rate=speech_rate,
            pitch_rate=pitch_rate,
        )
        audio = synthesizer.call(text)
        if audio:
            with open(output_path, 'wb') as f:
                f.write(audio)
            delay = synthesizer.get_first_package_delay()
            print(f"  [CosyVoice] ✓ {len(audio)/1024:.0f}KB, 首包{delay}ms")
            return True
        else:
            print(f"  [CosyVoice] ✗ 合成返回空")
            return False
    except Exception as e:
        print(f"  [CosyVoice] ✗ {e}")
        return False


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="CosyVoice TTS 测试")
    parser.add_argument("--key", required=True, help="DashScope API Key")
    parser.add_argument("--text", default="这是一段测试语音。意识流编程，完整版。", help="合成文本")
    parser.add_argument("--output", default="cosyvoice_test.mp3", help="输出文件")
    args = parser.parse_args()
    ok = synthesize(args.text, args.output, api_key=args.key)
    if ok:
        print(f"成功! 保存到 {args.output}")
    else:
        print("失败!")
        sys.exit(1)
