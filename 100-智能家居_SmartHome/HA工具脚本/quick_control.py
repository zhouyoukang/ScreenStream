#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速控制脚本 - 提供简单的命令行接口来控制智能家居设备
"""

import sys
import argparse
from smart_home_controller import SmartHomeController

def main():
    parser = argparse.ArgumentParser(description='智能家居快速控制')
    
    # 添加子命令
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 灯光控制
    light_parser = subparsers.add_parser('light', help='控制灯光')
    light_parser.add_argument('action', choices=['on', 'off', 'toggle'], help='灯光操作')
    
    # 音乐控制
    music_parser = subparsers.add_parser('music', help='控制音乐')
    music_parser.add_argument('action', choices=['play', 'pause', 'stop'], help='音乐操作')
    
    # AI助手控制
    ai_parser = subparsers.add_parser('ai', help='控制AI助手')
    ai_parser.add_argument('assistant', choices=['doubao', 'kimi'], help='AI助手类型')
    ai_parser.add_argument('action', choices=['start', 'stop'], help='AI助手操作')
    
    # 系统状态
    status_parser = subparsers.add_parser('status', help='查看系统状态')
    
    # 语音控制
    voice_parser = subparsers.add_parser('speak', help='语音播放')
    voice_parser.add_argument('text', help='要播放的文字')
    
    # Rhasspy训练
    train_parser = subparsers.add_parser('train', help='训练Rhasspy模型')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # 创建控制器
    controller = SmartHomeController()
    
    # 执行命令
    if args.command == 'light':
        success = controller.control_bedroom_light(args.action)
        print(f"💡 床底灯{args.action}: {'成功' if success else '失败'}")
        
    elif args.command == 'music':
        success = controller.control_music_player(args.action)
        print(f"🎵 音乐{args.action}: {'成功' if success else '失败'}")
        
    elif args.command == 'ai':
        success = controller.control_ai_assistant(args.assistant, args.action)
        print(f"🤖 AI助手{args.assistant} {args.action}: {'成功' if success else '失败'}")
        
    elif args.command == 'status':
        status = controller.get_system_status()
        print("📊 智能家居系统状态:")
        print(f"  Node-RED: {'✅ 已连接' if status['nodered_connected'] else '❌ 未连接'}")
        print(f"  Rhasspy: {'✅ 已连接' if status['rhasspy_connected'] else '❌ 未连接'}")
        print(f"  流程数量: {status['flows_count']}")
        if status['power_usage']:
            print(f"  功率使用: {status['power_usage']}W")
        
    elif args.command == 'speak':
        success = controller.speak_text(args.text)
        print(f"🎙️ 语音播放: {'成功' if success else '失败'}")
        
    elif args.command == 'train':
        success = controller.train_rhasspy()
        print(f"🎯 Rhasspy训练: {'开始' if success else '失败'}")

if __name__ == "__main__":
    main()

