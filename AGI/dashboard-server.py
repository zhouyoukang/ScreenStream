"""
Windsurf 智能体系仪表盘 — Web版
启动: python .windsurf/dashboard-server.py
访问: http://localhost:9090
"""
import http.server, json, os, re, glob, socketserver
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
<title>Windsurf 仪表盘</title>
<style>
:root{--bg:#0a0a0f;--surface:#12121a;--card:#1a1a2e;--border:#2a2a3e;--text:#e0e0e0;--muted:#888;--accent:#6c5ce7;--green:#2ecc71;--red:#e74c3c;--yellow:#f1c40f;--blue:#3498db}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--text);font-family:-apple-system,system-ui,'Segoe UI',sans-serif;line-height:1.6;min-height:100vh}
.container{max-width:1200px;margin:0 auto;padding:16px}
header{text-align:center;padding:24px 0 16px;border-bottom:1px solid var(--border);margin-bottom:24px}
header h1{font-size:1.8em;background:linear-gradient(135deg,var(--accent),var(--blue));-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:4px}
header p{color:var(--muted);font-size:.9em}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:24px}
.stat{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:16px;text-align:center}
.stat .num{font-size:2em;font-weight:700;color:var(--accent)}
.stat .label{font-size:.8em;color:var(--muted);margin-top:4px}
.zone{background:var(--surface);border:1px solid var(--border);border-radius:12px;margin-bottom:16px;overflow:hidden}
.zone-header{padding:16px 20px;cursor:pointer;display:flex;align-items:center;gap:12px;user-select:none}
.zone-header:hover{background:var(--card)}
.zone-header .badge{padding:2px 10px;border-radius:6px;font-size:.75em;font-weight:600;text-transform:uppercase}
.z0 .badge{background:rgba(231,76,60,.2);color:var(--red)}
.z1 .badge{background:rgba(108,92,231,.2);color:var(--accent)}
.z2 .badge{background:rgba(52,152,219,.2);color:var(--blue)}
.zone-header h2{flex:1;font-size:1.1em}
.zone-header .arrow{transition:transform .2s;color:var(--muted)}
.zone-header.open .arrow{transform:rotate(90deg)}
.zone-body{padding:0 20px 20px;display:none}
.zone-body.show{display:block}
table{width:100%;border-collapse:collapse;margin:12px 0}
th,td{padding:8px 12px;text-align:left;border-bottom:1px solid var(--border);font-size:.9em}
th{color:var(--muted);font-weight:500;font-size:.8em;text-transform:uppercase}
.ok{color:var(--green)}
.warn{color:var(--yellow)}
.err{color:var(--red)}
.tag{display:inline-block;padding:1px 8px;border-radius:4px;font-size:.75em;margin:1px}
.tag-on{background:rgba(46,204,113,.15);color:var(--green)}
.tag-glob{background:rgba(241,196,15,.15);color:var(--yellow)}
.tag-model{background:rgba(52,152,219,.15);color:var(--blue)}
.tag-py{background:rgba(46,204,113,.15);color:var(--green)}
.tag-dis{background:rgba(231,76,60,.15);color:var(--red)}
.health{margin-top:24px}
.health h2{margin-bottom:12px;font-size:1.2em}
.check{display:flex;align-items:center;gap:8px;padding:6px 0;font-size:.9em}
.check .icon{font-size:1.1em}
.check .zone-tag{font-size:.7em;padding:1px 6px;border-radius:3px;background:var(--card);color:var(--muted)}
.tree{background:var(--card);border-radius:8px;padding:16px;font-family:'Cascadia Code','Fira Code',monospace;font-size:.82em;line-height:1.8;overflow-x:auto;margin:12px 0;white-space:pre}
.sub{margin:12px 0}
.sub h3{font-size:.95em;color:var(--accent);margin-bottom:8px;padding-bottom:4px;border-bottom:1px solid var(--border)}
.clickable{cursor:pointer;text-decoration:underline;text-decoration-style:dotted;text-underline-offset:3px}
.clickable:hover{color:var(--accent)}
.modal-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:100;justify-content:center;align-items:center}
.modal-overlay.show{display:flex}
.modal{background:var(--surface);border:1px solid var(--border);border-radius:12px;width:90%;max-width:800px;max-height:80vh;display:flex;flex-direction:column}
.modal-header{padding:16px 20px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between}
.modal-header h3{font-size:1em}
.modal-close{background:none;border:none;color:var(--muted);font-size:1.5em;cursor:pointer;padding:0 8px}
.modal-close:hover{color:var(--text)}
.modal-body{padding:16px 20px;overflow-y:auto;flex:1}
.modal-body pre{font-family:'Cascadia Code','Fira Code',monospace;font-size:.82em;line-height:1.5;white-space:pre-wrap;word-break:break-all}
.refresh-btn{background:var(--accent);color:#fff;border:none;padding:8px 20px;border-radius:8px;cursor:pointer;font-size:.9em;margin-top:16px}
.refresh-btn:hover{opacity:.9}
@media(max-width:600px){.container{padding:8px}.stats{grid-template-columns:repeat(2,1fr)}}
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>Windsurf 智能体系</h1>
    <p>三层架构 · 全景仪表盘</p>
  </header>
  <div class="stats" id="stats"></div>
  <div id="zones"></div>
  <div class="health" id="health"></div>
  <button class="refresh-btn" onclick="loadAll()">刷新全部</button>
</div>
<div class="modal-overlay" id="modal" onclick="if(event.target===this)closeModal()">
  <div class="modal">
    <div class="modal-header"><h3 id="modalTitle"></h3><button class="modal-close" onclick="closeModal()">&times;</button></div>
    <div class="modal-body"><pre id="modalContent"></pre></div>
  </div>
</div>
<script>
const API = '';
let DATA = {};

async function loadAll() {
  const [z0, z1, z2, hc] = await Promise.all([
    fetch(API+'/api/zone0').then(r=>r.json()),
    fetch(API+'/api/zone1').then(r=>r.json()),
    fetch(API+'/api/zone2').then(r=>r.json()),
    fetch(API+'/api/health').then(r=>r.json())
  ]);
  DATA = {z0, z1, z2, hc};
  renderStats();
  renderZones();
  renderHealth();
}

function renderStats() {
  const {z0,z1,z2,hc} = DATA;
  const okCount = hc.filter(c=>c.ok).length;
  document.getElementById('stats').innerHTML = `
    <div class="stat"><div class="num">${z1.rules?.count||0}</div><div class="label">Rules</div></div>
    <div class="stat"><div class="num">${z1.skills?.count||0}</div><div class="label">Skills</div></div>
    <div class="stat"><div class="num">${z1.workflows?.count||0}</div><div class="label">Workflows</div></div>
    <div class="stat"><div class="num">${z2.count||0}</div><div class="label">AGENTS.md</div></div>
    <div class="stat"><div class="num">${z0.global_skills?.count||0}</div><div class="label">全局Skills</div></div>
    <div class="stat"><div class="num">${Object.keys(z0.mcp_config?.servers||{}).length}</div><div class="label">MCP</div></div>
    <div class="stat"><div class="num" style="color:${okCount===hc.length?'var(--green)':'var(--yellow)'}">
      ${okCount}/${hc.length}</div><div class="label">健康检查</div></div>
  `;
}

function renderZones() {
  const {z0,z1,z2} = DATA;
  let html = '';
  // Zone 0
  html += `<div class="zone z0">
    <div class="zone-header" onclick="toggleZone(this)">
      <span class="badge">Zone 0</span><h2>全局级 — 影响所有项目</h2><span class="arrow">▶</span>
    </div><div class="zone-body">`;
  // Global rules
  html += `<div class="sub"><h3>全局规则 (${z0.global_rules?.lines||0}行)</h3>
    <p class="clickable" onclick="viewFile('global_rules')">${z0.global_rules?.path}</p></div>`;
  // MCP
  html += `<div class="sub"><h3>MCP配置</h3><table><tr><th>Server</th><th>状态</th><th>命令</th></tr>`;
  for (const [name, cfg] of Object.entries(z0.mcp_config?.servers||{})) {
    const st = cfg.disabled ? '<span class="tag tag-dis">禁用</span>' : '<span class="tag tag-on">启用</span>';
    html += `<tr><td>${name}</td><td>${st}</td><td style="font-size:.8em;color:var(--muted)">${cfg.command}</td></tr>`;
  }
  html += `</table></div>`;
  // Global hooks
  const gh = z0.global_hooks;
  html += `<div class="sub"><h3>全局Hooks</h3>
    <p>${gh?.empty ? '<span class="ok">✅ 已清空（安全）</span>' : '<span class="err">⚠ 非空！</span>'}</p></div>`;
  // Global skills
  html += `<div class="sub"><h3>全局Skills (${z0.global_skills?.count||0})</h3><table><tr><th>名称</th><th>SKILL.md</th><th>行数</th></tr>`;
  for (const s of z0.global_skills?.skills||[]) {
    html += `<tr><td>${s.name}</td><td>${s.has_skill_md?'<span class="ok">✅</span>':'<span class="err">❌</span>'}</td><td>${s.lines}</td></tr>`;
  }
  html += `</table></div></div></div>`;

  // Zone 1
  html += `<div class="zone z1">
    <div class="zone-header open" onclick="toggleZone(this)">
      <span class="badge">Zone 1</span><h2>项目级 — 当前工作区</h2><span class="arrow">▶</span>
    </div><div class="zone-body show">`;
  // Rules
  html += `<div class="sub"><h3>Rules (${z1.rules?.count||0})</h3><table><tr><th>文件</th><th>触发</th><th>行数</th></tr>`;
  for (const r of z1.rules?.items||[]) {
    const tag = r.trigger==='always_on'?'tag-on':r.trigger==='glob'?'tag-glob':'tag-model';
    html += `<tr><td class="clickable" onclick="viewRule('${r.name}')">${r.name}</td>
      <td><span class="tag ${tag}">${r.trigger}</span></td><td>${r.lines}</td></tr>`;
  }
  html += `</table></div>`;
  // Skills
  html += `<div class="sub"><h3>Skills (${z1.skills?.count||0}) — 全部有frontmatter ✅</h3><table><tr><th>名称</th><th>FM</th><th>行</th><th>描述</th></tr>`;
  for (const s of z1.skills?.items||[]) {
    html += `<tr><td class="clickable" onclick="viewSkill('${s.name}')">${s.name}</td>
      <td>${s.has_frontmatter?'<span class="ok">✅</span>':'<span class="err">❌</span>'}</td>
      <td>${s.lines}</td><td style="font-size:.8em;color:var(--muted)">${s.description||''}</td></tr>`;
  }
  html += `</table></div>`;
  // Workflows
  html += `<div class="sub"><h3>Workflows (${z1.workflows?.count||0})</h3><table><tr><th>命令</th><th>行</th><th>描述</th></tr>`;
  for (const w of z1.workflows?.items||[]) {
    html += `<tr><td>/${w.name}</td><td>${w.lines}</td><td style="font-size:.8em;color:var(--muted)">${w.description||''}</td></tr>`;
  }
  html += `</table></div>`;
  // Hooks
  html += `<div class="sub"><h3>项目Hooks</h3><table><tr><th>事件</th><th>语言</th><th>命令</th></tr>`;
  for (const h of z1.hooks?.items||[]) {
    html += `<tr><td>${h.event}</td><td><span class="tag tag-py">${h.language}</span></td>
      <td style="font-size:.8em;color:var(--muted)">${h.command}</td></tr>`;
  }
  html += `</table></div></div></div>`;

  // Zone 2
  html += `<div class="zone z2">
    <div class="zone-header" onclick="toggleZone(this)">
      <span class="badge">Zone 2</span><h2>目录级 — AGENTS.md (${z2.count})</h2><span class="arrow">▶</span>
    </div><div class="zone-body"><table><tr><th>目录</th><th>行数</th></tr>`;
  for (const a of z2.items||[]) {
    html += `<tr><td class="clickable" onclick="viewAgent('${a.path}')">${a.directory}/</td><td>${a.lines}</td></tr>`;
  }
  html += `</table></div></div>`;

  document.getElementById('zones').innerHTML = html;
}

function renderHealth() {
  const {hc} = DATA;
  let html = '<h2>健康检查</h2>';
  for (const c of hc) {
    html += `<div class="check">
      <span class="icon">${c.ok?'✅':'❌'}</span>
      <span class="zone-tag">Z${c.zone}</span>
      <span>${c.name}</span>
      <span style="color:var(--muted);font-size:.8em;margin-left:auto">${c.detail||''}</span>
    </div>`;
  }
  document.getElementById('health').innerHTML = html;
}

function toggleZone(el) {
  el.classList.toggle('open');
  el.nextElementSibling.classList.toggle('show');
}

async function viewFile(key) {
  let content = DATA.z0?.[key]?.content || '';
  showModal(DATA.z0?.[key]?.path || key, content);
}
async function viewRule(name) {
  const r = DATA.z1.rules.items.find(i=>i.name===name);
  if (r) showModal(name, r.content);
}
async function viewSkill(name) {
  const res = await fetch(API+`/api/file?path=.windsurf/skills/${name}/SKILL.md`);
  const d = await res.json();
  showModal(`skills/${name}/SKILL.md`, d.content||d.error);
}
async function viewAgent(path) {
  const res = await fetch(API+`/api/file?path=${encodeURIComponent(path)}`);
  const d = await res.json();
  showModal(path, d.content||d.error);
}

function showModal(title, content) {
  document.getElementById('modalTitle').textContent = title;
  document.getElementById('modalContent').textContent = content;
  document.getElementById('modal').classList.add('show');
}
function closeModal() { document.getElementById('modal').classList.remove('show'); }
document.addEventListener('keydown', e=>{ if(e.key==='Escape') closeModal(); });

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

    def _json(self, data, code=200):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, default=str).encode('utf-8'))

    def log_message(self, format, *args):
        pass  # Suppress request logs

if __name__ == '__main__':
    with socketserver.TCPServer(('127.0.0.1', PORT), Handler) as httpd:
        print(f'Windsurf Dashboard: http://localhost:{PORT}')
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print('\nStopped.')
