#!/usr/bin/env python3
"""
修复Home Assistant语音助手管道配置
"""
import json
import shutil
from pathlib import Path

def fix_pipeline_config():
    """修复管道配置，将包含STT的管道设为默认"""
    
    config_file = Path("config/.storage/assist_pipeline.pipelines")
    backup_file = Path("config/.storage/assist_pipeline.pipelines.backup")
    
    print("🔧 开始修复Assistant管道配置...")
    
    # 备份原文件
    shutil.copy2(config_file, backup_file)
    print(f"✅ 已备份原配置文件到: {backup_file}")
    
    # 读取配置
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # 查找有STT配置的管道
    pipelines = config['data']['items']
    stt_pipelines = []
    
    for pipeline in pipelines:
        if pipeline.get('stt_engine') == 'stt.faster_whisper':
            stt_pipelines.append(pipeline)
            print(f"🎤 找到STT管道: {pipeline['name']} (ID: {pipeline['id']})")
    
    if not stt_pipelines:
        print("❌ 没有找到配置了STT的管道")
        return False
    
    # 选择最合适的管道（优先选择包含"千问3"或"local-qwen3"的）
    preferred_pipeline = None
    for pipeline in stt_pipelines:
        if 'local-qwen3' in pipeline['name'] or '千问3' in pipeline['name']:
            preferred_pipeline = pipeline
            break
    
    if not preferred_pipeline:
        preferred_pipeline = stt_pipelines[0]  # 选择第一个
    
    # 更新默认管道
    old_preferred = config['data']['preferred_item']
    config['data']['preferred_item'] = preferred_pipeline['id']
    
    # 保存配置
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    print(f"✅ 已将默认管道从 '{old_preferred}' 更改为:")
    print(f"   名称: {preferred_pipeline['name']}")
    print(f"   ID: {preferred_pipeline['id']}")
    print(f"   STT引擎: {preferred_pipeline['stt_engine']}")
    print(f"   STT语言: {preferred_pipeline['stt_language']}")
    print(f"   TTS引擎: {preferred_pipeline['tts_engine']}")
    
    return True

if __name__ == "__main__":
    success = fix_pipeline_config()
    if success:
        print("\n🎯 修复完成！请重启Home Assistant以应用更改。")
        print("💡 重启后，语音识别应该能正常工作了。")
    else:
        print("\n❌ 修复失败，请检查配置文件。")

