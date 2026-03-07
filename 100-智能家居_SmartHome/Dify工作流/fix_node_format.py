#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用标准Dify节点格式修复显示问题
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

def create_standard_format_workflow():
    """创建使用标准格式的工作流"""
    print("🔧 创建标准格式工作流...")
    
    app_id = str(uuid.uuid4())
    workflow_id = str(uuid.uuid4())
    
    # 使用标准的Dify节点格式
    standard_graph = {
        "nodes": [
            {
                "id": "start",
                "type": "start",
                "position": {"x": 80, "y": 150},
                "positionAbsolute": {"x": 80, "y": 150},
                "data": {
                    "title": "开始",
                    "desc": "",
                    "type": "start",
                    "variables": [
                        {
                            "variable": "query",
                            "label": "用户输入",
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
                    "title": "LLM",
                    "desc": "",
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
                            "text": "{{#start.query#}}"
                        }
                    ],
                    "memory": {
                        "enabled": False
                    },
                    "vision": {
                        "enabled": False
                    }
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
                    "title": "结束",
                    "desc": "",
                    "type": "end",
                    "outputs": [
                        {
                            "variable": "result",
                            "label": "结果",
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
    graph_json = json.dumps(standard_graph, ensure_ascii=False).replace("'", "''")
    features_json = json.dumps(features).replace("'", "''")
    
    # 插入应用
    app_sql = f"""
    INSERT INTO apps (
        id, tenant_id, name, mode, icon, icon_background, 
        status, enable_site, enable_api, api_rpm, api_rph, 
        is_demo, is_public, is_universal, workflow_id, 
        description, use_icon_as_answer_icon, created_at, updated_at
    ) VALUES (
        '{app_id}', '19eae045-9287-4361-baf8-95c389fac479', '标准格式测试', 'workflow', 
        '🎯', '#8B5CF6',
        'normal', true, true, 0, 0,
        false, false, false, '{workflow_id}',
        '使用标准Dify格式的测试工作流', false, NOW(), NOW()
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
        print("✅ 标准格式测试工作流创建成功")
        print(f"🎯 应用ID: {app_id}")
        print(f"🔧 工作流ID: {workflow_id}")
        return True
    else:
        print(f"❌ 创建工作流失败: {output}")
        return False

def check_existing_working_workflow():
    """检查是否有其他正常工作的工作流作为参考"""
    print("\n🔍 检查现有工作流...")
    
    sql = """
    SELECT 
        a.name,
        (w.graph::jsonb->'nodes'->0->'data'->>'title') as node_title,
        LENGTH(w.graph) as graph_size
    FROM apps a 
    JOIN workflows w ON a.workflow_id = w.id 
    WHERE a.mode = 'workflow' 
    ORDER BY a.created_at DESC 
    LIMIT 5;
    """
    
    success, output = execute_docker_sql(sql)
    if success:
        print("📊 现有工作流对比:")
        print(output)
    else:
        print(f"❌ 检查失败: {output}")

def main():
    """主函数"""
    print("🎯 使用标准格式修复节点显示")
    print("=" * 50)
    
    # 检查现有工作流
    check_existing_working_workflow()
    
    # 创建标准格式工作流
    create_standard_format_workflow()
    
    print("\n💡 关键修复点:")
    print("- 添加了 positionAbsolute 字段")
    print("- 添加了 selected 和 dragging 字段")
    print("- 添加了 viewport 配置")
    print("- 使用了标准的节点尺寸")
    print("- 添加了边的 data 字段")
    
    print("\n🎯 测试步骤:")
    print("1. 刷新浏览器")
    print("2. 查看 '标准格式测试' 应用")
    print("3. 节点应该显示: '开始' → 'LLM' → '结束'")

if __name__ == "__main__":
    main()
