package info.dvkr.screenstream

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Handler
import android.os.Looper
import android.util.Log
import info.dvkr.screenstream.common.AgentBridge
import info.dvkr.screenstream.mjpeg.settings.MjpegSettings
import info.dvkr.screenstream.common.module.StreamingModuleManager
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.GlobalScope
import kotlinx.coroutines.launch
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import info.dvkr.screenstream.ui.AccessibilityAutoEnable
import org.koin.core.context.GlobalContext

/**
 * Agent & Development control receiver for automated workflows.
 * Eliminates manual phone interaction — full Agent programmatic control.
 *
 * Usage:
 *   adb shell am broadcast -a com.screenstream.DEV_CONTROL \
 *     --es command <cmd> [--ei port <int>] [--ez start_app <bool>] [--ez skip_a11y <bool>] \
 *     -n info.dvkr.screenstream.dev/info.dvkr.screenstream.DevControlReceiver
 *
 * Commands (--es command):
 *   start_module    Start streaming module (foreground service)
 *   stop_module     Stop streaming module entirely
 *   start_stream    Start screen capture (requires prior projection grant)
 *   stop_stream     Stop screen capture (module stays running)
 *   grant_project   Launch AgentProjectionActivity for MediaProjection consent
 *   status          Log current streaming/agent status
 *   full_setup      Complete setup: a11y + module + projection grant (one-shot)
 *
 * Legacy parameters (still supported):
 *   --ei port <int>        Set HTTP server port (1025-65535)
 *   --ez start_app <bool>  Launch SingleActivity (default true)
 *   --ez skip_a11y <bool>  Skip AccessibilityService auto-enable (default false)
 */
public class DevControlReceiver : BroadcastReceiver() {

    companion object {
        private const val TAG = "DevControlReceiver"
        const val ACTION = "com.screenstream.DEV_CONTROL"
    }

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != ACTION) return

        val command = intent.getStringExtra("command") ?: ""
        Log.i(TAG, "Received DEV_CONTROL: command=$command")

        // Handle command-based Agent control
        when (command) {
            "start_module" -> handleStartModule(context)
            "stop_module" -> handleStopModule()
            "start_stream" -> handleStartStream(context)
            "stop_stream" -> handleStopStream()
            "grant_project" -> handleGrantProjection(context)
            "status" -> handleStatus(context)
            "full_setup" -> handleFullSetup(context, intent)
            else -> handleLegacy(context, intent)
        }
    }

    private fun handleStartModule(context: Context) {
        AgentBridge.startModule(context) { ok, msg ->
            Log.i(TAG, "start_module: ok=$ok msg=$msg")
        }
    }

    private fun handleStopModule() {
        AgentBridge.stopModule { ok, msg ->
            Log.i(TAG, "stop_module: ok=$ok msg=$msg")
        }
    }

    private fun handleStartStream(context: Context) {
        val storedIntent = AgentBridge.getStoredProjectionIntent()
        if (storedIntent != null) {
            // Reuse stored projection intent — zero UI interaction
            Handler(Looper.getMainLooper()).post {
                try {
                    val manager: StreamingModuleManager = GlobalContext.get().get()
                    val activeModule = manager.activeModuleStateFlow.value

                    if (activeModule == null) {
                        Log.w(TAG, "start_stream: No active module. Starting module first...")
                        AgentBridge.startModule(context) { ok, _ ->
                            if (ok) {
                                // Retry after module starts
                                Handler(Looper.getMainLooper()).postDelayed({
                                    sendProjectionEvent(storedIntent)
                                }, 1000)
                            }
                        }
                        return@post
                    }

                    sendProjectionEvent(storedIntent)
                } catch (e: Exception) {
                    Log.e(TAG, "start_stream error: ${e.message}")
                }
            }
        } else {
            Log.w(TAG, "start_stream: No stored projection intent. Run 'grant_project' first.")
            handleGrantProjection(context)
        }
    }

    private fun sendProjectionEvent(intent: Intent) {
        try {
            val manager: StreamingModuleManager = GlobalContext.get().get()
            val activeModule = manager.activeModuleStateFlow.value
            if (activeModule == null) {
                Log.w(TAG, "No active streaming module")
                return
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
                return
            }
            sendEvent.isAccessible = true
            sendEvent.invoke(activeModule, event)
            Log.i(TAG, "StartProjection event sent via reflection")
        } catch (e: Exception) {
            Log.e(TAG, "sendProjectionEvent error: ${e.message}")
        }
    }

    private fun handleStopStream() {
        AgentBridge.stopStream { ok, msg ->
            Log.i(TAG, "stop_stream: ok=$ok msg=$msg")
        }
    }

    private fun handleGrantProjection(context: Context) {
        try {
            val projIntent = Intent(context, AgentProjectionActivity::class.java).apply {
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                putExtra("auto_finish", true)
                putExtra("start_stream", true)
                putExtra("start_module", true)
            }
            context.startActivity(projIntent)
            Log.i(TAG, "AgentProjectionActivity launched for MediaProjection grant")
        } catch (e: Exception) {
            Log.e(TAG, "grant_project failed: ${e.message}")
        }
    }

    private fun handleStatus(context: Context) {
        val status = AgentBridge.getFullStatus(context)
        Log.i(TAG, "Agent Status: $status")
    }

    private fun handleFullSetup(context: Context, intent: Intent) {
        Log.i(TAG, "full_setup: Starting complete Agent setup...")

        // Step 1: Auto-enable AccessibilityService
        try {
            if (!AccessibilityAutoEnable.isAccessibilityEnabled(context)) {
                GlobalScope.launch(Dispatchers.IO) {
                    val result = AccessibilityAutoEnable.enable(context)
                    Log.i(TAG, "full_setup: A11y: ${result.method} → ${result.message}")
                }
            } else {
                Log.i(TAG, "full_setup: A11y already enabled")
            }
        } catch (e: Exception) {
            Log.e(TAG, "full_setup: A11y failed: ${e.message}")
        }

        // Step 2: Set port if provided
        val port = intent.getIntExtra("port", -1)
        if (port in 1025..65535) {
            setPort(port)
        }

        // Step 3: Start module + request projection
        AgentBridge.startModule(context) { ok, msg ->
            Log.i(TAG, "full_setup: Module: ok=$ok msg=$msg")
            if (ok) {
                // Step 4: Launch projection activity
                Handler(Looper.getMainLooper()).postDelayed({
                    handleGrantProjection(context)
                }, 500)
            }
        }
    }

    private fun handleLegacy(context: Context, intent: Intent) {
        // 1. Set server port if provided
        val port = intent.getIntExtra("port", -1)
        if (port in 1025..65535) {
            setPort(port)
        }

        // 2. Auto-enable AccessibilityService
        val skipA11y = intent.getBooleanExtra("skip_a11y", false)
        if (!skipA11y) {
            try {
                if (!AccessibilityAutoEnable.isAccessibilityEnabled(context)) {
                    GlobalScope.launch(Dispatchers.IO) {
                        val result = AccessibilityAutoEnable.enable(context)
                        Log.i(TAG, "A11y auto-enable: ${result.method} → ${result.message}")
                    }
                } else {
                    Log.i(TAG, "AccessibilityService already enabled")
                }
            } catch (e: Exception) {
                Log.e(TAG, "A11y auto-enable failed: ${e.message}")
            }
        }

        // 3. Launch app if requested (default: true)
        val startApp = intent.getBooleanExtra("start_app", true)
        if (startApp) {
            try {
                val launchIntent = Intent(context, SingleActivity::class.java).apply {
                    addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP)
                }
                context.startActivity(launchIntent)
                Log.i(TAG, "App launched via DEV_CONTROL")
            } catch (e: Exception) {
                Log.e(TAG, "Failed to launch app: ${e.message}")
            }
        }
    }

    private fun setPort(port: Int) {
        try {
            val koin = GlobalContext.get()
            val mjpegSettings: MjpegSettings = koin.get()
            val currentPort = mjpegSettings.data.value.serverPort
            if (currentPort != port) {
                runBlocking {
                    mjpegSettings.updateData { copy(serverPort = port) }
                }
                Log.i(TAG, "Server port changed: $currentPort → $port")
            } else {
                Log.i(TAG, "Server port already $port")
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to set port: ${e.message}")
        }
    }
}
