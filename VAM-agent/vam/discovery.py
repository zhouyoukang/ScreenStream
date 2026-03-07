"""
VaM 资源发现引擎 — 自动索引VaM安装中的真实资源

扫描2098+ VAR包 (75.2GB) 中的:
  - 外观预设 (.vap)
  - 服装 (.vab/.vam/.vaj)
  - 发型 (.vab/.vam/.vaj)
  - 场景 (.json)
  - 插件/脚本 (.cs/.cslist)
  - Morph (.vmi/.vmb)
  - 纹理 (.jpg/.png)
  - 动画 (.vmd/.bvh) — MMD/BVH动画文件 (v2.4+)
  - 运动 (.funscript) — 触觉设备运动脚本 (v2.4+)

架构:
  ResourceIndex      — 资源索引 (内存缓存 + JSON持久化)
  VarScanner         — VAR包批量扫描器
  AssetResolver      — 资源路径解析 (VAR内路径 ↔ 本地路径)
  LocalAssetScanner  — 本地非VAR资源扫描
  DepsScanner        — GitHub deps/目录扫描 (整合的第三方项目索引)
  VarCleaner         — VAR包清理工具 (冗余文件检测, from vam-varbsorb)
"""
import json
import os
import time
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

from .config import VAM_CONFIG


# ── 资源分类规则 ──

CATEGORY_RULES = {
    "appearance": {
        "paths": ["Custom/Atom/Person/Appearance"],
        "extensions": {".vap", ".json"},
    },
    "clothing": {
        "paths": ["Custom/Clothing"],
        "extensions": {".vab", ".vam", ".vaj"},
    },
    "hair": {
        "paths": ["Custom/Hair"],
        "extensions": {".vab", ".vam", ".vaj"},
    },
    "scene": {
        "paths": ["Saves/scene"],
        "extensions": {".json"},
    },
    "morph": {
        "paths": ["Custom/Atom/Person/Morphs", "Morphs"],
        "extensions": {".vmi", ".vmb", ".dsf"},
    },
    "texture": {
        "paths": ["Custom/Atom/Person/Textures", "Textures"],
        "extensions": {".jpg", ".png", ".tif", ".tga"},
    },
    "plugin": {
        "paths": ["Custom/Scripts"],
        "extensions": {".cs", ".cslist"},
    },
    "asset": {
        "paths": ["Custom/Assets", "Custom/SubScene"],
        "extensions": {".assetbundle", ".scene"},
    },
    "pose": {
        "paths": ["Custom/Atom/Person/Pose"],
        "extensions": {".json", ".vap"},
    },
    "animation": {
        "paths": ["Custom/Atom/Person/Animations", "Saves/PluginData/mmd2timeline"],
        "extensions": {".vmd", ".bvh", ".json"},
    },
    "motion": {
        "paths": ["Custom/Atom/Person/PluginData"],
        "extensions": {".funscript", ".json"},
    },
}


class ResourceEntry:
    """单个资源条目"""
    __slots__ = ("var_name", "var_path", "internal_path",
                 "category", "name", "creator", "extension")

    def __init__(self, var_name: str, var_path: str,
                 internal_path: str, category: str):
        self.var_name = var_name
        self.var_path = var_path
        self.internal_path = internal_path
        self.category = category
        self.extension = Path(internal_path).suffix.lower()
        self.name = Path(internal_path).stem
        self.creator = var_name.split(".")[0] if "." in var_name else ""

    @property
    def vam_reference(self) -> str:
        """VaM内部引用路径 (用于场景JSON)"""
        return f"{self.var_name}:/{self.internal_path}"

    def to_dict(self) -> dict:
        return {
            "var": self.var_name,
            "path": self.internal_path,
            "category": self.category,
            "name": self.name,
            "creator": self.creator,
            "ref": self.vam_reference,
        }


class ResourceIndex:
    """
    资源索引 — 内存缓存 + JSON持久化

    首次扫描约需1-3分钟(2098 VARs), 后续从缓存加载<1秒
    """

    CACHE_FILE = "resource_index.json"

    def __init__(self):
        self.entries: list[ResourceEntry] = []
        self.by_category: dict[str, list[ResourceEntry]] = defaultdict(list)
        self.by_creator: dict[str, list[ResourceEntry]] = defaultdict(list)
        self.var_count: int = 0
        self.scan_time: float = 0
        self._loaded: bool = False

    @property
    def cache_path(self) -> Path:
        return VAM_CONFIG.AGENT_ROOT / "cache" / self.CACHE_FILE

    def load_cache(self) -> bool:
        """从缓存加载索引"""
        if not self.cache_path.exists():
            return False
        try:
            data = json.loads(self.cache_path.read_text(encoding="utf-8"))
            for entry_data in data.get("entries", []):
                entry = ResourceEntry(
                    entry_data["var"], "", entry_data["path"],
                    entry_data["category"],
                )
                entry.creator = entry_data.get("creator", "")
                entry.name = entry_data.get("name", "")
                self.entries.append(entry)
                self.by_category[entry.category].append(entry)
                self.by_creator[entry.creator].append(entry)
            self.var_count = data.get("var_count", 0)
            self.scan_time = data.get("scan_time", 0)
            self._loaded = True
            return True
        except Exception:
            return False

    def save_cache(self):
        """保存索引到缓存"""
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "var_count": self.var_count,
            "scan_time": self.scan_time,
            "total_entries": len(self.entries),
            "by_category": {k: len(v) for k, v in self.by_category.items()},
            "entries": [e.to_dict() for e in self.entries],
        }
        self.cache_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )

    def add(self, entry: ResourceEntry):
        self.entries.append(entry)
        self.by_category[entry.category].append(entry)
        self.by_creator[entry.creator].append(entry)

    # ── 查询方法 ──

    def find(self, category: str = "", creator: str = "",
             name_contains: str = "", limit: int = 50) -> list[ResourceEntry]:
        """通用查询"""
        results = self.entries
        if category:
            results = self.by_category.get(category, [])
        if creator:
            creator_lower = creator.lower()
            results = [e for e in results if e.creator.lower() == creator_lower]
        if name_contains:
            search_lower = name_contains.lower()
            results = [e for e in results if search_lower in e.name.lower()]
        return results[:limit]

    def appearances(self, creator: str = "",
                    limit: int = 50) -> list[ResourceEntry]:
        """查询外观预设"""
        return self.find("appearance", creator=creator, limit=limit)

    def clothing(self, creator: str = "",
                 limit: int = 50) -> list[ResourceEntry]:
        return self.find("clothing", creator=creator, limit=limit)

    def hair(self, creator: str = "",
             limit: int = 50) -> list[ResourceEntry]:
        return self.find("hair", creator=creator, limit=limit)

    def scenes(self, creator: str = "",
               limit: int = 50) -> list[ResourceEntry]:
        return self.find("scene", creator=creator, limit=limit)

    def plugins(self, creator: str = "",
                limit: int = 50) -> list[ResourceEntry]:
        return self.find("plugin", creator=creator, limit=limit)

    def morphs(self, name_contains: str = "",
               limit: int = 50) -> list[ResourceEntry]:
        return self.find("morph", name_contains=name_contains, limit=limit)

    def poses(self, limit: int = 50) -> list[ResourceEntry]:
        return self.find("pose", limit=limit)

    def creators(self) -> list[tuple]:
        """列出所有创作者及其资源数"""
        counts = Counter(e.creator for e in self.entries)
        return counts.most_common()

    def summary(self) -> dict:
        return {
            "var_count": self.var_count,
            "total_entries": len(self.entries),
            "scan_time_sec": round(self.scan_time, 1),
            "categories": {k: len(v) for k, v in self.by_category.items()},
            "top_creators": self.creators()[:20],
        }


class VarScanner:
    """
    VAR包批量扫描器

    扫描AddonPackages下所有.var文件, 提取资源信息到索引
    """

    def __init__(self, packages_dir: Optional[Path] = None):
        self.packages_dir = packages_dir or VAM_CONFIG.ADDON_PACKAGES

    def _classify(self, filepath: str) -> Optional[str]:
        """根据内部路径分类"""
        ext = Path(filepath).suffix.lower()
        for category, rules in CATEGORY_RULES.items():
            if ext not in rules["extensions"]:
                continue
            for prefix in rules["paths"]:
                if filepath.startswith(prefix):
                    return category
        return None

    def scan(self, index: ResourceIndex,
             progress_callback=None) -> ResourceIndex:
        """
        扫描所有VAR包

        参数:
            index: 目标索引
            progress_callback: fn(current, total, var_name) 进度回调
        """
        if not self.packages_dir.exists():
            return index

        var_files = list(self.packages_dir.rglob("*.var"))
        total = len(var_files)
        start = time.time()

        for i, var_path in enumerate(var_files):
            parts = var_path.name.split(".")
            if len(parts) < 4:
                continue

            var_name = ".".join(parts[:3])

            if progress_callback and i % 100 == 0:
                progress_callback(i, total, var_name)

            try:
                with zipfile.ZipFile(str(var_path), "r") as zf:
                    for name in zf.namelist():
                        category = self._classify(name)
                        if category:
                            entry = ResourceEntry(
                                var_name, str(var_path),
                                name, category,
                            )
                            index.add(entry)
            except (zipfile.BadZipFile, OSError):
                pass

        index.var_count = total
        index.scan_time = time.time() - start
        index._loaded = True
        return index


class AssetResolver:
    """
    资源路径解析器

    将VAR内部路径解析为VaM可用的引用格式
    """

    @staticmethod
    def var_ref(var_name: str, internal_path: str) -> str:
        """构建VaM VAR引用路径"""
        return f"{var_name}:/{internal_path}"

    @staticmethod
    def plugin_ref(var_name: str, cslist_path: str) -> str:
        """构建插件引用ID (用于storable id)"""
        return f"{var_name}:/{cslist_path}"

    @staticmethod
    def appearance_ref(var_name: str, vap_path: str) -> str:
        """构建外观预设引用"""
        return f"{var_name}:/{vap_path}"

    @staticmethod
    def parse_ref(ref: str) -> tuple:
        """解析VaM引用路径"""
        if ":/" in ref:
            var_name, path = ref.split(":/", 1)
            return var_name, path
        return "", ref


# ── 本地资源扫描 (非VAR, 直接在文件系统上) ──

class LocalAssetScanner:
    """扫描VaM安装目录中的非VAR资源 (直接文件)"""

    @staticmethod
    def scan_appearances() -> list[dict]:
        """扫描本地外观预设"""
        results = []
        base = VAM_CONFIG.APPEARANCES_DIR
        if base.exists():
            for f in base.rglob("*.vap"):
                results.append({
                    "name": f.stem,
                    "path": str(f.relative_to(VAM_CONFIG.VAM_INSTALL)),
                    "local_path": str(f),
                    "type": "local",
                })
        return results

    @staticmethod
    def scan_clothing() -> list[dict]:
        """扫描本地服装"""
        results = []
        base = VAM_CONFIG.CLOTHING_DIR
        if base.exists():
            for f in base.rglob("*.vam"):
                results.append({
                    "name": f.stem,
                    "path": str(f.relative_to(VAM_CONFIG.VAM_INSTALL)),
                    "local_path": str(f),
                    "creator": f.parent.name if f.parent != base else "",
                })
        return results

    @staticmethod
    def scan_hair() -> list[dict]:
        """扫描本地发型"""
        results = []
        base = VAM_CONFIG.HAIR_DIR
        if base.exists():
            for f in base.rglob("*.vam"):
                results.append({
                    "name": f.stem,
                    "path": str(f.relative_to(VAM_CONFIG.VAM_INSTALL)),
                    "local_path": str(f),
                    "gender": "Female" if "Female" in str(f) else "Male",
                })
        return results

    @staticmethod
    def scan_scripts() -> list[dict]:
        """扫描本地脚本"""
        results = []
        base = VAM_CONFIG.SCRIPTS_DIR
        if base.exists():
            for f in base.rglob("*.cs"):
                results.append({
                    "name": f.stem,
                    "path": str(f.relative_to(VAM_CONFIG.VAM_INSTALL)),
                    "local_path": str(f),
                    "size_kb": round(f.stat().st_size / 1024, 1),
                })
        return results

    @staticmethod
    def scan_scenes() -> list[dict]:
        """扫描本地场景"""
        results = []
        base = VAM_CONFIG.SCENES_DIR
        if base.exists():
            for f in base.rglob("*.json"):
                results.append({
                    "name": f.stem,
                    "path": str(f.relative_to(VAM_CONFIG.VAM_INSTALL)),
                    "local_path": str(f),
                    "size_kb": round(f.stat().st_size / 1024, 1),
                })
        return results

    @staticmethod
    def full_scan() -> dict:
        """完整本地资源扫描"""
        return {
            "appearances": LocalAssetScanner.scan_appearances(),
            "clothing": LocalAssetScanner.scan_clothing(),
            "hair": LocalAssetScanner.scan_hair(),
            "scripts": LocalAssetScanner.scan_scripts(),
            "scenes": LocalAssetScanner.scan_scenes(),
        }


# ── 便捷函数 ──

_global_index: Optional[ResourceIndex] = None


def get_index(force_rescan: bool = False) -> ResourceIndex:
    """
    获取全局资源索引 (单例, 自动缓存)

    首次调用自动扫描, 后续从缓存加载
    """
    global _global_index
    if _global_index and _global_index._loaded and not force_rescan:
        return _global_index

    index = ResourceIndex()
    if not force_rescan and index.load_cache():
        _global_index = index
        return index

    # 首次扫描
    scanner = VarScanner()
    scanner.scan(index)
    index.save_cache()
    _global_index = index
    return index


def quick_search(category: str = "", name: str = "",
                 creator: str = "", limit: int = 20) -> list[dict]:
    """快速搜索资源"""
    index = get_index()
    results = index.find(category, creator, name, limit)
    return [e.to_dict() for e in results]


# ── GitHub deps/ 扫描器 ──

class DepsScanner:
    """Scan the deps/ directory for cloned GitHub repositories.

    Indexes all third-party VaM projects that have been cloned into
    the agent's deps/ folder, extracting metadata like license,
    source language, and available assets.

    Usage:
        scanner = DepsScanner()
        projects = scanner.scan()
        # → [{"name": "Cue", "license": "CC0", "languages": ["C#"], ...}, ...]

        cs_projects = scanner.find_by_language("C#")
        scanner.summary()
    """

    LICENSE_FILES = ["LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING"]
    README_FILES = ["README.md", "README.txt", "README"]

    LANGUAGE_EXTENSIONS = {
        ".cs": "C#",
        ".py": "Python",
        ".js": "JavaScript",
        ".json": "JSON",
        ".cslist": "VaM Plugin List",
        ".scad": "OpenSCAD",
    }

    def __init__(self, deps_dir: Optional[Path] = None):
        if deps_dir is None:
            self.deps_dir = Path(__file__).resolve().parent.parent / "deps"
        else:
            self.deps_dir = Path(deps_dir)

    def scan(self) -> list[dict]:
        """Scan all subdirectories in deps/ and extract project metadata."""
        if not self.deps_dir.exists():
            return []

        projects = []
        for entry in sorted(self.deps_dir.iterdir()):
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            projects.append(self._scan_project(entry))
        return projects

    def _scan_project(self, project_dir: Path) -> dict:
        """Extract metadata from a single project directory."""
        info = {
            "name": project_dir.name,
            "path": str(project_dir),
            "license": self._detect_license(project_dir),
            "languages": [],
            "file_count": 0,
            "has_readme": False,
            "source_files": [],
        }

        lang_set = set()
        file_count = 0
        source_files = []

        for root, _dirs, files in os.walk(project_dir):
            # Skip hidden dirs and common non-source dirs
            rel = Path(root).relative_to(project_dir)
            parts = rel.parts
            if any(p.startswith(".") or p in ("bin", "obj", "node_modules")
                   for p in parts):
                continue

            for f in files:
                file_count += 1
                ext = Path(f).suffix.lower()
                if ext in self.LANGUAGE_EXTENSIONS:
                    lang_set.add(self.LANGUAGE_EXTENSIONS[ext])
                    if ext in (".cs", ".py", ".js"):
                        source_files.append(
                            str(Path(root, f).relative_to(project_dir))
                        )
                if f.upper() in [r.upper() for r in self.README_FILES]:
                    info["has_readme"] = True

        info["languages"] = sorted(lang_set)
        info["file_count"] = file_count
        info["source_files"] = source_files[:20]  # cap at 20
        return info

    def _detect_license(self, project_dir: Path) -> str:
        """Detect license type from LICENSE file content."""
        for lf in self.LICENSE_FILES:
            lpath = project_dir / lf
            if lpath.exists():
                try:
                    text = lpath.read_text(encoding="utf-8", errors="ignore")[:500].lower()
                    if "cc0" in text or "public domain" in text:
                        return "CC0"
                    if "creative commons" in text:
                        if "attribution" in text and "sharealike" in text:
                            return "CC BY-SA"
                        if "attribution" in text:
                            return "CC BY"
                        return "CC"
                    if "mit" in text:
                        return "MIT"
                    if "apache" in text:
                        return "Apache-2.0"
                    if "gpl" in text:
                        return "GPL"
                    if "bsd" in text:
                        return "BSD"
                    return "Other"
                except Exception:
                    return "Unknown"
        return "None"

    def find_by_language(self, language: str) -> list[dict]:
        """Find projects that use a specific language."""
        return [p for p in self.scan() if language in p["languages"]]

    def find_by_license(self, license_type: str) -> list[dict]:
        """Find projects with a specific license."""
        return [p for p in self.scan()
                if p["license"].lower() == license_type.lower()]

    def summary(self) -> dict:
        """Summary of all deps projects."""
        projects = self.scan()
        all_langs = set()
        license_counts: dict[str, int] = {}
        for p in projects:
            all_langs.update(p["languages"])
            lic = p["license"]
            license_counts[lic] = license_counts.get(lic, 0) + 1

        return {
            "total_projects": len(projects),
            "languages": sorted(all_langs),
            "licenses": license_counts,
            "total_files": sum(p["file_count"] for p in projects),
        }


# ── VAR包清理工具 (from vam-varbsorb, MIT) ──

class VarCleaner:
    """VAR package cleanup utility.

    Ported from acidbubbles/vam-varbsorb (MIT license).
    Detects redundant loose files that already exist inside VAR packages,
    allowing safe cleanup of duplicate assets.

    Usage:
        cleaner = VarCleaner()
        dupes = cleaner.find_duplicates()
        orphans = cleaner.find_orphan_morphs()
        report = cleaner.cleanup_report()
    """

    # File categories that can be absorbed into VARs
    ABSORBABLE_EXTENSIONS = {
        ".vap", ".vab", ".vam", ".vaj",  # appearance/clothing/hair
        ".json",                           # scenes/presets
        ".cs", ".cslist",                  # plugins
        ".vmi", ".vmb", ".dsf",            # morphs
        ".jpg", ".png", ".tif", ".tga",    # textures
        ".assetbundle",                     # unity assets
        ".wav", ".mp3", ".ogg",            # audio
    }

    # Directories to scan for loose files
    SCAN_DIRS = [
        "Custom/Atom/Person/Appearance",
        "Custom/Atom/Person/Clothing",
        "Custom/Atom/Person/Hair",
        "Custom/Atom/Person/Morphs",
        "Custom/Atom/Person/Pose",
        "Custom/Atom/Person/Textures",
        "Custom/Scripts",
        "Custom/Assets",
        "Custom/SubScene",
        "Saves/scene",
    ]

    def __init__(self, vam_root: Optional[str] = None):
        self.vam_root = Path(vam_root) if vam_root else VAM_CONFIG.VAM_ROOT

    def find_loose_files(self) -> list[dict]:
        """Find all loose (non-VAR) files in scannable directories."""
        results = []
        for scan_dir in self.SCAN_DIRS:
            full_path = self.vam_root / scan_dir
            if not full_path.exists():
                continue
            for root, _dirs, files in os.walk(full_path):
                for f in files:
                    ext = Path(f).suffix.lower()
                    if ext in self.ABSORBABLE_EXTENSIONS:
                        fpath = Path(root) / f
                        results.append({
                            "path": str(fpath.relative_to(self.vam_root)),
                            "extension": ext,
                            "size_bytes": fpath.stat().st_size
                                if fpath.exists() else 0,
                        })
        return results

    def find_orphan_morphs(self) -> list[dict]:
        """Find .vmb morph files without corresponding .vmi metadata."""
        morphs_dir = self.vam_root / "Custom/Atom/Person/Morphs"
        if not morphs_dir.exists():
            return []

        orphans = []
        for root, _dirs, files in os.walk(morphs_dir):
            vmb_files = {f for f in files if f.lower().endswith(".vmb")}
            vmi_files = {f[:-4] for f in files if f.lower().endswith(".vmi")}

            for vmb in vmb_files:
                stem = vmb[:-4]
                if stem not in vmi_files:
                    orphans.append({
                        "path": str((Path(root) / vmb).relative_to(
                            self.vam_root)),
                        "missing": f"{stem}.vmi",
                    })
        return orphans

    @staticmethod
    def parse_var_name(filename: str) -> Optional[dict]:
        """Parse a VAR filename into author/name/version components.

        Format: Author.PackageName.Version.var
        """
        if not filename.endswith(".var"):
            return None
        parts = filename[:-4].split(".")
        if len(parts) < 3:
            return None
        try:
            return {
                "author": parts[0],
                "name": ".".join(parts[1:-1]),
                "version": int(parts[-1]),
                "filename": filename,
            }
        except (ValueError, IndexError):
            return None

    def find_duplicate_vars(self) -> list[dict]:
        """Find VAR packages where multiple versions exist."""
        packages_dir = VAM_CONFIG.ADDON_PACKAGES
        if not packages_dir.exists():
            return []

        by_name: dict[str, list[dict]] = defaultdict(list)
        for f in packages_dir.glob("*.var"):
            parsed = self.parse_var_name(f.name)
            if parsed:
                key = f"{parsed['author']}.{parsed['name']}"
                parsed["size_bytes"] = f.stat().st_size
                by_name[key].append(parsed)

        duplicates = []
        for key, versions in by_name.items():
            if len(versions) > 1:
                versions.sort(key=lambda v: v["version"])
                duplicates.append({
                    "package": key,
                    "versions": [v["version"] for v in versions],
                    "latest": versions[-1]["version"],
                    "removable": [v["filename"] for v in versions[:-1]],
                    "space_bytes": sum(
                        v["size_bytes"] for v in versions[:-1]
                    ),
                })
        return duplicates

    def cleanup_report(self) -> dict:
        """Generate a comprehensive cleanup report."""
        loose = self.find_loose_files()
        orphans = self.find_orphan_morphs()
        dup_vars = self.find_duplicate_vars()

        return {
            "loose_files": len(loose),
            "loose_size_mb": round(
                sum(f["size_bytes"] for f in loose) / 1024 / 1024, 1
            ),
            "orphan_morphs": len(orphans),
            "duplicate_var_packages": len(dup_vars),
            "removable_var_space_mb": round(
                sum(d["space_bytes"] for d in dup_vars) / 1024 / 1024, 1
            ),
        }
