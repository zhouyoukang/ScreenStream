"""
VaM 场景管理 — 创建/列表/修改/加载/删除场景
"""
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Optional

from .config import VAM_CONFIG

try:
    from voxta.config import VOXTA_CONFIG
    _VOXTA_CHARACTERS = VOXTA_CONFIG.CHARACTERS
    _VOXTA_PLUGIN_ID = VOXTA_CONFIG.VOXTA_PLUGIN_ID
except ImportError:
    _VOXTA_CHARACTERS = {}
    _VOXTA_PLUGIN_ID = "plugin#0_AcidBubbles.Voxta.83:/Custom/Scripts/Voxta/VoxtaClient.cslist"


def _vec3(x=0, y=0, z=0):
    return {"x": str(x), "y": str(y), "z": str(z)}


def _color(r=1.0, g=1.0, b=1.0):
    return {"r": str(r), "g": str(g), "b": str(b)}


class SceneBuilder:
    """参数化VaM场景构建器"""

    def __init__(self, version="1.22.0.3"):
        self.data = {"version": version, "atoms": []}
        self._counter = {}

    # ── 工厂 ──

    @classmethod
    def load(cls, path: str) -> "SceneBuilder":
        """从现有场景JSON加载"""
        scene = cls()
        with open(path, "r", encoding="utf-8") as f:
            scene.data = json.load(f)
        for atom in scene.data.get("atoms", []):
            atype = atom.get("type", "")
            aid = atom.get("id", "")
            if "#" in aid:
                try:
                    num = int(aid.split("#")[-1])
                    scene._counter[atype] = max(scene._counter.get(atype, 0), num)
                except ValueError:
                    pass
        return scene

    @classmethod
    def quick_voxta(cls, char_name: str = "香草", with_lighting: bool = True) -> "SceneBuilder":
        """快速创建含Voxta角色的场景"""
        scene = cls()
        char_id = _VOXTA_CHARACTERS.get(char_name, char_name)
        scene.add_person(voxta_char_id=char_id, enable_lip_sync=True, enable_actions=True)
        scene.add_camera(position=(0, 1.5, 2.0), fov=60)
        if with_lighting:
            scene.add_three_point_lighting()
        return scene

    # ── 保存 ──

    def save(self, path: str = None, name: str = None) -> str:
        """保存场景JSON"""
        if path is None:
            if name is None:
                name = f"Agent_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            path = str(VAM_CONFIG.SCENES_GENERATED / f"{name}.json")
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
        return str(p)

    # ── Atom管理 ──

    def _next_id(self, atom_type: str) -> str:
        self._counter[atom_type] = self._counter.get(atom_type, 0) + 1
        return f"{atom_type}#{self._counter[atom_type]}"

    def _make_atom(self, atom_id, atom_type, position=(0, 0, 0),
                   rotation=(0, 0, 0), on=True, storables=None):
        if isinstance(position, (list, tuple)):
            position = _vec3(*position)
        if isinstance(rotation, (list, tuple)):
            rotation = _vec3(*rotation)
        atom = {
            "id": atom_id, "type": atom_type,
            "on": "true" if on else "false",
            "position": position, "rotation": rotation,
            "storables": storables or [],
        }
        self.data["atoms"].append(atom)
        return atom

    def get_atom(self, atom_id: str):
        for a in self.data["atoms"]:
            if a["id"] == atom_id:
                return a
        return None

    def remove_atom(self, atom_id: str):
        self.data["atoms"] = [a for a in self.data["atoms"] if a["id"] != atom_id]

    # ── Person ──

    def add_person(self, atom_id=None, position=(0, 0, 0), rotation=(0, 0, 0),
                   gender="Female", scale=1.0, voxta_char_id=None,
                   voxta_host="127.0.0.1:5384", enable_lip_sync=True,
                   enable_actions=True, enable_speech_recognition=False,
                   appearance_preset=None, plugins=None):
        if atom_id is None:
            atom_id = self._next_id("Person")
        storables = [
            {"id": "geometry", "character": gender, "clothing": [], "hair": []},
            {"id": "rescaleObject", "scale": str(scale)},
        ]
        if appearance_preset:
            storables.append({"id": "preset", "presetPath": appearance_preset})
        if voxta_char_id:
            storables.append({
                "id": _VOXTA_PLUGIN_ID,
                "enabled": "true", "pluginLabel": "Voxta Client",
                "host": voxta_host, "apiKey": "", "autoConnect": "true",
                "characterId": voxta_char_id,
                "enableLipSync": "true" if enable_lip_sync else "false",
                "enableSpeechRecognition": "true" if enable_speech_recognition else "false",
                "enableActions": "true" if enable_actions else "false",
            })
        if plugins:
            storables.extend(plugins)
        return self._make_atom(atom_id, "Person", position, rotation, storables=storables)

    # ── Camera ──

    def add_camera(self, atom_id=None, position=(0, 1.5, 2.0),
                   rotation=(0, 180, 0), fov=60, depth_of_field=True,
                   focus_distance=2.0):
        if atom_id is None:
            atom_id = self._next_id("WindowCamera")
        storables = [{"id": "CameraControl", "FOV": str(fov),
                       "depthOfField": "true" if depth_of_field else "false",
                       "focusDistance": str(focus_distance)}]
        return self._make_atom(atom_id, "WindowCamera", position, rotation, storables=storables)

    # ── Light ──

    def add_light(self, atom_id=None, position=(0, 2, 0), light_type="Directional",
                  intensity=1.0, color=(1.0, 1.0, 1.0), shadow_type="Soft", range_val=None):
        if atom_id is None:
            atom_id = self._next_id("InvisibleLight")
        st = {"id": "Light", "type": light_type, "intensity": str(intensity),
              "color": _color(*color), "shadowType": shadow_type}
        if range_val is not None:
            st["range"] = str(range_val)
        return self._make_atom(atom_id, "InvisibleLight", position, storables=[st])

    def add_three_point_lighting(self):
        self.add_light(position=(1.5, 2.0, 1.0), light_type="Directional",
                       intensity=1.2, color=(1.0, 0.95, 0.9))
        self.add_light(position=(-1.5, 1.5, 1.0), light_type="Point",
                       intensity=0.6, color=(0.9, 0.95, 1.0))
        self.add_light(position=(0, 0.5, -1.5), light_type="Point",
                       intensity=0.4, color=(1.0, 1.0, 1.0))

    # ── 其他Atom ──

    def add_empty(self, atom_id=None, position=(0, 0, 0)):
        if atom_id is None:
            atom_id = self._next_id("Empty")
        return self._make_atom(atom_id, "Empty", position)

    def add_audio(self, atom_id=None, position=(0, 1, 0), clip=None, volume=1.0):
        if atom_id is None:
            atom_id = self._next_id("AudioSource")
        storables = [{"id": "AudioSource", "volume": str(volume)}]
        if clip:
            storables[0]["clip"] = clip
        return self._make_atom(atom_id, "AudioSource", position, storables=storables)

    def add_text(self, atom_id=None, position=(0, 1.5, 1), text="", font_size=36):
        if atom_id is None:
            atom_id = self._next_id("UIText")
        storables = [{"id": "Text", "text": text, "fontSize": str(font_size)}]
        return self._make_atom(atom_id, "UIText", position, storables=storables)

    # ── 插件操作 ──

    def add_plugin_to_atom(self, atom_id: str, plugin_storable: dict):
        atom = self.get_atom(atom_id)
        if atom is None:
            raise ValueError(f"Atom {atom_id} not found")
        atom["storables"].append(plugin_storable)

    def add_scripter(self, atom_id: str, script_path: str, plugin_index: int = 1):
        rel = script_path
        if os.path.isabs(script_path):
            try:
                rel = os.path.relpath(script_path, VAM_CONFIG.VAM_INSTALL)
            except ValueError:
                pass
        self.add_plugin_to_atom(atom_id, {
            "id": f"plugin#{plugin_index}_Scripter", "enabled": "true",
            "pluginLabel": "Scripter", "scriptPath": rel,
        })

    def add_timeline(self, atom_id: str, plugin_index: int = 1):
        self.add_plugin_to_atom(atom_id, {
            "id": f"plugin#{plugin_index}_VamTimeline.AtomPlugin",
            "enabled": "true", "pluginLabel": "Timeline",
        })

    # ── 批量 ──

    def add_multi_person(self, characters: list, spacing: float = 1.2):
        n = len(characters)
        start_x = -(n - 1) * spacing / 2
        for i, char in enumerate(characters):
            char_id = _VOXTA_CHARACTERS.get(char, char) if isinstance(char, str) else char
            self.add_person(position=(start_x + i * spacing, 0, 0),
                            voxta_char_id=char_id, enable_lip_sync=True, enable_actions=True)

    # ── 信息 ──

    def summary(self) -> str:
        atoms = self.data.get("atoms", [])
        by_type = {}
        for a in atoms:
            t = a.get("type", "?")
            by_type[t] = by_type.get(t, 0) + 1
        lines = [f"Scene v{self.data.get('version', '?')} | {len(atoms)} atoms"]
        for t, c in sorted(by_type.items()):
            lines.append(f"  {t}: {c}")
        for a in atoms:
            if a.get("type") == "Person":
                for s in a.get("storables", []):
                    if "Voxta" in s.get("id", ""):
                        cid = s.get("characterId", "?")
                        cname = next((k for k, v in _VOXTA_CHARACTERS.items() if v == cid), cid[:12])
                        lines.append(f"  Voxta: {a['id']} → {cname}")
        return "\n".join(lines)


# ── 场景文件管理 ──

def list_scenes(directory: str = None, include_generated: bool = True) -> list:
    """列出所有场景文件"""
    scenes = []
    dirs_to_scan = []

    if directory:
        dirs_to_scan.append(Path(directory))
    else:
        dirs_to_scan.append(VAM_CONFIG.SCENES_DIR)

    for d in dirs_to_scan:
        if not d.exists():
            continue
        for f in d.rglob("*.json"):
            if f.suffix == ".json" and not f.name.endswith(".hide"):
                try:
                    stat = f.stat()
                    scenes.append({
                        "name": f.stem,
                        "path": str(f),
                        "size_kb": round(stat.st_size / 1024, 1),
                        "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                        "is_generated": "Generated" in str(f),
                    })
                except OSError:
                    pass

    scenes.sort(key=lambda x: x.get("modified", ""), reverse=True)
    return scenes


def read_scene(path: str) -> dict:
    """读取场景JSON"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_scene_info(path: str) -> dict:
    """获取场景详细信息"""
    data = read_scene(path)
    atoms = data.get("atoms", [])
    by_type = {}
    voxta_chars = []

    for a in atoms:
        t = a.get("type", "?")
        by_type[t] = by_type.get(t, 0) + 1
        if t == "Person":
            for s in a.get("storables", []):
                if "Voxta" in s.get("id", ""):
                    voxta_chars.append({
                        "atom_id": a["id"],
                        "char_id": s.get("characterId", ""),
                        "lip_sync": s.get("enableLipSync", "false"),
                        "actions": s.get("enableActions", "false"),
                    })

    plugins = set()
    for a in atoms:
        for s in a.get("storables", []):
            sid = s.get("id", "")
            if sid.startswith("plugin#"):
                plugins.add(sid.split("_", 1)[-1].split(":")[0] if "_" in sid else sid)

    return {
        "version": data.get("version", "?"),
        "atom_count": len(atoms),
        "atom_types": by_type,
        "voxta_characters": voxta_chars,
        "plugins": list(plugins),
    }


def delete_scene(path: str) -> bool:
    """删除场景文件"""
    try:
        os.remove(path)
        return True
    except OSError:
        return False


# ═══════════════════════════════════════════════════════
# 对话树 (from vam-story-builder dialog system)
# ═══════════════════════════════════════════════════════

class DialogNode:
    """对话树节点 — 支持条件分支和动作触发。

    从vam-story-builder的Twine对话树系统移植,
    适配VaM Scripter + Voxta脚本系统。
    """

    def __init__(self, node_id: str, text: str, speaker: str = "npc",
                 actions: list = None):
        self.id = node_id
        self.text = text
        self.speaker = speaker
        self.actions = actions or []
        self.choices = []  # [(choice_text, target_node_id, condition?)]
        self.next_id = None  # 线性后继(无选择时)

    def add_choice(self, text: str, target_id: str, condition: str = None):
        """添加选择分支"""
        self.choices.append({
            "text": text, "target": target_id,
            "condition": condition,
        })
        return self

    def set_next(self, target_id: str):
        """设置线性后继"""
        self.next_id = target_id
        return self

    def to_dict(self) -> dict:
        d = {
            "id": self.id, "text": self.text, "speaker": self.speaker,
            "actions": self.actions,
        }
        if self.choices:
            d["choices"] = self.choices
        if self.next_id:
            d["next"] = self.next_id
        return d


class DialogTree:
    """对话树 — 管理分支对话流程。

    从vam-story-builder Twine系统移植,增强为:
    - JSON序列化(可嵌入场景或独立保存)
    - 条件分支(基于Voxta flags/variables)
    - 动作触发(连接VaM Atom动画/表情)
    """

    def __init__(self, name: str = "dialog"):
        self.name = name
        self.nodes = {}
        self.start_id = None

    def add_node(self, node: DialogNode) -> "DialogTree":
        self.nodes[node.id] = node
        if self.start_id is None:
            self.start_id = node.id
        return self

    def create_node(self, node_id: str, text: str, speaker: str = "npc",
                    actions: list = None) -> DialogNode:
        """创建并添加节点,返回节点引用以便链式调用"""
        node = DialogNode(node_id, text, speaker, actions)
        self.add_node(node)
        return node

    def get_node(self, node_id: str) -> Optional[DialogNode]:
        return self.nodes.get(node_id)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "start": self.start_id,
            "nodes": {nid: n.to_dict() for nid, n in self.nodes.items()},
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    def save(self, path: str = None) -> str:
        """保存对话树为JSON"""
        if path is None:
            path = str(VAM_CONFIG.SCENES_GENERATED / f"dialog_{self.name}.json")
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.to_json(), encoding="utf-8")
        return str(p)

    @classmethod
    def load(cls, path: str) -> "DialogTree":
        """从JSON加载对话树"""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        tree = cls(data.get("name", "dialog"))
        tree.start_id = data.get("start")
        for nid, nd in data.get("nodes", {}).items():
            node = DialogNode(
                nid, nd["text"], nd.get("speaker", "npc"),
                nd.get("actions", [])
            )
            for ch in nd.get("choices", []):
                node.add_choice(ch["text"], ch["target"], ch.get("condition"))
            if nd.get("next"):
                node.set_next(nd["next"])
            tree.nodes[nid] = node
        return tree

    def to_voxta_script(self) -> str:
        """将对话树编译为Voxta脚本(characterMessage序列)。

        生成可嵌入Characters.Scripts的JavaScript代码。
        """
        lines = ['import { chat } from "@voxta";']
        lines.append(f'let currentNode = "{self.start_id}";')
        lines.append('const nodes = ' + json.dumps(
            {nid: n.to_dict() for nid, n in self.nodes.items()},
            ensure_ascii=False
        ) + ';')
        lines.append('''
function playNode(nodeId) {
  const node = nodes[nodeId];
  if(!node) return;
  chat.characterMessage(node.text);
  if(node.actions) {
    node.actions.forEach(a => chat.appTrigger(a));
  }
  if(node.next) {
    currentNode = node.next;
  }
}
chat.addEventListener("start", (e) => {
  if(!e.hasBootstrapMessages) playNode(currentNode);
});
chat.addEventListener("messageReceived", (e) => {
  const node = nodes[currentNode];
  if(node && node.choices) {
    const msg = e.message.toLowerCase();
    for(const ch of node.choices) {
      if(msg.includes(ch.text.toLowerCase())) {
        currentNode = ch.target;
        playNode(currentNode);
        return;
      }
    }
  }
  if(node && node.next) {
    currentNode = node.next;
    playNode(currentNode);
  }
});''')
        return "\n".join(lines)

    def summary(self) -> str:
        total = len(self.nodes)
        branching = sum(1 for n in self.nodes.values() if n.choices)
        linear = sum(1 for n in self.nodes.values() if n.next_id and not n.choices)
        terminal = sum(1 for n in self.nodes.values()
                       if not n.next_id and not n.choices)
        return (f"DialogTree '{self.name}': {total} nodes "
                f"({branching} branching, {linear} linear, {terminal} terminal)")


# ═══════════════════════════════════════════════════════
# 场景合并加载 (from vam-story-builder merge-load)
# ═══════════════════════════════════════════════════════

def merge_scenes(base_path: str, *overlay_paths: str,
                 conflict: str = "overlay") -> dict:
    """合并多个场景JSON(merge-load兼容)。

    从vam-story-builder的merge-load系统移植:
    - base: 基础场景(包含环境/灯光/相机)
    - overlays: 叠加层(角色/道具/脚本)
    - conflict: "overlay"=覆盖同ID atom | "skip"=跳过 | "rename"=重命名

    返回合并后的场景dict。
    """
    base = read_scene(base_path)
    base_ids = {a["id"] for a in base.get("atoms", [])}

    for overlay_path in overlay_paths:
        overlay = read_scene(overlay_path)
        for atom in overlay.get("atoms", []):
            aid = atom["id"]
            if aid in base_ids:
                if conflict == "skip":
                    continue
                elif conflict == "rename":
                    i = 2
                    while f"{aid}_{i}" in base_ids:
                        i += 1
                    atom["id"] = f"{aid}_{i}"
                    base_ids.add(atom["id"])
                else:  # overlay
                    base["atoms"] = [a for a in base["atoms"] if a["id"] != aid]
            base["atoms"].append(atom)
            base_ids.add(atom["id"])

    return base


# ═══════════════════════════════════════════════════════
# 场景模板 (快速原型)
# ═══════════════════════════════════════════════════════

class SceneTemplates:
    """预设场景模板 — 一键生成常用场景配置。"""

    @staticmethod
    def conversation(char_names: list, environment: str = "indoor") -> SceneBuilder:
        """对话场景: N个角色面对面"""
        scene = SceneBuilder()
        scene.add_camera(position=(0, 1.6, 2.5), fov=55)
        scene.add_three_point_lighting()
        n = len(char_names)
        spacing = 1.0
        start_x = -(n - 1) * spacing / 2
        for i, name in enumerate(char_names):
            char_id = _VOXTA_CHARACTERS.get(name, name)
            scene.add_person(
                position=(start_x + i * spacing, 0, 0),
                rotation=(0, 180 if i % 2 == 0 else 0, 0),
                voxta_char_id=char_id,
                enable_lip_sync=True,
                enable_actions=True,
            )
        return scene

    @staticmethod
    def interview(host_name: str, guest_name: str) -> SceneBuilder:
        """访谈场景: 主持人+嘉宾 对坐"""
        scene = SceneBuilder()
        scene.add_camera(position=(0, 1.6, 3.0), fov=50)
        scene.add_three_point_lighting()
        host_id = _VOXTA_CHARACTERS.get(host_name, host_name)
        guest_id = _VOXTA_CHARACTERS.get(guest_name, guest_name)
        scene.add_person(position=(-0.6, 0, 0), rotation=(0, 30, 0),
                         voxta_char_id=host_id, enable_lip_sync=True)
        scene.add_person(position=(0.6, 0, 0), rotation=(0, -30, 0),
                         voxta_char_id=guest_id, enable_lip_sync=True)
        return scene

    @staticmethod
    def presentation(presenter_name: str) -> SceneBuilder:
        """演示场景: 演讲者 + 文字板"""
        scene = SceneBuilder()
        scene.add_camera(position=(0, 1.5, 3.5), fov=45)
        scene.add_three_point_lighting()
        char_id = _VOXTA_CHARACTERS.get(presenter_name, presenter_name)
        scene.add_person(position=(0.5, 0, 0), rotation=(0, -15, 0),
                         voxta_char_id=char_id, enable_lip_sync=True)
        scene.add_text(position=(-1.0, 1.5, 0.5), text="", font_size=48)
        return scene

    @staticmethod
    def empty_stage(with_lighting: bool = True) -> SceneBuilder:
        """空舞台: 仅相机和灯光"""
        scene = SceneBuilder()
        scene.add_camera(position=(0, 1.5, 3.0), fov=60)
        if with_lighting:
            scene.add_three_point_lighting()
        return scene


# ═══════════════════════════════════════════════════════
# VaM完整参考常量 (from acidbubbles/vam-keybindings GlobalCommands.cs)
# ═══════════════════════════════════════════════════════

VAM_ATOM_TYPES = {
    "People": ["Person"],
    "Light": ["InvisibleLight"],
    "Camera": ["WindowCamera"],
    "Shapes": ["Cube", "Sphere", "Capsule", "ISCube", "ISSphere",
               "ISCapsule", "ISCone", "ISCylinder", "ISTube"],
    "FloorsAndWalls": ["Slate", "Wall", "WoodPanel"],
    "Reflective": ["Glass", "ReflectiveSlate", "ReflectiveWoodPanel"],
    "Sound": ["AudioSource", "AptSpeaker", "RhythmAudioSource"],
    "Force": ["CycleForce", "GrabPoint", "RhythmForce", "SyncForce"],
    "Triggers": ["Button", "CollisionTrigger", "LookAtTrigger",
                 "UIButton", "UIButtonImage", "UISlider", "UIToggle",
                 "VariableTrigger"],
    "Misc": ["AnimationPattern", "ClothGrabSphere", "CustomUnityAsset",
             "Empty", "ImagePanel", "SimpleSign", "SubScene",
             "UIText", "VaMLogo", "WebBrowser", "WebPanel"],
    "Toys": ["Dildo", "Paddle"],
}

VAM_PERSON_CONTROLLERS = [
    "control", "headControl", "neckControl",
    "lShoulderControl", "rShoulderControl",
    "lArmControl", "rArmControl",
    "lElbowControl", "rElbowControl",
    "lHandControl", "rHandControl",
    "chestControl", "lNippleControl", "rNippleControl",
    "abdomen2Control", "abdomenControl",
    "hipControl", "pelvisControl",
    "testesControl", "penisBaseControl", "penisMidControl", "penisTipControl",
    "lThighControl", "rThighControl",
    "lKneeControl", "rKneeControl",
    "lFootControl", "rFootControl",
    "lToeControl", "rToeControl",
    "eyeTargetControl",
]

VAM_PERSON_TABS = [
    "Clothing", "Hair", "Appearance Presets", "General Presets",
    "Pose Presets", "Skin Presets", "Plugins Presets",
    "Morphs Presets", "Hair Presets", "Clothing Presets",
    "Male Morphs", "Female Morphs",
]

VAM_MAIN_TABS = [
    "TabFile", "TabUserPrefs", "TabNavigation", "TabSelect",
    "TabSessionPluginPresets", "TabSessionPlugins",
    "TabScenePlugins", "TabScenePluginPresets",
    "TabSceneLighting", "TabSceneMisc", "TabAnimation",
    "TabAddAtom", "TabAudio",
]
