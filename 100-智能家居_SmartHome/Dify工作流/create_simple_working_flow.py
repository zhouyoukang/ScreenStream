#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
创建一个简单但完全正确的工作流
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

def create_simple_working_workflow():
    """创建简单可工作的工作流"""
    print("🔧 创建简单可工作的工作流...")
    
    app_id = str(uuid.uuid4())
    workflow_id = str(uuid.uuid4())
    
    # 简单的三节点工作流：开始 → LLM → 结束
    simple_graph = {
        "nodes": [
            {
                "id": "start",
                "type": "start",
                "position": {"x": 80, "y": 150},
                "data": {
                    "title": "开始",
                    "type": "start",
                    "variables": [
                        {
                            "variable": "query",
                            "label": "用户问题",
                            "type": "paragraph",
                            "required": True,
                            "max_length": 2000
                        }
                    ]
                }
            },
            {
                "id": "llm",
                "type": "llm",
                "position": {"x": 400, "y": 150},
                "data": {
                    "title": "AI回答",
                    "type": "llm",
                    "model": {
                        "provider": "openai",
                        "name": "gpt-3.5-turbo",
                        "mode": "chat",
                        "completion_params": {
                            "temperature": 0.7,
                            "max_tokens": 1000
                        }
                    },
                    "prompt_template": [
                        {
                            "role": "system",
                            "text": "你是一个有用的AI助手。"
                        },
                        {
                            "role": "user", 
                            "text": "{{#start.query#}}"
                        }
                    ],
                    "context": {
                        "enabled": False
                    },
                    "vision": {
                        "enabled": False
                    },
                    "memory": {
                        "enabled": False
                    }
                }
            },
            {
                "id": "end",
                "type": "end",
                "position": {"x": 720, "y": 150},
                "data": {
                    "title": "结束",
                    "type": "end",
                    "outputs": [
                        {
                            "variable": "answer",
                            "label": "AI回答",
                            "type": "paragraph",
                            "value_selector": ["llm", "text"]
                        }
                    ]
                }
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
    graph_json = json.dumps(simple_graph, ensure_ascii=False).replace("'", "''")
    features_json = json.dumps(features).replace("'", "''")
    
    # 插入应用
    app_sql = f"""
    INSERT INTO apps (
        id, tenant_id, name, mode, icon, icon_background, 
        status, enable_site, enable_api, api_rpm, api_rph, 
        is_demo, is_public, is_universal, workflow_id, 
        description, use_icon_as_answer_icon, created_at, updated_at
    ) VALUES (
        '{app_id}', '19eae045-9287-4361-baf8-95c389fac479', '简单AI助手', 'workflow', 
        '🤖', '#10B981',
        'normal', true, true, 0, 0,
        false, false, false, '{workflow_id}',
        '简单可靠的AI问答助手', false, NOW(), NOW()
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
        print("✅ 简单AI助手工作流创建成功")
        print(f"🤖 应用ID: {app_id}")
        print(f"🔧 工作流ID: {workflow_id}")
        return True
    else:
        print(f"❌ 创建工作流失败: {output}")
        return False

def main():
    """主函数"""
    print("🔧 创建简单可工作的工作流")
    print("=" * 50)
    
    # 创建简单工作流
    if create_simple_working_workflow():
        print("\n🎯 工作流特点:")
        print("- ✅ 3个节点：开始 → AI回答 → 结束")
        print("- ✅ 包含所有必需字段")
        print("- ✅ 使用GPT-3.5-turbo模型")
        print("- ✅ 简单可靠的问答功能")
        
        print("\n🧪 测试用例:")
        print("- 问题: '你好，请介绍一下自己'")
        print("- 预期: AI生成的自我介绍")
        
        print("\n🎯 现在请测试:")
        print("1. 刷新浏览器 http://localhost:8090")
        print("2. 查找 '简单AI助手' 应用")
        print("3. 进入工作流编辑器查看节点")
        print("4. 发布并测试工作流")

if __name__ == "__main__":
    main()
