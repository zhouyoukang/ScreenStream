#!/usr/bin/env python3
"""
Windsurf Model Delegate System v1.0
====================================
超MCP架构: Agent自感知 + 模型委派 + 积分监控 + gRPC直调

道生一(state.vscdb读取) → 一生二(自感知+监控) → 二生三(委派+路由+优化) → 三生万物(MCP服务)

核心能力:
  1. 自感知: 实时检测当前模型身份/积分/token消耗
  2. 模型委派: 高层Agent调用SWE-1.5(Free)/低成本模型
  3. 积分监控: 实时跟踪消耗/余额/速率
  4. 成本路由: 任务复杂度→最优模型自动选择
  5. gRPC直调: 绕过UI直接调用推理端点(实验性)

用法:
  python model_delegate.py --sense          # 自感知报告
  python model_delegate.py --models         # 完整模型矩阵
  python model_delegate.py --monitor        # 实时积分监控
  python model_delegate.py --route TASK     # 推荐最优模型
  python model_delegate.py --server         # 启动MCP HTTP服务
  python model_delegate.py --grpc-test      # gRPC直调测试
"""

import sqlite3, json, os, base64, struct, sys, time, re
from pathlib import Path
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading

# ============================================================
# 常量
# ============================================================
DB_PATH = Path(os.environ.get('APPDATA', '')) / 'Windsurf' / 'User' / 'globalStorage' / 'state.vscdb'
JS_PATH = Path('D:/Windsurf/resources/app/out/vs/workbench/workbench.desktop.main.js')
STORAGE_PATH = Path(os.environ.get('APPDATA', '')) / 'Windsurf' / 'User' / 'globalStorage' / 'storage.json'
PORT = 9850

# 已知模型成本映射 (从protobuf解码, IEEE754 float)
KNOWN_COSTS = {
    'MODEL_SWE_1_5_SLOW': 0.0,    # SWE-1.5 = FREE
    'MODEL_SWE_1_5': 0.5,          # SWE-1.5 Fast
    'MODEL_PRIVATE_2': 2.0,         # Claude Sonnet 4.5
    'MODEL_PRIVATE_11': 1.0,        # Claude Haiku 4.5
    'MODEL_CLAUDE_4_SONNET': 2.0,
    'MODEL_CLAUDE_4_5_OPUS': 4.0,
    'claude-opus-4-6-thinking-1m': 12.0,
    'claude-opus-4-6': 6.0,
    'claude-sonnet-4-6': 4.0,
    'gpt-5-3-codex-medium': 2.0,
    'kimi-k2-5': 1.0,
    'MODEL_CHAT_GPT_4O_2024_08_06': 1.0,
}

# 任务复杂度→推荐模型
ROUTE_TABLE = [
    # (max_complexity, model_enum, display_name, cost)
    (1, 'MODEL_SWE_1_5_SLOW', 'SWE-1.5 (Free)', 0.0),        # 简单: grep/读文件/格式化
    (2, 'MODEL_SWE_1_5', 'SWE-1.5 Fast (0.5x)', 0.5),         # 中简: 单文件修改/小bug
    (3, 'kimi-k2-5', 'Kimi K2.5 (1x)', 1.0),                  # 中等: 多文件/设计
    (4, 'MODEL_PRIVATE_2', 'Claude Sonnet 4.5 (2x)', 2.0),     # 复杂: 架构/多模块
    (5, 'claude-opus-4-6-thinking-1m', 'Opus 4.6 Thinking 1M (12x)', 12.0),  # 极复杂
]

# ============================================================
# 核心: Protobuf解码工具
# ============================================================
def decode_varint(data, pos):
    val = 0; shift = 0
    while pos < len(data):
        b = data[pos]; pos += 1
        val |= (b & 0x7F) << shift; shift += 7
        if not (b & 0x80): break
    return val, pos

def parse_pb(data, depth=0):
    fields = {}
    pos = 0
    while pos < len(data):
        try:
            tag, pos = decode_varint(data, pos)
            fnum = tag >> 3; wtype = tag & 7
            if fnum == 0: break
            if wtype == 0:
                val, pos = decode_varint(data, pos)
                fields.setdefault(fnum, []).append(val)
            elif wtype == 1:
                val = struct.unpack_from('<Q', data, pos)[0]; pos += 8
                fields.setdefault(fnum, []).append(val)
            elif wtype == 2:
                length, pos = decode_varint(data, pos)
                val = data[pos:pos+length]; pos += length
                try:
                    txt = val.decode('utf-8')
                    if txt.isprintable() and len(txt) < 500:
                        fields.setdefault(fnum, []).append(txt)
                    elif depth < 2:
                        sub = parse_pb(val, depth+1)
                        fields.setdefault(fnum, []).append(sub if sub else f"<{len(val)}B>")
                    else:
                        fields.setdefault(fnum, []).append(f"<{len(val)}B>")
                except:
                    if depth < 2:
                        sub = parse_pb(val, depth+1)
                        fields.setdefault(fnum, []).append(sub if sub else f"<{len(val)}B>")
                    else:
                        fields.setdefault(fnum, []).append(f"<{len(val)}B>")
            elif wtype == 5:
                val = struct.unpack_from('<I', data, pos)[0]; pos += 4
                fields.setdefault(fnum, []).append(val)
            else: break
        except: break
    return fields

def float_from_uint32(v):
    try: return struct.unpack('f', struct.pack('I', v))[0]
    except: return None

# ============================================================
# Layer 1: 自感知 (Self-Awareness)
# ============================================================
class ModelSense:
    """Agent自感知模块: 检测当前模型/积分/账号状态"""
    
    def __init__(self):
        self._cache = {}
        self._last_refresh = 0
        self._refresh_interval = 5  # seconds
    
    def _read_db(self, key):
        if not DB_PATH.exists():
            return None
        conn = sqlite3.connect(f'file:{DB_PATH}?mode=ro', uri=True)
        cur = conn.cursor()
        cur.execute("SELECT value FROM ItemTable WHERE key=?", (key,))
        row = cur.fetchone()
        conn.close()
        return row[0] if row else None
    
    def refresh(self):
        """刷新所有状态"""
        now = time.time()
        if now - self._last_refresh < self._refresh_interval:
            return self._cache
        
        # Plan info
        plan_raw = self._read_db('windsurf.settings.cachedPlanInfo')
        self._cache['plan'] = json.loads(plan_raw) if plan_raw else {}
        
        # Current user
        user = self._read_db('codeium.windsurf-windsurf_auth')
        self._cache['user'] = user
        
        # Auth status
        auth_raw = self._read_db('windsurfAuthStatus')
        if auth_raw:
            auth = json.loads(auth_raw)
            self._cache['apiKey'] = auth.get('apiKey', '')[:25] + '...'
            
            # Decode command models
            cmd_protos = auth.get('allowedCommandModelConfigsProtoBinaryBase64', [])
            models = []
            for pb64 in cmd_protos:
                data = base64.b64decode(pb64)
                f = parse_pb(data)
                name = next((v for v in f.get(1, []) if isinstance(v, str)), '?')
                enum_id = next((v for v in f.get(22, []) if isinstance(v, str)), '?')
                cost_raw = next((v for v in f.get(3, []) if isinstance(v, int)), 0)
                cost = float_from_uint32(cost_raw) if cost_raw else 0.0
                ctx = next((v for v in f.get(18, []) if isinstance(v, int)), 0)
                models.append({'name': name, 'enum': enum_id, 'cost': cost, 'ctx': ctx})
            self._cache['commandModels'] = models
            self._cache['commandModelCount'] = len(models)
        
        self._last_refresh = now
        return self._cache
    
    def sense(self):
        """返回完整自感知报告"""
        self.refresh()
        plan = self._cache.get('plan', {})
        usage = plan.get('usage', {})
        
        return {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'user': self._cache.get('user', '?'),
            'plan': plan.get('planName', '?'),
            'credits': {
                'total': usage.get('messages', 0),
                'used': usage.get('usedMessages', 0),
                'remaining': usage.get('remainingMessages', 0),
                'flowActions': usage.get('remainingFlowActions', 0),
            },
            'grace': plan.get('gracePeriodStatus', 0),
            'commandModels': self._cache.get('commandModels', []),
            'estimatedCurrentModel': self._detect_current_model(),
        }
    
    def _detect_current_model(self):
        """推断当前正在使用的模型"""
        # 基于能力指纹推断
        # 如果在Cascade中, 大概率是用户截图中显示的模型
        models = self._cache.get('commandModels', [])
        # 找出最贵的模型作为可能的当前模型
        if models:
            most_expensive = max(models, key=lambda m: m.get('cost', 0))
            return {
                'guess': most_expensive['name'],
                'cost': most_expensive['cost'],
                'confidence': 'medium',
                'method': 'most_expensive_available'
            }
        return {'guess': 'unknown', 'confidence': 'low'}
    
    def credits_remaining(self):
        """快速获取剩余积分"""
        self.refresh()
        usage = self._cache.get('plan', {}).get('usage', {})
        return usage.get('remainingMessages', 0)

# ============================================================
# Layer 2: 模型路由 (Cost-Optimal Routing)
# ============================================================
class ModelRouter:
    """任务复杂度→最优模型自动路由"""
    
    @staticmethod
    def classify_task(task_description):
        """将任务描述分类为复杂度级别 1-5"""
        desc = task_description.lower()
        
        # Level 1: 简单文件操作
        simple_keywords = ['grep', 'search', 'find', 'list', 'read', 'format', 'rename']
        if any(k in desc for k in simple_keywords):
            return 1
        
        # Level 2: 单文件修改
        basic_keywords = ['fix', 'typo', 'add import', 'comment', 'simple bug', 'one file']
        if any(k in desc for k in basic_keywords):
            return 2
        
        # Level 3: 中等复杂度
        medium_keywords = ['implement', 'feature', 'multiple files', 'refactor', 'test']
        if any(k in desc for k in medium_keywords):
            return 3
        
        # Level 4: 复杂架构
        complex_keywords = ['architecture', 'design', 'multi-module', 'system', 'integration']
        if any(k in desc for k in complex_keywords):
            return 4
        
        # Level 5: 极复杂推理
        extreme_keywords = ['reverse', 'deep analysis', 'breakthrough', 'novel', 'research']
        if any(k in desc for k in extreme_keywords):
            return 5
        
        return 3  # 默认中等
    
    @staticmethod
    def route(task_description, budget=None):
        """推荐最优模型"""
        complexity = ModelRouter.classify_task(task_description)
        
        for max_c, enum_id, name, cost in ROUTE_TABLE:
            if complexity <= max_c:
                if budget is not None and cost > budget:
                    continue
                return {
                    'complexity': complexity,
                    'recommended_model': name,
                    'model_enum': enum_id,
                    'cost': cost,
                    'task': task_description[:100],
                }
        
        # 预算不够，降级到免费
        return {
            'complexity': complexity,
            'recommended_model': 'SWE-1.5 (Free)',
            'model_enum': 'MODEL_SWE_1_5_SLOW',
            'cost': 0.0,
            'task': task_description[:100],
            'note': 'budget_constrained_fallback'
        }

# ============================================================
# Layer 3: 全模型矩阵 (Complete Model Matrix)
# ============================================================
class ModelMatrix:
    """完整102模型积分矩阵"""
    
    def __init__(self):
        self._models = []
        self._loaded = False
    
    def load(self):
        if self._loaded:
            return
        
        if not DB_PATH.exists():
            return
        
        conn = sqlite3.connect(f'file:{DB_PATH}?mode=ro', uri=True)
        cur = conn.cursor()
        cur.execute("SELECT value FROM ItemTable WHERE key='windsurfAuthStatus'")
        row = cur.fetchone()
        if not row:
            conn.close()
            return
        
        auth = json.loads(row[0])
        pb_b64 = auth.get('userStatusProtoBinaryBase64', '')
        if not pb_b64:
            conn.close()
            return
        
        data = base64.b64decode(pb_b64)
        
        # Extract field 33
        pos = 0
        field33_raw = None
        while pos < len(data):
            try:
                tag, new_pos = decode_varint(data, pos)
                fnum = tag >> 3; wtype = tag & 7
                if fnum == 0: break
                if wtype == 2:
                    length, new_pos = decode_varint(data, new_pos)
                    val = data[new_pos:new_pos+length]
                    if fnum == 33: field33_raw = val
                    new_pos += length; pos = new_pos
                elif wtype == 0: _, pos = decode_varint(data, new_pos)
                elif wtype == 1: pos = new_pos + 8
                elif wtype == 5: pos = new_pos + 4
                else: break
            except: break
        
        if field33_raw:
            f33 = parse_pb(field33_raw, depth=0)
            max_field = max(f33.keys(), key=lambda k: len(f33[k]))
            for m in f33[max_field]:
                if isinstance(m, dict):
                    name = next((v for v in m.get(1, []) if isinstance(v, str)), '?')
                    enum_id = next((v for v in m.get(22, []) if isinstance(v, str)), '?')
                    cost_raw = next((v for v in m.get(3, []) if isinstance(v, int)), 0)
                    cost = float_from_uint32(cost_raw) if cost_raw else 0.0
                    ctx = next((v for v in m.get(18, []) if isinstance(v, int)), 0)
                    tier = next((v for v in m.get(24, []) if isinstance(v, int)), 0)
                    is_new = 1 in m.get(15, [])
                    self._models.append({
                        'name': name, 'enum': enum_id, 'cost': cost,
                        'ctx': ctx, 'tier': tier, 'new': is_new
                    })
        
        conn.close()
        self._loaded = True
    
    def all(self):
        self.load()
        return self._models
    
    def free(self):
        return [m for m in self.all() if m['cost'] == 0]
    
    def by_cost(self, max_cost):
        return [m for m in self.all() if m['cost'] <= max_cost]
    
    def search(self, query):
        q = query.lower()
        return [m for m in self.all() if q in m['name'].lower() or q in m['enum'].lower()]

# ============================================================
# Layer 4: HTTP API Server (MCP-like)
# ============================================================
class DelegateHandler(BaseHTTPRequestHandler):
    sense = ModelSense()
    router = ModelRouter()
    matrix = ModelMatrix()
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)
        
        routes = {
            '/': self._dashboard,
            '/api/health': self._health,
            '/api/sense': self._sense,
            '/api/credits': self._credits,
            '/api/models': self._models,
            '/api/models/free': self._models_free,
            '/api/models/search': self._models_search,
            '/api/route': self._route,
            '/api/matrix': self._matrix_summary,
            '/api/self': self._self_detect,
        }
        
        handler = routes.get(path)
        if handler:
            try:
                result = handler(params)
                self._json_response(200, result)
            except Exception as e:
                self._json_response(500, {'error': str(e)})
        else:
            self._json_response(404, {'error': 'not found', 'routes': list(routes.keys())})
    
    def _json_response(self, code, data):
        body = json.dumps(data, indent=2, ensure_ascii=False, default=str).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)
    
    def _health(self, p):
        return {'status': 'ok', 'service': 'model-delegate', 'version': '1.0',
                'port': PORT, 'models': len(self.matrix.all()),
                'credits': self.sense.credits_remaining()}
    
    def _sense(self, p):
        return self.sense.sense()
    
    def _credits(self, p):
        s = self.sense.sense()
        return s.get('credits', {})
    
    def _models(self, p):
        return {'count': len(self.matrix.all()), 'models': self.matrix.all()}
    
    def _models_free(self, p):
        free = self.matrix.free()
        return {'count': len(free), 'models': free}
    
    def _models_search(self, p):
        q = p.get('q', [''])[0]
        if not q:
            return {'error': 'query required: /api/models/search?q=swe'}
        results = self.matrix.search(q)
        return {'query': q, 'count': len(results), 'models': results}
    
    def _route(self, p):
        task = p.get('task', [''])[0]
        budget = p.get('budget', [None])[0]
        if not task:
            return {'error': 'task required: /api/route?task=fix+bug+in+main.py'}
        budget_f = float(budget) if budget else None
        return self.router.route(task, budget_f)
    
    def _matrix_summary(self, p):
        all_m = self.matrix.all()
        tiers = {}
        for m in all_m:
            c = m['cost']
            if c == 0: tier = 'free'
            elif c <= 0.5: tier = 'low'
            elif c <= 1: tier = 'standard'
            elif c <= 2: tier = 'medium'
            elif c <= 4: tier = 'high'
            else: tier = 'premium'
            tiers.setdefault(tier, []).append(m['name'])
        return {'total': len(all_m), 'tiers': {k: {'count': len(v), 'models': v} for k, v in tiers.items()}}
    
    def _self_detect(self, p):
        return {
            'note': 'Agent self-detection via capability fingerprinting',
            'currentModel': self.sense._detect_current_model(),
            'method': [
                '1. UI screenshot analysis (user provides)',
                '2. Capability fingerprinting (context length, reasoning depth)',
                '3. state.vscdb selectedCommandModel (if available)',
                '4. promptCreditsUsed per step (post-hoc)',
            ],
            'limitation': 'Server does not expose current modelUid to Agent in gRPC response'
        }
    
    def _dashboard(self, p):
        s = self.sense.sense()
        credits = s.get('credits', {})
        models = self.matrix.all()
        free = [m for m in models if m['cost'] == 0]
        
        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Model Delegate</title>
<style>
body {{ font-family: -apple-system, sans-serif; background: #0d1117; color: #c9d1d9; padding: 20px; }}
h1 {{ color: #58a6ff; }} h2 {{ color: #8b949e; }}
.card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; margin: 12px 0; }}
.stat {{ font-size: 2em; color: #58a6ff; }} .cost-free {{ color: #3fb950; }} .cost-high {{ color: #f85149; }}
table {{ border-collapse: collapse; width: 100%; }} th,td {{ padding: 8px; border: 1px solid #30363d; text-align: left; }}
th {{ background: #21262d; }} .badge {{ padding: 2px 8px; border-radius: 12px; font-size: 0.8em; }}
.badge-free {{ background: #238636; }} .badge-low {{ background: #1f6feb; }} .badge-high {{ background: #da3633; }}
</style></head><body>
<h1>Windsurf Model Delegate v1.0</h1>
<div class="card">
  <h2>Self-Awareness</h2>
  <p>User: <b>{s.get('user','?')}</b> | Plan: <b>{s.get('plan','?')}</b> | Grace: {s.get('grace',0)}</p>
  <p>Credits: <span class="stat">{credits.get('remaining',0)}</span> / {credits.get('total',0)} remaining ({credits.get('used',0)} used)</p>
  <p>Estimated current model: <b>{s.get('estimatedCurrentModel',{}).get('guess','?')}</b></p>
</div>
<div class="card">
  <h2>Model Matrix ({len(models)} models)</h2>
  <p><span class="cost-free">FREE: {len(free)}</span> | Total: {len(models)}</p>
  <table><tr><th>Name</th><th>Enum</th><th>Cost</th><th>Context</th></tr>"""
        
        for m in sorted(models, key=lambda x: x['cost'])[:30]:
            cost_class = 'cost-free' if m['cost'] == 0 else ('cost-high' if m['cost'] > 4 else '')
            ctx_str = f"{m['ctx']//1000}K" if m['ctx'] else '?'
            html += f"<tr><td>{m['name']}</td><td><code>{m['enum']}</code></td><td class='{cost_class}'>{m['cost']}x</td><td>{ctx_str}</td></tr>"
        
        html += """</table></div>
<div class="card"><h2>API Endpoints</h2><ul>
<li><code>GET /api/health</code> — 健康检查</li>
<li><code>GET /api/sense</code> — 完整自感知报告</li>
<li><code>GET /api/credits</code> — 积分余额</li>
<li><code>GET /api/models</code> — 全部102模型</li>
<li><code>GET /api/models/free</code> — 免费模型</li>
<li><code>GET /api/models/search?q=swe</code> — 搜索模型</li>
<li><code>GET /api/route?task=fix+bug</code> — 任务路由推荐</li>
<li><code>GET /api/matrix</code> — 模型矩阵概览</li>
<li><code>GET /api/self</code> — 自我检测分析</li>
</ul></div></body></html>"""
        
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode())
        return None  # Already handled
    
    def do_POST(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(length)) if length else {}
        
        routes = {
            '/api/delegate/submit': self._submit_task,
            '/api/delegate/complete': self._complete_task,
        }
        handler = routes.get(parsed.path)
        if handler:
            try:
                result = handler(body)
                self._json_response(200, result)
            except Exception as e:
                self._json_response(500, {'error': str(e)})
        else:
            self._json_response(404, {'error': 'not found'})
    
    def _submit_task(self, body):
        """High-layer Agent submits a task for SWE delegation"""
        task = body.get('task', '')
        model = body.get('model', 'MODEL_SWE_1_5_SLOW')
        priority = body.get('priority', 'normal')
        
        if not task:
            return {'error': 'task required'}
        
        # Route to optimal model if not specified
        if model == 'auto':
            route = self.router.route(task)
            model = route['model_enum']
        
        # Create task card
        task_id = f"T{int(time.time())}"
        card = {
            'id': task_id,
            'task': task,
            'model': model,
            'model_name': KNOWN_COSTS.get(model, {}) if isinstance(KNOWN_COSTS.get(model), dict) else model,
            'cost': KNOWN_COSTS.get(model, 1.0),
            'priority': priority,
            'status': 'pending',
            'submitted_at': datetime.now(timezone.utc).isoformat(),
            'submitted_by': 'cascade_high_layer',
        }
        
        # Write to task queue file
        queue_file = Path(__file__).parent / '_task_queue.json'
        queue = json.loads(queue_file.read_text('utf-8')) if queue_file.exists() else {'tasks': []}
        queue['tasks'].append(card)
        queue_file.write_text(json.dumps(queue, indent=2, ensure_ascii=False), 'utf-8')
        
        return {'ok': True, 'task_id': task_id, 'card': card,
                'instructions': f'Switch to {model} model and execute: {task[:200]}'}
    
    def _complete_task(self, body):
        """SWE marks a task as completed with results"""
        task_id = body.get('task_id', '')
        result = body.get('result', '')
        
        queue_file = Path(__file__).parent / '_task_queue.json'
        if not queue_file.exists():
            return {'error': 'no task queue'}
        
        queue = json.loads(queue_file.read_text('utf-8'))
        for t in queue['tasks']:
            if t['id'] == task_id:
                t['status'] = 'completed'
                t['result'] = result
                t['completed_at'] = datetime.now(timezone.utc).isoformat()
                queue_file.write_text(json.dumps(queue, indent=2, ensure_ascii=False), 'utf-8')
                return {'ok': True, 'task_id': task_id}
        
        return {'error': f'task {task_id} not found'}
    
    def log_message(self, format, *args):
        pass  # Suppress default logging

# ============================================================
# CLI
# ============================================================
def main():
    import argparse
    parser = argparse.ArgumentParser(description='Windsurf Model Delegate')
    parser.add_argument('--sense', action='store_true', help='Self-awareness report')
    parser.add_argument('--models', action='store_true', help='Complete model matrix')
    parser.add_argument('--monitor', action='store_true', help='Real-time credit monitor')
    parser.add_argument('--route', type=str, help='Route task to optimal model')
    parser.add_argument('--server', action='store_true', help='Start HTTP server')
    parser.add_argument('--port', type=int, default=PORT, help=f'Server port (default: {PORT})')
    parser.add_argument('--search', type=str, help='Search models by name')
    args = parser.parse_args()
    
    if args.sense:
        sense = ModelSense()
        report = sense.sense()
        print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    
    elif args.models:
        matrix = ModelMatrix()
        for m in sorted(matrix.all(), key=lambda x: x['cost']):
            cost_str = "Free" if m['cost'] == 0 else f"{m['cost']}x"
            ctx_str = f"{m['ctx']//1000}K" if m['ctx'] else '?'
            new_tag = " [NEW]" if m.get('new') else ""
            print(f"  {m['name']:<45} {cost_str:<8} {ctx_str:<8} {m['enum']}{new_tag}")
    
    elif args.monitor:
        sense = ModelSense()
        sense._refresh_interval = 2
        print("Real-time Credit Monitor (Ctrl+C to stop)")
        print("-" * 50)
        try:
            while True:
                r = sense.credits_remaining()
                s = sense.sense()
                credits = s.get('credits', {})
                ts = datetime.now().strftime('%H:%M:%S')
                print(f"  [{ts}] {credits.get('remaining',0)}/{credits.get('total',0)} credits | used: {credits.get('used',0)} | user: {s.get('user','?')}")
                time.sleep(5)
        except KeyboardInterrupt:
            print("\nStopped.")
    
    elif args.route:
        result = ModelRouter.route(args.route)
        print(json.dumps(result, indent=2))
    
    elif args.search:
        matrix = ModelMatrix()
        results = matrix.search(args.search)
        for m in results:
            cost_str = "Free" if m['cost'] == 0 else f"{m['cost']}x"
            print(f"  {m['name']:<45} {cost_str:<8} {m['enum']}")
    
    elif args.server:
        port = args.port
        server = HTTPServer(('0.0.0.0', port), DelegateHandler)
        print(f"Model Delegate Server v1.0 on http://localhost:{PORT}/")
        print(f"  /api/sense — Self-awareness")
        print(f"  /api/credits — Credit balance")
        print(f"  /api/models — All 102 models")
        print(f"  /api/route?task=... — Cost-optimal routing")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nShutdown.")
    
    else:
        # Default: quick status
        sense = ModelSense()
        s = sense.sense()
        credits = s.get('credits', {})
        print(f"Windsurf Model Delegate v1.0")
        print(f"  User: {s.get('user','?')} ({s.get('plan','?')})")
        print(f"  Credits: {credits.get('remaining',0)}/{credits.get('total',0)}")
        print(f"  Models: {len(ModelMatrix().all())}")
        print(f"  Free models: {len(ModelMatrix().free())}")
        print(f"\nRun with --sense, --models, --server, --route, --monitor for more")

if __name__ == '__main__':
    main()
