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

private fun execShell(vararg cmd: String): String {
    val process = Runtime.getRuntime().exec(cmd)
    val completed = process.waitFor(10, java.util.concurrent.TimeUnit.SECONDS)
    val output = if (completed) process.inputStream.bufferedReader().readText() else ""
    if (!completed) process.destroyForcibly()
    else process.destroy()
    return output
}

private fun detectA11yMethod(): String {
    return try {
        val process = Runtime.getRuntime().exec(arrayOf("su", "-c", "id"))
        val ok = process.waitFor() == 0
        process.destroy()
        if (ok) "root" else "manual"
    } catch (_: Exception) {
        "manual"
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
        if (json.has("keysym")) {
            svc.onKeyEvent(
                json.optBoolean("down", true), json.getLong("keysym"),
                json.optBoolean("shift", false), json.optBoolean("ctrl", false)
            )
        } else if (json.has("keycode")) {
            val keycode = json.getInt("keycode")
            execShell("input", "keyevent", keycode.toString())
        } else {
            call.respondText(jsonError("Provide 'keysym' or 'keycode'"), ContentType.Application.Json, HttpStatusCode.BadRequest)
            return@requireInputService
        }
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
        val limit = call.request.queryParameters["limit"]?.toIntOrNull() ?: 200
        val offset = call.request.queryParameters["offset"]?.toIntOrNull() ?: 0
        val filter = call.request.queryParameters["filter"] ?: ""
        val allApps = svc.getInstalledApps()
        val filtered = if (filter.isEmpty()) allApps else {
            val result = org.json.JSONArray()
            for (i in 0 until allApps.length()) {
                val app = allApps.getJSONObject(i)
                val label = app.optString("label", "") + app.optString("packageName", "")
                if (label.contains(filter, ignoreCase = true)) result.put(app)
            }
            result
        }
        val total = filtered.length()
        val page = org.json.JSONArray()
        val end = minOf(offset + limit, total)
        for (i in offset until end) page.put(filtered.get(i))
        call.respondText(
            JSONObject().put("apps", page).put("total", total).put("offset", offset).put("limit", limit).toString(),
            ContentType.Application.Json
        )
    }}

    get("/clipboard") { requireInputService { svc ->
        val text = svc.getClipboardText()
        call.respondText(
            JSONObject().put("text", text ?: JSONObject.NULL).toString(),
            ContentType.Application.Json
        )
    }}

    post("/clipboard") { requireInputService { svc ->
        val json = JSONObject(call.receiveText())
        val text = json.getString("text")
        svc.setClipboard(text)
        call.respondText(
            JSONObject().put("ok", true).put("length", text.length).toString(),
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

    // ==================== Smart Home ====================

    // Smart Home Gateway proxy — forwards to local gateway (port 8900) or direct HA
    // Configuration: set HA URL via /smarthome/config
    val smarthomeGatewayUrl = System.getProperty("smarthome.gateway") ?: "http://127.0.0.1:8900"
    val smarthomeHaUrl = System.getProperty("smarthome.ha_url") ?: "http://192.168.31.228:8123"
    val smarthomeHaToken = System.getProperty("smarthome.ha_token") ?: ""

    // GET /smarthome/status — check gateway & HA connectivity
    get("/smarthome/status") {
        val result = JSONObject()
        result.put("gateway_url", smarthomeGatewayUrl)
        result.put("ha_url", smarthomeHaUrl)
        result.put("ha_configured", smarthomeHaToken.isNotEmpty())
        // Try to reach gateway
        try {
            val url = java.net.URL("$smarthomeGatewayUrl/")
            val conn = url.openConnection() as java.net.HttpURLConnection
            conn.connectTimeout = 3000
            conn.readTimeout = 3000
            conn.requestMethod = "GET"
            val code = conn.responseCode
            result.put("gateway_reachable", code == 200)
            if (code == 200) {
                val body = conn.inputStream.bufferedReader().readText()
                result.put("gateway_info", JSONObject(body))
            }
            conn.disconnect()
        } catch (e: Exception) {
            result.put("gateway_reachable", false)
            result.put("gateway_error", e.message ?: "")
        }
        call.respondText(result.toString(), ContentType.Application.Json)
    }

    // GET /smarthome/devices — list all smart home devices
    get("/smarthome/devices") {
        val domain = call.parameters["domain"]
        try {
            val urlStr = if (domain != null) "$smarthomeGatewayUrl/devices?domain=$domain"
                         else "$smarthomeGatewayUrl/devices"
            val url = java.net.URL(urlStr)
            val conn = url.openConnection() as java.net.HttpURLConnection
            conn.connectTimeout = 5000
            conn.readTimeout = 5000
            val body = conn.inputStream.bufferedReader().readText()
            conn.disconnect()
            call.respondText(body, ContentType.Application.Json)
        } catch (e: Exception) {
            call.respondText("{\"count\":0,\"devices\":[],\"gateway_offline\":true,\"error\":\"${e.message?.replace("\"", "'") ?: ""}\"}", ContentType.Application.Json)
        }
    }

    // GET /smarthome/devices/{id} — get single device state
    get("/smarthome/devices/{id}") {
        val id = call.parameters["id"] ?: run {
            call.respondText(jsonError("Missing device id"), ContentType.Application.Json, HttpStatusCode.BadRequest)
            return@get
        }
        try {
            val url = java.net.URL("$smarthomeGatewayUrl/devices/$id")
            val conn = url.openConnection() as java.net.HttpURLConnection
            conn.connectTimeout = 5000
            conn.readTimeout = 5000
            val body = conn.inputStream.bufferedReader().readText()
            conn.disconnect()
            call.respondText(body, ContentType.Application.Json)
        } catch (e: Exception) {
            call.respondText("{\"error\":\"Gateway offline\",\"gateway_offline\":true}", ContentType.Application.Json)
        }
    }

    // POST /smarthome/control — control a device via gateway
    post("/smarthome/control") {
        try {
            val reqBody = call.receiveText()
            val json = JSONObject(reqBody)
            val entityId = json.getString("entity_id")
            val action = json.getString("action")
            val value = json.opt("value")
            val extra = json.optJSONObject("extra")

            val payload = JSONObject()
            payload.put("action", action)
            if (value != null) payload.put("value", value)
            if (extra != null) payload.put("extra", extra)

            val url = java.net.URL("$smarthomeGatewayUrl/devices/$entityId/control")
            val conn = url.openConnection() as java.net.HttpURLConnection
            conn.requestMethod = "POST"
            conn.setRequestProperty("Content-Type", "application/json")
            conn.doOutput = true
            conn.connectTimeout = 5000
            conn.readTimeout = 5000
            conn.outputStream.write(payload.toString().toByteArray())
            val body = conn.inputStream.bufferedReader().readText()
            conn.disconnect()
            call.respondText(body, ContentType.Application.Json)
        } catch (e: Exception) {
            call.respondText(jsonError("Smart home control error: ${e.message}"), ContentType.Application.Json, HttpStatusCode.BadRequest)
        }
    }

    // POST /smarthome/control/direct — control device directly via HA REST API (no gateway needed)
    post("/smarthome/control/direct") {
        if (smarthomeHaToken.isEmpty()) {
            call.respondText(jsonError("HA token not configured"), ContentType.Application.Json, HttpStatusCode.ServiceUnavailable)
            return@post
        }
        try {
            val reqBody = call.receiveText()
            val json = JSONObject(reqBody)
            val entityId = json.getString("entity_id")
            val action = json.optString("action", "toggle")
            val domain = entityId.split(".")[0]

            val haPayload = JSONObject()
            haPayload.put("entity_id", entityId)
            // Pass through extra fields like brightness, temperature, etc.
            for (key in json.keys()) {
                if (key !in listOf("entity_id", "action")) {
                    haPayload.put(key, json.get(key))
                }
            }

            val url = java.net.URL("$smarthomeHaUrl/api/services/$domain/$action")
            val conn = url.openConnection() as java.net.HttpURLConnection
            conn.requestMethod = "POST"
            conn.setRequestProperty("Content-Type", "application/json")
            conn.setRequestProperty("Authorization", "Bearer $smarthomeHaToken")
            conn.doOutput = true
            conn.connectTimeout = 5000
            conn.readTimeout = 5000
            conn.outputStream.write(haPayload.toString().toByteArray())
            val code = conn.responseCode
            val body = if (code in 200..299) conn.inputStream.bufferedReader().readText()
                       else conn.errorStream?.bufferedReader()?.readText() ?: ""
            conn.disconnect()
            val result = JSONObject()
            result.put("ok", code in 200..299)
            result.put("status", code)
            result.put("entity_id", entityId)
            result.put("action", action)
            call.respondText(result.toString(), ContentType.Application.Json,
                if (code in 200..299) HttpStatusCode.OK else HttpStatusCode.fromValue(code))
        } catch (e: Exception) {
            call.respondText(jsonError("HA direct control error: ${e.message}"), ContentType.Application.Json, HttpStatusCode.BadRequest)
        }
    }

    // GET /smarthome/scenes — list scenes via gateway
    get("/smarthome/scenes") {
        try {
            val url = java.net.URL("$smarthomeGatewayUrl/scenes")
            val conn = url.openConnection() as java.net.HttpURLConnection
            conn.connectTimeout = 5000
            conn.readTimeout = 5000
            val body = conn.inputStream.bufferedReader().readText()
            conn.disconnect()
            call.respondText(body, ContentType.Application.Json)
        } catch (e: Exception) {
            call.respondText("{\"count\":0,\"scenes\":[],\"gateway_offline\":true}", ContentType.Application.Json)
        }
    }

    // POST /smarthome/scenes/{id}/activate — trigger a scene
    post("/smarthome/scenes/{id}/activate") {
        val id = call.parameters["id"] ?: run {
            call.respondText(jsonError("Missing scene id"), ContentType.Application.Json, HttpStatusCode.BadRequest)
            return@post
        }
        try {
            val url = java.net.URL("$smarthomeGatewayUrl/scenes/$id/activate")
            val conn = url.openConnection() as java.net.HttpURLConnection
            conn.requestMethod = "POST"
            conn.setRequestProperty("Content-Type", "application/json")
            conn.doOutput = true
            conn.connectTimeout = 5000
            conn.readTimeout = 5000
            conn.outputStream.write("{}".toByteArray())
            val body = conn.inputStream.bufferedReader().readText()
            conn.disconnect()
            call.respondText(body, ContentType.Application.Json)
        } catch (e: Exception) {
            call.respondText(jsonError("Scene activate error: ${e.message}"), ContentType.Application.Json, HttpStatusCode.BadRequest)
        }
    }

    // POST /smarthome/quick/{action} — quick actions: all_off, lights_off, etc.
    post("/smarthome/quick/{action}") {
        val action = call.parameters["action"] ?: run {
            call.respondText(jsonError("Missing action"), ContentType.Application.Json, HttpStatusCode.BadRequest)
            return@post
        }
        try {
            val url = java.net.URL("$smarthomeGatewayUrl/quick/$action")
            val conn = url.openConnection() as java.net.HttpURLConnection
            conn.requestMethod = "POST"
            conn.setRequestProperty("Content-Type", "application/json")
            conn.doOutput = true
            conn.connectTimeout = 10000
            conn.readTimeout = 10000
            conn.outputStream.write("{}".toByteArray())
            val body = conn.inputStream.bufferedReader().readText()
            conn.disconnect()
            call.respondText(body, ContentType.Application.Json)
        } catch (e: Exception) {
            call.respondText(jsonError("Quick action error: ${e.message}"), ContentType.Application.Json, HttpStatusCode.BadRequest)
        }
    }

    // ==================== Accessibility ====================

    get("/a11y/status") {
        val svc = InputService.instance
        val json = JSONObject().apply {
            put("connected", svc != null)
            put("enabled", InputService.isConnected())
            put("method_available", detectA11yMethod())
        }
        call.respondText(json.toString(), ContentType.Application.Json)
    }

    post("/a11y/enable") {
        try {
            val pkg = call.application.environment.config.propertyOrNull("ktor.application.id")?.getString()
                ?: "info.dvkr.screenstream.dev"
            val component = "$pkg/info.dvkr.screenstream.input.InputService"

            val current = execShell("su", "-c", "settings get secure enabled_accessibility_services").trim()
            if (component in current) {
                call.respondText(
                    JSONObject().put("ok", true).put("message", "Already enabled").toString(),
                    ContentType.Application.Json
                )
                return@post
            }

            val newValue = if (current == "null" || current.isBlank()) component else "$current:$component"
            execShell("su", "-c", "settings put secure enabled_accessibility_services $newValue")
            execShell("su", "-c", "settings put secure accessibility_enabled 1")

            val verify = execShell("su", "-c", "settings get secure enabled_accessibility_services").trim()
            val success = component in verify
            call.respondText(
                JSONObject().put("ok", success).put("method", "root").put("message", if (success) "Enabled via root" else "Enable failed").toString(),
                ContentType.Application.Json
            )
        } catch (e: Exception) {
            call.respondText(jsonError("A11y enable error: ${e.message}"), ContentType.Application.Json, HttpStatusCode.InternalServerError)
        }
    }

    // ==================== Agent Streaming Control ====================

    get("/stream/status") {
        try {
            val bridge = Class.forName("info.dvkr.screenstream.common.AgentBridge")
            val getStatus = bridge.getMethod("getStreamingStatus")
            val status = getStatus.invoke(null)
            call.respondText(status.toString(), ContentType.Application.Json)
        } catch (e: Exception) {
            call.respondText(
                JSONObject().put("error", "AgentBridge not available: ${e.message}").toString(),
                ContentType.Application.Json, HttpStatusCode.InternalServerError
            )
        }
    }

    post("/stream/start") {
        try {
            val bridge = Class.forName("info.dvkr.screenstream.common.AgentBridge")
            val hasIntent = bridge.getMethod("hasProjectionIntent").invoke(null) as Boolean
            val status = bridge.getMethod("getStreamingStatus").invoke(null) as JSONObject
            val isStreaming = status.optBoolean("isStreaming", false)

            if (isStreaming) {
                call.respondText(
                    JSONObject().put("ok", true).put("action", "already_streaming").put("status", status).toString(),
                    ContentType.Application.Json
                )
                return@post
            }

            if (!hasIntent) {
                val pkg = InputService.instance?.packageName ?: "info.dvkr.screenstream.dev"
                call.respondText(
                    JSONObject()
                        .put("ok", false)
                        .put("action", "no_projection_intent")
                        .put("message", "MediaProjection not yet granted. Run once via ADB then /stream/start works automatically.")
                        .put("adb_command", "adb shell am start -n $pkg/info.dvkr.screenstream.AgentProjectionActivity")
                        .toString(),
                    ContentType.Application.Json, HttpStatusCode.BadRequest
                )
                return@post
            }

            // Use AgentBridge.startStream — handles main-thread dispatch + reflection internally
            val latch = java.util.concurrent.CountDownLatch(1)
            var resultOk = false
            var resultMsg = ""
            val startStream = bridge.getMethod("startStream", Function2::class.java)
            val callback = { ok: Boolean, msg: String ->
                resultOk = ok; resultMsg = msg; latch.countDown()
            }
            startStream.invoke(null, callback)
            latch.await(11, java.util.concurrent.TimeUnit.SECONDS)
            if (resultMsg.isEmpty()) resultMsg = "Timeout: no response from startStream after 11s"
            call.respondText(
                JSONObject().put("ok", resultOk).put("action", if (resultOk) "stream_started" else "failed").put("message", resultMsg).toString(),
                ContentType.Application.Json, if (resultOk) HttpStatusCode.OK else HttpStatusCode.InternalServerError
            )
        } catch (e: Exception) {
            call.respondText(jsonError("Start stream failed: ${e.message}"), ContentType.Application.Json, HttpStatusCode.InternalServerError)
        }
    }

    post("/stream/stop") {
        try {
            val bridge = Class.forName("info.dvkr.screenstream.common.AgentBridge")
            val stopStream = bridge.getMethod("stopStream", Function2::class.java)
            stopStream.invoke(null, null)
            call.respondText(
                JSONObject().put("ok", true).put("action", "stop_stream").toString(),
                ContentType.Application.Json
            )
        } catch (e: Exception) {
            call.respondText(jsonError("Stop stream failed: ${e.message}"), ContentType.Application.Json, HttpStatusCode.InternalServerError)
        }
    }

    get("/agent/status") {
        try {
            val bridge = Class.forName("info.dvkr.screenstream.common.AgentBridge")
            val svc = InputService.instance
            val streaming = bridge.getMethod("getStreamingStatus").invoke(null) as JSONObject
            val result = JSONObject()
            result.put("streaming", streaming)
            result.put("inputService", JSONObject().apply {
                put("connected", svc != null)
                put("inputEnabled", InputService.isInputEnabled)
                put("scaling", InputService.scaling.toDouble())
            })
            result.put("timestamp", System.currentTimeMillis())
            call.respondText(result.toString(), ContentType.Application.Json)
        } catch (e: Exception) {
            call.respondText(jsonError("Agent status error: ${e.message}"), ContentType.Application.Json, HttpStatusCode.InternalServerError)
        }
    }

    get("/health") {
        val svc = InputService.instance
        call.respondText(
            JSONObject().apply {
                put("ok", true)
                put("inputService", svc != null)
                put("uptime", android.os.SystemClock.elapsedRealtime())
                try {
                    val bridge = Class.forName("info.dvkr.screenstream.common.AgentBridge")
                    val status = bridge.getMethod("getStreamingStatus").invoke(null) as JSONObject
                    put("isStreaming", status.optBoolean("isStreaming", false))
                    put("moduleActive", status.optBoolean("moduleActive", false))
                } catch (_: Exception) {
                    put("isStreaming", false)
                    put("moduleActive", false)
                }
            }.toString(),
            ContentType.Application.Json
        )
    }

    // ==================== Settings API ====================

    get("/settings") {
        try {
            val result = JSONObject()
            // Input settings
            result.put("input", JSONObject().apply {
                put("connected", InputService.isConnected())
                put("inputEnabled", InputService.isInputEnabled)
                put("scaling", InputService.scaling.toDouble())
                put("screenOffMode", InputService.isScreenOffMode)
            })
            // MJPEG/Streaming settings via reflection (avoids circular module dependency)
            try {
                val koin = org.koin.core.context.GlobalContext.getOrNull()
                if (koin != null) {
                    val settingsClass = Class.forName("info.dvkr.screenstream.mjpeg.settings.MjpegSettings")
                    val settingsObj = koin.get<Any>(settingsClass.kotlin)
                    val dataFlow = settingsClass.getMethod("getData").invoke(settingsObj)
                    val dataValue = dataFlow.javaClass.getMethod("getValue").invoke(dataFlow)
                    val streaming = JSONObject()
                    for (field in listOf("streamCodec", "vrMode", "vrIpd", "jpegQuality", "resizeFactor",
                        "maxFPS", "rotation", "keepAwake", "stopOnSleep", "resolutionWidth", "resolutionHeight",
                        "resolutionStretch", "imageCrop", "imageGrayscale", "serverPort", "htmlEnableButtons", "htmlFitWindow")) {
                        try {
                            val getter = dataValue.javaClass.getMethod("get${field.replaceFirstChar { it.uppercase() }}")
                            streaming.put(field, getter.invoke(dataValue))
                        } catch (_: Exception) {}
                    }
                    val codec = streaming.optInt("streamCodec", 0)
                    streaming.put("streamCodecName", when (codec) { 1 -> "H264"; 2 -> "H265"; else -> "MJPEG" })
                    val vr = streaming.optInt("vrMode", 0)
                    streaming.put("vrModeName", when (vr) { 1 -> "left"; 2 -> "right"; 3 -> "stereo"; else -> "disabled" })
                    result.put("streaming", streaming)
                }
            } catch (e: Exception) {
                result.put("streaming_error", e.message ?: "MjpegSettings not available")
            }
            call.respondText(result.toString(), ContentType.Application.Json)
        } catch (e: Exception) {
            call.respondText(jsonError("Settings read error: ${e.message}"), ContentType.Application.Json, HttpStatusCode.InternalServerError)
        }
    }

    post("/settings") {
        try {
            val json = JSONObject(call.receiveText())
            val updated = mutableListOf<String>()
            if (json.has("inputEnabled")) {
                InputService.isInputEnabled = json.getBoolean("inputEnabled")
                updated.add("inputEnabled")
            }
            if (json.has("scaling")) {
                InputService.scaling = json.getDouble("scaling").toFloat()
                updated.add("scaling")
            }
            call.respondText(
                JSONObject().put("ok", true).put("updated", org.json.JSONArray(updated)).toString(),
                ContentType.Application.Json
            )
        } catch (e: Exception) {
            call.respondText(jsonError("Settings update error: ${e.message}"), ContentType.Application.Json, HttpStatusCode.InternalServerError)
        }
    }

    // ==================== On-Device Shell (Quest 3 Self-Sufficient — No PC/ADB Needed) ====================

    post("/shell") {
        val json = JSONObject(call.receiveText())
        val cmd = json.optString("command", "")
        if (cmd.isEmpty()) {
            call.respondText(jsonError("Empty command"), ContentType.Application.Json, HttpStatusCode.BadRequest)
            return@post
        }
        val timeoutMs = json.optLong("timeout", 15000)
        try {
            val process = ProcessBuilder("sh", "-c", cmd)
                .redirectErrorStream(false)
                .start()
            val stdout = process.inputStream.bufferedReader()
            val stderr = process.errorStream.bufferedReader()
            val completed = process.waitFor(timeoutMs, java.util.concurrent.TimeUnit.MILLISECONDS)
            val out = stdout.readText()
            val err = stderr.readText()
            val rc = if (completed) process.exitValue() else -1
            if (!completed) process.destroyForcibly()
            call.respondText(
                JSONObject()
                    .put("ok", completed && rc == 0)
                    .put("stdout", out.take(65536))
                    .put("stderr", err.take(8192))
                    .put("rc", rc)
                    .put("timeout", !completed)
                    .toString(),
                ContentType.Application.Json
            )
        } catch (e: Exception) {
            call.respondText(jsonError("Shell error: ${e.message}"), ContentType.Application.Json, HttpStatusCode.InternalServerError)
        }
    }

    // ==================== System Deep Sensing ====================

    get("/system/info") {
        val json = JSONObject()
        // Battery via sys filesystem (no Context needed)
        try {
            val level = execShell("sh", "-c", "cat /sys/class/power_supply/battery/capacity 2>/dev/null || cat /sys/class/power_supply/Battery/capacity 2>/dev/null").trim()
            val status = execShell("sh", "-c", "cat /sys/class/power_supply/battery/status 2>/dev/null || cat /sys/class/power_supply/Battery/status 2>/dev/null").trim()
            val temp = execShell("sh", "-c", "cat /sys/class/power_supply/battery/temp 2>/dev/null || cat /sys/class/power_supply/Battery/temp 2>/dev/null").trim()
            if (level.isNotEmpty()) {
                json.put("battery", JSONObject()
                    .put("level", level.toIntOrNull() ?: 0)
                    .put("charging", status.lowercase() in listOf("charging", "full"))
                    .put("temperature", (temp.toIntOrNull() ?: 0) / 10)
                )
            }
        } catch (_: Exception) {}
        // Memory via /proc/meminfo
        try {
            val memRaw = execShell("sh", "-c", "cat /proc/meminfo | head -6").trim()
            val totalKb = Regex("MemTotal:\\s+(\\d+)").find(memRaw)?.groupValues?.get(1)?.toLongOrNull()
            val availKb = Regex("MemAvailable:\\s+(\\d+)").find(memRaw)?.groupValues?.get(1)?.toLongOrNull()
            if (totalKb != null && availKb != null) {
                json.put("memory", JSONObject()
                    .put("totalMB", totalKb / 1024)
                    .put("availMB", availKb / 1024)
                    .put("usedMB", (totalKb - availKb) / 1024)
                    .put("lowMemory", availKb < 200 * 1024)
                    .put("threshold", 216)
                )
            }
        } catch (_: Exception) {}
        try { json.put("meminfo", execShell("sh", "-c", "cat /proc/meminfo | head -10").trim()) } catch (_: Exception) {}
        // Uptime via SystemClock (no Context needed)
        try {
            val uptimeMs = android.os.SystemClock.elapsedRealtime()
            val hrs = uptimeMs / 3600000
            val mins = (uptimeMs % 3600000) / 60000
            json.put("uptime", "${hrs}h ${mins}m")
            json.put("uptimeMs", uptimeMs)
        } catch (_: Exception) {}
        try { json.put("disk", execShell("sh", "-c", "df -h /data 2>/dev/null | tail -1").trim()) } catch (_: Exception) {}
        try { json.put("cpu", execShell("sh", "-c", "cat /proc/cpuinfo | grep -E 'processor|Hardware|model' | head -6").trim()) } catch (_: Exception) {}
        try { json.put("platform", android.os.Build.BOARD) } catch (_: Exception) {}
        try { json.put("cpuAbi", android.os.Build.SUPPORTED_ABIS?.joinToString(",") ?: "") } catch (_: Exception) {}
        call.respondText(json.toString(), ContentType.Application.Json)
    }

    get("/system/processes") {
        val top = call.request.queryParameters["top"]?.toIntOrNull() ?: 20
        try {
            val ps = execShell("sh", "-c", "ps -A -o PID,RSS,NAME --sort=-rss 2>/dev/null | head -${top + 1}")
            call.respondText(
                JSONObject().put("processes", ps.trim()).put("top", top).toString(),
                ContentType.Application.Json
            )
        } catch (e: Exception) {
            call.respondText(jsonError(e.message ?: ""), ContentType.Application.Json, HttpStatusCode.InternalServerError)
        }
    }

    get("/system/properties") {
        val key = call.request.queryParameters["key"]
        try {
            val props = if (key != null) {
                execShell("sh", "-c", "getprop $key")
            } else {
                execShell("sh", "-c", "getprop | head -100")
            }
            call.respondText(
                JSONObject().put("properties", props.trim()).toString(),
                ContentType.Application.Json
            )
        } catch (e: Exception) {
            call.respondText(jsonError(e.message ?: ""), ContentType.Application.Json, HttpStatusCode.InternalServerError)
        }
    }

    // ==================== VR Sensing (Quest 3 Specific) ====================

    get("/vr/status") {
        val json = JSONObject()
        // Device identity (no Context needed)
        try { json.put("platform", execShell("sh", "-c", "getprop ro.build.display.id").trim()) } catch (_: Exception) {}
        try { json.put("model", android.os.Build.MODEL) } catch (_: Exception) {}
        try { json.put("codename", android.os.Build.DEVICE) } catch (_: Exception) {}
        try { json.put("sdk", android.os.Build.VERSION.SDK_INT) } catch (_: Exception) {}
        try { json.put("android", android.os.Build.VERSION.RELEASE) } catch (_: Exception) {}
        try { json.put("gpu", execShell("sh", "-c", "getprop ro.board.platform").trim()) } catch (_: Exception) {}
        // Display via wm command (no Context needed)
        try {
            val size = execShell("sh", "-c", "wm size 2>/dev/null").trim()
            val density = execShell("sh", "-c", "wm density 2>/dev/null").trim()
            val sizeParts = size.removePrefix("Physical size:").trim().split("x")
            val w = sizeParts.getOrNull(0)?.trim()?.toIntOrNull() ?: 0
            val h = sizeParts.getOrNull(1)?.trim()?.toIntOrNull() ?: 0
            val dpi = density.removePrefix("Physical density:").trim().toIntOrNull() ?: 0
            json.put("display", JSONObject().put("widthPx", w).put("heightPx", h).put("densityDpi", dpi))
        } catch (_: Exception) {}
        try { json.put("ovr_headset", execShell("sh", "-c", "getprop ro.ovr.headset").trim()) } catch (_: Exception) {}
        try { json.put("ovr_build", execShell("sh", "-c", "getprop ro.ovr.build.display.id").trim()) } catch (_: Exception) {}
        try { json.put("hardware", android.os.Build.HARDWARE) } catch (_: Exception) {}
        try { json.put("manufacturer", android.os.Build.MANUFACTURER) } catch (_: Exception) {}
        call.respondText(json.toString(), ContentType.Application.Json)
    }

    get("/vr/services") {
        try {
            val services = execShell("sh", "-c", "dumpsys activity services 2>/dev/null | grep -i 'ServiceRecord.*\\(com\\.oculus\\|com\\.meta\\)' | head -50")
            val lines = services.trim().lines().filter { it.isNotBlank() }
            call.respondText(
                JSONObject().put("services", org.json.JSONArray(lines)).put("count", lines.size).toString(),
                ContentType.Application.Json
            )
        } catch (e: Exception) {
            call.respondText(jsonError(e.message ?: ""), ContentType.Application.Json, HttpStatusCode.InternalServerError)
        }
    }

    get("/vr/display") {
        try {
            val display = execShell("sh", "-c", "dumpsys display 2>/dev/null | grep -E 'PhysicalDisplay|mBaseDisplay|density|refreshRate|resolution' | head -15")
            call.respondText(
                JSONObject().put("display", display.trim()).toString(),
                ContentType.Application.Json
            )
        } catch (e: Exception) {
            call.respondText(jsonError(e.message ?: ""), ContentType.Application.Json, HttpStatusCode.InternalServerError)
        }
    }

    get("/vr/controllers") {
        try {
            val ctrl = execShell("sh", "-c", "dumpsys input 2>/dev/null | grep -iA5 'controller\\|touch' | head -30")
            call.respondText(
                JSONObject().put("controllers", ctrl.trim()).toString(),
                ContentType.Application.Json
            )
        } catch (e: Exception) {
            call.respondText(jsonError(e.message ?: ""), ContentType.Application.Json, HttpStatusCode.InternalServerError)
        }
    }

    // ==================== Package Management (All Packages, Not Just Launchable) ====================

    get("/packages") {
        val filter = call.request.queryParameters["filter"] ?: ""
        try {
            val cmd = if (filter.isEmpty()) "pm list packages" else "pm list packages | grep -i $filter"
            val packages = execShell("sh", "-c", cmd)
            val list = packages.trim().lines().filter { it.startsWith("package:") }.map { it.removePrefix("package:") }
            call.respondText(
                JSONObject().put("packages", org.json.JSONArray(list)).put("count", list.size).toString(),
                ContentType.Application.Json
            )
        } catch (e: Exception) {
            call.respondText(jsonError(e.message ?: ""), ContentType.Application.Json, HttpStatusCode.InternalServerError)
        }
    }

    get("/packages/{pkg}") {
        val pkg = call.parameters["pkg"] ?: run {
            call.respondText(jsonError("Missing package name"), ContentType.Application.Json, HttpStatusCode.BadRequest)
            return@get
        }
        try {
            val info = execShell("sh", "-c", "dumpsys package $pkg | head -80")
            call.respondText(
                JSONObject().put("package", pkg).put("info", info.trim()).toString(),
                ContentType.Application.Json
            )
        } catch (e: Exception) {
            call.respondText(jsonError(e.message ?: ""), ContentType.Application.Json, HttpStatusCode.InternalServerError)
        }
    }

    // ==================== CDP Browser Proxy (On-Device, No ADB Forward Needed) ====================

    get("/cdp/pages") {
        try {
            val url = java.net.URL("http://127.0.0.1:9222/json")
            val conn = url.openConnection() as java.net.HttpURLConnection
            conn.connectTimeout = 3000
            conn.readTimeout = 3000
            val body = conn.inputStream.bufferedReader().readText()
            conn.disconnect()
            call.respondText(body, ContentType.Application.Json)
        } catch (e: Exception) {
            call.respondText(
                JSONObject().put("error", "CDP not available: ${e.message}")
                    .put("hint", "Ensure a Chromium browser is running with remote debugging")
                    .toString(),
                ContentType.Application.Json, HttpStatusCode.ServiceUnavailable
            )
        }
    }

    post("/cdp/eval") {
        val json = JSONObject(call.receiveText())
        val expression = json.optString("expression", "")
        val pageIndex = json.optInt("page", 0)
        if (expression.isEmpty()) {
            call.respondText(jsonError("Empty expression"), ContentType.Application.Json, HttpStatusCode.BadRequest)
            return@post
        }
        try {
            // Get page list
            val listUrl = java.net.URL("http://127.0.0.1:9222/json")
            val listConn = listUrl.openConnection() as java.net.HttpURLConnection
            listConn.connectTimeout = 3000
            listConn.readTimeout = 3000
            val pages = org.json.JSONArray(listConn.inputStream.bufferedReader().readText())
            listConn.disconnect()
            if (pages.length() == 0) {
                call.respondText(jsonError("No browser pages found"), ContentType.Application.Json, HttpStatusCode.NotFound)
                return@post
            }
            val page = pages.getJSONObject(pageIndex.coerceIn(0, pages.length() - 1))
            val wsUrl = page.optString("webSocketDebuggerUrl", "")
            if (wsUrl.isEmpty()) {
                call.respondText(jsonError("No WebSocket URL for page"), ContentType.Application.Json, HttpStatusCode.ServiceUnavailable)
                return@post
            }
            // Use HTTP evaluate endpoint instead of WebSocket for simplicity
            val pageId = page.optString("id", "")
            val evalUrl = java.net.URL("http://127.0.0.1:9222/json/evaluate/$pageId")
            // CDP doesn't have a simple HTTP eval endpoint, so we report the WS URL for Agent to use
            call.respondText(
                JSONObject()
                    .put("page_title", page.optString("title", ""))
                    .put("page_url", page.optString("url", ""))
                    .put("ws_url", wsUrl)
                    .put("hint", "Use WebSocket CDP protocol to evaluate JS. Or use /shell with am/content commands.")
                    .toString(),
                ContentType.Application.Json
            )
        } catch (e: Exception) {
            call.respondText(jsonError("CDP eval error: ${e.message}"), ContentType.Application.Json, HttpStatusCode.InternalServerError)
        }
    }

    // ==================== Agent Digest (Minimal Tokens) ====================

    get("/digest") {
        val json = JSONObject()
        // Battery: BatteryManager API via InputService context (Quest 3 has no sysfs battery path)
        try {
            val svc = InputService.instance
            if (svc != null) {
                val bm = svc.getSystemService(android.content.Context.BATTERY_SERVICE) as android.os.BatteryManager
                json.put("bat", bm.getIntProperty(android.os.BatteryManager.BATTERY_PROPERTY_CAPACITY))
                json.put("charging", bm.isCharging)
            } else {
                val level = execShell("sh", "-c", "cat /sys/class/power_supply/battery/capacity 2>/dev/null || cat /sys/class/power_supply/Battery/capacity 2>/dev/null").trim()
                val status = execShell("sh", "-c", "cat /sys/class/power_supply/battery/status 2>/dev/null || cat /sys/class/power_supply/Battery/status 2>/dev/null").trim()
                if (level.isNotEmpty()) {
                    json.put("bat", level.toIntOrNull() ?: 0)
                    json.put("charging", status.lowercase() in listOf("charging", "full"))
                }
            }
        } catch (_: Exception) {}
        // Foreground: use InputService if connected, else shell fallback
        try {
            val svc = InputService.instance
            if (svc != null) {
                val fg = svc.getForegroundApp()
                json.put("fg", fg.optString("packageName", "").split(".").lastOrNull() ?: "")
            } else {
                val act = execShell("sh", "-c", "dumpsys activity top 2>/dev/null | grep -m1 'ACTIVITY' | awk '{print $2}'").trim()
                val pkg = if (act.contains("/")) act.split("/")[0] else act
                json.put("fg", pkg.split(".").lastOrNull() ?: "?")
            }
        } catch (_: Exception) { json.put("fg", "?") }
        json.put("input", InputService.isConnected())
        try {
            val bridge = Class.forName("info.dvkr.screenstream.common.AgentBridge")
            val status = bridge.getMethod("getStreamingStatus").invoke(null) as JSONObject
            json.put("stream", status.optBoolean("isStreaming", false))
        } catch (_: Exception) { json.put("stream", false) }
        // WiFi RSSI via shell
        try {
            val rssiLine = execShell("sh", "-c", "dumpsys wifi 2>/dev/null | grep -o 'rssi=-[0-9]*' | head -1").trim()
            if (rssiLine.contains("=")) json.put("rssi", rssiLine.split("=")[1].toIntOrNull() ?: 0)
        } catch (_: Exception) {}
        try { json.put("model", android.os.Build.MODEL) } catch (_: Exception) {}
        call.respondText(json.toString(), ContentType.Application.Json)
    }

    // ==================== Capabilities (Agent Self-Discovery) ====================

    get("/capabilities") {
        val groups = JSONObject()
        groups.put("input", org.json.JSONArray(listOf(
            "POST /tap", "POST /swipe", "POST /key", "POST /text", "POST /pointer",
            "POST /home", "POST /back", "POST /recents", "POST /notifications", "POST /quicksettings",
            "POST /volume/up", "POST /volume/down", "POST /lock"
        )))
        groups.put("system_actions", org.json.JSONArray(listOf(
            "POST /wake", "POST /power", "POST /screenshot", "POST /splitscreen",
            "POST /brightness/{level}", "GET /brightness"
        )))
        groups.put("gestures", org.json.JSONArray(listOf(
            "POST /longpress", "POST /doubletap", "POST /scroll", "POST /pinch"
        )))
        groups.put("app_device", org.json.JSONArray(listOf(
            "POST /openapp", "POST /openurl", "GET /deviceinfo", "GET /apps",
            "GET /clipboard", "POST /clipboard", "POST /killapp", "GET /foreground",
            "POST /scaling/{f}", "POST /enable/{b}", "POST /rotate/{d}",
            "POST /stayawake/{b}", "GET /stayawake", "POST /showtouches/{b}", "GET /showtouches"
        )))
        groups.put("ai_brain", org.json.JSONArray(listOf(
            "GET /viewtree", "GET /windowinfo", "POST /findclick", "POST /dismiss",
            "POST /findnodes", "POST /settext", "GET /screen/text"
        )))
        groups.put("media_hw", org.json.JSONArray(listOf(
            "POST /media/{action}", "POST /findphone/{b}", "POST /vibrate",
            "POST /flashlight/{b}", "POST /dnd/{b}", "GET /dnd", "POST /volume",
            "POST /autorotate/{b}", "GET /autorotate"
        )))
        groups.put("files", org.json.JSONArray(listOf(
            "GET /files/storage", "GET /files/list", "GET /files/info", "GET /files/read",
            "GET /files/download", "GET /files/search",
            "POST /files/mkdir", "POST /files/delete", "POST /files/rename",
            "POST /files/move", "POST /files/copy", "POST /files/upload"
        )))
        groups.put("macros", org.json.JSONArray(listOf(
            "GET /macro/list", "POST /macro/create", "POST /macro/run/{id}",
            "POST /macro/run-inline", "POST /macro/stop/{id}", "GET /macro/{id}",
            "POST /macro/update/{id}", "POST /macro/delete/{id}",
            "GET /macro/running", "GET /macro/log/{id}",
            "GET /macro/triggers", "POST /macro/trigger/{id}", "POST /macro/trigger/{id}/remove"
        )))
        groups.put("smarthome", org.json.JSONArray(listOf(
            "GET /smarthome/status", "GET /smarthome/devices", "GET /smarthome/devices/{id}",
            "POST /smarthome/control", "POST /smarthome/control/direct",
            "GET /smarthome/scenes", "POST /smarthome/scenes/{id}/activate",
            "POST /smarthome/quick/{action}"
        )))
        groups.put("platform", org.json.JSONArray(listOf(
            "POST /command", "POST /command/stream", "POST /intent",
            "GET /wait", "GET /notifications/read"
        )))
        groups.put("streaming", org.json.JSONArray(listOf(
            "GET /stream/status", "POST /stream/start", "POST /stream/stop",
            "GET /agent/status", "GET /health", "GET /settings", "POST /settings"
        )))
        groups.put("shell_system", org.json.JSONArray(listOf(
            "POST /shell", "GET /system/info", "GET /system/processes", "GET /system/properties"
        )))
        groups.put("vr", org.json.JSONArray(listOf(
            "GET /vr/status", "GET /vr/services", "GET /vr/display", "GET /vr/controllers"
        )))
        groups.put("packages", org.json.JSONArray(listOf(
            "GET /packages", "GET /packages/{pkg}"
        )))
        groups.put("cdp", org.json.JSONArray(listOf(
            "GET /cdp/pages", "POST /cdp/eval"
        )))
        groups.put("meta", org.json.JSONArray(listOf(
            "GET /digest", "GET /capabilities", "GET /a11y/status", "POST /a11y/enable"
        )))
        groups.put("websocket", org.json.JSONArray(listOf("WS /ws/touch")))
        var total = 0
        for (key in groups.keys()) {
            total += groups.getJSONArray(key).length()
        }
        call.respondText(
            JSONObject()
                .put("version", "v33-quest3-supreme")
                .put("total_endpoints", total)
                .put("groups", groups)
                .put("port", 8084)
                .put("auth", "Bearer token via Authorization header or ?token= query param")
                .toString(),
            ContentType.Application.Json
        )
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
