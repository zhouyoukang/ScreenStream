"""
VaM Agent Bridge v2.0 — Python client for the BepInEx HTTP Bridge plugin.

Usage:
    from vam.bridge import VaMBridge, VaMBridgeError
    
    bridge = VaMBridge()  # defaults to localhost:8285
    
    # Health & Status
    bridge.health()           # instant, no main-thread marshal
    bridge.status()           # full runtime status
    bridge.is_alive()         # bool
    bridge.list_atom_types()  # creatable types
    
    # Atoms
    bridge.list_atoms()
    bridge.create_atom("Person", "Person#2")
    bridge.remove_atom("Person#2")
    
    # Parameters (float/bool/string/chooser)
    bridge.get_params("Person#1", "geometry")
    bridge.set_float("Person#1", "storable_id", "param_name", 0.5)
    bridge.set_chooser("Person#1", "storable_id", "Character ID", "abc-123")
    bridge.get_choosers("Person#1", "storable_id")
    bridge.get_actions("Person#1", "storable_id")
    
    # Morphs (with filtering)
    bridge.list_morphs("Person#1", filter="Smile", modified_only=True)
    bridge.set_morph("Person#1", "Brow Height", 0.5)
    
    # Voxta (v2.0 - no storable ID lookup needed)
    bridge.voxta_send_message("Person#1", "Hello!")
    state = bridge.voxta_state("Person#1")
    bridge.voxta_new_chat("Person#1")
    
    # Timeline (v2.0)
    bridge.timeline_play("Person#1", animation="wave")
    bridge.timeline_scrub("Person#1", time=2.5)
    bridge.timeline_stop("Person#1")
    
    # Global actions
    bridge.undo()
    bridge.redo()
    bridge.global_action("play")
    
    # Browse & inspect
    bridge.list_scenes()
    bridge.get_log()
    bridge.get_prefs()
"""

from .client import VaMBridge, VaMBridgeError

__all__ = ["VaMBridge", "VaMBridgeError"]
