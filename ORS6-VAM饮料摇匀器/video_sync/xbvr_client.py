"""
XBVR REST API 客户端

XBVR (xbapps/xbvr, 450⭐) 是VR视频管理器，提供:
- 场景管理 (元数据/标签/演员/工作室)
- 脚本匹配 (自动关联funscript)
- DLNA流媒体
- 支持DeoVR/HereSphere/SLR等播放器

API文档: https://github.com/xbapps/xbvr
默认端口: 9999 (Web UI + REST API)

用法:
    client = XBVRClient(port=9999)
    
    # 查找有脚本的VR场景
    scenes = client.find_scripted_scenes()
    for s in scenes:
        print(f"{s.title} — {s.duration}s — {len(s.cast)}演员")
    
    # 搜索场景
    results = client.search("keyword")
    
    # 获取场景详情
    scene = client.get_scene(scene_id=123)
"""

import json
import logging
import urllib.request
import urllib.parse
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class XBVRFile:
    """XBVR文件信息"""
    id: int = 0
    path: str = ""
    filename: str = ""
    size: int = 0
    video_width: int = 0
    video_height: int = 0
    video_bitrate: int = 0
    video_projection: str = ""  # "180_sbs", "360_tb", "flat", etc.
    has_heatmap: bool = False


@dataclass
class XBVRScene:
    """XBVR场景信息"""
    id: int = 0
    scene_id: str = ""
    title: str = ""
    synopsis: str = ""
    duration: int = 0  # 秒
    site: str = ""
    studio: str = ""
    release_date: str = ""
    cast: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    files: list[XBVRFile] = field(default_factory=list)
    is_scripted: bool = False
    has_preview: bool = False
    star_rating: float = 0.0
    favorite: bool = False
    cover_url: str = ""
    scene_url: str = ""
    
    @property
    def primary_file(self) -> Optional[XBVRFile]:
        return self.files[0] if self.files else None
    
    @property
    def file_path(self) -> str:
        f = self.primary_file
        return f.path if f else ""
    
    @property
    def is_vr(self) -> bool:
        f = self.primary_file
        if f and f.video_projection:
            return f.video_projection in ("180_sbs", "180_tb", "360_tb", "360_sbs",
                                           "mkx200", "mkx220", "vrca220", "rf52")
        return False
    
    @property
    def resolution_label(self) -> str:
        f = self.primary_file
        if not f:
            return ""
        h = f.video_height
        if h >= 3840:
            return "8K"
        elif h >= 2880:
            return "6K"
        elif h >= 2160:
            return "5K"
        elif h >= 1440:
            return "4K"
        elif h >= 1080:
            return "1080p"
        return f"{h}p"
    
    def summary(self) -> str:
        cast_str = ", ".join(self.cast[:3]) if self.cast else "未知"
        tags_str = ", ".join(self.tags[:5]) if self.tags else ""
        scripted = "✓脚本" if self.is_scripted else ""
        vr = "VR" if self.is_vr else "2D"
        return (f"[{self.id}] {self.title} ({self.duration//60}min) "
                f"— {cast_str} [{vr} {self.resolution_label}] {scripted}")


class XBVRClient:
    """XBVR REST API客户端
    
    连接到XBVR实例，查询和管理VR视频场景。
    支持场景搜索、脚本匹配状态查询、演员/标签过滤。
    """
    
    def __init__(self, host: str = "127.0.0.1", port: int = 9999,
                 timeout: float = 10.0):
        self.host = host
        self.port = port
        self.timeout = timeout
    
    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}/api"
    
    def health_check(self) -> bool:
        """检查XBVR是否可达"""
        try:
            self._get("/options/state")
            return True
        except Exception:
            return False
    
    # ── 场景查询 ──
    
    def get_scene(self, scene_id: int) -> Optional[XBVRScene]:
        """获取场景详情"""
        try:
            data = self._get(f"/scene/{scene_id}")
            return self._parse_scene(data)
        except Exception as e:
            logger.error(f"获取场景失败 {scene_id}: {e}")
            return None
    
    def find_scenes(self, limit: int = 100, offset: int = 0,
                    sort: str = "release_date_desc",
                    cast: str = "",
                    tag: str = "",
                    site: str = "") -> list[XBVRScene]:
        """查询场景列表
        
        Args:
            limit: 每页数量
            offset: 偏移量
            sort: 排序方式 (release_date_desc/added_date_desc/rating_desc等)
            cast: 演员名筛选
            tag: 标签筛选
            site: 站点筛选
        """
        params = {
            "limit": limit,
            "offset": offset,
            "sort": sort,
        }
        if cast:
            params["cast"] = cast
        if tag:
            params["tag"] = tag
        if site:
            params["site"] = site
        
        try:
            data = self._get("/scene/list", params)
            scenes_data = data.get("scenes", []) if isinstance(data, dict) else data
            if isinstance(scenes_data, list):
                return [self._parse_scene(s) for s in scenes_data]
            return []
        except Exception as e:
            logger.error(f"查询场景失败: {e}")
            return []
    
    def search(self, query: str, limit: int = 50) -> list[XBVRScene]:
        """搜索场景
        
        Args:
            query: 搜索关键词 (标题/演员/标签)
            limit: 最大返回数量
        """
        try:
            body = json.dumps({"q": query}).encode("utf-8")
            data = self._post("/scene/search", body)
            scenes_data = data.get("scenes", []) if isinstance(data, dict) else data
            if isinstance(scenes_data, list):
                return [self._parse_scene(s) for s in scenes_data[:limit]]
            return []
        except Exception as e:
            logger.error(f"搜索失败 '{query}': {e}")
            return []
    
    def find_scripted_scenes(self, limit: int = 200) -> list[XBVRScene]:
        """查找所有有Funscript脚本的场景
        
        Returns:
            is_scripted=True的场景列表
        """
        all_scenes = self.find_scenes(limit=limit, sort="rating_desc")
        scripted = [s for s in all_scenes if s.is_scripted]
        logger.info(f"XBVR: {len(scripted)}/{len(all_scenes)} 场景有脚本")
        return scripted
    
    def find_scenes_by_cast(self, performer: str,
                             scripted_only: bool = False) -> list[XBVRScene]:
        """按演员查找场景"""
        scenes = self.find_scenes(cast=performer, limit=200)
        if scripted_only:
            scenes = [s for s in scenes if s.is_scripted]
        return scenes
    
    def find_scenes_by_tag(self, tag: str,
                            scripted_only: bool = False) -> list[XBVRScene]:
        """按标签查找场景"""
        scenes = self.find_scenes(tag=tag, limit=200)
        if scripted_only:
            scenes = [s for s in scenes if s.is_scripted]
        return scenes
    
    # ── 统计 ──
    
    def get_stats(self) -> dict:
        """获取XBVR库统计
        
        Returns:
            包含场景总数、有脚本数、VR数等统计信息
        """
        scenes = self.find_scenes(limit=500)
        
        total = len(scenes)
        scripted = sum(1 for s in scenes if s.is_scripted)
        vr = sum(1 for s in scenes if s.is_vr)
        
        # 演员统计
        cast_count = {}
        for s in scenes:
            for c in s.cast:
                cast_count[c] = cast_count.get(c, 0) + 1
        
        # 站点统计
        site_count = {}
        for s in scenes:
            if s.site:
                site_count[s.site] = site_count.get(s.site, 0) + 1
        
        return {
            "total_scenes": total,
            "scripted_scenes": scripted,
            "vr_scenes": vr,
            "script_coverage": f"{scripted/total*100:.1f}%" if total else "0%",
            "top_cast": dict(sorted(cast_count.items(),
                                     key=lambda x: x[1], reverse=True)[:10]),
            "sites": dict(sorted(site_count.items(),
                                  key=lambda x: x[1], reverse=True)[:10]),
        }
    
    def get_available_sites(self) -> list[dict]:
        """获取可用的刮削站点"""
        try:
            data = self._get("/options/sites")
            return data if isinstance(data, list) else []
        except Exception as e:
            logger.error(f"获取站点列表失败: {e}")
            return []
    
    # ── 内部HTTP ──
    
    def _get(self, path: str, params: dict = None) -> dict | list:
        """GET请求"""
        url = self.base_url + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        
        req = urllib.request.Request(url)
        req.add_header("Accept", "application/json")
        
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    
    def _post(self, path: str, body: bytes = None) -> dict | list:
        """POST请求"""
        url = self.base_url + path
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")
        
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    
    def _parse_scene(self, data: dict) -> XBVRScene:
        """解析场景JSON"""
        files = []
        for f in data.get("files", []) or []:
            files.append(XBVRFile(
                id=f.get("id", 0),
                path=f.get("path", ""),
                filename=f.get("filename", ""),
                size=f.get("size", 0),
                video_width=f.get("video_width", 0),
                video_height=f.get("video_height", 0),
                video_bitrate=f.get("video_bitrate", 0),
                video_projection=f.get("video_projection", ""),
                has_heatmap=f.get("has_heatmap", False),
            ))
        
        cast_list = []
        for c in data.get("cast", []) or []:
            if isinstance(c, dict):
                cast_list.append(c.get("name", ""))
            elif isinstance(c, str):
                cast_list.append(c)
        
        tags_list = []
        for t in data.get("tags", []) or []:
            if isinstance(t, dict):
                tags_list.append(t.get("name", ""))
            elif isinstance(t, str):
                tags_list.append(t)
        
        return XBVRScene(
            id=data.get("id", 0),
            scene_id=data.get("scene_id", ""),
            title=data.get("title", ""),
            synopsis=data.get("synopsis", ""),
            duration=data.get("duration", 0),
            site=data.get("site", ""),
            studio=data.get("studio", {}).get("name", "") if isinstance(data.get("studio"), dict) else str(data.get("studio", "")),
            release_date=data.get("release_date", ""),
            cast=cast_list,
            tags=tags_list,
            files=files,
            is_scripted=data.get("is_scripted", False),
            has_preview=data.get("has_preview", False),
            star_rating=data.get("star_rating", 0.0),
            favorite=data.get("favourite", False),
            cover_url=data.get("cover_url", ""),
            scene_url=data.get("scene_url", ""),
        )
    
    def __repr__(self):
        return f"XBVRClient(http://{self.host}:{self.port})"
