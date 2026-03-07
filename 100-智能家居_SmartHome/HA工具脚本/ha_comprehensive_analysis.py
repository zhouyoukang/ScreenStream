#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Home Assistant 综合系统分析工具
结合 API、配置文件和日志进行全面分析
"""

import requests
import json
import yaml
import os
import re
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import defaultdict, Counter
import time

class HAComprehensiveAnalyzer:
    """Home Assistant 综合分析器"""
    
    def __init__(self, base_url: str = "http://localhost:8123", token: str = None, config_dir: str = "config"):
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.config_dir = config_dir
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
        # 数据存储
        self.config_data = {}
        self.states_data = []
        self.log_data = []
        self.custom_components = []
        
    def _api_call(self, endpoint: str, method: str = "GET", data: Dict = None, timeout: int = 5) -> Optional[Dict]:
        """执行 API 调用，带重试机制"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                url = f"{self.base_url}/api/{endpoint}"
                if method == "GET":
                    response = self.session.get(url, timeout=timeout)
                elif method == "POST":
                    response = self.session.post(url, json=data, timeout=timeout)
                
                response.raise_for_status()
                return response.json() if response.text else {}
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    print(f"⏱️  API 超时，重试 {attempt + 1}/{max_retries}...")
                    time.sleep(1)
                    continue
                print(f"❌ API 调用超时 [{endpoint}]")
                return None
            except requests.exceptions.ConnectionError:
                print(f"❌ 无法连接到 Home Assistant [{endpoint}]")
                return None
            except Exception as e:
                print(f"❌ API 调用失败 [{endpoint}]: {e}")
                return None
        return None
    
    def load_config_files(self):
        """加载配置文件"""
        print("📂 加载配置文件...")
        
        # 加载主配置
        config_file = os.path.join(self.config_dir, "configuration.yaml")
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    self.config_data = yaml.safe_load(f) or {}
                print(f"  ✅ 已加载 configuration.yaml")
            except Exception as e:
                print(f"  ❌ 加载 configuration.yaml 失败: {e}")
        
        # 加载自动化
        automation_file = os.path.join(self.config_dir, "automations.yaml")
        if os.path.exists(automation_file):
            try:
                with open(automation_file, 'r', encoding='utf-8') as f:
                    self.config_data['automations'] = yaml.safe_load(f) or []
                print(f"  ✅ 已加载 automations.yaml ({len(self.config_data['automations'])} 个自动化)")
            except Exception as e:
                print(f"  ❌ 加载 automations.yaml 失败: {e}")
        
        # 加载脚本
        scripts_file = os.path.join(self.config_dir, "scripts.yaml")
        if os.path.exists(scripts_file):
            try:
                with open(scripts_file, 'r', encoding='utf-8') as f:
                    self.config_data['scripts'] = yaml.safe_load(f) or {}
                print(f"  ✅ 已加载 scripts.yaml ({len(self.config_data['scripts'])} 个脚本)")
            except Exception as e:
                print(f"  ❌ 加载 scripts.yaml 失败: {e}")
        
        # 加载场景
        scenes_file = os.path.join(self.config_dir, "scenes.yaml")
        if os.path.exists(scenes_file):
            try:
                with open(scenes_file, 'r', encoding='utf-8') as f:
                    self.config_data['scenes'] = yaml.safe_load(f) or []
                print(f"  ✅ 已加载 scenes.yaml ({len(self.config_data['scenes'])} 个场景)")
            except Exception as e:
                print(f"  ❌ 加载 scenes.yaml 失败: {e}")
    
    def load_log_file(self, lines: int = 500):
        """加载日志文件"""
        print(f"📋 加载最近 {lines} 行日志...")
        
        log_file = os.path.join(self.config_dir, "home-assistant.log")
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    all_lines = f.readlines()
                    self.log_data = all_lines[-lines:]
                print(f"  ✅ 已加载 {len(self.log_data)} 行日志")
            except Exception as e:
                print(f"  ❌ 加载日志失败: {e}")
    
    def scan_custom_components(self):
        """扫描自定义组件"""
        print("🔍 扫描自定义组件...")
        
        custom_dir = os.path.join(self.config_dir, "custom_components")
        if os.path.exists(custom_dir):
            try:
                for item in os.listdir(custom_dir):
                    item_path = os.path.join(custom_dir, item)
                    if os.path.isdir(item_path):
                        manifest_path = os.path.join(item_path, "manifest.json")
                        if os.path.exists(manifest_path):
                            with open(manifest_path, 'r', encoding='utf-8') as f:
                                manifest = json.load(f)
                                self.custom_components.append({
                                    'domain': manifest.get('domain', item),
                                    'name': manifest.get('name', item),
                                    'version': manifest.get('version', 'Unknown'),
                                    'path': item_path
                                })
                print(f"  ✅ 发现 {len(self.custom_components)} 个自定义组件")
            except Exception as e:
                print(f"  ❌ 扫描自定义组件失败: {e}")
    
    def analyze_log_errors(self) -> Dict:
        """分析日志中的错误和警告"""
        errors = []
        warnings = []
        custom_component_warnings = []
        
        for line in self.log_data:
            if 'ERROR' in line:
                errors.append(line.strip())
            elif 'WARNING' in line:
                warnings.append(line.strip())
                if 'custom integration' in line.lower():
                    # 提取组件名称
                    match = re.search(r'custom integration (\w+)', line)
                    if match:
                        custom_component_warnings.append(match.group(1))
        
        return {
            'errors': errors[-20:],  # 最近20个错误
            'warnings': warnings[-30:],  # 最近30个警告
            'error_count': len(errors),
            'warning_count': len(warnings),
            'custom_component_warnings': list(set(custom_component_warnings))
        }
    
    def analyze_device_updates(self) -> Dict:
        """分析设备更新频率"""
        device_updates = defaultdict(int)
        xiaomi_devices = []
        
        for line in self.log_data:
            if 'Device updated:' in line:
                # 提取设备信息
                match = re.search(r'\[custom_components\.xiaomi_miot\.core\.device\.([^\]]+)\]', line)
                if match:
                    device = match.group(1)
                    device_updates[device] += 1
                    if device not in xiaomi_devices:
                        xiaomi_devices.append(device)
        
        return {
            'device_updates': dict(device_updates),
            'xiaomi_devices': xiaomi_devices,
            'total_updates': sum(device_updates.values())
        }
    
    def try_get_api_data(self):
        """尝试获取 API 数据"""
        print("🌐 尝试连接 Home Assistant API...")
        
        # 尝试获取配置
        config = self._api_call("config", timeout=3)
        if config:
            print("  ✅ API 连接成功")
            self.api_config = config
            
            # 尝试获取状态
            states = self._api_call("states", timeout=5)
            if states:
                self.states_data = states
                print(f"  ✅ 获取到 {len(states)} 个实体状态")
            
            return True
        else:
            print("  ⚠️  API 连接失败，将使用配置文件和日志进行分析")
            return False
    
    def analyze_configuration(self) -> Dict:
        """分析配置文件"""
        analysis = {
            'integrations': [],
            'sensors': 0,
            'switches': 0,
            'lights': 0,
            'automations': 0,
            'scripts': 0,
            'scenes': 0,
            'issues': []
        }
        
        # 检查配置问题
        if 'logger' in str(self.config_data):
            # 检查重复的 logger 配置
            config_str = str(self.config_data)
            if config_str.count("'logger'") > 1:
                analysis['issues'].append("配置文件中存在重复的 'logger' 配置")
        
        # 统计自动化
        if 'automations' in self.config_data:
            analysis['automations'] = len(self.config_data['automations'])
        
        # 统计脚本
        if 'scripts' in self.config_data:
            analysis['scripts'] = len(self.config_data['scripts'])
        
        # 统计场景
        if 'scenes' in self.config_data:
            analysis['scenes'] = len(self.config_data['scenes'])
        
        # 提取集成
        for key in self.config_data.keys():
            if key not in ['homeassistant', 'automations', 'scripts', 'scenes']:
                analysis['integrations'].append(key)
        
        return analysis
    
    def generate_comprehensive_report(self) -> str:
        """生成综合报告"""
        print("\n" + "="*80)
        print("📊 开始生成综合分析报告...")
        print("="*80 + "\n")
        
        # 收集所有数据
        self.load_config_files()
        self.load_log_file(lines=1000)
        self.scan_custom_components()
        api_available = self.try_get_api_data()
        
        # 执行分析
        log_analysis = self.analyze_log_errors()
        device_analysis = self.analyze_device_updates()
        config_analysis = self.analyze_configuration()
        
        # 生成报告
        report = self._format_comprehensive_report(
            api_available, log_analysis, device_analysis, config_analysis
        )
        
        return report
    
    def _format_comprehensive_report(self, api_available, log_analysis,
                                     device_analysis, config_analysis) -> str:
        """格式化综合报告"""
        lines = []

        lines.append("=" * 100)
        lines.append("📊 HOME ASSISTANT 系统综合分析报告")
        lines.append("=" * 100)
        lines.append(f"生成时间: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}")
        lines.append(f"分析方式: {'API + 配置文件 + 日志' if api_available else '配置文件 + 日志'}")
        lines.append("")

        # ========== 第一部分：系统基本信息 ==========
        lines.append("🖥️  第一部分：系统基本信息")
        lines.append("-" * 100)

        if api_available and hasattr(self, 'api_config'):
            config = self.api_config
            lines.append(f"Home Assistant 版本: {config.get('version', 'Unknown')}")
            lines.append(f"位置名称: {config.get('location_name', 'Unknown')}")
            lines.append(f"时区: {config.get('time_zone', 'Unknown')}")
            lines.append(f"纬度/经度: {config.get('latitude', 'N/A')}, {config.get('longitude', 'N/A')}")
            lines.append(f"单位系统: {config.get('unit_system', {}).get('length', 'Unknown')}")
            lines.append(f"货币: {config.get('currency', 'Unknown')}")
            lines.append(f"配置目录: {config.get('config_dir', 'Unknown')}")
        else:
            lines.append("⚠️  无法通过 API 获取系统信息")
            if 'homeassistant' in self.config_data:
                ha_config = self.config_data['homeassistant']
                lines.append(f"位置名称: {ha_config.get('name', 'Unknown')}")
                lines.append(f"时区: {ha_config.get('time_zone', 'Unknown')}")
                lines.append(f"纬度/经度: {ha_config.get('latitude', 'N/A')}, {ha_config.get('longitude', 'N/A')}")

        lines.append(f"运行方式: Docker 容器")
        lines.append(f"API 状态: {'✅ 可用' if api_available else '❌ 不可用'}")
        lines.append("")

        # ========== 第二部分：自定义组件 ==========
        lines.append("🔧 第二部分：自定义组件状态")
        lines.append("-" * 100)
        lines.append(f"已安装自定义组件数量: {len(self.custom_components)}")
        lines.append("")

        if self.custom_components:
            lines.append("📦 自定义组件列表:")
            for i, comp in enumerate(self.custom_components[:30], 1):  # 显示前30个
                version_str = f"v{comp['version']}" if comp['version'] != 'Unknown' else '版本未知'
                lines.append(f"  {i:2d}. {comp['name']:40s} ({comp['domain']:25s}) - {version_str}")

            if len(self.custom_components) > 30:
                lines.append(f"  ... 还有 {len(self.custom_components) - 30} 个组件")

        lines.append("")

        # 自定义组件警告
        if log_analysis['custom_component_warnings']:
            lines.append("⚠️  日志中发现的自定义组件警告:")
            for comp in log_analysis['custom_component_warnings'][:20]:
                lines.append(f"  • {comp}")
            lines.append("")

        # ========== 第三部分：配置文件分析 ==========
        lines.append("📝 第三部分：配置文件分析")
        lines.append("-" * 100)
        lines.append(f"自动化规则数量: {config_analysis['automations']}")
        lines.append(f"脚本数量: {config_analysis['scripts']}")
        lines.append(f"场景数量: {config_analysis['scenes']}")
        lines.append(f"配置的集成数量: {len(config_analysis['integrations'])}")
        lines.append("")

        if config_analysis['integrations']:
            lines.append("🔌 已配置的集成:")
            for integration in sorted(config_analysis['integrations'])[:30]:
                lines.append(f"  • {integration}")
            if len(config_analysis['integrations']) > 30:
                lines.append(f"  ... 还有 {len(config_analysis['integrations']) - 30} 个集成")
            lines.append("")

        # 配置问题
        if config_analysis['issues']:
            lines.append("⚠️  配置文件问题:")
            for issue in config_analysis['issues']:
                lines.append(f"  • {issue}")
            lines.append("")

        # ========== 第四部分：自动化详情 ==========
        if 'automations' in self.config_data and self.config_data['automations']:
            lines.append("🤖 第四部分：自动化规则详情")
            lines.append("-" * 100)

            automations = self.config_data['automations']
            lines.append(f"总计: {len(automations)} 个自动化规则")
            lines.append("")

            lines.append("📋 自动化列表:")
            for i, auto in enumerate(automations, 1):
                alias = auto.get('alias', f'自动化 {i}')
                description = auto.get('description', '无描述')
                auto_id = auto.get('id', 'N/A')

                lines.append(f"\n  {i}. {alias}")
                lines.append(f"     ID: {auto_id}")
                lines.append(f"     描述: {description}")

                # 触发器
                triggers = auto.get('triggers', auto.get('trigger', []))
                if not isinstance(triggers, list):
                    triggers = [triggers]
                lines.append(f"     触发器数量: {len(triggers)}")

                # 条件
                conditions = auto.get('conditions', auto.get('condition', []))
                if conditions:
                    if not isinstance(conditions, list):
                        conditions = [conditions]
                    lines.append(f"     条件数量: {len(conditions)}")

                # 动作
                actions = auto.get('actions', auto.get('action', []))
                if not isinstance(actions, list):
                    actions = [actions]
                lines.append(f"     动作数量: {len(actions)}")

            lines.append("")

        # ========== 第五部分：脚本详情 ==========
        if 'scripts' in self.config_data and self.config_data['scripts']:
            lines.append("📜 第五部分：脚本详情")
            lines.append("-" * 100)

            scripts = self.config_data['scripts']
            lines.append(f"总计: {len(scripts)} 个脚本")
            lines.append("")

            lines.append("📋 脚本列表:")
            for i, (script_name, script_config) in enumerate(scripts.items(), 1):
                alias = script_config.get('alias', script_name)
                description = script_config.get('description', '无描述')
                icon = script_config.get('icon', 'mdi:script')

                lines.append(f"\n  {i}. {alias} ({script_name})")
                lines.append(f"     图标: {icon}")
                lines.append(f"     描述: {description}")

                # 序列步骤
                sequence = script_config.get('sequence', [])
                lines.append(f"     步骤数量: {len(sequence)}")

            lines.append("")

        # ========== 第六部分：场景详情 ==========
        if 'scenes' in self.config_data and self.config_data['scenes']:
            lines.append("🎬 第六部分：场景详情")
            lines.append("-" * 100)

            scenes = self.config_data['scenes']
            lines.append(f"总计: {len(scenes)} 个场景")
            lines.append("")

            lines.append("📋 场景列表:")
            for i, scene in enumerate(scenes, 1):
                name = scene.get('name', f'场景 {i}')
                icon = scene.get('icon', 'mdi:palette')
                entities = scene.get('entities', {})

                lines.append(f"\n  {i}. {name}")
                lines.append(f"     图标: {icon}")
                lines.append(f"     控制实体数量: {len(entities)}")

            lines.append("")

        # ========== 第七部分：设备活动分析 ==========
        lines.append("📱 第七部分：设备活动分析（基于日志）")
        lines.append("-" * 100)

        if device_analysis['xiaomi_devices']:
            lines.append(f"检测到 {len(device_analysis['xiaomi_devices'])} 个活跃的小米设备")
            lines.append(f"日志中记录的设备更新总数: {device_analysis['total_updates']}")
            lines.append("")

            lines.append("🔄 设备更新频率 TOP 15:")
            sorted_devices = sorted(device_analysis['device_updates'].items(),
                                   key=lambda x: x[1], reverse=True)
            for i, (device, count) in enumerate(sorted_devices[:15], 1):
                lines.append(f"  {i:2d}. {device:50s}: {count:4d} 次更新")

            lines.append("")

            lines.append("📋 检测到的小米设备类型:")
            device_types = set()
            for device in device_analysis['xiaomi_devices']:
                # 提取设备类型
                parts = device.split('.')
                if len(parts) >= 2:
                    device_types.add(f"{parts[0]}.{parts[1]}")

            for device_type in sorted(device_types):
                lines.append(f"  • {device_type}")
        else:
            lines.append("⚠️  日志中未检测到设备更新记录")

        lines.append("")

        # ========== 第八部分：日志分析 ==========
        lines.append("📋 第八部分：日志分析")
        lines.append("-" * 100)
        lines.append(f"分析的日志行数: {len(self.log_data)}")
        lines.append(f"错误数量: {log_analysis['error_count']}")
        lines.append(f"警告数量: {log_analysis['warning_count']}")
        lines.append("")

        # 最近的错误
        if log_analysis['errors']:
            lines.append("❌ 最近的错误 (最多显示 10 条):")
            for error in log_analysis['errors'][-10:]:
                # 截断过长的错误信息
                if len(error) > 150:
                    error = error[:147] + "..."
                lines.append(f"  • {error}")
            lines.append("")

        # 最近的警告
        if log_analysis['warnings']:
            lines.append("⚠️  最近的警告 (最多显示 10 条，排除自定义组件警告):")
            non_custom_warnings = [w for w in log_analysis['warnings']
                                  if 'custom integration' not in w.lower()]
            for warning in non_custom_warnings[-10:]:
                # 截断过长的警告信息
                if len(warning) > 150:
                    warning = warning[:147] + "..."
                lines.append(f"  • {warning}")
            lines.append("")

        # ========== 第九部分：实体状态分析（如果 API 可用）==========
        if api_available and self.states_data:
            lines.append("📊 第九部分：实体状态分析")
            lines.append("-" * 100)
            lines.append(f"总实体数: {len(self.states_data)}")
            lines.append("")

            # 按域分类统计
            domain_stats = defaultdict(int)
            state_stats = defaultdict(int)
            unavailable_entities = []
            unknown_entities = []

            for state in self.states_data:
                entity_id = state.get('entity_id', '')
                domain = entity_id.split('.')[0] if '.' in entity_id else 'unknown'
                state_value = state.get('state', 'unknown')

                domain_stats[domain] += 1
                state_stats[state_value] += 1

                if state_value == 'unavailable':
                    unavailable_entities.append({
                        'entity_id': entity_id,
                        'name': state.get('attributes', {}).get('friendly_name', entity_id)
                    })
                elif state_value == 'unknown':
                    unknown_entities.append({
                        'entity_id': entity_id,
                        'name': state.get('attributes', {}).get('friendly_name', entity_id)
                    })

            # 域统计
            lines.append("📈 实体域统计 TOP 20:")
            sorted_domains = sorted(domain_stats.items(), key=lambda x: x[1], reverse=True)
            for i, (domain, count) in enumerate(sorted_domains[:20], 1):
                percentage = (count / len(self.states_data)) * 100
                lines.append(f"  {i:2d}. {domain:25s}: {count:4d} ({percentage:5.1f}%)")
            lines.append("")

            # 状态统计
            lines.append("📊 实体状态统计:")
            for state_value, count in sorted(state_stats.items(), key=lambda x: x[1], reverse=True)[:15]:
                lines.append(f"  • {state_value:20s}: {count:4d}")
            lines.append("")

            # 不可用实体
            if unavailable_entities:
                lines.append(f"❌ 不可用的实体 ({len(unavailable_entities)} 个):")
                for entity in unavailable_entities[:15]:
                    lines.append(f"  • {entity['name']} ({entity['entity_id']})")
                if len(unavailable_entities) > 15:
                    lines.append(f"  ... 还有 {len(unavailable_entities) - 15} 个不可用实体")
                lines.append("")

            # 未知状态实体
            if unknown_entities:
                lines.append(f"❓ 未知状态的实体 ({len(unknown_entities)} 个):")
                for entity in unknown_entities[:15]:
                    lines.append(f"  • {entity['name']} ({entity['entity_id']})")
                if len(unknown_entities) > 15:
                    lines.append(f"  ... 还有 {len(unknown_entities) - 15} 个未知状态实体")
                lines.append("")

            # 功率监控
            power_entities = []
            for state in self.states_data:
                entity_id = state.get('entity_id', '')
                attributes = state.get('attributes', {})
                if 'power' in entity_id.lower() or attributes.get('unit_of_measurement') == 'W':
                    try:
                        power_value = float(state.get('state', 0))
                        if power_value > 0:
                            power_entities.append({
                                'entity_id': entity_id,
                                'name': attributes.get('friendly_name', entity_id),
                                'power': power_value
                            })
                    except (ValueError, TypeError):
                        pass

            if power_entities:
                total_power = sum(e['power'] for e in power_entities)
                lines.append(f"⚡ 功率监控 ({len(power_entities)} 个设备):")
                lines.append(f"总功率: {total_power:.2f} W")
                lines.append("")

                lines.append("🔋 功率消耗 TOP 10:")
                power_entities.sort(key=lambda x: x['power'], reverse=True)
                for i, entity in enumerate(power_entities[:10], 1):
                    lines.append(f"  {i:2d}. {entity['name']:40s}: {entity['power']:7.2f} W")
                lines.append("")

            # 电池设备
            battery_entities = []
            for state in self.states_data:
                entity_id = state.get('entity_id', '')
                attributes = state.get('attributes', {})
                if 'battery' in entity_id.lower() or attributes.get('device_class') == 'battery':
                    try:
                        battery_level = float(state.get('state', 0))
                        battery_entities.append({
                            'entity_id': entity_id,
                            'name': attributes.get('friendly_name', entity_id),
                            'level': battery_level
                        })
                    except (ValueError, TypeError):
                        pass

            if battery_entities:
                lines.append(f"🔋 电池设备 ({len(battery_entities)} 个):")
                battery_entities.sort(key=lambda x: x['level'])

                low_battery = [e for e in battery_entities if e['level'] < 20]
                if low_battery:
                    lines.append(f"\n⚠️  低电量设备 ({len(low_battery)} 个):")
                    for entity in low_battery:
                        lines.append(f"  🔴 {entity['name']:40s}: {entity['level']:5.1f}%")

                lines.append(f"\n所有电池设备:")
                for entity in battery_entities[:15]:
                    if entity['level'] < 20:
                        icon = "🔴"
                    elif entity['level'] < 50:
                        icon = "🟡"
                    else:
                        icon = "🟢"
                    lines.append(f"  {icon} {entity['name']:40s}: {entity['level']:5.1f}%")

                if len(battery_entities) > 15:
                    lines.append(f"  ... 还有 {len(battery_entities) - 15} 个电池设备")
                lines.append("")

        # ========== 第十部分：问题诊断和建议 ==========
        lines.append("🔍 第十部分：问题诊断和改进建议")
        lines.append("-" * 100)

        issues = []
        warnings = []
        suggestions = []

        # 检查配置问题
        if config_analysis['issues']:
            for issue in config_analysis['issues']:
                issues.append(f"配置文件: {issue}")

        # 检查日志错误
        if log_analysis['error_count'] > 0:
            issues.append(f"系统日志中发现 {log_analysis['error_count']} 个错误")

        # 检查日志警告
        if log_analysis['warning_count'] > 50:
            warnings.append(f"系统日志中有大量警告 ({log_analysis['warning_count']} 个)")

        # 检查不可用实体
        if api_available and self.states_data:
            unavailable_count = sum(1 for s in self.states_data if s.get('state') == 'unavailable')
            if unavailable_count > 0:
                issues.append(f"发现 {unavailable_count} 个不可用的实体")

        # 检查自定义组件
        if len(self.custom_components) > 30:
            warnings.append(f"安装了大量自定义组件 ({len(self.custom_components)} 个)，可能影响系统稳定性")

        # 生成建议
        if config_analysis['issues']:
            suggestions.append("修复 configuration.yaml 中的重复配置项")

        if log_analysis['error_count'] > 0:
            suggestions.append("检查并解决日志中的错误信息")

        if api_available and self.states_data:
            unavailable_count = sum(1 for s in self.states_data if s.get('state') == 'unavailable')
            if unavailable_count > 5:
                suggestions.append("检查不可用设备的网络连接和配置")

        suggestions.append("定期清理日志文件以节省磁盘空间")
        suggestions.append("考虑使用 HACS 管理自定义组件以便于更新")
        suggestions.append("定期备份配置文件")

        # 输出诊断结果
        if issues:
            lines.append("❌ 发现的问题:")
            for i, issue in enumerate(issues, 1):
                lines.append(f"  {i}. {issue}")
            lines.append("")

        if warnings:
            lines.append("⚠️  警告:")
            for i, warning in enumerate(warnings, 1):
                lines.append(f"  {i}. {warning}")
            lines.append("")

        if not issues and not warnings:
            lines.append("✅ 未发现严重问题，系统运行良好")
            lines.append("")

        lines.append("💡 改进建议:")
        for i, suggestion in enumerate(suggestions, 1):
            lines.append(f"  {i}. {suggestion}")
        lines.append("")

        # ========== 报告总结 ==========
        lines.append("=" * 100)
        lines.append("📋 报告总结")
        lines.append("=" * 100)

        # 计算健康评分
        health_score = 100
        health_score -= len(issues) * 10
        health_score -= len(warnings) * 5
        health_score = max(0, health_score)

        lines.append(f"系统健康评分: {health_score}/100")

        if health_score >= 90:
            lines.append("评级: ⭐⭐⭐⭐⭐ 优秀")
        elif health_score >= 75:
            lines.append("评级: ⭐⭐⭐⭐ 良好")
        elif health_score >= 60:
            lines.append("评级: ⭐⭐⭐ 一般")
        elif health_score >= 40:
            lines.append("评级: ⭐⭐ 需要改进")
        else:
            lines.append("评级: ⭐ 需要立即处理")

        lines.append("")
        lines.append(f"分析的数据源:")
        lines.append(f"  • 配置文件: ✅")
        lines.append(f"  • 日志文件: ✅ ({len(self.log_data)} 行)")
        lines.append(f"  • API 数据: {'✅' if api_available else '❌'}")
        if api_available and self.states_data:
            lines.append(f"  • 实体状态: ✅ ({len(self.states_data)} 个)")

        lines.append("")
        lines.append("=" * 100)
        lines.append("报告生成完成")
        lines.append("=" * 100)

        return "\n".join(lines)

def main():
    """主函数"""
    HA_URL = "http://localhost:8123"
    HA_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI1NmRmNzVlMmZiNGE0OWFlYWEzNGFlNjU4ZmE0NDNkOCIsImlhdCI6MTc1OTA3ODAwNSwiZXhwIjoyMDc0NDM4MDA1fQ.0KwD0UZ-GTQ2Uy2c7SCIfQXvbtGyw0Z7WuRNTIniajQ"
    CONFIG_DIR = "config"
    
    print("🚀 启动 Home Assistant 综合系统分析")
    print(f"📡 Home Assistant URL: {HA_URL}")
    print(f"📂 配置目录: {CONFIG_DIR}")
    print("")
    
    analyzer = HAComprehensiveAnalyzer(HA_URL, HA_TOKEN, CONFIG_DIR)
    
    try:
        report = analyzer.generate_comprehensive_report()
        print(report)
        
        # 保存报告
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = f"ha_comprehensive_report_{timestamp}.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"\n💾 完整报告已保存到: {report_file}")
        
    except Exception as e:
        print(f"\n❌ 分析过程中出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

