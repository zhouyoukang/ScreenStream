"""
Stash GraphQL API 客户端

Stash (11933⭐) 是通用媒体管理器，提供:
- 视频元数据管理 (标签/演员/工作室)
- GraphQL API (端口9999)
- 场景搜索和过滤
- 与MultiFunPlayer/FunGen集成用于脚本匹配

本客户端实现场景查询和funscript文件关联。
"""

import json
import logging
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class StashScene:
    """Stash场景信息"""
    id: str = ""
    title: str = ""
    path: str = ""
    duration: float = 0.0
    tags: list[str] = field(default_factory=list)
    performers: list[str] = field(default_factory=list)
    studio: str = ""
    rating: int = 0
    organized: bool = False
    
    @property
    def filename(self) -> str:
        return Path(self.path).name if self.path else ""
    
    @property
    def stem(self) -> str:
        return Path(self.path).stem if self.path else ""


class StashClient:
    """Stash GraphQL API客户端
    
    用法:
        client = StashClient(host="127.0.0.1", port=9999)
        
        # 查询场景
        scenes = client.find_scenes(query="keyword", per_page=10)
        for scene in scenes:
            print(f"{scene.title} - {scene.duration}s")
        
        # 获取单个场景
        scene = client.get_scene("123")
        
        # 查找有funscript的场景
        scenes = client.find_interactive_scenes()
    """
    
    def __init__(self, host: str = "127.0.0.1", port: int = 9999,
                 api_key: str = ""):
        self.host = host
        self.port = port
        self.api_key = api_key
    
    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/graphql"
    
    def _request(self, query: str, variables: dict = None) -> dict:
        """执行GraphQL请求"""
        payload = json.dumps({
            "query": query,
            "variables": variables or {},
        }).encode("utf-8")
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["ApiKey"] = self.api_key
        
        req = urllib.request.Request(self.url, data=payload, headers=headers)
        
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.URLError as e:
            logger.error(f"Stash API请求失败: {e}")
            return {}
        except Exception as e:
            logger.error(f"Stash API错误: {e}")
            return {}
    
    def _parse_scene(self, data: dict) -> StashScene:
        """解析场景数据"""
        files = data.get("files", [])
        path = files[0].get("path", "") if files else ""
        
        return StashScene(
            id=str(data.get("id", "")),
            title=data.get("title", "") or "",
            path=path,
            duration=data.get("files", [{}])[0].get("duration", 0)
                     if files else 0,
            tags=[t.get("name", "") for t in data.get("tags", [])],
            performers=[p.get("name", "")
                        for p in data.get("performers", [])],
            studio=data.get("studio", {}).get("name", "")
                   if data.get("studio") else "",
            rating=data.get("rating100", 0) or 0,
            organized=data.get("organized", False),
        )
    
    def health_check(self) -> bool:
        """检查Stash是否在运行"""
        try:
            req = urllib.request.Request(
                f"http://{self.host}:{self.port}",
                method="HEAD",
            )
            with urllib.request.urlopen(req, timeout=5):
                return True
        except Exception:
            return False
    
    def find_scenes(self, query: str = "", per_page: int = 25,
                    page: int = 1, sort: str = "updated_at",
                    direction: str = "DESC",
                    tag_ids: list[int] = None) -> list[StashScene]:
        """查询场景列表
        
        Args:
            query: 搜索关键词
            per_page: 每页数量
            page: 页码 (从1开始)
            sort: 排序字段
            direction: 排序方向 (ASC/DESC)
            tag_ids: 过滤标签ID列表
        """
        scene_filter = {}
        if tag_ids:
            scene_filter["tags"] = {
                "value": tag_ids,
                "modifier": "INCLUDES",
            }
        
        gql = """
        query FindScenes($filter: FindFilterType, $scene_filter: SceneFilterType) {
          findScenes(filter: $filter, scene_filter: $scene_filter) {
            count
            scenes {
              id
              title
              rating100
              organized
              files { path duration }
              tags { name }
              performers { name }
              studio { name }
            }
          }
        }
        """
        
        variables = {
            "filter": {
                "q": query,
                "per_page": per_page,
                "page": page,
                "sort": sort,
                "direction": direction,
            },
        }
        if scene_filter:
            variables["scene_filter"] = scene_filter
        
        result = self._request(gql, variables)
        scenes_data = (result.get("data", {})
                       .get("findScenes", {})
                       .get("scenes", []))
        
        return [self._parse_scene(s) for s in scenes_data]
    
    def get_scene(self, scene_id: str) -> Optional[StashScene]:
        """获取单个场景详情"""
        gql = """
        query FindScene($id: ID!) {
          findScene(id: $id) {
            id
            title
            rating100
            organized
            files { path duration }
            tags { name }
            performers { name }
            studio { name }
          }
        }
        """
        
        result = self._request(gql, {"id": scene_id})
        scene_data = result.get("data", {}).get("findScene")
        
        if scene_data:
            return self._parse_scene(scene_data)
        return None
    
    def find_interactive_scenes(self, per_page: int = 100
                                ) -> list[StashScene]:
        """查找标记为interactive的场景 (通常有funscript)"""
        gql = """
        query FindInteractive($filter: FindFilterType, $scene_filter: SceneFilterType) {
          findScenes(filter: $filter, scene_filter: $scene_filter) {
            count
            scenes {
              id
              title
              rating100
              organized
              files { path duration }
              tags { name }
              performers { name }
              studio { name }
            }
          }
        }
        """
        
        variables = {
            "filter": {
                "per_page": per_page,
                "sort": "updated_at",
                "direction": "DESC",
            },
            "scene_filter": {
                "interactive": True,
            },
        }
        
        result = self._request(gql, variables)
        scenes_data = (result.get("data", {})
                       .get("findScenes", {})
                       .get("scenes", []))
        
        return [self._parse_scene(s) for s in scenes_data]
    
    def get_scene_count(self) -> int:
        """获取场景总数"""
        gql = """
        query {
          findScenes(filter: { per_page: 0 }) {
            count
          }
        }
        """
        result = self._request(gql)
        return (result.get("data", {})
                .get("findScenes", {})
                .get("count", 0))
    
    def get_tags(self) -> list[dict]:
        """获取所有标签"""
        gql = """
        query {
          allTags {
            id
            name
            scene_count
          }
        }
        """
        result = self._request(gql)
        return result.get("data", {}).get("allTags", [])
