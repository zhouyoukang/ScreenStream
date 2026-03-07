#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试前端显示问题
"""

import json
import uuid
import subprocess

def execute_docker_sql(sql_command):
    """执行Docker中的SQL命令"""
    try:
        docker_path = r"C:\Program Files\Docker\Docker\resources\bin\docker.exe"
        cmd = [
            docker_path, "exec", "docker-db-1", 
            "psql", "-U", "postgres", "-d", "dify", 
            "-c", sql_command
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        
        if result.returncode == 0:
            return True, result.stdout
        else:
            return False, result.stderr
    except Exception as e:
        return False, str(e)

def create_english_title_workflow():
    """创建英文标题的工作流，排除中文显示问题"""
    print("🔧 创建英文标题工作流...")
    
    app_id = str(uuid.uuid4())
    workflow_id = str(uuid.uuid4())
    
    # 使用英文标题
    english_graph = {
        "nodes": [
            {
                "id": "start",
                "type": "start",
                "position": {"x": 80, "y": 150},
                "positionAbsolute": {"x": 80, "y": 150},
                "data": {
                    "title": "Start",
                    "desc": "Start node",
                    "type": "start",
                    "variables": [
                        {
                            "variable": "input",
                            "label": "User Input",
                            "type": "paragraph",
                            "required": True,
                            "max_length": 1000
                        }
                    ]
                },
                "width": 243,
                "height": 52,
                "selected": False,
                "dragging": False
            },
            {
                "id": "llm",
                "type": "llm",
                "position": {"x": 400, "y": 150},
                "positionAbsolute": {"x": 400, "y": 150},
                "data": {
                    "title": "LLM Node",
                    "desc": "AI processing",
                    "type": "llm",
                    "model": {
                        "provider": "openai",
                        "name": "gpt-3.5-turbo",
                        "mode": "chat",
                        "completion_params": {
                            "temperature": 0.7
                        }
                    },
                    "prompt_template": [
                        {
                            "role": "user",
                            "text": "{{#start.input#}}"
                        }
                    ]
                },
                "width": 243,
                "height": 52,
                "selected": False,
                "dragging": False
            },
            {
                "id": "end",
                "type": "end",
                "position": {"x": 720, "y": 150},
                "positionAbsolute": {"x": 720, "y": 150},
                "data": {
                    "title": "End",
                    "desc": "End node",
                    "type": "end",
                    "outputs": [
                        {
                            "variable": "output",
                            "label": "Result",
                            "type": "paragraph",
                            "value_selector": ["llm", "text"]
                        }
                    ]
                },
                "width": 243,
                "height": 52,
                "selected": False,
                "dragging": False
            }
        ],
        "edges": [
            {
                "id": "start-llm",
                "source": "start",
                "target": "llm",
                "type": "custom",
                "sourceHandle": "source",
                "targetHandle": "target",
                "data": {}
            },
            {
                "id": "llm-end",
                "source": "llm",
                "target": "end",
                "type": "custom",
                "sourceHandle": "source",
                "targetHandle": "target",
                "data": {}
            }
        ],
        "viewport": {
            "x": 0,
            "y": 0,
            "zoom": 1
        }
    }
    
    features = {
        "text_to_speech": {"enabled": False},
        "speech_to_text": {"enabled": False},
        "retrieval": {"enabled": False},
        "sensitive_word_avoidance": {"enabled": False}
    }
    
    # 转义JSON
    graph_json = json.dumps(english_graph, ensure_ascii=False).replace("'", "''")
    features_json = json.dumps(features).replace("'", "''")
    
    # 插入应用
    app_sql = f"""
    INSERT INTO apps (
        id, tenant_id, name, mode, icon, icon_background, 
        status, enable_site, enable_api, api_rpm, api_rph, 
        is_demo, is_public, is_universal, workflow_id, 
        description, use_icon_as_answer_icon, created_at, updated_at
    ) VALUES (
        '{app_id}', '19eae045-9287-4361-baf8-95c389fac479', 'English Title Test', 'workflow', 
        '🇺🇸', '#F59E0B',
        'normal', true, true, 0, 0,
        false, false, false, '{workflow_id}',
        'Test workflow with English titles', false, NOW(), NOW()
    );
    """
    
    success, output = execute_docker_sql(app_sql)
    if not success:
        print(f"❌ 创建应用失败: {output}")
        return False
    
    # 插入工作流
    workflow_sql = f"""
    INSERT INTO workflows (
        id, tenant_id, app_id, type, version, graph, features,
        created_by, created_at, updated_at, environment_variables, 
        conversation_variables
    ) VALUES (
        '{workflow_id}', '19eae045-9287-4361-baf8-95c389fac479', '{app_id}', 'workflow', 'draft', 
        '{graph_json}', '{features_json}',
        '19eae045-9287-4361-baf8-95c389fac479', NOW(), NOW(), '{{}}', '{{}}'
    );
    """
    
    success, output = execute_docker_sql(workflow_sql)
    if success:
        print("✅ 英文标题测试工作流创建成功")
        print(f"🇺🇸 应用ID: {app_id}")
        print(f"🔧 工作流ID: {workflow_id}")
        return True
    else:
        print(f"❌ 创建工作流失败: {output}")
        return False

def check_browser_console_logs():
    """提供检查浏览器控制台的指导"""
    print("\n🔍 浏览器调试指导:")
    print("=" * 40)
    print("请在浏览器中按 F12 打开开发者工具，然后:")
    print("1. 切换到 Console 标签")
    print("2. 刷新页面")
    print("3. 查看是否有 JavaScript 错误")
    print("4. 特别注意与 'node'、'title'、'render' 相关的错误")
    print()
    print("常见错误类型:")
    print("- 字体加载失败")
    print("- CSS 样式问题")
    print("- React 渲染错误")
    print("- 数据格式不匹配")

def restart_containers():
    """重启容器的指导"""
    print("\n🔄 容器重启指导:")
    print("=" * 40)
    print("如果问题持续存在，可能需要重启容器:")
    print("1. 停止容器: docker-compose down")
    print("2. 启动容器: docker-compose up -d")
    print("3. 等待所有服务启动完成")
    print("4. 重新访问 http://localhost:8090")

def main():
    """主函数"""
    print("🐛 前端显示问题调试")
    print("=" * 50)
    
    # 创建英文标题工作流
    create_english_title_workflow()
    
    # 提供调试指导
    check_browser_console_logs()
    restart_containers()
    
    print("\n🎯 测试计划:")
    print("1. 刷新浏览器，查看 'English Title Test' 应用")
    print("2. 检查节点是否显示: 'Start' → 'LLM Node' → 'End'")
    print("3. 如果英文也不显示，问题可能是:")
    print("   - 前端渲染逻辑问题")
    print("   - CSS 样式问题")
    print("   - 容器需要重启")
    print("4. 如果英文显示正常，问题可能是中文字体问题")

if __name__ == "__main__":
    main()
