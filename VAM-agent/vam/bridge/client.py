"""
VaM Bridge HTTP Client v2.0 — Python wrapper for AgentBridge BepInEx plugin.

All VaM runtime operations go through this client:
  Python Agent → HTTP → AgentBridge (BepInEx) → VaM C# API

v2.0 additions (based on deep reverse-engineering of VaM core):
  - StringChooser param support (required for Voxta character/scenario selection)
  - Storable action listing
  - Voxta convenience endpoints (send/state/action - no storable ID lookup)
  - Timeline convenience endpoints (play/stop/scrub/speed)
  - Morph filtering (?filter= and ?modified=true)
  - Scene file browser, log access, prefs, atom types, global actions
  - Lightweight health check (no main-thread marshal)

Non-interference guarantee:
  - All operations are HTTP calls to a background thread in VaM
  - No mouse/keyboard/focus stealing
  - User continues using VaM normally
"""

import json
import logging
import urllib.request
import urllib.error
import urllib.parse
from typing import Optional, Dict, List, Any, Tuple, Union

log = logging.getLogger("vam.bridge")

# Default bridge port (must match AgentBridge.cs config)
DEFAULT_PORT = 8285
DEFAULT_HOST = "127.0.0.1"
DEFAULT_TIMEOUT = 30


class VaMBridgeError(Exception):
    """Bridge communication error"""
    def __init__(self, message: str, status_code: int = 0, response: dict = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response or {}


class VaMBridge:
    """
    Python client for the AgentBridge v2.0 BepInEx HTTP plugin.
    
    Provides typed methods for ALL VaM runtime operations:
    - Atom CRUD (create/read/update/delete)
    - Storable parameter get/set (float/bool/string/chooser)
    - Action invocation and discovery
    - Controller position/rotation
    - Morph manipulation (with filtering)
    - Scene load/save/clear/browse
    - Screenshot capture
    - Voxta chat control (send/state/action)
    - Timeline animation control (play/stop/scrub/speed)
    - Global VaM actions (undo/redo/play/stop/reset)
    - Log access, prefs management
    - Batch command execution
    """

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT,
                 auth_key: str = "", timeout: int = DEFAULT_TIMEOUT):
        self.base_url = f"http://{host}:{port}"
        self.auth_key = auth_key
        self.timeout = timeout

    # ══════════════════════════════════════════
    # HTTP Transport
    # ══════════════════════════════════════════

    def _request(self, method: str, path: str, data: dict = None) -> dict:
        """Send HTTP request to the bridge."""
        url = f"{self.base_url}{path}"
        body = json.dumps(data).encode("utf-8") if data else None

        req = urllib.request.Request(url, data=body, method=method)
        req.add_header("Content-Type", "application/json")
        if self.auth_key:
            req.add_header("X-Agent-Key", self.auth_key)

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8") if e.fp else "{}"
            try:
                err_data = json.loads(raw)
            except json.JSONDecodeError:
                err_data = {"error": raw}
            raise VaMBridgeError(
                err_data.get("error", f"HTTP {e.code}"),
                status_code=e.code,
                response=err_data,
            )
        except urllib.error.URLError as e:
            raise VaMBridgeError(
                f"Bridge unreachable at {self.base_url}: {e.reason}"
            )
        except Exception as e:
            raise VaMBridgeError(f"Bridge request failed: {e}")

    def _get(self, path: str) -> dict:
        return self._request("GET", path)

    def _post(self, path: str, data: dict = None) -> dict:
        return self._request("POST", path, data)

    def _delete(self, path: str) -> dict:
        return self._request("DELETE", path)

    @staticmethod
    def _encode(segment: str) -> str:
        """URL-encode a path segment."""
        return urllib.parse.quote(segment, safe="")

    # ══════════════════════════════════════════
    # Status
    # ══════════════════════════════════════════

    def status(self) -> dict:
        """Get VaM runtime status."""
        return self._get("/api/status")

    def health(self) -> dict:
        """Lightweight health check (no main-thread marshal, instant)."""
        return self._get("/api/health")

    def is_alive(self) -> bool:
        """Check if bridge is reachable and VaM is running."""
        try:
            s = self.health()
            ok = s.get("ok", False)
            return ok is True or (isinstance(ok, str) and ok.lower() == "true")
        except VaMBridgeError:
            return False

    def list_atom_types(self) -> List[str]:
        """List all creatable atom types."""
        r = self._get("/api/atom-types")
        return r.get("types", [])

    # ══════════════════════════════════════════
    # Atoms
    # ══════════════════════════════════════════

    def list_atoms(self) -> List[dict]:
        """List all atoms in current scene."""
        return self._get("/api/atoms")

    def get_atom(self, atom_id: str) -> dict:
        """Get detailed atom info including storables and controllers."""
        return self._get(f"/api/atom/{self._encode(atom_id)}")

    def create_atom(self, atom_type: str, atom_id: str = None) -> dict:
        """Create a new atom. Returns atom details after creation."""
        data = {"type": atom_type}
        if atom_id:
            data["id"] = atom_id
        return self._post("/api/atom", data)

    def remove_atom(self, atom_id: str) -> dict:
        """Remove an atom from the scene."""
        return self._delete(f"/api/atom/{self._encode(atom_id)}")

    # ══════════════════════════════════════════
    # Storables & Parameters
    # ══════════════════════════════════════════

    def list_storables(self, atom_id: str) -> List[str]:
        """List all storable IDs on an atom."""
        r = self._get(f"/api/atom/{self._encode(atom_id)}/storables")
        return r.get("storables", [])

    def get_params(self, atom_id: str, storable_id: str) -> dict:
        """Get all parameters (float/bool/string) of a storable."""
        return self._get(
            f"/api/atom/{self._encode(atom_id)}"
            f"/storable/{self._encode(storable_id)}/params"
        )

    def set_float(self, atom_id: str, storable_id: str,
                  name: str, value: float) -> dict:
        """Set a float parameter."""
        return self._post(
            f"/api/atom/{self._encode(atom_id)}"
            f"/storable/{self._encode(storable_id)}/float",
            {"name": name, "value": value}
        )

    def set_bool(self, atom_id: str, storable_id: str,
                 name: str, value: bool) -> dict:
        """Set a bool parameter."""
        return self._post(
            f"/api/atom/{self._encode(atom_id)}"
            f"/storable/{self._encode(storable_id)}/bool",
            {"name": name, "value": value}
        )

    def set_string(self, atom_id: str, storable_id: str,
                   name: str, value: str) -> dict:
        """Set a string parameter."""
        return self._post(
            f"/api/atom/{self._encode(atom_id)}"
            f"/storable/{self._encode(storable_id)}/string",
            {"name": name, "value": value}
        )

    def call_action(self, atom_id: str, storable_id: str, name: str) -> dict:
        """Call a JSONStorableAction on a storable."""
        return self._post(
            f"/api/atom/{self._encode(atom_id)}"
            f"/storable/{self._encode(storable_id)}/action",
            {"name": name}
        )

    def get_choosers(self, atom_id: str, storable_id: str) -> List[dict]:
        """Get all StringChooser parameters and their available choices."""
        r = self._get(
            f"/api/atom/{self._encode(atom_id)}"
            f"/storable/{self._encode(storable_id)}/choosers"
        )
        return r.get("choosers", [])

    def set_chooser(self, atom_id: str, storable_id: str,
                    name: str, value: str) -> dict:
        """Set a StringChooser parameter value."""
        return self._post(
            f"/api/atom/{self._encode(atom_id)}"
            f"/storable/{self._encode(storable_id)}/chooser",
            {"name": name, "value": value}
        )

    def get_actions(self, atom_id: str, storable_id: str) -> List[str]:
        """List all available actions on a storable."""
        r = self._get(
            f"/api/atom/{self._encode(atom_id)}"
            f"/storable/{self._encode(storable_id)}/actions"
        )
        return r.get("actions", [])

    # ══════════════════════════════════════════
    # Controllers (Position/Rotation)
    # ══════════════════════════════════════════

    def get_controllers(self, atom_id: str) -> List[dict]:
        """List all controllers on an atom with positions."""
        r = self._get(f"/api/atom/{self._encode(atom_id)}/controllers")
        return r.get("controllers", [])

    def set_controller(self, atom_id: str, controller_name: str,
                       position: Tuple[float, float, float] = None,
                       rotation: Tuple[float, float, float] = None) -> dict:
        """Set controller position and/or rotation."""
        data = {}
        if position is not None:
            data["position"] = {"x": position[0], "y": position[1], "z": position[2]}
        if rotation is not None:
            data["rotation"] = {"x": rotation[0], "y": rotation[1], "z": rotation[2]}
        return self._post(
            f"/api/atom/{self._encode(atom_id)}"
            f"/controller/{self._encode(controller_name)}",
            data
        )

    # ══════════════════════════════════════════
    # Morphs
    # ══════════════════════════════════════════

    def list_morphs(self, atom_id: str, filter: str = None,
                    modified_only: bool = False) -> dict:
        """List morphs on a Person atom.
        
        Args:
            filter: Name substring filter (case-insensitive)
            modified_only: If True, only return non-default morphs
        """
        params = []
        if filter:
            params.append(f"filter={urllib.parse.quote(filter)}")
        if modified_only:
            params.append("modified=true")
        qs = "?" + "&".join(params) if params else ""
        return self._get(f"/api/atom/{self._encode(atom_id)}/morphs{qs}")

    def set_morph(self, atom_id: str, name: str, value: float) -> dict:
        """Set a morph value on a Person atom."""
        return self._post(
            f"/api/atom/{self._encode(atom_id)}/morphs",
            {"name": name, "value": value}
        )

    def set_morphs(self, atom_id: str, morphs: Dict[str, float]) -> List[dict]:
        """Set multiple morphs at once via batch command."""
        commands = [
            {"action": "set_morph", "params": {"atom": atom_id, "name": n, "value": v}}
            for n, v in morphs.items()
        ]
        return self.batch(commands)

    # ══════════════════════════════════════════
    # Scene
    # ══════════════════════════════════════════

    def load_scene(self, path: str) -> dict:
        """Load a scene file."""
        return self._post("/api/scene/load", {"path": path})

    def save_scene(self, path: str) -> dict:
        """Save current scene to file."""
        return self._post("/api/scene/save", {"path": path})

    def clear_scene(self) -> dict:
        """Clear all atoms from scene."""
        return self._post("/api/scene/clear")

    def scene_info(self) -> dict:
        """Get current scene information."""
        return self._get("/api/scene/info")

    # ══════════════════════════════════════════
    # Misc
    # ══════════════════════════════════════════

    def freeze(self, enabled: bool = True) -> dict:
        """Toggle animation freeze."""
        return self._post("/api/freeze", {"enabled": enabled})

    def navigate_to(self, atom_id: str) -> dict:
        """Navigate camera to an atom."""
        return self._post("/api/navigate", {"id": atom_id})

    def screenshot(self, path: str = None) -> dict:
        """Capture screenshot. Returns {ok, path, width, height}."""
        data = {"path": path} if path else {}
        return self._post("/api/screenshot", data)

    def list_plugins(self, atom_id: str) -> List[dict]:
        """List plugins on an atom."""
        r = self._get(f"/api/plugins/{self._encode(atom_id)}")
        return r.get("plugins", [])

    # ══════════════════════════════════════════
    # Log & Scenes & Prefs (v2.0)
    # ══════════════════════════════════════════

    def get_log(self) -> List[dict]:
        """Get recent VaM log messages from ring buffer."""
        r = self._get("/api/log")
        return r.get("messages", [])

    def list_scenes(self) -> List[dict]:
        """Browse available scene files."""
        r = self._get("/api/scenes")
        return r.get("scenes", [])

    def get_prefs(self) -> dict:
        """Read VaM preferences (prefs.json)."""
        r = self._get("/api/prefs")
        return r.get("prefs", {})

    def set_prefs(self, **kwargs) -> dict:
        """Update VaM preferences. Pass key=value pairs."""
        return self._post("/api/prefs", kwargs)

    # ══════════════════════════════════════════
    # Global Actions (v2.0)
    # ══════════════════════════════════════════

    def global_action(self, action: str) -> dict:
        """Execute a global SuperController action.
        
        Actions: play, stop, reset, undo, redo
        """
        return self._post("/api/global/action", {"action": action})

    def undo(self) -> dict:
        """Undo last action."""
        return self.global_action("undo")

    def redo(self) -> dict:
        """Redo last undone action."""
        return self.global_action("redo")

    # ══════════════════════════════════════════
    # Batch Commands
    # ══════════════════════════════════════════

    def batch(self, commands: List[dict]) -> dict:
        """Execute multiple commands in a single request.
        
        Each command: {"action": str, "params": dict}
        
        Actions:
          set_float:      {atom, storable, name, value}
          set_bool:       {atom, storable, name, value}
          set_string:     {atom, storable, name, value}
          set_chooser:    {atom, storable, name, value}  (v2.0)
          call_action:    {atom, storable, name}
          set_position:   {atom, controller, x, y, z}
          set_rotation:   {atom, controller, x, y, z}    (v2.0)
          set_morph:      {atom, name, value}
          voxta_send:     {atom, message}                (v2.0)
          voxta_action:   {atom, name}                   (v2.0)
        """
        return self._post("/api/command", {"commands": commands})

    # ══════════════════════════════════════════
    # High-Level Convenience Methods
    # ══════════════════════════════════════════

    def set_expression(self, atom_id: str, expression: str,
                       intensity: float = 1.0) -> List[dict]:
        """Set a facial expression using predefined morph combinations.
        
        Expressions: smile, sad, angry, surprised, wink, neutral
        """
        EXPRESSIONS = {
            "smile": {"Mouth Smile": 0.7, "Mouth Smile Simple": 0.5,
                       "Brow Inner Up": 0.3},
            "sad": {"Mouth Frown": 0.6, "Brow Inner Up": 0.5,
                     "Brow Down": 0.3},
            "angry": {"Brow Down": 0.7, "Nose Wrinkle": 0.4,
                       "Mouth Narrow": 0.3},
            "surprised": {"Brow Inner Up": 0.8, "Mouth Open Wide": 0.5,
                           "Eyes Squint": -0.3},
            "wink": {"Eye Blink Left": 0.9},
            "neutral": {"Mouth Smile": 0, "Mouth Frown": 0, "Brow Down": 0,
                         "Brow Inner Up": 0, "Mouth Open Wide": 0},
        }
        morphs = EXPRESSIONS.get(expression, {})
        scaled = {k: v * intensity for k, v in morphs.items()}
        return self.set_morphs(atom_id, scaled)

    def move_hand(self, atom_id: str, hand: str = "right",
                  position: Tuple[float, float, float] = None,
                  rotation: Tuple[float, float, float] = None) -> dict:
        """Move a character's hand controller."""
        ctrl = "rHandControl" if hand == "right" else "lHandControl"
        return self.set_controller(atom_id, ctrl, position, rotation)

    def move_head(self, atom_id: str,
                  position: Tuple[float, float, float] = None,
                  rotation: Tuple[float, float, float] = None) -> dict:
        """Move a character's head controller."""
        return self.set_controller(atom_id, "headControl", position, rotation)

    def voxta_send_message(self, atom_id: str, message: str) -> dict:
        """Send a message through Voxta plugin (v2.0 dedicated endpoint).
        
        Uses /api/voxta/{atomId}/send — auto-discovers Voxta storable,
        no manual storable ID lookup needed.
        """
        return self._post(
            f"/api/voxta/{self._encode(atom_id)}/send",
            {"message": message}
        )

    def voxta_state(self, atom_id: str) -> dict:
        """Get comprehensive Voxta plugin state (v2.0).
        
        Returns: connected, active, ready, error, status, state,
                 lastUserMessage, lastCharacterMessage, currentAction,
                 userName, characterName, flags
        """
        return self._get(f"/api/voxta/{self._encode(atom_id)}/state")

    def voxta_get_reply(self, atom_id: str) -> str:
        """Get the last character message from Voxta plugin."""
        state = self.voxta_state(atom_id)
        return state.get("lastCharacterMessage", "")

    def voxta_action(self, atom_id: str, action: str) -> dict:
        """Call a Voxta plugin action (v2.0).
        
        Actions: startNewChat, deleteCurrentChat, revertLastSentMessage,
                 clearContext, enableLipSync
        """
        return self._post(
            f"/api/voxta/{self._encode(atom_id)}/action",
            {"name": action}
        )

    def voxta_new_chat(self, atom_id: str) -> dict:
        """Start a new Voxta chat session."""
        return self.voxta_action(atom_id, "startNewChat")

    def timeline_play(self, atom_id: str, animation: str = None) -> dict:
        """Play a Timeline animation (v2.0 dedicated endpoint)."""
        data = {"action": "play"}
        if animation:
            data["animation"] = animation
        return self._post(f"/api/timeline/{self._encode(atom_id)}", data)

    def timeline_stop(self, atom_id: str) -> dict:
        """Stop Timeline animation (v2.0 dedicated endpoint)."""
        return self._post(
            f"/api/timeline/{self._encode(atom_id)}",
            {"action": "stop"}
        )

    def timeline_scrub(self, atom_id: str, time: float) -> dict:
        """Scrub Timeline to a specific time position."""
        return self._post(
            f"/api/timeline/{self._encode(atom_id)}",
            {"action": "scrub", "time": time}
        )

    def timeline_speed(self, atom_id: str, speed: float) -> dict:
        """Set Timeline playback speed."""
        return self._post(
            f"/api/timeline/{self._encode(atom_id)}",
            {"action": "speed", "value": speed}
        )

    # ══════════════════════════════════════════
    # Diagnostics
    # ══════════════════════════════════════════

    def health_report(self) -> dict:
        """Comprehensive bridge health report."""
        report = {"bridge_alive": False, "vam_running": False}
        try:
            status = self.status()
            report["bridge_alive"] = True
            report["vam_running"] = status.get("running", False)
            report["atom_count"] = status.get("atomCount", 0)
            report["freeze"] = status.get("freezeAnimation", False)
            report["version"] = status.get("version", "unknown")

            # Scene info
            try:
                scene = self.scene_info()
                report["scene"] = scene
            except VaMBridgeError:
                report["scene"] = None

        except VaMBridgeError as e:
            report["error"] = str(e)

        return report

    def __repr__(self):
        alive = "alive" if self.is_alive() else "offline"
        return f"VaMBridge({self.base_url}, {alive})"
