#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动化场景示例 - 展示如何创建复杂的智能家居自动化场景
"""

import time
import schedule
from datetime import datetime
from smart_home_controller import SmartHomeController

class AutomationScenes:
    """自动化场景管理器"""
    
    def __init__(self):
        self.controller = SmartHomeController()
        
    def morning_routine(self):
        """早晨例程"""
        print("🌅 执行早晨例程...")
        
        # 1. 开启床底灯（柔和亮度）
        self.controller.control_bedroom_light("on")
        
        # 2. 播放晨间音乐
        self.controller.control_music_player("play")
        
        # 3. 语音提醒
        self.controller.speak_text("早上好，新的一天开始了")
        
        # 4. 启动AI助手
        self.controller.control_ai_assistant("doubao", "start")
        
        print("✅ 早晨例程完成")
    
    def evening_routine(self):
        """晚间例程"""
        print("🌙 执行晚间例程...")
        
        # 1. 检查功率使用情况
        power = self.controller.monitor_power_usage()
        if power and power > 500:
            self.controller.speak_text("当前功率使用较高，建议关闭部分设备")
        
        # 2. 渐进关闭设备
        self.controller.control_music_player("pause")
        time.sleep(5)
        
        # 3. 关闭床底灯
        self.controller.control_bedroom_light("off")
        
        # 4. 晚安语音
        self.controller.speak_text("晚安，祝您好梦")
        
        print("✅ 晚间例程完成")
    
    def power_saving_mode(self):
        """节能模式"""
        print("⚡ 启动节能模式...")
        
        # 检查功率使用
        power = self.controller.monitor_power_usage()
        if power and power > 400:
            # 关闭非必要设备
            self.controller.control_bedroom_light("off")
            self.controller.control_music_player("stop")
            self.controller.speak_text("已启动节能模式")
            
        print("✅ 节能模式启动完成")
    
    def ai_interaction_demo(self):
        """AI交互演示"""
        print("🤖 AI交互演示...")
        
        # 1. 启动豆包AI
        self.controller.control_ai_assistant("doubao", "start")
        time.sleep(2)
        
        # 2. 切换到Kimi
        self.controller.control_ai_assistant("doubao", "stop")
        self.controller.control_ai_assistant("kimi", "start")
        
        # 3. 语音反馈
        self.controller.speak_text("AI助手已切换到Kimi")
        
        print("✅ AI交互演示完成")
    
    def voice_control_demo(self):
        """语音控制演示"""
        print("🎙️ 语音控制演示...")
        
        # 模拟语音指令处理
        commands = [
            "开启床底灯",
            "播放音乐", 
            "启动AI助手",
            "查看功率使用"
        ]
        
        for cmd in commands:
            print(f"🎯 处理语音指令: {cmd}")
            
            if "床底灯" in cmd:
                action = "on" if "开启" in cmd else "off"
                self.controller.control_bedroom_light(action)
                
            elif "音乐" in cmd:
                action = "play" if "播放" in cmd else "stop"
                self.controller.control_music_player(action)
                
            elif "AI助手" in cmd:
                self.controller.control_ai_assistant("doubao", "start")
                
            elif "功率" in cmd:
                power = self.controller.monitor_power_usage()
                self.controller.speak_text(f"当前功率使用为{power}瓦")
            
            time.sleep(2)
        
        print("✅ 语音控制演示完成")
    
    def security_check(self):
        """安全检查例程"""
        print("🔒 执行安全检查...")
        
        # 获取系统状态
        status = self.controller.get_system_status()
        
        issues = []
        if not status['nodered_connected']:
            issues.append("Node-RED连接异常")
        if not status['rhasspy_connected']:
            issues.append("Rhasspy连接异常")
        if status['power_usage'] and status['power_usage'] > 600:
            issues.append("功率使用过高")
        
        if issues:
            for issue in issues:
                self.controller.speak_text(f"安全警告：{issue}")
                print(f"⚠️ {issue}")
        else:
            self.controller.speak_text("系统安全检查通过")
            print("✅ 系统运行正常")
    
    def setup_schedule(self):
        """设置定时任务"""
        print("⏰ 设置自动化定时任务...")
        
        # 早晨例程 - 每天7:00
        schedule.every().day.at("07:00").do(self.morning_routine)
        
        # 晚间例程 - 每天22:00  
        schedule.every().day.at("22:00").do(self.evening_routine)
        
        # 节能检查 - 每2小时
        schedule.every(2).hours.do(self.power_saving_mode)
        
        # 安全检查 - 每6小时
        schedule.every(6).hours.do(self.security_check)
        
        print("✅ 定时任务设置完成")
        print("📋 定时任务列表:")
        print("  07:00 - 早晨例程")
        print("  22:00 - 晚间例程") 
        print("  每2小时 - 节能检查")
        print("  每6小时 - 安全检查")
    
    def run_automation(self):
        """运行自动化系统"""
        print("🚀 启动智能家居自动化系统")
        
        # 设置定时任务
        self.setup_schedule()
        
        # 运行定时任务检查
        print("🔄 开始运行自动化任务...")
        while True:
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次

def demo_all_scenes():
    """演示所有自动化场景"""
    automation = AutomationScenes()
    
    print("🎭 智能家居自动化场景演示")
    print("=" * 50)
    
    scenes = [
        ("早晨例程", automation.morning_routine),
        ("AI交互演示", automation.ai_interaction_demo),
        ("语音控制演示", automation.voice_control_demo),
        ("安全检查", automation.security_check),
        ("节能模式", automation.power_saving_mode),
        ("晚间例程", automation.evening_routine)
    ]
    
    for name, scene_func in scenes:
        print(f"\n🎯 演示: {name}")
        print("-" * 30)
        scene_func()
        print(f"⏱️ 等待5秒后继续...")
        time.sleep(5)
    
    print("\n🎉 所有场景演示完成！")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "demo":
        demo_all_scenes()
    else:
        automation = AutomationScenes()
        automation.run_automation()

