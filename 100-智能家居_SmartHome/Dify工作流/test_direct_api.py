#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接测试API端口
"""

import requests
import json

def test_direct_api():
    """直接测试API"""
    print("🔍 直接测试API端口...")
    
    try:
        # 直接访问API容器的5001端口（通过nginx代理）
        url = "http://localhost:8090/console/api/health"
        response = requests.get(url, timeout=10)
        
        print(f"📊 健康检查响应状态: {response.status_code}")
        if response.status_code == 200:
            print(f"✅ API健康: {response.text}")
        else:
            print(f"❌ API不健康: {response.text}")
            
    except Exception as e:
        print(f"❌ 健康检查失败: {e}")
    
    # 尝试获取应用列表（不需要认证的接口）
    try:
        print("\n🔍 测试应用列表API...")
        url = "http://localhost:8090/console/api/setup"
        response = requests.get(url, timeout=10)
        
        print(f"📊 Setup API响应状态: {response.status_code}")
        print(f"📄 响应内容: {response.text[:200]}...")
        
    except Exception as e:
        print(f"❌ Setup API失败: {e}")

def check_nginx_logs():
    """检查nginx日志"""
    print("\n📋 检查nginx错误日志...")
    
    import subprocess
    try:
        docker_path = r"C:\Program Files\Docker\Docker\resources\bin\docker.exe"
        cmd = [docker_path, "logs", "docker-nginx-1", "--tail", "20"]
        
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        if result.returncode == 0:
            print("✅ Nginx日志:")
            print(result.stdout)
        else:
            print(f"❌ 获取nginx日志失败: {result.stderr}")
            
    except Exception as e:
        print(f"❌ 检查nginx日志失败: {e}")

def main():
    """主函数"""
    print("🐛 直接API测试工具")
    print("=" * 40)
    
    test_direct_api()
    check_nginx_logs()

if __name__ == "__main__":
    main()
