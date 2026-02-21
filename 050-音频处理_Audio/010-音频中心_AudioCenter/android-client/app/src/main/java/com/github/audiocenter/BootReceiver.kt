package com.github.audiocenter

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Build
import android.util.Log

class BootReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        val action = intent.action
        Log.d("AudioCenter", "Received intent: $action")

        when (action) {
            Intent.ACTION_BOOT_COMPLETED,
            "com.github.audiocenter.ACTION_START" -> {
                startService(context)
            }
            "com.github.audiocenter.ACTION_STOP" -> {
                stopService(context)
            }
        }
    }

    private fun startService(context: Context) {
        val serviceIntent = Intent(context, AudioStreamingService::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            context.startForegroundService(serviceIntent)
        } else {
            context.startService(serviceIntent)
        }
    }

    private fun stopService(context: Context) {
        val serviceIntent = Intent(context, AudioStreamingService::class.java)
        context.stopService(serviceIntent)
    }
}
