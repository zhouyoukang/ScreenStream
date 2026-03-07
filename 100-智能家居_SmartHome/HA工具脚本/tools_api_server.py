#!/usr/bin/env python3
# Home Assistant 工具库管理 API 服务器
# 功能：
# 1. 提供REST API接口执行PowerShell脚本
# 2. 将执行结果返回给HA仪表盘
# 3. 管理备份和工具库功能

import os
import json
import subprocess
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
import threading
import time
from datetime import datetime

app = Flask(__name__)
CORS(app)  # 启用跨域请求支持

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='tools_api_server.log'
)
logger = logging.getLogger('tools_api')

# 工作目录配置
WORKSPACE_PATH = os.path.dirname(os.path.abspath(__file__))
BACKUP_SCRIPTS_PATH = os.path.join(WORKSPACE_PATH, "HA备份")
TOOLS_PATH = os.path.join(WORKSPACE_PATH, "Homeassistant工具库")

# 存储任务状态
task_status = {}
task_results = {}
task_id_counter = 0

# 获取新的任务ID
def get_new_task_id():
    global task_id_counter
    task_id_counter += 1
    return f"task_{task_id_counter}"

@app.route('/api/status', methods=['GET'])
def get_status():
    """获取服务器状态"""
    return jsonify({
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "tasks": len(task_status)
    })

@app.route('/api/scripts', methods=['GET'])
def list_scripts():
    """列出可用的脚本"""
    scripts = []
    
    # 备份脚本
    if os.path.exists(BACKUP_SCRIPTS_PATH):
        for file in os.listdir(BACKUP_SCRIPTS_PATH):
            if file.endswith('.ps1'):
                scripts.append({
                    "id": file.replace('.ps1', ''),
                    "name": file.replace('.ps1', ''),
                    "path": os.path.join(BACKUP_SCRIPTS_PATH, file),
                    "category": "backup"
                })
    
    # 工具库脚本
    if os.path.exists(TOOLS_PATH):
        for root, _, files in os.walk(TOOLS_PATH):
            for file in files:
                if file.endswith('.ps1'):
                    rel_path = os.path.relpath(root, TOOLS_PATH)
                    category = rel_path if rel_path != '.' else "main"
                    scripts.append({
                        "id": os.path.join(category, file).replace('\\', '_').replace('.ps1', ''),
                        "name": file.replace('.ps1', ''),
                        "path": os.path.join(root, file),
                        "category": category
                    })
    
    return jsonify(scripts)

@app.route('/api/backups', methods=['GET'])
def list_backups():
    """列出备份文件夹中的内容"""
    backups = []
    backup_root = os.path.join(WORKSPACE_PATH, "HA备份")
    
    if os.path.exists(backup_root):
        for item in os.listdir(backup_root):
            item_path = os.path.join(backup_root, item)
            if os.path.isdir(item_path) and "备份" in item:
                # 获取文件夹信息
                try:
                    created_time = datetime.fromtimestamp(os.path.getctime(item_path))
                    size = sum(
                        os.path.getsize(os.path.join(dirpath, filename))
                        for dirpath, _, filenames in os.walk(item_path)
                        for filename in filenames
                    ) / (1024 * 1024)  # 转换为MB
                    
                    backups.append({
                        "name": item,
                        "path": item_path,
                        "created": created_time.isoformat(),
                        "size_mb": round(size, 2)
                    })
                except Exception as e:
                    logger.error(f"获取备份信息出错: {str(e)}")
    
    return jsonify(sorted(backups, key=lambda x: x["created"], reverse=True))

def run_powershell_script(script_path, task_id, params=None):
    """在单独的线程中执行PowerShell脚本"""
    task_status[task_id] = "running"
    task_results[task_id] = {"output": "", "start_time": datetime.now().isoformat()}
    
    try:
        cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File", script_path]
        if params:
            for key, value in params.items():
                cmd.append(f"-{key}")
                cmd.append(f"{value}")
        
        logger.info(f"执行脚本: {' '.join(cmd)}")
        
        # 执行PowerShell脚本并捕获输出
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8'
        )
        
        # 读取输出并更新任务结果
        stdout, stderr = process.communicate()
        
        task_results[task_id]["output"] = stdout
        task_results[task_id]["error"] = stderr
        task_results[task_id]["return_code"] = process.returncode
        task_results[task_id]["end_time"] = datetime.now().isoformat()
        
        if process.returncode == 0:
            task_status[task_id] = "completed"
        else:
            task_status[task_id] = "failed"
        
    except Exception as e:
        logger.error(f"脚本执行出错: {str(e)}")
        task_status[task_id] = "failed"
        task_results[task_id]["error"] = str(e)
        task_results[task_id]["end_time"] = datetime.now().isoformat()

@app.route('/api/run_script', methods=['POST'])
def execute_script():
    """执行PowerShell脚本"""
    data = request.json
    script_path = data.get("script_path")
    params = data.get("params", {})
    
    if not script_path or not os.path.exists(script_path):
        return jsonify({"error": "脚本不存在"}), 404
    
    task_id = get_new_task_id()
    thread = threading.Thread(
        target=run_powershell_script,
        args=(script_path, task_id, params)
    )
    thread.start()
    
    return jsonify({
        "task_id": task_id,
        "status": "started",
        "script": script_path
    })

@app.route('/api/task/<task_id>', methods=['GET'])
def get_task_status(task_id):
    """获取任务状态"""
    if task_id not in task_status:
        return jsonify({"error": "任务不存在"}), 404
        
    return jsonify({
        "task_id": task_id,
        "status": task_status[task_id],
        "results": task_results.get(task_id, {})
    })

@app.route('/api/restart_ha', methods=['POST'])
def restart_ha():
    """重启Home Assistant"""
    restart_script = os.path.join(WORKSPACE_PATH, "重启HA.ps1")
    
    if not os.path.exists(restart_script):
        return jsonify({"error": "重启脚本不存在"}), 404
    
    task_id = get_new_task_id()
    thread = threading.Thread(
        target=run_powershell_script,
        args=(restart_script, task_id, {})
    )
    thread.start()
    
    return jsonify({
        "task_id": task_id,
        "status": "started",
        "message": "正在重启Home Assistant..."
    })

@app.route('/api/system_info', methods=['GET'])
def get_system_info():
    """获取系统信息"""
    try:
        # 获取备份和日志统计
        backup_count = 0
        latest_backup = None
        backup_root = os.path.join(WORKSPACE_PATH, "HA备份")
        
        if os.path.exists(backup_root):
            backup_folders = [f for f in os.listdir(backup_root) if os.path.isdir(os.path.join(backup_root, f)) and "备份" in f]
            backup_count = len(backup_folders)
            
            if backup_folders:
                latest_backup = max(
                    [os.path.join(backup_root, f) for f in backup_folders],
                    key=os.path.getctime
                )
                latest_backup = os.path.basename(latest_backup)
        
        # 获取日志信息
        log_path = os.path.join(WORKSPACE_PATH, "config", "home-assistant.log")
        log_size = 0
        error_count = 0
        
        if os.path.exists(log_path):
            log_size = os.path.getsize(log_path) / (1024 * 1024)  # MB
            
            # 统计错误数量
            try:
                with open(log_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if "ERROR" in line:
                            error_count += 1
            except:
                pass
        
        return jsonify({
            "backup_count": backup_count,
            "latest_backup": latest_backup,
            "log_size_mb": round(log_size, 2),
            "error_count": error_count,
            "timestamp": datetime.now().isoformat()
        })
    
    except Exception as e:
        logger.error(f"获取系统信息出错: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000) 