package com.ffalcon.mars.android.sdk.demo

import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageInstaller
import android.os.Build
import java.io.File
import java.io.FileInputStream

object SilentInstaller {

    private const val ACTION_INSTALL_COMPLETE = "com.your.package.INSTALL_COMPLETE"

    fun installAndRestart(context: Context, apkFile: File) {
        val packageInstaller = context.packageManager.packageInstaller
        val sessionParams = PackageInstaller.SessionParams(
            PackageInstaller.SessionParams.MODE_FULL_INSTALL
        ).apply {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                setRequireUserAction(PackageInstaller.SessionParams.USER_ACTION_NOT_REQUIRED)
            }
        }

        // 注册广播接收器（监听安装完成）
        val receiver = SilentInstallerReceiver()
        context.registerReceiver(receiver, IntentFilter(ACTION_INSTALL_COMPLETE))

        try {
            // 创建安装会话
            val sessionId = packageInstaller.createSession(sessionParams)
            val session = packageInstaller.openSession(sessionId)

            // 写入 APK
            FileInputStream(apkFile).use { apkStream ->
                session.openWrite("package.apk", 0, apkFile.length()).use { sessionStream ->
                    apkStream.copyTo(sessionStream)
                    session.fsync(sessionStream)
                }
            }

            // 使用显式 Intent
            val intent = Intent(context, SilentInstallerReceiver::class.java).apply {
                action = ACTION_INSTALL_COMPLETE
            }

            // 提交安装（绑定广播接收器）
            val pendingIntent = PendingIntent.getBroadcast(
                context,
                0,
                intent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            )
            session.commit(pendingIntent.intentSender)

        } catch (e: Exception) {
            e.printStackTrace()
            context.unregisterReceiver(receiver) // 防止内存泄漏
        }
    }


    class SilentInstallerReceiver : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) {
            val status = intent.getIntExtra(PackageInstaller.EXTRA_STATUS, -1)
            if (status == PackageInstaller.STATUS_SUCCESS) {
                // 安装成功，启动应用
                val launchIntent =
                    context.packageManager.getLaunchIntentForPackage(context.packageName)
                launchIntent?.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                context.startActivity(launchIntent)
            }
            // 注销广播接收器
            context.unregisterReceiver(this)
        }
    }
}