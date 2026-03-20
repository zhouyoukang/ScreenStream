#!/usr/bin/env python3
"""
Windsurf Continue Bypass — 一键patch脚本 v5.0
==============================================
道生一(maxGeneratorInvocations=9999) → 一生二(+AutoContinue=ENABLED) → 二生三(+ParallelRollout) → 三生万物

5处patch (消除Continue触发 + 自动续接 + 并行rollout实验):
  P1. extension.js: maxGeneratorInvocations=0→9999
  P2. workbench.desktop.main.js: maxGeneratorInvocations=0→9999 (×2)
  P3. @exa/chat-client/index.js: maxGeneratorInvocations=0→9999
  P4. workbench.desktop.main.js: AutoContinue default DISABLED→ENABLED (核心突破)
  P5. extension.js: 注入ParallelRolloutConfig(2并行×50invocations) (实验性)

用法:
  python patch_continue_bypass.py              # 应用所有patch
  python patch_continue_bypass.py --verify     # 仅验证patch状态
  python patch_continue_bypass.py --rollback   # 非交互式回滚到最新原始备份
  python patch_continue_bypass.py --backup     # 仅备份不patch
  python patch_continue_bypass.py --watch      # 检测Windsurf更新并自动重新patch
  python patch_continue_bypass.py --status     # 完整状态报告(版本+patch+备份)
  python patch_continue_bypass.py --p5-only     # 仅应用P5(实验性ParallelRollout)

根因分析 (v5.0):
  - 服务端强制~25次invocation限制, 客户端maxGen=9999被服务端cap
  - 服务端发送terminationReason=MAX_INVOCATIONS触发Continue按钮
  - AutoContinue是Windsurf内置功能, 默认DISABLED(迁移逻辑强制UNSPECIFIED→DISABLED)
  - P4补丁将迁移逻辑改为: 非ENABLED→强制ENABLED, 使Continue时自动续接
"""

import os, sys, shutil, json, hashlib, re
from datetime import datetime
from pathlib import Path

def _find_windsurf():
    """Auto-detect Windsurf installation path."""
    candidates = [
        Path(os.environ.get("WINDSURF_PATH", "")),
        Path(r"D:\Windsurf\resources\app"),
        Path(r"C:\Users") / os.environ.get("USERNAME", "user") / "AppData" / "Local" / "Programs" / "Windsurf" / "resources" / "app",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Windsurf" / "resources" / "app",
    ]
    for c in candidates:
        if c.exists() and (c / "package.json").exists():
            return c
    return Path(r"D:\Windsurf\resources\app")

WINDSURF_BASE = _find_windsurf()
SCRIPT_DIR = Path(__file__).parent
BACKUP_DIR = SCRIPT_DIR / "_windsurf_backups"
STATE_FILE = BACKUP_DIR / "_patch_state.json"

FILES = {
    "extension": WINDSURF_BASE / "extensions" / "windsurf" / "dist" / "extension.js",
    "workbench": WINDSURF_BASE / "out" / "vs" / "workbench" / "workbench.desktop.main.js",
    "chat_client": WINDSURF_BASE / "node_modules" / "@exa" / "chat-client" / "index.js",
}

PATCHES = [
    {
        "id": "P1",
        "file": "extension",
        "old": "maxGeneratorInvocations=0",
        "new": "maxGeneratorInvocations=9999",
        "desc": "extension.js maxGen 0→9999",
        "expected_count": 1,
    },
    {
        "id": "P2",
        "file": "workbench",
        "old": "maxGeneratorInvocations=0",
        "new": "maxGeneratorInvocations=9999",
        "desc": "workbench.js maxGen 0→9999 (×2)",
        "expected_count": 2,
    },
    {
        "id": "P3",
        "file": "chat_client",
        "old": "maxGeneratorInvocations=0",
        "new": "maxGeneratorInvocations=9999",
        "desc": "chat-client maxGen 0→9999",
        "expected_count": 1,
    },
    {
        "id": "P4",
        "file": "workbench",
        "old": "C.autoContinueOnMaxGeneratorInvocations===AutoContinueOnMaxGeneratorInvocations.UNSPECIFIED&&(C.autoContinueOnMaxGeneratorInvocations=AutoContinueOnMaxGeneratorInvocations.DISABLED)",
        "new": "C.autoContinueOnMaxGeneratorInvocations!==AutoContinueOnMaxGeneratorInvocations.ENABLED  &&(C.autoContinueOnMaxGeneratorInvocations=AutoContinueOnMaxGeneratorInvocations.ENABLED )",
        "desc": "AutoContinue default DISABLED→ENABLED (核心突破)",
        "expected_count": 1,
    },
]

# ============================================================
# P6-P9: 从WF无限调优v5.6.29逆向提取的新补丁方案 (2026-03-18)
# 这些方案在Windsurf版本更新后P1-P4匹配失败时作为备选
# ============================================================
PATCHES_WF_EXTENDED = [
    {
        "id": "P6",
        "file": "workbench",
        "regex": True,
        "pattern": r'(\w+)\[\1\.MAX_INVOCATIONS=3\]="MAX_INVOCATIONS"',
        "replace": lambda m: f'{m.group(1)}[{m.group(1)}.MAX_INVOCATIONS=999999]="MAX_INVOCATIONS"',
        "desc": "WF方案E: workbench MAX_INVOCATIONS枚举 3→999999 (regex)",
    },
    {
        "id": "P7",
        "file": "workbench",
        "regex": True,
        "pattern": r'=\s*\(0,\s*(\w+)\.useMemo\)\(\(\)\s*=>\s*\{',
        "replace_first_only": True,
        "replace_str": "=(0,{useMemo_var}.useMemo)(()=>false,[",
        "desc": "WF方案F: workbench useMemo弹窗禁用→false (regex, 首次匹配)",
    },
    {
        "id": "P8",
        "file": "extension",
        "regex": True,
        "pattern": r'(\w+)\[\1\.MAX_INVOCATIONS=3\]="MAX_INVOCATIONS"',
        "replace": lambda m: f'{m.group(1)}[{m.group(1)}.MAX_INVOCATIONS=999999]="MAX_INVOCATIONS"',
        "desc": "WF方案C: extension.js MAX_INVOCATIONS枚举 3→999999 (regex)",
    },
    {
        "id": "P9",
        "file": "extension",
        "old": "executorConfig:{maxGeneratorInvocations:3}",
        "new": "executorConfig:{maxGeneratorInvocations:999999}",
        "desc": "WF方案A: extension.js executorConfig注入极大值",
        "expected_count": 1,
    },
]

REGEX_FALLBACKS = [
    re.compile(r'(this\.maxGeneratorInvocations\s*=\s*)0([,;\s])'),
    re.compile(r'(name:"max_generator_invocations".{0,200}?maxGeneratorInvocations\s*=\s*)0([,;\s])'),
]

AUTO_CONTINUE_REGEX = re.compile(
    r'(C\.autoContinueOnMaxGeneratorInvocations)==='
    r'(AutoContinueOnMaxGeneratorInvocations)\.UNSPECIFIED'
    r'&&\(\1=(\2)\.DISABLED\)'
)

# P5: ParallelRolloutConfig injection patterns
P5_CASCADE_CONFIG_TYPENAME = 'typeName="exa.cortex_pb.CascadeConfig"'
P5_PRC_TYPENAME = 'typeName="exa.cortex_pb.ParallelRolloutConfig"'
P5_MARKER = 'parallelRolloutConfig||'  # presence = P5 already applied


def _adaptive_patch(content, file_key):
    """Regex fallback when exact match fails (e.g., after Windsurf update changes formatting)."""
    patched = content
    count = 0
    for rx in REGEX_FALLBACKS:
        matches = list(rx.finditer(patched))
        for m in matches:
            old_val = m.group(0)
            new_val = m.group(1) + "9999" + m.group(2)
            patched = patched[:m.start()] + new_val + patched[m.end():]
            count += 1
            _log(f"  Regex fallback: '{old_val[:60]}' → 9999")
            break  # re-scan after replacement (positions shifted)
        if count > 0:
            break
    return patched, count


def _file_hash(path):
    """SHA256 of file for change detection."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def _get_windsurf_version():
    """Read Windsurf version from package.json."""
    pkg = WINDSURF_BASE / "package.json"
    if pkg.exists():
        try:
            return json.loads(pkg.read_text(encoding="utf-8")).get("version", "unknown")
        except Exception:
            pass
    return "unknown"


def _load_state():
    """Load persistent state (hashes, version, backup info)."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_state(state):
    """Save persistent state."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def backup_files(only_originals=False):
    """Backup files. If only_originals=True, skip files that are already patched."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backed = []
    state = _load_state()
    for key, path in FILES.items():
        if not path.exists():
            backed.append(f"  ❌ {path.name} not found")
            continue
        if only_originals:
            content = path.read_text(encoding="utf-8")
            has_patch = any(content.count(p["new"]) >= p["expected_count"] for p in PATCHES if p["file"] == key)
            if has_patch:
                backed.append(f"  ⏭️  {path.name} (already patched, skipping)")
                continue
        bk = BACKUP_DIR / f"{path.name}.{ts}.bak"
        shutil.copy2(path, bk)
        sz = bk.stat().st_size
        fh = _file_hash(path)
        backed.append(f"  ✅ {path.name} → {bk.name} ({sz:,}B) [{fh}]")
        state.setdefault("original_backups", {})
        if key not in state["original_backups"]:
            state["original_backups"][key] = {"file": str(bk), "hash": fh, "size": sz, "ts": ts}
    state["windsurf_version"] = _get_windsurf_version()
    state["last_backup"] = ts
    _save_state(state)
    print(f"备份完成 ({ts}):")
    for b in backed:
        print(b)
    return ts


def verify_patches():
    results = []
    for p in PATCHES:
        path = FILES[p["file"]]
        if not path.exists():
            results.append({"id": p["id"], "status": "FILE_MISSING", "desc": p["desc"]})
            continue
        content = path.read_text(encoding="utf-8")
        applied = content.count(p["new"])
        unapplied = content.count(p["old"])
        if applied >= p["expected_count"] and unapplied == 0:
            status = "APPLIED"
        elif unapplied >= p["expected_count"]:
            status = "NOT_APPLIED"
        elif applied > 0 and unapplied > 0:
            status = "PARTIAL"
        else:
            status = "UNKNOWN"
        results.append({
            "id": p["id"],
            "status": status,
            "applied": applied,
            "unapplied": unapplied,
            "desc": p["desc"],
            "hash": _file_hash(path) if path.exists() else None,
        })
    # P5 verification
    results.append(verify_p5())
    return results


def _find_class_name(content, type_name_str):
    """Find minified class variable name from its protobuf typeName."""
    idx = content.find(type_name_str)
    if idx < 0:
        return None
    chunk = content[max(0, idx - 600):idx]
    matches = re.findall(r'class\s+(\w+)\s+extends', chunk)
    return matches[-1] if matches else None


def apply_p5_parallel_rollout(dry_run=False):
    """P5: Inject ParallelRolloutConfig into CascadeConfig constructor.
    
    Dynamic approach (survives Windsurf updates):
    1. Find ParallelRolloutConfig class name via typeName
    2. Find CascadeConfig constructor via typeName
    3. Inject parallelRolloutConfig default after initPartial
    
    Returns: (success: bool, message: str)
    """
    ext_path = FILES["extension"]
    if not ext_path.exists():
        return False, "extension.js not found"
    
    content = ext_path.read_text(encoding="utf-8")
    
    # Check if already applied
    if P5_MARKER in content:
        return True, "P5 already applied"
    
    # Step 1: Find ParallelRolloutConfig class name
    prc_class = _find_class_name(content, P5_PRC_TYPENAME)
    if not prc_class:
        return False, "ParallelRolloutConfig class not found"
    
    # Step 2: Find CascadeConfig constructor
    # Pattern: constructor(X){super(),Y.proto3.util.initPartial(X,this)}static runtime=Y.proto3;static typeName="exa.cortex_pb.CascadeConfig"
    cc_rx = re.compile(
        r'(constructor\((\w+)\)\{super\(\),(\w+)\.proto3\.util\.initPartial\(\2,this\)\})'
        r'(static\s+runtime=\3\.proto3;static\s+' + re.escape(P5_CASCADE_CONFIG_TYPENAME) + r')'
    )
    cc_match = cc_rx.search(content)
    if not cc_match:
        return False, "CascadeConfig constructor pattern not found"
    
    old_ctor = cc_match.group(1)
    arg_var = cc_match.group(2)
    mod_var = cc_match.group(3)
    static_part = cc_match.group(4)
    
    # Step 3: Build new constructor with parallelRolloutConfig injection
    new_ctor = (
        f'constructor({arg_var}){{super(),{mod_var}.proto3.util.initPartial({arg_var},this);'
        f'this.parallelRolloutConfig||(this.parallelRolloutConfig='
        f'new {prc_class}({{numParallelRollouts:2,maxInvocationsPerRollout:50}}))}}'
    )
    
    old_full = old_ctor + static_part
    new_full = new_ctor + static_part
    
    count = content.count(old_full)
    if count != 1:
        return False, f"Expected 1 match for CascadeConfig constructor, found {count}"
    
    if dry_run:
        return True, f"P5 ready: inject {prc_class}(2×50) into CascadeConfig"
    
    new_content = content.replace(old_full, new_full)
    ext_path.write_text(new_content, encoding="utf-8")
    _log(f"  ✅ P5: ParallelRolloutConfig({prc_class}) injected — 2 parallel × 50 invocations")
    return True, f"P5 applied: {prc_class}(2×50)"


def verify_p5():
    """Verify P5 patch status."""
    ext_path = FILES["extension"]
    if not ext_path.exists():
        return {"id": "P5", "status": "FILE_MISSING", "desc": "ParallelRollout injection"}
    content = ext_path.read_text(encoding="utf-8")
    if P5_MARKER in content:
        return {"id": "P5", "status": "APPLIED", "desc": "ParallelRollout injection (experimental)"}
    if P5_CASCADE_CONFIG_TYPENAME in content:
        return {"id": "P5", "status": "NOT_APPLIED", "desc": "ParallelRollout injection (experimental)"}
    return {"id": "P5", "status": "UNKNOWN", "desc": "ParallelRollout injection (experimental)"}


def apply_patches():
    print("=" * 60)
    print(f"Windsurf Continue Bypass Patcher v5.0")
    print(f"Windsurf: {_get_windsurf_version()} @ {WINDSURF_BASE}")
    print("=" * 60)

    ts = backup_files(only_originals=True)
    print()

    total_applied = 0
    state = _load_state()
    for p in PATCHES:
        path = FILES[p["file"]]
        if not path.exists():
            print(f"  ❌ {p['id']}: {path.name} not found")
            continue
        content = path.read_text(encoding="utf-8")
        count = content.count(p["old"])
        if count == 0:
            already = content.count(p["new"])
            if already >= p["expected_count"]:
                print(f"  ⏭️  {p['id']}: Already applied ({p['desc']})")
                total_applied += already
                continue
            else:
                patched, rx_count = _adaptive_patch(content, p["file"])
                if rx_count > 0:
                    path.write_text(patched, encoding="utf-8")
                    print(f"  ⚡ {p['id']}: Regex fallback applied ({p['desc']})")
                    total_applied += rx_count
                else:
                    print(f"  ⚠️  {p['id']}: Pattern not found ({p['desc']})")
                continue
        new_content = content.replace(p["old"], p["new"])
        path.write_text(new_content, encoding="utf-8")
        verify = path.read_text(encoding="utf-8").count(p["new"])
        if verify >= p["expected_count"]:
            print(f"  ✅ {p['id']}: {p['desc']} ({verify}x)")
            total_applied += verify
        else:
            print(f"  ❌ {p['id']}: Verify failed ({p['desc']})")

    state["last_patch"] = datetime.now().isoformat()
    state["windsurf_version"] = _get_windsurf_version()
    state["patched_hashes"] = {key: _file_hash(path) for key, path in FILES.items() if path.exists()}
    _save_state(state)

    # P5: ParallelRollout (experimental)
    p5_ok, p5_msg = apply_p5_parallel_rollout()
    if p5_ok:
        total_applied += 1
        print(f"  {'⏭️ ' if 'already' in p5_msg else '✅'} P5: {p5_msg}")
    else:
        print(f"  ⚠️  P5: {p5_msg} (experimental, non-critical)")

    print(f"\n{'=' * 60}")
    print(f"Total: {total_applied} patches applied/verified")
    print(f"Backup: {BACKUP_DIR}")
    print(f"\n⚡ 激活: Ctrl+Shift+P → Reload Window")
    print(f"⚡ 验证: 新对话中观察是否超过20 tool calls不触发Continue")
    print(f"⚡ P5验证: 观察invocation数是否超过25 (实验性)")
    return total_applied


def rollback(force=True):
    """Non-interactive rollback. Finds oldest backup per file (=original)."""
    state = _load_state()
    orig = state.get("original_backups", {})
    baks = sorted(BACKUP_DIR.glob("*.bak"), key=lambda x: x.name)
    if not baks:
        print("  无备份文件")
        return

    file_originals = {}
    for b in baks:
        base = b.name.split(".")[0]
        if base == "extension":
            base = "extension.js"
        for key, path in FILES.items():
            if path.name == b.name.rsplit(".", 2)[0]:
                if key not in file_originals:
                    file_originals[key] = b

    print("回滚目标 (最早备份=原始文件):")
    for key, bak in file_originals.items():
        print(f"  {bak.name} ({bak.stat().st_size:,}B) → {FILES[key].name}")

    if not force:
        print("\n使用 --rollback --force 或 -y 跳过确认")
        print("回滚? (y/n): ", end="")
        if input().strip().lower() != "y":
            print("取消")
            return

    for key, bak in file_originals.items():
        path = FILES[key]
        shutil.copy2(bak, path)
        print(f"  ✅ {bak.name} → {path}")
    print("回滚完成。需Reload Window生效。")


def _log(msg):
    """Append to watch log (for scheduled task with no console)."""
    log_file = BACKUP_DIR / "_watch.log"
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    except Exception:
        pass
    print(msg)


def _apply_rate_limit_bypass():
    """Call patch_rate_limit_bypass.py apply to re-apply P6-P9."""
    import subprocess
    script = SCRIPT_DIR / "patch_rate_limit_bypass.py"
    if script.exists():
        try:
            result = subprocess.run([sys.executable, str(script), "apply"], capture_output=True, text=True, timeout=30)
            _log(f"P6-P9 rate limit bypass: {result.stdout.strip().split(chr(10))[-1] if result.stdout else 'no output'}")
        except Exception as e:
            _log(f"P6-P9 rate limit bypass failed: {e}")
    else:
        _log(f"⚠️ {script} not found, skipping P6-P9")


def watch():
    """Check if Windsurf updated (files changed) and auto-re-patch."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    state = _load_state()
    patched_hashes = state.get("patched_hashes", {})
    saved_ver = state.get("windsurf_version", "unknown")
    current_ver = _get_windsurf_version()

    if saved_ver != current_ver:
        _log(f"⚠️ Windsurf版本变更: {saved_ver} → {current_ver} — 自动重新patch")
        apply_patches()
        _apply_rate_limit_bypass()
        return True

    changed = False
    for key, path in FILES.items():
        if not path.exists():
            continue
        current_hash = _file_hash(path)
        saved_hash = patched_hashes.get(key)
        if saved_hash and current_hash != saved_hash:
            _log(f"⚠️ {path.name} 文件已变更 (hash: {saved_hash} → {current_hash})")
            changed = True

    if changed:
        results = verify_patches()
        needs_repatch = any(r["status"] != "APPLIED" for r in results)
        if needs_repatch:
            _log("Patch已丢失！自动重新patch...")
            apply_patches()
            _apply_rate_limit_bypass()
            return True
        else:
            _log("✅ Patch仍有效(可能是无关变更)")
            state["patched_hashes"] = {key: _file_hash(path) for key, path in FILES.items() if path.exists()}
            _save_state(state)
    else:
        _log(f"✅ Windsurf {current_ver} — patch有效")
    return False


def status():
    """Complete status report."""
    ver = _get_windsurf_version()
    state = _load_state()
    print("=" * 60)
    print(f"Windsurf Continue Bypass — Status Report")
    print("=" * 60)
    print(f"Windsurf版本: {ver}")
    print(f"安装路径: {WINDSURF_BASE}")
    print(f"上次patch: {state.get('last_patch', 'never')}")
    print()

    results = verify_patches()
    print("Patch状态:")
    for r in results:
        icon = "✅" if r["status"] == "APPLIED" else "❌" if r["status"] == "NOT_APPLIED" else "⚠️"
        print(f"  {icon} {r['id']}: {r['status']} — {r['desc']}")
    applied = sum(1 for r in results if r["status"] == "APPLIED")
    print(f"  → {applied}/{len(results)} APPLIED")
    print()

    baks = sorted(BACKUP_DIR.glob("*.bak"))
    print(f"备份: {len(baks)} files in {BACKUP_DIR}")
    orig = state.get("original_backups", {})
    for key, info in orig.items():
        p = Path(info["file"])
        exists = "✅" if p.exists() else "❌"
        print(f"  {exists} {key} 原始: {p.name} ({info['size']:,}B)")
    print()

    print(f"文件大小:")
    for key, path in FILES.items():
        if path.exists():
            sz = path.stat().st_size
            h = _file_hash(path)
            print(f"  {path.name}: {sz:,}B [{h}]")
    print("=" * 60)


def cleanup_backups(keep=3):
    """Keep only the N most recent backup sets per file."""
    groups = {}
    for b in BACKUP_DIR.glob("*.bak"):
        base = b.name.rsplit(".", 2)[0]
        groups.setdefault(base, []).append(b)
    removed = 0
    for base, files in groups.items():
        files.sort(key=lambda x: x.name, reverse=True)
        for old in files[keep:]:
            state = _load_state()
            orig_files = [Path(v["file"]) for v in state.get("original_backups", {}).values()]
            if old in orig_files:
                continue
            old.unlink()
            removed += 1
    if removed:
        print(f"清理: 删除 {removed} 个旧备份")


def main():
    args = sys.argv[1:]

    if "--verify" in args:
        results = verify_patches()
        print("Patch状态验证:")
        for r in results:
            icon = "✅" if r["status"] == "APPLIED" else "❌" if r["status"] == "NOT_APPLIED" else "⚠️"
            detail = f"applied={r.get('applied', '?')}, unapplied={r.get('unapplied', '?')}" if "applied" in r else ""
            print(f"  {icon} {r['id']}: {r['status']} — {r['desc']} {detail}")
        applied = sum(1 for r in results if r["status"] == "APPLIED")
        print(f"\n{applied}/{len(results)} patches verified")

    elif "--rollback" in args:
        force = "--force" in args or "-y" in args
        rollback(force=force)

    elif "--backup" in args:
        backup_files(only_originals=("--originals" in args))

    elif "--watch" in args:
        watch()

    elif "--p5-only" in args:
        ok, msg = apply_p5_parallel_rollout()
        print(f"{'✅' if ok else '❌'} P5: {msg}")

    elif "--status" in args:
        status()

    elif "--cleanup" in args:
        cleanup_backups(keep=3)

    else:
        apply_patches()

    if "--json" in args:
        results = verify_patches()
        print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
