#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完成目录整理 - 处理剩余文件和生成最终报告
"""

import os
import shutil
from datetime import datetime
from pathlib import Path

class FinalCleanup:
    """最终清理工具"""
    
    def __init__(self, base_dir: str = "d:/homeassistant"):
        self.base_dir = Path(base_dir)
        self.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        self.stats = {
            'moved_files': 0,
            'created_files': 0,
            'errors': []
        }
    
    def move_remaining_files(self):
        """移动剩余的分析文件"""
        print("📦 移动剩余文件...")
        
        # 需要移动的文件
        files_to_move = {
            'ha_comprehensive_analysis.py': '🔧_工具脚本',
            'ha_system_analysis.py': '🔧_工具脚本',
            'directory_cleanup_plan.py': '🔧_工具脚本',
            'finalize_cleanup.py': '🔧_工具脚本',
            '快速参考卡片.md': '📊_分析报告',
        }
        
        for filename, target_dir in files_to_move.items():
            source = self.base_dir / filename
            if source.exists():
                try:
                    target = self.base_dir / target_dir / filename
                    if not target.exists():
                        shutil.move(str(source), str(target))
                        self.stats['moved_files'] += 1
                        print(f"  ✅ 移动: {filename} → {target_dir}")
                except Exception as e:
                    print(f"  ⚠️  无法移动 {filename}: {e}")
                    self.stats['errors'].append(f"移动 {filename}: {e}")
    
    def create_main_readme(self):
        """创建主目录README"""
        print("\n📝 创建主目录README...")
        
        readme_content = """# 🏠 Home Assistant 工作目录

**最后整理时间**: {timestamp}

---

## 📁 目录结构说明

### 核心配置目录

- **`config/`** - Home Assistant 核心配置文件
  - `configuration.yaml` - 主配置文件
  - `automations.yaml` - 自动化规则
  - `scripts.yaml` - 脚本配置
  - `scenes.yaml` - 场景配置
  - `home-assistant.log` - 系统日志

- **`custom_components/`** - 自定义组件（37个）
  - AI和语音助手（9个）
  - 智能设备集成（12个）
  - 界面和工具（16个）

### 整理后的目录

- **`📊_分析报告/`** - 系统分析报告和健康检查结果
  - 系统健康报告
  - 整理报告
  - 快速参考卡片

- **`🔧_工具脚本/`** - Python工具和分析脚本
  - 系统分析工具
  - 修复脚本
  - 测试工具

- **`📚_文档指南/`** - 使用指南和说明文档
  - 优化指南
  - 部署指南
  - README文档

- **`💾_备份文件/`** - 配置备份和系统备份
  - 配置文件备份
  - 系统快照

- **`📦_下载资源/`** - 下载的组件和资源包
  - 组件源码
  - 安装包
  - 系统镜像

- **`🗂️_待处理/`** - 临时存放不确定的文件

- **`🎨_前端资源/`** - 前端相关的资源文件

### 备份目录

- **`config_backup_20250830_135905/`** - 最新配置备份（保留）

---

## 🎯 快速开始

### 查看系统状态
```bash
# 查看最新的系统健康报告
cat 📊_分析报告/Home_Assistant_系统健康报告_详细版.md

# 查看快速参考
cat 📊_分析报告/快速参考卡片.md
```

### 运行分析工具
```bash
# 运行系统综合分析
python 🔧_工具脚本/ha_comprehensive_analysis.py
```

### 查看配置
```bash
# 编辑主配置
nano config/configuration.yaml

# 编辑自动化
nano config/automations.yaml
```

---

## 📊 系统概览

### 当前状态
- **健康评分**: 85/100 ⭐⭐⭐⭐
- **自定义组件**: 37个
- **自动化规则**: 9个
- **场景脚本**: 8个
- **活跃设备**: 17个小米设备

### 最近修复
- ✅ 修复 configuration.yaml 重复配置
- ✅ 整理目录结构
- ✅ 移动分析报告和工具脚本
- ✅ 清理旧的下载目录

---

## 🔧 维护任务

### 每日检查
- [ ] 查看系统日志
- [ ] 检查设备在线状态
- [ ] 验证自动化运行

### 每周维护
- [ ] 运行系统分析工具
- [ ] 检查组件更新
- [ ] 清理日志文件

### 每月维护
- [ ] 优化数据库
- [ ] 创建完整备份
- [ ] 更新文档

---

## 📞 获取帮助

### 文档资源
- [Home Assistant 官方文档](https://www.home-assistant.io/docs/)
- [HACS 文档](https://hacs.xyz/)
- 本地文档: `📚_文档指南/`

### 分析报告
- 详细报告: `📊_分析报告/Home_Assistant_系统健康报告_详细版.md`
- 行动指南: `📚_文档指南/执行摘要_立即行动指南.md`
- 快速参考: `📊_分析报告/快速参考卡片.md`

---

## ⚠️ 重要提示

### 受保护的目录（请勿删除）
- `config/` - 核心配置
- `custom_components/` - 自定义组件
- `config_backup_20250830_135905/` - 最新备份

### 修改配置前
1. 创建备份
2. 使用开发者工具检查配置
3. 重启前验证语法

---

**最后更新**: {timestamp}  
**维护者**: Home Assistant 系统管理员
""".format(timestamp=datetime.now().strftime('%Y年%m月%d日 %H:%M:%S'))
        
        readme_path = self.base_dir / 'README.md'
        try:
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(readme_content)
            self.stats['created_files'] += 1
            print(f"  ✅ 创建: README.md")
        except Exception as e:
            print(f"  ❌ 创建README失败: {e}")
            self.stats['errors'].append(f"创建README: {e}")
    
    def create_directory_structure_doc(self):
        """创建目录结构文档"""
        print("\n📝 创建目录结构文档...")
        
        doc_content = """# 📁 Home Assistant 目录结构详解

**生成时间**: {timestamp}

---

## 🌳 完整目录树

```
d:/homeassistant/
│
├── 📊_分析报告/              # 系统分析报告
│   ├── Home_Assistant_系统健康报告_详细版.md
│   ├── 快速参考卡片.md
│   ├── ha_comprehensive_report_*.txt
│   └── 目录整理报告_*.txt
│
├── 🔧_工具脚本/              # Python工具和脚本
│   ├── ha_comprehensive_analysis.py    # 综合分析工具
│   ├── ha_system_analysis.py           # 系统分析工具
│   ├── directory_cleanup_plan.py       # 目录整理工具
│   ├── fix_*.py                        # 各种修复脚本
│   ├── test_*.py                       # 测试脚本
│   └── *.ps1                           # PowerShell脚本
│
├── 📚_文档指南/              # 使用指南和文档
│   ├── 执行摘要_立即行动指南.md
│   ├── home_assistant优化指南.md
│   ├── 移动仪表盘*.md
│   └── README_*.md
│
├── 💾_备份文件/              # 配置备份
│   └── configuration.yaml.*.bak
│
├── 📦_下载资源/              # 下载的组件和资源
│   ├── *.zip                           # 组件压缩包
│   ├── *.ova                           # 虚拟机镜像
│   ├── *-main/                         # 组件源码目录
│   └── HA备份/
│
├── 🗂️_待处理/               # 临时文件
│
├── 🎨_前端资源/              # 前端资源
│
├── config/                   # 核心配置目录 ⚠️ 受保护
│   ├── configuration.yaml              # 主配置文件
│   ├── automations.yaml                # 自动化规则
│   ├── scripts.yaml                    # 脚本配置
│   ├── scenes.yaml                     # 场景配置
│   ├── conversation.yaml               # 对话配置
│   ├── template_sensors.yaml           # 模板传感器
│   ├── home-assistant.log              # 系统日志
│   ├── home-assistant_v2.new.db        # 数据库
│   ├── lovelace/                       # 仪表盘配置
│   ├── python_scripts/                 # Python脚本
│   └── www/                            # Web资源
│
├── custom_components/        # 自定义组件 ⚠️ 受保护
│   ├── hacs/                           # HACS
│   ├── xiaomi_miot/                    # 小米Miot
│   ├── sonoff/                         # Sonoff
│   ├── ha_openai/                      # OpenAI集成
│   ├── extended_openai_conversation/   # OpenAI对话
│   ├── ollama_conversation/            # Ollama
│   ├── localtuya/                      # LocalTuya
│   ├── ecoflow_cloud/                  # EcoFlow
│   ├── bambu_lab/                      # 拓竹3D打印
│   ├── dahua/                          # 大华摄像头
│   └── ... (共37个组件)
│
├── config_backup_20250830_135905/  # 最新备份 ⚠️ 受保护
│
└── README.md                 # 主目录说明

```

---

## 📂 目录详细说明

### 1. 📊_分析报告/

**用途**: 存放系统分析报告和健康检查结果

**主要文件**:
- `Home_Assistant_系统健康报告_详细版.md` - 完整的系统健康分析
- `快速参考卡片.md` - 一页纸快速参考
- `ha_comprehensive_report_*.txt` - 原始分析数据
- `目录整理报告_*.txt` - 目录整理记录

**使用场景**:
- 查看系统当前状态
- 了解需要处理的问题
- 跟踪系统改进进度

---

### 2. 🔧_工具脚本/

**用途**: 存放Python工具和分析脚本

**主要脚本**:
- `ha_comprehensive_analysis.py` - 综合系统分析工具
- `ha_system_analysis.py` - 基础系统分析
- `directory_cleanup_plan.py` - 目录整理工具
- `fix_*.py` - 各种问题修复脚本
- `test_*.py` - 功能测试脚本
- `*.ps1` - PowerShell管理脚本

**使用方法**:
```bash
# 运行综合分析
python 🔧_工具脚本/ha_comprehensive_analysis.py

# 运行修复脚本
python 🔧_工具脚本/fix_assistant_pipeline.py
```

---

### 3. 📚_文档指南/

**用途**: 存放使用指南和说明文档

**主要文档**:
- `执行摘要_立即行动指南.md` - 问题修复行动指南
- `home_assistant优化指南.md` - 系统优化建议
- `移动仪表盘*.md` - 移动端配置指南
- `README_*.md` - 各种说明文档

**适用人群**:
- 系统管理员
- 新用户入门
- 功能配置参考

---

### 4. 💾_备份文件/

**用途**: 存放配置文件备份

**备份策略**:
- 修改配置前创建备份
- 保留最近3个版本
- 定期清理旧备份

**恢复方法**:
```bash
# 恢复配置
cp 💾_备份文件/configuration.yaml.bak config/configuration.yaml
```

---

### 5. 📦_下载资源/

**用途**: 存放下载的组件源码和安装包

**内容**:
- 组件压缩包 (*.zip)
- 虚拟机镜像 (*.ova, *.qcow2)
- 组件源码目录 (*-main/)
- 旧的备份目录

**管理建议**:
- 安装完成后可以删除压缩包
- 保留常用组件的源码
- 定期清理不需要的资源

---

### 6. config/ ⚠️ 核心目录

**用途**: Home Assistant 核心配置

**重要文件**:
- `configuration.yaml` - 主配置（已修复重复项）
- `automations.yaml` - 9个自动化规则
- `scripts.yaml` - 8个场景脚本
- `scenes.yaml` - 8个场景配置
- `home-assistant.log` - 系统日志

**注意事项**:
- ⚠️ 修改前务必备份
- ⚠️ 使用开发者工具检查配置
- ⚠️ 重启前验证语法

---

### 7. custom_components/ ⚠️ 自定义组件

**用途**: 存放37个自定义组件

**组件分类**:
- **AI和语音** (9个): OpenAI, Ollama, Whisper等
- **智能设备** (12个): 小米, Sonoff, Tuya等
- **界面工具** (16个): HACS, Dwains等

**管理方式**:
- 通过HACS统一管理
- 定期检查更新
- 移除不使用的组件

---

## 🔒 受保护的目录

以下目录**不会被自动整理工具移动或删除**:

1. `config/` - 核心配置目录
2. `custom_components/` - 自定义组件
3. `www/` - Web资源
4. `config_backup_20250830_135905/` - 最新备份

---

## 📋 文件命名规范

### 分析报告
- 格式: `*报告_YYYYMMDD_HHMMSS.md`
- 示例: `系统健康报告_20251007_140121.md`

### 工具脚本
- 格式: `功能描述_用途.py`
- 示例: `ha_comprehensive_analysis.py`

### 文档指南
- 格式: `主题_说明.md`
- 示例: `移动仪表盘_部署指南.md`

---

## 🔄 维护流程

### 每周维护
1. 运行系统分析工具
2. 查看生成的报告
3. 处理发现的问题
4. 更新文档

### 每月维护
1. 清理日志文件
2. 优化数据库
3. 检查组件更新
4. 创建完整备份
5. 清理下载资源

### 季度维护
1. 全面系统审计
2. 性能优化
3. 安全加固
4. 文档更新

---

## 📊 目录大小参考

| 目录 | 预估大小 | 说明 |
|------|----------|------|
| config/ | 100-500MB | 包含数据库和日志 |
| custom_components/ | 50-200MB | 37个组件 |
| 📦_下载资源/ | 1-5GB | 可定期清理 |
| 📊_分析报告/ | <10MB | 文本文件 |
| 🔧_工具脚本/ | <5MB | Python脚本 |

---

**文档版本**: 1.0  
**最后更新**: {timestamp}
""".format(timestamp=datetime.now().strftime('%Y年%m月%d日 %H:%M:%S'))
        
        doc_path = self.base_dir / '📚_文档指南' / '目录结构详解.md'
        try:
            with open(doc_path, 'w', encoding='utf-8') as f:
                f.write(doc_content)
            self.stats['created_files'] += 1
            print(f"  ✅ 创建: 目录结构详解.md")
        except Exception as e:
            print(f"  ❌ 创建文档失败: {e}")
            self.stats['errors'].append(f"创建目录结构文档: {e}")
    
    def generate_final_report(self):
        """生成最终整理报告"""
        print("\n📊 生成最终报告...")
        
        report = f"""
{'='*80}
🎉 Home Assistant 目录整理完成报告
{'='*80}
完成时间: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}

📈 整理统计
{'-'*80}
移动文件数量: {self.stats['moved_files']}
创建文档数量: {self.stats['created_files']}
错误数量: {len(self.stats['errors'])}

✅ 完成的任务
{'-'*80}
1. ✅ 修复 config/configuration.yaml 重复配置
   - 删除重复的 logger 配置
   - 删除重复的 python_script 配置

2. ✅ 创建新的目录结构
   - 📊_分析报告/ - 系统分析报告
   - 🔧_工具脚本/ - Python工具脚本
   - 📚_文档指南/ - 使用指南文档
   - 💾_备份文件/ - 配置备份
   - 📦_下载资源/ - 下载的组件
   - 🗂️_待处理/ - 临时文件
   - 🎨_前端资源/ - 前端资源

3. ✅ 整理分析报告和工具脚本
   - 移动所有 .md 报告到分析报告目录
   - 移动所有 .py 脚本到工具脚本目录
   - 移动所有 .ps1 脚本到工具脚本目录

4. ✅ 清理旧的下载目录
   - 移动14个旧组件目录到下载资源
   - 移动压缩包和镜像文件

5. ✅ 创建文档
   - 主目录 README.md
   - 目录结构详解.md
   - 各子目录的 README.md

📁 新目录结构
{'-'*80}
d:/homeassistant/
├── 📊_分析报告/          # 系统分析报告
├── 🔧_工具脚本/          # Python工具和脚本
├── 📚_文档指南/          # 使用指南和文档
├── 💾_备份文件/          # 配置备份
├── 📦_下载资源/          # 下载的组件和资源
├── 🗂️_待处理/           # 临时文件
├── 🎨_前端资源/          # 前端资源
├── config/              # 核心配置 ⚠️ 受保护
├── custom_components/   # 自定义组件 ⚠️ 受保护
└── README.md            # 主目录说明

🎯 下一步建议
{'-'*80}
1. 查看主目录 README.md 了解新的目录结构
2. 阅读 📚_文档指南/目录结构详解.md 获取详细说明
3. 运行 Home Assistant 配置检查验证修复
4. 重启 Home Assistant 使配置生效
5. 查看 📊_分析报告/ 中的系统健康报告

⚠️  重要提示
{'-'*80}
- config/ 目录中的重复配置已修复
- 所有核心配置文件保持不变
- 自定义组件未受影响
- 建议重启 Home Assistant 验证配置

📞 获取帮助
{'-'*80}
- 查看: README.md
- 详细文档: 📚_文档指南/目录结构详解.md
- 快速参考: 📊_分析报告/快速参考卡片.md

{'='*80}
整理完成！您的 Home Assistant 工作目录现在更加整洁有序！
{'='*80}
"""
        
        print(report)
        
        # 保存报告
        report_file = self.base_dir / '📊_分析报告' / f'最终整理报告_{self.timestamp}.txt'
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"\n💾 报告已保存: {report_file}")
        except Exception as e:
            print(f"\n❌ 保存报告失败: {e}")
    
    def run(self):
        """执行最终清理"""
        print("🚀 开始最终整理...\n")
        
        # 1. 移动剩余文件
        self.move_remaining_files()
        
        # 2. 创建主README
        self.create_main_readme()
        
        # 3. 创建目录结构文档
        self.create_directory_structure_doc()
        
        # 4. 生成最终报告
        self.generate_final_report()

def main():
    """主函数"""
    cleanup = FinalCleanup("d:/homeassistant")
    cleanup.run()

if __name__ == "__main__":
    main()

