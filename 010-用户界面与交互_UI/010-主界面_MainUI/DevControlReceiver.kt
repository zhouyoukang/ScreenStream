package info.dvkr.screenstream

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log
import info.dvkr.screenstream.mjpeg.settings.MjpegSettings
import kotlinx.coroutines.runBlocking
import org.koin.core.context.GlobalContext

/**
 * Development control receiver for automated deployment workflows.
 * Eliminates manual phone interaction during build-deploy-test cycles.
 *
 * Usage:
 *   adb shell am broadcast -a com.screenstream.DEV_CONTROL --ei port 8086 -n info.dvkr.screenstream.dev/info.dvkr.screenstream.DevControlReceiver
 *
 * Parameters:
 *   --ei port <int>       Set HTTP server port (1025-65535, default 8080)
 *   --ez start_app <bool> Launch SingleActivity (default true)
 */
public class DevControlReceiver : BroadcastReceiver() {

    companion object {
        private const val TAG = "DevControlReceiver"
        const val ACTION = "com.screenstream.DEV_CONTROL"
    }

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != ACTION) return

        Log.i(TAG, "Received DEV_CONTROL broadcast")

        // 1. Set server port if provided
        val port = intent.getIntExtra("port", -1)
        if (port in 1025..65535) {
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
                    Log.i(TAG, "Server port already $port, no change needed")
                }
            } catch (e: Exception) {
                Log.e(TAG, "Failed to set port: ${e.message}")
            }
        }

        // 2. Launch app if requested (default: true)
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
}
