package info.dvkr.screenstream.input

import android.content.Context
import android.util.Log
import kotlinx.coroutines.*
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.UUID
import java.util.concurrent.ConcurrentHashMap

/**
 * MacroEngine - Phase 2 自动化宏系统引擎
 *
 * 支持创建、存储和执行由多个步骤组成的宏（自动化序列）。
 * 每个步骤可以是 API 调用（直接映射 InputService 方法）或等待延迟。
 *
 * 宏定义格式（JSON）:
 * {
 *   "name": "自动回复微信",
 *   "actions": [
 *     { "type": "api", "endpoint": "/findclick", "params": { "text": "消息" } },
 *     { "type": "wait", "ms": 500 },
 *     { "type": "api", "endpoint": "/settext", "params": { "search": "", "value": "收到" } }
 *   ],
 *   "loop": false,
 *   "loopCount": 1
 * }
 */
public class MacroEngine private constructor() {

    public companion object {
        private const val TAG = "MacroEngine"
        public val instance: MacroEngine = MacroEngine()
    }

    private val macros = ConcurrentHashMap<String, JSONObject>()
    private val runningJobs = ConcurrentHashMap<String, Job>()
    private val executionLogs = ConcurrentHashMap<String, JSONArray>()
    private val scope = CoroutineScope(Dispatchers.Default + SupervisorJob())
    private var storageFile: File? = null

    /**
     * Initialize persistence. Call from InputService.onServiceConnected().
     * Loads previously saved macros from disk.
     */
    public fun init(context: Context) {
        storageFile = File(context.filesDir, "macros.json")
        loadFromDisk()
    }

    private fun saveToDisk() {
        val file = storageFile ?: return
        try {
            val arr = JSONArray()
            for (entry in macros) {
                arr.put(entry.value)
            }
            val tmp = File(file.parent, "macros.json.tmp")
            tmp.writeText(arr.toString(2), Charsets.UTF_8)
            tmp.renameTo(file)
            Log.d(TAG, "Saved ${macros.size} macros to disk")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to save macros: ${e.message}")
        }
    }

    private fun loadFromDisk() {
        val file = storageFile ?: return
        if (!file.exists()) return
        try {
            val text = file.readText(Charsets.UTF_8)
            val arr = JSONArray(text)
            var loaded = 0
            for (i in 0 until arr.length()) {
                val obj = arr.getJSONObject(i)
                val id = obj.optString("id", "")
                if (id.isEmpty()) continue
                macros[id] = obj
                loaded++
            }
            Log.i(TAG, "Loaded $loaded macros from disk")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to load macros: ${e.message}")
        }
    }

    // ==================== CRUD ====================

    public fun createMacro(definition: JSONObject): String {
        val id = definition.optString("id", "").ifEmpty { UUID.randomUUID().toString().take(8) }
        definition.put("id", id)
        if (!definition.has("enabled")) definition.put("enabled", true)
        definition.put("createdAt", System.currentTimeMillis())
        macros[id] = definition
        saveToDisk()
        Log.i(TAG, "Created macro: $id - ${definition.optString("name", "unnamed")}")
        return id
    }

    public fun listMacros(): JSONArray {
        val arr = JSONArray()
        for (entry in macros) {
            val summary = JSONObject()
            val macro = entry.value
            summary.put("id", entry.key)
            summary.put("name", macro.optString("name", "unnamed"))
            summary.put("enabled", macro.optBoolean("enabled", true))
            summary.put("stepsCount", (macro.optJSONArray("actions") ?: macro.optJSONArray("steps"))?.length() ?: 0)
            summary.put("running", runningJobs.containsKey(entry.key))
            arr.put(summary)
        }
        return arr
    }

    public fun getMacro(id: String): JSONObject? = macros[id]

    public fun updateMacro(id: String, definition: JSONObject): Boolean {
        if (!macros.containsKey(id)) return false
        definition.put("id", id)
        definition.put("updatedAt", System.currentTimeMillis())
        macros[id] = definition
        saveToDisk()
        return true
    }

    public fun deleteMacro(id: String): Boolean {
        stopMacro(id)
        val removed = macros.remove(id) != null
        if (removed) saveToDisk()
        return removed
    }

    // ==================== Execution ====================

    public fun runMacro(id: String, service: InputService): JSONObject {
        val macro = macros[id] ?: return JSONObject().put("ok", false).put("error", "Macro not found: $id")
        if (!macro.optBoolean("enabled", true)) {
            return JSONObject().put("ok", false).put("error", "Macro disabled: $id")
        }
        if (runningJobs.containsKey(id)) {
            return JSONObject().put("ok", false).put("error", "Macro already running: $id")
        }

        val steps = macro.optJSONArray("actions") ?: macro.optJSONArray("steps")
            ?: return JSONObject().put("ok", false).put("error", "No actions defined")

        val loop = macro.optBoolean("loop", false)
        val loopCount = macro.optInt("loopCount", 1).coerceIn(1, 10000)
        val logs = JSONArray()
        executionLogs[id] = logs

        val job = scope.launch {
            try {
                val iterations = if (loop) loopCount else 1
                repeat(iterations) { iteration ->
                    for (i in 0 until steps.length()) {
                        if (!isActive) break
                        val step = steps.getJSONObject(i)
                        val startMs = System.currentTimeMillis()
                        val result = executeStep(step, service)
                        val elapsed = System.currentTimeMillis() - startMs
                        logs.put(JSONObject().apply {
                            put("iteration", iteration + 1)
                            put("step", i + 1)
                            put("type", step.optString("type", "api"))
                            put("endpoint", step.optString("endpoint", ""))
                            put("elapsed", elapsed)
                            put("result", result)
                        })
                    }
                }
                Log.i(TAG, "Macro '$id' completed (${logs.length()} steps)")
            } catch (e: CancellationException) {
                Log.i(TAG, "Macro '$id' cancelled")
                logs.put(JSONObject().put("cancelled", true))
            } catch (e: Exception) {
                Log.e(TAG, "Macro '$id' failed: ${e.message}")
                logs.put(JSONObject().put("error", e.message ?: "unknown"))
            } finally {
                runningJobs.remove(id)
            }
        }
        runningJobs[id] = job
        return JSONObject().put("ok", true).put("macroId", id).put("message", "Macro started")
    }

    public fun runInline(steps: JSONArray, service: InputService, loopCount: Int = 1): JSONObject {
        val id = "inline-${UUID.randomUUID().toString().take(6)}"
        val logs = JSONArray()
        executionLogs[id] = logs
        val iterations = if (loopCount <= 0) 10000 else loopCount.coerceAtMost(10000)

        val job = scope.launch {
            try {
                repeat(iterations) { iteration ->
                    for (i in 0 until steps.length()) {
                        if (!isActive) break
                        val step = steps.getJSONObject(i)
                        val result = executeStep(step, service)
                        logs.put(JSONObject().apply {
                            put("iteration", iteration + 1)
                            put("step", i + 1)
                            put("result", result)
                        })
                    }
                }
            } catch (e: CancellationException) {
                logs.put(JSONObject().put("cancelled", true))
            } catch (e: Exception) {
                logs.put(JSONObject().put("error", e.message ?: "unknown"))
            } finally {
                runningJobs.remove(id)
            }
        }
        runningJobs[id] = job
        return JSONObject().put("ok", true).put("runId", id)
    }

    public fun stopMacro(id: String): Boolean {
        val job = runningJobs.remove(id) ?: return false
        job.cancel()
        return true
    }

    public fun getRunningMacros(): JSONArray {
        val arr = JSONArray()
        runningJobs.keys().asIterator().forEach { arr.put(it) }
        return arr
    }

    public fun getExecutionLog(id: String): JSONArray? = executionLogs[id]

    // ==================== Step Execution ====================

    private suspend fun executeStep(step: JSONObject, svc: InputService): String {
        val type = step.optString("type", "api")
        return when (type) {
            "wait" -> {
                delay(step.optLong("ms", 500))
                "waited ${step.optLong("ms", 500)}ms"
            }
            "api" -> {
                val endpoint = step.optString("endpoint", "")
                val params = step.optJSONObject("params") ?: JSONObject()
                executeApiAction(endpoint, params, svc)
                val afterDelay = step.optLong("delay", 0)
                if (afterDelay > 0) delay(afterDelay)
                "ok"
            }
            else -> {
                Log.w(TAG, "Unknown step type: $type")
                "unknown type: $type"
            }
        }
    }

    private fun executeApiAction(endpoint: String, p: JSONObject, svc: InputService) {
        when (endpoint) {
            // Basic controls
            "/tap" -> {
                if (p.has("nx") && p.has("ny")) {
                    svc.tapNormalized(p.getDouble("nx").toFloat(), p.getDouble("ny").toFloat())
                } else {
                    svc.tap(p.getInt("x"), p.getInt("y"))
                }
            }
            "/swipe" -> {
                val dur = p.optLong("duration", 300)
                if (p.has("nx1")) {
                    svc.swipeNormalized(
                        p.getDouble("nx1").toFloat(), p.getDouble("ny1").toFloat(),
                        p.getDouble("nx2").toFloat(), p.getDouble("ny2").toFloat(), dur
                    )
                } else {
                    svc.swipe(p.getInt("x1"), p.getInt("y1"), p.getInt("x2"), p.getInt("y2"), dur)
                }
            }
            "/text" -> svc.inputText(p.getString("text"))
            "/key" -> svc.onKeyEvent(
                p.optBoolean("down", true), p.getLong("keysym"),
                p.optBoolean("shift", false), p.optBoolean("ctrl", false)
            )

            // Navigation
            "/home" -> svc.goHome()
            "/back" -> svc.goBack()
            "/recents" -> svc.showRecents()
            "/notifications" -> svc.showNotifications()
            "/quicksettings" -> svc.showQuickSettings()

            // System
            "/volume/up" -> svc.volumeUp()
            "/volume/down" -> svc.volumeDown()
            "/lock" -> svc.lockScreen()
            "/wake" -> svc.wakeScreen()
            "/power" -> svc.showPowerDialog()
            "/screenshot" -> svc.takeScreenshot()
            "/splitscreen" -> svc.toggleSplitScreen()

            // Brightness
            "/brightness" -> svc.setBrightness(p.getInt("level"))

            // Enhanced Gestures
            "/longpress" -> {
                val dur = p.optLong("duration", 0)
                if (p.has("nx")) {
                    svc.longPressNormalized(p.getDouble("nx").toFloat(), p.getDouble("ny").toFloat(), dur)
                } else {
                    svc.longPressAt(p.getInt("x"), p.getInt("y"), dur)
                }
            }
            "/doubletap" -> {
                if (p.has("nx")) {
                    svc.doubleTapNormalized(p.getDouble("nx").toFloat(), p.getDouble("ny").toFloat())
                } else {
                    svc.doubleTapAt(p.getInt("x"), p.getInt("y"))
                }
            }
            "/scroll" -> {
                svc.scrollNormalized(
                    p.optDouble("nx", 0.5).toFloat(), p.optDouble("ny", 0.5).toFloat(),
                    p.optString("direction", "down"), p.optInt("distance", 500)
                )
            }
            "/pinch" -> {
                svc.pinchZoom(
                    p.optDouble("cx", 0.5).toFloat(), p.optDouble("cy", 0.5).toFloat(),
                    p.optBoolean("zoomIn", true)
                )
            }

            // App management
            "/openapp" -> svc.openApp(p.getString("packageName"))
            "/openurl" -> svc.openUrl(p.getString("url"))

            // AI Brain
            "/findclick" -> {
                val text = p.optString("text", "")
                val id = p.optString("id", "")
                when {
                    text.isNotEmpty() -> svc.findAndClickByText(text)
                    id.isNotEmpty() -> svc.findAndClickById(id)
                }
            }
            "/dismiss" -> svc.dismissTopDialog()
            "/settext" -> svc.setNodeText(p.optString("search", ""), p.optString("value", ""))

            else -> Log.w(TAG, "Unknown macro endpoint: $endpoint")
        }
    }
}
