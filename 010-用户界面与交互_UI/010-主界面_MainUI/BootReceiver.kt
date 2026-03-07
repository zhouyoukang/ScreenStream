package info.dvkr.screenstream

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log

public class BootReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Intent.ACTION_BOOT_COMPLETED &&
            intent.action != "android.intent.action.QUICKBOOT_POWERON") return

        val prefs = context.getSharedPreferences("screenstream_boot", Context.MODE_PRIVATE)
        val startOnBoot = prefs.getBoolean("start_on_boot", false)

        Log.i("BootReceiver", "Boot completed, startOnBoot=$startOnBoot")

        if (!startOnBoot) return

        try {
            val launchIntent = Intent(context, SingleActivity::class.java).apply {
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                putExtra("boot_start", true)
            }
            context.startActivity(launchIntent)
            Log.i("BootReceiver", "App launched on boot")
        } catch (e: Exception) {
            Log.e("BootReceiver", "Failed to start on boot: ${e.message}")
        }
    }
}
