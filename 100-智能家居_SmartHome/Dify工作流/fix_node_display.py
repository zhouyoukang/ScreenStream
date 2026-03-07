#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复节点显示问题 - 添加正确的节点标题和内容
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

def create_complete_workflow():
    """创建一个完整显示的工作流"""
    print("🔧 创建完整显示的工作流...")
    
    app_id = str(uuid.uuid4())
    workflow_id = str(uuid.uuid4())
    
    # 完整的工作流结构，确保所有显示字段都正确
    complete_graph = {
        "nodes": [
            {
                "id": "start",
                "type": "start",
                "position": {"x": 80, "y": 150},
                "data": {
                    "title": "开始",
                    "desc": "工作流开始节点",
                    "type": "start",
                    "variables": [
                        {
                            "variable": "user_question",
                            "label": "用户问题",
                            "type": "paragraph",
                            "required": True,
                            "max_length": 2000,
                            "description": "请输入你的问题"
                        }
                    ]
                },
                "width": 243,
                "height": 84
            },
            {
                "id": "llm",
                "type": "llm",
                "position": {"x": 400, "y": 150},
                "data": {
                    "title": "AI回答",
                    "desc": "使用AI生成回答",
                    "type": "llm",
                    "model": {
                        "provider": "openai",
                        "name": "gpt-3.5-turbo",
                        "mode": "chat",
                        "completion_params": {
                            "temperature": 0.7,
                            "max_tokens": 2000
                        }
                    },
                    "prompt_template": [
                        {
                            "role": "system",
                            "text": "你是一个有用的AI助手，请回答用户的问题。"
                        },
                        {
                            "role": "user",
                            "text": "{{#start.user_question#}}"
                        }
                    ]
                },
                "width": 243,
                "height": 84
            },
            {
                "id": "end",
                "type": "end",
                "position": {"x": 720, "y": 150},
                "data": {
                    "title": "结束",
                    "desc": "工作流结束节点",
                    "type": "end",
                    "outputs": [
                        {
                            "variable": "answer",
                            "label": "AI回答",
                            "type": "paragraph",
                            "value_selector": ["llm", "text"]
                        }
                    ]
                },
                "width": 243,
                "height": 84
            }
        ],
        "edges": [
            {
                "id": "start-llm",
                "source": "start",
                "target": "llm",
                "type": "custom",
                "sourceHandle": "source",
                "targetHandle": "target"
            },
            {
                "id": "llm-end",
                "source": "llm",
                "target": "end",
                "type": "custom",
                "sourceHandle": "source",
                "targetHandle": "target"
            }
        ]
    }
    
    features = {
        "text_to_speech": {"enabled": False},
        "speech_to_text": {"enabled": False},
        "retrieval": {"enabled": False},
        "sensitive_word_avoidance": {"enabled": False}
    }
    
    # 转义JSON
    graph_json = json.dumps(complete_graph, ensure_ascii=False).replace("'", "''")
    features_json = json.dumps(features).replace("'", "''")
    
    # 插入应用
    app_sql = f"""
    INSERT INTO apps (
        id, tenant_id, name, mode, icon, icon_background, 
        status, enable_site, enable_api, api_rpm, api_rph, 
        is_demo, is_public, is_universal, workflow_id, 
        description, use_icon_as_answer_icon, created_at, updated_at
    ) VALUES (
        '{app_id}', '19eae045-9287-4361-baf8-95c389fac479', '完整显示测试', 'workflow', 
        '✨', '#10B981',
        'normal', true, true, 0, 0,
        false, false, false, '{workflow_id}',
        '节点标题完整显示的测试工作流', false, NOW(), NOW()
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
        print("✅ 完整显示测试工作流创建成功")
        print(f"✨ 应用ID: {app_id}")
        print(f"🔧 工作流ID: {workflow_id}")
        return True
    else:
        print(f"❌ 创建工作流失败: {output}")
        return False

def update_existing_workflow():
    """更新现有的超简单测试工作流，添加标题"""
    print("\n🔄 更新现有工作流的节点标题...")
    
    # 获取超简单测试的工作流ID
    sql = """
    SELECT w.id, w.graph 
    FROM workflows w 
    JOIN apps a ON w.app_id = a.id 
    WHERE a.name = '超简单测试';
    """
    
    success, output = execute_docker_sql(sql)
    if not success:
        print(f"❌ 获取工作流失败: {output}")
        return False
    
    # 解析输出获取工作流ID
    lines = output.strip().split('\n')
    workflow_id = None
    for line in lines:
        if line.strip() and not line.startswith('-') and not line.startswith('id') and not line.startswith('('):
            parts = line.split('|')
            if len(parts) >= 2:
                workflow_id = parts[0].strip()
                break
    
    if not workflow_id:
        print("❌ 未找到工作流ID")
        return False
    
    # 更新图结构，添加正确的标题
    updated_graph = {
        "nodes": [
            {
                "id": "start",
                "type": "start",
                "position": {"x": 100, "y": 200},
                "data": {
                    "title": "开始",
                    "desc": "工作流开始",
                    "type": "start",
                    "variables": [
                        {
                            "variable": "query",
                            "label": "用户问题",
                            "type": "paragraph",
                            "required": True,
                            "max_length": 1000,
                            "description": "请输入你的问题"
                        }
                    ]
                },
                "width": 243,
                "height": 84
            },
            {
                "id": "end",
                "type": "end", 
                "position": {"x": 500, "y": 200},
                "data": {
                    "title": "结束",
                    "desc": "工作流结束",
                    "type": "end",
                    "outputs": [
                        {
                            "variable": "result",
                            "label": "结果",
                            "type": "paragraph",
                            "value_selector": ["start", "query"]
                        }
                    ]
                },
                "width": 243,
                "height": 84
            }
        ],
        "edges": [
            {
                "id": "start-end",
                "source": "start",
                "target": "end",
                "type": "custom",
                "sourceHandle": "source",
                "targetHandle": "target"
            }
        ]
    }
    
    graph_json = json.dumps(updated_graph, ensure_ascii=False).replace("'", "''")
    
    # 更新工作流
    update_sql = f"""
    UPDATE workflows 
    SET graph = '{graph_json}', updated_at = NOW()
    WHERE id = '{workflow_id}';
    """
    
    success, output = execute_docker_sql(update_sql)
    if success:
        print("✅ 工作流标题更新成功")
        return True
    else:
        print(f"❌ 更新失败: {output}")
        return False

def main():
    """主函数"""
    print("✨ 修复节点显示问题")
    print("=" * 50)
    
    # 创建新的完整显示工作流
    create_complete_workflow()
    
    # 更新现有工作流
    update_existing_workflow()
    
    print("\n🎯 现在请测试:")
    print("1. 刷新浏览器")
    print("2. 查看 '完整显示测试' 应用")
    print("3. 查看更新后的 '超简单测试' 应用")
    print("4. 节点应该显示正确的标题：'开始'、'AI回答'、'结束'")

if __name__ == "__main__":
    main()
