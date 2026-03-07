#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试API响应，看看前端实际收到的工作流数据
"""

import requests
import json
import subprocess

def get_tenant_info():
    """获取租户信息"""
    try:
        docker_path = r"C:\Program Files\Docker\Docker\resources\bin\docker.exe"
        cmd = [
            docker_path, "exec", "docker-db-1", 
            "psql", "-U", "postgres", "-d", "dify", 
            "-c", "SELECT id FROM tenants LIMIT 1;"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if line.strip() and not line.startswith('-') and not line.startswith('id') and not line.startswith('('):
                    return line.strip()
        return None
    except Exception as e:
        print(f"获取租户信息失败: {e}")
        return None

def get_app_info():
    """获取应用信息"""
    try:
        docker_path = r"C:\Program Files\Docker\Docker\resources\bin\docker.exe"
        cmd = [
            docker_path, "exec", "docker-db-1", 
            "psql", "-U", "postgres", "-d", "dify", 
            "-c", "SELECT id, name FROM apps WHERE name LIKE '%复制版%' LIMIT 1;"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        if result.returncode == 0:
            print("应用查询结果:")
            print(result.stdout)
            # 解析结果获取app_id
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if 'DeepResearch复制版' in line:
                    parts = line.split('|')
                    if len(parts) >= 2:
                        app_id = parts[0].strip()
                        return app_id
        return None
    except Exception as e:
        print(f"获取应用信息失败: {e}")
        return None

def test_api_call():
    """测试API调用"""
    print("🔍 调试API响应...")
    
    # 获取租户ID
    tenant_id = get_tenant_info()
    if not tenant_id:
        print("❌ 无法获取租户ID")
        return
    
    print(f"✅ 租户ID: {tenant_id}")
    
    # 获取应用ID
    app_id = get_app_info()
    if not app_id:
        print("❌ 无法获取应用ID")
        return
    
    print(f"✅ 应用ID: {app_id}")
    
    # 尝试调用API
    try:
        # 首先尝试获取应用列表
        url = "http://localhost:8090/console/api/apps"
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        print(f"🌐 调用API: {url}")
        response = requests.get(url, headers=headers, timeout=10)
        
        print(f"📊 响应状态: {response.status_code}")
        print(f"📋 响应头: {dict(response.headers)}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ API响应成功")
            print(f"📄 响应数据长度: {len(str(data))}")
            
            # 查找我们的应用
            if 'data' in data:
                apps = data['data']
                for app in apps:
                    if 'DeepResearch复制版' in app.get('name', ''):
                        print(f"🎯 找到目标应用: {app['name']}")
                        print(f"📝 应用模式: {app.get('mode', 'unknown')}")
                        print(f"🆔 应用ID: {app.get('id', 'unknown')}")
                        break
            else:
                print("⚠️ 响应中没有data字段")
                print(f"📄 完整响应: {json.dumps(data, indent=2, ensure_ascii=False)}")
        else:
            print(f"❌ API调用失败: {response.status_code}")
            print(f"📄 错误响应: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ 网络请求失败: {e}")
    except json.JSONDecodeError as e:
        print(f"❌ JSON解析失败: {e}")
    except Exception as e:
        print(f"❌ 未知错误: {e}")

def check_workflow_api():
    """检查工作流API"""
    print("\n🔧 检查工作流API...")
    
    app_id = get_app_info()
    if not app_id:
        return
    
    try:
        # 尝试获取工作流详情
        url = f"http://localhost:8090/console/api/apps/{app_id}/workflows/draft"
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        print(f"🌐 调用工作流API: {url}")
        response = requests.get(url, headers=headers, timeout=10)
        
        print(f"📊 响应状态: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ 工作流API响应成功")
            
            if 'graph' in data:
                graph = data['graph']
                print(f"📊 图数据存在，节点数: {len(graph.get('nodes', []))}")
                print(f"🔗 边数: {len(graph.get('edges', []))}")
                
                # 打印节点信息
                for i, node in enumerate(graph.get('nodes', [])):
                    print(f"  节点{i+1}: ID={node.get('id')}, Type={node.get('type')}, Title={node.get('data', {}).get('title')}")
            else:
                print("⚠️ 响应中没有graph字段")
                print(f"📄 响应键: {list(data.keys())}")
        else:
            print(f"❌ 工作流API调用失败: {response.status_code}")
            print(f"📄 错误响应: {response.text}")
            
    except Exception as e:
        print(f"❌ 工作流API调用失败: {e}")

def main():
    """主函数"""
    print("🐛 Dify API响应调试工具")
    print("=" * 50)
    
    test_api_call()
    check_workflow_api()
    
    print("\n💡 如果API响应正常但前端不显示，可能的原因:")
    print("1. 前端JavaScript错误")
    print("2. 浏览器缓存问题")
    print("3. 版本兼容性问题")
    print("4. 前端渲染逻辑问题")

if __name__ == "__main__":
    main()
