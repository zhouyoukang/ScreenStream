#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
创建一个综合性的多功能工作流，测试所有主要节点类型
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

def create_comprehensive_workflow():
    """创建综合性工作流"""
    print("🚀 创建综合性多功能工作流...")
    
    app_id = str(uuid.uuid4())
    workflow_id = str(uuid.uuid4())
    
    # 综合性工作流：开始 → 条件分支 → LLM/HTTP请求 → 文本处理 → 结束
    comprehensive_graph = {
        "nodes": [
            # 开始节点
            {
                "id": "start",
                "type": "start",
                "position": {"x": 100, "y": 200},
                "data": {
                    "title": "开始",
                    "type": "start",
                    "variables": [
                        {
                            "variable": "user_query",
                            "label": "用户问题",
                            "type": "paragraph",
                            "required": True,
                            "max_length": 2000,
                            "description": "请输入您的问题"
                        },
                        {
                            "variable": "query_type",
                            "label": "问题类型",
                            "type": "select",
                            "required": True,
                            "options": [
                                {"label": "AI问答", "value": "ai_chat"},
                                {"label": "网络搜索", "value": "web_search"},
                                {"label": "文本处理", "value": "text_process"}
                            ],
                            "description": "选择问题处理方式"
                        }
                    ]
                }
            },
            
            # 条件分支节点
            {
                "id": "condition",
                "type": "if-else",
                "position": {"x": 400, "y": 200},
                "data": {
                    "title": "智能路由",
                    "type": "if-else",
                    "conditions": [
                        {
                            "id": "ai_route",
                            "variable_selector": ["start", "query_type"],
                            "comparison_operator": "is",
                            "value": "ai_chat"
                        }
                    ],
                    "logical_operator": "and"
                }
            },
            
            # LLM节点 (AI问答路径)
            {
                "id": "llm_chat",
                "type": "llm",
                "position": {"x": 600, "y": 100},
                "data": {
                    "title": "AI智能问答",
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
                            "text": "你是一个专业的AI助手，请根据用户问题提供准确、有用的回答。"
                        },
                        {
                            "role": "user",
                            "text": "用户问题：{{#start.user_query#}}\n\n请提供详细的回答。"
                        }
                    ]
                }
            },
            
            # HTTP请求节点 (网络搜索路径)
            {
                "id": "web_search",
                "type": "http-request",
                "position": {"x": 600, "y": 300},
                "data": {
                    "title": "网络搜索",
                    "type": "http-request",
                    "method": "GET",
                    "url": "https://api.duckduckgo.com/",
                    "params": [
                        {
                            "key": "q",
                            "value": "{{#start.user_query#}}"
                        },
                        {
                            "key": "format",
                            "value": "json"
                        }
                    ],
                    "headers": {
                        "User-Agent": "Dify-Workflow/1.0"
                    }
                }
            },
            
            # 文本处理节点
            {
                "id": "text_processor",
                "type": "template-transform",
                "position": {"x": 900, "y": 200},
                "data": {
                    "title": "结果处理",
                    "type": "template-transform",
                    "template": "## 处理结果\n\n**原始问题：** {{#start.user_query#}}\n\n**问题类型：** {{#start.query_type#}}\n\n**处理结果：**\n{% if condition.result == true %}\n{{#llm_chat.text#}}\n{% else %}\n基于网络搜索的结果处理\n{% endif %}\n\n**处理时间：** {{#sys.current_time#}}"
                }
            },
            
            # 结束节点
            {
                "id": "end",
                "type": "end",
                "position": {"x": 1200, "y": 200},
                "data": {
                    "title": "完成",
                    "type": "end",
                    "outputs": [
                        {
                            "variable": "final_result",
                            "label": "最终结果",
                            "type": "paragraph",
                            "value_selector": ["text_processor", "output"]
                        },
                        {
                            "variable": "query_type_used",
                            "label": "使用的处理方式",
                            "type": "string",
                            "value_selector": ["start", "query_type"]
                        }
                    ]
                }
            }
        ],
        
        "edges": [
            # 开始 → 条件分支
            {
                "id": "start-condition",
                "source": "start",
                "target": "condition",
                "type": "custom",
                "sourceHandle": "source",
                "targetHandle": "target"
            },
            
            # 条件分支 → LLM (true路径)
            {
                "id": "condition-llm",
                "source": "condition",
                "target": "llm_chat",
                "type": "custom",
                "sourceHandle": "true",
                "targetHandle": "target"
            },
            
            # 条件分支 → HTTP请求 (false路径)
            {
                "id": "condition-http",
                "source": "condition",
                "target": "web_search",
                "type": "custom",
                "sourceHandle": "false",
                "targetHandle": "target"
            },
            
            # LLM → 文本处理
            {
                "id": "llm-processor",
                "source": "llm_chat",
                "target": "text_processor",
                "type": "custom",
                "sourceHandle": "source",
                "targetHandle": "target"
            },
            
            # HTTP请求 → 文本处理
            {
                "id": "http-processor",
                "source": "web_search",
                "target": "text_processor",
                "type": "custom",
                "sourceHandle": "source",
                "targetHandle": "target"
            },
            
            # 文本处理 → 结束
            {
                "id": "processor-end",
                "source": "text_processor",
                "target": "end",
                "type": "custom",
                "sourceHandle": "source",
                "targetHandle": "target"
            }
        ],
        
        "viewport": {
            "x": 0,
            "y": 0,
            "zoom": 0.8
        }
    }
    
    features = {
        "text_to_speech": {"enabled": False},
        "speech_to_text": {"enabled": False},
        "retrieval": {"enabled": False},
        "sensitive_word_avoidance": {"enabled": False}
    }
    
    # 转义JSON
    graph_json = json.dumps(comprehensive_graph, ensure_ascii=False).replace("'", "''")
    features_json = json.dumps(features).replace("'", "''")
    
    # 插入应用
    app_sql = f"""
    INSERT INTO apps (
        id, tenant_id, name, mode, icon, icon_background, 
        status, enable_site, enable_api, api_rpm, api_rph, 
        is_demo, is_public, is_universal, workflow_id, 
        description, use_icon_as_answer_icon, created_at, updated_at
    ) VALUES (
        '{app_id}', '19eae045-9287-4361-baf8-95c389fac479', '综合智能助手', 'workflow', 
        '🤖', '#6366F1',
        'normal', true, true, 0, 0,
        false, false, false, '{workflow_id}',
        '集成AI问答、网络搜索、文本处理的综合性智能助手', false, NOW(), NOW()
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
        print("✅ 综合智能助手工作流创建成功")
        print(f"🤖 应用ID: {app_id}")
        print(f"🔧 工作流ID: {workflow_id}")
        return app_id, workflow_id
    else:
        print(f"❌ 创建工作流失败: {output}")
        return None, None

def main():
    """主函数"""
    print("🚀 创建综合性多功能工作流")
    print("=" * 60)
    
    app_id, workflow_id = create_comprehensive_workflow()
    
    if app_id and workflow_id:
        print("\n🎯 工作流功能说明:")
        print("=" * 40)
        print("📝 **开始节点**: 接收用户问题和问题类型选择")
        print("🔀 **条件分支**: 根据问题类型智能路由")
        print("🤖 **LLM节点**: AI智能问答处理")
        print("🌐 **HTTP请求**: 网络搜索功能")
        print("📄 **文本处理**: 结果格式化和模板转换")
        print("✅ **结束节点**: 输出最终处理结果")
        
        print("\n🧪 测试用例:")
        print("=" * 40)
        print("1. **AI问答测试**:")
        print("   - 问题: '什么是人工智能？'")
        print("   - 类型: 选择 'AI问答'")
        print("   - 预期: GPT生成的AI相关回答")
        
        print("\n2. **网络搜索测试**:")
        print("   - 问题: '今天的天气如何？'")
        print("   - 类型: 选择 '网络搜索'")
        print("   - 预期: 基于搜索API的结果")
        
        print("\n3. **文本处理测试**:")
        print("   - 问题: '处理这段文本'")
        print("   - 类型: 选择 '文本处理'")
        print("   - 预期: 格式化的文本输出")
        
        print("\n🎯 现在请测试:")
        print("1. 刷新浏览器 http://localhost:8090")
        print("2. 查找 '综合智能助手' 应用")
        print("3. 进入工作流编辑器查看节点连接")
        print("4. 点击 '发布' 按钮发布工作流")
        print("5. 在 '概览' 页面测试不同的输入")
        
        print(f"\n📊 工作流统计:")
        print(f"- 节点数量: 6个")
        print(f"- 连接数量: 6条")
        print(f"- 功能覆盖: AI问答、网络搜索、条件分支、文本处理")

if __name__ == "__main__":
    main()
