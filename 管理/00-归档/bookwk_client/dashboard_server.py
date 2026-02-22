# -*- coding: utf-8 -*-
"""BookWK 本地Web仪表盘 — 代理API调用，前端展示全站数据"""
import sys, io, json, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, ".")

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from bookwk_api import BookWKClient

PORT = 9090
client = None

class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # suppress logs

    def _json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, html):
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == "/":
            self._html(DASHBOARD_HTML)
        elif path == "/api/userinfo":
            self._json(client.get_user_info())
        elif path == "/api/courses":
            self._json(client.get_courses())
        elif path == "/api/userlist":
            self._json(client.get_user_list())
        elif path == "/api/levels":
            self._json(client.get_agent_levels())
        elif path == "/api/logs":
            self._json(client.get_logs())
        elif path == "/api/help":
            self._json(client.get_help_list())
        elif path == "/api/favorites":
            self._json(client.get_favorites())
        elif path == "/api/call":
            act = params.get("act", [""])[0]
            api = params.get("api", ["sub"])[0]
            if act:
                self._json(client.call(act, api))
            else:
                self._json({"code": -1, "msg": "missing act param"})
        else:
            self._json({"code": 404, "msg": "not found"}, 404)

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>BookWK Dashboard — 29网课平台本地控制台</title>
<script src="https://unpkg.com/vue@3/dist/vue.global.prod.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
:root {
  --bg: #0f172a; --surface: #1e293b; --surface2: #334155;
  --border: #475569; --text: #e2e8f0; --text2: #94a3b8;
  --primary: #3b82f6; --success: #10b981; --warning: #f59e0b;
  --danger: #ef4444; --accent: #8b5cf6;
}
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:'Inter',sans-serif; background:var(--bg); color:var(--text); min-height:100vh; }
.header { background:linear-gradient(135deg,#1e3a5f,#0f172a); padding:20px 32px; border-bottom:1px solid var(--border); display:flex; justify-content:space-between; align-items:center; }
.header h1 { font-size:22px; font-weight:700; }
.header h1 span { color:var(--primary); }
.header .badge { background:var(--success); color:#fff; padding:4px 12px; border-radius:20px; font-size:12px; font-weight:600; }
.container { max-width:1400px; margin:0 auto; padding:24px; }
.stats-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:16px; margin-bottom:24px; }
.stat-card { background:var(--surface); border:1px solid var(--border); border-radius:12px; padding:20px; transition:transform .2s; }
.stat-card:hover { transform:translateY(-2px); }
.stat-card .label { color:var(--text2); font-size:12px; text-transform:uppercase; letter-spacing:1px; margin-bottom:8px; }
.stat-card .value { font-size:28px; font-weight:700; }
.stat-card .value.money { color:var(--success); }
.stat-card .value.orders { color:var(--primary); }
.stat-card .value.users { color:var(--accent); }
.stat-card .value.courses { color:var(--warning); }
.tabs { display:flex; gap:4px; margin-bottom:20px; background:var(--surface); padding:4px; border-radius:10px; }
.tab { padding:10px 20px; border-radius:8px; cursor:pointer; font-size:14px; font-weight:500; color:var(--text2); transition:all .2s; border:none; background:none; }
.tab:hover { color:var(--text); }
.tab.active { background:var(--primary); color:#fff; }
.panel { background:var(--surface); border:1px solid var(--border); border-radius:12px; overflow:hidden; }
.panel-header { padding:16px 20px; border-bottom:1px solid var(--border); display:flex; justify-content:space-between; align-items:center; }
.panel-header h2 { font-size:16px; font-weight:600; }
.panel-header .count { color:var(--text2); font-size:13px; }
table { width:100%; border-collapse:collapse; }
th { text-align:left; padding:12px 16px; color:var(--text2); font-size:12px; font-weight:600; text-transform:uppercase; letter-spacing:1px; border-bottom:1px solid var(--border); }
td { padding:12px 16px; border-bottom:1px solid rgba(71,85,105,.3); font-size:13px; }
tr:hover { background:rgba(59,130,246,.05); }
.price { color:var(--success); font-weight:600; }
.status-active { color:var(--success); }
.status-inactive { color:var(--danger); }
.search-box { background:var(--surface2); border:1px solid var(--border); border-radius:8px; padding:8px 14px; color:var(--text); font-size:14px; width:300px; outline:none; }
.search-box:focus { border-color:var(--primary); }
.info-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:16px; padding:20px; }
.info-item { display:flex; justify-content:space-between; padding:10px 14px; background:var(--surface2); border-radius:8px; }
.info-item .k { color:var(--text2); font-size:13px; }
.info-item .v { font-weight:600; font-size:13px; }
.loading { text-align:center; padding:40px; color:var(--text2); }
.api-tester { padding:20px; }
.api-tester input { background:var(--surface2); border:1px solid var(--border); border-radius:8px; padding:10px 14px; color:var(--text); font-size:14px; width:200px; margin-right:8px; }
.api-tester button { background:var(--primary); border:none; color:#fff; padding:10px 20px; border-radius:8px; cursor:pointer; font-weight:600; }
.api-tester button:hover { background:#2563eb; }
.api-result { background:#0d1117; border-radius:8px; padding:16px; margin-top:12px; font-family:'Consolas',monospace; font-size:12px; white-space:pre-wrap; max-height:400px; overflow-y:auto; color:#c9d1d9; }
.level-badge { display:inline-block; padding:2px 10px; border-radius:12px; font-size:11px; font-weight:600; }
.level-top { background:rgba(139,92,246,.2); color:#a78bfa; }
.level-base { background:rgba(59,130,246,.2); color:#60a5fa; }
.level-entry { background:rgba(16,185,129,.2); color:#34d399; }
.scroll-table { max-height:500px; overflow-y:auto; }
</style>
</head>
<body>
<div id="app">
  <div class="header">
    <h1>📊 <span>BookWK</span> Dashboard — 29网课平台本地控制台</h1>
    <div style="display:flex;gap:12px;align-items:center">
      <span v-if="user" style="color:var(--text2);font-size:13px">UID:{{user.uid}} | {{user.user}}</span>
      <span class="badge" v-if="user">余额 ¥{{user.money}}</span>
    </div>
  </div>

  <div class="container">
    <!-- Stats -->
    <div class="stats-grid" v-if="user">
      <div class="stat-card"><div class="label">账户余额</div><div class="value money">¥{{user.money}}</div></div>
      <div class="stat-card"><div class="label">订单总数</div><div class="value orders">{{user.dd}}</div></div>
      <div class="stat-card"><div class="label">下级用户</div><div class="value users">{{user.zcz}}</div></div>
      <div class="stat-card"><div class="label">课程总数</div><div class="value courses">{{courseCount}}</div></div>
      <div class="stat-card"><div class="label">代理等级</div><div class="value" style="color:var(--accent)">顶级代理</div></div>
      <div class="stat-card"><div class="label">费率</div><div class="value" style="color:var(--warning)">{{user.addprice}}</div></div>
    </div>

    <!-- Tabs -->
    <div class="tabs">
      <button class="tab" :class="{active:tab==='courses'}" @click="tab='courses'">课程目录 ({{courseCount}})</button>
      <button class="tab" :class="{active:tab==='levels'}" @click="tab='levels'">代理等级</button>
      <button class="tab" :class="{active:tab==='userinfo'}" @click="tab='userinfo'">账户详情</button>
      <button class="tab" :class="{active:tab==='help'}" @click="tab='help'">帮助文档</button>
      <button class="tab" :class="{active:tab==='api'}" @click="tab='api'">API测试器</button>
    </div>

    <!-- Courses -->
    <div class="panel" v-if="tab==='courses'">
      <div class="panel-header">
        <h2>课程目录</h2>
        <div style="display:flex;gap:12px;align-items:center">
          <span class="count">共 {{filteredCourses.length}} 门</span>
          <input class="search-box" v-model="search" placeholder="搜索课程名/编号...">
        </div>
      </div>
      <div class="scroll-table">
        <table>
          <thead><tr><th>CID</th><th>课程名称</th><th>编号</th><th>价格</th><th>秒刷</th><th>状态</th></tr></thead>
          <tbody>
            <tr v-for="c in filteredCourses.slice(0,200)" :key="c.cid">
              <td>{{c.cid}}</td>
              <td>{{c.name}}</td>
              <td style="color:var(--text2)">{{c.noun}}</td>
              <td class="price">¥{{c.price.toFixed(2)}}</td>
              <td>{{c.miaoshua?'是':'否'}}</td>
              <td><span :class="c.status==='1'?'status-active':'status-inactive'">{{c.status==='1'?'上架':'下架'}}</span></td>
            </tr>
          </tbody>
        </table>
        <div v-if="filteredCourses.length>200" style="padding:12px;text-align:center;color:var(--text2);font-size:13px">
          显示前200条，共{{filteredCourses.length}}条 (使用搜索筛选)
        </div>
      </div>
    </div>

    <!-- Agent Levels -->
    <div class="panel" v-if="tab==='levels'">
      <div class="panel-header"><h2>代理等级体系</h2></div>
      <table>
        <thead><tr><th>排序</th><th>等级名称</th><th>费率</th><th>利润空间</th></tr></thead>
        <tbody>
          <tr v-for="l in levels" :key="l.sort+l.rate">
            <td>{{l.sort}}</td>
            <td><span class="level-badge" :class="l.name.includes('顶级')?'level-top':l.name.includes('基础')?'level-base':'level-entry'">{{l.name}}</span></td>
            <td class="price">{{l.rate}}</td>
            <td style="color:var(--text2)">{{((1-parseFloat(l.rate))*100).toFixed(1)}}%</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- User Info -->
    <div class="panel" v-if="tab==='userinfo' && user">
      <div class="panel-header"><h2>账户详细信息 (16字段)</h2></div>
      <div class="info-grid">
        <div class="info-item" v-for="(v,k) in userFields" :key="k"><span class="k">{{k}}</span><span class="v">{{v}}</span></div>
      </div>
    </div>

    <!-- Help -->
    <div class="panel" v-if="tab==='help'">
      <div class="panel-header"><h2>帮助文档</h2></div>
      <div v-for="h in helpList" :key="h.id" style="padding:16px 20px;border-bottom:1px solid var(--border)">
        <div style="font-weight:600;margin-bottom:8px">{{h.title}}</div>
        <div style="color:var(--text2);font-size:13px;line-height:1.6" v-html="h.content"></div>
        <div style="color:var(--text2);font-size:11px;margin-top:8px">更新: {{h.upTime}}</div>
      </div>
    </div>

    <!-- API Tester -->
    <div class="panel" v-if="tab==='api'">
      <div class="panel-header"><h2>API 测试器</h2></div>
      <div class="api-tester">
        <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
          <select v-model="apiType" style="background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:10px;color:var(--text)">
            <option value="sub">apisub</option><option value="sb">apisb</option>
          </select>
          <input v-model="apiAct" placeholder="act名称 (如 userinfo)">
          <button @click="testApi">执行</button>
        </div>
        <div style="margin-top:8px;color:var(--text2);font-size:12px">
          已验证: userinfo, userlist, getclass, getclassfl, getFavorites, adddjlist, loglist, help_list, user_notice
        </div>
        <div class="api-result" v-if="apiResult">{{apiResult}}</div>
      </div>
    </div>
  </div>
</div>

<script>
const {createApp,ref,computed,onMounted} = Vue;
createApp({
  setup(){
    const tab = ref('courses');
    const user = ref(null);
    const courses = ref([]);
    const levels = ref([]);
    const helpList = ref([]);
    const search = ref('');
    const apiType = ref('sub');
    const apiAct = ref('');
    const apiResult = ref('');
    const courseCount = computed(()=>courses.value.length);

    const filteredCourses = computed(()=>{
      if(!search.value) return courses.value;
      const q = search.value.toLowerCase();
      return courses.value.filter(c=>c.name.toLowerCase().includes(q)||c.cid.includes(q)||c.noun.toLowerCase().includes(q));
    });

    const userFields = computed(()=>{
      if(!user.value) return {};
      const skip = ['notice','sjnotice','dailitongji'];
      const o = {};
      for(const[k,v] of Object.entries(user.value)){
        if(k==='code'||k==='msg'||skip.includes(k)) continue;
        o[k] = v;
      }
      return o;
    });

    const load = async(url)=>{
      const r = await fetch(url);
      return r.json();
    };

    const testApi = async()=>{
      apiResult.value = 'Loading...';
      try{
        const r = await load(`/api/call?act=${apiAct.value}&api=${apiType.value}`);
        apiResult.value = JSON.stringify(r, null, 2);
      }catch(e){ apiResult.value = 'Error: '+e.message; }
    };

    onMounted(async()=>{
      const [u,c,l,h] = await Promise.all([
        load('/api/userinfo'), load('/api/courses'),
        load('/api/levels'), load('/api/help')
      ]);
      if(u.code===1) user.value = u;
      if(c.code===1) courses.value = c.data||[];
      if(l.code===1) levels.value = l.data||[];
      if(h.code===1) helpList.value = h.data||[];
    });

    return {tab,user,courses,levels,helpList,search,courseCount,filteredCourses,userFields,apiType,apiAct,apiResult,testApi};
  }
}).mount('#app');
</script>
</body>
</html>"""

def main():
    global client
    user = os.environ.get("BOOKWK_USER", "3183561752")
    pwd = os.environ.get("BOOKWK_PASS", "3183561752")
    
    print(f"[*] Initializing BookWK client...")
    client = BookWKClient()
    r = client.login_password(user, pwd)
    if r.get("code") != 1:
        print(f"[!] Login failed: {r.get('msg')}")
        sys.exit(1)
    
    print(f"[*] Starting dashboard on http://localhost:{PORT}")
    server = HTTPServer(("127.0.0.1", PORT), DashboardHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Shutting down")
        server.shutdown()

if __name__ == "__main__":
    main()
