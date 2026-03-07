"""
VaM VAR包构建器 — 程序化创建/管理VAR包

从以下外部项目提取核心逻辑:
  - vamtb: VarFile类 (VAR创建/解压/元数据), file_utils (CRC32/varsplit)
  - vam-varbsorb: 场景引用扫描
  - vam-story-builder: 场景打包流程

架构:
  VarBuilder     — VAR包创建 (从文件→.var)
  VarInspector   — VAR包检查 (解压/元数据/依赖)
  VarNaming      — VAR命名规范工具
  DependencyResolver — 依赖解析
"""
import json
import os
import shutil
import tempfile
from binascii import crc32
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from zipfile import ZipFile

from .config import VAM_CONFIG
from .plugin_gen import MetaGenerator


# ── VAR 命名工具 ──

class VarNaming:
    """VAR包命名规范工具 (from vamtb file_utils)"""

    @staticmethod
    def split(var_filename: str) -> tuple:
        """
        拆分VAR文件名为组件

        返回: (full_name, creator, asset, version, extension)
        """
        basename = os.path.basename(var_filename)
        parts = basename.split(".", 3)
        if len(parts) != 4:
            raise ValueError(f"Invalid VAR filename: {var_filename}")
        creator, asset, version, ext = parts
        full_name = f"{creator}.{asset}.{version}"
        return full_name, creator, asset, version, ext

    @staticmethod
    def is_valid(filename: str) -> bool:
        """检查VAR文件名是否合规"""
        try:
            _, creator, asset, version, ext = VarNaming.split(filename)
            if not creator or not asset or not version or ext != "var":
                return False
            int(version)
            return True
        except (ValueError, IndexError):
            return False

    @staticmethod
    def make_name(creator: str, asset: str, version: int) -> str:
        """生成标准VAR文件名"""
        return f"{creator}.{asset}.{version}.var"

    @staticmethod
    def varname(filename: str) -> str:
        """提取不带扩展名的VAR名"""
        return VarNaming.split(filename)[0]


# ── 文件工具 ──

def file_crc32(filepath: str) -> str:
    """计算文件CRC32校验和 (from vamtb file_utils)"""
    with open(filepath, "rb") as f:
        buf = f.read()
    return "%08X" % (crc32(buf) & 0xFFFFFFFF)


def file_size_human(filepath: str) -> str:
    """人类可读的文件大小"""
    size = os.path.getsize(filepath)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


# ── VAR包检查器 ──

class VarInspector:
    """
    VAR包检查器 — 读取/解析现有VAR包

    基于vamtb VarFile类的核心逻辑
    """

    def __init__(self, var_path: str):
        self.var_path = Path(var_path)
        if not self.var_path.exists():
            raise FileNotFoundError(f"VAR not found: {var_path}")
        self._tmp_dir: Optional[Path] = None
        self._meta: Optional[dict] = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

    @property
    def filename(self) -> str:
        return self.var_path.name

    @property
    def varname(self) -> str:
        return VarNaming.varname(self.filename)

    def extract(self, target_dir: Optional[str] = None) -> Path:
        """解压VAR到临时目录"""
        if target_dir:
            extract_path = Path(target_dir)
        else:
            extract_path = Path(tempfile.mkdtemp(prefix="vam_var_"))
        self._tmp_dir = extract_path

        with ZipFile(str(self.var_path)) as z:
            z.extractall(extract_path)

        return extract_path

    def meta(self) -> dict:
        """读取meta.json"""
        if self._meta:
            return self._meta

        with ZipFile(str(self.var_path)) as z:
            if "meta.json" not in z.namelist():
                raise ValueError(f"No meta.json in {self.filename}")
            with z.open("meta.json") as f:
                self._meta = json.loads(f.read())

        return self._meta

    def list_contents(self) -> list[str]:
        """列出VAR包内所有文件"""
        with ZipFile(str(self.var_path)) as z:
            return [
                name for name in z.namelist()
                if name != "meta.json"
            ]

    def dependencies(self) -> list[str]:
        """获取依赖列表"""
        meta = self.meta()
        deps = meta.get("dependencies", {})
        return list(deps.keys())

    def info(self) -> dict:
        """获取VAR包完整信息"""
        meta = self.meta()
        return {
            "filename": self.filename,
            "varname": self.varname,
            "size": file_size_human(str(self.var_path)),
            "crc32": file_crc32(str(self.var_path)),
            "creator": meta.get("creatorName", ""),
            "package": meta.get("packageName", ""),
            "description": meta.get("description", ""),
            "license": meta.get("licenseType", ""),
            "content_count": len(meta.get("contentList", [])),
            "dependency_count": len(meta.get("dependencies", {})),
            "dependencies": self.dependencies(),
        }

    def cleanup(self):
        """清理临时目录"""
        if self._tmp_dir and self._tmp_dir.exists():
            shutil.rmtree(self._tmp_dir, ignore_errors=True)
            self._tmp_dir = None


# ── VAR包构建器 ──

class VarBuilder:
    """
    VAR包构建器 — 从文件/场景创建VAR包

    基于vamtb的VarFile创建逻辑

    用法:
        builder = VarBuilder("MyCreator", "MyPackage", version=1)
        builder.add_file("Custom/Scenes/scene.json", scene_content)
        builder.add_directory("Custom/Scripts/MyPlugin/", local_dir)
        builder.set_description("An awesome VaM package")
        builder.add_dependency("AcidBubbles.Timeline.latest")
        var_path = builder.build()
    """

    def __init__(self, creator: str, package_name: str,
                 version: int = 1):
        self.creator = creator
        self.package_name = package_name
        self.version = version
        self.files: dict[str, bytes] = {}  # archive_path → content
        self.local_files: dict[str, str] = {}  # archive_path → local_path
        self.meta_gen = MetaGenerator(creator, package_name)

    @property
    def varname(self) -> str:
        return f"{self.creator}.{self.package_name}.{self.version}"

    @property
    def filename(self) -> str:
        return f"{self.varname}.var"

    def add_file(self, archive_path: str, content: str | bytes) -> "VarBuilder":
        """添加文件内容到VAR包"""
        if isinstance(content, str):
            content = content.encode("utf-8")
        self.files[archive_path] = content
        self.meta_gen.add_content(archive_path)
        return self

    def add_file_from_disk(self, archive_path: str,
                           local_path: str) -> "VarBuilder":
        """从本地文件添加到VAR包"""
        self.local_files[archive_path] = local_path
        self.meta_gen.add_content(archive_path)
        return self

    def add_directory(self, archive_prefix: str,
                      local_dir: str) -> "VarBuilder":
        """添加整个目录到VAR包"""
        local_path = Path(local_dir)
        if not local_path.exists():
            raise FileNotFoundError(f"Directory not found: {local_dir}")
        for f in local_path.rglob("*"):
            if f.is_file():
                rel = f.relative_to(local_path)
                arc_path = f"{archive_prefix}/{rel.as_posix()}"
                self.local_files[arc_path] = str(f)
                self.meta_gen.add_content(arc_path)
        return self

    def add_scene(self, scene_data: dict,
                  scene_name: str = "scene") -> "VarBuilder":
        """添加场景JSON"""
        content = json.dumps(scene_data, indent=3).encode("utf-8")
        path = f"Saves/scene/{scene_name}.json"
        self.files[path] = content
        self.meta_gen.add_content(path)
        return self

    def add_plugin(self, plugin_code: str,
                   plugin_name: str = "MyPlugin") -> "VarBuilder":
        """添加C#插件"""
        path = f"Custom/Scripts/{plugin_name}.cs"
        self.files[path] = plugin_code.encode("utf-8")
        self.meta_gen.add_content(path)
        return self

    def set_description(self, desc: str) -> "VarBuilder":
        self.meta_gen.set_description(desc)
        return self

    def set_license(self, license_type: str) -> "VarBuilder":
        self.meta_gen.set_license(license_type)
        return self

    def add_dependency(self, var_name: str) -> "VarBuilder":
        """添加VAR依赖"""
        self.meta_gen.add_dependency(var_name)
        return self

    def build(self, output_dir: Optional[str] = None) -> str:
        """
        构建VAR包

        返回: VAR文件路径
        """
        output_dir = output_dir or str(VAM_CONFIG.ADDON_PACKAGES)
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        var_filepath = output_path / self.filename

        # 生成meta.json
        meta_content = json.dumps(
            self.meta_gen.build(), indent=3
        ).encode("utf-8")

        # 打包
        with ZipFile(str(var_filepath), "w") as zf:
            # meta.json 先写
            zf.writestr("meta.json", meta_content)

            # 内存中的文件
            for arc_path, content in self.files.items():
                zf.writestr(arc_path, content)

            # 磁盘上的文件
            for arc_path, local_path in self.local_files.items():
                zf.write(local_path, arc_path)

        return str(var_filepath)

    def preview(self) -> dict:
        """预览将要创建的VAR包"""
        all_files = list(self.files.keys()) + list(self.local_files.keys())
        return {
            "varname": self.varname,
            "filename": self.filename,
            "file_count": len(all_files),
            "files": all_files,
            "dependencies": list(self.meta_gen.dependencies.keys()),
            "description": self.meta_gen.description,
            "license": self.meta_gen.license_type,
        }


# ── 依赖解析器 ──

class DependencyResolver:
    """
    VAR依赖解析器

    扫描AddonPackages目录, 解析依赖树
    """

    def __init__(self):
        self.packages_dir = VAM_CONFIG.ADDON_PACKAGES
        self._var_cache: dict[str, dict] = {}

    def scan_packages(self) -> list[dict]:
        """扫描所有已安装的VAR包"""
        if not self.packages_dir.exists():
            return []

        packages = []
        for f in self.packages_dir.rglob("*.var"):
            if VarNaming.is_valid(f.name):
                try:
                    info = {"filename": f.name, "path": str(f),
                            "size": file_size_human(str(f))}
                    name, creator, asset, version, _ = VarNaming.split(f.name)
                    info["varname"] = name
                    info["creator"] = creator
                    info["asset"] = asset
                    info["version"] = version
                    packages.append(info)
                except Exception:
                    pass
        return packages

    def find_package(self, var_name: str) -> Optional[str]:
        """查找VAR包路径 (支持 .latest 版本)"""
        if not self.packages_dir.exists():
            return None

        parts = var_name.split(".")
        if len(parts) < 3:
            return None

        creator, asset = parts[0], parts[1]
        version_spec = parts[2]

        candidates = []
        pattern = f"{creator}.{asset}.*.var"
        for f in self.packages_dir.rglob(pattern):
            try:
                _, _, _, ver, _ = VarNaming.split(f.name)
                candidates.append((int(ver), str(f)))
            except (ValueError, IndexError):
                pass

        if not candidates:
            return None

        if version_spec == "latest":
            candidates.sort(key=lambda x: x[0], reverse=True)
            return candidates[0][1]
        elif version_spec.startswith("min"):
            min_ver = int(version_spec[3:])
            valid = [(v, p) for v, p in candidates if v >= min_ver]
            if valid:
                valid.sort(key=lambda x: x[0])
                return valid[0][1]
        else:
            exact = int(version_spec)
            for v, p in candidates:
                if v == exact:
                    return p

        return None

    def resolve_dependencies(self, var_path: str,
                             max_depth: int = 10) -> dict:
        """
        递归解析VAR依赖树

        返回: {varname: {status, path, deps: [...]}}
        """
        resolved = {}
        self._resolve_recursive(var_path, resolved, depth=0,
                                max_depth=max_depth)
        return resolved

    def _resolve_recursive(self, var_path: str, resolved: dict,
                           depth: int, max_depth: int):
        if depth > max_depth:
            return

        try:
            inspector = VarInspector(var_path)
            varname = inspector.varname
            if varname in resolved:
                return

            deps = inspector.dependencies()
            dep_results = []
            for dep_name in deps:
                dep_path = self.find_package(dep_name)
                dep_status = "found" if dep_path else "missing"
                dep_results.append({
                    "name": dep_name,
                    "status": dep_status,
                    "path": dep_path,
                })
                if dep_path:
                    self._resolve_recursive(
                        dep_path, resolved, depth + 1, max_depth
                    )

            resolved[varname] = {
                "status": "found",
                "path": var_path,
                "dependencies": dep_results,
            }
        except Exception as e:
            resolved[os.path.basename(var_path)] = {
                "status": "error",
                "error": str(e),
            }

    def check_missing(self) -> list[dict]:
        """检查所有VAR包中的缺失依赖"""
        missing = []
        packages = self.scan_packages()
        for pkg in packages:
            try:
                inspector = VarInspector(pkg["path"])
                deps = inspector.dependencies()
                for dep in deps:
                    if not self.find_package(dep):
                        missing.append({
                            "required_by": pkg["varname"],
                            "missing": dep,
                        })
            except Exception:
                pass
        return missing


# ── 便捷函数 ──

def quick_var(creator: str, package_name: str,
              scene_data: dict, version: int = 1,
              description: str = "") -> str:
    """快速创建包含场景的VAR包"""
    builder = VarBuilder(creator, package_name, version)
    builder.add_scene(scene_data, package_name)
    if description:
        builder.set_description(description)
    return builder.build()


def inspect_var(var_path: str) -> dict:
    """快速检查VAR包信息"""
    with VarInspector(var_path) as inspector:
        return inspector.info()
