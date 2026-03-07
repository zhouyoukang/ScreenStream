#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import shutil
import sys

def copy_gooddawg_files():
    """复制gooddawg库文件到合适位置"""
    # 获取当前目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 源目录路径 - 修正为宇树go1电机/gooddawg目录
    source_dir = os.path.join(os.path.dirname(current_dir), '宇树go1电机', 'gooddawg')
    
    # 目标目录路径 (在当前目录的父级目录下创建一个gooddawg目录)
    target_dir = os.path.join(os.path.dirname(current_dir), 'gooddawg')
    
    # 检查源目录是否存在
    if not os.path.exists(source_dir):
        print(f"错误: 找不到源目录 {source_dir}")
        print("尝试创建源目录和必要的文件...")
        
        # 如果源目录不存在，尝试从build_a_packet.py创建
        build_packet_path = os.path.join(os.path.dirname(current_dir), '宇树go1电机', 'build_a_packet.py')
        if os.path.exists(build_packet_path):
            # 创建源目录
            os.makedirs(source_dir, exist_ok=True)
            
            # 复制build_a_packet.py到源目录
            shutil.copy2(build_packet_path, os.path.join(source_dir, 'build_a_packet.py'))
            print(f"已从 {build_packet_path} 创建必要文件")
        else:
            print(f"错误: 无法找到 {build_packet_path}")
            sys.exit(1)
    
    # 如果目标目录不存在，则创建
    os.makedirs(target_dir, exist_ok=True)
    
    # 创建__init__.py文件
    init_file = os.path.join(target_dir, '__init__.py')
    with open(init_file, 'w') as f:
        f.write('# gooddawg库初始化文件\n')
    
    print(f"已创建 {init_file}")
    
    # 复制build_a_packet.py文件
    try:
        build_a_packet_src = os.path.join(source_dir, 'build_a_packet.py')
        build_a_packet_dst = os.path.join(target_dir, 'build_a_packet.py')
        
        if os.path.exists(build_a_packet_src):
            shutil.copy2(build_a_packet_src, build_a_packet_dst)
            print(f"已复制 {build_a_packet_src} 到 {build_a_packet_dst}")
        else:
            print(f"警告: 找不到 {build_a_packet_src}")
    
    except Exception as e:
        print(f"复制文件时出错: {e}")
        sys.exit(1)
    
    print("\n准备工作完成！")
    print("现在可以运行 gooddawg_test.py 脚本测试电机了。")

if __name__ == "__main__":
    print("准备 gooddawg 库环境...")
    copy_gooddawg_files() 