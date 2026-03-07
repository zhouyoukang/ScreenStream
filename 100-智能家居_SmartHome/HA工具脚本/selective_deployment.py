#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
选择性部署工具 - 让用户选择要添加的功能
"""

import json
import requests
from enhanced_flows import FlowEnhancer

class SelectiveDeployer:
    """选择性部署器"""
    
    def __init__(self):
        self.enhancer = FlowEnhancer()
        self.available_features = {
            "1": {"name": "🌡️ 环境监控系统", "method": "create_temperature_monitoring", "description": "温湿度监控，高低温自动响应"},
            "2": {"name": "⏰ 定时自动化任务", "method": "create_scheduled_tasks", "description": "早晨7:00和晚间22:00例程"},
            "3": {"name": "🎙️ 语音控制集成", "method": "create_voice_control", "description": "Rhasspy语音指令识别和响应"},
            "4": {"name": "🔒 安全监控系统", "method": "create_security_monitoring", "description": "每小时安全检查和异常警告"},
            "5": {"name": "⚡ 智能节能管理", "method": "create_energy_management", "description": "30分钟节能检查和优化建议"},
            "6": {"name": "🏠 智能场景控制", "method": "create_automation_scenes", "description": "根据时间自动切换场景模式"}
        }
    
    def show_menu(self):
        """显示功能选择菜单"""
        print("🎯 Node-RED功能增强 - 选择性部署")
        print("=" * 50)
        print("📋 可添加的功能模块:")
        print()
        
        for key, feature in self.available_features.items():
            print(f"{key}. {feature['name']}")
            print(f"   {feature['description']}")
            print()
        
        print("🔧 部署选项:")
        print("A. 全部部署 - 一次性添加所有功能")
        print("C. 自定义选择 - 选择特定功能组合") 
        print("P. 预览配置 - 查看将要添加的节点")
        print("Q. 退出")
        print()
    
    def get_user_choice(self):
        """获取用户选择"""
        while True:
            choice = input("请选择功能 (输入数字/字母): ").upper().strip()
            
            if choice == "Q":
                return "quit"
            elif choice == "A":
                return "all"
            elif choice == "C":
                return "custom"
            elif choice == "P":
                return "preview"
            elif choice in self.available_features:
                return choice
            else:
                print("❌ 无效选择，请重新输入")
    
    def deploy_all_features(self):
        """部署所有功能"""
        print("🚀 部署所有功能...")
        enhanced_flows = self.enhancer.create_enhanced_flows()
        return self.deploy_flows(enhanced_flows, "所有功能")
    
    def deploy_selected_features(self, selected_features):
        """部署选定的功能"""
        print(f"🚀 部署选定功能: {', '.join([self.available_features[f]['name'] for f in selected_features])}")
        
        # 从基础流程开始
        flows = self.enhancer.base_flows.copy()
        
        # 总是需要新实体配置
        flows.extend(self.enhancer.create_new_entities())
        
        # 添加选定的功能
        for feature_id in selected_features:
            feature = self.available_features[feature_id]
            method = getattr(self.enhancer, feature['method'])
            flows.extend(method())
        
        return self.deploy_flows(flows, f"{len(selected_features)}个功能")
    
    def preview_configuration(self, selected_features=None):
        """预览配置"""
        if selected_features is None:
            selected_features = list(self.available_features.keys())
        
        print("👀 配置预览")
        print("=" * 30)
        
        total_new_nodes = 0
        for feature_id in selected_features:
            feature = self.available_features[feature_id]
            method = getattr(self.enhancer, feature['method'])
            nodes = method()
            
            print(f"\n{feature['name']}:")
            print(f"  📊 新增节点: {len(nodes)}个")
            print(f"  📝 描述: {feature['description']}")
            
            # 显示主要节点类型
            node_types = {}
            for node in nodes:
                node_type = node.get('type', 'unknown')
                node_types[node_type] = node_types.get(node_type, 0) + 1
            
            if node_types:
                print("  🔧 节点类型:")
                for ntype, count in node_types.items():
                    print(f"    - {ntype}: {count}个")
            
            total_new_nodes += len(nodes)
        
        print(f"\n📈 总计: 新增 {total_new_nodes} 个节点")
        print("=" * 30)
    
    def deploy_flows(self, flows, description):
        """部署流程到Node-RED"""
        try:
            # 保存到文件
            filename = f"deployed_flows_{len(flows)}_nodes.json"
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(flows, f, ensure_ascii=False, indent=2)
            
            print(f"📝 配置已保存到: {filename}")
            
            # 尝试部署
            response = requests.post(
                "http://localhost:1880/flows",
                json=flows,
                headers={"Content-Type": "application/json"},
                timeout=15
            )
            
            if response.status_code == 200:
                print(f"✅ {description}已成功部署到Node-RED!")
                print("🎉 你的智能家居系统已升级完成!")
                return True
            else:
                print(f"❌ 部署失败: HTTP {response.status_code}")
                print(f"💡 你可以手动导入 {filename} 文件到Node-RED")
                return False
                
        except Exception as e:
            print(f"❌ 部署失败: {e}")
            print(f"💡 你可以手动导入 {filename} 文件到Node-RED")
            return False
    
    def custom_selection(self):
        """自定义功能选择"""
        print("\n🔧 自定义功能选择")
        print("请选择要部署的功能 (多个功能用空格分隔，如: 1 3 5)")
        print("或输入功能编号范围 (如: 1-3)")
        
        while True:
            selection = input("选择功能: ").strip()
            
            if not selection:
                print("❌ 请至少选择一个功能")
                continue
            
            try:
                selected = []
                
                # 处理范围选择 (如 1-3)
                if '-' in selection:
                    start, end = selection.split('-')
                    start, end = int(start.strip()), int(end.strip())
                    selected = [str(i) for i in range(start, end + 1) if str(i) in self.available_features]
                else:
                    # 处理单个或多个选择
                    parts = selection.split()
                    selected = [p for p in parts if p in self.available_features]
                
                if not selected:
                    print("❌ 没有有效的功能选择")
                    continue
                
                # 显示选择确认
                print(f"\n📋 已选择 {len(selected)} 个功能:")
                for s in selected:
                    print(f"  {s}. {self.available_features[s]['name']}")
                
                confirm = input("\n确认部署这些功能? (y/n): ").lower().strip()
                if confirm in ['y', 'yes', '是']:
                    return self.deploy_selected_features(selected)
                else:
                    continue
                    
            except Exception as e:
                print(f"❌ 选择格式错误: {e}")
                continue
    
    def run(self):
        """运行部署器"""
        while True:
            self.show_menu()
            choice = self.get_user_choice()
            
            if choice == "quit":
                print("👋 部署已取消")
                break
            elif choice == "all":
                if self.deploy_all_features():
                    break
            elif choice == "custom":
                if self.custom_selection():
                    break
            elif choice == "preview":
                print("\n请选择要预览的功能 (多个用空格分隔，回车预览全部):")
                selection = input("功能编号: ").strip()
                
                if selection:
                    selected = [p for p in selection.split() if p in self.available_features]
                else:
                    selected = list(self.available_features.keys())
                
                self.preview_configuration(selected)
                input("\n按回车继续...")
            elif choice in self.available_features:
                # 单个功能部署
                if self.deploy_selected_features([choice]):
                    break

if __name__ == "__main__":
    deployer = SelectiveDeployer()
    deployer.run()

