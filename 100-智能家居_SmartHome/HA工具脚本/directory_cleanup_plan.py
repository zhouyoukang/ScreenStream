#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Home Assistant 目录整理和优化工具
自动分析、分类和整理工作目录
"""

import os
import shutil
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set
import hashlib

class DirectoryOrganizer:
    """目录整理器"""
    
    def __init__(self, base_dir: str = "d:/homeassistant"):
        self.base_dir = Path(base_dir)
        self.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 定义新的目录结构
        self.new_structure = {
            '📊_分析报告': '存放系统分析报告和健康检查结果',
            '🔧_工具脚本': '存放Python工具和分析脚本',
            '📚_文档指南': '存放使用指南和说明文档',
            '💾_备份文件': '存放配置备份和系统备份',
            '🗂️_待处理': '临时存放不确定的文件',
            '📦_下载资源': '存放下载的组件和资源包',
            '🎨_前端资源': '存放前端相关的资源文件',
        }
        
        # 核心目录（不能移动或删除）
        self.protected_dirs = {
            'config', 'custom_components', 'www', 
            'config_backup_20250830_135905'  # 最新备份
        }
        
        # 文件分类规则
        self.file_categories = {
            '分析报告': ['.md', '.txt'],
            '工具脚本': ['.py', '.ps1', '.bat', '.sh'],
            '文档指南': ['.md', '.mdc'],
            '配置文件': ['.yaml', '.yml', '.json'],
            '压缩包': ['.zip', '.rar', '.7z', '.tar', '.gz', '.xz'],
            '日志文件': ['.log'],
            '图片文件': ['.png', '.jpg', '.jpeg', '.gif', '.svg'],
            '音频文件': ['.wav', '.mp3'],
            '数据文件': ['.db', '.db-shm', '.db-wal'],
        }
        
        # 统计信息
        self.stats = {
            'total_files': 0,
            'moved_files': 0,
            'deleted_files': 0,
            'duplicate_files': 0,
            'created_dirs': 0,
            'errors': []
        }
        
        # 操作日志
        self.operations = []
        
    def log_operation(self, operation: str, source: str, target: str = '', status: str = 'success'):
        """记录操作"""
        self.operations.append({
            'timestamp': datetime.now().isoformat(),
            'operation': operation,
            'source': source,
            'target': target,
            'status': status
        })
        
    def is_protected(self, path: Path) -> bool:
        """检查路径是否受保护"""
        try:
            rel_path = path.relative_to(self.base_dir)
            first_part = str(rel_path).split(os.sep)[0]
            return first_part in self.protected_dirs
        except:
            return False
    
    def get_file_hash(self, filepath: Path) -> str:
        """计算文件哈希值"""
        try:
            hash_md5 = hashlib.md5()
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except:
            return ""
    
    def find_duplicates(self) -> Dict[str, List[Path]]:
        """查找重复文件"""
        print("🔍 扫描重复文件...")
        
        file_hashes = {}
        duplicates = {}
        
        for root, dirs, files in os.walk(self.base_dir):
            root_path = Path(root)
            
            # 跳过受保护的目录
            if self.is_protected(root_path):
                continue
            
            # 跳过隐藏目录和特殊目录
            dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
            
            for file in files:
                if file.startswith('.'):
                    continue
                    
                filepath = root_path / file
                
                # 跳过大文件（>100MB）
                try:
                    if filepath.stat().st_size > 100 * 1024 * 1024:
                        continue
                except:
                    continue
                
                file_hash = self.get_file_hash(filepath)
                if not file_hash:
                    continue
                
                if file_hash in file_hashes:
                    if file_hash not in duplicates:
                        duplicates[file_hash] = [file_hashes[file_hash]]
                    duplicates[file_hash].append(filepath)
                else:
                    file_hashes[file_hash] = filepath
        
        print(f"  发现 {len(duplicates)} 组重复文件")
        return duplicates
    
    def create_new_structure(self):
        """创建新的目录结构"""
        print("\n📁 创建新目录结构...")
        
        for dir_name, description in self.new_structure.items():
            dir_path = self.base_dir / dir_name
            if not dir_path.exists():
                dir_path.mkdir(exist_ok=True)
                self.stats['created_dirs'] += 1
                print(f"  ✅ 创建: {dir_name}")
                
                # 创建说明文件
                readme_path = dir_path / 'README.md'
                with open(readme_path, 'w', encoding='utf-8') as f:
                    f.write(f"# {dir_name}\n\n{description}\n\n创建时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    def categorize_file(self, filepath: Path) -> str:
        """判断文件应该归类到哪个目录"""
        filename = filepath.name.lower()
        suffix = filepath.suffix.lower()
        
        # 分析报告
        if any(keyword in filename for keyword in ['report', '报告', 'analysis', '分析', 'health', '健康']):
            if suffix in ['.md', '.txt']:
                return '📊_分析报告'
        
        # 工具脚本
        if suffix in ['.py', '.ps1', '.bat', '.sh']:
            if any(keyword in filename for keyword in ['tool', '工具', 'script', '脚本', 'fix', 'check', 'test']):
                return '🔧_工具脚本'
        
        # 文档指南
        if suffix == '.md' and any(keyword in filename for keyword in ['readme', 'guide', '指南', 'doc', '文档', '说明']):
            return '📚_文档指南'
        
        # 备份文件
        if 'backup' in filename or '备份' in filename or suffix == '.bak':
            return '💾_备份文件'
        
        # 压缩包
        if suffix in ['.zip', '.rar', '.7z', '.tar', '.gz', '.xz', '.ova']:
            return '📦_下载资源'
        
        return None
    
    def organize_files(self):
        """整理文件"""
        print("\n📦 开始整理文件...")
        
        files_to_move = []
        
        # 扫描根目录的文件
        for item in self.base_dir.iterdir():
            if item.is_file():
                self.stats['total_files'] += 1
                
                # 跳过特殊文件
                if item.name.startswith('.') or item.name in ['desktop.ini']:
                    continue
                
                target_dir = self.categorize_file(item)
                if target_dir:
                    files_to_move.append((item, target_dir))
        
        # 移动文件
        for source, target_dir_name in files_to_move:
            try:
                target_dir = self.base_dir / target_dir_name
                target_path = target_dir / source.name
                
                # 如果目标文件已存在，添加时间戳
                if target_path.exists():
                    stem = source.stem
                    suffix = source.suffix
                    target_path = target_dir / f"{stem}_{self.timestamp}{suffix}"
                
                shutil.move(str(source), str(target_path))
                self.stats['moved_files'] += 1
                self.log_operation('move', str(source), str(target_path))
                print(f"  ✅ 移动: {source.name} → {target_dir_name}")
                
            except Exception as e:
                self.stats['errors'].append(f"移动文件失败 {source}: {e}")
                print(f"  ❌ 错误: {source.name} - {e}")
    
    def cleanup_old_directories(self):
        """清理旧目录"""
        print("\n🧹 清理旧目录...")
        
        # 需要清理的目录模式
        cleanup_patterns = [
            'HA备份',
            'Baidu_sst-main',
            'SonoffLAN-3.8.1',
            'dji_hass-main',
            'dronelink-dji-android-master',
            'extended_openai_conversation-1.0.4',
            'ha-bambulab-main',
            'haier-0.1.2 (1)',
            'hassio-ecoflow-cloud-main',
            'openrgb-ha-master',
            'rasa-assistant-main',
            'tuya-local-main',
            'tuya-smart-life-dev',
            'view_assist_integration-2025.4.1',
        ]
        
        for pattern in cleanup_patterns:
            dir_path = self.base_dir / pattern
            if dir_path.exists() and dir_path.is_dir():
                try:
                    # 移动到下载资源目录
                    target_path = self.base_dir / '📦_下载资源' / pattern
                    if not target_path.exists():
                        shutil.move(str(dir_path), str(target_path))
                        print(f"  ✅ 移动: {pattern} → 📦_下载资源")
                        self.log_operation('move_dir', str(dir_path), str(target_path))
                except Exception as e:
                    print(f"  ⚠️  无法移动 {pattern}: {e}")
    
    def handle_duplicates(self, duplicates: Dict[str, List[Path]]):
        """处理重复文件"""
        print("\n🔄 处理重复文件...")

        for file_hash, file_list in duplicates.items():
            if len(file_list) < 2:
                continue

            # 过滤出仍然存在的文件
            existing_files = [f for f in file_list if f.exists()]
            if len(existing_files) < 2:
                continue

            # 保留最新的文件
            try:
                existing_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            except Exception as e:
                print(f"  ⚠️  排序文件时出错: {e}")
                continue

            keep_file = existing_files[0]

            print(f"\n  保留: {keep_file.name}")

            for dup_file in existing_files[1:]:
                # 跳过受保护的文件
                if self.is_protected(dup_file):
                    continue

                try:
                    if dup_file.exists():
                        dup_file.unlink()
                        self.stats['duplicate_files'] += 1
                        self.stats['deleted_files'] += 1
                        print(f"    ❌ 删除重复: {dup_file}")
                        self.log_operation('delete_duplicate', str(dup_file))
                except Exception as e:
                    print(f"    ⚠️  无法删除 {dup_file}: {e}")
    
    def generate_report(self) -> str:
        """生成整理报告"""
        report_lines = []
        
        report_lines.append("=" * 80)
        report_lines.append("📊 Home Assistant 目录整理报告")
        report_lines.append("=" * 80)
        report_lines.append(f"整理时间: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}")
        report_lines.append(f"工作目录: {self.base_dir}")
        report_lines.append("")
        
        report_lines.append("📈 整理统计")
        report_lines.append("-" * 80)
        report_lines.append(f"扫描文件总数: {self.stats['total_files']}")
        report_lines.append(f"移动文件数量: {self.stats['moved_files']}")
        report_lines.append(f"删除重复文件: {self.stats['duplicate_files']}")
        report_lines.append(f"删除文件总数: {self.stats['deleted_files']}")
        report_lines.append(f"创建新目录数: {self.stats['created_dirs']}")
        report_lines.append(f"错误数量: {len(self.stats['errors'])}")
        report_lines.append("")
        
        if self.stats['errors']:
            report_lines.append("❌ 错误列表")
            report_lines.append("-" * 80)
            for error in self.stats['errors'][:10]:
                report_lines.append(f"  • {error}")
            if len(self.stats['errors']) > 10:
                report_lines.append(f"  ... 还有 {len(self.stats['errors']) - 10} 个错误")
            report_lines.append("")
        
        report_lines.append("📁 新目录结构")
        report_lines.append("-" * 80)
        for dir_name, description in self.new_structure.items():
            report_lines.append(f"{dir_name}/")
            report_lines.append(f"  └─ {description}")
        report_lines.append("")
        
        report_lines.append("=" * 80)
        report_lines.append("整理完成")
        report_lines.append("=" * 80)
        
        return "\n".join(report_lines)
    
    def run(self):
        """执行整理流程"""
        print("🚀 开始 Home Assistant 目录整理")
        print(f"📂 工作目录: {self.base_dir}")
        print("")
        
        # 1. 创建新目录结构
        self.create_new_structure()
        
        # 2. 查找重复文件
        duplicates = self.find_duplicates()
        
        # 3. 整理文件
        self.organize_files()
        
        # 4. 清理旧目录
        self.cleanup_old_directories()
        
        # 5. 处理重复文件
        if duplicates:
            self.handle_duplicates(duplicates)
        
        # 6. 生成报告
        report = self.generate_report()
        print("\n" + report)
        
        # 保存报告
        report_file = self.base_dir / '📊_分析报告' / f'目录整理报告_{self.timestamp}.txt'
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        # 保存操作日志
        log_file = self.base_dir / '📊_分析报告' / f'整理操作日志_{self.timestamp}.json'
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(self.operations, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 报告已保存: {report_file}")
        print(f"💾 日志已保存: {log_file}")

def main():
    """主函数"""
    organizer = DirectoryOrganizer("d:/homeassistant")
    organizer.run()

if __name__ == "__main__":
    main()

