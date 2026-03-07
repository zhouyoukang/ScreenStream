"""
VaM 资源管理 — VAR包/外观预设/服装/发型/脚本/资源扫描

v2: 整合 vamtb VarFile解析 + varbsorb 场景引用扫描
"""
import re
import json
import zlib
import zipfile
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from typing import Optional

from .config import VAM_CONFIG


# ── VAR命名规范 (from vamtb f_varsplit) ──

_VAR_NAME_RE = re.compile(
    r'^(?P<creator>[^.]+)\.(?P<asset>[^.]+)\.(?P<version>\d+|latest)\.var$'
)

# ── 场景引用正则 (from varbsorb ScanJsonFilesOperation) ──

_SCENE_REF_RE = re.compile(
    r'"(assetUrl|audioClip|url|uid|JsonFilePath|plugin#\d+|act1Target\d+ValueName)"'
    r'\s*:\s*"(?P<path>[^"]+\.[a-zA-Z]{2,6})"'
)

# ── VaM资源类型检测 (from vamtb helpers f_get_type) ──

_RESOURCE_TYPES = {
    '.json': 'preset', '.vap': 'appearance', '.vaj': 'animation',
    '.vam': 'morph', '.vmi': 'morph_info', '.vmb': 'morph_binary',
    '.cs': 'script', '.cslist': 'script_list', '.js': 'js_script',
    '.dll': 'plugin', '.assetbundle': 'asset_bundle',
    '.jpg': 'texture', '.png': 'texture', '.tif': 'texture',
    '.wav': 'audio', '.mp3': 'audio', '.ogg': 'audio',
    '.obj': 'mesh', '.fbx': 'mesh', '.glb': 'mesh',
}

# ── 遗留路径迁移 (from varbsorb MigrateLegacyPaths) ──

_LEGACY_PATH_MAP = {
    'Saves/Scripts/':  'Custom/Scripts/',
    'Saves/Assets/':   'Custom/Assets/',
    'Import/morphs/':  'Custom/Atom/Person/Morphs/',
    'Textures/':       'Custom/Atom/Person/Textures/',
}


# ── VAR命名解析 (from vamtb) ──

def parse_var_name(filename: str) -> Optional[dict]:
    """严格解析VAR文件名: creator.asset.version.var

    从vamtb f_varsplit()移植，增加版本校验。
    """
    m = _VAR_NAME_RE.match(filename)
    if not m:
        return None
    return {
        "creator": m.group("creator"),
        "asset": m.group("asset"),
        "version": m.group("version"),
        "full_name": f"{m.group('creator')}.{m.group('asset')}.{m.group('version')}",
    }


def is_valid_var_name(filename: str) -> bool:
    """检查是否为合法VAR文件名"""
    return _VAR_NAME_RE.match(filename) is not None


# ── VAR元数据读取 (from vamtb VarFile.meta) ──

def read_var_meta(var_path) -> Optional[dict]:
    """从VAR包中读取meta.json，无需解压整个文件。

    从vamtb VarFile类移植，使用zipfile直接读取。
    """
    var_path = Path(var_path)
    if not var_path.exists():
        return None
    try:
        with zipfile.ZipFile(var_path, 'r') as zf:
            if 'meta.json' not in zf.namelist():
                return None
            with zf.open('meta.json') as mf:
                return json.load(mf)
    except (zipfile.BadZipFile, json.JSONDecodeError, KeyError):
        return None


def get_var_detail(var_path) -> dict:
    """深度分析单个VAR包：元数据+内容清单+依赖+校验和。

    综合vamtb VarFile + varbsorb ScanVarPackagesOperation。
    """
    var_path = Path(var_path)
    result = {
        "name": var_path.name,
        "size_mb": round(var_path.stat().st_size / (1024 * 1024), 1),
        "valid_name": False,
        "meta": None,
        "files": [],
        "dependencies": [],
        "file_types": {},
        "crc32": None,
        "errors": [],
    }

    parsed = parse_var_name(var_path.name)
    if parsed:
        result["valid_name"] = True
        result.update(parsed)

    try:
        with zipfile.ZipFile(var_path, 'r') as zf:
            # 读取meta.json
            if 'meta.json' in zf.namelist():
                with zf.open('meta.json') as mf:
                    meta = json.load(mf)
                    result["meta"] = {
                        "creator": meta.get("creatorName", ""),
                        "package": meta.get("packageName", ""),
                        "version": meta.get("version", ""),
                        "license": meta.get("licenseType", ""),
                        "description": meta.get("description", ""),
                        "credits": meta.get("credits", ""),
                        "content_list": meta.get("contentList", []),
                        "dependencies": meta.get("dependencies", {}),
                        "custom_options": meta.get("customOptions", {}),
                    }
                    result["dependencies"] = list(meta.get("dependencies", {}).keys())
            else:
                result["errors"].append("missing meta.json")

            # 文件清单和类型统计
            type_counts = defaultdict(int)
            for info in zf.infolist():
                if info.filename.endswith('/'):
                    continue
                ext = Path(info.filename).suffix.lower()
                rtype = _RESOURCE_TYPES.get(ext, 'other')
                type_counts[rtype] += 1
                result["files"].append({
                    "path": info.filename,
                    "size": info.file_size,
                    "type": rtype,
                })
            result["file_types"] = dict(type_counts)
            result["file_count"] = len(result["files"])

    except zipfile.BadZipFile:
        result["errors"].append("corrupt zip file")
    except Exception as e:
        result["errors"].append(str(e))

    return result


def get_var_dependencies(var_path) -> list:
    """提取VAR包的依赖列表。

    从vamtb Db.search_deps()移植。
    """
    meta = read_var_meta(var_path)
    if not meta:
        return []
    return list(meta.get("dependencies", {}).keys())


def resolve_dependencies(var_path, max_depth: int = 10) -> dict:
    """递归解析VAR依赖链。

    从vamtb search_deps_recurse()移植，增加循环检测和深度限制。
    返回 {var_name: {"found": bool, "path": str|None, "depth": int}}
    """
    addon_path = VAM_CONFIG.ADDON_PACKAGES
    if not addon_path.exists():
        return {}

    # 建立名称→路径索引
    var_index = {}
    for f in addon_path.rglob("*.var"):
        parsed = parse_var_name(f.name)
        if parsed:
            var_index[parsed["full_name"]] = f
            # latest别名
            latest_key = f"{parsed['creator']}.{parsed['asset']}.latest"
            existing = var_index.get(latest_key)
            if existing is None or parsed["version"] > parse_var_name(existing.name).get("version", "0"):
                var_index[latest_key] = f

    result = {}
    visited = set()

    def _resolve(vpath, depth):
        if depth > max_depth:
            return
        deps = get_var_dependencies(vpath)
        for dep_name in deps:
            if dep_name in visited:
                continue
            visited.add(dep_name)
            dep_path = var_index.get(dep_name)
            result[dep_name] = {
                "found": dep_path is not None,
                "path": str(dep_path) if dep_path else None,
                "depth": depth,
            }
            if dep_path:
                _resolve(dep_path, depth + 1)

    _resolve(Path(var_path), 1)
    return result


def var_crc32(var_path) -> Optional[str]:
    """计算VAR包CRC32校验和。

    从vamtb file_utils移植。
    """
    try:
        crc = 0
        with open(var_path, 'rb') as f:
            while chunk := f.read(65536):
                crc = zlib.crc32(chunk, crc)
        return f"{crc & 0xFFFFFFFF:08x}"
    except OSError:
        return None


# ── VAR包管理 ──

def list_var_packages(top_n: int = 0) -> dict:
    """扫描所有.var插件包"""
    addon_path = VAM_CONFIG.ADDON_PACKAGES
    if not addon_path.exists():
        return {"count": 0, "total_size_mb": 0, "packages": []}

    packages = []
    total_size = 0
    invalid_names = []
    for f in addon_path.iterdir():
        if f.suffix == ".var":
            size = f.stat().st_size
            total_size += size
            parsed = parse_var_name(f.name)
            if parsed:
                packages.append({
                    "name": f.name,
                    "creator": parsed["creator"],
                    "asset": parsed["asset"],
                    "version": parsed["version"],
                    "size_mb": round(size / (1024 * 1024), 1),
                })
            else:
                invalid_names.append(f.name)
                packages.append({
                    "name": f.name,
                    "creator": "unknown",
                    "size_mb": round(size / (1024 * 1024), 1),
                })

    packages.sort(key=lambda x: -x["size_mb"])
    result = {
        "count": len(packages),
        "total_size_mb": round(total_size / (1024 * 1024), 1),
        "total_size_gb": round(total_size / (1024 ** 3), 2),
    }
    if invalid_names:
        result["invalid_names"] = invalid_names
    if top_n > 0:
        result["top"] = packages[:top_n]
    else:
        result["packages"] = packages
    return result


def get_var_creators() -> dict:
    """按创作者统计VAR包"""
    addon_path = VAM_CONFIG.ADDON_PACKAGES
    if not addon_path.exists():
        return {}

    creators = defaultdict(lambda: {"count": 0, "size_mb": 0})
    for f in addon_path.iterdir():
        if f.suffix == ".var":
            parts = f.stem.split(".")
            creator = parts[0] if len(parts) >= 2 else "unknown"
            creators[creator]["count"] += 1
            creators[creator]["size_mb"] += round(f.stat().st_size / (1024 * 1024), 1)

    return dict(sorted(creators.items(), key=lambda x: -x[1]["count"]))


def search_var(keyword: str) -> list:
    """按关键词搜索VAR包"""
    addon_path = VAM_CONFIG.ADDON_PACKAGES
    if not addon_path.exists():
        return []

    kw = keyword.lower()
    results = []
    for f in addon_path.iterdir():
        if f.suffix == ".var" and kw in f.name.lower():
            results.append({
                "name": f.name,
                "size_mb": round(f.stat().st_size / (1024 * 1024), 1),
                "path": str(f),
            })
    return results


# ── 外观预设管理 ──

def list_appearances() -> list:
    """列出所有外观预设"""
    appearances = []
    base = VAM_CONFIG.APPEARANCES_DIR
    if not base.exists():
        return appearances

    for f in base.rglob("*"):
        if f.suffix in VAM_CONFIG.APPEARANCE_EXTENSIONS:
            appearances.append({
                "name": f.stem,
                "path": str(f),
                "size_kb": round(f.stat().st_size / 1024, 1),
            })
    return appearances


# ── 服装管理 ──

def list_clothing() -> list:
    """列出所有自定义服装"""
    items = []
    base = VAM_CONFIG.CLOTHING_DIR
    if not base.exists():
        return items

    for f in base.rglob("*"):
        if f.is_file() and f.suffix in {".json", ".vaj", ".vam"}:
            items.append({
                "name": f.stem,
                "path": str(f),
                "category": f.parent.name,
            })
    return items


# ── 发型管理 ──

def list_hair() -> list:
    """列出所有自定义发型"""
    items = []
    base = VAM_CONFIG.HAIR_DIR
    if not base.exists():
        return items

    for f in base.rglob("*"):
        if f.is_file() and f.suffix in {".json", ".vaj", ".vam"}:
            items.append({
                "name": f.stem,
                "path": str(f),
            })
    return items


# ── C#脚本管理 ──

def list_scripts() -> list:
    """列出所有C#/JS脚本"""
    scripts = []
    base = VAM_CONFIG.SCRIPTS_DIR
    if not base.exists():
        return scripts

    for f in base.rglob("*"):
        if f.suffix in VAM_CONFIG.SCRIPT_EXTENSIONS:
            scripts.append({
                "name": f.name,
                "path": str(f),
                "size_kb": round(f.stat().st_size / 1024, 1),
                "type": f.suffix,
                "dir": f.parent.name if f.parent != base else "root",
            })
    return scripts


def create_script(name: str, code: str, subdir: str = None) -> str:
    """创建新的C#脚本"""
    if subdir:
        target = VAM_CONFIG.SCRIPTS_DIR / subdir / name
    else:
        target = VAM_CONFIG.SCRIPTS_DIR / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(code, encoding="utf-8")
    return str(target)


# ── 资源文件(人物/场景包) ──

def list_resource_files() -> dict:
    """列出资源文件目录内容"""
    base = VAM_CONFIG.RESOURCES_DIR
    if not base.exists():
        return {"exists": False}

    result = {"exists": True, "categories": {}}
    for d in base.iterdir():
        if d.is_dir():
            file_count = sum(1 for _ in d.rglob("*") if _.is_file())
            result["categories"][d.name] = {"files": file_count, "path": str(d)}
    return result


# ── 全盘扫描 ──

def full_scan() -> dict:
    """执行完整资源扫描"""
    scan = {
        "scan_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "var_packages": list_var_packages(top_n=20),
        "scripts": list_scripts(),
        "appearances": list_appearances(),
        "resource_files": list_resource_files(),
    }

    # 目录统计
    dirs_to_check = {
        "Saves/scene": VAM_CONFIG.SCENES_DIR,
        "Custom/Scripts": VAM_CONFIG.SCRIPTS_DIR,
        "AddonPackages": VAM_CONFIG.ADDON_PACKAGES,
        "Custom/Clothing": VAM_CONFIG.CLOTHING_DIR,
        "Custom/Hair": VAM_CONFIG.HAIR_DIR,
        "Custom/Assets": VAM_CONFIG.ASSETS_DIR,
        "BepInEx/plugins": VAM_CONFIG.BEPINEX_PLUGINS,
        "Cache": VAM_CONFIG.CACHE_DIR,
    }

    scan["directory_stats"] = {}
    for name, path in dirs_to_check.items():
        if path.exists():
            file_count = sum(1 for _ in path.rglob("*") if _.is_file())
            scan["directory_stats"][name] = {"files": file_count, "path": str(path)}
        else:
            scan["directory_stats"][name] = {"files": 0, "exists": False}

    return scan


# ── 磁盘空间 ──

def disk_usage() -> dict:
    """检查VaM相关驱动器磁盘空间"""
    import shutil
    result = {}
    for drive in ["F:", "D:", "E:"]:
        try:
            total, used, free = shutil.disk_usage(drive + "\\")
            result[drive] = {
                "total_gb": round(total / (1024 ** 3), 1),
                "used_gb": round(used / (1024 ** 3), 1),
                "free_gb": round(free / (1024 ** 3), 1),
                "used_pct": round(used / total * 100, 1),
            }
        except Exception:
            pass
    return result


# ── 场景引用扫描 (from varbsorb) ──

def _migrate_legacy_path(ref_path: str) -> str:
    """迁移旧版VaM路径到新格式。

    从varbsorb MigrateLegacyPaths移植。
    """
    normalized = ref_path.replace('\\', '/')
    for old, new in _LEGACY_PATH_MAP.items():
        if normalized.startswith(old):
            return new + normalized[len(old):]
    return ref_path


def scan_scene_references(scene_path) -> dict:
    """扫描场景JSON中所有资源引用。

    从varbsorb ScanJsonFilesOperation的_findFilesFastRegex移植。
    返回 {"references": [...], "var_refs": [...], "local_refs": [...], "broken": [...]}
    """
    scene_path = Path(scene_path)
    if not scene_path.exists():
        return {"error": "file not found"}

    try:
        content = scene_path.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        content = scene_path.read_text(encoding='utf-8-sig')

    matches = _SCENE_REF_RE.finditer(content)
    var_refs = set()
    local_refs = set()
    all_refs = []

    for m in matches:
        ref_path = m.group('path')
        ref_path = _migrate_legacy_path(ref_path)

        if ':' in ref_path:
            # VAR包引用: creator.asset.version:/path/to/file
            var_refs.add(ref_path.split(':')[0])
        else:
            local_refs.add(ref_path)

        all_refs.append({
            "field": m.group(1),
            "path": ref_path,
            "is_var": ':' in ref_path,
        })

    # 检查本地引用完整性
    broken = []
    vam_root = VAM_CONFIG.VAM_INSTALL
    scene_dir = scene_path.parent
    for ref in local_refs:
        # 尝试相对于场景目录和VaM根目录
        abs_scene = scene_dir / ref
        abs_vam = vam_root / ref
        if not abs_scene.exists() and not abs_vam.exists():
            broken.append(ref)

    return {
        "total_refs": len(all_refs),
        "var_packages_used": sorted(var_refs),
        "local_files_used": sorted(local_refs),
        "broken_refs": broken,
        "references": all_refs[:100],
    }


def check_scene_integrity(scene_path) -> dict:
    """场景完整性检查：验证所有引用的资源是否存在。

    综合varbsorb的引用扫描 + vamtb的VAR索引。
    """
    refs = scan_scene_references(scene_path)
    if "error" in refs:
        return refs

    # 检查VAR包依赖
    addon_path = VAM_CONFIG.ADDON_PACKAGES
    var_index = set()
    if addon_path.exists():
        for f in addon_path.rglob("*.var"):
            parsed = parse_var_name(f.name)
            if parsed:
                var_index.add(parsed["full_name"])

    missing_vars = []
    for var_ref in refs.get("var_packages_used", []):
        if var_ref not in var_index:
            missing_vars.append(var_ref)

    return {
        "scene": str(scene_path),
        "total_refs": refs["total_refs"],
        "var_packages_used": len(refs["var_packages_used"]),
        "local_files_used": len(refs["local_files_used"]),
        "missing_vars": missing_vars,
        "broken_local_refs": refs["broken_refs"],
        "healthy": len(missing_vars) == 0 and len(refs["broken_refs"]) == 0,
    }


# ── VAR包健康报告 ──

def var_health_report(top_n: int = 10) -> dict:
    """VAR包健康报告：无效命名/缺少meta/损坏文件。

    综合vamtb+varbsorb的扫描逻辑。
    """
    addon_path = VAM_CONFIG.ADDON_PACKAGES
    if not addon_path.exists():
        return {"error": "addon path not found"}

    report = {
        "total": 0,
        "valid_names": 0,
        "invalid_names": [],
        "missing_meta": [],
        "corrupt": [],
        "has_dependencies": 0,
        "total_dependencies": 0,
        "largest": [],
    }

    all_vars = []
    for f in addon_path.iterdir():
        if f.suffix != ".var":
            continue
        report["total"] += 1
        size = f.stat().st_size
        all_vars.append((f, size))

        if is_valid_var_name(f.name):
            report["valid_names"] += 1
        else:
            report["invalid_names"].append(f.name)

        try:
            meta = read_var_meta(f)
            if meta is None:
                report["missing_meta"].append(f.name)
            else:
                deps = meta.get("dependencies", {})
                if deps:
                    report["has_dependencies"] += 1
                    report["total_dependencies"] += len(deps)
        except Exception:
            report["corrupt"].append(f.name)

    all_vars.sort(key=lambda x: -x[1])
    report["largest"] = [
        {"name": f.name, "size_mb": round(s / (1024 * 1024), 1)}
        for f, s in all_vars[:top_n]
    ]

    report["health_score"] = round(
        (report["valid_names"] / max(report["total"], 1)) * 50
        + ((report["total"] - len(report["missing_meta"])) / max(report["total"], 1)) * 30
        + ((report["total"] - len(report["corrupt"])) / max(report["total"], 1)) * 20
    )

    return report


# ═══════════════════════════════════════════════════════
# 依赖图 (from gicstin/VPM DependencyGraph.cs)
# ═══════════════════════════════════════════════════════

_CONTENT_TYPE_MAP = {
    ".json": "scene", ".vap": "preset", ".vam": "asset_config",
    ".jpg": "texture", ".jpeg": "texture", ".png": "texture",
    ".tif": "texture", ".tiff": "texture",
    ".assetbundle": "asset_bundle",
    ".cs": "script", ".cslist": "script",
    ".vmi": "morph_info", ".vmb": "morph_binary",
    ".wav": "audio", ".mp3": "audio", ".ogg": "audio",
    ".bvh": "animation", ".anim": "animation",
}


def _classify_var_contents(var_path) -> dict:
    """统计VAR包内文件类型分布（from VPM OptimizedVarScanner）。"""
    counts = {}
    try:
        with zipfile.ZipFile(str(var_path), "r") as zf:
            for name in zf.namelist():
                ext = os.path.splitext(name)[1].lower()
                ctype = _CONTENT_TYPE_MAP.get(ext, "other")
                counts[ctype] = counts.get(ctype, 0) + 1
                # 细分VaM自定义目录
                nl = name.lower()
                if "/custom/clothing/" in nl:
                    counts["clothing"] = counts.get("clothing", 0) + 1
                elif "/custom/hair/" in nl:
                    counts["hair"] = counts.get("hair", 0) + 1
                elif "/custom/atom/person/morphs/" in nl:
                    counts["morph"] = counts.get("morph", 0) + 1
                elif "/saves/scene/" in nl and ext == ".json":
                    counts["scene_file"] = counts.get("scene_file", 0) + 1
                elif "/saves/person/appearance/" in nl:
                    counts["look"] = counts.get("look", 0) + 1
                elif "/saves/person/pose/" in nl:
                    counts["pose"] = counts.get("pose", 0) + 1
    except Exception:
        pass
    return counts


class VarDependencyGraph:
    """VAR包双向依赖图（from VPM DependencyGraph.cs移植）。

    功能:
    - 正向依赖: 包A依赖哪些包
    - 反向依赖: 谁依赖包A
    - 孤儿检测: 没有任何包依赖的包
    - 关键包检测: 被大量包依赖的核心包
    - 传递依赖链: 完整依赖树
    - 重复/版本检测: 同一包的多个版本
    """

    def __init__(self):
        self._forward = {}   # pkg -> set(deps)
        self._reverse = {}   # pkg -> set(dependents)
        self._by_base = {}   # "creator.name" -> set(versions)
        self._all = set()
        self._meta_cache = {}

    def build(self, addon_path=None):
        """从AddonPackages目录构建依赖图。"""
        if addon_path is None:
            addon_path = VAM_CONFIG.ADDON_PACKAGES
        addon_path = Path(addon_path)
        if not addon_path.exists():
            return

        # Pass 1: 收集所有包
        for f in addon_path.iterdir():
            if f.suffix != ".var":
                continue
            parsed = parse_var_name(f.name)
            if not parsed:
                continue
            full = parsed["full_name"]
            base = f"{parsed['creator']}.{parsed['asset']}"
            self._all.add(full)
            self._by_base.setdefault(base, set()).add(full)
            self._forward.setdefault(full, set())

        # Pass 2: 构建依赖关系
        for f in addon_path.iterdir():
            if f.suffix != ".var":
                continue
            parsed = parse_var_name(f.name)
            if not parsed:
                continue
            full = parsed["full_name"]
            try:
                meta = read_var_meta(f)
                if meta and meta.get("dependencies"):
                    self._meta_cache[full] = meta
                    for dep_name in meta["dependencies"]:
                        resolved = self._resolve(dep_name)
                        for r in resolved:
                            self._forward[full].add(r)
                            self._reverse.setdefault(r, set()).add(full)
            except Exception:
                pass

    def _resolve(self, dep_str: str) -> list:
        """解析依赖字符串（支持.latest和精确版本）。"""
        if dep_str.endswith(".latest"):
            base = dep_str.rsplit(".", 1)[0]
            versions = self._by_base.get(base, set())
            return list(versions) if versions else [dep_str]
        if dep_str in self._all:
            return [dep_str]
        # 尝试匹配基础名
        parts = dep_str.rsplit(".", 1)
        if len(parts) == 2:
            base = parts[0]
            if base in self._by_base:
                return list(self._by_base[base])
        return [dep_str]

    def get_dependencies(self, pkg: str) -> list:
        """获取包的直接依赖。"""
        return list(self._forward.get(pkg, set()))

    def get_dependents(self, pkg: str) -> list:
        """获取依赖此包的所有包（反向依赖）。"""
        result = set()
        if pkg in self._reverse:
            result.update(self._reverse[pkg])
        # 也检查同基础名的其他版本
        parsed = parse_var_name(pkg + ".var") if not pkg.endswith(".var") else parse_var_name(pkg)
        if parsed:
            base = f"{parsed['creator']}.{parsed['asset']}"
            for ver in self._by_base.get(base, set()):
                if ver in self._reverse:
                    result.update(self._reverse[ver])
        return list(result)

    def get_orphans(self) -> list:
        """获取孤儿包（没有任何包依赖它们）。"""
        return [p for p in self._all
                if p not in self._reverse or len(self._reverse[p]) == 0]

    def get_critical(self, min_dependents: int = 3) -> list:
        """获取关键包（被大量包依赖）。"""
        critical = []
        for pkg, deps in self._reverse.items():
            if len(deps) >= min_dependents:
                critical.append({"package": pkg, "dependent_count": len(deps)})
        critical.sort(key=lambda x: -x["dependent_count"])
        return critical

    def get_full_chain(self, pkg: str, max_depth: int = 10) -> set:
        """获取完整传递依赖链。"""
        chain = set()
        visited = set()
        self._collect_recursive(pkg, chain, visited, 0, max_depth)
        return chain

    def _collect_recursive(self, pkg, chain, visited, depth, max_depth):
        if depth >= max_depth or pkg in visited:
            return
        visited.add(pkg)
        for dep in self._forward.get(pkg, set()):
            chain.add(dep)
            self._collect_recursive(dep, chain, visited, depth + 1, max_depth)

    def get_duplicates(self) -> list:
        """检测重复包（同一creator.name的多个版本）。"""
        dupes = []
        for base, versions in self._by_base.items():
            if len(versions) > 1:
                sorted_v = sorted(versions)
                dupes.append({"base_name": base, "versions": sorted_v,
                              "count": len(sorted_v)})
        dupes.sort(key=lambda x: -x["count"])
        return dupes

    def get_missing(self) -> list:
        """检测缺失依赖（被引用但不存在）。"""
        missing = set()
        for pkg, deps in self._forward.items():
            for dep in deps:
                if dep not in self._all:
                    missing.add(dep)
        return sorted(missing)

    def summary(self) -> dict:
        """依赖图摘要。"""
        total_links = sum(len(d) for d in self._forward.values())
        return {
            "total_packages": len(self._all),
            "total_links": total_links,
            "orphans": len(self.get_orphans()),
            "critical_packages": len(self.get_critical()),
            "duplicates": len(self.get_duplicates()),
            "missing_deps": len(self.get_missing()),
        }


# ── 增强型VAR扫描 (from VPM OptimizedVarScanner + ContentTagScanner) ──

def var_deep_scan(var_path) -> dict:
    """VAR包深度扫描：元数据+内容分类+依赖+完整性。

    综合VPM的OptimizedVarScanner和ContentTagScanner。
    """
    var_path = Path(var_path)
    result = {
        "file": var_path.name,
        "size_mb": round(var_path.stat().st_size / (1024 * 1024), 2),
    }

    parsed = parse_var_name(var_path.name)
    if parsed:
        result["creator"] = parsed["creator"]
        result["asset"] = parsed["asset"]
        result["version"] = parsed["version"]
    else:
        result["valid_name"] = False
        return result

    result["valid_name"] = True
    result["content_types"] = _classify_var_contents(var_path)

    meta = read_var_meta(var_path)
    if meta:
        result["description"] = meta.get("description", "")
        result["license"] = meta.get("licenseType", "")
        result["dependencies"] = list(meta.get("dependencies", {}).keys())
        result["preload_morphs"] = meta.get("customOptions", {}).get(
            "preloadMorphs", "false") == "true"
    else:
        result["missing_meta"] = True

    result["crc32"] = var_crc32(var_path)
    return result
