package info.dvkr.screenstream.common

import android.content.Context
import android.content.Intent
import android.os.Handler
import android.os.Looper
import android.util.Log
import info.dvkr.screenstream.common.module.StreamingModuleManager
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.firstOrNull
import kotlinx.coroutines.runBlocking
import org.json.JSONArray
import org.json.JSONObject
import org.koin.core.context.GlobalContext

public object AgentBridge {

    private const val TAG = "AgentBridge"

    @Volatile
    private var projectionIntent: Intent? = null

    @Volatile
    private var projectionGranted: Boolean = false

    @JvmStatic
    public fun storeProjectionIntent(intent: Intent) {
        projectionIntent = intent
        projectionGranted = true
        Log.i(TAG, "Projection intent stored")
    }

    @JvmStatic
    public fun getStoredProjectionIntent(): Intent? = projectionIntent

    @JvmStatic
    public fun hasProjectionIntent(): Boolean = projectionIntent != null

    @JvmStatic
    public fun isProjectionGranted(): Boolean = projectionGranted

    @JvmStatic
    public fun getStreamingStatus(): JSONObject {
        val json = JSONObject()
        try {
            val koin = GlobalContext.getOrNull()
            if (koin == null) {
                json.put("error", "Koin not initialized")
                return json
            }
            val manager: StreamingModuleManager = koin.get()
            val activeModule = manager.activeModuleStateFlow.value
            json.put("moduleActive", activeModule != null)
            json.put("moduleId", activeModule?.id?.value ?: "none")
            val isStreaming = activeModule?.let {
                runBlocking { it.isStreaming.first() }
            } ?: false
            json.put("isStreaming", isStreaming)
            val isRunning = activeModule?.let {
                runBlocking { it.isRunning.first() }
            } ?: false
            json.put("isRunning", isRunning)
            json.put("hasProjectionIntent", projectionIntent != null)
            json.put("projectionGranted", projectionGranted)
            val selectedId = runBlocking {
                manager.selectedModuleIdFlow.firstOrNull()?.value ?: "unknown"
            }
            json.put("selectedModule", selectedId)
            val modules = JSONArray()
            manager.modules.forEach { modules.put(it.id.value) }
            json.put("availableModules", modules)
        } catch (e: Exception) {
            json.put("error", e.message ?: "Unknown error")
        }
        return json
    }

    @JvmStatic
    public fun startModule(context: Context, callback: ((Boolean, String) -> Unit)? = null) {
        Handler(Looper.getMainLooper()).post {
            try {
                val manager: StreamingModuleManager = GlobalContext.get().get()
                val moduleId = runBlocking { manager.selectedModuleIdFlow.first() }
                if (manager.isActive(moduleId)) {
                    callback?.invoke(true, "Module $moduleId already active")
                    return@post
                }
                runBlocking { manager.startModule(moduleId, context) }
                callback?.invoke(true, "Module $moduleId started")
            } catch (e: Exception) {
                callback?.invoke(false, e.message ?: "Unknown error")
            }
        }
    }

    @JvmStatic
    public fun startStream(callback: ((Boolean, String) -> Unit)? = null) {
        Handler(Looper.getMainLooper()).post {
            try {
                val intent = projectionIntent
                if (intent == null) {
                    callback?.invoke(false, "No projection intent stored. Grant MediaProjection first.")
                    return@post
                }
                val manager: StreamingModuleManager = GlobalContext.get().get()
                val activeModule = manager.activeModuleStateFlow.value
                if (activeModule == null) {
                    callback?.invoke(false, "No active streaming module")
                    return@post
                }
                val isStreaming = runBlocking { activeModule.isStreaming.first() }
                if (isStreaming) {
                    callback?.invoke(true, "Already streaming")
                    return@post
                }
                // Use reflection to call sendEvent(MjpegEvent.StartProjection(intent)) on main thread
                val eventClass = Class.forName("info.dvkr.screenstream.mjpeg.internal.MjpegEvent\$StartProjection")
                val event = eventClass.getConstructor(Intent::class.java).newInstance(intent)
                val mjpegEventClass = Class.forName("info.dvkr.screenstream.mjpeg.internal.MjpegEvent")
                // Find sendEvent method - may be name-mangled by Kotlin internal visibility
                val sendEvent = activeModule.javaClass.declaredMethods.firstOrNull { m ->
                    m.name.startsWith("sendEvent") && m.parameterCount == 1 && mjpegEventClass.isAssignableFrom(m.parameterTypes[0])
                } ?: activeModule.javaClass.methods.firstOrNull { m ->
                    m.name.startsWith("sendEvent") && m.parameterCount == 1 && mjpegEventClass.isAssignableFrom(m.parameterTypes[0])
                }
                if (sendEvent == null) {
                    val allMethods = activeModule.javaClass.declaredMethods.map { "${it.name}(${it.parameterTypes.joinToString { t -> t.simpleName }})" }
                    callback?.invoke(false, "sendEvent not found. Methods: ${allMethods.filter { it.contains("send") || it.contains("Event") }.take(10)}")
                    return@post
                }
                sendEvent.isAccessible = true
                sendEvent.invoke(activeModule, event)
                // Poll up to 8s for isStreaming to become true
                var waited = 0
                while (waited < 16) {
                    Thread.sleep(500)
                    val nowStreaming = runBlocking { activeModule.isStreaming.first() }
                    if (nowStreaming) {
                        callback?.invoke(true, "Stream started")
                        return@post
                    }
                    waited++
                }
                // Check if module is still running after timeout
                val stillRunning = runBlocking { activeModule.isRunning.first() }
                val msg = if (stillRunning) "Start event sent but isStreaming never became true. Check serverPort conflict or BindException in app logs." else "Module stopped during stream start."
                callback?.invoke(false, msg)
            } catch (e: Exception) {
                Log.e(TAG, "startStream failed", e)
                callback?.invoke(false, "startStream error: ${e.message}")
            }
        }
    }

    @JvmStatic
    public fun stopStream(callback: ((Boolean, String) -> Unit)? = null) {
        Handler(Looper.getMainLooper()).post {
            try {
                val manager: StreamingModuleManager = GlobalContext.get().get()
                val activeModule = manager.activeModuleStateFlow.value
                if (activeModule != null) {
                    activeModule.stopStream("Agent request via AgentBridge")
                    callback?.invoke(true, "Stream stopped")
                } else {
                    callback?.invoke(false, "No active streaming module")
                }
            } catch (e: Exception) {
                callback?.invoke(false, e.message ?: "Unknown error")
            }
        }
    }

    @JvmStatic
    public fun stopModule(callback: ((Boolean, String) -> Unit)? = null) {
        Handler(Looper.getMainLooper()).post {
            try {
                val manager: StreamingModuleManager = GlobalContext.get().get()
                runBlocking { manager.stopModule() }
                callback?.invoke(true, "Module stopped")
            } catch (e: Exception) {
                callback?.invoke(false, e.message ?: "Unknown error")
            }
        }
    }

    @JvmStatic
    public fun getFullStatus(context: Context): JSONObject {
        val json = JSONObject()
        try {
            json.put("streaming", getStreamingStatus())
            json.put("inputServiceConnected", try {
                Class.forName("info.dvkr.screenstream.input.InputService")
                    .getMethod("isConnected").invoke(null) as Boolean
            } catch (ex: Exception) { false })
            json.put("package", context.packageName)
            json.put("timestamp", System.currentTimeMillis())
        } catch (e: Exception) {
            json.put("error", e.message)
        }
        return json
    }
}
