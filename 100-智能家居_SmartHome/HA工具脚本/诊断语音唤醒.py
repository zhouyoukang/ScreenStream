#!/usr/bin/env python3
"""
语音唤醒系统诊断工具
检查 Wyoming 服务连接状态、HA 集成配置和管道配置
"""
import socket
import json
import os
import subprocess

# 尝试导入 requests，如果没有则使用 urllib
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    import urllib.request
    import urllib.error

# 配置
HA_URL = "http://localhost:8123"
HA_TOKEN_FILE = os.path.join(os.path.dirname(__file__), "..", "ha_token.txt")
PIPELINE_FILE = os.path.join(os.path.dirname(__file__), "..", "config", ".storage", "assist_pipeline.pipelines")

# Wyoming 服务端点
WYOMING_SERVICES = {
    "Whisper STT (主)": ("192.168.31.141", 10300),
    "Whisper STT (备)": ("192.168.31.141", 10310),
    "OpenWakeWord (1)": ("192.168.31.141", 10400),
    "OpenWakeWord (2)": ("192.168.31.141", 10443),
    "Piper TTS": ("192.168.31.141", 10200),
}

def check_port(host, port, timeout=3):
    """检查端口是否可达"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception as e:
        return False

def get_ha_token():
    """获取 HA Token"""
    try:
        with open(HA_TOKEN_FILE, 'r') as f:
            return f.read().strip()
    except:
        return None

def http_get(url, headers=None, timeout=10):
    """统一的 HTTP GET 请求，兼容有无 requests 库"""
    if HAS_REQUESTS:
        resp = requests.get(url, headers=headers, timeout=timeout)
        return resp.status_code, resp.json() if resp.status_code == 200 else None
    else:
        req = urllib.request.Request(url, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            return e.code, None

def check_ha_entities(token):
    """检查 HA 中的语音相关实体"""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    entities = {
        "stt": [],
        "tts": [],
        "wake_word": [],
        "assist_pipeline": []
    }
    
    try:
        status_code, states = http_get(f"{HA_URL}/api/states", headers=headers)
        if status_code == 200 and states:
            for state in states:
                entity_id = state.get("entity_id", "")
                if entity_id.startswith("stt."):
                    entities["stt"].append({
                        "entity_id": entity_id,
                        "state": state.get("state"),
                        "friendly_name": state.get("attributes", {}).get("friendly_name")
                    })
                elif entity_id.startswith("tts."):
                    entities["tts"].append({
                        "entity_id": entity_id,
                        "state": state.get("state")
                    })
                elif entity_id.startswith("wake_word."):
                    entities["wake_word"].append({
                        "entity_id": entity_id,
                        "state": state.get("state"),
                        "friendly_name": state.get("attributes", {}).get("friendly_name")
                    })
        return entities
    except Exception as e:
        print(f"⚠️ 无法连接 HA API: {e}")
        return entities

def check_wyoming_integrations(token):
    """检查 Wyoming 集成配置"""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        status_code, entries = http_get(f"{HA_URL}/api/config/config_entries/entry", headers=headers)
        if status_code == 200 and entries:
            wyoming_entries = [e for e in entries if e.get("domain") == "wyoming"]
            return wyoming_entries
    except:
        pass
    return []

def check_pipeline_config():
    """检查管道配置，找出有唤醒词但没有 STT 的管道"""
    issues = []
    pipelines_with_wake = []
    
    try:
        with open(PIPELINE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        for pipeline in data.get("data", {}).get("items", []):
            name = pipeline.get("name", "Unknown")
            wake_word = pipeline.get("wake_word_entity")
            wake_word_id = pipeline.get("wake_word_id")
            stt_engine = pipeline.get("stt_engine")
            
            if wake_word:
                pipelines_with_wake.append({
                    "name": name,
                    "wake_word_id": wake_word_id,
                    "stt_engine": stt_engine
                })
                
                if not stt_engine:
                    issues.append(f"❌ 管道 '{name}' 有唤醒词但没有 STT 引擎！")
        
        return pipelines_with_wake, issues
    except FileNotFoundError:
        return [], ["⚠️ 未找到管道配置文件"]
    except Exception as e:
        return [], [f"⚠️ 读取管道配置失败: {e}"]

def check_docker_containers():
    """检查 Docker 容器状态"""
    containers = {}
    try:
        result = subprocess.run(
            ['C:\\Program Files\\Docker\\Docker\\resources\\bin\\docker.exe', 'ps', '-a', 
             '--filter', 'name=romantic_colden',
             '--filter', 'name=kind_knuth', 
             '--filter', 'name=custom_wake',
             '--filter', 'name=wake_zh',
             '--filter', 'name=vibrant_hamilton',
             '--format', '{{.Names}}|{{.Status}}'],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split('\n'):
                if '|' in line:
                    name, status = line.split('|', 1)
                    is_running = 'Up' in status
                    containers[name] = {"status": status, "running": is_running}
    except Exception as e:
        print(f"  ⚠️ 无法检查 Docker: {e}")
    return containers

def main():
    print("=" * 60)
    print("  🎤 语音唤醒系统诊断工具 v2.0")
    print("=" * 60)
    print()
    
    all_issues = []
    
    # 0. 检查 Docker 容器状态
    print("🐳 检查 Docker 容器状态:")
    print("-" * 40)
    containers = check_docker_containers()
    if containers:
        for name, info in containers.items():
            icon = "✅" if info["running"] else "❌"
            print(f"  {icon} {name}: {info['status']}")
            if not info["running"]:
                all_issues.append(f"容器 {name} 未运行")
    else:
        print("  ⚠️ 无法获取容器状态")
    print()
    
    # 1. 检查 Wyoming 服务端口
    print("📡 检查 Wyoming 服务连接状态:")
    print("-" * 40)
    
    all_services_ok = True
    for name, (host, port) in WYOMING_SERVICES.items():
        is_open = check_port(host, port)
        status = "✅ 可达" if is_open else "❌ 不可达"
        if not is_open:
            all_services_ok = False
            all_issues.append(f"{name} ({host}:{port}) 不可达")
        print(f"  {name}: {host}:{port} - {status}")
    
    print()
    
    # 2. 检查管道配置
    print("🔧 检查管道配置:")
    print("-" * 40)
    pipelines, pipeline_issues = check_pipeline_config()
    all_issues.extend(pipeline_issues)
    
    print(f"  配置了唤醒词的管道: {len(pipelines)} 个")
    for p in pipelines:
        stt_status = "✅" if p["stt_engine"] else "❌ 无STT"
        print(f"    • {p['name']}: {p['wake_word_id']} - {stt_status}")
    
    if pipeline_issues:
        for issue in pipeline_issues:
            print(f"  {issue}")
    print()
    
    # 3. 检查 HA 实体
    print("🏠 检查 Home Assistant 实体:")
    print("-" * 40)
    
    token = get_ha_token()
    if not token:
        print("  ⚠️ 未找到 HA Token，跳过 API 检查")
        print(f"  请在 {HA_TOKEN_FILE} 中配置 Token")
    else:
        entities = check_ha_entities(token)
        
        print(f"\n  📢 STT (语音识别) 实体: {len(entities['stt'])} 个")
        for e in entities['stt']:
            state_icon = "✅" if e['state'] != 'unavailable' else "❌"
            print(f"    {state_icon} {e['entity_id']} - {e.get('friendly_name', 'N/A')}")
        
        if not entities['stt']:
            print("    ⚠️ 没有找到 STT 实体！需要添加 Wyoming Whisper 集成")
        
        print(f"\n  🔔 唤醒词实体: {len(entities['wake_word'])} 个")
        for e in entities['wake_word']:
            state_icon = "✅" if e['state'] != 'unavailable' else "❌"
            print(f"    {state_icon} {e['entity_id']} - {e.get('friendly_name', 'N/A')}")
        
        print(f"\n  🔊 TTS (语音合成) 实体: {len(entities['tts'])} 个")
        for e in entities['tts'][:5]:  # 只显示前5个
            print(f"    • {e['entity_id']}")
        if len(entities['tts']) > 5:
            print(f"    ... 还有 {len(entities['tts']) - 5} 个")
        
        # 检查 Wyoming 集成
        print(f"\n  🔌 Wyoming 集成配置:")
        wyoming_entries = check_wyoming_integrations(token)
        if wyoming_entries:
            for entry in wyoming_entries:
                title = entry.get("title", "Unknown")
                host = entry.get("data", {}).get("host", "N/A")
                port = entry.get("data", {}).get("port", "N/A")
                print(f"    • {title}: {host}:{port}")
        else:
            print("    ⚠️ 未找到 Wyoming 集成，请手动添加")
    
    print()
    print("=" * 60)
    print("  📋 诊断结论")
    print("=" * 60)
    
    # 汇总所有问题
    if all_issues:
        print("\n发现以下问题:\n")
        for i, issue in enumerate(all_issues, 1):
            print(f"  {i}. {issue}")
        
        print("\n" + "=" * 60)
        print("  🔧 修复建议")
        print("=" * 60)
        
        # 提供修复建议
        has_container_issue = any("容器" in i for i in all_issues)
        has_port_issue = any("不可达" in i for i in all_issues)
        
        if has_container_issue or has_port_issue:
            print("\n  1. 运行启动脚本:")
            print("     D:\\homeassistant\\🔧_工具脚本\\启动语音唤醒服务.bat")
        
        if any("STT" in i for i in all_issues):
            print("\n  2. 修复管道配置:")
            print("     在 HA 中: 设置 → 语音助手 → 编辑管道 → 添加语音识别引擎")
        
        if any("实体" in i.lower() for i in all_issues):
            print("\n  3. 添加 Wyoming 集成:")
            print("     HA: 设置 → 设备与服务 → 添加集成 → Wyoming")
            print("     Whisper: 192.168.31.141:10300")
    else:
        print("\n✅ 所有服务正常运行！")
        print("\n如果语音唤醒仍不工作，请检查:")
        print("  1. 麦克风设备是否正常工作")
        print("  2. 在 HA 中选择了正确的语音助手管道")
        print("  3. 尝试重启 Home Assistant")
    
    print()
    input("按 Enter 键退出...")

if __name__ == "__main__":
    main()
