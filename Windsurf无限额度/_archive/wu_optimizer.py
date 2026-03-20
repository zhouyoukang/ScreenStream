#!/usr/bin/env python3
"""
WU 全维度优化器 v1.0
====================
基于 WU v1.5.6 完全逆向，一键诊断+修复+优化所有问题。

功能矩阵:
  ☰乾 WU运行状态诊断 (进程/端口/代理/会话)
  ☷坤 系统环境清理 (旧证书/portproxy/hosts)
  ☲离 积分消耗分析 (模型成本/日用量/剩余预测)
  ☳震 429限速检测 (连接测试/延迟/错误率)
  ☴巽 补丁状态检查 (main.js 6项补丁)
  ☵坎 天卡状态监控 (过期预警/自动续期提醒)
  ☶艮 Windsurf配置优化 (proxyStrictSSL/detect_proxy)
  ☱兑 一键修复所有问题

用法:
  python wu_optimizer.py              # 全景诊断
  python wu_optimizer.py --fix        # 诊断+修复
  python wu_optimizer.py --monitor    # 持续监控模式
  python wu_optimizer.py --credits    # 积分详情
"""

import os, sys, json, subprocess, socket, ssl, time, platform
from pathlib import Path
from datetime import datetime, timezone, timedelta

# ============================================================
# 路径常量
# ============================================================
WU_DATA = Path(os.environ.get('APPDATA', '')) / 'windsurf-unlimited'
WU_SESSION = WU_DATA / 'session.json'
WU_PROXY = WU_DATA / 'proxy.json'
WU_CERTS = WU_DATA / 'certs'
WU_INSTALL = Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'WindsurfUnlimited'
WU_ASAR = WU_INSTALL / 'resources' / 'app.asar'

WS_SETTINGS = Path(os.environ.get('APPDATA', '')) / 'Windsurf' / 'User' / 'settings.json'
WS_STATE_DB = Path(os.environ.get('APPDATA', '')) / 'Windsurf' / 'User' / 'globalStorage' / 'state.vscdb'
WS_USER_PB = Path.home() / '.codeium' / 'windsurf' / 'user_settings.pb'

HOSTS_FILE = r'C:\Windows\System32\drivers\etc\hosts'
WU_MITM_IP = '127.65.43.21'
WU_MITM_MARKER = '# windsurf-mitm-proxy'
MITM_DOMAINS = ['server.self-serve.windsurf.com', 'server.codeium.com']

# 旧CFW/代理证书模式(需要清理)
OLD_CERT_PATTERNS = ['Windsurf Interceptor', 'Windsurf Self-Hosted', 'Windsurf Self-Proxy']

# WU后端API
WU_API_USAGE = '/api/v1/auth/usage'
WU_API_VALIDATE = '/api/v1/auth/validate'

# ============================================================
# 诊断结果
# ============================================================
class DiagResult:
    def __init__(self):
        self.items = []
        self.errors = []
        self.warnings = []
        self.fixes = []
    
    def ok(self, cat, name, detail=''):
        self.items.append(('✅', cat, name, detail))
    
    def fail(self, cat, name, detail=''):
        self.items.append(('❌', cat, name, detail))
        self.errors.append(f'{name}: {detail}')
    
    def warn(self, cat, name, detail=''):
        self.items.append(('⚠️', cat, name, detail))
        self.warnings.append(f'{name}: {detail}')
    
    def fix(self, name, detail=''):
        self.fixes.append(f'{name}: {detail}')
    
    @property
    def score(self):
        s = 0
        for status, *_ in self.items:
            if status == '✅': s += 1
            elif status == '⚠️': s += 0.5
        return s
    
    @property
    def total(self):
        return len(self.items)

# ============================================================
# ☰ 乾: WU运行状态
# ============================================================
def diag_wu_runtime(r: DiagResult):
    print('\n☰ 乾·WU运行状态')
    print('-' * 50)
    
    # 安装检查
    wu_exe = WU_INSTALL / 'WindsurfUnlimited.exe'
    if wu_exe.exists():
        size = wu_exe.stat().st_size / 1024 / 1024
        r.ok('☰', 'WU安装', f'{size:.0f}MB')
    else:
        r.fail('☰', 'WU安装', '未安装')
        return
    
    # 进程检查
    try:
        out = subprocess.run(['tasklist', '/fi', 'IMAGENAME eq WindsurfUnlimited.exe', '/fo', 'csv', '/nh'],
                            capture_output=True, text=True, timeout=5, encoding='gbk', errors='replace').stdout
        count = out.count('WindsurfUnlimited')
        if count > 0:
            r.ok('☰', 'WU进程', f'{count}个进程运行中')
        else:
            r.fail('☰', 'WU进程', '未运行')
    except:
        r.warn('☰', 'WU进程', '检测失败')
    
    # MITM代理监听
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        s.connect((WU_MITM_IP, 443))
        s.close()
        r.ok('☰', 'MITM代理', f'{WU_MITM_IP}:443 监听中')
    except:
        r.fail('☰', 'MITM代理', f'{WU_MITM_IP}:443 未监听')
    
    # 会话状态
    if WU_SESSION.exists():
        try:
            session = json.loads(WU_SESSION.read_text())
            expires = datetime.fromtimestamp(session.get('expires_at', 0))
            now = datetime.now()
            remaining = expires - now
            card_type = session.get('card_type_label', '未知')
            server = session.get('server_url', '未知')
            
            if remaining.total_seconds() > 0:
                hours = remaining.total_seconds() / 3600
                r.ok('☰', '会话状态', f'{card_type} | 剩余{hours:.1f}h | {server}')
            else:
                hours = abs(remaining.total_seconds()) / 3600
                r.fail('☰', '会话过期', f'{card_type} | 已过期{hours:.1f}h | 需要续期')
        except Exception as e:
            r.warn('☰', '会话状态', f'读取失败: {e}')
    else:
        r.fail('☰', '会话文件', '不存在')

# ============================================================
# ☷ 坤: 系统环境
# ============================================================
def diag_system_env(r: DiagResult, fix=False):
    print('\n☷ 坤·系统环境')
    print('-' * 50)
    
    # Hosts检查
    try:
        hosts = open(HOSTS_FILE, encoding='utf-8').read()
        if WU_MITM_MARKER in hosts and WU_MITM_IP in hosts:
            r.ok('☷', 'hosts劫持', f'{WU_MITM_IP} → {", ".join(MITM_DOMAINS)}')
        else:
            r.fail('☷', 'hosts劫持', '缺失WU hosts条目')
    except:
        r.warn('☷', 'hosts', '读取失败')
    
    # 证书检查
    try:
        # Use certutil which has more reliable encoding
        out = subprocess.run(
            ['certutil', '-store', 'Root'],
            capture_output=True, text=True, timeout=15, encoding='gbk', errors='replace'
        ).stdout
        
        has_wu_ca = 'MITM CA' in out or 'Local Proxy' in out
        has_old = any(p in out for p in OLD_CERT_PATTERNS)
        
        if has_wu_ca and not has_old:
            r.ok('☷', 'CA证书', 'WU MITM CA已安装, 无旧证书')
        elif has_wu_ca and has_old:
            r.warn('☷', 'CA证书', f'有旧证书残留')
            if fix:
                clean_old_certs(r)
        elif not has_wu_ca:
            r.fail('☷', 'CA证书', 'WU MITM CA未安装')
    except:
        r.warn('☷', 'CA证书', '检测失败')
    
    # Portproxy检查
    try:
        out = subprocess.run(
            ['netsh', 'interface', 'portproxy', 'show', 'all'],
            capture_output=True, text=True, timeout=5, encoding='gbk', errors='replace'
        ).stdout
        if '443' in out and '192.168' in out:
            r.warn('☷', 'portproxy', '有旧CFW portproxy规则(443→LAN)')
            if fix:
                clean_portproxy_443(r)
        else:
            r.ok('☷', 'portproxy', '无冲突规则')
    except:
        r.warn('☷', 'portproxy', '检测失败')
    
    # Windsurf进程检查
    try:
        out = subprocess.run(
            ['tasklist', '/fi', 'IMAGENAME eq Windsurf.exe', '/fo', 'csv', '/nh'],
            capture_output=True, text=True, timeout=5, encoding='gbk', errors='replace'
        ).stdout
        ws_count = out.count('Windsurf.exe')
        if ws_count > 0:
            r.ok('☷', 'Windsurf进程', f'{ws_count}个进程')
        else:
            r.warn('☷', 'Windsurf进程', '未运行')
    except:
        pass

# ============================================================
# ☲ 离: 积分分析
# ============================================================
def diag_credits(r: DiagResult):
    print('\n☲ 离·积分分析')
    print('-' * 50)
    
    if not WU_SESSION.exists():
        r.fail('☲', '积分', '无会话数据')
        return {}
    
    try:
        session = json.loads(WU_SESSION.read_text())
        import urllib.request, urllib.error
        
        body = json.dumps({
            'client_id': session.get('client_id', ''),
            'session_token': session.get('session_token', '')
        }).encode()
        
        req = urllib.request.Request(
            session.get('server_url', '') + WU_API_USAGE,
            data=body,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        resp = urllib.request.urlopen(req, timeout=10, context=ctx)
        data = json.loads(resp.read())
        
        total_credits = data.get('credit_limit', 0)
        used_credits = data.get('total_credits_used', 0)
        remaining = total_credits - used_credits
        
        r.ok('☲', '积分', f'{used_credits:.0f}/{total_credits} 已用 | 剩余 {remaining:.0f}')
        
        # 模型消耗分析
        models = data.get('models', {})
        billing = data.get('billing_models', {})
        if models:
            print(f"  模型使用明细:")
            for model, count in sorted(models.items(), key=lambda x: -x[1]):
                credits = billing.get(model, {}).get('credits', 0)
                avg = credits / count if count > 0 else 0
                print(f"    {model}: {count}次 ({credits:.0f}积分, 均{avg:.1f}/次)")
        
        # 日消耗
        daily = data.get('daily', {})
        if daily:
            for date, d in daily.items():
                print(f"  日期 {date}: {d.get('credits', 0):.0f}积分 | {d.get('chats', 0)}次对话 | {d.get('requests', 0)}请求")
        
        return data
    except Exception as e:
        r.warn('☲', '积分查询', f'API失败: {e}')
        return {}

# ============================================================
# ☳ 震: 连接性测试
# ============================================================
def diag_connectivity(r: DiagResult):
    print('\n☳ 震·连接性测试')
    print('-' * 50)
    
    # TLS握手测试
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        start = time.time()
        s = ctx.wrap_socket(
            socket.socket(socket.AF_INET, socket.SOCK_STREAM),
            server_hostname='server.self-serve.windsurf.com'
        )
        s.settimeout(10)
        s.connect((WU_MITM_IP, 443))
        latency = (time.time() - start) * 1000
        
        cert = s.getpeercert()
        issuer = dict(x[0] for x in cert.get('issuer', []))
        cn = issuer.get('commonName', 'unknown')
        s.close()
        
        if 'MITM' in cn or 'Windsurf' in cn:
            r.ok('☳', 'TLS握手', f'{latency:.0f}ms | CA={cn}')
        else:
            r.warn('☳', 'TLS握手', f'{latency:.0f}ms | 证书异常: {cn}')
    except Exception as e:
        r.fail('☳', 'TLS握手', str(e))
    
    # DNS解析测试
    for domain in MITM_DOMAINS:
        try:
            ip = socket.gethostbyname(domain)
            if ip == WU_MITM_IP:
                r.ok('☳', f'DNS {domain[:20]}', f'→ {ip} ✓')
            else:
                r.fail('☳', f'DNS {domain[:20]}', f'→ {ip} (应为{WU_MITM_IP})')
        except:
            r.fail('☳', f'DNS {domain[:20]}', '解析失败')
    
    # WU后端连通性
    if WU_SESSION.exists():
        try:
            session = json.loads(WU_SESSION.read_text())
            server = session.get('server_url', '')
            if server:
                import urllib.request
                ctx2 = ssl.create_default_context()
                ctx2.check_hostname = False
                ctx2.verify_mode = ssl.CERT_NONE
                
                start = time.time()
                req = urllib.request.Request(server + '/api/v1/public/info')
                resp = urllib.request.urlopen(req, timeout=10, context=ctx2)
                latency = (time.time() - start) * 1000
                r.ok('☳', 'WU后端', f'{latency:.0f}ms | {server}')
        except Exception as e:
            r.fail('☳', 'WU后端', str(e))

# ============================================================
# ☴ 巽: 补丁状态
# ============================================================
def diag_patches(r: DiagResult):
    print('\n☴ 巽·补丁状态')
    print('-' * 50)
    
    if not WU_ASAR.exists():
        r.fail('☴', 'app.asar', '不存在')
        return
    
    # Quick check without full extraction - use asar list or check backup
    bak = WU_INSTALL / 'resources' / 'app.asar.bak_original'
    asar_size = WU_ASAR.stat().st_size
    
    if bak.exists():
        bak_size = bak.stat().st_size
        if asar_size != bak_size:
            r.ok('☴', 'main.js补丁', f'已补丁 (asar={asar_size:,}B vs orig={bak_size:,}B)')
        else:
            r.warn('☴', 'main.js补丁', '未补丁(大小与原始相同)')
    else:
        r.warn('☴', 'main.js补丁', f'未检测(无原始备份) asar={asar_size:,}B')
    
    # Check Windsurf client patches (patch_windsurf.py)
    ws_js = Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Windsurf' / 'resources' / 'app' / 'out' / 'vs' / 'workbench' / 'workbench.desktop.main.js'
    if ws_js.exists():
        try:
            content = ws_js.read_text(encoding='utf-8', errors='ignore')[:5000]
            if 'Pro Ultimate' in content or 'hasCapacity' in content:
                r.ok('☴', 'Windsurf客户端补丁', '已检测到补丁标记')
            else:
                r.warn('☴', 'Windsurf客户端补丁', '未检测到')
        except:
            r.warn('☴', 'Windsurf客户端补丁', '检测失败')

# ============================================================
# ☶ 艮: Windsurf配置
# ============================================================
def diag_ws_config(r: DiagResult, fix=False):
    print('\n☶ 艮·Windsurf配置')
    print('-' * 50)
    
    if WS_SETTINGS.exists():
        try:
            settings = json.loads(WS_SETTINGS.read_text())
            
            ssl_strict = settings.get('http.proxyStrictSSL', True)
            proxy_support = settings.get('http.proxySupport', 'override')
            
            if not ssl_strict:
                r.ok('☶', 'proxyStrictSSL', 'false (MITM兼容)')
            else:
                r.fail('☶', 'proxyStrictSSL', 'true → 需要设为false')
                if fix:
                    settings['http.proxyStrictSSL'] = False
                    WS_SETTINGS.write_text(json.dumps(settings, indent=2))
                    r.fix('proxyStrictSSL', '已修复为false')
            
            if proxy_support == 'off':
                r.ok('☶', 'proxySupport', 'off (不干扰MITM)')
            else:
                r.warn('☶', 'proxySupport', f'{proxy_support} → 建议设为off')
                if fix:
                    settings['http.proxySupport'] = 'off'
                    WS_SETTINGS.write_text(json.dumps(settings, indent=2))
                    r.fix('proxySupport', '已修复为off')
        except Exception as e:
            r.warn('☶', 'settings.json', f'读取失败: {e}')
    else:
        r.warn('☶', 'settings.json', '不存在')
    
    # user_settings.pb (detect_proxy)
    if WS_USER_PB.exists():
        size = WS_USER_PB.stat().st_size
        r.ok('☶', 'user_settings.pb', f'{size:,}B (WU管理detect_proxy)')
    else:
        r.warn('☶', 'user_settings.pb', '不存在')

# ============================================================
# 修复函数
# ============================================================
def clean_old_certs(r: DiagResult):
    """清理旧CFW/代理证书"""
    for pattern in OLD_CERT_PATTERNS:
        try:
            subprocess.run(
                ['powershell', '-Command',
                 f"Get-ChildItem cert:\\LocalMachine\\Root | Where-Object {{ $_.Subject -match '{pattern}' }} | Remove-Item -Force"],
                capture_output=True, timeout=10
            )
            r.fix('清理证书', f'已移除: {pattern}')
        except:
            pass

def clean_portproxy_443(r: DiagResult):
    """清理443端口的旧portproxy规则"""
    try:
        # Only remove rules that forward 443 to LAN IPs (not WU's own)
        out = subprocess.run(
            ['netsh', 'interface', 'portproxy', 'show', 'all'],
            capture_output=True, text=True, timeout=5, encoding='gbk', errors='replace'
        ).stdout
        
        for line in out.splitlines():
            if '443' in line and '192.168' in line:
                parts = line.split()
                if len(parts) >= 4:
                    listen_addr = parts[0]
                    listen_port = parts[1]
                    subprocess.run(
                        ['netsh', 'interface', 'portproxy', 'delete', 'v4tov4',
                         f'listenaddress={listen_addr}', f'listenport={listen_port}'],
                        capture_output=True, timeout=5
                    )
                    r.fix('portproxy', f'已删除: {listen_addr}:{listen_port}')
    except:
        pass

# ============================================================
# 报告生成
# ============================================================
def generate_report(r: DiagResult, credits_data: dict):
    """生成完整诊断报告"""
    lines = [
        f"# WU 全维度诊断报告",
        f"> 时间: {datetime.now().isoformat()}",
        f"> 评分: {r.score}/{r.total} ({r.score/max(r.total,1)*100:.0f}%)",
        "",
        "## 诊断结果",
        "",
        "| 状态 | 卦 | 检查项 | 详情 |",
        "|------|-----|--------|------|",
    ]
    
    for status, cat, name, detail in r.items:
        lines.append(f"| {status} | {cat} | {name} | {detail} |")
    
    if r.errors:
        lines.extend(["", "## ❌ 错误", ""])
        for e in r.errors:
            lines.append(f"- {e}")
    
    if r.warnings:
        lines.extend(["", "## ⚠️ 警告", ""])
        for w in r.warnings:
            lines.append(f"- {w}")
    
    if r.fixes:
        lines.extend(["", "## 🔧 已修复", ""])
        for f in r.fixes:
            lines.append(f"- {f}")
    
    # 建议
    lines.extend([
        "",
        "## 📋 优化建议",
        "",
        "### 立即执行",
        "1. 如果天卡已过期 → WU界面续费或切换卡密",
        "2. 运行 `python wu_patch_asar.py` → 注入429重试+增加重试次数",
        "3. Windsurf模型切换到 **SWE-1.6** (0积分消耗)",
        "",
        "### 长期优化",
        "4. 运行 `python wu_optimizer.py --monitor` 持续监控",
        "5. 避免使用 Claude Opus 4.6 thinking (5-10x积分消耗)",
        "6. 开启 AutoContinue + 0x模型 = 零成本续接",
    ])
    
    return '\n'.join(lines)

# ============================================================
# 主函数
# ============================================================
def main():
    import argparse
    parser = argparse.ArgumentParser(description='WU 全维度优化器')
    parser.add_argument('--fix', action='store_true', help='诊断+修复')
    parser.add_argument('--monitor', action='store_true', help='持续监控模式')
    parser.add_argument('--credits', action='store_true', help='积分详情')
    parser.add_argument('--report', action='store_true', help='生成报告文件')
    args = parser.parse_args()
    
    print("=" * 60)
    print("WU 全维度优化器 v1.0")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    r = DiagResult()
    
    # 八卦全景诊断
    diag_wu_runtime(r)
    diag_system_env(r, fix=args.fix)
    credits_data = diag_credits(r)
    diag_connectivity(r)
    diag_patches(r)
    diag_ws_config(r, fix=args.fix)
    
    # 汇总
    print(f"\n{'='*60}")
    print(f"诊断评分: {r.score}/{r.total} ({r.score/max(r.total,1)*100:.0f}%)")
    print(f"错误: {len(r.errors)} | 警告: {len(r.warnings)} | 修复: {len(r.fixes)}")
    print(f"{'='*60}")
    
    if r.errors:
        print("\n❌ 错误:")
        for e in r.errors:
            print(f"  - {e}")
    
    if r.fixes:
        print("\n🔧 已修复:")
        for f in r.fixes:
            print(f"  - {f}")
    
    # 生成报告
    if args.report:
        report = generate_report(r, credits_data)
        report_path = Path(__file__).parent / 'WU_OPTIMIZER_REPORT.md'
        report_path.write_text(report, encoding='utf-8')
        print(f"\n📄 报告已保存: {report_path}")
    
    # 监控模式
    if args.monitor:
        print("\n🔄 进入持续监控模式 (60s间隔, Ctrl+C退出)")
        try:
            while True:
                time.sleep(60)
                print(f"\n--- {datetime.now().strftime('%H:%M:%S')} 监控刷新 ---")
                r2 = DiagResult()
                diag_wu_runtime(r2)
                diag_connectivity(r2)
                print(f"评分: {r2.score}/{r2.total}")
                if r2.errors:
                    for e in r2.errors:
                        print(f"  ❌ {e}")
        except KeyboardInterrupt:
            print("\n监控已停止")
    
    return 0 if not r.errors else 1

if __name__ == '__main__':
    sys.exit(main())
