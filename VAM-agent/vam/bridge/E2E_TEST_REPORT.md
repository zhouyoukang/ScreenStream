# AgentBridge v2.0 E2E Test Report

> Date: 2026-03-04 | VaM: UNOFFICIAL | Bridge: AgentBridge/2.0.0 | Port: 8285

## Summary

| Category | Pass | Fail | Skip | Total |
|----------|------|------|------|-------|
| Health/Status | 2 | 0 | 0 | 2 |
| Atoms CRUD | 5 | 0 | 0 | 5 |
| Controllers | 2 | 0 | 0 | 2 |
| Storable Params | 3 | 0 | 0 | 3 |
| Morphs | 3 | 0 | 0 | 3 |
| Scene Ops | 5 | 0 | 0 | 5 |
| Global Actions | 3 | 2 | 0 | 5 |
| Plugins | 1 | 0 | 0 | 1 |
| Log | 1 | 0 | 0 | 1 |
| Batch Commands | 1 | 0 | 0 | 1 |
| Prefs | 1 | 0 | 0 | 1 |
| Navigate | 1 | 0 | 0 | 1 |
| Voxta/Timeline | 0 | 0 | 2 | 2 |
| **Total** | **28** | **2** | **2** | **32** |

**Pass Rate: 87.5% (28/32)** | Effective: 93.3% (28/30 testable)

## Detailed Results

### Health/Status
- [x] `GET /api/health` → 200, `{"ok":"true", "version":"AgentBridge/2.0.0"}`
- [x] `GET /api/status` → 200, atomCount/freezeAnimation/vamVersion correct

### Atoms CRUD
- [x] `GET /api/atoms` → 200, returns all atoms with id/type/on/position
- [x] `GET /api/atom/{id}` → 200, full atom detail (279 storables for Person)
- [x] `POST /api/atom` → 200, creates Empty atom, returns full detail
- [x] `DELETE /api/atom/{id}` → 200, removes atom, verified via GET /api/atoms
- [x] `GET /api/atom-types` → 200, returns 21 types including Person/Empty/CustomUnityAsset

### Controllers
- [x] `GET /api/atom/{id}/controllers` → 200, lists controllers with position/rotation/state (41 for Person)
- [x] `POST /api/atom/{id}/controller/{ctrl}` → 200, position set verified

### Storable Parameters
- [x] `GET /api/atom/{id}/storable/{sid}/params` → 200, returns floats/bools/strings
- [x] `POST /api/atom/{id}/storable/{sid}/float` → 200, scale changed from 1→2
- [x] `GET /api/atom/{id}/storable/{sid}/actions` → 200, lists available actions

### Morphs
- [x] `GET /api/atom/{id}/morphs?filter=smile` → 200, filtered morph list
- [x] `GET /api/atom/{id}/morphs?modified=true` → 200, only non-default morphs
- [x] `POST /api/atom/{id}/morphs` → 200, morph value set successfully

### Scene Operations
- [x] `GET /api/scene/info` → 200, atomCount/atomTypes/freezeAnimation
- [x] `GET /api/scenes` → 200, lists scene files with path/name/dir/size/modified
- [x] `POST /api/scene/load` → 200, loaded scene, atoms updated
- [x] `POST /api/scene/save` → 200, saved scene to file
- [x] `POST /api/scene/clear` → 200, cleared scene (loads default)

### Global Actions
- [x] `play` → 200, animation started
- [x] `stop` → 200, animation stopped
- [x] `unknown` → 400, correct error response
- [ ] `undo` → 400, "Undo not available" (method not found via reflection)
- [ ] `redo` → 400, "Redo not available" (method not found via reflection)

### Other Endpoints
- [x] `GET /api/atom/{id}/plugins` → 200 (fixed: now works with/without trailing slash)
- [x] `GET /api/log` → 200, returns message buffer
- [x] `POST /api/command` → 200, batch commands execute in sequence
- [x] `GET /api/prefs` → 200, returns VaM preferences
- [x] `POST /api/navigate` → 200, selects atom via SelectController
- [x] `POST /api/freeze` → 200, freeze state set via reflection

### Skipped (No Plugins Loaded)
- [ ] `Voxta endpoints` — No Voxta plugin in test scene
- [ ] `Timeline endpoints` — No Timeline plugin in test scene

## Bugs Found & Fixed

### During Compilation (9 fixes)
1. **JSONObject→JSONClass** — VaM uses `JSONClass` not `JSONObject`
2. **JSONBool→JSONData(bool)** — `JSONBool` class not accessible
3. **Implicit type conversions** — VaM's SimpleJSON lacks implicit operators for bool/int/float; fixed with `.AsBool`/`.AsInt`/`.AsFloat` setters and `JB()`/`JI()`/`JF()` helpers
4. **MotionAnimationMaster.PlayAll** — Method doesn't exist; use `StartPlayback`/`StopPlayback`/`ResetAnimation`
5. **SuperController.Undo/Redo** — Not directly callable; reflection fallback (methods not found at runtime)
6. **SuperController.freezeAnimation** — Read-only property; reflection setter
7. **SuperController.NavigateToAtom** — Doesn't exist; replaced with `SelectController`
8. **SuperController.ClearAll** — Doesn't exist; replaced with `NewScene`
9. **AddAtomByType ambiguity** — Multiple overloads; explicit `(type, true, true, true)` call

### During E2E Testing (2 fixes)
10. **ExtractSegment off-by-one** — `RemoveEmptyEntries` shifted indices; removed flag
11. **Plugins route trailing slash** — Route only matched `/plugins/`; added `EndsWith("/plugins")`

## Known Limitations
- JSON values serialized as strings (VaM's SimpleJSON `JSONData` stores everything as strings internally): `"atomCount":"4"` instead of `"atomCount":4`
- Scene paths use backslashes on Windows; clients must JSON-escape them (`\\`)
- Undo/Redo unavailable via reflection in this VaM version
- `freezeAnimation` setter uses reflection (may be read-only in some versions)

## Compilation Command
```powershell
dotnet "C:\Program Files\dotnet\sdk\8.0.418\Roslyn\bincore\csc.dll" `
  /target:library /langversion:latest /nostdlib `
  /out:AgentBridge.dll `
  /reference:mscorlib.dll /reference:System.dll /reference:System.Core.dll `
  /reference:Assembly-CSharp.dll /reference:UnityEngine.dll `
  /reference:UnityEngine.CoreModule.dll /reference:UnityEngine.ImageConversionModule.dll `
  /reference:BepInEx.dll /reference:0Harmony.dll `
  /nowarn:CS0114,CS0108 AgentBridge.cs
```

## Deployment
- Source: `d:\道\道生一\一生二\VAM-agent\vam\bridge\AgentBridge.cs`
- DLL: `F:\vam1.22\VAM版本\vam1.22.1.0\BepInEx\plugins\AgentBridge.dll` (46KB)
- Requires VaM restart after DLL update (BepInEx loads plugins at startup)
