"""
道 — 智能体系仪表盘
启动: python AGI/dashboard-server.py          (前台+托盘)
      pythonw AGI/dashboard-server.py         (后台+托盘，无控制台)
      python AGI/dashboard-server.py --no-tray (纯HTTP，无托盘)
访问: http://localhost:9090
"""
import http.server, json, os, re, glob, socketserver, sys, threading, time, signal, webbrowser
from pathlib import Path
from urllib.parse import urlparse, parse_qs

PORT = 9090
PROJECT_ROOT = Path(__file__).parent.parent
WINDSURF_DIR = PROJECT_ROOT / '.windsurf'
GLOBAL_ROOT = Path.home() / '.codeium' / 'windsurf'

def safe_read(path, max_lines=500):
    try:
        text = Path(path).read_text(encoding='utf-8', errors='replace')
        lines = text.splitlines()
        return '\n'.join(lines[:max_lines]), len(lines)
    except Exception as e:
        return f"[Error: {e}]", 0

def list_files(directory, pattern='*', max_depth=2):
    results = []
    base = Path(directory)
    if not base.exists(): return results
    for p in sorted(base.rglob(pattern)):
        depth = len(p.relative_to(base).parts)
        if depth > max_depth: continue
        results.append({
            'path': str(p.relative_to(PROJECT_ROOT)),
            'name': p.name,
            'is_dir': p.is_dir(),
            'size': p.stat().st_size if p.is_file() else 0,
            'lines': sum(1 for _ in open(p, errors='replace')) if p.is_file() and p.suffix in ('.md','.json','.kt','.py','.html','.js','.css','.toml','.kts') else 0
        })
    return results

def get_zone0():
    data = {}
    # Global rules
    gr = GLOBAL_ROOT / 'memories' / 'global_rules.md'
    content, lines = safe_read(gr)
    data['global_rules'] = {'path': str(gr), 'exists': gr.exists(), 'lines': lines, 'content': content}
    # Global hooks
    gh = GLOBAL_ROOT / 'hooks.json'
    content, lines = safe_read(gh)
    data['global_hooks'] = {'path': str(gh), 'exists': gh.exists(), 'lines': lines, 'content': content}
    is_empty = '"hooks": {}' in content or '"hooks":{}' in content
    has_ps = 'powershell' in content.lower() or '.ps1' in content.lower()
    data['global_hooks']['safe'] = is_empty or (not has_ps)
    data['global_hooks']['empty'] = is_empty
    # MCP config
    mc = GLOBAL_ROOT / 'mcp_config.json'
    content, lines = safe_read(mc)
    data['mcp_config'] = {'path': str(mc), 'exists': mc.exists(), 'lines': lines, 'content': content}
    try:
        mcp_json = json.loads(content)
        servers = {}
        for name, cfg in mcp_json.get('mcpServers', {}).items():
            servers[name] = {'disabled': cfg.get('disabled', False), 'command': cfg.get('command', '')}
        data['mcp_config']['servers'] = servers
    except: data['mcp_config']['servers'] = {}
    # Global skills
    gs = GLOBAL_ROOT / 'skills'
    skills = []
    if gs.exists():
        for d in sorted(gs.iterdir()):
            if d.is_dir():
                skill_file = d / 'SKILL.md'
                skills.append({'name': d.name, 'has_skill_md': skill_file.exists(),
                              'lines': sum(1 for _ in open(skill_file, errors='replace')) if skill_file.exists() else 0})
    data['global_skills'] = {'path': str(gs), 'exists': gs.exists(), 'count': len(skills), 'skills': skills}
    return data

def get_zone1():
    data = {}
    # .windsurfrules
    wr = PROJECT_ROOT / '.windsurfrules'
    content, lines = safe_read(wr)
    data['windsurfrules'] = {'path': str(wr), 'exists': wr.exists(), 'lines': lines, 'content': content}
    # Rules
    rules_dir = WINDSURF_DIR / 'rules'
    rules = []
    if rules_dir.exists():
        for f in sorted(rules_dir.glob('*.md')):
            c, l = safe_read(f)
            # Detect trigger type
            trigger = 'always_on'
            if f.name in ('soul.md', 'execution-engine.md', 'project-structure.md'): trigger = 'always_on'
            elif f.name in ('kotlin-android.md', 'frontend-html.md'): trigger = 'glob'
            elif f.name == 'build-deploy.md': trigger = 'model'
            rules.append({'name': f.name, 'lines': l, 'trigger': trigger, 'content': c})
    data['rules'] = {'path': str(rules_dir), 'count': len(rules), 'items': rules}
    # Skills
    skills_dir = WINDSURF_DIR / 'skills'
    skills = []
    if skills_dir.exists():
        for d in sorted(skills_dir.iterdir()):
            if d.is_dir():
                sf = d / 'SKILL.md'
                if sf.exists():
                    c, l = safe_read(sf, max_lines=5)
                    has_fm = c.strip().startswith('---')
                    desc = ''
                    for line in c.splitlines():
                        if line.startswith('description:'):
                            desc = line[12:].strip()
                            break
                    skills.append({'name': d.name, 'lines': l, 'has_frontmatter': has_fm, 'description': desc})
    data['skills'] = {'path': str(skills_dir), 'count': len(skills), 'items': skills}
    # Workflows
    wf_dir = WINDSURF_DIR / 'workflows'
    workflows = []
    if wf_dir.exists():
        for f in sorted(wf_dir.glob('*.md')):
            c, l = safe_read(f, max_lines=5)
            desc = ''
            for line in c.splitlines():
                if line.startswith('description:'):
                    desc = line[12:].strip()
                    break
            workflows.append({'name': f.stem, 'lines': l, 'description': desc})
    data['workflows'] = {'path': str(wf_dir), 'count': len(workflows), 'items': workflows}
    # Hooks
    hf = WINDSURF_DIR / 'hooks.json'
    content, lines = safe_read(hf)
    data['hooks'] = {'path': str(hf), 'exists': hf.exists(), 'content': content}
    try:
        hooks_json = json.loads(content)
        hook_list = []
        for event, cmds in hooks_json.get('hooks', {}).items():
            for cmd in cmds:
                c = cmd.get('command', '')
                lang = 'python' if 'python' in c.lower() else ('node' if 'node' in c.lower() else 'unknown')
                hook_list.append({'event': event, 'command': c, 'language': lang, 'safe': lang != 'powershell'})
        data['hooks']['items'] = hook_list
    except: data['hooks']['items'] = []
    return data

# Known directories that have AGENTS.md (avoid rglob which follows junctions)
AGENTS_DIRS = [
    '', '反向控制', '基础设施', '投屏链路', '投屏链路/MJPEG投屏', '投屏链路/RTSP投屏',
    '投屏链路/WebRTC投屏', '用户界面', '配置管理', '智能家居', '手机操控库', '远程桌面',
    '构建部署', '构建部署/三界隔离', '阿里云服务器', '台式机保护', '双电脑互联', 'AGI',
]

def get_zone2():
    agents = []
    for d in AGENTS_DIRS:
        for name in ('AGENTS.md', '道之AGENTS.md'):
            md = PROJECT_ROOT / d / name if d else PROJECT_ROOT / name
            if md.exists():
                rel = md.relative_to(PROJECT_ROOT)
                _, l = safe_read(md)
                agents.append({'path': str(rel), 'directory': str(rel.parent) if str(rel.parent) != '.' else '(根目录)', 'lines': l})
    return {'count': len(agents), 'items': agents}

def health_check():
    checks = []
    def check(name, zone, ok, detail=''):
        checks.append({'name': name, 'zone': zone, 'ok': ok, 'detail': detail})
    # Zone 0
    gh = GLOBAL_ROOT / 'hooks.json'
    if gh.exists():
        c = gh.read_text(errors='replace')
        is_empty = '"hooks": {}' in c or '"hooks":{}' in c
        check('全局hooks为空', 0, is_empty, '已清空' if is_empty else '⚠ 非空!')
    else:
        check('全局hooks为空', 0, False, '文件不存在')
    mc = GLOBAL_ROOT / 'mcp_config.json'
    check('MCP配置存在', 0, mc.exists())
    gr = GLOBAL_ROOT / 'memories' / 'global_rules.md'
    check('全局规则存在', 0, gr.exists(), f'{sum(1 for _ in open(gr, errors="replace"))}行' if gr.exists() else '')
    # Zone 1
    rules_dir = WINDSURF_DIR / 'rules'
    rule_count = len(list(rules_dir.glob('*.md'))) if rules_dir.exists() else 0
    check('Rules 6个', 1, rule_count == 6, f'实际{rule_count}个')
    skills_dir = WINDSURF_DIR / 'skills'
    skill_dirs = [d for d in skills_dir.iterdir() if d.is_dir() and (d / 'SKILL.md').exists()] if skills_dir.exists() else []
    check('Skills 13个', 1, len(skill_dirs) == 13, f'实际{len(skill_dirs)}个')
    fm_count = 0
    for d in skill_dirs:
        sf = d / 'SKILL.md'
        if sf.exists() and sf.read_text(errors='replace').strip().startswith('---'): fm_count += 1
    check('Skills全部有frontmatter', 1, fm_count == len(skill_dirs), f'{fm_count}/{len(skill_dirs)}')
    old_path_count = 0
    for d in skill_dirs:
        sf = d / 'SKILL.md'
        if sf.exists() and 'e:\\github\\AIOT' in sf.read_text(errors='replace'): old_path_count += 1
    check('Skills无旧路径', 1, old_path_count == 0, f'{old_path_count}个含旧路径' if old_path_count else '全部已修正')
    wf_dir = WINDSURF_DIR / 'workflows'
    wf_count = len(list(wf_dir.glob('*.md'))) if wf_dir.exists() else 0
    check('Workflows 10个', 1, wf_count == 10, f'实际{wf_count}个')
    hf = WINDSURF_DIR / 'hooks.json'
    if hf.exists():
        hc = hf.read_text(errors='replace')
        has_ps = 'powershell' in hc.lower() or '.ps1' in hc.lower()
        check('项目hooks无PS', 1, not has_ps)
    # Zone 2
    agent_count = sum(1 for d in AGENTS_DIRS for n in ('AGENTS.md','道之AGENTS.md') if (PROJECT_ROOT / d / n if d else PROJECT_ROOT / n).exists())
    check('AGENTS.md ≥17', 2, agent_count >= 17, f'实际{agent_count}个')
    return checks

def get_risks():
    risks = []
    def warn(msg, level='warn', zone=1):
        risks.append({'msg': msg, 'level': level, 'zone': zone})
    # Zone 0
    gh = GLOBAL_ROOT / 'hooks.json'
    if gh.exists():
        c = gh.read_text(errors='replace')
        if '"hooks": {}' not in c and '"hooks":{}' not in c:
            warn('\u5168\u5c40hooks\u975e\u7a7a\uff01\u53ef\u80fd\u5f71\u54cd\u6240\u6709\u7a97\u53e3', 'error', 0)
        if 'powershell' in c.lower() or '.ps1' in c.lower():
            warn('\u5168\u5c40hooks\u542bPowerShell\uff01\u6781\u5ea6\u5371\u9669', 'error', 0)
    # Zone 1 Skills
    skills_dir = WINDSURF_DIR / 'skills'
    if skills_dir.exists():
        for d in skills_dir.iterdir():
            if d.is_dir():
                sf = d / 'SKILL.md'
                if sf.exists():
                    c = sf.read_text(errors='replace')
                    if not c.strip().startswith('---'):
                        warn(f'Skill {d.name} \u7f3afrontmatter', 'warn', 1)
                    if 'e:\\github\\AIOT' in c or 'e:/github/AIOT' in c:
                        warn(f'Skill {d.name} \u542b\u65e7\u8def\u5f84', 'error', 1)
    # Zone 1 Hooks
    hf = WINDSURF_DIR / 'hooks.json'
    if hf.exists():
        hc = hf.read_text(errors='replace')
        if 'powershell' in hc.lower() or '.ps1' in hc.lower():
            warn('\u9879\u76eehooks\u542bPowerShell\uff01', 'error', 1)
    # Stale check
    import time
    for name in ('soul.md', 'execution-engine.md', 'project-structure.md'):
        rf = WINDSURF_DIR / 'rules' / name
        if rf.exists():
            age_days = (time.time() - rf.stat().st_mtime) / 86400
            if age_days > 30:
                warn(f'Rule {name} \u8d85\u8fc730\u5929\u672a\u66f4\u65b0', 'info', 1)
    return risks

def save_file_api(rel_path, content):
    full = (PROJECT_ROOT / rel_path).resolve()
    if not str(full).startswith(str(PROJECT_ROOT.resolve())):
        return {'error': 'Access denied'}, 403
    try:
        full.write_text(content, encoding='utf-8')
        return {'ok': True, 'path': rel_path}, 200
    except Exception as e:
        return {'error': str(e)}, 500

def read_file_api(rel_path):
    # Security: only allow reading within project or global windsurf dir
    full = (PROJECT_ROOT / rel_path).resolve()
    if not (str(full).startswith(str(PROJECT_ROOT.resolve())) or str(full).startswith(str(GLOBAL_ROOT.resolve()))):
        return {'error': 'Access denied'}, 403
    content, lines = safe_read(full)
    return {'path': str(rel_path), 'lines': lines, 'content': content}, 200

DASHBOARD_HTML = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>道 — 智能体系</title>
<style>
:root{--ink:#0d0d0d;--paper:#141410;--scroll:#1c1b17;--line:#2a2822;--text:#c8c0a8;--faint:#7a7460;--vermillion:#c43e1c;--jade:#5a8a6a;--amber:#b89a3c;--sky:#4a7a9a;--gold:#d4a840;--white:#e8e0c8}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--ink);color:var(--text);font-family:'Noto Serif SC','Source Han Serif SC','Songti SC','SimSun',serif;line-height:1.8;min-height:100vh}
.container{max-width:1100px;margin:0 auto;padding:20px 24px}
header{text-align:center;padding:40px 0 20px;margin-bottom:32px;position:relative}
header::after{content:'';display:block;width:120px;height:1px;background:linear-gradient(90deg,transparent,var(--faint),transparent);margin:20px auto 0}
header h1{font-size:2.8em;font-weight:400;letter-spacing:.3em;color:var(--white);margin-bottom:2px}
header .subtitle{color:var(--faint);font-size:.85em;letter-spacing:.15em}
header .breath{display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--jade);margin-left:10px;animation:breath 4s ease-in-out infinite;vertical-align:middle}
@keyframes breath{0%,100%{opacity:.3;transform:scale(.8)}50%{opacity:1;transform:scale(1.2)}}
.verse{text-align:center;color:var(--faint);font-size:.8em;letter-spacing:.1em;margin-bottom:28px;font-style:italic}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin-bottom:28px}
.stat{background:var(--scroll);border:1px solid var(--line);border-radius:4px;padding:16px 12px;text-align:center;transition:border-color .3s}
.stat:hover{border-color:var(--faint)}
.stat .num{font-size:2.2em;font-weight:300;color:var(--gold);font-family:'Georgia',serif}
.stat .label{font-size:.75em;color:var(--faint);margin-top:6px;letter-spacing:.08em}
.zone{background:var(--paper);border:1px solid var(--line);border-radius:4px;margin-bottom:14px;overflow:hidden}
.zone-header{padding:14px 20px;cursor:pointer;display:flex;align-items:center;gap:12px;user-select:none;transition:background .2s}
.zone-header:hover{background:var(--scroll)}
.zone-header .gua{font-size:1.1em;opacity:.6}
.z0 .gua{color:var(--vermillion)}
.z1 .gua{color:var(--gold)}
.z2 .gua{color:var(--sky)}
.zone-header h2{flex:1;font-size:1em;font-weight:400;letter-spacing:.05em}
.zone-header .arrow{transition:transform .3s;color:var(--faint);font-size:.7em}
.zone-header.open .arrow{transform:rotate(90deg)}
.zone-body{padding:0 20px 20px;display:none}
.zone-body.show{display:block}
table{width:100%;border-collapse:collapse;margin:10px 0}
th,td{padding:7px 10px;text-align:left;border-bottom:1px solid var(--line);font-size:.85em}
th{color:var(--faint);font-weight:400;font-size:.75em;letter-spacing:.05em}
.ok{color:var(--jade)}
.warn{color:var(--amber)}
.err{color:var(--vermillion)}
.tag{display:inline-block;padding:1px 8px;border-radius:2px;font-size:.72em;margin:1px;font-family:-apple-system,system-ui,sans-serif}
.tag-on{background:rgba(90,138,106,.15);color:var(--jade)}
.tag-glob{background:rgba(184,154,60,.15);color:var(--amber)}
.tag-model{background:rgba(74,122,154,.15);color:var(--sky)}
.tag-py{background:rgba(90,138,106,.15);color:var(--jade)}
.tag-dis{background:rgba(196,62,28,.12);color:var(--vermillion)}
.health{margin-top:28px}
.health h2{margin-bottom:10px;font-size:1.05em;font-weight:400;letter-spacing:.1em}
.check{display:flex;align-items:center;gap:8px;padding:5px 0;font-size:.85em}
.check .icon{font-size:.9em}
.check .zt{font-size:.65em;padding:1px 5px;border-radius:2px;background:var(--scroll);color:var(--faint);font-family:-apple-system,system-ui,sans-serif}
.sub{margin:10px 0}
.sub h3{font-size:.88em;color:var(--gold);font-weight:400;margin-bottom:6px;padding-bottom:4px;border-bottom:1px solid var(--line);letter-spacing:.05em}
.clickable{cursor:pointer;color:var(--text);border-bottom:1px dotted var(--faint);transition:color .2s}
.clickable:hover{color:var(--gold)}
.modal-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.75);z-index:100;justify-content:center;align-items:center}
.modal-overlay.show{display:flex}
.modal{background:var(--paper);border:1px solid var(--line);border-radius:4px;width:90%;max-width:800px;max-height:80vh;display:flex;flex-direction:column}
.modal-header{padding:14px 20px;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between}
.modal-header h3{font-size:.95em;font-weight:400}
.modal-close{background:none;border:none;color:var(--faint);font-size:1.4em;cursor:pointer;padding:0 6px}
.modal-close:hover{color:var(--text)}
.modal-body{padding:14px 20px;overflow-y:auto;flex:1}
.modal-body pre{font-family:'Cascadia Code','Fira Code',monospace;font-size:.78em;line-height:1.6;white-space:pre-wrap;word-break:break-all;color:var(--text)}
.refresh-btn{background:var(--scroll);color:var(--text);border:1px solid var(--line);padding:7px 20px;border-radius:3px;cursor:pointer;font-size:.82em;letter-spacing:.08em;transition:border-color .2s}
.refresh-btn:hover{border-color:var(--gold);color:var(--gold)}
.toast-container{position:fixed;top:16px;right:16px;z-index:200;display:flex;flex-direction:column;gap:8px}
.toast{padding:10px 18px;border-radius:3px;font-size:.82em;animation:fadeIn .4s;max-width:340px;cursor:pointer;border-left:3px solid}
.toast-ok{background:rgba(90,138,106,.15);border-color:var(--jade);color:var(--jade)}
.toast-warn{background:rgba(184,154,60,.15);border-color:var(--amber);color:var(--amber)}
.toast-err{background:rgba(196,62,28,.15);border-color:var(--vermillion);color:var(--vermillion)}
@keyframes fadeIn{from{opacity:0;transform:translateY(-10px)}to{opacity:1;transform:translateY(0)}}
.risks{margin-bottom:16px}
.risk-item{display:flex;align-items:center;gap:8px;padding:7px 12px;margin:3px 0;font-size:.82em;border-left:2px solid}
.risk-error{background:rgba(196,62,28,.06);border-color:var(--vermillion);color:var(--vermillion)}
.risk-warn{background:rgba(184,154,60,.06);border-color:var(--amber);color:var(--amber)}
.risk-info{background:rgba(74,122,154,.06);border-color:var(--sky);color:var(--sky)}
.edit-area{width:100%;min-height:280px;background:var(--ink);color:var(--text);border:1px solid var(--line);border-radius:3px;padding:12px;font-family:'Cascadia Code','Fira Code',monospace;font-size:.78em;line-height:1.6;resize:vertical}
.edit-actions{display:flex;gap:8px;margin-top:8px;justify-content:flex-end}
.btn-save{background:var(--jade);color:var(--ink);border:none;padding:5px 14px;border-radius:3px;cursor:pointer;font-size:.82em}
.btn-cancel{background:var(--scroll);color:var(--text);border:1px solid var(--line);padding:5px 14px;border-radius:3px;cursor:pointer;font-size:.82em}
.footer{text-align:center;margin-top:32px;padding-top:16px;border-top:1px solid var(--line);color:var(--faint);font-size:.72em;letter-spacing:.1em}
@media(max-width:600px){.container{padding:12px}.stats{grid-template-columns:repeat(2,1fr)}header h1{font-size:2em}}
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>道</h1>
    <div class="subtitle">天 · 人 · 地<span class="breath" id="autoLed" title="知常曰明 — 自观不息"></span></div>
  </header>
  <div class="verse" id="verse"></div>
  <div class="stats" id="stats"></div>
  <div class="risks" id="risks"></div>
  <div id="zones"></div>
  <div class="health" id="health"></div>
  <div style="display:flex;gap:10px;margin-top:20px;align-items:center;justify-content:center">
    <button class="refresh-btn" onclick="loadAll()">观 · 刷新</button>
    <span style="color:var(--faint);font-size:.75em" id="lastRefresh"></span>
  </div>
  <div class="footer">道生一 · 一生二 · 二生三 · 三生万物</div>
  <div class="toast-container" id="toasts"></div>
</div>
<div class="modal-overlay" id="modal" onclick="if(event.target===this)closeModal()">
  <div class="modal">
    <div class="modal-header"><h3 id="modalTitle"></h3><div><button id="editToggle" onclick="toggleEdit()" style="background:var(--scroll);color:var(--text);border:1px solid var(--line);padding:3px 10px;border-radius:3px;cursor:pointer;font-size:.78em;margin-right:8px">为 · 编辑</button><button class="modal-close" onclick="closeModal()">&times;</button></div></div>
    <div class="modal-body">
      <pre id="modalContent"></pre>
      <textarea id="editArea" class="edit-area" style="display:none"></textarea>
      <div id="editActions" class="edit-actions" style="display:none">
        <button class="btn-cancel" onclick="cancelEdit()">止</button>
        <button class="btn-save" onclick="saveEdit()">存</button>
      </div>
    </div>
  </div>
</div>
<script>
const API='';let DATA={};let PREV_HC=null;let autoTimer=null;
const VERSES=[
  '\u89c2\u5176\u5999\u2003\u2014\u2014\u2003\u300a\u9053\u5fb7\u7ecf\u300b\u7b2c\u4e00\u7ae0',
  '\u5927\u97f3\u5e0c\u58f0\uff0c\u5927\u8c61\u65e0\u5f62\u2003\u2014\u2014\u2003\u300a\u9053\u5fb7\u7ecf\u300b\u7b2c\u56db\u5341\u4e00\u7ae0',
  '\u77e5\u5e38\u66f0\u660e\u2003\u2014\u2014\u2003\u300a\u9053\u5fb7\u7ecf\u300b\u7b2c\u5341\u516d\u7ae0',
  '\u5929\u7f51\u6062\u6062\uff0c\u758f\u800c\u4e0d\u5931\u2003\u2014\u2014\u2003\u300a\u9053\u5fb7\u7ecf\u300b\u7b2c\u4e03\u5341\u4e09\u7ae0',
  '\u4e07\u7269\u8d1f\u9634\u800c\u62b1\u9633\uff0c\u51b2\u6c14\u4ee5\u4e3a\u548c\u2003\u2014\u2014\u2003\u300a\u9053\u5fb7\u7ecf\u300b\u7b2c\u56db\u5341\u4e8c\u7ae0',
  '\u4e0a\u5584\u82e5\u6c34\u2003\u2014\u2014\u2003\u300a\u9053\u5fb7\u7ecf\u300b\u7b2c\u516b\u7ae0',
  '\u65e0\u4e3a\u800c\u65e0\u4e0d\u4e3a\u2003\u2014\u2014\u2003\u300a\u9053\u5fb7\u7ecf\u300b\u7b2c\u56db\u5341\u516b\u7ae0',
  '\u5929\u5730\u4e0e\u6211\u5e76\u751f\uff0c\u800c\u4e07\u7269\u4e0e\u6211\u4e3a\u4e00\u2003\u2014\u2014\u2003\u300a\u5e84\u5b50\u00b7\u9f50\u7269\u8bba\u300b',
  '\u81f3\u4eba\u65e0\u5df1\uff0c\u795e\u4eba\u65e0\u529f\uff0c\u5723\u4eba\u65e0\u540d\u2003\u2014\u2014\u2003\u300a\u5e84\u5b50\u00b7\u900d\u9065\u6e38\u300b',
  '\u5434\u751f\u4e4b\u4e5f\u6709\u6daf\uff0c\u800c\u77e5\u4e5f\u65e0\u6daf\u2003\u2014\u2014\u2003\u300a\u5e84\u5b50\u00b7\u517b\u751f\u4e3b\u300b',
];
document.getElementById('verse').textContent=VERSES[Math.floor(Math.random()*VERSES.length)];

function toast(msg,type='ok'){const t=document.createElement('div');t.className=`toast toast-${type}`;t.textContent=msg;t.onclick=()=>t.remove();document.getElementById('toasts').appendChild(t);setTimeout(()=>t.remove(),4000)}

async function loadAll(){
  try{
    const[z0,z1,z2,hc,risks]=await Promise.all([fetch(API+'/api/zone0').then(r=>r.json()),fetch(API+'/api/zone1').then(r=>r.json()),fetch(API+'/api/zone2').then(r=>r.json()),fetch(API+'/api/health').then(r=>r.json()),fetch(API+'/api/risks').then(r=>r.json())]);
    if(PREV_HC){const p=PREV_HC.filter(c=>c.ok).length,n=hc.filter(c=>c.ok).length;if(n<p)toast(`\u6c14\u8861\u5931\u8c03: ${n}/${hc.length}`,'err');else if(n>p)toast(`\u6c14\u8861\u590d\u548c: ${n}/${hc.length}`,'ok')}
    PREV_HC=hc;DATA={z0,z1,z2,hc,risks};renderStats();renderRisks();renderZones();renderHealth();
    document.getElementById('lastRefresh').textContent=new Date().toLocaleTimeString();
  }catch(e){toast('\u89c2\u5bdf\u5931\u8d25: '+e.message,'err')}
}
function startAutoRefresh(){if(autoTimer)clearInterval(autoTimer);autoTimer=setInterval(loadAll,30000)}
startAutoRefresh();

function renderStats(){
  const{z0,z1,z2,hc}=DATA;const ok=hc.filter(c=>c.ok).length;
  document.getElementById('stats').innerHTML=`
    <div class="stat"><div class="num">${z1.rules?.count||0}</div><div class="label">\u5f8b · Rules</div></div>
    <div class="stat"><div class="num">${z1.skills?.count||0}</div><div class="label">\u672f · Skills</div></div>
    <div class="stat"><div class="num">${z1.workflows?.count||0}</div><div class="label">\u6cd5 · Workflows</div></div>
    <div class="stat"><div class="num">${z2.count||0}</div><div class="label">\u5fb7 · AGENTS</div></div>
    <div class="stat"><div class="num">${z0.global_skills?.count||0}</div><div class="label">\u5929\u672f</div></div>
    <div class="stat"><div class="num">${Object.keys(z0.mcp_config?.servers||{}).length}</div><div class="label">\u5668 · MCP</div></div>
    <div class="stat"><div class="num" style="color:${ok===hc.length?'var(--jade)':'var(--amber)'}">
      ${ok}/${hc.length}</div><div class="label">\u6c14 · \u548c</div></div>`;
}

function renderZones(){
  const{z0,z1,z2}=DATA;let h='';
  h+=`<div class="zone z0"><div class="zone-header" onclick="toggleZone(this)">
    <span class="gua">\u2630</span><h2>\u5929 \u2014 \u5929\u9053\u65e0\u4eb2\uff0c\u5e38\u4e0e\u5584\u4eba</h2><span class="arrow">\u25b6</span>
    </div><div class="zone-body">`;
  h+=`<div class="sub"><h3>\u5929\u5f8b (\u5168\u5c40\u89c4\u5219 ${z0.global_rules?.lines||0}\u884c)</h3>
    <p class="clickable" onclick="viewFile('global_rules')">${z0.global_rules?.path}</p></div>`;
  h+=`<div class="sub"><h3>\u4e94\u5668 (MCP)</h3><table><tr><th>\u5668</th><th>\u72b6\u6001</th><th>\u547d\u4ee4</th></tr>`;
  for(const[n,c] of Object.entries(z0.mcp_config?.servers||{})){
    h+=`<tr><td>${n}</td><td>${c.disabled?'<span class="tag tag-dis">\u5bc2</span>':'<span class="tag tag-on">\u901a</span>'}</td><td style="font-size:.78em;color:var(--faint)">${c.command}</td></tr>`}
  h+=`</table></div>`;
  const gh=z0.global_hooks;
  h+=`<div class="sub"><h3>\u5929\u94a9 (Hooks)</h3><p>${gh?.empty?'<span class="ok">\u2714 \u865a\u65e0\uff08\u5b89\uff09</span>':'<span class="err">\u26a0 \u975e\u865a\uff01</span>'}</p></div>`;
  h+=`<div class="sub"><h3>\u5929\u672f (${z0.global_skills?.count||0})</h3><table><tr><th>\u540d</th><th>\u5177</th><th>\u884c</th></tr>`;
  for(const s of z0.global_skills?.skills||[]){h+=`<tr><td>${s.name}</td><td>${s.has_skill_md?'<span class="ok">\u2714</span>':'<span class="err">\u2718</span>'}</td><td>${s.lines}</td></tr>`}
  h+=`</table></div></div></div>`;

  h+=`<div class="zone z1"><div class="zone-header open" onclick="toggleZone(this)">
    <span class="gua">\u2634</span><h2>\u4eba \u2014 \u4eba\u6cd5\u5730\uff0c\u5730\u6cd5\u5929\uff0c\u5929\u6cd5\u9053</h2><span class="arrow">\u25b6</span>
    </div><div class="zone-body show">`;
  h+=`<div class="sub"><h3>\u5f8b (${z1.rules?.count||0})</h3><table><tr><th>\u6587</th><th>\u89e6</th><th>\u884c</th></tr>`;
  for(const r of z1.rules?.items||[]){const tg=r.trigger==='always_on'?'tag-on':r.trigger==='glob'?'tag-glob':'tag-model';
    h+=`<tr><td class="clickable" onclick="viewRule('${r.name}')">${r.name}</td><td><span class="tag ${tg}">${r.trigger==='always_on'?'\u5e38':r.trigger==='glob'?'\u611f':'\u673a'}</span></td><td>${r.lines}</td></tr>`}
  h+=`</table></div>`;
  h+=`<div class="sub"><h3>\u672f (${z1.skills?.count||0})</h3><table><tr><th>\u540d</th><th>\u5177</th><th>\u884c</th><th>\u9053</th></tr>`;
  for(const s of z1.skills?.items||[]){h+=`<tr><td class="clickable" onclick="viewSkill('${s.name}')">${s.name}</td><td>${s.has_frontmatter?'<span class="ok">\u2714</span>':'<span class="err">\u2718</span>'}</td><td>${s.lines}</td><td style="font-size:.78em;color:var(--faint)">${(s.description||'').slice(0,30)}</td></tr>`}
  h+=`</table></div>`;
  h+=`<div class="sub"><h3>\u6cd5 (${z1.workflows?.count||0})</h3><table><tr><th>\u5f0f</th><th>\u884c</th><th>\u9053</th></tr>`;
  for(const w of z1.workflows?.items||[]){h+=`<tr><td>/${w.name}</td><td>${w.lines}</td><td style="font-size:.78em;color:var(--faint)">${(w.description||'').slice(0,40)}</td></tr>`}
  h+=`</table></div>`;
  h+=`<div class="sub"><h3>\u94a9 (Hooks)</h3><table><tr><th>\u65f6</th><th>\u8bed</th><th>\u547d</th></tr>`;
  for(const hk of z1.hooks?.items||[]){h+=`<tr><td>${hk.event}</td><td><span class="tag tag-py">${hk.language}</span></td><td style="font-size:.78em;color:var(--faint)">${hk.command}</td></tr>`}
  h+=`</table></div></div></div>`;

  h+=`<div class="zone z2"><div class="zone-header" onclick="toggleZone(this)">
    <span class="gua">\u2637</span><h2>\u5730 \u2014 \u5fb7 \u00d7 ${z2.count}</h2><span class="arrow">\u25b6</span>
    </div><div class="zone-body"><table><tr><th>\u5730</th><th>\u884c</th></tr>`;
  for(const a of z2.items||[]){h+=`<tr><td class="clickable" onclick="viewAgent('${a.path}')">${a.directory}/</td><td>${a.lines}</td></tr>`}
  h+=`</table></div></div>`;
  document.getElementById('zones').innerHTML=h;
}

function renderHealth(){
  const{hc}=DATA;let h='<h2>\u6c14 \u2014 \u4e07\u7269\u8d1f\u9634\u800c\u62b1\u9633\uff0c\u51b2\u6c14\u4ee5\u4e3a\u548c</h2>';
  for(const c of hc){h+=`<div class="check"><span class="icon">${c.ok?'\u25cf':'\u25cb'}</span><span class="zt">${['\u5929','\u4eba','\u5730'][c.zone]}</span><span>${c.name}</span><span style="color:var(--faint);font-size:.78em;margin-left:auto">${c.detail||''}</span></div>`}
  document.getElementById('health').innerHTML=h;
}

function renderRisks(){
  const risks=DATA.risks||[];
  if(!risks.length){document.getElementById('risks').innerHTML='';return}
  let h='<div class="sub"><h3>\u7978 \u2014 \u7978\u516e\u798f\u4e4b\u6240\u5029</h3>';
  for(const r of risks){h+=`<div class="risk-item risk-${r.level}"><span>${['\u5929','\u4eba','\u5730'][r.zone]}</span><span>${r.msg}</span></div>`}
  h+='</div>';document.getElementById('risks').innerHTML=h;
}

function toggleZone(el){el.classList.toggle('open');el.nextElementSibling.classList.toggle('show')}

async function viewFile(key){showModal(DATA.z0?.[key]?.path||key,DATA.z0?.[key]?.content||'')}
async function viewRule(name){const r=DATA.z1.rules.items.find(i=>i.name===name);if(r)showModal(name,r.content,`.windsurf/rules/${name}`)}
async function viewSkill(name){const p=`.windsurf/skills/${name}/SKILL.md`;const res=await fetch(API+`/api/file?path=${p}`);const d=await res.json();showModal(`\u672f/${name}`,d.content||d.error,p)}
async function viewAgent(path){const res=await fetch(API+`/api/file?path=${encodeURIComponent(path)}`);const d=await res.json();showModal(path,d.content||d.error,path)}

let currentFilePath=null;
function showModal(title,content,filePath){
  currentFilePath=filePath||null;
  document.getElementById('modalTitle').textContent=title;
  document.getElementById('modalContent').textContent=content;
  document.getElementById('modalContent').style.display='block';
  document.getElementById('editArea').style.display='none';
  document.getElementById('editActions').style.display='none';
  document.getElementById('editToggle').style.display=currentFilePath?'':'none';
  document.getElementById('modal').classList.add('show');
}
function toggleEdit(){const pre=document.getElementById('modalContent'),area=document.getElementById('editArea'),actions=document.getElementById('editActions');if(area.style.display==='none'){area.value=pre.textContent;pre.style.display='none';area.style.display='block';actions.style.display='flex';area.focus()}else{cancelEdit()}}
function cancelEdit(){document.getElementById('modalContent').style.display='block';document.getElementById('editArea').style.display='none';document.getElementById('editActions').style.display='none'}
async function saveEdit(){
  if(!currentFilePath){toast('\u65e0\u5f84\u53ef\u5b58','err');return}
  try{const res=await fetch(API+'/api/file/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:currentFilePath,content:document.getElementById('editArea').value})});
  const d=await res.json();if(d.ok){toast('\u5df1\u5b58: '+currentFilePath,'ok');document.getElementById('modalContent').textContent=document.getElementById('editArea').value;cancelEdit();loadAll()}else{toast('\u5b58\u5931\u8d25: '+(d.error||''),'err')}}catch(e){toast('\u5b58\u5931\u8d25: '+e.message,'err')}
}
function closeModal(){document.getElementById('modal').classList.remove('show');cancelEdit()}
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeModal();if(e.key==='s'&&(e.ctrlKey||e.metaKey)&&document.getElementById('editArea').style.display!=='none'){e.preventDefault();saveEdit()}});
loadAll();
</script>
</body>
</html>'''

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        if path == '/' or path == '/index.html':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(DASHBOARD_HTML.encode('utf-8'))
        elif path == '/api/zone0':
            self._json(get_zone0())
        elif path == '/api/zone1':
            self._json(get_zone1())
        elif path == '/api/zone2':
            self._json(get_zone2())
        elif path == '/api/health':
            self._json(health_check())
        elif path == '/api/risks':
            self._json(get_risks())
        elif path == '/favicon.ico':
            svg = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y=".9em" font-size="80">\xf0\x9f\xa7\xa0</text></svg>'
            self.send_response(200)
            self.send_header('Content-Type', 'image/svg+xml')
            self.end_headers()
            self.wfile.write(svg)
        elif path == '/api/file':
            rel = qs.get('path', [''])[0]
            data, code = read_file_api(rel)
            self._json(data, code)
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length).decode('utf-8') if length else '{}'
        if path == '/api/file/save':
            try:
                j = json.loads(body)
                data, code = save_file_api(j.get('path',''), j.get('content',''))
                self._json(data, code)
            except Exception as e:
                self._json({'error': str(e)}, 400)
        else:
            self.send_error(404)

    def _json(self, data, code=200):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, default=str).encode('utf-8'))

    def log_message(self, format, *args):
        pass  # Suppress request logs

### ========== 系统托盘 + 守护进程 ==========

_httpd = None
_tray_icon = None

def start_http_server():
    """启动HTTP服务器（在后台线程运行）"""
    global _httpd
    # 防止端口占用：允许地址复用
    socketserver.TCPServer.allow_reuse_address = True
    try:
        _httpd = socketserver.TCPServer(('127.0.0.1', PORT), Handler)
        _httpd.serve_forever()
    except OSError as e:
        if 'address already in use' in str(e).lower() or '10048' in str(e):
            print(f'[道] 端口 {PORT} 已被占用，服务已在运行')
        else:
            raise

def stop_http_server():
    global _httpd
    if _httpd:
        _httpd.shutdown()
        _httpd = None

def create_tray_icon():
    """创建☯系统托盘图标（pystray + PIL）"""
    try:
        import pystray
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print('[道] pystray/PIL未安装，跳过托盘。pip install pystray pillow')
        return None

    # 绘制☯太极图标 64x64
    size = 64
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # 外圆
    draw.ellipse([2, 2, size-2, size-2], fill='#1a1a2e', outline='#d4a840', width=2)
    # 阴阳：左黑右白半圆
    draw.pieslice([2, 2, size-2, size-2], 90, 270, fill='#e8e0c8')
    # 上小圆
    r = size // 8
    cx, cy_top, cy_bot = size//2, size//4, size*3//4
    draw.ellipse([cx-r, cy_top-r, cx+r, cy_top+r], fill='#1a1a2e')
    draw.ellipse([cx-r, cy_bot-r, cx+r, cy_bot+r], fill='#e8e0c8')
    # 上弧修补
    draw.pieslice([size//4, 2, size*3//4, size//2], 90, 270, fill='#e8e0c8')
    draw.pieslice([size//4, size//2, size*3//4, size-2], 270, 90, fill='#1a1a2e')
    # 重绘小圆（保证在上层）
    draw.ellipse([cx-r, cy_top-r, cx+r, cy_top+r], fill='#1a1a2e')
    draw.ellipse([cx-r, cy_bot-r, cx+r, cy_bot+r], fill='#e8e0c8')

    def on_open(icon, item):
        webbrowser.open(f'http://localhost:{PORT}')

    def on_autostart(icon, item):
        _toggle_autostart()

    def on_quit(icon, item):
        stop_http_server()
        icon.stop()

    menu = pystray.Menu(
        pystray.MenuItem(f'观 · 打开仪表盘 (:{ PORT })', on_open, default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('开机自启', on_autostart, checked=lambda item: _is_autostart_enabled()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('止 · 退出', on_quit),
    )

    icon = pystray.Icon('dao-dashboard', img, '道 — 智能体系', menu)
    return icon

def _get_startup_shortcut_path():
    """获取Startup目录中的快捷方式路径"""
    startup = Path(os.environ.get('APPDATA', '')) / 'Microsoft' / 'Windows' / 'Start Menu' / 'Programs' / 'Startup'
    return startup / '道-仪表盘.bat'

def _is_autostart_enabled():
    return _get_startup_shortcut_path().exists()

def _toggle_autostart():
    """切换开机自启状态"""
    bat = _get_startup_shortcut_path()
    if bat.exists():
        bat.unlink()
        print('[道] 已关闭开机自启')
    else:
        # 用pythonw无窗口启动
        script = Path(__file__).resolve()
        pythonw = Path(sys.executable).parent / 'pythonw.exe'
        if not pythonw.exists():
            pythonw = Path(sys.executable)  # fallback to python.exe
        bat.write_text(f'@echo off\nstart "" "{pythonw}" "{script}"\n', encoding='utf-8')
        print(f'[道] 已启用开机自启: {bat}')

def run_with_watchdog(func, name='server', restart_delay=3, max_restarts=10):
    """守护进程：崩溃自动重启"""
    restarts = 0
    while restarts < max_restarts:
        try:
            func()
            break  # 正常退出
        except Exception as e:
            restarts += 1
            print(f'[道] {name} 异常退出 ({restarts}/{max_restarts}): {e}')
            if restarts < max_restarts:
                time.sleep(restart_delay)
            else:
                print(f'[道] {name} 重启次数耗尽，停止守护')

if __name__ == '__main__':
    no_tray = '--no-tray' in sys.argv

    # 启动HTTP服务器（后台线程）
    server_thread = threading.Thread(target=lambda: run_with_watchdog(start_http_server, 'HTTP'), daemon=True)
    server_thread.start()
    print(f'[道] http://localhost:{PORT}')

    if no_tray:
        # 纯HTTP模式（无托盘）
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            stop_http_server()
            print('\n[道] 止。')
    else:
        # 系统托盘模式
        icon = create_tray_icon()
        if icon:
            print('[道] 系统托盘已就绪（右键托盘图标操作）')
            icon.run()  # 阻塞，直到用户选择"退出"
        else:
            # pystray不可用，降级为纯HTTP
            print('[道] 降级为纯HTTP模式')
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                stop_http_server()
                print('\n[道] 止。')
