package info.dvkr.screenstream

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.util.Log
import info.dvkr.screenstream.common.AgentBridge
import info.dvkr.screenstream.common.module.StreamingModuleManager
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.koin.core.context.GlobalContext

/**
 * AgentProjectionActivity — Transparent Activity for programmatic MediaProjection grant.
 *
 * Launched via ADB to handle the one-time MediaProjection consent dialog:
 *   adb shell am start -n info.dvkr.screenstream.dev/info.dvkr.screenstream.AgentProjectionActivity
 *
 * Flow:
 *   1. Activity launches (transparent, no visible UI)
 *   2. Requests MediaProjection permission (system dialog appears)
 *   3. User approves (one-time tap on "Start now")
 *   4. Stores projection intent in AgentBridge for reuse
 *   5. Sends StartProjection event to active streaming module
 *   6. Auto-finishes (Activity disappears)
 *
 * After first approval, subsequent streaming starts can use stored intent
 * via HTTP API (/stream/start) or ADB broadcast without any UI interaction.
 *
 * Optional extras:
 *   --ez auto_finish true    Auto-finish after granting (default: true)
 *   --ez start_stream true   Also start streaming after grant (default: true)
 *   --ez start_module true   Start streaming module first if not running (default: true)
 */
public class AgentProjectionActivity : Activity() {

    companion object {
        private const val TAG = "AgentProjection"
        private const val REQUEST_CODE_PROJECTION = 9001
    }

    private var autoFinish = true
    private var startStream = true
    private var startModule = true

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        autoFinish = intent?.getBooleanExtra("auto_finish", true) ?: true
        startStream = intent?.getBooleanExtra("start_stream", true) ?: true
        startModule = intent?.getBooleanExtra("start_module", true) ?: true

        Log.i(TAG, "onCreate: autoFinish=$autoFinish startStream=$startStream startModule=$startModule")

        // Ensure streaming module is started first
        if (startModule) {
            ensureModuleStarted()
        }

        // Request MediaProjection permission
        requestProjection()
    }

    private fun ensureModuleStarted() {
        try {
            val koin = GlobalContext.getOrNull() ?: return
            val manager: StreamingModuleManager = koin.get()
            val moduleId = runBlocking { manager.selectedModuleIdFlow.first() }

            if (!manager.isActive(moduleId)) {
                Log.i(TAG, "Starting module: $moduleId")
                Handler(Looper.getMainLooper()).post {
                    runBlocking { manager.startModule(moduleId, this@AgentProjectionActivity) }
                }
                // Give service time to start
                Thread.sleep(500)
            } else {
                Log.i(TAG, "Module already active: $moduleId")
            }
        } catch (e: Exception) {
            Log.e(TAG, "ensureModuleStarted error: ${e.message}")
        }
    }

    private fun requestProjection() {
        val projectionManager = getSystemService(Context.MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
        val captureIntent = projectionManager.createScreenCaptureIntent()
        Log.i(TAG, "Requesting MediaProjection permission...")

        @Suppress("DEPRECATION")
        startActivityForResult(captureIntent, REQUEST_CODE_PROJECTION)
    }

    @Suppress("DEPRECATION")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)

        if (requestCode != REQUEST_CODE_PROJECTION) {
            Log.w(TAG, "Unknown request code: $requestCode")
            finishIfAuto()
            return
        }

        if (resultCode != RESULT_OK || data == null) {
            Log.w(TAG, "MediaProjection denied (resultCode=$resultCode)")
            finishIfAuto()
            return
        }

        Log.i(TAG, "MediaProjection GRANTED!")

        // Store intent for reuse via AgentBridge
        AgentBridge.storeProjectionIntent(data)

        // Send StartProjection event to the active MJPEG streaming module
        if (startStream) {
            sendProjectionToModule(data)
        }

        finishIfAuto()
    }

    private fun sendProjectionToModule(intent: Intent) {
        Handler(Looper.getMainLooper()).post {
            try {
                val koin = GlobalContext.getOrNull() ?: return@post
                val manager: StreamingModuleManager = koin.get()
                val activeModule = manager.activeModuleStateFlow.value
                if (activeModule == null) {
                    Log.w(TAG, "No active streaming module")
                    return@post
                }
                // Use reflection to avoid internal visibility issue with MjpegEvent
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
                    Log.e(TAG, "sendEvent method not found on ${activeModule.javaClass.name}")
                    return@post
                }
                sendEvent.isAccessible = true
                sendEvent.invoke(activeModule, event)
                Log.i(TAG, "StartProjection event sent via reflection")
            } catch (e: Exception) {
                Log.e(TAG, "sendProjectionToModule error: ${e.message}")
            }
        }
    }

    private fun finishIfAuto() {
        if (autoFinish) {
            Log.i(TAG, "Auto-finishing activity")
            finish()
        }
    }
}
