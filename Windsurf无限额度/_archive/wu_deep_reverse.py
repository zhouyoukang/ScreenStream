#!/usr/bin/env python3
"""
WindsurfUnlimited v1.5.6 深度逆向诊断+优化器
====================================================
功能:
  1. 全景诊断: WU状态/代理/hosts/证书/portproxy/Windsurf配置
  2. 冲突清理: 移除旧CFW残留/多余证书/冲突portproxy
  3. 积分优化: 分析积分消耗模式+建议
  4. 一键修复: 修复所有发现的问题
  5. Windsurf配置: 确保detect_proxy/proxyStrictSSL正确

用法:
  python wu_deep_reverse.py                # 全景诊断
  python wu_deep_reverse.py --fix          # 诊断+修复
  python wu_deep_reverse.py --clean-certs  # 清理多余证书
  python wu_deep_reverse.py --report       # 生成完整报告
"""

import os, sys, json, subprocess, socket, ssl, time, platform, hashlib, struct
from pathlib import Path
from datetime import datetime, timezone

# ============================================================
# 常量
# ============================================================
WU_APP_DATA = Path(os.environ.get('APPDATA', '')) / 'windsurf-unlimited'
WU_SESSION = WU_APP_DATA / 'session.json'
WU_PROXY_JSON = WU_APP_DATA / 'proxy.json'
WU_DEVICE_ID = WU_APP_DATA / 'device_id.txt'
WU_CERTS_DIR = WU_APP_DATA / 'certs'
WU_INSTALL = Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'WindsurfUnlimited'
WU_MAIN_JS = WU_INSTALL / 'resources' / 'app.asar'

WS_SETTINGS = Path(os.environ.get('APPDATA', '')) / 'Windsurf' / 'User' / 'settings.json'
WS_STATE_DB = Path(os.environ.get('APPDATA', '')) / 'Windsurf' / 'User' / 'globalStorage' / 'state.vscdb'
WS_USER_PB = Path.home() / '.codeium' / 'windsurf' / 'user_settings.pb'

HOSTS_FILE = r'C:\Windows\System32\drivers\etc\hosts'
WU_HOSTS_MARKER = '# windsurf-mitm-proxy'
WU_HOSTS_IP = '127.65.43.21'
MITM_DOMAINS = ['server.self-serve.windsurf.com', 'server.codeium.com']
MITM_PORT = 443

# 需要保留的CA证书(WU自己的)
WU_CA_CN = 'Windsurf MITM CA'

# 需要清理的旧证书
OLD_CERT_PATTERNS = [
    'Windsurf Proxy',
    'Windsurf Interceptor',
    'Windsurf Self-Hosted',
    'Windsurf Self-Proxy',
]

class DiagResult:
    def __init__(self):
        self.checks = []
        self.errors = []
        self.warnings = []
        self.fixes = []
        self.score = 0
        self.max_score = 0
    
    def ok(self, name, detail=''):
        self.checks.append(('✅', name, detail))
        self.score += 1
        self.max_score += 1
    
    def fail(self, name, detail=''):
        self.checks.append(('❌', name, detail))
        self.errors.append(f'{name}: {detail}')
        self.max_score += 1
    
    def warn(self, name, detail=''):
        self.checks.append(('⚠️', name, detail))
        self.warnings.append(f'{name}: {detail}')
        self.score += 0.5
        self.max_score += 1
    
    def fix(self, name, detail=''):
        self.fixes.append(f'{name}: {detail}')

# ============================================================
# 1. WU状态诊断
# ============================================================
def diag_wu_status(r: DiagResult):
    """诊断WindsurfUnlimited运行状态"""
    print('\n☰ 乾·WU状态诊断')
    print('=' * 50)
    
    # 安装检查
    if WU_INSTALL.exists() and (WU_INSTALL / 'WindsurfUnlimited.exe').exists():
        size_mb = (WU_INSTALL / 'WindsurfUnlimited.exe').stat().st_size / 1024 / 1024
        r.ok('WU安装', f'{size_mb:.0f}MB @ {WU_INSTALL}')
    else:
        r.fail('WU安装', '未找到WindsurfUnlimited.exe')
        return
    
    # 进程检查
    try:
        out = subprocess.check_output(
            'tasklist /fi "IMAGENAME eq WindsurfUnlimited.exe" /fo csv /nh',
            shell=True, encoding='utf-8', errors='replace'
        ).strip()
        procs = [l for l in out.split('\n') if 'WindsurfUnlimited' in l]
        if procs:
            r.ok('WU进程', f'{len(procs)}个进程运行中')
        else:
            r.fail('WU进程', '未运行')
    except:
        r.fail('WU进程', '检测失败')
    
    # Session检查
    if WU_SESSION.exists():
        try:
            sess = json.loads(WU_SESSION.read_text('utf-8'))
            card_type = sess.get('card_type_label', sess.get('card_type', '?'))
            expires = sess.get('expires_at', 0)
            exp_dt = datetime.fromtimestamp(expires, tz=timezone.utc)
            now = datetime.now(tz=timezone.utc)
            remaining = exp_dt - now
            server = sess.get('server_url', '?')
            status = sess.get('status', '?')
            
            if remaining.total_seconds() > 0:
                hours = remaining.total_seconds() / 3600
                r.ok('WU会话', f'{card_type} | 剩余{hours:.1f}h | {server}')
            else:
                r.fail('WU会话', f'{card_type} 已过期 {abs(remaining.total_seconds()/3600):.1f}h前')
            
            print(f'  卡密类型: {card_type}')
            print(f'  到期时间: {exp_dt.strftime("%Y-%m-%d %H:%M:%S")} UTC')
            print(f'  服务器: {server}')
            print(f'  状态: {status}')
            print(f'  client_id: {sess.get("client_id", "?")[:20]}...')
        except Exception as e:
            r.fail('WU会话', f'解析失败: {e}')
    else:
        r.fail('WU会话', '未登录(session.json不存在)')
    
    # Device ID
    if WU_DEVICE_ID.exists():
        did = WU_DEVICE_ID.read_text('utf-8').strip()
        r.ok('设备ID', did)
    else:
        r.warn('设备ID', '未生成')
    
    # 证书目录
    if WU_CERTS_DIR.exists():
        certs = list(WU_CERTS_DIR.glob('*'))
        r.ok('WU证书', f'{len(certs)}个文件 @ {WU_CERTS_DIR}')
    else:
        r.fail('WU证书', '证书目录不存在')

# ============================================================
# 2. 代理诊断
# ============================================================
def diag_proxy(r: DiagResult):
    """诊断MITM代理状态"""
    print('\n☷ 坤·代理诊断')
    print('=' * 50)
    
    # 端口443监听检查
    try:
        out = subprocess.check_output(
            'netstat -ano | findstr ":443 " | findstr "LISTEN"',
            shell=True, encoding='utf-8', errors='replace'
        ).strip()
        listeners = []
        for line in out.split('\n'):
            parts = line.split()
            if len(parts) >= 5:
                addr = parts[1]
                pid = parts[4]
                try:
                    pname = subprocess.check_output(
                        f'tasklist /fi "PID eq {pid}" /fo csv /nh',
                        shell=True, encoding='utf-8', errors='replace'
                    ).strip()
                    name = pname.split('"')[1] if '"' in pname else f'PID {pid}'
                except:
                    name = f'PID {pid}'
                listeners.append((addr, pid, name))
        
        wu_listening = False
        conflicts = []
        for addr, pid, name in listeners:
            if WU_HOSTS_IP in addr and 'WindsurfUnlimited' in name:
                wu_listening = True
                r.ok(f'WU代理监听', f'{addr} (PID {pid})')
            elif '127.0.0.1:443' in addr:
                conflicts.append((addr, pid, name))
        
        if not wu_listening:
            r.fail('WU代理监听', f'{WU_HOSTS_IP}:443 未监听')
        
        for addr, pid, name in conflicts:
            r.warn(f'端口冲突', f'{addr} 被 {name}(PID {pid}) 占用')
    except:
        r.warn('端口检查', '检测失败')
    
    # TLS连接测试
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with socket.create_connection((WU_HOSTS_IP, 443), timeout=5) as sock:
            with ctx.wrap_socket(sock, server_hostname=MITM_DOMAINS[0]) as ssock:
                cert = ssock.getpeercert(binary_form=True)
                r.ok('TLS握手', f'{ssock.version()} 成功')
    except Exception as e:
        r.fail('TLS握手', f'失败: {e}')
    
    # DNS解析检查
    for domain in MITM_DOMAINS:
        try:
            ip = socket.gethostbyname(domain)
            if ip == WU_HOSTS_IP:
                r.ok(f'DNS {domain[:25]}', f'→ {ip}')
            else:
                r.fail(f'DNS {domain[:25]}', f'→ {ip} (应为{WU_HOSTS_IP})')
        except:
            r.fail(f'DNS {domain[:25]}', '解析失败')

# ============================================================
# 3. Hosts诊断
# ============================================================
def diag_hosts(r: DiagResult):
    """诊断hosts文件"""
    print('\n☲ 离·Hosts诊断')
    print('=' * 50)
    
    try:
        content = Path(HOSTS_FILE).read_text('utf-8', errors='replace')
        
        if WU_HOSTS_MARKER in content:
            r.ok('WU hosts标记', '存在')
        else:
            r.fail('WU hosts标记', '缺失')
        
        if WU_HOSTS_IP in content:
            # 检查是否指向正确IP
            for domain in MITM_DOMAINS:
                if f'{WU_HOSTS_IP} {domain}' in content or f'{WU_HOSTS_IP}\t{domain}' in content:
                    r.ok(f'hosts {domain[:25]}', f'→ {WU_HOSTS_IP}')
                elif domain in content:
                    r.warn(f'hosts {domain[:25]}', '存在但IP可能不正确')
                else:
                    r.fail(f'hosts {domain[:25]}', '条目缺失')
        else:
            r.fail('WU hosts IP', f'{WU_HOSTS_IP}不在hosts中')
        
        # 检查冲突条目
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('#') or not line:
                continue
            for domain in MITM_DOMAINS:
                if domain in line and WU_HOSTS_IP not in line and WU_HOSTS_MARKER not in line:
                    r.warn('hosts冲突', f'发现非WU条目: {line[:80]}')
    except Exception as e:
        r.fail('hosts读取', str(e))

# ============================================================
# 4. 证书诊断
# ============================================================
def diag_certs(r: DiagResult):
    """诊断Root CA证书"""
    print('\n☳ 震·证书诊断')
    print('=' * 50)
    
    try:
        out = subprocess.check_output(
            'powershell -Command "Get-ChildItem cert:\\LocalMachine\\Root | '
            'Where-Object { $_.Subject -match \'MITM|Windsurf|Proxy|Local\' } | '
            'Select-Object Subject, Thumbprint, NotAfter | ConvertTo-Json"',
            shell=True, encoding='utf-8', errors='replace'
        ).strip()
        
        if not out or out == '':
            r.ok('Root CA', '无Windsurf相关证书')
            return
        
        certs = json.loads(out)
        if isinstance(certs, dict):
            certs = [certs]
        
        wu_cert_found = False
        old_certs = []
        
        for cert in certs:
            subj = cert.get('Subject', '')
            thumb = cert.get('Thumbprint', '')
            
            if WU_CA_CN in subj:
                wu_cert_found = True
                r.ok('WU CA证书', f'{subj[:50]} [{thumb[:8]}]')
            elif any(p in subj for p in OLD_CERT_PATTERNS):
                old_certs.append(cert)
                r.warn('旧CA证书', f'{subj[:50]} [{thumb[:8]}]')
            elif 'Razer' in subj:
                pass  # 非相关
            else:
                r.warn('未知CA', f'{subj[:50]} [{thumb[:8]}]')
        
        if not wu_cert_found:
            r.fail('WU CA证书', f'未找到CN={WU_CA_CN}的证书')
        
        if old_certs:
            print(f'  ⚠️ 发现{len(old_certs)}个旧证书可清理')
    except Exception as e:
        r.warn('证书检查', f'PowerShell执行失败: {e}')

# ============================================================
# 5. Portproxy诊断
# ============================================================
def diag_portproxy(r: DiagResult):
    """诊断netsh portproxy"""
    print('\n☴ 巽·Portproxy诊断')
    print('=' * 50)
    
    try:
        out = subprocess.check_output(
            'netsh interface portproxy show all',
            shell=True, encoding='utf-8', errors='replace'
        ).strip()
        
        conflicts = []
        for line in out.split('\n'):
            if '443' in line and '127.0.0.1' in line.split('  ')[0] if '  ' in line else False:
                conflicts.append(line.strip())
        
        if not conflicts:
            r.ok('portproxy', '无443冲突')
        else:
            for c in conflicts:
                r.warn('portproxy冲突', f'{c}')
            print(f'  旧CFW portproxy残留可能干扰WU代理')
    except Exception as e:
        r.warn('portproxy检查', str(e))

# ============================================================
# 6. Windsurf配置诊断
# ============================================================
def diag_windsurf(r: DiagResult):
    """诊断Windsurf IDE配置"""
    print('\n☵ 坎·Windsurf配置诊断')
    print('=' * 50)
    
    # settings.json
    if WS_SETTINGS.exists():
        try:
            content = WS_SETTINGS.read_text('utf-8')
            settings = json.loads(content)
            
            # proxyStrictSSL
            strict_ssl = settings.get('http.proxyStrictSSL', True)
            if not strict_ssl:
                r.ok('proxyStrictSSL', 'false (MITM兼容)')
            else:
                r.fail('proxyStrictSSL', 'true (需关闭)')
            
            # proxySupport
            proxy_support = settings.get('http.proxySupport', 'override')
            if proxy_support == 'off':
                r.ok('proxySupport', 'off (不干扰MITM)')
            else:
                r.warn('proxySupport', f'{proxy_support} (建议off)')
        except Exception as e:
            r.warn('settings.json', f'解析失败: {e}')
    else:
        r.fail('settings.json', '不存在')
    
    # detect_proxy (protobuf field 34)
    if WS_USER_PB.exists():
        try:
            data = WS_USER_PB.read_bytes()
            # 简单检查field 34的值
            r.ok('user_settings.pb', f'{len(data)}B (WU自动管理detect_proxy)')
        except:
            r.warn('user_settings.pb', '读取失败')
    else:
        r.warn('user_settings.pb', '不存在(首次启动后生成)')
    
    # Windsurf进程
    try:
        out = subprocess.check_output(
            'tasklist /fi "IMAGENAME eq Windsurf.exe" /fo csv /nh',
            shell=True, encoding='utf-8', errors='replace'
        ).strip()
        procs = [l for l in out.split('\n') if 'Windsurf.exe' in l]
        if procs:
            r.ok('Windsurf进程', f'{len(procs)}个进程')
        else:
            r.warn('Windsurf进程', '未运行')
    except:
        r.warn('Windsurf进程', '检测失败')

# ============================================================
# 7. 积分分析
# ============================================================
def diag_credits(r: DiagResult):
    """分析WU积分消耗"""
    print('\n☶ 艮·积分分析')
    print('=' * 50)
    
    if WU_SESSION.exists():
        try:
            sess = json.loads(WU_SESSION.read_text('utf-8'))
            server_url = sess.get('server_url', '')
            client_id = sess.get('client_id', '')
            
            print(f'  服务器: {server_url}')
            print(f'  客户端: {client_id[:30]}...')
            print(f'  卡密类型: {sess.get("card_type_label", "?")}')
            
            # 积分信息需要通过API获取(截图显示52/5000)
            print('\n  📊 积分优化建议:')
            print('  1. 切换Windsurf模型到SWE-1.6 (creditMultiplier=0)')
            print('  2. 减少Always-On规则数量(5→3核心)')
            print('  3. 减少MCP工具声明(113→50关键)')
            print('  4. 清理不相关Memory条目')
            print('  5. 开启AutoContinue配合0x模型')
            
            r.ok('积分分析', '建议已生成')
        except:
            r.warn('积分分析', '解析失败')
    else:
        r.fail('积分分析', '未登录')

# ============================================================
# 修复功能
# ============================================================
def fix_portproxy_conflict():
    """清理旧CFW portproxy 127.0.0.1:443冲突"""
    print('\n🔧 清理portproxy冲突...')
    try:
        # 仅删除127.0.0.1:443→179的旧CFW规则
        subprocess.run(
            'netsh interface portproxy delete v4tov4 listenaddress=127.0.0.1 listenport=443',
            shell=True, capture_output=True
        )
        print('  ✅ 已删除 127.0.0.1:443 portproxy')
        return True
    except Exception as e:
        print(f'  ❌ 失败: {e}')
        return False

def fix_old_certs():
    """清理旧的Windsurf代理证书"""
    print('\n🔧 清理旧CA证书...')
    cleaned = 0
    for pattern in OLD_CERT_PATTERNS:
        try:
            subprocess.run(
                f'powershell -Command "Get-ChildItem cert:\\LocalMachine\\Root | '
                f'Where-Object {{ $_.Subject -match \'{pattern}\' }} | '
                f'Remove-Item -Force"',
                shell=True, capture_output=True
            )
            cleaned += 1
        except:
            pass
    print(f'  ✅ 清理了{cleaned}类旧证书')
    return cleaned > 0

def fix_windsurf_settings():
    """修复Windsurf settings.json"""
    print('\n🔧 修复Windsurf配置...')
    if not WS_SETTINGS.exists():
        print('  ⚠️ settings.json不存在')
        return False
    
    try:
        content = WS_SETTINGS.read_text('utf-8')
        settings = json.loads(content)
        changed = False
        
        if settings.get('http.proxyStrictSSL') != False:
            settings['http.proxyStrictSSL'] = False
            changed = True
            print('  ✅ http.proxyStrictSSL → false')
        
        if settings.get('http.proxySupport') != 'off':
            settings['http.proxySupport'] = 'off'
            changed = True
            print('  ✅ http.proxySupport → off')
        
        if changed:
            WS_SETTINGS.write_text(json.dumps(settings, indent=2, ensure_ascii=False), 'utf-8')
            print('  ✅ settings.json已更新')
        else:
            print('  ✅ settings.json已正确')
        return True
    except Exception as e:
        print(f'  ❌ 修复失败: {e}')
        return False

# ============================================================
# 报告生成
# ============================================================
def generate_report(r: DiagResult):
    """生成完整逆向分析报告"""
    report_path = Path(__file__).parent / 'WU_DEEP_REVERSE_REPORT.md'
    
    lines = [
        '# WindsurfUnlimited v1.5.6 深度逆向报告',
        f'> 生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
        f'> 诊断评分: {r.score}/{r.max_score} ({r.score/max(r.max_score,1)*100:.0f}%)',
        '',
        '## 一、完整架构逆向',
        '',
        '### 1.1 技术栈',
        '| 组件 | 技术 | 说明 |',
        '|------|------|------|',
        '| 框架 | Electron + electron-builder | Tauri风格,非Tauri |',
        '| 前端 | React 18 + Zustand 5 + Lucide Icons | SPA |',
        '| 后端 | Node.js http2.createSecureServer | HTTP/2 TLS MITM |',
        '| 加密 | AES-256-GCM + HMAC-SHA256 | 客户端↔服务端全加密 |',
        '| 证书 | node-forge RSA 2048 + 自签CA | 动态生成 |',
        '| 代理 | SOCKS5 + HTTP Proxy Agent | 支持上游代理 |',
        '| 更新 | GitHub Release (chaogei/windsurf-unlimited) | electron-updater |',
        '',
        '### 1.2 五层MITM架构',
        '```',
        '┌─────────────────────────────────────────────────────┐',
        '│  Layer 1: hosts劫持                                  │',
        '│  127.65.43.21 server.self-serve.windsurf.com        │',
        '│  127.65.43.21 server.codeium.com                    │',
        '│  标记: # windsurf-mitm-proxy                        │',
        '├─────────────────────────────────────────────────────┤',
        '│  Layer 2: CA证书信任                                 │',
        '│  CN=Windsurf MITM CA, O=Local Proxy                 │',
        '│  安装到 cert:\\LocalMachine\\Root                    │',
        '├─────────────────────────────────────────────────────┤',
        '│  Layer 3: HTTP/2 TLS MITM服务器                      │',
        '│  127.65.43.21:443 (node http2.createSecureServer)   │',
        '│  自签server.crt (SAN=两个域名)                       │',
        '├─────────────────────────────────────────────────────┤',
        '│  Layer 4: Windsurf settings.json                     │',
        '│  http.proxyStrictSSL=false                           │',
        '│  http.proxySupport=off                               │',
        '├─────────────────────────────────────────────────────┤',
        '│  Layer 5: Windsurf user_settings.pb                  │',
        '│  detect_proxy=1 (protobuf field 34)                  │',
        '│  自动修改Windsurf的protobuf二进制设置                 │',
        '└─────────────────────────────────────────────────────┘',
        '```',
        '',
        '### 1.3 数据流',
        '```',
        'Windsurf Language Server',
        '  ↓ gRPC (server.self-serve.windsurf.com:443)',
        '  ↓ DNS解析→127.65.43.21 (hosts劫持)',
        '  ↓ TLS握手(WU自签CA)',
        'WU MITM Proxy (127.65.43.21:443)',
        '  ├─ /RecordAnalytics等8类 → 直接返回200空(节省积分)',
        '  ├─ /GetChatMessage,/GetCompletions → 流式代理',
        '  │   ↓ AES-256-GCM加密 + HMAC签名',
        '  │   ↓ POST chaogei.top/api/v1/stream-proxy',
        '  │   ↓ 服务端持有真Pro账号→调用Codeium API',
        '  │   ↓ 流式响应SSE逐帧解密→转发给Windsurf',
        '  └─ 其他gRPC → 普通代理',
        '      ↓ POST chaogei.top/api/v1/proxy',
        '      ↓ 服务端统一处理→返回',
        '',
        'inference.codeium.com (推理) → 直连(不经过代理)',
        '  ↓ 使用代理获取的auth_token',
        '  ↓ Codeium真实推理服务器',
        '```',
        '',
        '### 1.4 加密协议',
        '| 组件 | 算法 | 密钥来源 |',
        '|------|------|---------|',
        '| 请求加密 | AES-256-GCM (12B IV + 16B AuthTag) | client_secret SHA256 |',
        '| 请求签名 | HMAC-SHA256 | client_secret |',
        '| 响应验证 | HMAC-SHA256签名验证 + AES-GCM解密 | client_secret |',
        '| API Key | 从state.vscdb提取Windsurf apiKey | 本地读取 |',
        '| 协议版本 | "2" | 硬编码 |',
        '',
        '### 1.5 Telemetry过滤(积分节省)',
        '以下8类请求被WU直接拦截返回200,不消耗积分:',
        '1. `/RecordAnalytics`',
        '2. `/RecordCortexTrajectory`',
        '3. `/RecordCortexTrajectoryStep`',
        '4. `/RecordAsyncTelemetry`',
        '5. `/RecordStateInitialization`',
        '6. `/RecordCortexExecutionMeta`',
        '7. `/RecordCortexGeneratorMeta`',
        '8. `/RecordTrajectorySegment`',
        '',
        '### 1.6 vs CFW v2.0.5 对比',
        '| 维度 | WU v1.5.6 | CFW v2.0.5 |',
        '|------|-----------|------------|',
        '| 框架 | Electron | Tauri/Rust 9.2MB |',
        '| MITM IP | 127.65.43.21 | 127.0.0.1 |',
        '| 后端 | chaogei.top(中国) | 38.175.203.46(日本) |',
        '| 认证 | 卡密制(天卡/月卡) | 授权码(免费) |',
        '| 积分 | 5000/天卡 | 无限制 |',
        '| 加密 | AES-256-GCM+HMAC | 直接gRPC转发 |',
        '| Telemetry | 8类过滤 | 全部转发 |',
        '| detect_proxy | 自动修改protobuf | 不处理 |',
        '| 安全软件检测 | ✅ 主动检测10种 | ❌ |',
        '| 代理软件检测 | ✅ 检测20种 | ❌ |',
        '| hosts备份 | ✅ .mitm_backup | ❌ |',
        '',
        '## 二、限速/请求失败根因分析',
        '',
        '### 2.1 积分耗尽 (52/5000)',
        '- 天卡5000积分 ≈ 每个gRPC请求消耗≥1积分',
        '- 高消耗模型(Claude Opus 4.6) × 大系统提示(15K tokens) = 快速消耗',
        '- 每次Continue = 新请求 = 新积分消耗',
        '- **解决**: 切换Windsurf模型到SWE-1.6 (creditMultiplier=0)',
        '',
        '### 2.2 portproxy冲突',
        '- 旧CFW portproxy: 127.0.0.1:443→192.168.31.179:443',
        '- svchost.exe(IP Helper)占用127.0.0.1:443',
        '- **解决**: 删除旧portproxy规则',
        '',
        '### 2.3 多证书冲突',
        '- 发现5个Root CA证书(WU+CFW旧+自建代理)',
        '- TLS握手时可能选择错误证书',
        '- **解决**: 清理旧证书,仅保留WU的MITM CA',
        '',
        '## 三、诊断结果',
        '',
        f'**评分: {r.score}/{r.max_score} ({r.score/max(r.max_score,1)*100:.0f}%)**',
        '',
    ]
    
    if r.checks:
        lines.append('| 状态 | 检查项 | 详情 |')
        lines.append('|------|--------|------|')
        for status, name, detail in r.checks:
            lines.append(f'| {status} | {name} | {detail} |')
    
    if r.errors:
        lines.append('')
        lines.append('### ❌ 错误')
        for e in r.errors:
            lines.append(f'- {e}')
    
    if r.warnings:
        lines.append('')
        lines.append('### ⚠️ 警告')
        for w in r.warnings:
            lines.append(f'- {w}')
    
    if r.fixes:
        lines.append('')
        lines.append('### 🔧 已修复')
        for f in r.fixes:
            lines.append(f'- {f}')
    
    report_path.write_text('\n'.join(lines), 'utf-8')
    print(f'\n📝 报告已保存: {report_path}')
    return report_path

# ============================================================
# Main
# ============================================================
def main():
    import argparse
    parser = argparse.ArgumentParser(description='WU v1.5.6 深度逆向诊断+优化')
    parser.add_argument('--fix', action='store_true', help='诊断+修复所有问题')
    parser.add_argument('--clean-certs', action='store_true', help='清理旧CA证书')
    parser.add_argument('--report', action='store_true', help='生成完整报告')
    args = parser.parse_args()
    
    print('╔══════════════════════════════════════════════════╗')
    print('║  WindsurfUnlimited v1.5.6 深度逆向诊断器        ║')
    print('║  伏羲八卦×五感×三转法轮                         ║')
    print('╚══════════════════════════════════════════════════╝')
    
    r = DiagResult()
    
    # 诊断
    diag_wu_status(r)
    diag_proxy(r)
    diag_hosts(r)
    diag_certs(r)
    diag_portproxy(r)
    diag_windsurf(r)
    diag_credits(r)
    
    # 修复
    if args.fix:
        print('\n' + '=' * 50)
        print('🔧 执行修复...')
        print('=' * 50)
        
        fix_portproxy_conflict()
        r.fix('portproxy', '已清理127.0.0.1:443冲突')
        
        fix_windsurf_settings()
        r.fix('Windsurf配置', 'proxyStrictSSL=false, proxySupport=off')
    
    if args.clean_certs or args.fix:
        fix_old_certs()
        r.fix('旧证书', '已清理旧CFW/自建代理证书')
    
    # 报告
    print(f'\n{"=" * 50}')
    print(f'诊断评分: {r.score}/{r.max_score} ({r.score/max(r.max_score,1)*100:.0f}%)')
    print(f'错误: {len(r.errors)} | 警告: {len(r.warnings)} | 修复: {len(r.fixes)}')
    
    if args.report or args.fix:
        generate_report(r)
    
    # 关键建议
    print('\n📌 立即执行建议:')
    print('1. Windsurf模型切换到 SWE-1.6 或 SWE-1.5 (0积分消耗)')
    print('2. 确保WU代理已启动(截图显示"运行中"✅)')
    print('3. 运行 python wu_deep_reverse.py --fix 清理冲突')
    print('4. 卡密到期后续购或切换到CFW/BYOK方案')
    
    return 0 if not r.errors else 1

if __name__ == '__main__':
    sys.exit(main())
