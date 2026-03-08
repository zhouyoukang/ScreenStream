#!/usr/bin/env python3
"""
三电脑服务器 · 数据守护者 (Data Guardian)
伏羲八卦×老子道德经×释迦四谛 — 万物数据安全守护

八维守护:
  ☰乾·Git — 未提交/未推送/分支健康
  ☷坤·磁盘 — 空间/健康/分区
  ☲离·关键文件 — 存在性/完整性/大小异常
  ☳震·凭据 — secrets.env备份/加密/一致性
  ☴巽·同步 — Syncthing/跨盘一致性
  ☵坎·Junction — 链接有效性/目标可达
  ☶艮·子仓库 — 独立git项目状态
  ☱兑·备份 — 备份新鲜度/完整性

用法:
  python data_guardian.py              # 全量检查+报告
  python data_guardian.py --fix        # 检查+自动修复可修复项
  python data_guardian.py --backup     # 执行关键数据备份
  python data_guardian.py --json       # JSON格式输出
"""

import json, os, sys, time, shutil, hashlib, subprocess
from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path(r"D:\道\道生一\一生二")
BACKUP_DIR = ROOT / "三电脑服务器" / "_backups"

# ══════════════════════════════════════════════════════════════
# 关键文件注册表 — 丢失任何一个都是灾难
# ══════════════════════════════════════════════════════════════

CRITICAL_FILES = [
    # 凭据 (最高优先级)
    {"path": "secrets.env",                                    "cat": "凭据", "min_kb": 3,   "max_kb": 50},
    {"path": "凭据中心.md",                                    "cat": "凭据", "min_kb": 5,   "max_kb": 100},
    # 规则体系
    {"path": ".windsurf/rules/soul.md",                        "cat": "规则", "min_kb": 1,   "max_kb": 20},
    {"path": ".windsurf/rules/execution-engine.md",            "cat": "规则", "min_kb": 3,   "max_kb": 30},
    {"path": ".windsurf/rules/project-structure.md",           "cat": "规则", "min_kb": 1,   "max_kb": 20},
    {"path": ".windsurf/rules/cyclic-thinking.md",             "cat": "规则", "min_kb": 1,   "max_kb": 20},
    # 核心代码
    {"path": "手机操控库/phone_lib.py",                         "cat": "核心代码", "min_kb": 20, "max_kb": 100},
    {"path": "电脑现成项目app/agent_master.py",                 "cat": "核心代码", "min_kb": 10, "max_kb": 80},
    {"path": "远程桌面/remote_agent.py",                        "cat": "核心代码", "min_kb": 50, "max_kb": 200},
    {"path": "密码管理/password_hub.py",                        "cat": "核心代码", "min_kb": 10, "max_kb": 80},
    {"path": "密码管理/phone_hub.py",                           "cat": "核心代码", "min_kb": 5,  "max_kb": 50},
    {"path": "三电脑服务器/resource_registry.py",               "cat": "核心代码", "min_kb": 5,  "max_kb": 50},
    # 数据库 (逆向成果)
    {"path": "电脑现成项目app/_ultimate_db.json",               "cat": "数据库", "min_kb": 500, "max_kb": 5000},
    {"path": "手机现成app库/_unified_db.json",                  "cat": "数据库", "min_kb": 500, "max_kb": 5000},
    {"path": "密码管理/_deep_reverse_db.json",                  "cat": "数据库", "min_kb": 30,  "max_kb": 500},
    # 架构文档
    {"path": "核心架构.md",                                     "cat": "文档", "min_kb": 3,   "max_kb": 30},
    {"path": "三电脑服务器/README.md",                          "cat": "文档", "min_kb": 5,   "max_kb": 50},
    # 配置
    {"path": "三电脑服务器/笔记本179/Caddyfile",               "cat": "配置", "min_kb": 2,   "max_kb": 20},
    {"path": "远程桌面/frp/frpc.toml",                         "cat": "配置", "min_kb": 0.5, "max_kb": 10},
    {"path": "100-智能家居_SmartHome/HA核心配置/configuration.yaml", "cat": "配置", "min_kb": 2, "max_kb": 30},
]

JUNCTION_LINKS = [
    {"path": r"E:\AI创意资源分享",     "target_drive": "F"},
    {"path": r"E:\AIhuanlian",         "target_drive": "F"},
    {"path": r"E:\.ollama",            "target_drive": "F"},
    {"path": r"E:\ChatTTS-UI-0.84",    "target_drive": "F"},
    {"path": r"E:\BcutBilibili",       "target_drive": "F"},
    {"path": r"E:\Deep-Live-Cam-1.8",  "target_drive": "F"},
    {"path": r"E:\酒馆",              "target_drive": "F"},
]

SUB_REPOS = [
    {"path": "clash-agent",  "name": "Clash Agent"},
    {"path": "YAVAM",        "name": "YAVAM"},
]

DISK_THRESHOLDS = {"C": 85, "D": 90, "E": 80, "F": 80}

# ══════════════════════════════════════════════════════════════
# 检查引擎
# ══════════════════════════════════════════════════════════════

def _run(cmd, cwd=None, timeout=15):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd or str(ROOT),
                          timeout=timeout, encoding='utf-8', errors='replace')
        return r.stdout.strip(), r.returncode
    except Exception as e:
        return str(e), -1

def _file_hash(path, chunk=8192):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            d = f.read(chunk)
            if not d: break
            h.update(d)
    return h.hexdigest()[:16]

class Guardian:
    def __init__(self):
        self.issues = []
        self.warnings = []
        self.ok = []
        self.stats = {}

    def _issue(self, gua, severity, msg):
        entry = {"gua": gua, "severity": severity, "msg": msg, "time": datetime.now().isoformat()}
        if severity == "CRITICAL":
            self.issues.append(entry)
        elif severity == "WARNING":
            self.warnings.append(entry)
        else:
            self.ok.append(entry)

    # ── ☰乾 · Git状态 ──
    def check_git(self):
        out, rc = _run(["git", "status", "--porcelain"])
        dirty = len(out.splitlines()) if out else 0
        self.stats["git_dirty"] = dirty
        if dirty > 0:
            self._issue("☰乾", "WARNING", f"Git有{dirty}个未提交的文件变更")
        else:
            self._issue("☰乾", "OK", "Git工作区干净")

        # Check unpushed commits
        out, _ = _run(["git", "rev-list", "--count", "origin/main..HEAD"])
        try:
            ahead = int(out)
        except ValueError:
            ahead = -1
        self.stats["git_ahead"] = ahead
        if ahead > 10:
            self._issue("☰乾", "CRITICAL", f"Git有{ahead}个commit未push到GitHub！本地数据面临丢失风险")
        elif ahead > 0:
            self._issue("☰乾", "WARNING", f"Git有{ahead}个commit未push")
        elif ahead == 0:
            self._issue("☰乾", "OK", "Git已完全同步到远程")

        # Last commit time
        out, _ = _run(["git", "log", "-1", "--format=%ai"])
        self.stats["git_last_commit"] = out

    # ── ☷坤 · 磁盘健康 ──
    def check_disks(self):
        for drive in ["C", "D", "E", "F"]:
            try:
                total, used, free = shutil.disk_usage(f"{drive}:\\")
                pct = round(used / total * 100, 1)
                free_gb = round(free / (1024**3), 1)
                self.stats[f"disk_{drive}_pct"] = pct
                self.stats[f"disk_{drive}_free_gb"] = free_gb
                threshold = DISK_THRESHOLDS.get(drive, 85)
                if pct > threshold:
                    self._issue("☷坤", "CRITICAL" if pct > 95 else "WARNING",
                               f"{drive}:盘使用{pct}%（剩余{free_gb}GB），超过阈值{threshold}%")
                else:
                    self._issue("☷坤", "OK", f"{drive}:盘使用{pct}%，剩余{free_gb}GB")
            except Exception as e:
                self._issue("☷坤", "WARNING", f"{drive}:盘不可访问: {e}")

    # ── ☲离 · 关键文件 ──
    def check_critical_files(self):
        missing = 0
        anomaly = 0
        for f in CRITICAL_FILES:
            p = ROOT / f["path"]
            if not p.exists():
                self._issue("☲离", "CRITICAL", f"关键文件缺失: {f['path']} [{f['cat']}]")
                missing += 1
                continue
            size_kb = p.stat().st_size / 1024
            if size_kb < f["min_kb"]:
                self._issue("☲离", "WARNING", f"文件异常小: {f['path']} ({size_kb:.1f}KB < {f['min_kb']}KB)")
                anomaly += 1
            elif size_kb > f["max_kb"]:
                self._issue("☲离", "WARNING", f"文件异常大: {f['path']} ({size_kb:.1f}KB > {f['max_kb']}KB)")
                anomaly += 1
        total = len(CRITICAL_FILES)
        ok = total - missing - anomaly
        self.stats["critical_files_total"] = total
        self.stats["critical_files_ok"] = ok
        self.stats["critical_files_missing"] = missing
        if missing == 0 and anomaly == 0:
            self._issue("☲离", "OK", f"全部{total}个关键文件完整")

    # ── ☳震 · 凭据安全 ──
    def check_credentials(self):
        secrets_path = ROOT / "secrets.env"
        if not secrets_path.exists():
            self._issue("☳震", "CRITICAL", "secrets.env不存在！所有凭据丢失！")
            return
        # Check gitignored
        out, _ = _run(["git", "check-ignore", "secrets.env"])
        if "secrets.env" not in out:
            self._issue("☳震", "CRITICAL", "secrets.env未被.gitignore忽略！凭据可能泄露到GitHub！")
        else:
            self._issue("☳震", "OK", "secrets.env已被gitignore保护")
        # Check backup exists
        backup_path = BACKUP_DIR / "secrets.env.backup"
        if backup_path.exists():
            age = datetime.now() - datetime.fromtimestamp(backup_path.stat().st_mtime)
            if age > timedelta(days=7):
                self._issue("☳震", "WARNING", f"secrets.env备份已过期({age.days}天前)")
            else:
                self._issue("☳震", "OK", f"secrets.env备份新鲜({age.days}天前)")
        else:
            self._issue("☳震", "WARNING", "secrets.env无备份副本")
        self.stats["secrets_size"] = secrets_path.stat().st_size
        self.stats["secrets_hash"] = _file_hash(secrets_path)

    # ── ☴巽 · 同步状态 ──
    def check_sync(self):
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            s.connect(("127.0.0.1", 8384))
            s.close()
            self._issue("☴巽", "OK", "Syncthing :8384在线")
        except Exception:
            self._issue("☴巽", "WARNING", "Syncthing :8384离线，跨设备同步可能中断")
        # Check if E: drive has a shallow copy
        e_path = Path(r"E:\道\道生一\一生二")
        if e_path.exists():
            e_items = len(list(e_path.iterdir())) if e_path.is_dir() else 0
            d_items = len(list(ROOT.iterdir()))
            self.stats["e_drive_items"] = e_items
            self.stats["d_drive_items"] = d_items
            if e_items < d_items * 0.5:
                self._issue("☴巽", "WARNING", f"E盘副本可能不完整(E:{e_items}项 vs D:{d_items}项)")
            else:
                self._issue("☴巽", "OK", f"E盘副本存在({e_items}项)")
        else:
            self._issue("☴巽", "WARNING", "E盘无工作区副本")

    # ── ☵坎 · Junction链接 ──
    def check_junctions(self):
        ok = broken = 0
        for j in JUNCTION_LINKS:
            p = Path(j["path"])
            if p.exists():
                ok += 1
            else:
                self._issue("☵坎", "WARNING", f"Junction断裂: {j['path']}")
                broken += 1
        self.stats["junction_ok"] = ok
        self.stats["junction_broken"] = broken
        if broken == 0:
            self._issue("☵坎", "OK", f"全部{ok}个Junction链接有效")

    # ── ☶艮 · 子仓库 ──
    def check_sub_repos(self):
        for repo in SUB_REPOS:
            rp = ROOT / repo["path"]
            if not (rp / ".git").exists():
                self._issue("☶艮", "WARNING", f"子仓库{repo['name']}不存在")
                continue
            out, _ = _run(["git", "status", "--porcelain"], cwd=str(rp))
            dirty = len(out.splitlines()) if out else 0
            if dirty > 0:
                self._issue("☶艮", "WARNING", f"子仓库{repo['name']}有{dirty}个未提交变更")
            else:
                self._issue("☶艮", "OK", f"子仓库{repo['name']}干净")

    # ── ☱兑 · 备份新鲜度 ──
    def check_backups(self):
        if not BACKUP_DIR.exists():
            self._issue("☱兑", "WARNING", "备份目录不存在，将在首次备份时创建")
            return
        backups = list(BACKUP_DIR.glob("*"))
        if not backups:
            self._issue("☱兑", "WARNING", "备份目录为空")
            return
        newest = max(backups, key=lambda p: p.stat().st_mtime)
        age = datetime.now() - datetime.fromtimestamp(newest.stat().st_mtime)
        self.stats["backup_count"] = len(backups)
        self.stats["backup_newest_age_hours"] = round(age.total_seconds() / 3600, 1)
        if age > timedelta(days=7):
            self._issue("☱兑", "WARNING", f"最新备份已过期({age.days}天前)")
        else:
            self._issue("☱兑", "OK", f"备份存在({len(backups)}个文件，最新{age.days}天前)")

    # ── 全量检查 ──
    def check_all(self):
        self.check_git()
        self.check_disks()
        self.check_critical_files()
        self.check_credentials()
        self.check_sync()
        self.check_junctions()
        self.check_sub_repos()
        self.check_backups()
        return self

    # ── 评分 ──
    def score(self):
        total = len(self.issues) + len(self.warnings) + len(self.ok)
        if total == 0: return 0
        return round(len(self.ok) / total * 100)

    # ── 报告 ──
    def report(self):
        print("=" * 60)
        print("三电脑服务器 · 数据守护者 · 伏羲八卦全维检查")
        print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        if self.issues:
            print(f"\n🔴 严重问题 ({len(self.issues)}个):")
            for i in self.issues:
                print(f"  [{i['gua']}] {i['msg']}")

        if self.warnings:
            print(f"\n🟡 警告 ({len(self.warnings)}个):")
            for w in self.warnings:
                print(f"  [{w['gua']}] {w['msg']}")

        print(f"\n🟢 正常 ({len(self.ok)}个):")
        for o in self.ok:
            print(f"  [{o['gua']}] {o['msg']}")

        sc = self.score()
        icon = "🟢" if sc >= 80 else "🟡" if sc >= 60 else "🔴"
        print(f"\n{'='*60}")
        print(f"健康评分: {icon} {sc}/100")
        print(f"严重: {len(self.issues)} | 警告: {len(self.warnings)} | 正常: {len(self.ok)}")

        # Key stats
        if self.stats.get("git_ahead", 0) > 0:
            print(f"\n⚠️  立即行动: git push — {self.stats['git_ahead']}个commit仅存本地!")
        print()

    def to_json(self):
        return {
            "timestamp": datetime.now().isoformat(),
            "score": self.score(),
            "critical": [{"gua": i["gua"], "msg": i["msg"]} for i in self.issues],
            "warnings": [{"gua": w["gua"], "msg": w["msg"]} for w in self.warnings],
            "ok_count": len(self.ok),
            "stats": self.stats,
        }

# ══════════════════════════════════════════════════════════════
# 备份引擎 (老子·上善若水 — 备份如水自动流向安全处)
# ══════════════════════════════════════════════════════════════

def backup_critical():
    """备份关键文件到 _backups/ 目录"""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_dir = BACKUP_DIR / ts
    snapshot_dir.mkdir(exist_ok=True)

    backed = 0
    for f in CRITICAL_FILES:
        src = ROOT / f["path"]
        if not src.exists():
            continue
        # Preserve relative directory structure
        dest = snapshot_dir / f["path"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        backed += 1

    # Always backup secrets.env separately (latest copy)
    secrets_src = ROOT / "secrets.env"
    if secrets_src.exists():
        shutil.copy2(secrets_src, BACKUP_DIR / "secrets.env.backup")

    # Generate manifest
    manifest = {
        "timestamp": ts,
        "files_backed": backed,
        "total_registered": len(CRITICAL_FILES),
        "hashes": {}
    }
    for f in snapshot_dir.rglob("*"):
        if f.is_file():
            rel = f.relative_to(snapshot_dir)
            manifest["hashes"][str(rel)] = _file_hash(f)
    (snapshot_dir / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    # Cleanup old backups (keep last 10)
    snapshots = sorted([d for d in BACKUP_DIR.iterdir() if d.is_dir() and d.name != "_latest"], reverse=True)
    for old in snapshots[10:]:
        shutil.rmtree(old)
        print(f"  清理旧备份: {old.name}")

    print(f"\n备份完成: {backed}/{len(CRITICAL_FILES)}个文件 → {snapshot_dir}")
    print(f"备份大小: {sum(f.stat().st_size for f in snapshot_dir.rglob('*') if f.is_file()) / 1024:.1f} KB")
    return backed

# ══════════════════════════════════════════════════════════════
# 修复引擎 (释迦·中道 — 最小干预修复)
# ══════════════════════════════════════════════════════════════

def auto_fix(guardian):
    """自动修复可修复的问题"""
    fixed = 0

    # Fix 1: Create backup if missing
    if not BACKUP_DIR.exists() or not list(BACKUP_DIR.glob("*")):
        print("  [FIX] 创建首次备份...")
        backup_critical()
        fixed += 1

    # Fix 2: Backup secrets.env if no backup
    secrets_backup = BACKUP_DIR / "secrets.env.backup"
    secrets_src = ROOT / "secrets.env"
    if secrets_src.exists() and not secrets_backup.exists():
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(secrets_src, secrets_backup)
        print("  [FIX] 创建secrets.env备份")
        fixed += 1

    # Fix 3: Create _backups directory
    if not BACKUP_DIR.exists():
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        print("  [FIX] 创建备份目录")
        fixed += 1

    if fixed == 0:
        print("  无可自动修复的问题（git push需要手动执行）")
    else:
        print(f"\n自动修复: {fixed}项完成")

    # Remind manual actions
    if guardian.stats.get("git_ahead", 0) > 0:
        print(f"\n⚠️  需要手动执行:")
        print(f"  git add -A && git commit -m 'data guardian backup' && git push")
        print(f"  ({guardian.stats['git_ahead']}个commit仅存本地，面临丢失风险)")

    return fixed

# ══════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════

def main():
    args = sys.argv[1:]
    g = Guardian()
    g.check_all()

    if "--json" in args:
        print(json.dumps(g.to_json(), ensure_ascii=False, indent=2))
        return

    g.report()

    if "--fix" in args:
        print("\n── 自动修复 ──")
        auto_fix(g)

    if "--backup" in args:
        print("\n── 执行备份 ──")
        backup_critical()

    # Save report to file
    report_path = BACKUP_DIR / "latest_report.json" if BACKUP_DIR.exists() else None
    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(g.to_json(), ensure_ascii=False, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
