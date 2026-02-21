package com.github.audiocenter.receiver

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioTrack
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import okhttp3.*
import okio.ByteString
import timber.log.Timber
import java.util.concurrent.TimeUnit

class PlayerService : Service() {

    private var audioTrack: AudioTrack? = null
    private var webSocket: WebSocket? = null
    private val client = OkHttpClient.Builder()
        .readTimeout(0, TimeUnit.MILLISECONDS) // Keep connection open
        .build()

    private var targetIp: String = ""
    private var isRunning = false

    companion object {
        const val CHANNEL_ID = "AudioReceiverChannel"
        const val EXTRA_IP = "TargetIp"
        const val ACTION_STOP = "com.github.audiocenter.receiver.STOP"
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            stopSelf()
            return START_NOT_STICKY
        }

        val ip = intent?.getStringExtra(EXTRA_IP)
        if (ip != null && ip != targetIp) {
            targetIp = ip
            startFullService()
        }

        return START_STICKY
    }

    private fun startFullService() {
        if (isRunning) return
        isRunning = true

        createNotificationChannel()
        val stopIntent = Intent(this, PlayerService::class.java).apply { action = ACTION_STOP }
        val pendingStop = PendingIntent.getService(this, 0, stopIntent, PendingIntent.FLAG_IMMUTABLE)

        val notification = NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Audio Receiver Active")
            .setContentText("Listening to $targetIp")
            .setSmallIcon(android.R.drawable.ic_lock_silent_mode_off)
            .addAction(android.R.drawable.ic_menu_close_clear_cancel, "Stop", pendingStop)
            .setOngoing(true)
            .build()

        startForeground(1, notification)

        initAudioTrack()
        connectWebSocket()
    }

    private fun initAudioTrack() {
        val sampleRate = 16000 // Must match Sender
        val channelConfig = AudioFormat.CHANNEL_OUT_MONO
        val audioFormat = AudioFormat.ENCODING_PCM_16BIT
        val minBufferSize = AudioTrack.getMinBufferSize(sampleRate, channelConfig, audioFormat)
        
        // Use a slightly larger buffer for network stability
        val bufferSize = maxOf(minBufferSize, 16000 * 2 * (150 / 1000)) // ~150ms buffer

        audioTrack = AudioTrack.Builder()
            .setAudioAttributes(
                AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_MEDIA)
                    .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC)
                    .build()
            )
            .setAudioFormat(
                AudioFormat.Builder()
                    .setEncoding(audioFormat)
                    .setSampleRate(sampleRate)
                    .setChannelMask(channelConfig)
                    .build()
            )
            .setBufferSizeInBytes(bufferSize)
            .setTransferMode(AudioTrack.MODE_STREAM)
            .build()

        audioTrack?.play()
        Timber.d("AudioTrack started. Buffer size: $bufferSize bytes")
    }

    private fun connectWebSocket() {
        val request = Request.Builder()
            .url("ws://$targetIp:8085/stream/audio")
            .build()

        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                Timber.d("WebSocket Connected to $targetIp")
            }

            override fun onMessage(webSocket: WebSocket, bytes: ByteString) {
                // Determine format
                // Our sender sends 16-bit PCM.
                val data = bytes.toByteArray()
                audioTrack?.write(data, 0, data.size)
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                Timber.w("WebSocket Closing: $reason")
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Timber.e(t, "WebSocket Failure")
                tryReconnect()
            }
        })
    }
    
    private fun tryReconnect() {
        if (!isRunning) return
        Thread.sleep(3000)
        Timber.d("Reconnecting...")
        if (isRunning) connectWebSocket()
    }

    override fun onDestroy() {
        super.onDestroy()
        isRunning = false
        webSocket?.close(1000, "Service Stopped")
        audioTrack?.stop()
        audioTrack?.release()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val serviceChannel = NotificationChannel(
                CHANNEL_ID,
                "Audio Receiver Service",
                NotificationManager.IMPORTANCE_LOW
            )
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(serviceChannel)
        }
    }
}
