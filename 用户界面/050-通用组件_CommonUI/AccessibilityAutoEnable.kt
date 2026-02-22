package info.dvkr.screenstream.ui

import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.provider.Settings
import com.elvishew.xlog.XLog
import info.dvkr.screenstream.common.getLog
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.BufferedReader

/**
 * 三级自动启用 AccessibilityService 策略:
 *   L1 Root (su)     — Magisk/KernelSU 设备直接写 Settings.Secure
 *   L2 Shizuku/Sui   — 用户安装 Shizuku 应用或 Sui 模块后，通过 API 以 shell 身份操作
 *   L3 Manual         — 引导用户手动开启（兜底）
 */
object AccessibilityAutoEnable {

    private const val TAG = "A11yAutoEnable"

    enum class Method { ROOT, SHIZUKU, MANUAL }

    data class Result(
        val success: Boolean,
        val method: Method,
        val message: String
    )

    private fun getServiceComponent(context: Context): String {
        val pkg = context.packageName
        return "$pkg/info.dvkr.screenstream.input.InputService"
    }

    // ========== Public API ==========

    fun isAccessibilityEnabled(context: Context): Boolean {
        val component = getServiceComponent(context)
        val enabledServices = Settings.Secure.getString(
            context.contentResolver, Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES
        ) ?: return false
        return component in enabledServices
    }

    fun detectBestMethod(): Method {
        if (isRootAvailable()) return Method.ROOT
        if (isShizukuAvailable()) return Method.SHIZUKU
        return Method.MANUAL
    }

    suspend fun enable(context: Context): Result = withContext(Dispatchers.IO) {
        val component = getServiceComponent(context)

        if (isAccessibilityEnabled(context)) {
            return@withContext Result(true, Method.MANUAL, "Already enabled")
        }

        // L1: Root
        if (isRootAvailable()) {
            val ok = tryEnableViaRoot(component)
            if (ok) {
                XLog.i(getLog(TAG, "Enabled via ROOT"))
                return@withContext Result(true, Method.ROOT, "Enabled via root (su)")
            }
        }

        // L2: Shizuku
        if (isShizukuAvailable()) {
            val ok = tryEnableViaShizuku(component)
            if (ok) {
                XLog.i(getLog(TAG, "Enabled via SHIZUKU"))
                return@withContext Result(true, Method.SHIZUKU, "Enabled via Shizuku")
            }
        }

        // L3: Manual
        XLog.w(getLog(TAG, "No auto-enable method available, opening settings"))
        Result(false, Method.MANUAL, "Please enable manually in Settings")
    }

    fun openAccessibilitySettings(context: Context) {
        try {
            context.startActivity(
                Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            )
        } catch (e: Exception) {
            XLog.e(getLog(TAG, "Failed to open accessibility settings: ${e.message}"))
        }
    }

    // ========== L1: Root ==========

    private fun isRootAvailable(): Boolean {
        return try {
            val process = Runtime.getRuntime().exec(arrayOf("su", "-c", "id"))
            val exitCode = process.waitFor()
            process.destroy()
            exitCode == 0
        } catch (e: Exception) {
            false
        }
    }

    private fun tryEnableViaRoot(component: String): Boolean {
        return try {
            val current = execCommand("su", "-c", "settings get secure enabled_accessibility_services")
                .trim()

            if (component in current) return true

            val newValue = if (current == "null" || current.isBlank()) {
                component
            } else {
                "$current:$component"
            }

            execCommand("su", "-c", "settings put secure enabled_accessibility_services $newValue")
            execCommand("su", "-c", "settings put secure accessibility_enabled 1")

            // Verify
            val verify = execCommand("su", "-c", "settings get secure enabled_accessibility_services").trim()
            component in verify
        } catch (e: Exception) {
            XLog.e(getLog(TAG, "Root enable failed: ${e.message}"))
            false
        }
    }

    // ========== L2: Shizuku ==========

    private fun isShizukuAvailable(): Boolean {
        return try {
            if (Build.VERSION.SDK_INT < 23) return false
            val shizukuClass = Class.forName("rikka.shizuku.Shizuku")
            val pingMethod = shizukuClass.getMethod("pingBinder")
            pingMethod.invoke(null) as Boolean
        } catch (e: Exception) {
            false
        }
    }

    private fun tryEnableViaShizuku(component: String): Boolean {
        return try {
            if (Build.VERSION.SDK_INT < 23) return false

            val shizukuClass = Class.forName("rikka.shizuku.Shizuku")

            // Check permission
            val checkPerm = shizukuClass.getMethod("checkSelfPermission")
            val granted = checkPerm.invoke(null) as Int
            if (granted != PackageManager.PERMISSION_GRANTED) {
                XLog.w(getLog(TAG, "Shizuku permission not granted"))
                return false
            }

            // Use Shizuku's newProcess to execute settings command
            // (deprecated but simplest for one-off commands)
            val current = execViaShizuku("settings get secure enabled_accessibility_services").trim()

            val newValue = if (current == "null" || current.isBlank() || component in current) {
                if (component in current) return true
                component
            } else {
                "$current:$component"
            }

            execViaShizuku("settings put secure enabled_accessibility_services $newValue")
            execViaShizuku("settings put secure accessibility_enabled 1")

            val verify = execViaShizuku("settings get secure enabled_accessibility_services").trim()
            component in verify
        } catch (e: Exception) {
            XLog.e(getLog(TAG, "Shizuku enable failed: ${e.message}"))
            false
        }
    }

    private fun execViaShizuku(command: String): String {
        val shizukuClass = Class.forName("rikka.shizuku.Shizuku")
        val newProcessMethod = shizukuClass.getMethod(
            "newProcess",
            Array<String>::class.java,
            Array<String>::class.java,
            String::class.java
        )
        val process = newProcessMethod.invoke(
            null,
            arrayOf("sh", "-c", command),
            null,
            null
        ) as Process
        val output = process.inputStream.bufferedReader().readText()
        process.waitFor()
        process.destroy()
        return output
    }

    // ========== Util ==========

    private fun execCommand(vararg cmd: String): String {
        val process = Runtime.getRuntime().exec(cmd)
        val output = process.inputStream.bufferedReader().readText()
        process.waitFor()
        process.destroy()
        return output
    }
}
