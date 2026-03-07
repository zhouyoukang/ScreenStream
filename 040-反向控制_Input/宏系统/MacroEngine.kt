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

    // Trigger engine state
    private var triggerService: InputService? = null
    private val timerJobs = ConcurrentHashMap<String, Job>()
    private var lastForegroundPackage: String = ""
    private val triggerCooldowns = ConcurrentHashMap<String, Long>()
    private val TRIGGER_COOLDOWN_MS = 5000L // Prevent rapid re-triggering

    /**
     * Initialize persistence and trigger engine.
     * Call from InputService.onServiceConnected().
     */
    public fun init(context: Context, service: InputService? = null) {
        storageFile = File(context.filesDir, "macros.json")
        triggerService = service
        loadFromDisk()
        startTimerTriggers()
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

    // ==================== Trigger Engine ====================

    /**
     * Called by InputService when a notification arrives.
     * Checks all macros for matching notification triggers.
     */
    public fun onNotification(packageName: String, title: String, body: String) {
        val svc = triggerService ?: return
        for (entry in macros) {
            val macro = entry.value
            if (!macro.optBoolean("enabled", true)) continue
            val trigger = macro.optJSONObject("trigger") ?: continue
            if (trigger.optString("type") != "notification") continue
            if (!trigger.optBoolean("enabled", true)) continue
            if (!matchesTrigger(trigger, packageName, title, body)) continue
            if (isInCooldown(entry.key)) continue

            Log.i(TAG, "Trigger [notification] fired for macro '${entry.key}' (pkg=$packageName)")
            triggerCooldowns[entry.key] = System.currentTimeMillis()
            runMacro(entry.key, svc)
        }
    }

    /**
     * Called by InputService when the foreground app changes.
     * Checks all macros for matching app_switch triggers.
     */
    public fun onAppSwitch(newPackage: String) {
        if (newPackage == lastForegroundPackage) return
        val oldPackage = lastForegroundPackage
        lastForegroundPackage = newPackage
        val svc = triggerService ?: return

        for (entry in macros) {
            val macro = entry.value
            if (!macro.optBoolean("enabled", true)) continue
            val trigger = macro.optJSONObject("trigger") ?: continue
            if (trigger.optString("type") != "app_switch") continue
            if (!trigger.optBoolean("enabled", true)) continue

            val targetPkg = trigger.optString("package", "")
            val direction = trigger.optString("direction", "enter") // "enter", "leave", "any"
            if (targetPkg.isEmpty()) continue

            val match = when (direction) {
                "enter" -> newPackage.contains(targetPkg, ignoreCase = true)
                "leave" -> oldPackage.contains(targetPkg, ignoreCase = true)
                "any" -> newPackage.contains(targetPkg, ignoreCase = true) || oldPackage.contains(targetPkg, ignoreCase = true)
                else -> false
            }
            if (!match) continue
            if (isInCooldown(entry.key)) continue

            Log.i(TAG, "Trigger [app_switch] fired for macro '${entry.key}' ($oldPackage -> $newPackage)")
            triggerCooldowns[entry.key] = System.currentTimeMillis()
            runMacro(entry.key, svc)
        }
    }

    private fun matchesTrigger(trigger: JSONObject, pkg: String, title: String, body: String): Boolean {
        val filterPkg = trigger.optString("package", "")
        if (filterPkg.isNotEmpty() && !pkg.contains(filterPkg, ignoreCase = true)) return false
        val filterText = trigger.optString("textMatch", "")
        if (filterText.isNotEmpty()) {
            val combined = "$title $body"
            if (!combined.contains(filterText, ignoreCase = true)) return false
        }
        return true
    }

    private fun isInCooldown(macroId: String): Boolean {
        val last = triggerCooldowns[macroId] ?: return false
        return (System.currentTimeMillis() - last) < TRIGGER_COOLDOWN_MS
    }

    /**
     * Start timer-based triggers for all macros that have timer triggers.
     */
    private fun startTimerTriggers() {
        stopAllTimerTriggers()
        for (entry in macros) {
            startTimerTriggerIfNeeded(entry.key, entry.value)
        }
    }

    private fun startTimerTriggerIfNeeded(id: String, macro: JSONObject) {
        if (!macro.optBoolean("enabled", true)) return
        val trigger = macro.optJSONObject("trigger") ?: return
        if (trigger.optString("type") != "timer") return
        if (!trigger.optBoolean("enabled", true)) return
        val intervalMs = trigger.optLong("intervalMs", 0)
        if (intervalMs < 10000) return // Minimum 10 seconds to prevent abuse

        timerJobs[id]?.cancel()
        timerJobs[id] = scope.launch {
            val initialDelay = trigger.optLong("initialDelayMs", intervalMs)
            delay(initialDelay)
            while (isActive) {
                val svc = triggerService
                if (svc != null && !isInCooldown(id)) {
                    Log.i(TAG, "Trigger [timer] fired for macro '$id' (interval=${intervalMs}ms)")
                    triggerCooldowns[id] = System.currentTimeMillis()
                    runMacro(id, svc)
                }
                delay(intervalMs)
            }
        }
    }

    private fun stopAllTimerTriggers() {
        timerJobs.values.forEach { it.cancel() }
        timerJobs.clear()
    }

    /**
     * Set or update a trigger for a macro.
     * trigger JSON: { "type": "notification"|"app_switch"|"timer", "enabled": true, ... }
     */
    public fun setTrigger(macroId: String, trigger: JSONObject): Boolean {
        val macro = macros[macroId] ?: return false
        macro.put("trigger", trigger)
        saveToDisk()
        // Restart timer if applicable
        timerJobs[macroId]?.cancel()
        timerJobs.remove(macroId)
        startTimerTriggerIfNeeded(macroId, macro)
        return true
    }

    /**
     * Remove the trigger from a macro.
     */
    public fun removeTrigger(macroId: String): Boolean {
        val macro = macros[macroId] ?: return false
        macro.remove("trigger")
        timerJobs[macroId]?.cancel()
        timerJobs.remove(macroId)
        saveToDisk()
        return true
    }

    /**
     * List all macros that have triggers configured.
     */
    public fun listTriggers(): JSONArray {
        val arr = JSONArray()
        for (entry in macros) {
            val trigger = entry.value.optJSONObject("trigger") ?: continue
            arr.put(JSONObject().apply {
                put("macroId", entry.key)
                put("macroName", entry.value.optString("name", "unnamed"))
                put("trigger", trigger)
            })
        }
        return arr
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
