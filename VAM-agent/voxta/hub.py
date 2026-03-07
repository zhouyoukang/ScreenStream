"""
Voxta 中枢控制 — DB直控/角色CRUD/模块管理/诊断/自动修复/API直调

从 tools/agent_hub.py 整合至此，统一管理:
  1. VoxtaDB — 数据库高级操作(角色CRUD/模块配置/预设/记忆书/对话历史)
  2. DirectAPI — 直接调用底层AI服务(EdgeTTS/DashScope)
  3. Diagnostics — 全链路诊断(文件/服务/DB/模块/安全/磁盘)
  4. AutoFix — 自动修复已知问题(重复角色/死链模块/Vosk忽略词)
"""
import json
import logging
import shutil
import sqlite3
import base64
import struct
import uuid
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime
from typing import Optional

from .config import VOXTA_CONFIG
from . import process

_log = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════
# 数据库高级操作 (超越 db.py 的增强能力)
# ═══════════════════════════════════════════════════════

class VoxtaDB:
    """Voxta SQLite数据库高级操控 — 角色CRUD/模块配置/TavernCard导入"""

    def __init__(self, db_path=None):
        self.db_path = str(db_path or VOXTA_CONFIG.VOXTA_DB)

    def _conn(self):
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        return db

    @contextmanager
    def _db(self):
        """Context manager for safe DB connections (auto-close on exit/exception)"""
        db = self._conn()
        try:
            yield db
        finally:
            db.close()

    def backup(self) -> str:
        """备份数据库"""
        backup_dir = VOXTA_CONFIG.VOXTA_DIR / "Data" / ".agent_backup"
        backup_dir.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = backup_dir / f"Voxta.sqlite.db.{ts}.bak"
        shutil.copy2(self.db_path, str(dest))
        return str(dest)

    # ── 模块管理 ──

    def list_modules(self) -> list:
        with self._db() as db:
            rows = [dict(r) for r in db.execute("SELECT * FROM Modules")]
        result = []
        for r in rows:
            cfg = {}
            try:
                cfg = json.loads(r.get('Configuration', '{}') or '{}')
            except Exception:
                pass
            result.append({
                'id': r.get('LocalId', ''),
                'service': r.get('ServiceName', ''),
                'label': r.get('Label', ''),
                'enabled': bool(r.get('Enabled', 0)),
                'config': cfg,
            })
        return result

    def set_module_enabled(self, local_id: str, enabled: bool) -> bool:
        """启用/禁用模块"""
        with self._db() as db:
            db.execute("UPDATE Modules SET Enabled=? WHERE LocalId=?",
                       (1 if enabled else 0, local_id))
            db.commit()
        return True

    def find_module(self, service_name: str = None,
                    label: str = None) -> Optional[dict]:
        """按服务名或标签查找模块"""
        modules = self.list_modules()
        for m in modules:
            if service_name and service_name.lower() in m['service'].lower():
                if label is None or (m['label'] and label.lower() in m['label'].lower()):
                    return m
        return None

    def update_module_config(self, local_id: str, config_updates: dict) -> bool:
        """更新模块配置"""
        with self._db() as db:
            row = db.execute("SELECT Configuration FROM Modules WHERE LocalId=?",
                             (local_id,)).fetchone()
            if not row:
                return False
            cfg = json.loads(row['Configuration'] or '{}')
            cfg.update(config_updates)
            db.execute("UPDATE Modules SET Configuration=? WHERE LocalId=?",
                       (json.dumps(cfg), local_id))
            db.commit()
        return True

    # ── 角色管理 ──

    def list_characters(self) -> list:
        with self._db() as db:
            rows = [dict(r) for r in db.execute("SELECT * FROM Characters")]
        result = []
        for r in rows:
            result.append({
                'id': r.get('LocalId', ''),
                'name': r.get('Name', ''),
                'description': r.get('Description', ''),
                'culture': r.get('Culture', ''),
                'personality': r.get('Personality', ''),
                'profile': r.get('Profile', ''),
                'use_memory': bool(r.get('UseMemory', 0)),
                'use_vision': bool(r.get('UseVision', 0)),
                'thinking_speech': bool(r.get('EnableThinkingSpeech', 0)),
                'scenario_only': bool(r.get('ScenarioOnly', 0)),
                'date_created': r.get('DateCreated', ''),
                'date_modified': r.get('DateModified', ''),
            })
        return result

    def get_character_detail(self, local_id: str) -> Optional[dict]:
        """获取角色完整详情"""
        with self._db() as db:
            row = db.execute("SELECT * FROM Characters WHERE LocalId=?",
                             (local_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        scripts = json.loads(d.get('Scripts', '[]') or '[]')
        tts = json.loads(d.get('TextToSpeech', '[]') or '[]')
        return {
            'id': d.get('LocalId', ''),
            'name': d.get('Name', ''),
            'description': d.get('Description', ''),
            'personality': d.get('Personality', ''),
            'profile': d.get('Profile', ''),
            'culture': d.get('Culture', ''),
            'first_message': d.get('FirstMessage', ''),
            'message_examples': d.get('MessageExamples', ''),
            'tts': tts,
            'scripts': scripts,
            'use_memory': bool(d.get('UseMemory', 0)),
            'use_vision': bool(d.get('UseVision', 0)),
            'thinking_speech': bool(d.get('EnableThinkingSpeech', 0)),
            'explicit': bool(d.get('ExplicitContent', 0)),
            'date_created': d.get('DateCreated', ''),
            'date_modified': d.get('DateModified', ''),
        }

    def delete_character(self, local_id: str) -> bool:
        """删除角色"""
        self.backup()
        with self._db() as db:
            db.execute("DELETE FROM Characters WHERE LocalId=?", (local_id,))
            db.commit()
        return True

    _ALLOWED_FIELDS = {
        "Name", "Label", "Personality", "Profile", "Description", "Culture",
        "FirstMessage", "MessageExamples", "SystemPrompt", "PostHistoryInstructions",
        "EnableThinkingSpeech", "MemoryBooks", "Tags", "Extensions",
        "Creator", "CreatorNotes",
    }

    def update_character(self, local_id: str, updates: dict) -> bool:
        """更新角色字段"""
        bad_keys = set(updates.keys()) - self._ALLOWED_FIELDS
        if bad_keys:
            raise ValueError(f"Disallowed fields: {bad_keys}")
        with self._db() as db:
            for key, val in updates.items():
                db.execute(f"UPDATE Characters SET [{key}]=? WHERE LocalId=?",
                           (val, local_id))
            db.commit()
        return True

    def _get_user_id(self) -> str:
        """获取Voxta DB中的UserId"""
        try:
            with self._db() as db:
                row = db.execute("SELECT Id FROM Users LIMIT 1").fetchone()
                if row:
                    return dict(row)['Id']
        except Exception:
            pass
        return 'default'

    def create_character(self, name: str, profile: str, personality: str,
                         description: str = '', culture: str = 'zh-CN',
                         use_memory: bool = True, thinking_speech: bool = True,
                         tts_service: str = 'edgetts') -> str:
        """创建新角色"""
        local_id = str(uuid.uuid4()).upper()
        now = datetime.now().isoformat() + '+00:00'

        tts_configs = {
            'edgetts': json.dumps([{
                "voice": {"parameters": {"voice_id": "nova"},
                          "label": "EdgeTTS 中文女声"},
                "service": {"serviceName": "TextToSpeechHttpApi"}
            }]),
            'f5tts': json.dumps([{
                "voice": {"parameters": {"Filename": "Voxta_F_Anne.wav"},
                          "label": "F5TTS"},
                "service": {"serviceName": "F5TTS"}
            }]),
            'silero': json.dumps([{
                "voice": {"parameters": {"Gender": "Female"},
                          "label": "Silero Auto"},
                "service": {"serviceName": "Silero"}
            }]),
        }

        script = json.dumps([{"name": "index", "content":
            f'import {{ chat }} from "@voxta";\n'
            f'chat.addEventListener("start", (e) => {{\n'
            f'  if(!e.hasBootstrapMessages) {{\n'
            f'    chat.characterMessage("你好！我是{name}，很高兴认识你！");\n'
            f'  }}\n'
            f'}});'
        }])

        user_id = self._get_user_id()
        with self._db() as db:
            db.execute("""INSERT INTO Characters (
            UserId, LocalId, PackageId, Name, Description, Personality, Profile,
            Culture, TextToSpeech, Scripts, MemoryBooks, Tags,
            AppControlled, Locked, Version, Favorite, ScenarioOnly,
            DefaultScenarios, ChatStyle, ExplicitContent,
            EnableThinkingSpeech, NotifyUserAwayReturn, TimeAware,
            UseVision, UseMemory, MaxTokens, MaxSentences, Augmentations,
            DateCreated, DateModified, Creator, CreatorNotes
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
            user_id, local_id, local_id, name, description, personality, profile,
            culture, tts_configs.get(tts_service, tts_configs['edgetts']),
            script, '[]', json.dumps([culture.split('-')[0]]),
            1, 0, '1.0.0', 0, 0,
            '[]', 0, 0,
            1 if thinking_speech else 0, 1, 1,
            0, 1 if use_memory else 0, 0, 0, '[]',
                now, now, 'Voxta Agent', 'Created by voxta.hub'
            ))
            db.commit()
        return local_id

    # ── TavernCard导入 ──

    def import_tavern_card(self, png_path: str, culture: str = 'zh-CN',
                           tts_service: str = 'edgetts') -> dict:
        """从TavernCard V2 PNG导入角色到Voxta DB"""
        png_path = Path(png_path)
        if not png_path.exists():
            return {'error': f'File not found: {png_path}'}

        char_data = self._extract_tavern_data(png_path)
        if not char_data:
            return {'error': 'No TavernCard data found in PNG'}

        return self._import_tavern_data(char_data, culture, tts_service, str(png_path))

    def import_tavern_json(self, json_path: str, culture: str = 'zh-CN',
                           tts_service: str = 'edgetts') -> dict:
        """从TavernCard JSON文件导入角色"""
        json_path = Path(json_path)
        if not json_path.exists():
            return {'error': f'File not found: {json_path}'}
        with open(json_path, 'r', encoding='utf-8') as f:
            char_data = json.load(f)
        return self._import_tavern_data(char_data, culture, tts_service, str(json_path))

    def _extract_tavern_data(self, png_path: Path) -> Optional[dict]:
        """Extract TavernCard data from PNG tEXt/iTXt chunk (keyword='chara')"""
        with open(png_path, 'rb') as f:
            sig = f.read(8)
            if sig != b'\x89PNG\r\n\x1a\n':
                return None
            while True:
                header = f.read(8)
                if len(header) < 8:
                    break
                length = struct.unpack('>I', header[:4])[0]
                chunk_type = header[4:8]
                data = f.read(length)
                f.read(4)  # CRC
                if chunk_type == b'tEXt':
                    parts = data.split(b'\x00', 1)
                    if len(parts) == 2 and parts[0] == b'chara':
                        try:
                            decoded = base64.b64decode(parts[1])
                            return json.loads(decoded.decode('utf-8'))
                        except Exception:
                            pass
                elif chunk_type == b'iTXt':
                    parts = data.split(b'\x00', 1)
                    if len(parts) >= 2 and parts[0] == b'chara':
                        remainder = parts[1]
                        null_count = 0
                        idx = 0
                        for i, b in enumerate(remainder):
                            if b == 0:
                                null_count += 1
                                if null_count >= 3:
                                    idx = i + 1
                                    break
                        try:
                            text_data = remainder[idx:]
                            decoded = base64.b64decode(text_data)
                            return json.loads(decoded.decode('utf-8'))
                        except Exception:
                            try:
                                return json.loads(text_data.decode('utf-8'))
                            except Exception:
                                pass
                elif chunk_type == b'IEND':
                    break
        return None

    def _import_tavern_data(self, char_data: dict, culture: str,
                            tts_service: str, source: str) -> dict:
        """Internal: import from parsed TavernCard data dict"""
        name = char_data.get('name') or char_data.get('char_name', 'Unknown')
        description = char_data.get('description', '')
        personality = char_data.get('personality', '')
        scenario = char_data.get('scenario', '')
        first_message = char_data.get('first_mes', '')
        mes_example = char_data.get('mes_example', '')
        system_prompt = char_data.get('system_prompt', '')
        post_history = char_data.get('post_history_instructions', '')
        creator = char_data.get('creator', '')
        creator_notes = char_data.get('creator_notes', '')
        tags = char_data.get('tags', [])
        spec = char_data.get('spec', '')

        if spec == 'chara_card_v2' and 'data' in char_data:
            v2 = char_data['data']
            name = v2.get('name', name)
            description = v2.get('description', description)
            personality = v2.get('personality', personality)
            scenario = v2.get('scenario', scenario)
            first_message = v2.get('first_mes', first_message)
            mes_example = v2.get('mes_example', mes_example)
            system_prompt = v2.get('system_prompt', system_prompt)
            post_history = v2.get('post_history_instructions', post_history)
            creator = v2.get('creator', creator)
            creator_notes = v2.get('creator_notes', creator_notes)
            tags = v2.get('tags', tags)

        profile = description
        if scenario:
            profile += f"\n\n[Scenario]\n{scenario}"

        local_id = self.create_character(
            name=name, profile=profile, personality=personality,
            description=description[:500], culture=culture, tts_service=tts_service,
        )

        updates = {}
        if first_message:
            updates['FirstMessage'] = first_message
        if mes_example:
            updates['MessageExamples'] = mes_example
        if system_prompt:
            updates['SystemPrompt'] = system_prompt
        if post_history:
            updates['PostHistoryInstructions'] = post_history
        if creator:
            updates['Creator'] = creator
        if creator_notes:
            updates['CreatorNotes'] = creator_notes
        if tags:
            updates['Tags'] = json.dumps(tags)
        if updates:
            self.update_character(local_id, updates)
        return {
            'id': local_id, 'name': name, 'source': source,
            'fields_imported': list(updates.keys()) + ['Name', 'Profile', 'Personality'],
            'spec': spec or 'v1',
        }

    # ── 预设管理 ──

    def list_presets(self) -> list:
        with self._db() as db:
            rows = [dict(r) for r in db.execute("SELECT * FROM Presets")]
        result = []
        for r in rows:
            params = {}
            try:
                params = json.loads(r.get('Parameters', '{}') or '{}')
            except Exception:
                pass
            result.append({
                'id': r.get('LocalId', ''),
                'service': r.get('ServiceName', ''),
                'label': r.get('Label', ''),
                'type': r.get('ServiceType', 0),
                'params': params,
            })
        return result

    # ── 记忆书管理 ──

    def list_memory_books(self) -> list:
        with self._db() as db:
            rows = [dict(r) for r in db.execute("SELECT * FROM MemoryBooks")]
        return [{k: v for k, v in r.items() if v is not None and k != 'UserId'}
                for r in rows]

    # ── 对话历史 ──

    def recent_messages(self, limit: int = 20) -> list:
        with self._db() as db:
            rows = db.execute(
                "SELECT * FROM ChatMessages ORDER BY rowid DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def clear_chat_history(self) -> bool:
        """清空所有对话历史"""
        self.backup()
        with self._db() as db:
            db.execute("DELETE FROM ChatMessages")
            db.execute("DELETE FROM Chats")
            db.commit()
        return True

    # ── 统计 ──

    _ALLOWED_TABLES = frozenset([
        'Characters', 'ChatMessages', 'Chats', 'Modules',
        'Presets', 'MemoryBooks', 'Scenarios',
    ])

    def stats(self) -> dict:
        with self._db() as db:
            result = {}
            for t in self._ALLOWED_TABLES:
                try:
                    result[t] = db.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
                except Exception as e:
                    _log.debug("stats: table %s error: %s", t, e)
                    result[t] = -1
        return result

    def get_all_tables(self) -> dict:
        """获取所有表及行数"""
        with self._db() as db:
            cur = db.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cur.fetchall()]
            result = {}
            for table in tables:
                try:
                    result[table] = cur.execute(
                        f"SELECT COUNT(*) FROM [{table}]").fetchone()[0]
                except Exception as e:
                    _log.debug("get_all_tables: table %s error: %s", table, e)
                    result[table] = 'error'
        return result


# ═══════════════════════════════════════════════════════
# API直调层 (绕过Voxta,直接调用底层服务)
# ═══════════════════════════════════════════════════════

class DirectAPI:
    """直接调用底层AI服务API"""

    @staticmethod
    def edgetts_speak(text: str, voice: str = 'zh-CN-XiaoxiaoNeural') -> tuple:
        """直接调用EdgeTTS生成语音"""
        import urllib.request
        svc = VOXTA_CONFIG.SERVICES.get("edgetts", {})
        port = svc.get('port', 5050)
        data = json.dumps({'text': text, 'voice': voice}).encode('utf-8')
        req = urllib.request.Request(
            f'http://localhost:{port}/v1/audio/speech',
            data=data, headers={'Content-Type': 'application/json'}
        )
        try:
            resp = urllib.request.urlopen(req, timeout=10)
            if resp.status == 200:
                audio = resp.read()
                out = Path(__file__).parent / "configs" / f"tts_output_{int(datetime.now().timestamp())}.mp3"
                out.parent.mkdir(exist_ok=True)
                out.write_bytes(audio)
                return True, str(out)
            return False, f"HTTP {resp.status}"
        except Exception as e:
            return False, str(e)

    @staticmethod
    def edgetts_voices() -> Optional[list]:
        """获取EdgeTTS可用声音列表"""
        import urllib.request
        svc = VOXTA_CONFIG.SERVICES.get("edgetts", {})
        port = svc.get('port', 5050)
        try:
            resp = urllib.request.urlopen(f'http://localhost:{port}/v1/voices', timeout=5)
            if resp.status == 200:
                return json.loads(resp.read())
        except Exception:
            pass
        return None

    @staticmethod
    def edgetts_health() -> Optional[dict]:
        """EdgeTTS健康检查"""
        import urllib.request
        svc = VOXTA_CONFIG.SERVICES.get("edgetts", {})
        port = svc.get('port', 5050)
        try:
            resp = urllib.request.urlopen(f'http://localhost:{port}/health', timeout=5)
            if resp.status == 200:
                return json.loads(resp.read())
        except Exception:
            pass
        return None

    @staticmethod
    def dashscope_chat(message: str, api_key: str = None,
                       model: str = 'qwen-plus') -> tuple:
        """直接调用DashScope LLM"""
        import urllib.request
        if not api_key:
            return False, 'API key required'
        data = json.dumps({
            'model': model,
            'messages': [{'role': 'user', 'content': message}],
            'max_tokens': 200,
            'temperature': 0.8,
        }).encode('utf-8')
        req = urllib.request.Request(
            'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions',
            data=data,
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {api_key}'
            }
        )
        try:
            resp = urllib.request.urlopen(req, timeout=30)
            result = json.loads(resp.read())
            text = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            return True, text
        except Exception as e:
            return False, str(e)


# ═══════════════════════════════════════════════════════
# 全链路诊断
# ═══════════════════════════════════════════════════════

class Diagnostics:
    """全链路诊断"""

    @staticmethod
    def full_scan() -> list:
        issues = []
        vdb = VoxtaDB()

        # 文件完整性
        for name, info in VOXTA_CONFIG.get_all_critical_paths().items():
            if not info['exists']:
                issues.append(('CRITICAL', name, f'Missing: {info["path"]}'))

        # 服务状态
        for key, st in process.get_all_status().items():
            if not st.get('running'):
                issues.append(('INFO', st.get('name', key),
                               f'Offline :{st.get("port", "?")}'))

        # 数据库健康
        try:
            stats = vdb.stats()
            if stats.get('Characters', 0) == 0:
                issues.append(('WARNING', 'Voxta DB', 'No characters'))
            if stats.get('Modules', 0) == 0:
                issues.append(('CRITICAL', 'Voxta DB', 'No modules'))
        except Exception as e:
            issues.append(('CRITICAL', 'Voxta DB', f'Cannot read: {e}'))

        # 重复角色检查
        chars = vdb.list_characters()
        names = {}
        for c in chars:
            names.setdefault(c['name'], []).append(c['id'])
        for n, ids in names.items():
            if len(ids) > 1:
                issues.append(('WARNING', 'Characters',
                               f'Duplicate "{n}": {len(ids)} copies'))

        # 模块一致性
        modules = vdb.list_modules()
        enabled_cats = set()
        for m in modules:
            if m['enabled']:
                sn = m['service']
                for cat, services in VOXTA_CONFIG.MODULE_CATEGORIES.items():
                    if any(s in sn for s in services):
                        enabled_cats.add(cat)
                        break

        if 'LLM' not in enabled_cats:
            issues.append(('CRITICAL', 'Voxta', 'No LLM module enabled'))
        if 'TTS' not in enabled_cats:
            issues.append(('WARNING', 'Voxta', 'No TTS module enabled'))
        if 'STT' not in enabled_cats:
            issues.append(('WARNING', 'Voxta', 'No STT module enabled'))

        # WhisperLive死链
        wl = vdb.find_module('WhisperLive')
        if wl and wl['enabled'] and not process.check_port(10300):
            issues.append(('WARNING', 'WhisperLive',
                           'Enabled but :10300 offline'))

        # 凭据泄露检测 (检查未加密的API token)
        for m in modules:
            for k, v in m.get('config', {}).items():
                if isinstance(v, str) and len(v) > 20 \
                        and ('key' in k.lower() or 'token' in k.lower() or 'secret' in k.lower()) \
                        and not v.startswith('AQAAANCMnd8'):
                    issues.append(('WARNING', 'Security',
                                   f'可能存在未加密凭据 in {m["service"]}'))
                    break

        # 磁盘
        for drive in ['F:', 'D:']:
            try:
                total, used, free = shutil.disk_usage(drive + '\\')
                if used / total > 0.9:
                    issues.append(('WARNING', f'Disk {drive}',
                                   f'{used/total*100:.0f}% used'))
            except Exception:
                pass

        return issues

    @staticmethod
    def text_report() -> str:
        """生成文本格式诊断报告"""
        issues = Diagnostics.full_scan()
        vdb = VoxtaDB()
        stats = vdb.stats()
        svc = process.get_all_status()
        chars = vdb.list_characters()
        modules = vdb.list_modules()

        lines = [
            "=" * 65,
            f"  Voxta 中枢诊断  |  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "=" * 65,
            "\n[ 服务 ]",
        ]

        for k, s in svc.items():
            icon = "ON" if s.get('running') else "--"
            lines.append(f"  [{icon}] {s.get('name', k):12s} :{s.get('port', '?')}")

        lines.append(f"\n[ 数据库 ]")
        parts = []
        for k, v in stats.items():
            parts.append(f"  {k}: {v}")
        lines.append("  ".join(parts[:4]))
        if len(parts) > 4:
            lines.append("  ".join(parts[4:]))

        lines.append(f"\n[ 角色 ({len(chars)}) ]")
        for c in chars:
            mem = "M" if c['use_memory'] else "-"
            vis = "V" if c.get('use_vision') else "-"
            lines.append(
                f"  {c['name']:12s} [{c.get('culture', '')}] [{mem}{vis}] "
                f"{(c.get('description', '') or '')[:40]}"
            )

        enabled_count = sum(1 for m in modules if m['enabled'])
        lines.append(f"\n[ 模块 ({enabled_count}/{len(modules)} enabled) ]")
        for m in modules:
            st = "ON" if m['enabled'] else "--"
            lbl = f' "{m["label"]}"' if m['label'] else ''
            lines.append(f"  [{st}] {m['service']}{lbl}")

        if issues:
            lines.append(f"\n[ 问题 ({len(issues)}) ]")
            for level, comp, msg in issues:
                icon = {"CRITICAL": "!!", "WARNING": "!.", "INFO": ".."}[level]
                lines.append(f"  [{icon}] {comp}: {msg}")
        else:
            lines.append("\n  [OK] 无问题")

        lines.append("\n" + "=" * 65)
        return "\n".join(lines)

    @staticmethod
    def json_report() -> dict:
        """生成JSON格式全状态报告"""
        vdb = VoxtaDB()
        issues = Diagnostics.full_scan()
        return {
            'timestamp': datetime.now().isoformat(),
            'services': process.get_all_status(),
            'stats': vdb.stats(),
            'characters': vdb.list_characters(),
            'modules': [{k: v for k, v in m.items() if k != 'config'}
                        for m in vdb.list_modules()],
            'issues': [{'level': l, 'component': c, 'msg': m}
                       for l, c, m in issues],
        }


# ═══════════════════════════════════════════════════════
# 自动修复
# ═══════════════════════════════════════════════════════

class AutoFix:
    """自动修复已知问题"""

    @staticmethod
    def fix_duplicate_characters(dry_run: bool = True) -> list:
        """修复重复角色 — 保留较新的,删除较旧的"""
        vdb = VoxtaDB()
        chars = vdb.list_characters()
        names = {}
        for c in chars:
            names.setdefault(c['name'], []).append(c)

        fixes = []
        for name, copies in names.items():
            if len(copies) <= 1:
                continue
            copies.sort(key=lambda x: x.get('date_modified', ''), reverse=True)
            keep = copies[0]
            for dup in copies[1:]:
                fixes.append({
                    'action': 'delete_duplicate',
                    'name': name,
                    'keep_id': keep['id'],
                    'delete_id': dup['id'],
                })
                if not dry_run:
                    vdb.delete_character(dup['id'])
        return fixes

    @staticmethod
    def fix_whisper_live(dry_run: bool = True) -> Optional[dict]:
        """禁用WhisperLive(无服务)"""
        vdb = VoxtaDB()
        wl = vdb.find_module('WhisperLive')
        if wl and wl['enabled'] and not process.check_port(10300):
            if not dry_run:
                vdb.set_module_enabled(wl['id'], False)
            return {'action': 'disable', 'module': 'WhisperLive', 'id': wl['id']}
        return None

    @staticmethod
    def fix_vosk_ignored_words(dry_run: bool = True) -> Optional[dict]:
        """扩展Vosk中文忽略词"""
        vdb = VoxtaDB()
        vosk = vdb.find_module('Vosk')
        if vosk:
            current = vosk['config'].get('IgnoredWords', '')
            chinese_words = ("嗯\n啊\n哦\n呃\n那个\n就是\n然后\n对\n好\n是\n"
                             "huh\nthe\nand\ndo\nuh\num")
            if len(current) < len(chinese_words):
                if not dry_run:
                    vdb.update_module_config(vosk['id'],
                                             {'IgnoredWords': chinese_words})
                return {'action': 'expand', 'module': 'Vosk',
                        'from': len(current), 'to': len(chinese_words)}
        return None

    @staticmethod
    def run_all(dry_run: bool = True) -> list:
        """运行所有自动修复"""
        results = []
        results.extend(AutoFix.fix_duplicate_characters(dry_run))
        r = AutoFix.fix_whisper_live(dry_run)
        if r:
            results.append(r)
        r = AutoFix.fix_vosk_ignored_words(dry_run)
        if r:
            results.append(r)
        return results


# ═══════════════════════════════════════════════════════
# Voxta脚本生成器 (from voxta_unoffical_docs scripting API)
# ═══════════════════════════════════════════════════════

class VoxtaScriptGenerator:
    """基于Voxta脚本API知识生成角色脚本。

    从voxta_unoffical_docs legacy/voxta.doc.md 提取的完整API参考:
    - chat.addEventListener(trigger, handler) — 事件监听
    - chat.characterMessage(text) — 角色主动发言
    - chat.instructions(text) — 注入系统指令
    - chat.variables.get/set — 持久变量(跨会话)
    - chat.setFlag(name, duration?) — 标记系统(可过期)
    - chat.hasFlag(name) — 检查标记
    - chat.appTrigger(name, value?) — 触发VaM内动作
    - chat.setContext(key, text) — 动态上下文更新
    - chat.setRoleEnabled(role, bool) — 启用/禁用角色
    """

    TRIGGERS = [
        'start', 'messageReceived', 'messageSent', 'replyReceived',
        'replyChunk', 'speechRecognitionStart', 'speechRecognitionEnd',
        'speechRecognitionPartial', 'actionInferred', 'contextUpdated',
    ]

    @staticmethod
    def greeting(char_name: str, message: str = None) -> dict:
        """生成开场白脚本"""
        msg = message or f"你好！我是{char_name}，很高兴认识你！"
        code = (
            'import { chat } from "@voxta";\n'
            'chat.addEventListener("start", (e) => {\n'
            '  if(!e.hasBootstrapMessages) {\n'
            f'    chat.characterMessage("{msg}");\n'
            '  }\n'
            '});'
        )
        return {"name": "index", "content": code}

    @staticmethod
    def action_handler(actions: dict) -> dict:
        """生成动作处理脚本。

        actions: {action_name: vam_trigger_name}
        例: {"smile": "SetExpression_Happy", "wave": "PlayAnimation_Wave"}
        """
        handlers = []
        for action, trigger in actions.items():
            handlers.append(
                f'  if(e.action === "{action}") {{\n'
                f'    chat.appTrigger("{trigger}");\n'
                f'  }}'
            )
        handler_code = "\n".join(handlers)
        code = (
            'import { chat } from "@voxta";\n'
            'chat.addEventListener("actionInferred", (e) => {\n'
            f'{handler_code}\n'
            '});'
        )
        return {"name": "actions", "content": code}

    @staticmethod
    def context_updater(contexts: dict) -> dict:
        """生成动态上下文更新脚本。

        contexts: {context_key: context_text}
        例: {"location": "你们正在公园散步", "mood": "今天心情很好"}
        """
        setters = []
        for key, text in contexts.items():
            setters.append(f'  chat.setContext("{key}", "{text}");')
        setter_code = "\n".join(setters)
        code = (
            'import { chat } from "@voxta";\n'
            'chat.addEventListener("start", (e) => {\n'
            f'{setter_code}\n'
            '});'
        )
        return {"name": "context", "content": code}

    @staticmethod
    def flag_tracker(flags: list) -> dict:
        """生成标记追踪脚本(用于条件行为)。

        flags: [{"name": "greeted", "on_trigger": "start", "duration": 300}]
        """
        handlers = []
        for flag in flags:
            name = flag["name"]
            trigger = flag.get("on_trigger", "start")
            duration = flag.get("duration")
            dur_arg = f", {duration}" if duration else ""
            handlers.append(
                f'chat.addEventListener("{trigger}", (e) => {{\n'
                f'  chat.setFlag("{name}"{dur_arg});\n'
                f'}});'
            )
        code = 'import { chat } from "@voxta";\n' + "\n".join(handlers)
        return {"name": "flags", "content": code}

    @staticmethod
    def variable_counter(var_name: str, trigger: str = "messageReceived") -> dict:
        """生成变量计数器脚本(跨会话持久)。"""
        code = (
            'import { chat } from "@voxta";\n'
            f'chat.addEventListener("{trigger}", (e) => {{\n'
            f'  let count = parseInt(chat.variables.get("{var_name}") || "0");\n'
            f'  count++;\n'
            f'  chat.variables.set("{var_name}", count.toString());\n'
            f'  if(count % 10 === 0) {{\n'
            f'    chat.instructions("我们已经交流了" + count + "次了。");\n'
            f'  }}\n'
            f'}});'
        )
        return {"name": "counter", "content": code}

    @staticmethod
    def compose(scripts: list) -> str:
        """将多个脚本合并为JSON字符串(用于Characters.Scripts列)。"""
        return json.dumps(scripts, ensure_ascii=False)

    @classmethod
    def full_character_scripts(cls, char_name: str,
                                greeting_msg: str = None,
                                actions: dict = None,
                                contexts: dict = None) -> str:
        """一键生成完整角色脚本集。"""
        scripts = [cls.greeting(char_name, greeting_msg)]
        if actions:
            scripts.append(cls.action_handler(actions))
        if contexts:
            scripts.append(cls.context_updater(contexts))
        return cls.compose(scripts)
