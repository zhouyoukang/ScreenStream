# Quick Recipes: Common Compound Tasks
> AI reads this to instantly know the exact steps for common multi-file operations.
> Eliminates pattern re-derivation. Each recipe = minimal steps for maximum result.

## Recipe 1: Add New Backend API Endpoint

### Files to modify (in order):
1. `InputService.kt` — Add method implementation
2. `InputRoutes.kt` — Add route definition
3. `index.html` — Add UI trigger (optional)
4. `FEATURES.md` — Register feature

### Step 1: InputService.kt
Insert new public method at the appropriate section (see code-index.md INSERT POINTS).
`kotlin
public fun newMethod(param: Type): ReturnType {
    // Implementation using AccessibilityService API
    return result
}
`

### Step 2: InputRoutes.kt
Add route using requireInputService pattern:
`kotlin
// GET endpoint
get("/new-endpoint") { requireInputService { svc ->
    call.respondText(svc.newMethod().toString(), ContentType.Application.Json)
}}

// POST endpoint with JSON body
post("/new-endpoint") { requireInputService { svc ->
    val json = JSONObject(call.receiveText())
    val param = json.optString("param", "")
    svc.newMethod(param)
    call.respondText(jsonOk(), ContentType.Application.Json)
}}

// POST endpoint with path parameter
post("/new-endpoint/{value}") { requireInputService { svc ->
    val value = call.parameters["value"]?.toBooleanStrictOrNull()
    if (value == null) {
        call.respondText(jsonError("Use /new-endpoint/true or /new-endpoint/false"), ContentType.Application.Json, HttpStatusCode.BadRequest)
        return@requireInputService
    }
    val ok = svc.newMethod(value)
    call.respondText(JSONObject().put("ok", ok).put("value", value).toString(), ContentType.Application.Json)
}}
`

### Step 3: index.html (if UI needed)
Add to command menu in buildMenuHTML():
`javascript
['ICON', 'Label', "menuAction(function(){sendInputJson('/new-endpoint',{});showStatus('Done')})", 'Alt+X'],
`
Or add toggle function:
`javascript
function toggleNewFeature() {
    sendInputJson('/new-endpoint/' + (!newFeatureState), {}).then(function(d) {
        newFeatureState = !newFeatureState;
        showStatus('Feature ' + (newFeatureState ? 'ON' : 'OFF'));
    });
}
`

### Step 4: FEATURES.md
Append row to table.

---

## Recipe 2: Add New Frontend Platform Panel (S-series)

### Pattern: Copy S34 (simplest panel)
`javascript
// 1. State variable
var sXXVisible = false;

// 2. Toggle function
function toggleNewPanel() {
    if (sXXVisible) { closePlatformPanels(); return; }
    closePlatformPanels();
    sXXVisible = true;
    var el = document.getElementById('sXXPanel');
    if (!el) {
        el = document.createElement('div');
        el.id = 'sXXPanel';
        el.className = 'platform-panel';
        document.body.appendChild(el);
    }
    el.style.display = 'flex';
    sXXLoad();
}

// 3. Load data
function sXXLoad() {
    var el = document.getElementById('sXXPanel');
    el.innerHTML = '<div style="text-align:center;font-size:16px;font-weight:bold;">Panel Title <span style="cursor:pointer" onclick="toggleNewPanel()">X</span></div>';
    sendInputJson('/api-endpoint', {}).then(function(data) {
        // Render data
    }).catch(function(e) { panelError('sXXPanel', e.message); });
}
`

### Registration checklist:
1. Add keyboard shortcut in keydown handler (Alt+key)
2. Add to closePlatformPanels() cleanup
3. Add to isPlatformPanelOpen() check
4. Add to command menu in buildMenuHTML()
5. Register in FEATURES.md

---

## Recipe 3: Add New Device Control Toggle

### Fastest pattern (3 files, ~15 lines total):

**InputService.kt** (~5 lines):
`kotlin
public fun setNewFeature(enabled: Boolean): Boolean {
    return try {
        // System API call
        true
    } catch (e: Exception) { Log.e(TAG, "setNewFeature: {e.message}"); false }
}
`

**InputRoutes.kt** (~8 lines):
`kotlin
post("/newfeature/{enabled}") { requireInputService { svc ->
    val enabled = call.parameters["enabled"]?.toBooleanStrictOrNull()
    if (enabled == null) {
        call.respondText(jsonError("Use /newfeature/true or /newfeature/false"), ContentType.Application.Json, HttpStatusCode.BadRequest)
        return@requireInputService
    }
    val ok = svc.setNewFeature(enabled)
    call.respondText(JSONObject().put("ok", ok).put("enabled", enabled).toString(), ContentType.Application.Json)
}}
`

**index.html** (~3 lines in buildMenuHTML):
`javascript
['ICON', 'Label', "menuAction(toggleNewFeature)", 'Alt+X'],
// + toggle function
function toggleNewFeature() {
    sendInputJson('/newfeature/' + (!nfState), {}).then(function(d) { nfState = d.enabled; showStatus('Feature ' + (nfState?'ON':'OFF')); });
}
`

---

## Recipe 4: Batch Feature Implementation (multiple small features)

### Strategy: All backend first, then all frontend, then one compile
1. Add ALL new methods to InputService.kt (group by section)
2. Add ALL new routes to InputRoutes.kt (group by section)  
3. Add ALL new UI to index.html (menu items + toggle functions)
4. ONE compile + ONE deploy + verify ALL at once
5. Update FEATURES.md with all new entries

### Why: Avoids multiple compile cycles (each ~30-60s)

---

## Recipe 5: Security-Safe String Handling

### Backend (Kotlin):
- JSON response: Always use `JSONObject().put(key, value)` — NEVER string concatenation
- Path parameters: Always validate with null check + whitelist
- File paths: Always use `sanitizePath()` wrapper
- User filenames: Reject if contains `/ \ ..`

### Frontend (JavaScript):
- All dynamic content: Always wrap in `escapeHtml()`
- onclick handlers with dynamic data: Use `escapeHtml()` for the display, raw value for the action
- localStorage data: Treat as untrusted, escapeHtml before rendering
