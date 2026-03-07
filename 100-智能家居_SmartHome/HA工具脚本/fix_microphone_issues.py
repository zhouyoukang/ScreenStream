#!/usr/bin/env python3
"""
Home Assistant 麦克风问题修复工具
"""
import json
import os
import shutil
from datetime import datetime

def backup_config(file_path):
    """备份配置文件"""
    backup_path = f"{file_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(file_path, backup_path)
    print(f"✅ 已备份配置文件到: {backup_path}")
    return backup_path

def fix_assist_pipeline_stt():
    """修复语音识别管道配置"""
    config_file = "config/.storage/assist_pipeline.pipelines"
    
    if not os.path.exists(config_file):
        print(f"❌ 找不到配置文件: {config_file}")
        return False
    
    # 备份
    backup_config(config_file)
    
    # 读取配置
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    print("🔍 检查STT配置...")
    
    updated = False
    for item in config['data']['items']:
        name = item.get('name', 'Unknown')
        stt_engine = item.get('stt_engine')
        
        if stt_engine is None:
            print(f"⚠️ 发现问题: '{name}' 没有STT引擎")
            # 设置为使用本地faster_whisper
            item['stt_engine'] = 'stt.faster_whisper'
            item['stt_language'] = 'zh'
            print(f"✅ 已修复: '{name}' -> stt.faster_whisper")
            updated = True
        else:
            print(f"✅ 正常: '{name}' -> {stt_engine}")
    
    # 确保默认pipeline有STT
    preferred_id = config['data'].get('preferred_item')
    if preferred_id:
        for item in config['data']['items']:
            if item['id'] == preferred_id:
                if item.get('stt_engine') is None:
                    item['stt_engine'] = 'stt.faster_whisper'
                    item['stt_language'] = 'zh'
                    print(f"✅ 已修复默认pipeline: {item.get('name')}")
                    updated = True
                break
    
    if updated:
        # 保存修改
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print("✅ 配置已更新")
        return True
    else:
        print("ℹ️ STT配置正常，无需修改")
        return False

def check_microphone_permissions():
    """检查麦克风权限建议"""
    print("\n🎤 麦克风权限检查清单:")
    print("=" * 50)
    
    print("\n1️⃣ 浏览器权限:")
    print("   - 检查地址栏左侧的🔒图标")
    print("   - 确保麦克风权限设为'允许'")
    print("   - 尝试刷新页面并重新授权")
    
    print("\n2️⃣ Windows系统权限:")
    print("   - 设置 > 隐私和安全性 > 麦克风")
    print("   - 确保'允许应用访问麦克风'已开启")
    print("   - 确保浏览器在允许列表中")
    
    print("\n3️⃣ Home Assistant设置:")
    print("   - 确保使用HTTPS访问(http://IP地址可能被浏览器阻止麦克风)")
    print("   - 检查 设置 > 系统 > 音频 中的设备配置")
    
    print("\n4️⃣ 浏览器测试:")
    print("   - 访问 https://mictests.com 测试麦克风")
    print("   - 如果外部网站正常，问题在HA配置")
    
    print("\n5️⃣ 网络问题:")
    print("   - 确保没有使用代理/VPN")
    print("   - 尝试不同网络环境")

def main():
    print("🔧 Home Assistant 麦克风问题诊断工具")
    print("=" * 50)
    
    # 修复STT配置
    stt_fixed = fix_assist_pipeline_stt()
    
    # 检查权限
    check_microphone_permissions()
    
    print("\n📋 下一步操作:")
    if stt_fixed:
        print("1. 重启 Home Assistant")
        print("2. 清除浏览器缓存并刷新页面")
    print("3. 检查浏览器麦克风权限")
    print("4. 测试语音识别功能")
    
    print("\n💡 如果问题仍然存在:")
    print("   - 尝试不同浏览器 (Chrome/Edge/Firefox)")
    print("   - 检查Home Assistant日志")
    print("   - 确认Wyoming服务正常运行")

if __name__ == "__main__":
    main()

