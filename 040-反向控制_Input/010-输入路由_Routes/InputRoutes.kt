package info.dvkr.screenstream.input

import io.ktor.http.ContentType
import io.ktor.http.HttpStatusCode
import io.ktor.server.application.call
import io.ktor.server.request.receiveText
import io.ktor.server.response.respondText
import io.ktor.server.response.respondTextWriter
import io.ktor.server.routing.Route
import io.ktor.server.routing.RoutingContext
import io.ktor.server.routing.get
import io.ktor.server.routing.post
import io.ktor.server.websocket.webSocket
import io.ktor.websocket.Frame
import io.ktor.websocket.readText
import io.ktor.websocket.CloseReason
import io.ktor.websocket.close
import kotlinx.coroutines.channels.ClosedReceiveChannelException
import org.json.JSONObject

private fun jsonOk(): String = "{\"ok\": true}"
private fun jsonError(msg: String): String = "{\"error\": ${JSONObject.quote(msg)}}"

private suspend fun RoutingContext.requireInputService(block: suspend (InputService) -> Unit) {
    val service = InputService.instance
    if (service == null) {
        call.respondText(jsonError("InputService not connected"), ContentType.Application.Json, HttpStatusCode.ServiceUnavailable)
        return
    }
    try {
        block(service)
    } catch (e: Exception) {
        call.respondText(jsonError(e.message ?: "unknown error"), ContentType.Application.Json, HttpStatusCode.BadRequest)
    }
}

public fun Route.installInputRoutes() {
    get("/status") {
        val json = JSONObject().apply {
            put("connected", InputService.isConnected())
            put("inputEnabled", InputService.isInputEnabled)
            put("scaling", InputService.scaling.toDouble())
            put("screenOffMode", InputService.isScreenOffMode)
        }
        call.respondText(json.toString(), ContentType.Application.Json)
    }

    post("/tap") { requireInputService { svc ->
        val json = JSONObject(call.receiveText())
        if (json.has("nx") && json.has("ny")) {
            svc.tapNormalized(json.getDouble("nx").toFloat(), json.getDouble("ny").toFloat())
        } else {
            svc.tap(json.getInt("x"), json.getInt("y"))
        }
        call.respondText(jsonOk(), ContentType.Application.Json)
    }}

    post("/swipe") { requireInputService { svc ->
        val json = JSONObject(call.receiveText())
        val duration = json.optLong("duration", 300)
        if (json.has("nx1") && json.has("ny1") && json.has("nx2") && json.has("ny2")) {
            svc.swipeNormalized(
                json.getDouble("nx1").toFloat(), json.getDouble("ny1").toFloat(),
                json.getDouble("nx2").toFloat(), json.getDouble("ny2").toFloat(), duration
            )
        } else {
            svc.swipe(json.getInt("x1"), json.getInt("y1"), json.getInt("x2"), json.getInt("y2"), duration)
        }
        call.respondText(jsonOk(), ContentType.Application.Json)
    }}

    post("/key") { requireInputService { svc ->
        val json = JSONObject(call.receiveText())
        svc.onKeyEvent(
            json.optBoolean("down", true), json.getLong("keysym"),
            json.optBoolean("shift", false), json.optBoolean("ctrl", false)
        )
        call.respondText(jsonOk(), ContentType.Application.Json)
    }}

    post("/text") { requireInputService { svc ->
        val json = JSONObject(call.receiveText())
        val result = svc.inputText(json.getString("text"))
        if (result.ok) {
            call.respondText(
                JSONObject().put("ok", true).put("method", result.method ?: "").toString(),
                ContentType.Application.Json
            )
        } else {
            call.respondText(
                JSONObject().put("ok", false).put("error", result.error ?: "").toString(),
                ContentType.Application.Json
            )
        }
    }}

    post("/pointer") { requireInputService { svc ->
        val json = JSONObject(call.receiveText())
        svc.onPointerEvent(json.getInt("buttonMask"), json.getInt("x"), json.getInt("y"))
        call.respondText(jsonOk(), ContentType.Application.Json)
    }}

    post("/home") { requireInputService { it.goHome(); call.respondText(jsonOk(), ContentType.Application.Json) }}
    post("/back") { requireInputService { it.goBack(); call.respondText(jsonOk(), ContentType.Application.Json) }}
    post("/recents") { requireInputService { it.showRecents(); call.respondText(jsonOk(), ContentType.Application.Json) }}
    post("/notifications") { requireInputService { it.showNotifications(); call.respondText(jsonOk(), ContentType.Application.Json) }}
    post("/quicksettings") { requireInputService { it.showQuickSettings(); call.respondText(jsonOk(), ContentType.Application.Json) }}
    post("/volume/up") { requireInputService { it.volumeUp(); call.respondText(jsonOk(), ContentType.Application.Json) }}
    post("/volume/down") { requireInputService { it.volumeDown(); call.respondText(jsonOk(), ContentType.Application.Json) }}
    post("/lock") { requireInputService { it.lockScreen(); call.respondText(jsonOk(), ContentType.Application.Json) }}

    // System Actions
    post("/wake") { requireInputService { it.wakeScreen(); call.respondText(jsonOk(), ContentType.Application.Json) }}
    post("/power") { requireInputService { it.showPowerDialog(); call.respondText(jsonOk(), ContentType.Application.Json) }}
    post("/screenshot") { requireInputService { it.takeScreenshot(); call.respondText(jsonOk(), ContentType.Application.Json) }}
    post("/splitscreen") { requireInputService { it.toggleSplitScreen(); call.respondText(jsonOk(), ContentType.Application.Json) }}

    // Brightness
    post("/brightness/{level}") { requireInputService { svc ->
        val level = call.parameters["level"]?.toIntOrNull()
        if (level == null) {
            call.respondText(jsonError("Invalid brightness level"), ContentType.Application.Json, HttpStatusCode.BadRequest)
            return@requireInputService
        }
        svc.setBrightness(level)
        call.respondText(jsonOk(), ContentType.Application.Json)
    }}
    get("/brightness") { requireInputService { svc ->
        call.respondText(
            JSONObject().put("brightness", svc.getBrightness()).toString(),
            ContentType.Application.Json
        )
    }}

    // Enhanced Gestures
    post("/longpress") { requireInputService { svc ->
        val json = JSONObject(call.receiveText())
        val dur = json.optLong("duration", 0)
        if (json.has("nx") && json.has("ny")) {
            svc.longPressNormalized(json.getDouble("nx").toFloat(), json.getDouble("ny").toFloat(), dur)
        } else {
            svc.longPressAt(json.getInt("x"), json.getInt("y"), dur)
        }
        call.respondText(jsonOk(), ContentType.Application.Json)
    }}

    post("/doubletap") { requireInputService { svc ->
        val json = JSONObject(call.receiveText())
        if (json.has("nx") && json.has("ny")) {
            svc.doubleTapNormalized(json.getDouble("nx").toFloat(), json.getDouble("ny").toFloat())
        } else {
            svc.doubleTapAt(json.getInt("x"), json.getInt("y"))
        }
        call.respondText(jsonOk(), ContentType.Application.Json)
    }}

    post("/scroll") { requireInputService { svc ->
        val json = JSONObject(call.receiveText())
        val direction = json.optString("direction", "down")
        val distance = json.optInt("distance", 500)
        val nx = json.optDouble("nx", 0.5).toFloat()
        val ny = json.optDouble("ny", 0.5).toFloat()
        svc.scrollNormalized(nx, ny, direction, distance)
        call.respondText(jsonOk(), ContentType.Application.Json)
    }}

    post("/pinch") { requireInputService { svc ->
        val json = JSONObject(call.receiveText())
        val cx = json.optDouble("cx", 0.5).toFloat()
        val cy = json.optDouble("cy", 0.5).toFloat()
        val zoomIn = json.optBoolean("zoomIn", true)
        svc.pinchZoom(cx, cy, zoomIn)
        call.respondText(jsonOk(), ContentType.Application.Json)
    }}

    // App & Device Management
    post("/openapp") { requireInputService { svc ->
        val json = JSONObject(call.receiveText())
        val pkg = json.getString("packageName")
        val ok = svc.openApp(pkg)
        if (ok) call.respondText(jsonOk(), ContentType.Application.Json)
        else call.respondText(jsonError("App not found: $pkg"), ContentType.Application.Json, HttpStatusCode.NotFound)
    }}

    post("/openurl") { requireInputService { svc ->
        val json = JSONObject(call.receiveText())
        val url = json.getString("url")
        val ok = svc.openUrl(url)
        if (ok) call.respondText(jsonOk(), ContentType.Application.Json)
        else call.respondText(jsonError("Failed to open URL"), ContentType.Application.Json, HttpStatusCode.BadRequest)
    }}

    get("/deviceinfo") { requireInputService { svc ->
        call.respondText(svc.getDeviceInfo().toString(), ContentType.Application.Json)
    }}

    get("/apps") { requireInputService { svc ->
        call.respondText(svc.getInstalledApps().toString(), ContentType.Application.Json)
    }}

    get("/clipboard") { requireInputService { svc ->
        val text = svc.getClipboardText()
        call.respondText(
            JSONObject().put("text", text ?: JSONObject.NULL).toString(),
            ContentType.Application.Json
        )
    }}

    post("/scaling/{factor}") {
        val factor = call.parameters["factor"]?.toFloatOrNull()
        if (factor == null || factor <= 0) {
            call.respondText(jsonError("Invalid scaling factor"), ContentType.Application.Json, HttpStatusCode.BadRequest)
            return@post
        }
        InputService.scaling = factor
        call.respondText(jsonOk(), ContentType.Application.Json)
    }

    post("/enable/{enabled}") {
        val enabled = call.parameters["enabled"]?.toBooleanStrictOrNull()
        if (enabled == null) {
            call.respondText(jsonError("Invalid enabled value"), ContentType.Application.Json, HttpStatusCode.BadRequest)
            return@post
        }
        InputService.isInputEnabled = enabled
        call.respondText(jsonOk(), ContentType.Application.Json)
    }

    // ==================== View Tree & Semantic Actions (AI Brain Layer) ====================

    get("/viewtree") { requireInputService { svc ->
        val depth = call.request.queryParameters["depth"]?.toIntOrNull() ?: 8
        val tree = svc.getViewTree(depth)
        call.respondText(tree.toString(), ContentType.Application.Json)
    }}

    get("/windowinfo") { requireInputService { svc ->
        call.respondText(svc.getActiveWindowInfo().toString(), ContentType.Application.Json)
    }}

    post("/findclick") { requireInputService { svc ->
        val json = JSONObject(call.receiveText())
        val text = json.optString("text", "")
        val id = json.optString("id", "")
        val result = when {
            text.isNotEmpty() -> svc.findAndClickByText(text)
            id.isNotEmpty() -> svc.findAndClickById(id)
            else -> JSONObject().put("ok", false).put("error", "Provide 'text' or 'id'")
        }
        call.respondText(result.toString(), ContentType.Application.Json)
    }}

    post("/dismiss") { requireInputService { svc ->
        call.respondText(svc.dismissTopDialog().toString(), ContentType.Application.Json)
    }}

    post("/findnodes") { requireInputService { svc ->
        val json = JSONObject(call.receiveText())
        val text = json.optString("text", "")
        if (text.isEmpty()) {
            call.respondText(jsonError("Provide 'text'"), ContentType.Application.Json, HttpStatusCode.BadRequest)
            return@requireInputService
        }
        val nodes = svc.findNodesByText(text)
        call.respondText(JSONObject().put("nodes", nodes).put("count", nodes.length()).toString(), ContentType.Application.Json)
    }}

    post("/settext") { requireInputService { svc ->
        val json = JSONObject(call.receiveText())
        val search = json.optString("search", "")
        val value = json.optString("value", "")
        val result = svc.setNodeText(search, value)
        call.respondText(result.toString(), ContentType.Application.Json)
    }}

    // ==================== Media / Find Phone / Device Control ====================

    post("/media/{action}") { requireInputService { svc ->
        val action = call.parameters["action"] ?: ""
        val ok = svc.mediaControl(action)
        call.respondText(JSONObject().put("ok", ok).put("action", action).toString(), ContentType.Application.Json)
    }}

    post("/findphone/{enabled}") { requireInputService { svc ->
        val ring = call.parameters["enabled"]?.toBooleanStrictOrNull() ?: true
        val ok = svc.findPhone(ring)
        call.respondText(JSONObject().put("ok", ok).put("ringing", ring).toString(), ContentType.Application.Json)
    }}

    post("/vibrate") { requireInputService { svc ->
        val json = runCatching { JSONObject(call.receiveText()) }.getOrElse { JSONObject() }
        val ms = json.optLong("duration", 500)
        val ok = svc.vibrateDevice(ms)
        call.respondText(JSONObject().put("ok", ok).toString(), ContentType.Application.Json)
    }}

    post("/flashlight/{enabled}") { requireInputService { svc ->
        val enabled = call.parameters["enabled"]?.toBooleanStrictOrNull()
        if (enabled == null) {
            call.respondText(jsonError("Use /flashlight/true or /flashlight/false"), ContentType.Application.Json, HttpStatusCode.BadRequest)
            return@requireInputService
        }
        val ok = svc.setFlashlight(enabled)
        call.respondText(JSONObject().put("ok", ok).put("flashlight", enabled).toString(), ContentType.Application.Json)
    }}

    post("/dnd/{enabled}") { requireInputService { svc ->
        val enabled = call.parameters["enabled"]?.toBooleanStrictOrNull()
        if (enabled == null) {
            call.respondText(jsonError("Use /dnd/true or /dnd/false"), ContentType.Application.Json, HttpStatusCode.BadRequest)
            return@requireInputService
        }
        val ok = svc.setDndMode(enabled)
        call.respondText(JSONObject().put("ok", ok).put("dnd", enabled).toString(), ContentType.Application.Json)
    }}

    get("/dnd") { requireInputService { svc ->
        call.respondText(JSONObject().put("dnd", svc.isDndEnabled()).toString(), ContentType.Application.Json)
    }}

    post("/volume") { requireInputService { svc ->
        val json = JSONObject(call.receiveText())
        val stream = json.optString("stream", "music")
        val level = json.optInt("level", 5)
        val ok = svc.setVolumeLevel(stream, level)
        call.respondText(JSONObject().put("ok", ok).put("stream", stream).put("level", level).toString(), ContentType.Application.Json)
    }}

    post("/autorotate/{enabled}") { requireInputService { svc ->
        val enabled = call.parameters["enabled"]?.toBooleanStrictOrNull()
        if (enabled == null) {
            call.respondText(jsonError("Use /autorotate/true or /autorotate/false"), ContentType.Application.Json, HttpStatusCode.BadRequest)
            return@requireInputService
        }
        val ok = svc.setAutoRotate(enabled)
        call.respondText(JSONObject().put("ok", ok).put("autoRotate", enabled).toString(), ContentType.Application.Json)
    }}

    get("/autorotate") { requireInputService { svc ->
        call.respondText(JSONObject().put("autoRotate", svc.isAutoRotate()).toString(), ContentType.Application.Json)
    }}

    get("/foreground") { requireInputService { svc ->
        call.respondText(svc.getForegroundApp().toString(), ContentType.Application.Json)
    }}

    post("/killapp") { requireInputService { svc ->
        val ok = svc.killForegroundApp()
        call.respondText(JSONObject().put("ok", ok).toString(), ContentType.Application.Json)
    }}

    post("/upload") { requireInputService { svc ->
        val json = JSONObject(call.receiveText())
        val filename = json.optString("filename", "upload_${System.currentTimeMillis()}")
        val base64Data = json.optString("data", "")
        if (base64Data.isEmpty()) {
            call.respondText(jsonError("No data provided"), ContentType.Application.Json, HttpStatusCode.BadRequest)
            return@requireInputService
        }
        val bytes = android.util.Base64.decode(base64Data, android.util.Base64.DEFAULT)
        val result = svc.saveFile(filename, bytes)
        call.respondText(result.toString(), ContentType.Application.Json)
    }}

    // ==================== Stay Awake / Show Touches / Rotate ====================

    post("/stayawake/{enabled}") { requireInputService { svc ->
        val enabled = call.parameters["enabled"]?.toBooleanStrictOrNull()
        if (enabled == null) {
            call.respondText(jsonError("Use /stayawake/true or /stayawake/false"), ContentType.Application.Json, HttpStatusCode.BadRequest)
            return@requireInputService
        }
        val ok = svc.setStayAwake(enabled)
        call.respondText(
            JSONObject().put("ok", ok).put("stayAwake", enabled).toString(),
            ContentType.Application.Json
        )
    }}

    get("/stayawake") { requireInputService { svc ->
        call.respondText(
            JSONObject().put("stayAwake", svc.isStayAwake()).toString(),
            ContentType.Application.Json
        )
    }}

    post("/showtouches/{enabled}") { requireInputService { svc ->
        val enabled = call.parameters["enabled"]?.toBooleanStrictOrNull()
        if (enabled == null) {
            call.respondText(jsonError("Use /showtouches/true or /showtouches/false"), ContentType.Application.Json, HttpStatusCode.BadRequest)
            return@requireInputService
        }
        val ok = svc.setShowTouches(enabled)
        call.respondText(
            JSONObject().put("ok", ok).put("showTouches", enabled).toString(),
            ContentType.Application.Json
        )
    }}

    get("/showtouches") { requireInputService { svc ->
        call.respondText(
            JSONObject().put("showTouches", svc.getShowTouches()).toString(),
            ContentType.Application.Json
        )
    }}

    post("/rotate/{degrees}") { requireInputService { svc ->
        val degrees = call.parameters["degrees"]?.toIntOrNull()
        if (degrees == null || degrees !in listOf(0, 90, 180, 270)) {
            call.respondText(jsonError("Use /rotate/0, /rotate/90, /rotate/180, or /rotate/270"), ContentType.Application.Json, HttpStatusCode.BadRequest)
            return@requireInputService
        }
        val ok = svc.setRotation(degrees)
        call.respondText(
            JSONObject().put("ok", ok).put("rotation", degrees).toString(),
            ContentType.Application.Json
        )
    }}

    // ==================== Macro System (Phase 2) ====================

    get("/macro/list") {
        call.respondText(
            MacroEngine.instance.listMacros().toString(),
            ContentType.Application.Json
        )
    }

    get("/macro/running") {
        call.respondText(
            MacroEngine.instance.getRunningMacros().toString(),
            ContentType.Application.Json
        )
    }

    get("/macro/{id}") {
        val id = call.parameters["id"] ?: run {
            call.respondText(jsonError("Missing macro id"), ContentType.Application.Json, HttpStatusCode.BadRequest)
            return@get
        }
        val macro = MacroEngine.instance.getMacro(id)
        if (macro != null) {
            call.respondText(macro.toString(), ContentType.Application.Json)
        } else {
            call.respondText(jsonError("Macro not found: $id"), ContentType.Application.Json, HttpStatusCode.NotFound)
        }
    }

    get("/macro/log/{id}") {
        val id = call.parameters["id"] ?: run {
            call.respondText(jsonError("Missing macro id"), ContentType.Application.Json, HttpStatusCode.BadRequest)
            return@get
        }
        val log = MacroEngine.instance.getExecutionLog(id)
        if (log != null) {
            call.respondText(log.toString(), ContentType.Application.Json)
        } else {
            call.respondText(jsonError("No log for: $id"), ContentType.Application.Json, HttpStatusCode.NotFound)
        }
    }

    post("/macro/create") {
        val json = JSONObject(call.receiveText())
        val id = MacroEngine.instance.createMacro(json)
        call.respondText(
            JSONObject().put("ok", true).put("id", id).toString(),
            ContentType.Application.Json
        )
    }

    post("/macro/run/{id}") { requireInputService { svc ->
        val id = call.parameters["id"] ?: run {
            call.respondText(jsonError("Missing macro id"), ContentType.Application.Json, HttpStatusCode.BadRequest)
            return@requireInputService
        }
        val result = MacroEngine.instance.runMacro(id, svc)
        call.respondText(result.toString(), ContentType.Application.Json)
    }}

    post("/macro/run-inline") { requireInputService { svc ->
        val json = JSONObject(call.receiveText())
        val steps = json.optJSONArray("actions") ?: json.optJSONArray("steps") ?: run {
            call.respondText(jsonError("No actions/steps provided"), ContentType.Application.Json, HttpStatusCode.BadRequest)
            return@requireInputService
        }
        val loopCount = json.optInt("loop", 1)
        val result = MacroEngine.instance.runInline(steps, svc, loopCount)
        call.respondText(result.toString(), ContentType.Application.Json)
    }}

    post("/macro/stop/{id}") {
        val id = call.parameters["id"] ?: run {
            call.respondText(jsonError("Missing macro id"), ContentType.Application.Json, HttpStatusCode.BadRequest)
            return@post
        }
        val stopped = MacroEngine.instance.stopMacro(id)
        call.respondText(
            JSONObject().put("ok", stopped).toString(),
            ContentType.Application.Json
        )
    }

    post("/macro/update/{id}") {
        val id = call.parameters["id"] ?: run {
            call.respondText(jsonError("Missing macro id"), ContentType.Application.Json, HttpStatusCode.BadRequest)
            return@post
        }
        val json = JSONObject(call.receiveText())
        val updated = MacroEngine.instance.updateMacro(id, json)
        if (updated) {
            call.respondText(jsonOk(), ContentType.Application.Json)
        } else {
            call.respondText(jsonError("Macro not found: $id"), ContentType.Application.Json, HttpStatusCode.NotFound)
        }
    }

    post("/macro/delete/{id}") {
        val id = call.parameters["id"] ?: run {
            call.respondText(jsonError("Missing macro id"), ContentType.Application.Json, HttpStatusCode.BadRequest)
            return@post
        }
        val deleted = MacroEngine.instance.deleteMacro(id)
        call.respondText(
            JSONObject().put("ok", deleted).toString(),
            ContentType.Application.Json
        )
    }

    // ==================== S33: Remote File Manager ====================

    get("/files/storage") { requireInputService { svc ->
        call.respondText(svc.getStorageInfo().toString(), ContentType.Application.Json)
    }}

    get("/files/list") { requireInputService { svc ->
        val path = call.request.queryParameters["path"] ?: android.os.Environment.getExternalStorageDirectory().absolutePath
        val showHidden = call.request.queryParameters["hidden"]?.toBooleanStrictOrNull() ?: false
        val sortBy = call.request.queryParameters["sort"] ?: "name"
        call.respondText(svc.listFiles(path, showHidden, sortBy).toString(), ContentType.Application.Json)
    }}

    get("/files/info") { requireInputService { svc ->
        val path = call.request.queryParameters["path"] ?: run {
            call.respondText(jsonError("Missing path"), ContentType.Application.Json, HttpStatusCode.BadRequest)
            return@requireInputService
        }
        call.respondText(svc.getFileInfo(path).toString(), ContentType.Application.Json)
    }}

    get("/files/read") { requireInputService { svc ->
        val path = call.request.queryParameters["path"] ?: run {
            call.respondText(jsonError("Missing path"), ContentType.Application.Json, HttpStatusCode.BadRequest)
            return@requireInputService
        }
        call.respondText(svc.readTextFile(path).toString(), ContentType.Application.Json)
    }}

    get("/files/download") { requireInputService { svc ->
        val path = call.request.queryParameters["path"] ?: run {
            call.respondText(jsonError("Missing path"), ContentType.Application.Json, HttpStatusCode.BadRequest)
            return@requireInputService
        }
        call.respondText(svc.readFileBase64(path).toString(), ContentType.Application.Json)
    }}

    get("/files/search") { requireInputService { svc ->
        val path = call.request.queryParameters["path"] ?: android.os.Environment.getExternalStorageDirectory().absolutePath
        val query = call.request.queryParameters["q"] ?: run {
            call.respondText(jsonError("Missing query parameter 'q'"), ContentType.Application.Json, HttpStatusCode.BadRequest)
            return@requireInputService
        }
        val max = call.request.queryParameters["max"]?.toIntOrNull() ?: 100
        call.respondText(svc.searchFiles(path, query, max).toString(), ContentType.Application.Json)
    }}

    post("/files/mkdir") { requireInputService { svc ->
        val json = JSONObject(call.receiveText())
        val path = json.optString("path", "")
        if (path.isEmpty()) {
            call.respondText(jsonError("Missing path"), ContentType.Application.Json, HttpStatusCode.BadRequest)
            return@requireInputService
        }
        call.respondText(svc.createDirectory(path).toString(), ContentType.Application.Json)
    }}

    post("/files/delete") { requireInputService { svc ->
        val json = JSONObject(call.receiveText())
        val path = json.optString("path", "")
        if (path.isEmpty()) {
            call.respondText(jsonError("Missing path"), ContentType.Application.Json, HttpStatusCode.BadRequest)
            return@requireInputService
        }
        call.respondText(svc.removeFile(path).toString(), ContentType.Application.Json)
    }}

    post("/files/rename") { requireInputService { svc ->
        val json = JSONObject(call.receiveText())
        val path = json.optString("path", "")
        val newName = json.optString("newName", "")
        if (path.isEmpty() || newName.isEmpty()) {
            call.respondText(jsonError("Missing path or newName"), ContentType.Application.Json, HttpStatusCode.BadRequest)
            return@requireInputService
        }
        call.respondText(svc.renameFile(path, newName).toString(), ContentType.Application.Json)
    }}

    post("/files/move") { requireInputService { svc ->
        val json = JSONObject(call.receiveText())
        val src = json.optString("src", "")
        val dest = json.optString("dest", "")
        if (src.isEmpty() || dest.isEmpty()) {
            call.respondText(jsonError("Missing src or dest"), ContentType.Application.Json, HttpStatusCode.BadRequest)
            return@requireInputService
        }
        call.respondText(svc.moveFile(src, dest).toString(), ContentType.Application.Json)
    }}

    post("/files/copy") { requireInputService { svc ->
        val json = JSONObject(call.receiveText())
        val src = json.optString("src", "")
        val dest = json.optString("dest", "")
        if (src.isEmpty() || dest.isEmpty()) {
            call.respondText(jsonError("Missing src or dest"), ContentType.Application.Json, HttpStatusCode.BadRequest)
            return@requireInputService
        }
        call.respondText(svc.copyFile(src, dest).toString(), ContentType.Application.Json)
    }}

    post("/files/upload") { requireInputService { svc ->
        val json = JSONObject(call.receiveText())
        val path = json.optString("path", "")
        val data = json.optString("data", "")
        if (path.isEmpty() || data.isEmpty()) {
            call.respondText(jsonError("Missing path or data"), ContentType.Application.Json, HttpStatusCode.BadRequest)
            return@requireInputService
        }
        val bytes = android.util.Base64.decode(data, android.util.Base64.DEFAULT)
        call.respondText(svc.uploadFile(path, bytes).toString(), ContentType.Application.Json)
    }}

    // ==================== Semantic Automation Demo ====================

    // Proof-of-concept: open calculator → find button via View tree → click it
    post("/demo/semantic") { requireInputService { svc ->
        val json = runCatching { JSONObject(call.receiveText()) }.getOrElse { JSONObject() }
        val target = json.optString("target", "5")
        call.respondText(svc.runSemanticDemo(target).toString(), ContentType.Application.Json)
    }}

    // Cross-screen demo: Settings → WiFi → Toggle switch
    post("/demo/wifi") { requireInputService { svc ->
        call.respondText(svc.runWifiToggleDemo().toString(), ContentType.Application.Json)
    }}

    // Natural language command: user describes intent, system executes
    post("/command") { requireInputService { svc ->
        val json = runCatching { JSONObject(call.receiveText()) }.getOrElse { JSONObject() }
        val command = json.optString("command", "").trim()
        if (command.isEmpty()) {
            call.respondText(JSONObject().put("ok", false).put("error", "Empty command").toString(), ContentType.Application.Json)
        } else {
            call.respondText(svc.executeNaturalCommand(command).toString(), ContentType.Application.Json)
        }
    }}

    // Compound command with SSE streaming — real-time step-by-step feedback
    post("/command/stream") { requireInputService { svc ->
        val json = runCatching { JSONObject(call.receiveText()) }.getOrElse { JSONObject() }
        val command = json.optString("command", "").trim()
        if (command.isEmpty()) {
            call.respondText(JSONObject().put("ok", false).put("error", "Empty command").toString(), ContentType.Application.Json)
        } else {
            call.respondTextWriter(contentType = ContentType.Text.EventStream) {
                write("data: ${JSONObject().put("type", "start").put("command", command)}\n\n")
                flush()
                svc.executeCompoundCommand(command) { step ->
                    write("data: $step\n\n")
                    flush()
                }
                write("data: [DONE]\n\n")
                flush()
            }
        }
    }}

    // ==================== Platform Layer: APP Orchestration ====================

    // Generic Intent - launch ANY app/action/deep link
    post("/intent") { requireInputService { svc ->
        val body = call.receiveText()
        val params = JSONObject(body)
        call.respondText(svc.sendIntent(params).toString(), ContentType.Application.Json)
    }}

    // Extract ALL visible text from current screen
    get("/screen/text") { requireInputService { svc ->
        call.respondText(svc.extractScreenText().toString(), ContentType.Application.Json)
    }}

    // Wait for text to appear on screen (workflow chaining)
    get("/wait") { requireInputService { svc ->
        val text = call.request.queryParameters["text"] ?: ""
        val timeout = call.request.queryParameters["timeout"]?.toLongOrNull() ?: 10000L
        val interval = call.request.queryParameters["interval"]?.toLongOrNull() ?: 500L
        if (text.isEmpty()) {
            call.respondText(JSONObject().put("ok", false).put("error", "text parameter required").toString(), ContentType.Application.Json)
        } else {
            call.respondText(svc.waitForCondition(text, timeout, interval).toString(), ContentType.Application.Json)
        }
    }}

    // Read captured notifications
    get("/notifications/read") { requireInputService { svc ->
        val limit = call.request.queryParameters["limit"]?.toIntOrNull() ?: 20
        call.respondText(svc.getNotifications(limit).toString(), ContentType.Application.Json)
    }}

    // ==================== Macro Triggers ====================

    // List all configured triggers
    get("/macro/triggers") {
        call.respondText(
            MacroEngine.instance.listTriggers().toString(),
            ContentType.Application.Json
        )
    }

    // Set trigger for a macro
    post("/macro/trigger/{id}") {
        val id = call.parameters["id"] ?: run {
            call.respondText(jsonError("Missing macro id"), ContentType.Application.Json, HttpStatusCode.BadRequest)
            return@post
        }
        val trigger = JSONObject(call.receiveText())
        val ok = MacroEngine.instance.setTrigger(id, trigger)
        if (ok) {
            call.respondText(jsonOk(), ContentType.Application.Json)
        } else {
            call.respondText(jsonError("Macro not found: $id"), ContentType.Application.Json, HttpStatusCode.NotFound)
        }
    }

    // Remove trigger from a macro
    post("/macro/trigger/{id}/remove") {
        val id = call.parameters["id"] ?: run {
            call.respondText(jsonError("Missing macro id"), ContentType.Application.Json, HttpStatusCode.BadRequest)
            return@post
        }
        val ok = MacroEngine.instance.removeTrigger(id)
        if (ok) {
            call.respondText(jsonOk(), ContentType.Application.Json)
        } else {
            call.respondText(jsonError("Macro not found: $id"), ContentType.Application.Json, HttpStatusCode.NotFound)
        }
    }

    // ==================== WebSocket ====================

    // WebSocket real-time touch stream for 1:1 mirroring
    webSocket("/ws/touch") {
        val svc = InputService.instance
        if (svc == null) {
            close(CloseReason(CloseReason.Codes.CANNOT_ACCEPT, "InputService not connected"))
            return@webSocket
        }
        try {
            for (frame in incoming) {
                frame as? Frame.Text ?: continue
                val json = runCatching { JSONObject(frame.readText()) }.getOrNull() ?: continue
                val nx = json.optDouble("nx", -1.0).toFloat()
                val ny = json.optDouble("ny", -1.0).toFloat()
                if (nx < 0 || ny < 0) continue
                when (json.optString("t")) {
                    "s" -> svc.onTouchStreamStart(nx, ny)
                    "m" -> svc.onTouchStreamMove(nx, ny)
                    "e" -> svc.onTouchStreamEnd(nx, ny)
                }
            }
        } catch (_: ClosedReceiveChannelException) {
        } catch (_: Exception) {
        }
    }
}
