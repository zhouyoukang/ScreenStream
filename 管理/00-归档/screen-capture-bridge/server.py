"""
Screen Capture Bridge — Web UI + REST API Server

参考OBS的用户体验：录制控制台 + 状态监控 + 分段管理 + AI分析

启动: python server.py [--port 9905] [--dir "D:\\屏幕录制\\ai_segments"]
访问: http://localhost:9905
"""
import json
import os
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from bridge import ScreenBridge, EditDecisionList, check_ffmpeg, score_segment, QUALITY_PRESETS, DEFAULT_DIR

DEFAULT_PORT = 9905

# ── 全局状态 ──
recording_process = None
recording_start_time = None
recording_config = {}


def enumerate_sources() -> list:
    """枚举所有可用录制源"""
    sources = [
        {'id': 'desktop', 'name': '桌面 (主屏)', 'type': 'screen'},
        {'id': 'dual', 'name': '双屏 (全部)', 'type': 'screen'},
    ]
    try:
        r = subprocess.run(['ffmpeg', '-list_devices', 'true', '-f', 'dshow', '-i', 'dummy'],
                           capture_output=True, text=True, timeout=5)
        for line in (r.stderr or '').split('\n'):
            if '(video)' in line and '"' in line:
                name = line.split('"')[1]
                sources.append({'id': f'cam:{name}', 'name': f'📷 {name}', 'type': 'camera'})
    except Exception:
        pass
    return sources


def start_recording(watch_dir: str, segment_min: int = 2, quality: str = 'low',
                    source: str = 'desktop'):
    """启动FFmpeg分段录制（支持桌面/双屏/摄像头）"""
    global recording_process, recording_start_time, recording_config

    if recording_process and recording_process.poll() is None:
        return {'error': '已在录制中', 'pid': recording_process.pid}

    outdir = Path(watch_dir)
    outdir.mkdir(parents=True, exist_ok=True)

    preset = QUALITY_PRESETS.get(quality, QUALITY_PRESETS['low'])
    seg_seconds = segment_min * 60
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    src_tag = source.replace(':', '_').replace(' ', '')[:20]
    out_pattern = str(outdir / f"ai_seg_{ts}_{src_tag}_%03d.ts")

    # 构建输入源参数
    if source.startswith('cam:'):
        cam_name = source[4:]
        cmd = ['ffmpeg', '-y', '-f', 'dshow', '-i', f'video={cam_name}',
               '-c:v', 'libx264', '-preset', preset['preset'], '-crf', str(preset['crf']),
               '-force_key_frames', f'expr:gte(t,n_forced*{seg_seconds})']
    elif source == 'dual':
        cmd = ['ffmpeg', '-y', '-f', 'gdigrab', '-framerate', str(preset['fps']),
               '-i', 'desktop', '-c:v', 'libx264', '-preset', preset['preset'],
               '-crf', str(preset['crf']),
               '-force_key_frames', f'expr:gte(t,n_forced*{seg_seconds})']
        # dual: 不缩放，保留全虚拟桌面分辨率
        preset = {**preset, 'scale': None}
    else:  # desktop (default)
        cmd = ['ffmpeg', '-y', '-f', 'gdigrab', '-framerate', str(preset['fps']),
               '-i', 'desktop', '-c:v', 'libx264', '-preset', preset['preset'],
               '-crf', str(preset['crf']),
               '-force_key_frames', f'expr:gte(t,n_forced*{seg_seconds})']

    if preset.get('scale'):
        cmd += ['-vf', f"scale={preset['scale']}:force_original_aspect_ratio=decrease"]

    cmd += ['-f', 'segment', '-segment_time', str(seg_seconds),
            '-reset_timestamps', '1', '-segment_format', 'mpegts',
            out_pattern]

    log_path = outdir / f"ffmpeg_{ts}.log"
    log_fh = open(log_path, 'w', encoding='utf-8', errors='replace')

    recording_process = subprocess.Popen(
        cmd, stdout=subprocess.DEVNULL, stderr=log_fh,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
    )

    time.sleep(1)
    if recording_process.poll() is not None:
        log_fh.close()
        return {'error': 'FFmpeg启动失败', 'log': str(log_path)}

    recording_start_time = time.time()
    recording_config = {
        'quality': quality, 'segment_min': segment_min,
        'pattern': out_pattern, 'log': str(log_path), 'pid': recording_process.pid,
    }
    # 通知bridge哪些文件正在录制（前缀匹配）
    prefix = out_pattern.split('%')[0] if '%' in out_pattern else out_pattern
    BridgeHandler.bridge.set_recording_prefix(prefix)
    return {'status': 'recording', **recording_config}


def stop_recording():
    """停止录屏"""
    global recording_process, recording_start_time, recording_config
    if not recording_process or recording_process.poll() is not None:
        return {'status': 'not_recording'}

    elapsed = time.time() - recording_start_time if recording_start_time else 0
    recording_process.terminate()
    try:
        recording_process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        recording_process.kill()

    result = {
        'status': 'stopped',
        'elapsed': round(elapsed),
        'elapsed_str': f"{int(elapsed//60)}m{int(elapsed%60)}s",
    }
    recording_process = None
    recording_start_time = None
    recording_config = {}
    BridgeHandler.bridge.set_recording_prefix(None)
    return result


def get_recording_status():
    """获取录制状态"""
    global recording_process, recording_start_time, recording_config
    if recording_process and recording_process.poll() is None:
        elapsed = time.time() - recording_start_time if recording_start_time else 0
        seg_sec = recording_config.get('segment_min', 2) * 60
        seg_progress = (elapsed % seg_sec) / seg_sec if seg_sec > 0 else 0
        return {
            'recording': True, 'elapsed': round(elapsed),
            'elapsed_str': f"{int(elapsed//60)}m{int(elapsed%60)}s",
            'segment_progress': round(seg_progress, 3),
            'segment_remaining': round(seg_sec - (elapsed % seg_sec)),
            **recording_config,
        }
    return {'recording': False}


def get_disk_info(watch_dir: str) -> dict:
    """获取磁盘空间信息"""
    import shutil
    try:
        usage = shutil.disk_usage(watch_dir)
        return {
            'total_gb': round(usage.total / (1024**3), 1),
            'free_gb': round(usage.free / (1024**3), 1),
            'used_pct': round((usage.used / usage.total) * 100, 1),
        }
    except Exception:
        return {'total_gb': 0, 'free_gb': 0, 'used_pct': 0}


# ── HTML 前端 ──

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Screen Capture Bridge</title>
<style>
:root {
  --bg: #1a1a2e; --surface: #16213e; --surface2: #0f3460;
  --accent: #e94560; --accent2: #533483; --text: #eee; --text2: #aaa;
  --green: #00d26a; --yellow: #ffc107; --red: #ff4757;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; }

.header { background: var(--surface); padding: 12px 24px; display: flex; align-items: center; gap: 16px; border-bottom: 1px solid #333; }
.header h1 { font-size: 18px; font-weight: 600; }
.header .status-dot { width: 10px; height: 10px; border-radius: 50%; }
.header .status-dot.idle { background: var(--text2); }
.header .status-dot.recording { background: var(--red); animation: pulse 1s infinite; }
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }
.header .elapsed { font-family: monospace; font-size: 14px; color: var(--text2); }
.header .ffmpeg-badge { background: var(--green); color: #000; font-size: 11px; padding: 2px 8px; border-radius: 4px; font-weight: 600; }
.header .ffmpeg-badge.error { background: var(--red); color: #fff; }

.main { display: grid; grid-template-columns: 300px 1fr; gap: 0; min-height: calc(100vh - 49px); }

/* Left Panel */
.panel-left { background: var(--surface); border-right: 1px solid #333; overflow-y: auto; }
.section { padding: 16px; border-bottom: 1px solid #333; }
.section h3 { font-size: 13px; color: var(--text2); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px; }

.record-controls { display: flex; gap: 8px; }
.btn { padding: 8px 16px; border: none; border-radius: 6px; cursor: pointer; font-size: 13px; font-weight: 600; transition: all 0.15s; }
.btn:hover { filter: brightness(1.15); }
.btn-record { background: var(--red); color: #fff; flex: 1; }
.btn-record.active { background: #333; color: var(--text2); }
.btn-stop { background: #555; color: #fff; }
.btn-action { background: var(--surface2); color: var(--text); width: 100%; margin-top: 6px; }
.btn-small { padding: 4px 10px; font-size: 11px; border-radius: 4px; }
.btn-green { background: var(--green); color: #000; }
.btn-yellow { background: var(--yellow); color: #000; }
.btn-red { background: var(--red); color: #fff; }

.config-row { display: flex; align-items: center; gap: 8px; margin-top: 8px; }
.config-row label { font-size: 12px; color: var(--text2); min-width: 50px; }
.config-row select, .config-row input { background: var(--bg); color: var(--text); border: 1px solid #444; border-radius: 4px; padding: 4px 8px; font-size: 12px; }

.stats-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.stat-card { background: var(--bg); border-radius: 8px; padding: 10px; text-align: center; }
.stat-value { font-size: 20px; font-weight: 700; }
.stat-label { font-size: 11px; color: var(--text2); margin-top: 2px; }

/* Right Panel */
.panel-right { overflow-y: auto; padding: 16px; }
.tab-bar { display: flex; gap: 4px; margin-bottom: 16px; }
.tab { padding: 8px 16px; border-radius: 6px 6px 0 0; background: var(--surface); color: var(--text2); cursor: pointer; font-size: 13px; border: none; }
.tab.active { background: var(--surface2); color: var(--text); }

.segment-list { display: flex; flex-direction: column; gap: 6px; }
.segment-card { background: var(--surface); border-radius: 8px; padding: 12px 16px; display: flex; align-items: center; gap: 12px; transition: background 0.15s; }
.segment-card:hover { background: var(--surface2); }
.seg-icon { font-size: 20px; }
.seg-info { flex: 1; }
.seg-name { font-size: 13px; font-weight: 600; }
.seg-meta { font-size: 11px; color: var(--text2); margin-top: 2px; }
.seg-score { text-align: right; }
.score-bar { width: 60px; height: 6px; background: #333; border-radius: 3px; margin-top: 4px; }
.score-fill { height: 100%; border-radius: 3px; transition: width 0.3s; }
.score-value { font-size: 12px; font-weight: 600; }

.timeline-entry { padding: 8px 0; border-bottom: 1px solid #222; font-size: 13px; font-family: monospace; }

.edl-entry { display: flex; align-items: center; gap: 10px; padding: 8px 12px; background: var(--surface); border-radius: 6px; margin-bottom: 4px; }
.edl-action { font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 4px; }
.edl-keep { background: var(--green); color: #000; }
.edl-skip { background: #555; color: #aaa; }
.edl-highlight { background: var(--yellow); color: #000; }

.empty { text-align: center; color: var(--text2); padding: 40px; font-size: 14px; }
.toast { position: fixed; bottom: 36px; right: 20px; background: var(--surface2); color: var(--text); padding: 12px 20px; border-radius: 8px; font-size: 13px; z-index: 100; display: none; border: 1px solid #444; }

/* OBS-style bottom status bar */
.status-bar { background: #111; border-top: 1px solid #333; padding: 4px 16px; display: flex; align-items: center; gap: 20px; font-size: 11px; color: var(--text2); position: fixed; bottom: 0; left: 0; right: 0; z-index: 50; height: 28px; }
.status-bar .sb-item { display: flex; align-items: center; gap: 4px; }
.status-bar .sb-dot { width: 6px; height: 6px; border-radius: 50%; display: inline-block; }
.status-bar .sb-dot.green { background: var(--green); }
.status-bar .sb-dot.yellow { background: var(--yellow); }
.status-bar .sb-dot.red { background: var(--red); }

/* Segment progress bar */
.seg-progress { margin-top: 8px; }
.seg-progress-label { font-size: 11px; color: var(--text2); margin-bottom: 3px; display: flex; justify-content: space-between; }
.seg-progress-bar { width: 100%; height: 4px; background: #333; border-radius: 2px; overflow: hidden; }
.seg-progress-fill { height: 100%; background: var(--accent); border-radius: 2px; transition: width 0.5s linear; }

/* Keyboard hint */
.kbd-hint { font-size: 10px; color: var(--text2); text-align: center; margin-top: 8px; }
.kbd { background: #333; padding: 1px 5px; border-radius: 3px; font-family: monospace; font-size: 10px; border: 1px solid #555; }

/* Disk bar */
.disk-bar { width: 100%; height: 4px; background: #333; border-radius: 2px; margin-top: 4px; }
.disk-fill { height: 100%; border-radius: 2px; }

/* Adjust main for status bar */
.main { min-height: calc(100vh - 49px - 28px); }
</style>
</head>
<body>
<div class="header">
  <div class="status-dot idle" id="statusDot"></div>
  <h1>Screen Capture Bridge</h1>
  <span class="elapsed" id="elapsed"></span>
  <span style="flex:1"></span>
  <span class="ffmpeg-badge" id="ffmpegBadge">checking...</span>
</div>

<div class="main">
  <div class="panel-left">
    <div class="section">
      <h3>录制控制</h3>
      <div class="record-controls">
        <button class="btn btn-record" id="btnRecord" onclick="toggleRecord()">REC</button>
        <button class="btn btn-stop" id="btnStop" onclick="stopRecord()" disabled>STOP</button>
      </div>
      <div class="seg-progress" id="segProgress" style="display:none">
        <div class="seg-progress-label"><span>分段进度</span><span id="segRemaining">-</span></div>
        <div class="seg-progress-bar"><div class="seg-progress-fill" id="segProgressFill" style="width:0%"></div></div>
      </div>
      <div class="kbd-hint"><span class="kbd">Space</span> 开始/停止录制</div>
      <div class="config-row">
        <label>录制源</label>
        <select id="cfgSource"><option value="desktop">桌面 (主屏)</option><option value="dual">双屏 (全部)</option></select>
      </div>
      <div class="config-row">
        <label>画质</label>
        <select id="cfgQuality"><option value="low" selected>低 (720p 15fps)</option><option value="medium">中 (1080p 24fps)</option><option value="high">高 (1440p 30fps)</option></select>
      </div>
      <div class="config-row">
        <label>分段</label>
        <select id="cfgSegment"><option value="1">1分钟</option><option value="2" selected>2分钟</option><option value="5">5分钟</option><option value="10">10分钟</option></select>
      </div>
    </div>

    <div class="section">
      <h3>状态</h3>
      <div class="stats-grid">
        <div class="stat-card"><div class="stat-value" id="statSegments">-</div><div class="stat-label">分段</div></div>
        <div class="stat-card"><div class="stat-value" id="statSize">-</div><div class="stat-label">总大小</div></div>
        <div class="stat-card"><div class="stat-value" id="statReady">-</div><div class="stat-label">就绪</div></div>
        <div class="stat-card"><div class="stat-value" id="statRecording">-</div><div class="stat-label">录制中</div></div>
      </div>
    </div>

    <div class="section">
      <h3>操作</h3>
      <button class="btn btn-action" onclick="batchScore()">批量评分 + EDL</button>
      <button class="btn btn-action" onclick="doAssemble()">生成粗剪</button>
      <button class="btn btn-action" onclick="whatHappened()">最近发生了什么？</button>
      <button class="btn btn-action btn-red" style="margin-top:12px" onclick="doCleanup()">清理旧文件 (7天)</button>
    </div>

    <div class="section">
      <h3>目录</h3>
      <div style="font-size:12px;color:var(--text2);word-break:break-all" id="watchDir">-</div>
    </div>
  </div>

  <div class="panel-right">
    <div class="tab-bar">
      <button class="tab active" data-tab="segments" onclick="switchTab('segments')">分段列表</button>
      <button class="tab" data-tab="timeline" onclick="switchTab('timeline')">时间线</button>
      <button class="tab" data-tab="edl" onclick="switchTab('edl')">EDL 决策</button>
    </div>

    <div id="tab-segments">
      <div class="segment-list" id="segmentList"><div class="empty">加载中...</div></div>
    </div>
    <div id="tab-timeline" style="display:none">
      <div id="timelineContent"><div class="empty">点击"最近发生了什么？"生成时间线</div></div>
    </div>
    <div id="tab-edl" style="display:none">
      <div id="edlContent"><div class="empty">点击"批量评分 + EDL"生成剪辑决策</div></div>
    </div>
  </div>
</div>

<div class="status-bar">
  <div class="sb-item"><span class="sb-dot green" id="sbDot"></span> <span id="sbState">IDLE</span></div>
  <div class="sb-item" id="sbElapsed" style="display:none">REC: <span id="sbTime">0:00</span></div>
  <div class="sb-item">Segments: <span id="sbSegs">0</span></div>
  <div class="sb-item">Size: <span id="sbSize">0 MB</span></div>
  <div class="sb-item">Disk: <span id="sbDisk">-</span></div>
  <div class="sb-item" style="margin-left:auto;color:#555">Space=Rec | F5=Refresh</div>
</div>

<div class="toast" id="toast"></div>

<script>
const API = '';
let refreshTimer = null;

async function api(path, method='GET', body=null) {
  const opts = { method };
  if (body) { opts.headers = {'Content-Type':'application/json'}; opts.body = JSON.stringify(body); }
  const r = await fetch(API + path, opts);
  return r.json();
}

function toast(msg, ms=3000) {
  const t = document.getElementById('toast');
  t.textContent = msg; t.style.display = 'block';
  setTimeout(() => t.style.display = 'none', ms);
}

function switchTab(name) {
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab === name));
  ['segments','timeline','edl'].forEach(id => {
    document.getElementById('tab-'+id).style.display = id === name ? '' : 'none';
  });
}

function scoreColor(score) {
  if (score >= 0.7) return 'var(--yellow)';
  if (score >= 0.3) return 'var(--green)';
  return '#555';
}

let isRecording = false;

// ── 键盘快捷键 (OBS-style) ──
document.addEventListener('keydown', (e) => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
  if (e.code === 'Space') { e.preventDefault(); isRecording ? stopRecord() : toggleRecord(); }
});

// ── 自适应刷新 (录制中1s, 空闲5s) ──
function scheduleRefresh() {
  clearInterval(refreshTimer);
  refreshTimer = setInterval(refreshAll, isRecording ? 1000 : 5000);
}

// ── 刷新状态 ──
async function refreshStatus() {
  try {
    const s = await api('/api/status');
    document.getElementById('statSegments').textContent = s.total_segments;
    document.getElementById('statSize').textContent = s.total_size_mb + ' MB';
    document.getElementById('statReady').textContent = s.ready;
    document.getElementById('statRecording').textContent = s.recording;
    document.getElementById('watchDir').textContent = s.watch_dir;
    document.getElementById('sbSegs').textContent = s.total_segments;
    document.getElementById('sbSize').textContent = s.total_size_mb + ' MB';

    const rec = await api('/api/recording');
    const dot = document.getElementById('statusDot');
    const elapsed = document.getElementById('elapsed');
    const btnRec = document.getElementById('btnRecord');
    const btnStop = document.getElementById('btnStop');
    const wasRecording = isRecording;
    isRecording = rec.recording;
    if (wasRecording !== isRecording) scheduleRefresh();

    if (rec.recording) {
      dot.className = 'status-dot recording';
      elapsed.textContent = rec.elapsed_str;
      btnRec.disabled = true; btnRec.classList.add('active');
      btnStop.disabled = false;
      document.getElementById('sbDot').className = 'sb-dot red';
      document.getElementById('sbState').textContent = 'REC';
      document.getElementById('sbElapsed').style.display = '';
      document.getElementById('sbTime').textContent = rec.elapsed_str;
      document.getElementById('segProgress').style.display = '';
      const pct = Math.round((rec.segment_progress || 0) * 100);
      document.getElementById('segProgressFill').style.width = pct + '%';
      document.getElementById('segRemaining').textContent = rec.segment_remaining + 's';
    } else {
      dot.className = 'status-dot idle';
      elapsed.textContent = '';
      btnRec.disabled = false; btnRec.classList.remove('active');
      btnStop.disabled = true;
      document.getElementById('sbDot').className = 'sb-dot green';
      document.getElementById('sbState').textContent = 'IDLE';
      document.getElementById('sbElapsed').style.display = 'none';
      document.getElementById('segProgress').style.display = 'none';
    }

    const disk = await api('/api/disk-info');
    const diskColor = disk.free_gb < 5 ? 'var(--red)' : disk.free_gb < 20 ? 'var(--yellow)' : 'var(--green)';
    document.getElementById('sbDisk').innerHTML = disk.free_gb + ' GB free';
    document.getElementById('sbDisk').style.color = diskColor;
  } catch(e) { console.error('status error:', e); }
}

async function refreshSegments() {
  try {
    const data = await api('/api/segments');
    const list = document.getElementById('segmentList');
    if (!data.segments || data.segments.length === 0) {
      list.innerHTML = '<div class="empty">暂无视频分段</div>';
      return;
    }
    list.innerHTML = data.segments.map(s => {
      const icon = s.locked ? '🔴' : '🟢';
      const dur = s.video_info ? s.video_info.duration_str : '?';
      const res = s.video_info ? s.video_info.width + 'x' + s.video_info.height : '';
      return `<div class="segment-card">
        <span class="seg-icon">${icon}</span>
        <div class="seg-info">
          <div class="seg-name">${s.name}</div>
          <div class="seg-meta">${s.size_mb}MB | ${dur} | ${res} | ${s.modified}</div>
        </div>
        <div>
          ${!s.locked ? '<button class="btn btn-small btn-green" onclick="scoreOne(\''+s.path.replace(/\\/g,'\\\\')+'\')">评分</button>' : '<span style="color:var(--red);font-size:11px">录制中</span>'}
        </div>
      </div>`;
    }).join('');
  } catch(e) { console.error('segments error:', e); }
}

// ── 录制控制 ──
async function toggleRecord() {
  const quality = document.getElementById('cfgQuality').value;
  const segment = document.getElementById('cfgSegment').value;
  const source = document.getElementById('cfgSource').value;
  const r = await api('/api/record/start', 'POST', { quality, segment_min: parseInt(segment), source });
  if (r.error) { toast('错误: ' + r.error); return; }
  toast('开始录制 (PID: ' + r.pid + ')');
  refreshAll();
}

async function stopRecord() {
  const r = await api('/api/record/stop', 'POST');
  toast('停止录制: ' + (r.elapsed_str || ''));
  refreshAll();
}

// ── 操作 ──
async function scoreOne(path) {
  toast('评分中...');
  const r = await api('/api/score', 'POST', { path });
  toast('评分: ' + r.score + ' (' + (r.score >= 0.4 ? 'highlight' : r.score >= 0.1 ? 'keep' : 'skip') + ')');
}

async function batchScore() {
  toast('批量评分中，请稍候...');
  const r = await api('/api/batch-score', 'POST');
  if (r.error) { toast('错误: ' + r.error); return; }
  toast('完成: ' + r.stats.kept + '/' + r.stats.total + ' 保留');
  refreshEdl();
}

async function doAssemble() {
  toast('生成粗剪...');
  const r = await api('/api/assemble', 'POST');
  if (r.error) { toast('错误: ' + r.error); return; }
  toast('粗剪完成: ' + r.output);
}

async function whatHappened() {
  toast('分析中...');
  const r = await api('/api/what-happened?minutes=30');
  const div = document.getElementById('timelineContent');
  if (!r.segments_found) {
    div.innerHTML = '<div class="empty">' + r.timeline + '</div>';
  } else {
    let html = '<div style="margin-bottom:12px;color:var(--text2);font-size:13px">' +
      r.segments_found + ' 段 | ' + r.total_duration + 's | 平均活跃度 ' + (r.avg_activity*100).toFixed(0) + '%</div>';
    html += r.timeline.split('\n').map(line =>
      '<div class="timeline-entry">' + line + '</div>'
    ).join('');
    div.innerHTML = html;
  }
  switchTab('timeline');
}

async function refreshEdl() {
  const r = await api('/api/edl');
  const div = document.getElementById('edlContent');
  if (!r || !r.segments || r.segments.length === 0) {
    div.innerHTML = '<div class="empty">暂无EDL数据</div>';
    return;
  }
  let html = '<div style="margin-bottom:12px;color:var(--text2);font-size:13px">' +
    'kept: ' + r.stats.kept + ' | skipped: ' + r.stats.skipped +
    ' | highlights: ' + r.stats.highlights + ' | duration: ' + r.stats.kept_duration + 's</div>';
  html += r.segments.map(s => {
    const cls = s.action === 'highlight' ? 'edl-highlight' : s.action === 'keep' ? 'edl-keep' : 'edl-skip';
    return `<div class="edl-entry">
      <span class="edl-action ${cls}">${s.action.toUpperCase()}</span>
      <span style="flex:1;font-size:13px">${s.name}</span>
      <span style="font-size:12px;color:var(--text2)">${s.score.toFixed(3)}</span>
      <div class="score-bar"><div class="score-fill" style="width:${Math.round(s.score*100)}%;background:${scoreColor(s.score)}"></div></div>
    </div>`;
  }).join('');
  div.innerHTML = html;
}

async function doCleanup() {
  if (!confirm('清理7天前的旧文件？')) return;
  const r = await api('/api/cleanup', 'POST', { days: 7, force: true });
  toast('清理: 删除' + r.to_delete + '个, 保留' + r.to_keep + '个');
  refreshAll();
}

// ── 初始化 ──
async function init() {
  const ff = await api('/api/ffmpeg-check');
  const badge = document.getElementById('ffmpegBadge');
  if (ff.available) {
    badge.textContent = 'FFmpeg OK';
    badge.className = 'ffmpeg-badge';
  } else {
    badge.textContent = 'FFmpeg Missing';
    badge.className = 'ffmpeg-badge error';
  }
  // 动态加载录制源（摄像头等）
  try {
    const src = await api('/api/sources');
    const sel = document.getElementById('cfgSource');
    (src.sources || []).filter(s => s.type === 'camera').forEach(s => {
      const opt = document.createElement('option');
      opt.value = s.id; opt.textContent = s.name;
      sel.appendChild(opt);
    });
  } catch(e) {}
  refreshAll();
  scheduleRefresh();
}

function refreshAll() {
  refreshStatus();
  refreshSegments();
}

init();
</script>
</body>
</html>"""


class BridgeHandler(BaseHTTPRequestHandler):
    bridge = None

    def log_message(self, format, *args):
        pass  # 静默日志

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False, default=str).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', len(body))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == '/' or path == '/index.html':
            body = HTML_PAGE.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', len(body))
            self.end_headers()
            self.wfile.write(body)

        elif path == '/api/status':
            self.send_json(self.bridge.status())

        elif path == '/api/segments':
            segs = self.bridge.get_segments(include_locked=True)
            from dataclasses import asdict
            self.send_json({'segments': [asdict(s) for s in segs]})

        elif path == '/api/recording':
            self.send_json(get_recording_status())

        elif path == '/api/ffmpeg-check':
            self.send_json({'available': check_ffmpeg()})

        elif path == '/api/edl':
            edl = self.bridge.get_edl()
            self.send_json(edl or {})

        elif path == '/api/what-happened':
            minutes = int(params.get('minutes', [5])[0])
            from dataclasses import asdict
            summary = self.bridge.what_happened(minutes=minutes)
            self.send_json(asdict(summary))

        elif path == '/api/disk-info':
            self.send_json(get_disk_info(str(self.bridge.watch_dir)))

        elif path == '/api/sources':
            self.send_json({'sources': enumerate_sources()})

        else:
            self.send_json({'error': 'not found'}, 404)

    def do_POST(self):
        content_len = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(content_len)) if content_len > 0 else {}
        parsed = urlparse(self.path)
        path = parsed.path

        if path == '/api/record/start':
            quality = body.get('quality', 'low')
            segment_min = body.get('segment_min', 2)
            source = body.get('source', 'desktop')
            result = start_recording(str(self.bridge.watch_dir), segment_min, quality, source)
            self.send_json(result)

        elif path == '/api/record/stop':
            self.send_json(stop_recording())

        elif path == '/api/score':
            video_path = body.get('path', '')
            if not video_path or not Path(video_path).exists():
                self.send_json({'error': 'file not found'}, 400)
                return
            score = score_segment(video_path)
            self.send_json({'path': video_path, 'score': score})

        elif path == '/api/batch-score':
            segs = self.bridge.get_segments()
            if not segs:
                self.send_json({'error': 'no segments'})
                return
            edl = EditDecisionList(str(self.bridge.watch_dir))
            known = {s['file'] for s in edl.segments}
            for seg in segs:
                if seg.path in known:
                    continue
                score = score_segment(seg.path)
                edl.add_segment(seg.path, score, seg.video_info)
            self.send_json({'stats': edl.get_stats()})

        elif path == '/api/assemble':
            result = self.bridge.assemble()
            if result:
                size_mb = round(Path(result).stat().st_size / (1024*1024), 1)
                self.send_json({'output': result, 'size_mb': size_mb})
            else:
                self.send_json({'error': 'assemble failed (no EDL or no kept segments)'})

        elif path == '/api/cleanup':
            days = body.get('days', 7)
            force = body.get('force', False)
            result = self.bridge.cleanup(keep_days=days, dry_run=not force)
            self.send_json(result)

        else:
            self.send_json({'error': 'not found'}, 404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Screen Capture Bridge Web UI')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT, help=f'端口 (默认: {DEFAULT_PORT})')
    parser.add_argument('--dir', default=DEFAULT_DIR, help=f'录屏目录 (默认: {DEFAULT_DIR})')
    args = parser.parse_args()

    BridgeHandler.bridge = ScreenBridge(args.dir)

    class ThreadedServer(ThreadingMixIn, HTTPServer):
        daemon_threads = True
    server = ThreadedServer(('0.0.0.0', args.port), BridgeHandler)
    print(f"Screen Capture Bridge Web UI")
    print(f"  URL:  http://localhost:{args.port}")
    print(f"  Dir:  {args.dir}")
    print(f"  Ctrl+C 停止")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n停止")
        stop_recording()
        server.server_close()


if __name__ == '__main__':
    main()
