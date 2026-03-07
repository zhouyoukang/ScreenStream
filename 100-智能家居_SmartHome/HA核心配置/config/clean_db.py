#!/usr/bin/env python3
"""
Home Assistant 数据库修复工具
此脚本用于清理和修复 Home Assistant 数据库问题
"""
import os
import sys
import time
import sqlite3
import shutil
from pathlib import Path

def main():
    """主函数，执行数据库清理和修复"""
    print("Home Assistant 数据库修复工具")
    print("="*50)
    
    # 当前工作目录应该是 config 文件夹
    cwd = Path.cwd()
    print(f"当前工作目录: {cwd}")
    
    # 检查数据库文件
    old_db = cwd / "home-assistant_v2.db"
    backup_db = cwd / "home-assistant_v2.db.backup"
    new_db = cwd / "home-assistant_v2.new.db"
    
    if not old_db.exists():
        print(f"错误: 找不到原始数据库文件 {old_db}")
        return 1
    
    print(f"原始数据库大小: {old_db.stat().st_size / (1024*1024*1024):.2f} GB")
    
    # 尝试打开原始数据库
    try:
        print("尝试连接原始数据库...")
        conn = sqlite3.connect(str(old_db))
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check;")
        result = cursor.fetchone()
        if result[0] == "ok":
            print("数据库完整性检查: 通过")
        else:
            print(f"数据库完整性检查: 失败 - {result[0]}")
        conn.close()
    except sqlite3.Error as e:
        print(f"错误: 无法打开原始数据库 - {e}")
        print("原始数据库可能已损坏")
    
    # 创建新的空数据库
    if new_db.exists():
        print(f"新数据库已存在，大小: {new_db.stat().st_size / (1024*1024):.2f} MB")
    else:
        try:
            print("创建新的空数据库...")
            conn = sqlite3.connect(str(new_db))
            conn.close()
            print(f"新数据库已创建: {new_db}")
        except sqlite3.Error as e:
            print(f"错误: 无法创建新数据库 - {e}")
            return 1
    
    print("\n请确保您已完成以下操作:")
    print("1. 修改了 configuration.yaml 中的 recorder 配置使用 home-assistant_v2.new.db")
    print("2. 已重启 Home Assistant 或计划重启")
    print("\n注意: 新数据库将不包含历史数据，但系统将恢复正常运行")
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 