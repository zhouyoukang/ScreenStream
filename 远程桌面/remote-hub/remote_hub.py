"""
道·远程中枢 Python SDK v1.0
==============================
让任何Agent/脚本一行代码调用远程中枢能力。

用法:
    from remote_hub import RemoteHub
    hub = RemoteHub()                          # 自动读取secrets.env
    hub.exec("Get-Date")                       # 在选中Agent上执行
    hub.broadcast("$env:COMPUTERNAME")          # 在所有Agent上执行
    hub.health()                               # 健康检查(无需认证)
    hub.agents()                               # 列出所有Agent
    hub.select("ZHOUMAC")                      # 切换Agent
    hub.sysinfo()                              # 获取系统信息
    hub.diagnose()                             # 自动诊断(17步)
    hub.say("消息")                            # 发送消息到浏览器
"""

import json
import os
import urllib.request
import urllib.error


class RemoteHub:
    """道·远程中枢 SDK — 远程电脑的五感延伸"""

    def __init__(self, base_url=None, password=None, token=None):
        """
        初始化远程中枢连接。
        优先级: 参数 > 环境变量 > secrets.env > 默认值
        """
        self._base_url = base_url or os.environ.get('REMOTE_HUB_URL')
        self._password = password or os.environ.get('REMOTE_HUB_PASSWORD')
        self._token = token

        if not self._base_url or not self._password:
            self._load_secrets()

        if not self._base_url:
            self._base_url = 'https://aiotvr.xyz/agent'

        self._base_url = self._base_url.rstrip('/')

    def _load_secrets(self):
        """从secrets.env或.env加载凭据"""
        for env_path in [
            os.path.join(os.path.dirname(__file__), '.env'),
            os.path.join(os.path.dirname(__file__), '..', '..', 'secrets.env'),
        ]:
            if os.path.exists(env_path):
                with open(env_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if '=' in line and not line.startswith('#'):
                            k, v = line.split('=', 1)
                            k, v = k.strip(), v.strip()
                            if k == 'AUTH_PASSWORD' and not self._password:
                                self._password = v
                            elif k == 'PUBLIC_URL' and not self._base_url:
                                url = v
                                proto = 'https' if 'aiotvr.xyz' in url else 'http'
                                self._base_url = f'{proto}://{url}'

    def _ensure_token(self):
        """确保有有效的认证token"""
        if self._token:
            return
        if not self._password:
            raise RuntimeError('未设置密码: 传入password参数或设置REMOTE_HUB_PASSWORD环境变量')
        r = self._post('/login', {'password': self._password}, auth=False)
        if r.get('ok'):
            self._token = r['token']
        else:
            raise RuntimeError(f'登录失败: {r.get("error", "unknown")}')

    def _request(self, method, path, data=None, auth=True, timeout=30):
        """发送HTTP请求"""
        url = self._base_url + path
        headers = {'Content-Type': 'application/json'}
        if auth:
            self._ensure_token()
            headers['Authorization'] = f'Bearer {self._token}'

        body = json.dumps(data).encode('utf-8') if data else None
        req = urllib.request.Request(url, data=body, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            try:
                err = json.loads(e.read().decode('utf-8'))
            except Exception:
                err = {'error': str(e)}
            if e.code == 401 and auth:
                self._token = None
                self._ensure_token()
                headers['Authorization'] = f'Bearer {self._token}'
                req = urllib.request.Request(url, data=body, headers=headers, method=method)
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return json.loads(resp.read().decode('utf-8'))
            return err
        except urllib.error.URLError as e:
            return {'error': f'连接失败: {e.reason}'}

    def _get(self, path, auth=True, timeout=30):
        return self._request('GET', path, auth=auth, timeout=timeout)

    def _post(self, path, data=None, auth=True, timeout=30):
        return self._request('POST', path, data=data, auth=auth, timeout=timeout)

    # ==================== 核心API ====================

    def health(self):
        """☰乾: 健康检查(无需认证)"""
        return self._get('/health', auth=False, timeout=10)

    def agents(self):
        """☱兑: 列出所有Agent"""
        return self._get('/brain/agents')

    def state(self):
        """获取系统完整状态"""
        return self._get('/brain/state')

    def select(self, agent_id):
        """切换当前操作的Agent"""
        return self._post('/brain/select', {'id': agent_id})

    def exec(self, cmd, timeout=30000, agent_id=None):
        """
        ☳震: 在远程Agent上执行PowerShell命令
        返回: {"ok": bool, "output": str, "ms": int}
        """
        if agent_id:
            self.select(agent_id)
        r = self._post('/brain/exec', {'cmd': cmd, 'timeout': timeout},
                        timeout=max(timeout // 1000 + 10, 30))
        return r

    def broadcast(self, cmd, timeout=30000):
        """
        ☱兑: 在所有Agent上同时执行命令
        返回: {"ok": bool, "count": int, "results": [...]}
        """
        return self._post('/brain/broadcast', {'cmd': cmd, 'timeout': timeout},
                          timeout=max(timeout // 1000 + 10, 30))

    def sysinfo(self):
        """获取当前Agent的系统信息"""
        return self._post('/brain/sysinfo', {}, timeout=15)

    def diagnose(self):
        """☵坎: 自动诊断(17步)"""
        return self._post('/brain/auto', {}, timeout=120)

    def say(self, text, level='system'):
        """发送消息到浏览器(Sense)"""
        return self._post('/brain/say', {'text': text, 'level': level})

    def terminal(self, n=20):
        """获取最近的命令历史"""
        return self._get(f'/brain/terminal?n={n}')

    def messages(self, clear=False):
        """获取用户消息"""
        return self._get(f'/brain/messages?clear={"true" if clear else "false"}')

    # ==================== 便捷方法 ====================

    def hostname(self, agent_id=None):
        """获取Agent主机名"""
        r = self.exec('$env:COMPUTERNAME', agent_id=agent_id)
        return r.get('output', '').strip() if r.get('ok') else None

    def ram_free(self, agent_id=None):
        """获取空闲内存(GB)"""
        r = self.exec('[math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB,1)', agent_id=agent_id)
        try:
            return float(r.get('output', '0').strip()) if r.get('ok') else None
        except ValueError:
            return None

    def disk_free(self, drive='C:', agent_id=None):
        """获取磁盘空闲空间(GB)"""
        r = self.exec(f'[math]::Round((Get-CimInstance Win32_LogicalDisk -Filter "DeviceID=\'{drive}\'").FreeSpace/1GB,1)', agent_id=agent_id)
        try:
            return float(r.get('output', '0').strip()) if r.get('ok') else None
        except ValueError:
            return None

    def processes(self, name=None, agent_id=None):
        """列出进程"""
        cmd = f'Get-Process {name} -EA SilentlyContinue | Select Name,Id,@{{N="MB";E={{[math]::Round($_.WS/1MB)}}}} | ConvertTo-Json -Compress' if name else 'Get-Process | Measure-Object | Select -Expand Count'
        return self.exec(cmd, agent_id=agent_id)

    def is_alive(self):
        """检查远程中枢是否可达"""
        try:
            r = self.health()
            return r.get('status') == 'ok'
        except Exception:
            return False


# ==================== CLI ====================
if __name__ == '__main__':
    import sys
    hub = RemoteHub()

    if len(sys.argv) < 2:
        print('用法: python remote_hub.py <command> [args]')
        print('  health          - 健康检查')
        print('  agents          - 列出Agent')
        print('  exec <cmd>      - 执行命令')
        print('  broadcast <cmd> - 广播执行')
        print('  select <id>     - 切换Agent')
        print('  sysinfo         - 系统信息')
        print('  diagnose        - 自动诊断')
        print('  say <msg>       - 发送消息')
        sys.exit(0)

    cmd = sys.argv[1]
    arg = ' '.join(sys.argv[2:])

    if cmd == 'health':
        print(json.dumps(hub.health(), indent=2, ensure_ascii=False))
    elif cmd == 'agents':
        print(json.dumps(hub.agents(), indent=2, ensure_ascii=False))
    elif cmd == 'exec':
        print(json.dumps(hub.exec(arg), indent=2, ensure_ascii=False))
    elif cmd == 'broadcast':
        print(json.dumps(hub.broadcast(arg), indent=2, ensure_ascii=False))
    elif cmd == 'select':
        print(json.dumps(hub.select(arg), indent=2, ensure_ascii=False))
    elif cmd == 'sysinfo':
        print(json.dumps(hub.sysinfo(), indent=2, ensure_ascii=False))
    elif cmd == 'diagnose':
        print(json.dumps(hub.diagnose(), indent=2, ensure_ascii=False))
    elif cmd == 'say':
        print(json.dumps(hub.say(arg), indent=2, ensure_ascii=False))
    else:
        print(f'未知命令: {cmd}')
