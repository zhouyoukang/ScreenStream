#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复工作流的draft状态
"""

import json
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

def check_workflow_structure():
    """检查工作流结构"""
    print("🔍 检查工作流结构...")
    
    sql = """
    SELECT 
        a.name,
        a.id as app_id,
        w.id as workflow_id,
        w.version,
        LENGTH(w.graph) as graph_length,
        (w.graph::jsonb->'nodes'->0->'type')::text as first_node_type,
        (w.graph::jsonb->'nodes'->1->'type')::text as second_node_type,
        (w.graph::jsonb->'nodes'->2->'type')::text as third_node_type
    FROM apps a 
    JOIN workflows w ON a.workflow_id = w.id 
    WHERE a.name LIKE '%复制版%' OR a.name LIKE '%测试%'
    ORDER BY a.created_at DESC;
    """
    
    success, output = execute_docker_sql(sql)
    if success:
        print("✅ 工作流结构:")
        print(output)
        return True
    else:
        print(f"❌ 检查失败: {output}")
        return False

def update_workflow_version():
    """更新工作流版本为draft"""
    print("\n🔧 更新工作流版本...")
    
    # 获取所有测试工作流的ID
    sql = """
    UPDATE workflows 
    SET version = 'draft'
    WHERE app_id IN (
        SELECT id FROM apps 
        WHERE name LIKE '%复制版%' OR name LIKE '%测试%' OR name LIKE '%修复版%'
    );
    """
    
    success, output = execute_docker_sql(sql)
    if success:
        print("✅ 版本更新成功")
        return True
    else:
        print(f"❌ 版本更新失败: {output}")
        return False

def create_simple_working_workflow():
    """创建一个确定能工作的简单工作流"""
    print("\n🛠️ 创建确定能工作的简单工作流...")
    
    import uuid
    
    app_id = str(uuid.uuid4())
    workflow_id = str(uuid.uuid4())
    
    # 最简单的工作流 - 只有开始和结束节点
    simple_graph = {
        "nodes": [
            {
                "id": "start",
                "type": "start",
                "position": {"x": 100, "y": 200},
                "data": {
                    "title": "开始",
                    "type": "start",
                    "variables": [
                        {
                            "variable": "query",
                            "label": "用户问题",
                            "type": "paragraph",
                            "required": True,
                            "max_length": 1000
                        }
                    ]
                }
            },
            {
                "id": "end",
                "type": "end", 
                "position": {"x": 500, "y": 200},
                "data": {
                    "title": "结束",
                    "type": "end",
                    "outputs": [
                        {
                            "variable": "result",
                            "label": "结果",
                            "type": "paragraph",
                            "value_selector": ["start", "query"]
                        }
                    ]
                }
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
        '{app_id}', '19eae045-9287-4361-baf8-95c389fac479', '超简单测试', 'workflow', 
        '⚡', '#EF4444',
        'normal', true, true, 0, 0,
        false, false, false, '{workflow_id}',
        '只有开始和结束的超简单测试', false, NOW(), NOW()
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
        print("✅ 超简单测试工作流创建成功")
        print(f"⚡ 应用ID: {app_id}")
        print(f"🔧 工作流ID: {workflow_id}")
        return True
    else:
        print(f"❌ 创建工作流失败: {output}")
        return False

def main():
    """主函数"""
    print("🔧 修复工作流Draft状态")
    print("=" * 50)
    
    # 检查当前结构
    check_workflow_structure()
    
    # 更新版本
    update_workflow_version()
    
    # 创建超简单测试
    create_simple_working_workflow()
    
    # 再次检查
    print("\n🔍 最终检查...")
    check_workflow_structure()
    
    print("\n🎯 现在请测试:")
    print("1. 刷新浏览器 http://localhost:8090")
    print("2. 查找 '超简单测试' 应用")
    print("3. 进入工作流编辑器")
    print("4. 应该能看到开始和结束两个节点")

if __name__ == "__main__":
    main()
