#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Home Assistant 系统实时状态分析工具
通过 REST API 获取系统完整状态并生成详细报告
"""

import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import sys
from collections import defaultdict

class HASystemAnalyzer:
    """Home Assistant 系统分析器"""
    
    def __init__(self, base_url: str = "http://localhost:8123", token: str = None):
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
    def _api_call(self, endpoint: str, method: str = "GET", data: Dict = None) -> Optional[Dict]:
        """执行 API 调用"""
        try:
            url = f"{self.base_url}/api/{endpoint}"
            if method == "GET":
                response = self.session.get(url, timeout=10)
            elif method == "POST":
                response = self.session.post(url, json=data, timeout=10)
            
            response.raise_for_status()
            return response.json() if response.text else {}
        except Exception as e:
            print(f"❌ API 调用失败 [{endpoint}]: {e}")
            return None
    
    def get_config(self) -> Dict:
        """获取系统配置信息"""
        return self._api_call("config") or {}
    
    def get_states(self) -> List[Dict]:
        """获取所有实体状态"""
        return self._api_call("states") or []
    
    def get_services(self) -> Dict:
        """获取所有可用服务"""
        return self._api_call("services") or {}
    
    def get_error_log(self) -> str:
        """获取错误日志"""
        return self._api_call("error_log") or ""
    
    def get_events(self) -> List[Dict]:
        """获取事件列表"""
        return self._api_call("events") or []
    
    def analyze_devices(self, states: List[Dict]) -> Dict:
        """分析设备状态"""
        devices = {
            'switches': [],
            'lights': [],
            'sensors': [],
            'fans': [],
            'cameras': [],
            'climate': [],
            'binary_sensors': [],
            'other': []
        }
        
        device_stats = {
            'total': 0,
            'available': 0,
            'unavailable': 0,
            'unknown': 0,
            'on': 0,
            'off': 0
        }
        
        for state in states:
            entity_id = state.get('entity_id', '')
            domain = entity_id.split('.')[0] if '.' in entity_id else 'other'
            
            device_info = {
                'entity_id': entity_id,
                'name': state.get('attributes', {}).get('friendly_name', entity_id),
                'state': state.get('state', 'unknown'),
                'last_changed': state.get('last_changed', ''),
                'last_updated': state.get('last_updated', ''),
                'attributes': state.get('attributes', {})
            }
            
            # 分类设备
            if domain == 'switch':
                devices['switches'].append(device_info)
            elif domain == 'light':
                devices['lights'].append(device_info)
            elif domain == 'sensor':
                devices['sensors'].append(device_info)
            elif domain == 'fan':
                devices['fans'].append(device_info)
            elif domain == 'camera':
                devices['cameras'].append(device_info)
            elif domain == 'climate':
                devices['climate'].append(device_info)
            elif domain == 'binary_sensor':
                devices['binary_sensors'].append(device_info)
            else:
                devices['other'].append(device_info)
            
            # 统计
            device_stats['total'] += 1
            state_value = state.get('state', '').lower()
            
            if state_value == 'unavailable':
                device_stats['unavailable'] += 1
            elif state_value == 'unknown':
                device_stats['unknown'] += 1
            else:
                device_stats['available'] += 1
                
            if state_value == 'on':
                device_stats['on'] += 1
            elif state_value == 'off':
                device_stats['off'] += 1
        
        return {'devices': devices, 'stats': device_stats}
    
    def analyze_power_usage(self, states: List[Dict]) -> Dict:
        """分析功率使用情况"""
        power_devices = []
        total_power = 0
        
        for state in states:
            entity_id = state.get('entity_id', '')
            attributes = state.get('attributes', {})
            
            # 查找功率传感器
            if 'power' in entity_id.lower() or attributes.get('unit_of_measurement') == 'W':
                try:
                    power_value = float(state.get('state', 0))
                    if power_value > 0:
                        power_devices.append({
                            'entity_id': entity_id,
                            'name': attributes.get('friendly_name', entity_id),
                            'power': power_value,
                            'unit': attributes.get('unit_of_measurement', 'W')
                        })
                        total_power += power_value
                except (ValueError, TypeError):
                    pass
        
        # 按功率排序
        power_devices.sort(key=lambda x: x['power'], reverse=True)
        
        return {
            'devices': power_devices,
            'total_power': total_power,
            'device_count': len(power_devices)
        }
    
    def analyze_battery_devices(self, states: List[Dict]) -> List[Dict]:
        """分析电池设备"""
        battery_devices = []
        
        for state in states:
            entity_id = state.get('entity_id', '')
            attributes = state.get('attributes', {})
            
            # 查找电池传感器
            if 'battery' in entity_id.lower() or attributes.get('device_class') == 'battery':
                try:
                    battery_level = float(state.get('state', 0))
                    battery_devices.append({
                        'entity_id': entity_id,
                        'name': attributes.get('friendly_name', entity_id),
                        'level': battery_level,
                        'unit': attributes.get('unit_of_measurement', '%'),
                        'status': '正常' if battery_level > 20 else '⚠️ 低电量'
                    })
                except (ValueError, TypeError):
                    pass
        
        # 按电量排序
        battery_devices.sort(key=lambda x: x['level'])
        
        return battery_devices
    
    def analyze_automations(self, states: List[Dict]) -> Dict:
        """分析自动化状态"""
        automations = []
        
        for state in states:
            entity_id = state.get('entity_id', '')
            if entity_id.startswith('automation.'):
                attributes = state.get('attributes', {})
                automations.append({
                    'entity_id': entity_id,
                    'name': attributes.get('friendly_name', entity_id),
                    'state': state.get('state', 'unknown'),
                    'last_triggered': attributes.get('last_triggered', 'Never'),
                    'current': attributes.get('current', 0)
                })
        
        enabled = sum(1 for a in automations if a['state'] == 'on')
        disabled = sum(1 for a in automations if a['state'] == 'off')
        
        return {
            'automations': automations,
            'total': len(automations),
            'enabled': enabled,
            'disabled': disabled
        }
    
    def analyze_integrations(self, states: List[Dict]) -> Dict:
        """分析集成组件"""
        domains = defaultdict(int)
        
        for state in states:
            entity_id = state.get('entity_id', '')
            domain = entity_id.split('.')[0] if '.' in entity_id else 'unknown'
            domains[domain] += 1
        
        # 排序
        sorted_domains = sorted(domains.items(), key=lambda x: x[1], reverse=True)
        
        return {
            'domains': dict(sorted_domains),
            'total_domains': len(domains)
        }
    
    def check_system_health(self) -> Dict:
        """检查系统健康状态"""
        issues = []
        warnings = []
        
        # 获取状态
        states = self.get_states()
        
        # 检查不可用设备
        unavailable = [s for s in states if s.get('state') == 'unavailable']
        if unavailable:
            issues.append(f"发现 {len(unavailable)} 个不可用设备")
        
        # 检查未知状态设备
        unknown = [s for s in states if s.get('state') == 'unknown']
        if unknown:
            warnings.append(f"发现 {len(unknown)} 个未知状态设备")
        
        # 检查低电量设备
        battery_devices = self.analyze_battery_devices(states)
        low_battery = [d for d in battery_devices if d['level'] < 20]
        if low_battery:
            warnings.append(f"发现 {len(low_battery)} 个低电量设备")
        
        return {
            'issues': issues,
            'warnings': warnings,
            'health_score': max(0, 100 - len(issues) * 10 - len(warnings) * 5)
        }
    
    def generate_report(self) -> str:
        """生成完整的系统分析报告"""
        print("🔍 正在收集系统数据...")
        
        # 获取基础数据
        config = self.get_config()
        states = self.get_states()
        services = self.get_services()
        
        print(f"✅ 已获取 {len(states)} 个实体状态")
        
        # 执行各项分析
        device_analysis = self.analyze_devices(states)
        power_analysis = self.analyze_power_usage(states)
        battery_analysis = self.analyze_battery_devices(states)
        automation_analysis = self.analyze_automations(states)
        integration_analysis = self.analyze_integrations(states)
        health_check = self.check_system_health()
        
        # 生成报告
        report = self._format_report(
            config, device_analysis, power_analysis, 
            battery_analysis, automation_analysis, 
            integration_analysis, health_check, services
        )
        
        return report
    
    def _format_report(self, config, devices, power, battery,
                       automations, integrations, health, services) -> str:
        """格式化报告输出"""

        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("📊 HOME ASSISTANT 系统实时状态分析报告")
        report_lines.append("=" * 80)
        report_lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("")

        # 系统信息
        report_lines.append("🖥️  系统基本信息")
        report_lines.append("-" * 80)
        report_lines.append(f"版本: {config.get('version', 'Unknown')}")
        report_lines.append(f"位置: {config.get('location_name', 'Unknown')}")
        report_lines.append(f"时区: {config.get('time_zone', 'Unknown')}")
        report_lines.append(f"单位系统: {config.get('unit_system', {}).get('length', 'Unknown')}")
        report_lines.append(f"配置目录: {config.get('config_dir', 'Unknown')}")
        report_lines.append(f"纬度/经度: {config.get('latitude', 'N/A')}, {config.get('longitude', 'N/A')}")
        report_lines.append("")

        # 健康状态
        report_lines.append("💚 系统健康状态")
        report_lines.append("-" * 80)
        report_lines.append(f"健康评分: {health['health_score']}/100")

        if health['issues']:
            report_lines.append("\n❌ 严重问题:")
            for issue in health['issues']:
                report_lines.append(f"  • {issue}")

        if health['warnings']:
            report_lines.append("\n⚠️  警告:")
            for warning in health['warnings']:
                report_lines.append(f"  • {warning}")

        if not health['issues'] and not health['warnings']:
            report_lines.append("✅ 系统运行正常，未发现问题")

        report_lines.append("")

        # 设备统计
        stats = devices['stats']
        report_lines.append("📱 设备状态统计")
        report_lines.append("-" * 80)
        report_lines.append(f"总设备数: {stats['total']}")
        report_lines.append(f"  ✅ 可用: {stats['available']} ({stats['available']/stats['total']*100:.1f}%)")
        report_lines.append(f"  ❌ 不可用: {stats['unavailable']}")
        report_lines.append(f"  ❓ 未知: {stats['unknown']}")
        report_lines.append(f"  🟢 开启: {stats['on']}")
        report_lines.append(f"  ⚫ 关闭: {stats['off']}")
        report_lines.append("")

        # 设备详情
        dev = devices['devices']
        report_lines.append("🔌 设备详细信息")
        report_lines.append("-" * 80)

        # 开关设备
        if dev['switches']:
            report_lines.append(f"\n💡 开关设备 ({len(dev['switches'])} 个):")
            for switch in dev['switches'][:10]:  # 只显示前10个
                status_icon = "🟢" if switch['state'] == 'on' else "⚫"
                report_lines.append(f"  {status_icon} {switch['name']}: {switch['state']}")
            if len(dev['switches']) > 10:
                report_lines.append(f"  ... 还有 {len(dev['switches']) - 10} 个开关")

        # 灯光设备
        if dev['lights']:
            report_lines.append(f"\n💡 灯光设备 ({len(dev['lights'])} 个):")
            for light in dev['lights'][:10]:
                status_icon = "🟢" if light['state'] == 'on' else "⚫"
                brightness = light['attributes'].get('brightness', 'N/A')
                report_lines.append(f"  {status_icon} {light['name']}: {light['state']} (亮度: {brightness})")
            if len(dev['lights']) > 10:
                report_lines.append(f"  ... 还有 {len(dev['lights']) - 10} 个灯光")

        # 传感器
        if dev['sensors']:
            report_lines.append(f"\n🌡️  传感器 ({len(dev['sensors'])} 个):")
            # 只显示重要传感器
            important_sensors = [s for s in dev['sensors'] if any(
                keyword in s['entity_id'].lower()
                for keyword in ['temperature', 'humidity', 'power', 'battery', 'weather']
            )][:15]
            for sensor in important_sensors:
                unit = sensor['attributes'].get('unit_of_measurement', '')
                report_lines.append(f"  📊 {sensor['name']}: {sensor['state']} {unit}")

        # 风扇
        if dev['fans']:
            report_lines.append(f"\n🌀 风扇设备 ({len(dev['fans'])} 个):")
            for fan in dev['fans']:
                status_icon = "🟢" if fan['state'] == 'on' else "⚫"
                speed = fan['attributes'].get('percentage', 'N/A')
                report_lines.append(f"  {status_icon} {fan['name']}: {fan['state']} (速度: {speed}%)")

        # 摄像头
        if dev['cameras']:
            report_lines.append(f"\n📷 摄像头 ({len(dev['cameras'])} 个):")
            for camera in dev['cameras']:
                report_lines.append(f"  📹 {camera['name']}: {camera['state']}")

        report_lines.append("")

        # 功率使用分析
        report_lines.append("⚡ 功率使用分析")
        report_lines.append("-" * 80)
        report_lines.append(f"总功率: {power['total_power']:.2f} W")
        report_lines.append(f"监控设备数: {power['device_count']}")

        if power['devices']:
            report_lines.append("\n🔋 功率消耗 TOP 10:")
            for i, device in enumerate(power['devices'][:10], 1):
                report_lines.append(f"  {i}. {device['name']}: {device['power']:.2f} {device['unit']}")

        report_lines.append("")

        # 电池设备
        if battery:
            report_lines.append("🔋 电池设备状态")
            report_lines.append("-" * 80)
            report_lines.append(f"电池设备数: {len(battery)}")

            for device in battery[:10]:
                level = device['level']
                if level < 20:
                    icon = "🔴"
                elif level < 50:
                    icon = "🟡"
                else:
                    icon = "🟢"
                report_lines.append(f"  {icon} {device['name']}: {level}% - {device['status']}")

            if len(battery) > 10:
                report_lines.append(f"  ... 还有 {len(battery) - 10} 个电池设备")

            report_lines.append("")

        # 自动化状态
        report_lines.append("🤖 自动化规则")
        report_lines.append("-" * 80)
        report_lines.append(f"总自动化数: {automations['total']}")
        report_lines.append(f"  ✅ 已启用: {automations['enabled']}")
        report_lines.append(f"  ⏸️  已禁用: {automations['disabled']}")

        if automations['automations']:
            report_lines.append("\n📋 自动化列表:")
            for auto in automations['automations'][:15]:
                status_icon = "✅" if auto['state'] == 'on' else "⏸️"
                last_trigger = auto['last_triggered']
                if last_trigger and last_trigger != 'Never':
                    try:
                        trigger_time = datetime.fromisoformat(last_trigger.replace('Z', '+00:00'))
                        last_trigger = trigger_time.strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        pass
                report_lines.append(f"  {status_icon} {auto['name']}")
                report_lines.append(f"      最后触发: {last_trigger}")

            if len(automations['automations']) > 15:
                report_lines.append(f"  ... 还有 {len(automations['automations']) - 15} 个自动化")

        report_lines.append("")

        # 集成组件统计
        report_lines.append("🔧 集成组件统计")
        report_lines.append("-" * 80)
        report_lines.append(f"总域数: {integrations['total_domains']}")
        report_lines.append("\n📊 实体数量 TOP 15:")

        for i, (domain, count) in enumerate(list(integrations['domains'].items())[:15], 1):
            report_lines.append(f"  {i:2d}. {domain:20s}: {count:4d} 个实体")

        report_lines.append("")

        # 服务统计
        report_lines.append("🛠️  可用服务")
        report_lines.append("-" * 80)
        report_lines.append(f"总服务域数: {len(services)}")

        service_count = sum(len(s) for s in services.values())
        report_lines.append(f"总服务数: {service_count}")

        report_lines.append("\n主要服务域:")
        important_domains = ['homeassistant', 'light', 'switch', 'automation', 'script', 'notify']
        for domain in important_domains:
            if domain in services:
                report_lines.append(f"  • {domain}: {len(services[domain])} 个服务")

        report_lines.append("")
        report_lines.append("=" * 80)
        report_lines.append("报告生成完成")
        report_lines.append("=" * 80)

        return "\n".join(report_lines)

def main():
    """主函数"""
    # Home Assistant 配置
    HA_URL = "http://localhost:8123"
    HA_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI1NmRmNzVlMmZiNGE0OWFlYWEzNGFlNjU4ZmE0NDNkOCIsImlhdCI6MTc1OTA3ODAwNSwiZXhwIjoyMDc0NDM4MDA1fQ.0KwD0UZ-GTQ2Uy2c7SCIfQXvbtGyw0Z7WuRNTIniajQ"
    
    print("🚀 启动 Home Assistant 系统分析...")
    print(f"📡 连接到: {HA_URL}")
    print("")
    
    analyzer = HASystemAnalyzer(HA_URL, HA_TOKEN)
    
    try:
        report = analyzer.generate_report()
        print(report)
        
        # 保存报告
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = f"ha_system_report_{timestamp}.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"\n💾 报告已保存到: {report_file}")
        
    except Exception as e:
        print(f"\n❌ 分析过程中出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

